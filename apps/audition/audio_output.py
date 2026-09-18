"""Qt-only bounded PCM transfer with explicit output-device failure handling.

No native DSP runs here. The worker owns all source/transport operations.
QAudioSink state and buffer semantics follow Qt for Python 6.9.
"""
import queue
from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QAudioSink, QAudioFormat, QAudio

class OutputPump(QObject):
    """Only moves PCM bytes on the GUI thread. Never calls the DSP renderer.

    The device may accept partial writes; unconsumed bytes stay pending. Native
    queues contain at most2 blocks. Qt/OS buffering is additional and reported.
    """
    error=Signal(str)
    telemetry=Signal(dict)
    def __init__(self, audio_queue, parent=None):
        super().__init__(parent);self.queue=audio_queue;self.sink=None;self.io=None
        self.pending=b'';self.epoch=0;self.running=False;self.frame_bytes=8;self.generation=0
    def configure(self,device,rate,channels,epoch):
        self.close();self.epoch=epoch;self.frame_bytes=4*channels
        fmt=QAudioFormat();fmt.setSampleRate(rate);fmt.setChannelCount(channels);fmt.setSampleFormat(QAudioFormat.Float)
        if device.isNull() or not device.isFormatSupported(fmt):
            self.error.emit('選択デバイスはこのfloat32形式に未対応です。出力先・レートを変更してください。WAV書出しは利用できます。')
            return False
        self.sink=QAudioSink(device,fmt,self);self.sink.setBufferSize(4096*self.frame_bytes)
        generation=self.generation
        self.sink.stateChanged.connect(lambda state: self.device_state(generation,state))
        self.sink.setVolume(.25);self.io=self.sink.start()
        if self.io is None:
            self.error.emit('音声デバイスを開始できません。');self.close();return False
        self.sink.suspend();return True
    def play(self):
        if self.sink and self.io:
            self.sink.resume()
            if self.io is None or self.sink.state()==QAudio.StoppedState:
                self.running=False;return False
            self.running=True;return True
        return False
    def pause(self):
        self.running=False
        if self.sink:self.sink.suspend()
    def close(self):
        self.running=False;self.pending=b'';self.io=None;self.generation+=1
        old=self.sink;self.sink=None
        if old:old.reset();old.deleteLater()
    def device_state(self,generation,state):
        # Signals from an old stream must never stop its replacement.
        if generation!=self.generation or self.sink is None:return
        if state==QAudio.StoppedState and self.sink.error()!=QAudio.NoError:
            self.running=False;self.io=None;self.pending=b''
            self.error.emit('音声デバイスが停止しました。出力先を選び直してください。原音は保持しています。')
        # IdleState is also starvation, not necessarily EOF. The worker owns EOF.
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
                self.pause();self.io=None;self.error.emit('音声出力の書込みに失敗しました。');return
            if count==0:return
            self.pending=self.pending[count:]

