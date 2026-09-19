#!/usr/bin/env python3
"""Standalone PySide6 audition app; UI language never changes DSP state."""
from __future__ import annotations
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import sys
import tempfile
import threading
import uuid
import time
import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt, QTimer, Signal, QUrl, QPointF, QSignalBlocker
from PySide6.QtGui import QColor, QPainter, QPen, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSlider, QFileDialog, QTabWidget, QPlainTextEdit)
from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer, QAudioOutput
from native import NATIVE_MODES
from audio_output import OutputPump
from worker import PlayerWorker, Settings
from i18n import I18n, Message, Diagnostic, message
import sdk_compare
import comparison_batch


class Waveform(QWidget):
    seek = Signal(float)
    def __init__(self):
        super().__init__()
        self.values=np.zeros(1); self.duration=0.; self.position=0.; self.frozen=False
        self.anchor_text='SOURCE ANCHOR'
        self.setMinimumHeight(155); self.setCursor(Qt.PointingHandCursor)
    def set_audio(self,wave,frames,rate):
        self.values=np.max(np.abs(wave),axis=1); self.duration=frames/rate; self.position=0; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.fillRect(self.rect(),QColor('#101d29'))
        w,h=self.width(),self.height(); p.setPen(QPen(QColor('#263c4b'),1)); p.drawLine(0,h//2,w,h//2)
        p.setPen(QPen(QColor('#60b4c1'),1.4)); maximum=max(1.,float(self.values.max()))
        for i,v in enumerate(self.values):
            x=i*w/max(1,len(self.values)-1); a=float(v)/maximum*(h*.38)
            p.drawLine(QPointF(x,h/2-a),QPointF(x,h/2+a))
        x=np.clip(self.position/max(self.duration,1e-9),0,1)*w
        p.setPen(QPen(QColor('#ffcc70' if self.frozen else '#faf8f2'),2)); p.drawLine(QPointF(x,10),QPointF(x,h-10))
        p.setPen(QColor('#b8c9d7')); p.drawText(12,23,self.anchor_text)
        p.drawText(12,h-10,f'{self.position:7.3f} s  /  {self.duration:.3f} s')
    def mousePressEvent(self,event):
        if self.duration: self.seek.emit(float(np.clip(event.position().x()/max(1,self.width()),0,1))*self.duration)


class Control(QWidget):
    changed = Signal()
    def __init__(self,title,lo,hi,value,unit,scale=100):
        super().__init__(); self.scale=scale; layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        self.title_label=QLabel(title); layout.addWidget(self.title_label)
        self.spin=QDoubleSpinBox(); self.spin.setRange(lo,hi); self.spin.setDecimals(3 if scale==1000 else 2)
        self.spin.setSingleStep(.01 if scale==1000 else .1); self.spin.setSuffix(' '+unit); self.spin.setValue(value)
        self.slider=QSlider(Qt.Horizontal); self.slider.setRange(round(lo*scale),round(hi*scale)); self.slider.setValue(round(value*scale))
        layout.addWidget(self.spin); layout.addWidget(self.slider)
        self.spin.valueChanged.connect(self._spin); self.slider.valueChanged.connect(lambda v:self.spin.setValue(v/scale))
    def _spin(self,v):
        with QSignalBlocker(self.slider): self.slider.setValue(round(v*self.scale))
        self.changed.emit()
    def value(self): return self.spin.value()
    def setValue(self,v): self.spin.setValue(v)


class MainWindow(QMainWindow):
    def __init__(self,library=None,sdk=None,language=None,preferences=None):
        super().__init__(); self.setWindowTitle('boiled egg — Audition Lab'); self.resize(1110,810)
        self.closing=False; self.closed=False
        self.i18n=I18n(language,preferences)
        self._text_bindings={}; self._combo_bindings=[]; self._log_entries=deque(maxlen=80)
        self.library=library; self.sdk=sdk; self.source_path=None; self.reference_path=None; self.playing=False; self.eof=False
        self.last_speed=1.; self.duration=0.; self.native_ready=False; self.native_busy=False; self.last_state={}; self.comparisons=[]; self.stream_format=None
        self.temporary=tempfile.TemporaryDirectory(prefix='boiled-egg-audition-')
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='sdk-compare'); self.job=None; self.cancel=threading.Event()
        self.worker=PlayerWorker(library); self.worker.start(); self.pump=OutputPump(self.worker.audio,self)
        self.pump.error.connect(self.output_failed); self.pump.telemetry.connect(self.telemetry)
        self.setAcceptDrops(True)
        central=QWidget(); self.setCentralWidget(central); outer=QVBoxLayout(central); outer.setSpacing(12)
        heading=QHBoxLayout()
        title=QLabel('boiled egg   /   AUDITION LAB'); title.setObjectName('title'); heading.addWidget(title,1)
        heading.addWidget(self.label('language'))
        self.language_combo=QComboBox(); self.language_combo.setObjectName('languageSelector')
        self.language_combo.setAccessibleName('Language / 言語')
        self.language_combo.addItem('日本語','ja'); self.language_combo.addItem('English','en')
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.i18n.language))
        heading.addWidget(self.language_combo); outer.addLayout(heading)
        subtitle=self.label('subtitle'); subtitle.setObjectName('subtitle'); outer.addWidget(subtitle)
        bar=QHBoxLayout(); bar.addWidget(self.button('open_audio',self.choose_file)); bar.addWidget(self.button('demo',self.demo))
        self.file_label=self.label('drop_audio'); bar.addWidget(self.file_label,1); outer.addLayout(bar)
        self.wave=Waveform(); self.wave.seek.connect(self.seek); outer.addWidget(self.wave)
        self.tabs=QTabWidget(); outer.addWidget(self.tabs,1)
        native_page=QWidget(); nl=QVBoxLayout(native_page)
        row=QHBoxLayout()
        self.mode=self.combo([(f'native_{value}',value) for _,value in NATIVE_MODES]); self.mode.setCurrentIndex(1)
        row.addWidget(self.label('native_mode')); row.addWidget(self.mode,1)
        self.policy=self.combo([('policy_off',0),('policy_harmonic',1),('policy_mono',2)])
        row.addWidget(self.policy); nl.addLayout(row)
        nl.addWidget(self.label('native_hint',wrap=True))
        controls=QHBoxLayout()
        self.speed=self.control('speed',0,4,1,'×',1000)
        self.pitch=self.control('pitch',-24,24,0,'st'); self.formant=self.control('formant',-12,12,0,'st')
        for control in (self.speed,self.pitch,self.formant): controls.addWidget(control)
        nl.addLayout(controls)
        buttons=QHBoxLayout(); self.play_button=self.button('play',self.toggle_play); buttons.addWidget(self.play_button)
        self.freeze_button=self.button('freeze',self.freeze); buttons.addWidget(self.freeze_button)
        buttons.addWidget(self.button('start',lambda:self.seek(0))); buttons.addWidget(self.button('reset',self.reset_controls))
        nl.addLayout(buttons)
        erow=QHBoxLayout(); self.export_seconds=QDoubleSpinBox(); self.export_seconds.setRange(.1,120); self.export_seconds.setValue(10)
        self.bind(self.export_seconds,'seconds_suffix',setter='setSuffix')
        erow.addWidget(self.label('export_hint')); erow.addWidget(self.export_seconds)
        self.native_export_button=self.button('export',self.export_native); erow.addWidget(self.native_export_button); nl.addLayout(erow)
        compare_row=QHBoxLayout(); self.native_batch_button=self.button('compare_native',self.render_all_native)
        compare_row.addWidget(self.native_batch_button); compare_row.addWidget(self.button('cancel_native',self.worker.render_cancel.set)); nl.addLayout(compare_row)
        self.native_status=self.label('idle',wrap=True); nl.addWidget(self.native_status); nl.addStretch()
        self.tabs.addTab(native_page,''); self.setup_compare()
        outputs=QHBoxLayout(); outputs.addWidget(self.label('output_device')); self.device=QComboBox(); self.devices=QMediaDevices.audioOutputs()
        self.media_devices=QMediaDevices(self)
        self.selected_device_id=bytes(self.devices[0].id()) if self.devices else None
        self.bind(self.device,'choose_device',setter='setPlaceholderText')
        for device in self.devices: self.device.addItem(device.description())
        if not self.devices:
            self.device.addItem(''); self._combo_bindings.append((self.device,[message('no_device')]))
        outputs.addWidget(self.device,1); self.rate=QComboBox(); self.rate.addItems(['44100','48000','96000']); self.rate.setCurrentText('48000'); outputs.addWidget(self.rate)
        self.volume=self.control('volume',0,100,25,'%',1); outputs.addWidget(self.volume); outer.addLayout(outputs)
        self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(100); self.log.setMaximumBlockCount(80); outer.addWidget(self.log)
        self.debounce=QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(40); self.debounce.timeout.connect(self.apply_settings)
        for control in (self.speed,self.pitch,self.formant): control.changed.connect(self.controls_changed)
        self.mode.currentIndexChanged.connect(self.structure_changed); self.policy.currentIndexChanged.connect(self.structure_changed)
        self.rate.currentIndexChanged.connect(self.structure_changed); self.device.currentIndexChanged.connect(self.device_changed)
        self.media_devices.audioOutputsChanged.connect(self.refresh_devices)
        self.volume.changed.connect(self.volume_changed); self.tabs.currentChanged.connect(lambda _:self.pause())
        self.language_combo.currentIndexChanged.connect(lambda _:self.change_language(self.language_combo.currentData()))
        self.timer=QTimer(self); self.timer.setInterval(5); self.timer.timeout.connect(self.poll); self.timer.start()
        QShortcut(QKeySequence('Space'),self,activated=self.toggle_play); QShortcut(QKeySequence('F'),self,activated=self.freeze)
        self.retranslate_ui(); self.structure_changed(); self.log_message('intro')

    def text(self,key,**values):
        return self.i18n.text(message(key,**values))

    def bind(self,widget,key,*,setter='setText',**values):
        value=message(key,**values); self._text_bindings[(widget,setter)]=value
        getattr(widget,setter)(self.i18n.text(value))
        return widget

    def label(self,key,wrap=False):
        widget=QLabel(); widget.setTextFormat(Qt.PlainText); widget.setWordWrap(wrap)
        return self.bind(widget,key)

    def button(self,key,callback):
        widget=self.bind(QPushButton(),key); widget.clicked.connect(callback); return widget

    def control(self,key,*args):
        widget=Control('',*args); self.bind(widget.title_label,key); return widget

    def combo(self,items):
        widget=QComboBox(); messages=[]
        for key,data in items:
            value=message(key); messages.append(value); widget.addItem(self.i18n.text(value),data)
        self._combo_bindings.append((widget,messages)); return widget

    def log_message(self,key,**values):
        value=message(key,**values); self._log_entries.append(value)
        if hasattr(self,'log'): self.log.appendPlainText(self.i18n.text(value))

    def change_language(self,language):
        if language==self.i18n.language: return
        saved=self.i18n.select(language)
        self.retranslate_ui()
        if not saved: self.show_error(message('settings_failed'))

    def retranslate_ui(self):
        """Text only: never call pause, seek, set_comparisons or apply_settings.

        Combo labels are presentation. Item data, current indices and all pending
        worker/render/audio state remain untouched, including SDK policy tokens.
        """
        self.qt_translation_loaded=self.i18n.install_qt_translation()
        with QSignalBlocker(self.language_combo):
            self.language_combo.setCurrentIndex(self.language_combo.findData(self.i18n.language))
        for (widget,setter),value in self._text_bindings.items():
            with QSignalBlocker(widget): getattr(widget,setter)(self.i18n.text(value))
        for combo,values in self._combo_bindings:
            with QSignalBlocker(combo):
                for index,value in enumerate(values): combo.setItemText(index,self.i18n.text(value))
        with QSignalBlocker(self.tabs):
            self.tabs.setTabText(0,self.text('native_tab')); self.tabs.setTabText(1,self.text('compare_tab'))
        self.wave.anchor_text=self.text('source_anchor'); self.wave.update()
        self.bind(self.play_button,'pause' if self.playing else 'play')
        self.bind(self.freeze_button,'unfreeze' if self.speed.value()==0 else 'freeze')
        self.log.setPlainText('\n'.join(self.i18n.text(v) for v in self._log_entries))
        self.refresh_comparison_texts()

    def setup_compare(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.addWidget(self.label('compare_hint',wrap=True))
        row=QHBoxLayout(); self.sdk_mode=self.combo([(f'sdk_{index}',index) for index in range(len(sdk_compare.SDK_MODES))]); row.addWidget(self.sdk_mode)
        # Never submit translated currentText() as an SDK policy!
        self.sdk_policy=self.combo([('policy_off','off'),('policy_harmonic','harmonic'),('policy_mono','monophonic')])
        row.addWidget(self.sdk_policy); layout.addLayout(row)
        cr=QHBoxLayout(); self.sdk_speed=self.control('sdk_speed',.25,4,1,'×',1000)
        self.sdk_pitch=self.control('pitch',-24,24,0,'st'); self.sdk_formant=self.control('formant',-12,12,0,'st')
        for control in (self.sdk_speed,self.sdk_pitch,self.sdk_formant): cr.addWidget(control)
        layout.addLayout(cr); layout.addWidget(self.label('sdk_bounds',wrap=True))
        buttons=QHBoxLayout(); self.render_button=self.button('render_sdk',self.render_sdk); buttons.addWidget(self.render_button)
        self.batch_button=self.button('compare_sdk',self.render_all_sdk); buttons.addWidget(self.batch_button)
        buttons.addWidget(self.button('cancel_render',self.cancel.set)); buttons.addWidget(self.button('open_reference',self.open_reference)); layout.addLayout(buttons)
        actions=QHBoxLayout(); actions.addWidget(self.button('play_reference',self.play_reference))
        stop=self.button('stop_reference',lambda:self.media.stop()); actions.addWidget(stop)
        self.comparison_choice=QComboBox(); self.comparison_choice.currentIndexChanged.connect(self.select_comparison); layout.addWidget(self.comparison_choice)
        actions.addWidget(self.button('save_reference',self.save_comparison))
        self.reference_label=self.label('no_reference',wrap=True); layout.addWidget(self.reference_label); layout.addLayout(actions); layout.addStretch()
        self.media=QMediaPlayer(self); self.media_output=QAudioOutput(self); self.media_output.setVolume(.25); self.media.setAudioOutput(self.media_output)
        self.media.errorOccurred.connect(lambda *_:self.show_error(self.media.errorString()))
        self.tabs.addTab(page,'')

    def send(self,kind,value=None):
        if self.closing: return
        try: self.worker.command(kind,value)
        except Exception as exc: self.show_error(str(exc))
    def output_failed(self,text):
        self.pause(); self.show_error(text)
    def show_error(self,text):
        detail=text if isinstance(text,(Message,Diagnostic)) else Diagnostic(str(text))
        self.log_message('warning',detail=detail)
    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,self.text('open_audio'),'',self.text('audio_filter'))
        if path: self.load(path)
    def load(self,path):
        self.pause(); self.native_ready=False; self.send('load',str(path)); self.bind(self.file_label,'loading',name=Path(path).name)
    def demo(self):
        p=Path(self.temporary.name)/'demo.wav'; rate=48000; t=np.arange(rate*6)/rate
        gate=np.minimum(1,t*20)*np.minimum(1,(6-t)*20)
        x=.13*np.sin(2*np.pi*223*t)+.04*np.sin(2*np.pi*997*t)
        for center in (1,2,3,4,5): x+=.13*np.exp(-((t-center)/.01)**2)*np.sin(2*np.pi*3203*t)
        sf.write(p,np.c_[x*gate,.7*x*gate],rate,subtype='FLOAT'); self.load(p)
    def controls_changed(self):
        frozen=self.speed.value()==0; self.wave.frozen=frozen; self.wave.update()
        self.bind(self.freeze_button,'unfreeze' if frozen else 'freeze'); self.debounce.start()
    def structure_changed(self):
        timedomain=self.mode.currentData()>=3
        if timedomain: self.policy.setCurrentIndex(0)
        self.policy.setEnabled(not timedomain); enabled=not timedomain and self.policy.currentData()!=0
        if not enabled: self.formant.setValue(0)
        self.formant.setEnabled(enabled); self.pause(); self.debounce.start()
    def apply_settings(self):
        try: settings=Settings(self.mode.currentData(),self.policy.currentData(),self.speed.value(),self.pitch.value(),self.formant.value(),int(self.rate.currentText()))
        except Exception as exc: self.show_error(str(exc)); return
        self.send('settings',settings)
    def reset_controls(self): self.speed.setValue(1); self.pitch.setValue(0); self.formant.setValue(0)
    def freeze(self):
        if self.speed.value()>0: self.last_speed=self.speed.value(); self.speed.setValue(0)
        else: self.speed.setValue(self.last_speed or 1)
    def toggle_play(self):
        if self.tabs.currentIndex()!=0: self.play_reference(); return
        if self.playing: self.pause(); return
        if not self.native_ready: self.show_error(message('load_first')); return
        if self.native_busy: self.show_error(message('finish_first')); return
        self.media.stop(); self.apply_settings()
        if self.pump.play(): self.send('play'); self.playing=True; self.bind(self.play_button,'pause')
        else: self.show_error(message('no_playback_device'))
    def pause(self):
        self.send('pause'); self.pump.pause(); self.playing=False
        if hasattr(self,'play_button'): self.bind(self.play_button,'play')
        if hasattr(self,'media'): self.media.pause()
    def seek(self,seconds): self.pause(); self.send('seek',seconds)
    def selected_device(self):
        index=self.device.currentIndex()
        return self.devices[index] if 0<=index<len(self.devices) else None

    def refresh_devices(self):
        if self.closing: return
        previous=self.selected_device_id
        self.devices=QMediaDevices.audioOutputs()
        identifiers=[bytes(device.id()) for device in self.devices]
        # Names/positions may change while stable IDs do not. Never silently
        # choose a different speaker when the selected endpoint disappears.
        self._combo_bindings=[binding for binding in self._combo_bindings if binding[0] is not self.device]
        with QSignalBlocker(self.device):
            self.device.clear()
            for device in self.devices: self.device.addItem(device.description())
            if not self.devices:
                self.device.addItem(self.text('no_device'))
                self._combo_bindings.append((self.device,[message('no_device')]))
            self.device.setCurrentIndex(identifiers.index(previous) if previous in identifiers else -1)
        if previous is not None and previous not in identifiers:
            self.selected_device_id=None
            self.pause(); self.pump.close(); self.media.stop()
            self.show_error(message('device_removed'))

    def device_changed(self):
        if self.closing: return
        device=self.selected_device()
        self.selected_device_id=bytes(device.id()) if device is not None else None
        self.pause(); self.pump.close(); self.media.stop()
        if device is not None and self.stream_format is not None:
            # A device change does not seek/reset the native synthesis history.
            if self.pump.configure(device,**self.stream_format): self.volume_changed()
    def volume_changed(self):
        value=self.volume.value()/100
        if self.pump.sink: self.pump.sink.setVolume(value)
        self.media_output.setVolume(value)
    def export_native(self):
        if self.native_busy: self.show_error(message('native_busy')); return
        if not self.native_ready: self.show_error(message('load_first')); return
        path,_=QFileDialog.getSaveFileName(self,self.text('export_title'),'',self.text('wave_filter'))
        if path:
            self.pause(); self.apply_settings(); self.begin_native_job('export',(path,self.export_seconds.value())); self.log_message('exporting')
    def begin_native_job(self,kind,args):
        self.worker.render_cancel.clear(); self.native_busy=True
        self.native_batch_button.setEnabled(False); self.native_export_button.setEnabled(False)
        try: self.worker.command(kind,args)
        except Exception as exc:
            self.native_busy=False; self.native_batch_button.setEnabled(True); self.native_export_button.setEnabled(True); self.show_error(str(exc))
    def render_all_native(self):
        if not self.native_ready: self.show_error(message('load_first')); return
        if self.native_busy or (self.job and not self.job.done()): self.show_error(message('comparison_busy')); return
        self.pause(); self.apply_settings()
        directory=Path(self.temporary.name)/('native-'+uuid.uuid4().hex)
        self.begin_native_job('compare_native',(directory,self.export_seconds.value())); self.log_message('native_rendering')
    def mode_message(self,kind,index,raw):
        limit=len(NATIVE_MODES) if kind=='native' else len(sdk_compare.SDK_MODES)
        return message(f'{kind}_{index}') if type(index) is int and 0<=index<limit else raw
    def publish_comparison(self,receipt,directory,prefix):
        kind='native' if prefix.startswith('Native') else 'sdk'; entries=[]
        for row in receipt['results']:
            status=row['status']; status_message=message(status) if status in ('passed','failed','unsupported','cancelled','pending') else status
            item=dict(label=prefix+row['mode']+' — '+status,
                      label_message=message('choice',kind=message('kind_'+kind),
                          mode=self.mode_message(kind,row['index'],row['mode']),status=status_message))
            if status=='passed':
                item['path']=directory/row['output']
                source=message('source_loaded_pcm') if kind=='native' else receipt['source_name']
                item['detail_message']=message('comparison_detail',source=source,frames=row['receipt']['output_frames'],peak=row['receipt']['peak'])
            else: item['detail_message']=Diagnostic(row['reason'])
            entries.append(item)
        self.set_comparisons(entries)
        self.log_message('comparison_complete',passed=sum(row['status']=='passed' for row in receipt['results']),total=len(entries))
    def render_sdk(self):
        if self.native_busy: self.show_error(message('native_busy')); return
        if not self.source_path: self.show_error(message('load_first')); return
        if self.job and not self.job.done(): self.show_error(message('comparison_busy')); return
        self.pause(); self.cancel.clear(); dest=Path(self.temporary.name)/(uuid.uuid4().hex+'.wav')
        self._render_mode=self.sdk_mode.currentData()
        self.job=self.pool.submit(sdk_compare.render,self.source_path,dest,self._render_mode,self.sdk_speed.value(),
            self.sdk_pitch.value(),self.sdk_policy.currentData(),self.sdk_formant.value(),self.sdk,self.cancel)
        self.reference_path=None; self._render_destination=dest; self._batch_directory=None
        self.render_button.setEnabled(False); self.batch_button.setEnabled(False); self.bind(self.reference_label,'rendering_sdk')
    def render_all_sdk(self):
        if self.native_busy: self.show_error(message('native_busy')); return
        if not self.source_path: self.show_error(message('load_first')); return
        if self.job and not self.job.done(): self.show_error(message('comparison_busy')); return
        self.pause(); self.cancel.clear(); dest=Path(self.temporary.name)/('comparison-'+uuid.uuid4().hex)
        self.job=self.pool.submit(comparison_batch.render_batch,self.source_path,dest,self.sdk_speed.value(),
            self.sdk_pitch.value(),self.sdk_policy.currentData(),self.sdk_formant.value(),self.sdk,self.cancel)
        self._batch_directory=dest; self.reference_path=None; self.render_button.setEnabled(False); self.batch_button.setEnabled(False)
        self.bind(self.reference_label,'rendering_sdk_all')
    def set_comparisons(self,entries):
        self.media.stop(); self.comparisons=entries
        with QSignalBlocker(self.comparison_choice):
            self.comparison_choice.clear()
            for entry in entries: self.comparison_choice.addItem(self.i18n.text(entry.get('label_message',entry['label'])))
        if entries: self.comparison_choice.setCurrentIndex(0); self.select_comparison(0)
    def refresh_comparison_texts(self):
        with QSignalBlocker(self.comparison_choice):
            for index,entry in enumerate(self.comparisons):
                self.comparison_choice.setItemText(index,self.i18n.text(entry.get('label_message',entry['label'])))
        # A pending render message must not be replaced with a previous result.
        if (self.reference_label,'setText') not in self._text_bindings:
            self.describe_comparison(self.comparison_choice.currentIndex())
    def describe_comparison(self,index):
        if not 0<=index<len(self.comparisons): return
        entry=self.comparisons[index]
        label=self.i18n.text(entry.get('label_message',entry['label']))
        detail=self.i18n.text(entry.get('detail_message',entry.get('detail','')))
        self.reference_label.setText(label+'\n'+detail)
    def select_comparison(self,index):
        self.media.stop()
        if not 0<=index<len(self.comparisons): return
        self.reference_path=self.comparisons[index].get('path')
        self._text_bindings.pop((self.reference_label,'setText'),None); self.describe_comparison(index)
    def save_comparison(self):
        if not self.reference_path: self.show_error(message('save_select_first')); return
        path,_=QFileDialog.getSaveFileName(self,self.text('save_title'),'',self.text('wave_filter'))
        if path:
            try: comparison_batch.save_result(self.reference_path,path); self.log_message('saved',path=path)
            except Exception as exc: self.show_error(str(exc))
    def open_reference(self):
        path,_=QFileDialog.getOpenFileName(self,self.text('external_title'),'',self.text('audio_filter'))
        if path: self.set_comparisons([dict(path=Path(path),label='External comparison',label_message=message('external_label'),detail=path)])
    def play_reference(self):
        if not self.reference_path: self.show_error(message('reference_first')); return
        self.pause()
        device=self.selected_device()
        if device is None: self.show_error(message('device_unavailable')); return
        self.media_output.setDevice(device); self.media.setSource(QUrl.fromLocalFile(str(self.reference_path))); self.media.play()
    def telemetry(self,state):
        self.last_state=state; self.wave.position=state['source_position']/self.worker.source_rate; self.wave.update()
        self.bind(self.native_status,'telemetry',state=message('frozen_status' if state['speed']==0 else 'playing_status'),
                  source=self.wave.position,output=state['output_frames']/int(self.rate.currentText()),
                  pitch=state['pitch_semitones'],peak=state['peak'],warning=message('peak_warning' if state['peak']>1 else 'empty'))
    def poll(self):
        if self.closing: return
        for _ in range(12):
            try: kind,data=self.worker.messages.get_nowait()
            except queue.Empty: break
            if kind=='ready':
                resume_requested=self.playing; self.native_ready=True; self.playing=False; self.bind(self.play_button,'play'); self.eof=False
                from PySide6.QtMultimedia import QAudioDevice
                self.stream_format=dict(data)
                device=self.selected_device()
                if device is None: device=QAudioDevice()
                if self.pump.configure(device,**data):
                    self.volume_changed()
                    if resume_requested and self.pump.play():
                        self.send('play'); self.playing=True; self.bind(self.play_button,'pause')
            elif kind=='position':
                self.wave.position=data['source_seconds']; self.wave.update(); self.bind(self.native_status,'position',seconds=self.wave.position)
            elif kind=='loaded':
                self.source_path=Path(data['path']); self.duration=data['frames']/data['rate']; self.wave.set_audio(data['waveform'],data['frames'],data['rate'])
                self._text_bindings.pop((self.file_label,'setText'),None)
                self.file_label.setText(f"{self.source_path.name}  |  {data['rate']} Hz  |  {data['waveform'].shape[1]} ch  |  {self.duration:.2f} s")
                self.log_message('loaded')
            elif kind=='error':
                self.pause(); self.native_ready=self.source_path is not None; self.show_error(data)
                if self.source_path: self.bind(self.file_label,'source_retained',name=self.source_path.name)
            elif kind=='ended': self.eof=True
            elif kind=='exported': self.log_message('exported',path=data)
            elif kind=='render_finished':
                self.native_busy=False; self.native_batch_button.setEnabled(True); self.native_export_button.setEnabled(True)
            elif kind=='render_progress':
                status=message(data['status']) if data['status'] in ('passed','failed','unsupported','cancelled','pending') else data['status']
                self.bind(self.native_status,'render_progress',completed=data['completed'],total=data['total'],status=status)
            elif kind=='native_comparison':
                directory,receipt=data; self.publish_comparison(receipt,Path(directory),'Native: '); self.tabs.setCurrentIndex(1)
        self.pump.tick()
        if self.eof and self.worker.audio.empty() and not self.pump.pending:
            if not self.pump.sink or self.pump.sink.bytesFree()>=self.pump.sink.bufferSize():
                self.pause(); self.eof=False; self.bind(self.native_status,'ended')
        if self.job and self.job.done():
            job=self.job; self.job=None; self.render_button.setEnabled(True); self.batch_button.setEnabled(True)
            try:
                receipt=job.result()
                if self._batch_directory is not None: self.publish_comparison(receipt,self._batch_directory,'SDK: ')
                else:
                    self.set_comparisons([dict(path=self._render_destination,label=receipt['mode'],
                        label_message=self.mode_message('sdk',self._render_mode,receipt['mode']),
                        detail_message=message('single_detail',frames=receipt['output_frames'],peak=receipt['peak']))])
            except Exception as exc: self.show_error(str(exc)); self.bind(self.reference_label,'render_failed')
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if urls and urls[0].isLocalFile(): self.load(urls[0].toLocalFile())
    def closeEvent(self,event):
        if not self.closing:
            self.closing=True
            self.timer.stop(); self.debounce.stop(); self.pump.close(); self.media.stop()
            self.cancel.set(); self.worker.stop_worker()
            self.pool.shutdown(wait=False,cancel_futures=True)
            self.centralWidget().setEnabled(False)
            self.bind(self.native_status,'close_pending')
        if self.worker.is_alive() or (self.job is not None and not self.job.done()):
            # Keep Qt processing events; the native owner may still be reading a
            # file. Temporary storage must outlive both native and SDK jobs.
            QTimer.singleShot(25,self.close)
            event.ignore(); return
        self.temporary.cleanup(); self.closed=True; event.accept()


