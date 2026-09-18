#!/usr/bin/env python3
"""Standalone PySide6 audition application; native freeze is synthesized in C++."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import sys
import tempfile
import threading
import uuid
import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QUrl, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,
    QLabel,QPushButton,QComboBox,QDoubleSpinBox,QSlider,QFileDialog,QTabWidget,QGroupBox,QPlainTextEdit)
from PySide6.QtMultimedia import QAudioSink,QAudioFormat,QMediaDevices,QMediaPlayer,QAudioOutput
from native import NATIVE_MODES
from worker import PlayerWorker,Settings
import sdk_compare

class OutputPump(QObject):
    """Only moves PCM bytes on the GUI thread. Never calls the DSP renderer.

    The device may accept partial writes; unconsumed bytes stay pending. Native
    queues contain at most2 blocks. Qt/OS buffering is additional and reported.
    """
    error=Signal(str)
    telemetry=Signal(dict)
    def __init__(self, audio_queue, parent=None):
        super().__init__(parent);self.queue=audio_queue;self.sink=None;self.io=None
        self.pending=b'';self.epoch=0;self.running=False;self.frame_bytes=8
    def configure(self,device,rate,channels,epoch):
        self.close();self.epoch=epoch;self.frame_bytes=4*channels
        fmt=QAudioFormat();fmt.setSampleRate(rate);fmt.setChannelCount(channels);fmt.setSampleFormat(QAudioFormat.Float)
        if device.isNull() or not device.isFormatSupported(fmt):
            self.error.emit('選択デバイスはこのfloat32形式に未対応です。出力先・レートを変更してください。WAV書出しは利用できます。')
            return False
        self.sink=QAudioSink(device,fmt,self);self.sink.setBufferSize(4096*self.frame_bytes)
        self.sink.setVolume(.25);self.io=self.sink.start()
        if self.io is None:
            self.error.emit('音声デバイスを開始できません。');self.close();return False
        self.sink.suspend();return True
    def play(self):
        if self.sink and self.io:self.sink.resume();self.running=True;return True
        return False
    def pause(self):
        self.running=False
        if self.sink:self.sink.suspend()
    def close(self):
        self.running=False;self.pending=b'';self.io=None
        if self.sink:self.sink.reset();self.sink.deleteLater();self.sink=None
    def tick(self):
        if not self.running or not self.sink or not self.io:return
        # A bounded amount of GUI work; the worker does all DSP and file reads.
        for _ in range(3):
            if not self.pending:
                try:epoch,data,state=self.queue.get_nowait()
                except queue.Empty:return
                if epoch!=self.epoch:continue
                self.pending=data;self.telemetry.emit(state)
            available=self.sink.bytesFree()
            if available<=0:return
            count=self.io.write(self.pending[:available])
            if count<0:
                self.pause();self.error.emit('音声出力の書込みに失敗しました。');return
            if count==0:return
            self.pending=self.pending[count:]

class Waveform(QWidget):
    seek=Signal(float)
    def __init__(self):
        super().__init__();self.values=np.zeros(1);self.duration=0.;self.position=0.;self.frozen=False
        self.setMinimumHeight(155);self.setCursor(Qt.PointingHandCursor)
    def set_audio(self,wave,frames,rate):
        self.values=np.max(np.abs(wave),axis=1);self.duration=frames/rate;self.position=0;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor('#101d29'))
        w,h=self.width(),self.height();p.setPen(QPen(QColor('#263c4b'),1));p.drawLine(0,h//2,w,h//2)
        p.setPen(QPen(QColor('#60b4c1'),1.4));maximum=max(1.,float(self.values.max()))
        for i,v in enumerate(self.values):
            x=i*w/max(1,len(self.values)-1);a=float(v)/maximum*(h*.38)
            p.drawLine(QPointF(x,h/2-a),QPointF(x,h/2+a))
        x=np.clip(self.position/max(self.duration,1e-9),0,1)*w
        p.setPen(QPen(QColor('#ffcc70' if self.frozen else '#faf8f2'),2));p.drawLine(QPointF(x,10),QPointF(x,h-10))
        p.setPen(QColor('#b8c9d7'));p.drawText(12,23,'SOURCE ANCHOR  /  クリックして位置を選択')
        p.drawText(12,h-10,f'{self.position:7.3f} s  /  {self.duration:.3f} s')
    def mousePressEvent(self,event):
        if self.duration:self.seek.emit(float(np.clip(event.position().x()/max(1,self.width()),0,1))*self.duration)

class Control(QWidget):
    changed=Signal()
    def __init__(self,title,lo,hi,value,unit,scale=100):
        super().__init__();self.scale=scale;layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        layout.addWidget(QLabel(title));self.spin=QDoubleSpinBox();self.spin.setRange(lo,hi);self.spin.setDecimals(3 if scale==1000 else 2)
        self.spin.setSingleStep(.01 if scale==1000 else .1);self.spin.setSuffix(' '+unit);self.spin.setValue(value)
        self.slider=QSlider(Qt.Horizontal);self.slider.setRange(round(lo*scale),round(hi*scale));self.slider.setValue(round(value*scale))
        layout.addWidget(self.spin);layout.addWidget(self.slider)
        self.spin.valueChanged.connect(self._spin);self.slider.valueChanged.connect(lambda v:self.spin.setValue(v/scale))
    def _spin(self,v):
        self.slider.blockSignals(True);self.slider.setValue(round(v*self.scale));self.slider.blockSignals(False);self.changed.emit()
    def value(self):return self.spin.value()
    def setValue(self,v):self.spin.setValue(v)

class MainWindow(QMainWindow):
    def __init__(self,library=None,sdk=None):
        super().__init__();self.setWindowTitle('boiled egg — Audition Lab');self.resize(1110,810)
        self.library=library;self.sdk=sdk;self.source_path=None;self.reference_path=None;self.playing=False;self.eof=False
        self.last_speed=1.;self.duration=0.;self.native_ready=False;self.last_state={}
        self.temporary=tempfile.TemporaryDirectory(prefix='boiled-egg-audition-')
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='sdk-compare');self.job=None;self.cancel=threading.Event()
        self.worker=PlayerWorker(library);self.worker.start();self.pump=OutputPump(self.worker.audio,self)
        self.pump.error.connect(self.show_error);self.pump.telemetry.connect(self.telemetry)
        self.setAcceptDrops(True)
        central=QWidget();self.setCentralWidget(central);outer=QVBoxLayout(central);outer.setSpacing(12)
        title=QLabel('boiled egg   /   AUDITION LAB');title.setObjectName('title');outer.addWidget(title)
        subtitle=QLabel('C++ native transport  ·  speed 0 = FREEZE  ·  pitch 0 st = original pitch');subtitle.setObjectName('subtitle');outer.addWidget(subtitle)
        bar=QHBoxLayout();load=QPushButton('音声を開く');load.clicked.connect(self.choose_file);bar.addWidget(load)
        demo=QPushButton('デモ素材');demo.clicked.connect(self.demo);bar.addWidget(demo)
        self.file_label=QLabel('WAV / FLAC / AIFF / OGG をドロップ');bar.addWidget(self.file_label,1);outer.addLayout(bar)
        self.wave=Waveform();self.wave.seek.connect(self.seek);outer.addWidget(self.wave)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        native_page=QWidget();nl=QVBoxLayout(native_page)
        row=QHBoxLayout();self.mode=QComboBox()
        for label,value in NATIVE_MODES:self.mode.addItem(label,value)
        self.mode.setCurrentIndex(1);row.addWidget(QLabel('ネイティブ方式'));row.addWidget(self.mode,1)
        self.policy=QComboBox();self.policy.addItems(['Off','Harmonic / polyphonic','Monophonic']);row.addWidget(self.policy);nl.addLayout(row)
        hint=QLabel('フリーズ対応の新しい再生系です。従来SDKと同じPCMになる方式ではありません。切替・シーク後は再生を押してください。');hint.setWordWrap(True);nl.addWidget(hint)
        controls=QHBoxLayout();self.speed=Control('再生速度',0,4,1,'×',1000);self.pitch=Control('ピッチ変更',-24,24,0,'st');self.formant=Control('フォルマント変更',-12,12,0,'st')
        for control in (self.speed,self.pitch,self.formant):controls.addWidget(control)
        nl.addLayout(controls)
        buttons=QHBoxLayout();self.play_button=QPushButton('▶ 再生');self.play_button.clicked.connect(self.toggle_play);buttons.addWidget(self.play_button)
        self.freeze_button=QPushButton('❄ フリーズ  [F]');self.freeze_button.clicked.connect(self.freeze);buttons.addWidget(self.freeze_button)
        origin=QPushButton('先頭');origin.clicked.connect(lambda:self.seek(0));buttons.addWidget(origin)
        reset=QPushButton('速度1 / ピッチ0');reset.clicked.connect(self.reset_controls);buttons.addWidget(reset);nl.addLayout(buttons)
        erow=QHBoxLayout();self.export_seconds=QDoubleSpinBox();self.export_seconds.setRange(.1,120);self.export_seconds.setValue(10);self.export_seconds.setSuffix(' 秒')
        erow.addWidget(QLabel('現在位置・現在設定で有限長WAV書出し'));erow.addWidget(self.export_seconds)
        export=QPushButton('WAVを書出す');export.clicked.connect(self.export_native);erow.addWidget(export);nl.addLayout(erow)
        self.native_status=QLabel('待機中');self.native_status.setWordWrap(True);nl.addWidget(self.native_status);nl.addStretch()
        self.tabs.addTab(native_page,'ネイティブ再生・フリーズ')
        self.setup_compare()
        outputs=QHBoxLayout();outputs.addWidget(QLabel('出力先'));self.device=QComboBox();self.devices=QMediaDevices.audioOutputs()
        for d in self.devices:self.device.addItem(d.description())
        if not self.devices:self.device.addItem('音声デバイスなし — WAV書出しは使用可能')
        outputs.addWidget(self.device,1);self.rate=QComboBox();self.rate.addItems(['44100','48000','96000']);self.rate.setCurrentText('48000');outputs.addWidget(self.rate)
        self.volume=Control('試聴音量（生WAVには不適用）',0,100,25,'%',1);outputs.addWidget(self.volume);outer.addLayout(outputs)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumHeight(100);self.log.setMaximumBlockCount(80);outer.addWidget(self.log)
        self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(40);self.debounce.timeout.connect(self.apply_settings)
        for c in (self.speed,self.pitch,self.formant):c.changed.connect(self.controls_changed)
        self.mode.currentIndexChanged.connect(self.structure_changed);self.policy.currentIndexChanged.connect(self.structure_changed)
        self.rate.currentIndexChanged.connect(self.structure_changed);self.device.currentIndexChanged.connect(self.device_changed)
        self.volume.changed.connect(self.volume_changed);self.tabs.currentChanged.connect(lambda _:self.pause())
        self.timer=QTimer(self);self.timer.setInterval(5);self.timer.timeout.connect(self.poll);self.timer.start()
        QShortcut(QKeySequence('Space'),self,activated=self.toggle_play);QShortcut(QKeySequence('F'),self,activated=self.freeze)
        self.structure_changed();self.log.appendPlainText('速度0は一時停止ではありません。Pauseは再生停止、Freezeは原音位置だけを固定します。')
    def setup_compare(self):
        page=QWidget();layout=QVBoxLayout(page)
        note=QLabel('従来SDKの全5品質モードを、実SDK CLIでレンダーして試聴します。ネイティブフリーズとは別経路です。研究枝の未移植方式を別方式へ置換しません。既存の研究出力は「比較音源を開く」で試聴できます。');note.setWordWrap(True);layout.addWidget(note)
        row=QHBoxLayout();self.sdk_mode=QComboBox();self.sdk_mode.addItems([v[0] for v in sdk_compare.SDK_MODES]);row.addWidget(self.sdk_mode)
        self.sdk_policy=QComboBox();self.sdk_policy.addItems(['off','harmonic','monophonic']);row.addWidget(self.sdk_policy);layout.addLayout(row)
        cr=QHBoxLayout();self.sdk_speed=Control('通常SDKの速度',.25,4,1,'×',1000);self.sdk_pitch=Control('ピッチ',-24,24,0,'st');self.sdk_formant=Control('フォルマント',-12,12,0,'st')
        for control in (self.sdk_speed,self.sdk_pitch,self.sdk_formant):cr.addWidget(control)
        layout.addLayout(cr)
        bounds=QLabel('WSOLA: 速度0.25〜4・±24 st / PV: 速度0.5〜2・±12 st。範囲外と未対応保持はエラー表示。自動代替・時間合わせ・音量正規化なし。');bounds.setWordWrap(True);layout.addWidget(bounds)
        buttons=QHBoxLayout();self.render_button=QPushButton('現在の原音をSDKでレンダー');self.render_button.clicked.connect(self.render_sdk);buttons.addWidget(self.render_button)
        cancel=QPushButton('レンダー中止');cancel.clicked.connect(self.cancel.set);buttons.addWidget(cancel)
        external=QPushButton('比較音源を開く');external.clicked.connect(self.open_reference);buttons.addWidget(external);layout.addLayout(buttons)
        actions=QHBoxLayout();play=QPushButton('▶ 比較音源を再生');play.clicked.connect(self.play_reference);actions.addWidget(play)
        stop=QPushButton('比較音源を停止');actions.addWidget(stop)
        self.reference_label=QLabel('比較音源未選択');self.reference_label.setWordWrap(True);layout.addWidget(self.reference_label);layout.addLayout(actions);layout.addStretch()
        self.media=QMediaPlayer(self);self.media_output=QAudioOutput(self);self.media_output.setVolume(.25);self.media.setAudioOutput(self.media_output)
        self.media.errorOccurred.connect(lambda *_:self.show_error(self.media.errorString()));stop.clicked.connect(self.media.stop)
        self.tabs.addTab(page,'従来SDK・研究出力の比較')
    def send(self,kind,value=None):
        try:self.worker.command(kind,value)
        except Exception as exc:self.show_error(str(exc))
    def show_error(self,text):
        if hasattr(self,'log'):self.log.appendPlainText('注意: '+str(text))
    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,'音声を開く','','Audio (*.wav *.flac *.aiff *.aif *.ogg);;All files (*)')
        if path:self.load(path)
    def load(self,path):
        self.pause();self.native_ready=False;self.send('load',str(path));self.file_label.setText('読込み中: '+Path(path).name)
    def demo(self):
        p=Path(self.temporary.name)/'demo.wav';rate=48000;t=np.arange(rate*6)/rate
        gate=np.minimum(1,t*20)*np.minimum(1,(6-t)*20)
        x=.13*np.sin(2*np.pi*223*t)+.04*np.sin(2*np.pi*997*t)
        for center in (1,2,3,4,5):x+=.13*np.exp(-((t-center)/.01)**2)*np.sin(2*np.pi*3203*t)
        sf.write(p,np.c_[x*gate,.7*x*gate],rate,subtype='FLOAT');self.load(p)
    def controls_changed(self):
        frozen=self.speed.value()==0;self.wave.frozen=frozen;self.wave.update()
        self.freeze_button.setText('▶ フリーズ解除 [F]' if frozen else '❄ フリーズ [F]');self.debounce.start()
    def structure_changed(self):
        timedomain=self.mode.currentData()>=3
        if timedomain:self.policy.setCurrentIndex(0)
        self.policy.setEnabled(not timedomain);enabled=not timedomain and self.policy.currentIndex()!=0
        if not enabled:self.formant.setValue(0)
        self.formant.setEnabled(enabled);self.pause();self.debounce.start()
    def apply_settings(self):
        try:s=Settings(self.mode.currentData(),self.policy.currentIndex(),self.speed.value(),self.pitch.value(),self.formant.value(),int(self.rate.currentText()))
        except Exception as exc:self.show_error(str(exc));return
        self.send('settings',s)
    def reset_controls(self):self.speed.setValue(1);self.pitch.setValue(0);self.formant.setValue(0)
    def freeze(self):
        if self.speed.value()>0:self.last_speed=self.speed.value();self.speed.setValue(0)
        else:self.speed.setValue(self.last_speed or 1)
    def toggle_play(self):
        if self.tabs.currentIndex()!=0:self.play_reference();return
        if self.playing:self.pause();return
        if not self.native_ready:self.show_error('音声を読み込んでください。');return
        self.media.stop();self.apply_settings()
        if self.pump.play():self.send('play');self.playing=True;self.play_button.setText('Ⅱ 一時停止')
        else:self.show_error('音声デバイスがありません。有限長WAV書出し、SDK比較レンダーは使えます。')
    def pause(self):
        self.send('pause');self.pump.pause();self.playing=False
        if hasattr(self,'play_button'):self.play_button.setText('▶ 再生')
        if hasattr(self,'media'):self.media.pause()
    def seek(self,seconds):self.pause();self.send('seek',seconds)
    def device_changed(self):
        if self.native_ready:self.seek(self.wave.position)
    def volume_changed(self):
        value=self.volume.value()/100
        if self.pump.sink:self.pump.sink.setVolume(value)
        self.media_output.setVolume(value)
    def export_native(self):
        if not self.native_ready:self.show_error('先に原音を読み込んでください。');return
        path,_=QFileDialog.getSaveFileName(self,'生のfloat32 WAVを書出す','','Wave (*.wav)')
        if path:
            self.pause();self.apply_settings();self.send('export',(path,self.export_seconds.value()));self.log.appendPlainText('有限長書出し中（既存ファイルは上書きしません）')
    def render_sdk(self):
        if not self.source_path:self.show_error('先に原音を読み込んでください。');return
        if self.job and not self.job.done():self.show_error('比較レンダーが進行中です。');return
        self.pause();self.cancel.clear();dest=Path(self.temporary.name)/(uuid.uuid4().hex+'.wav')
        self.job=self.pool.submit(sdk_compare.render,self.source_path,dest,self.sdk_mode.currentIndex(),self.sdk_speed.value(),
            self.sdk_pitch.value(),self.sdk_policy.currentText(),self.sdk_formant.value(),self.sdk,self.cancel)
        self.reference_path=None;self._render_destination=dest;self.render_button.setEnabled(False);self.reference_label.setText('SDKレンダー中…')
    def open_reference(self):
        path,_=QFileDialog.getOpenFileName(self,'既存の研究出力を比較用に開く','','Audio (*.wav *.flac *.aiff *.ogg)')
        if path:self.reference_path=Path(path);self.reference_label.setText('外部比較音源（生成方式は未検証）: '+path)
    def play_reference(self):
        if not self.reference_path:self.show_error('比較音源を生成または開いてください。');return
        self.pause()
        if not self.devices:self.show_error('音声デバイスがありません。');return
        self.media_output.setDevice(self.devices[self.device.currentIndex()]);self.media.setSource(QUrl.fromLocalFile(str(self.reference_path)));self.media.play()
    def telemetry(self,state):
        self.last_state=state;self.wave.position=state['source_position']/self.worker.source_rate;self.wave.update()
        self.native_status.setText(f"{'FREEZE — 原音位置固定' if state['speed']==0 else '再生'} | 原音 {self.wave.position:.3f} s | 出力 {state['output_frames']/int(self.rate.currentText()):.3f} s | pitch {state['pitch_semitones']:+.2f} st | raw peak {state['peak']:.3f}"+('  ⚠ 1.0超（WAVは無制限）' if state['peak']>1 else ''))
    def poll(self):
        for _ in range(12):
            try:kind,data=self.worker.messages.get_nowait()
            except queue.Empty:break
            if kind=='ready':
                resume_requested=self.playing
                self.native_ready=True;self.playing=False;self.play_button.setText('▶ 再生');self.eof=False
                from PySide6.QtMultimedia import QAudioDevice
                device=self.devices[self.device.currentIndex()] if self.devices else QAudioDevice()
                if self.pump.configure(device,**data):
                    self.volume_changed()
                    if resume_requested and self.pump.play():
                        self.send('play');self.playing=True;self.play_button.setText('Ⅱ 一時停止')
            elif kind=='loaded':
                self.source_path=Path(data['path']);self.duration=data['frames']/data['rate'];self.wave.set_audio(data['waveform'],data['frames'],data['rate'])
                self.file_label.setText(f"{self.source_path.name}  |  {data['rate']} Hz  |  {data['waveform'].shape[1]} ch  |  {self.duration:.2f} s")
                self.log.appendPlainText('読込み完了。方式・速度を選択して再生できます。')
            elif kind=='error':
                self.pause();self.native_ready=self.source_path is not None;self.show_error(data)
                if self.source_path:self.file_label.setText('原音を維持: '+self.source_path.name)
            elif kind=='ended':self.eof=True
            elif kind=='exported':self.log.appendPlainText('WAV書出し完了: '+data)
        self.pump.tick()
        if self.eof and self.worker.audio.empty() and not self.pump.pending:
            if not self.pump.sink or self.pump.sink.bytesFree()>=self.pump.sink.bufferSize():self.pause();self.eof=False;self.native_status.setText('原音終端・tail出力完了')
        if self.job and self.job.done():
            job=self.job;self.job=None;self.render_button.setEnabled(True)
            try:
                receipt=job.result();self.reference_path=self._render_destination
                self.reference_label.setText(f"{receipt['mode']} | {receipt['output_frames']} frames | raw peak {receipt['peak']:.3f}\n無加工の比較WAVを生成しました。")
            except Exception as exc:self.show_error(str(exc));self.reference_label.setText('比較レンダー未完了（代替処理なし）')
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if urls and urls[0].isLocalFile():self.load(urls[0].toLocalFile())
    def closeEvent(self,event):
        self.timer.stop();self.debounce.stop();self.pump.close();self.media.stop();self.cancel.set();self.worker.stop_worker()
        self.worker.join(3);self.pool.shutdown(wait=True,cancel_futures=True)
        if self.worker.is_alive():self.show_error('ファイル処理終了を待ってから再度閉じてください。');self.timer.start();event.ignore();return
        self.temporary.cleanup();event.accept()

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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library');parser.add_argument('--sdk-cli');parser.add_argument('--file');parser.add_argument('--demo',action='store_true');parser.add_argument('--smoke',action='store_true');parser.add_argument('--screenshot',type=Path)
    args=parser.parse_args();app=QApplication(sys.argv[:1]);app.setStyle('Fusion');app.setStyleSheet(STYLE);window=MainWindow(args.library,args.sdk_cli);window.show()
    if args.file:window.load(args.file)
    elif args.demo or args.smoke:window.demo()
    if args.smoke or args.screenshot:
        def capture():
            if args.screenshot:args.screenshot.parent.mkdir(parents=True,exist_ok=True);window.grab().save(str(args.screenshot))
            if args.smoke:window.close()
        QTimer.singleShot(1600,capture)
    return app.exec()
if __name__=='__main__':raise SystemExit(main())
