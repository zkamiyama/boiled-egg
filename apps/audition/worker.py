"""Bounded-buffer file player. DSP and file I/O stay off the Qt event thread."""
from __future__ import annotations
from dataclasses import dataclass
import math
import queue
import threading
from pathlib import Path
import numpy as np
import soundfile as sf
from native import Transport

@dataclass(frozen=True)
class Settings:
    mode: int = 1
    policy: int = 0
    speed: float = 1.
    pitch: float = 0.
    formant: float = 0.
    output_rate: int = 48000
    def __post_init__(self):
        if self.mode not in range(6) or self.policy not in range(3):raise ValueError('Unknown mode/policy')
        if not all(math.isfinite(v) for v in (self.speed,self.pitch,self.formant)):raise ValueError('Nonfinite controls')
        if not 0<=self.speed<=4 or abs(self.pitch)>24 or abs(self.formant)>12:raise ValueError('Controls outside supported range')
        if self.output_rate not in (44100,48000,96000):raise ValueError('Unsupported player output rate')
        if self.mode>=3 and self.policy:raise ValueError('Time-domain formants are unsupported')
        if not self.policy and self.formant:raise ValueError('Formant shift requires a preservation policy')

class PlayerWorker(threading.Thread):
    """Commands only, one native owner. Audio queue holds at most two blocks.
    Python/Qt buffering is not a hard-real-time callback guarantee.
    """
    def __init__(self, library=None):
        super().__init__(name='boiled-egg-dsp',daemon=True)
        self.library=library;self.commands=queue.Queue(maxsize=64);self.audio=queue.Queue(maxsize=2)
        self.messages=queue.Queue();self.quit_event=threading.Event();self.settings=Settings()
        self.source=None;self.source_rate=48000;self.handle=None;self.playing=False;self.epoch=0
    def command(self, kind, value=None):
        try:self.commands.put_nowait((kind,value))
        except queue.Full:raise RuntimeError('Command queue full; wait for current load/render to finish')
    def stop_worker(self):self.quit_event.set()
    def clear_audio(self):
        while True:
            try:self.audio.get_nowait()
            except queue.Empty:break
    def _rebuild(self, position=0., settings=None, source=None, rate=None):
        # Construct a candidate before publishing it. An unsupported selection
        # must not destroy the working source/handle or alter saved controls.
        settings=self.settings if settings is None else settings
        source=self.source if source is None else source
        rate=self.source_rate if rate is None else rate
        if source is None:
            self.settings=settings
            return
        candidate=Transport(source,rate,settings.mode,settings.policy,settings.output_rate,self.library)
        try:
            candidate.set(settings.speed,settings.pitch,settings.formant)
            candidate.seek(min(position,len(source)))
        except BaseException:
            candidate.close()
            raise
        old=self.handle
        self.playing=False;self.epoch+=1;self.clear_audio()
        self.handle=candidate;self.settings=settings;self.source=source;self.source_rate=rate
        if old:old.close()
        self.messages.put(('ready',dict(rate=settings.output_rate,channels=source.shape[1],epoch=self.epoch)))
        self.messages.put(('position',dict(source_seconds=self.handle.info()['source_position']/rate)))
    def _load(self,path):
        info=sf.info(path)
        if info.channels not in (1,2):raise ValueError('Player accepts mono/stereo files; no silent downmix')
        if info.frames*info.channels>32_000_000:raise ValueError('File exceeds player limit of32 million scalar samples')
        x,rate=sf.read(path,dtype='float32',always_2d=True)
        if not len(x) or not np.isfinite(x).all():raise ValueError('Empty/nonfinite file')
        self._rebuild(source=x,rate=rate)
        step=max(1,len(x)//1000);self.messages.put(('loaded',dict(path=str(path),rate=rate,frames=len(x),waveform=x[::step].copy())))
    def _apply(self,kind,value):
        if kind=='load':self._load(Path(value))
        elif kind=='play':
            if self.handle:self.playing=True
        elif kind=='pause':self.playing=False
        elif kind=='settings':
            if not isinstance(value,Settings):raise TypeError('Settings instance required')
            before=self.settings
            if self.handle:
                structural=(before.mode,before.policy,before.output_rate)!=(value.mode,value.policy,value.output_rate)
                if structural:self._rebuild(self.handle.info()['source_position'],settings=value)
                else:
                    # Freeze stops the source clock immediately at the next
                    # owned block; pitch/formant smoothing follows output time.
                    self.handle.render(0,[(0,0,value.speed,0),(0,1,value.pitch,round(.02*value.output_rate)),(0,2,value.formant,round(.02*value.output_rate))])
                    self.settings=value
            else:self.settings=value
        elif kind=='seek':
            if self.handle:
                self.handle.seek(float(value)*self.source_rate)
                self.playing=False;self.epoch+=1;self.clear_audio()
                self.messages.put(('ready',dict(rate=self.settings.output_rate,channels=self.source.shape[1],epoch=self.epoch)))
                self.messages.put(('position',dict(source_seconds=self.handle.info()['source_position']/self.source_rate)))
        elif kind=='export':self._export(*value)
        else:raise ValueError('Unknown worker command')
    def _export(self,path,seconds):
        if self.source is None:raise ValueError('Load a source first')
        path=Path(path)
        if path.exists():raise ValueError('Export must not overwrite an existing file')
        if not .1<=seconds<=120:raise ValueError('Export duration must be .1..120 seconds, including freeze')
        self.playing=False
        source_position=self.handle.info()['source_position'] if self.handle else 0
        total=round(seconds*self.settings.output_rate)
        # Exclusive creation prevents accidentally truncating a source/project.
        with path.open('xb') as raw:
            try:
                with Transport(self.source,self.source_rate,self.settings.mode,self.settings.policy,self.settings.output_rate,self.library) as h:
                    h.set(self.settings.speed,self.settings.pitch,self.settings.formant);h.seek(source_position)
                    with sf.SoundFile(raw,mode='w',samplerate=self.settings.output_rate,channels=self.source.shape[1],format='WAV',subtype='FLOAT') as stream:
                        for pos in range(0,total,1024):
                            if self.quit_event.is_set():raise InterruptedError('Export cancelled')
                            stream.write(h.render(min(1024,total-pos)))
            except BaseException:
                raw.close();path.unlink(missing_ok=True);raise
        self.messages.put(('exported',str(path)))
    def run(self):
        try:
            while not self.quit_event.is_set():
                try:
                    while True:
                        kind,value=self.commands.get_nowait();self._apply(kind,value)
                except queue.Empty:pass
                except Exception as exc:
                    self.playing=False;self.messages.put(('error',str(exc)))
                if self.playing and self.handle and not self.audio.full():
                    try:
                        output=self.handle.render(1024)
                        state=self.handle.info();state['peak']=float(np.max(np.abs(output)))
                        self.audio.put_nowait((self.epoch,output.astype('<f4',copy=False).tobytes(),state))
                        if state['ended']:self.playing=False;self.messages.put(('ended',None))
                    except Exception as exc:
                        self.playing=False;self.messages.put(('error',str(exc)))
                else:self.quit_event.wait(.003)
        finally:
            if self.handle:self.handle.close();self.handle=None