STYLE='''
QWidget { background: #172733; color: #e6edf2; font-size: 13px; }
QLabel#title { font-size: 27px; font-weight: 700; color: #fcf9ee; }
QLabel#subtitle { color: #8dcad1; }
QPushButton { background: #294553; border: 1px solid #446575; border-radius: 5px; padding: 8px 13px; }
QPushButton:hover { background: #365e6f; } QPushButton:disabled { color: #83939c; }
QComboBox, QDoubleSpinBox { background: #10202b; border: 1px solid #456071; border-radius: 4px; padding: 6px; }
QTabWidget::pane { border: 1px solid #3b5667; padding: 8px; }
QTabBar::tab { background: #203844; padding: 10px 18px; } QTabBar::tab:selected { background: #345b6c; }
QSlider::groove:horizontal { background: #0d1c25; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #91d4cf; width: 15px; margin: -5px 0; border-radius: 6px; }
QPlainTextEdit { background: #101d29; border: 1px solid #355165; color: #b5c8d5; }
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library'); parser.add_argument('--sdk-cli'); parser.add_argument('--file')
    parser.add_argument('--demo',action='store_true'); parser.add_argument('--smoke',action='store_true'); parser.add_argument('--screenshot',type=Path)
    parser.add_argument('--language',choices=('ja','en'),help='Session language override; the in-app selector saves a preference')
    args=parser.parse_args(); app=QApplication(sys.argv[:1]); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    window=MainWindow(args.library,args.sdk_cli,language=args.language); window.show()
    if args.file: window.load(args.file)
    elif args.demo or args.smoke: window.demo()
    if args.smoke: app.setQuitOnLastWindowClosed(False)
    if args.smoke or args.screenshot:
        deadline=time.monotonic()+10
        def capture():
            if args.smoke and not window.native_ready and time.monotonic()<deadline:
                QTimer.singleShot(50,capture); return
            success=window.native_ready if args.smoke else True
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True,exist_ok=True)
                success=window.grab().save(str(args.screenshot)) and success
            if args.smoke:
                print('Standalone native source ready' if success else 'Standalone smoke failed: source/library unavailable',flush=True)
                window.close()
                def finish():
                    if window.closed: app.exit(0 if success else 1)
                    else: QTimer.singleShot(25,finish)
                finish()
        QTimer.singleShot(200,capture)
    return app.exec()

if __name__=='__main__': raise SystemExit(main())
