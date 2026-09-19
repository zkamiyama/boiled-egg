#!/usr/bin/env python3
"""Real Qt -> isolated PulseAudio null sink -> monitor capture, not a DAC test.

Needs pulseaudio/pactl/parec. No mocks, default-device changes or real sinks.
A missing audio route fails this dedicated test rather than skipping it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import numpy as np
import soundfile as sf


def require(condition, message):
    if not condition: raise RuntimeError(message)


def run(output):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    for name in ('pulseaudio','pactl','parec'):
        if not shutil.which(name): raise RuntimeError('Missing dedicated loopback dependency: '+name)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    with tempfile.TemporaryDirectory(prefix='be-qt-route-') as tmp:
        root=Path(tmp); socket=root/'native'; runtime=root/'runtime';runtime.mkdir(mode=0o700)
        env=dict(os.environ,PULSE_SERVER='unix:'+str(socket),XDG_RUNTIME_DIR=str(runtime))
        # Only this process and its children use this private software server.
        os.environ['PULSE_SERVER']=env['PULSE_SERVER'];os.environ['XDG_RUNTIME_DIR']=env['XDG_RUNTIME_DIR']
        with (output/'pulse.log').open('wb') as log:
            pulse=subprocess.Popen(['pulseaudio','-n','--daemonize=no','--exit-idle-time=-1',
                '--disable-shm=yes','--log-level=info',
                '--load=module-native-protocol-unix socket='+str(socket)+' auth-anonymous=1'],
                stdout=log,stderr=subprocess.STDOUT,env=env)
            window=None;recorder=None
            try:
                deadline=time.monotonic()+10
                while not socket.exists() and pulse.poll() is None and time.monotonic()<deadline: time.sleep(.02)
                require(socket.exists(),'Private PulseAudio server did not start')
                def pactl(*args):
                    return subprocess.check_output(['pactl',*args],env=env,text=True,stderr=subprocess.STDOUT,timeout=10).strip()
                module=pactl('load-module','module-null-sink','sink_name=be_audition',
                    'rate=48000','channels=2','format=float32le','sink_properties=device.description=BoiledEggVirtual')
                # Import Multimedia only after selecting the isolated server.
                from PySide6.QtWidgets import QApplication
                from PySide6.QtCore import QSettings
                from app import MainWindow
                qt=QApplication.instance() or QApplication([])
                def spin(predicate,seconds=8):
                    deadline=time.monotonic()+seconds
                    while not predicate() and time.monotonic()<deadline:
                        qt.processEvents();time.sleep(.002)
                    require(predicate(),'Qt audio route state did not complete')
                window=MainWindow(language='en',preferences=QSettings(str(root/'settings.ini'),QSettings.IniFormat))
                require(len(window.devices)==1,'Private server must expose exactly one test sink')
                device_name=window.devices[0].description()
                window.speed.setValue(0);window.pitch.setValue(12);window.apply_settings();window.debounce.stop()
                rate=48000;t=np.arange(rate)/rate
                left=.1*np.cos(2*np.pi*223*t);source=root/'tone.wav'
                sf.write(source,np.c_[left,-.375*left],rate,subtype='FLOAT')
                window.load(source);spin(lambda:window.native_ready and window.source_path==source)
                window.seek(.25);spin(lambda:window.wave.position==.25)
                window.volume.setValue(50)
                with (output/'capture.f32').open('wb') as capture,(output/'parec.log').open('wb') as errors:
                    recorder=subprocess.Popen(['parec','--raw','--format=float32le','--channels=2','--rate=48000',
                        '--latency-msec=50','--device=be_audition.monitor'],stdout=capture,stderr=errors,env=env)
                    window.toggle_play();require(window.playing,'Actual QAudioSink did not start')
                    deadline=time.monotonic()+3.5
                    while time.monotonic()<deadline:
                        qt.processEvents();time.sleep(.001)
                    require(recorder.poll() is None,'Monitor recorder exited early')
                    require(window.playing and window.pump.running,'Qt output stopped while rendering')
                    state=dict(window.last_state)
                    recorder.terminate();recorder.wait(timeout=5);recorder=None
                # Real device removal notification, no monkeypatched Qt enumerator.
                pactl('unload-module',module)
                spin(lambda:window.selected_device() is None and not window.playing)
                require(window.native_ready,'Device removal destroyed the loaded source')
                require('disconnected' in window.log.toPlainText(),'Missing disconnect diagnostic')
                replacement=pactl('load-module','module-null-sink','sink_name=be_replacement',
                    'rate=48000','channels=2','sink_properties=device.description=AnotherVirtual')
                spin(lambda:len(window.devices)==1)
                require(window.device.currentIndex()==-1,'New device was silently selected')
                pactl('unload-module',replacement)
                window.close();spin(lambda:window.closed)
                data=np.fromfile(output/'capture.f32',dtype='<f4')
                require(len(data)%2==0,'Partial captured stereo frame')
                y=data.reshape(-1,2)
                require(np.isfinite(y).all(),'Nonfinite monitor capture')
                active=np.flatnonzero(np.abs(y[:,0])>.005)
                require(len(active)>rate//2,'Monitor contains no sustained audio')
                # Selecting an active window verifies the route, not a fitted DSP
                # latency or source-relative quality metric. No gain fitting.
                start=int(active[0])+round(.6*rate);stop=start+rate
                require(stop<=len(y),'Insufficient settled captured audio')
                segment=y[start:stop];x=segment[:,0];energy=float(np.sum(x*x))
                require(energy>0,'Silent route is not a pass')
                rms=float(np.sqrt(energy/len(x)))
                residual=float(np.sqrt(np.sum((segment[:,1]+.375*x)**2)/energy))
                spectrum=np.abs(np.fft.rfft(x*np.hanning(len(x)),n=1048576))
                peak=int(np.argmax(spectrum));logs=np.log(np.maximum(spectrum[peak-1:peak+2],1e-30))
                delta=.5*(logs[0]-logs[2])/(logs[0]-2*logs[1]+logs[2])
                frequency=float((peak+delta)*rate/1048576);cents=float(1200*np.log2(frequency/446.))
                require(abs(cents)<5 and .01<rms<.07 and residual<1e-4,'Captured pitch/level/stereo route check failed')
                require(state.get('source_position')==12000. and state.get('output_frames',0)>rate,'Freeze clock not held')
                report=dict(schema='boiled-egg.qt-software-route.v1',passed=True,physical_output_verified=False,
                    route='C++ transport -> real Qt QAudioSink -> isolated PulseAudio null sink -> monitor',
                    captured_frames=len(y),sample_rate=rate,channels=2,device_description=device_name,
                    source_hz=223,pitch_semitones=12,expected_hz=446,measured_hz=frequency,pitch_error_cents=cents,
                    rms=rms,stereo_residual=residual,source_position=state['source_position'],
                    output_frames=state['output_frames'],real_unplug_notified=True,automatic_reroute=False,
                    analysis_start_frame=start,analysis_frames=rate,
                    capture_sha256=hashlib.sha256((output/'capture.f32').read_bytes()).hexdigest(),
                    verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    notes='Software route only; no speaker/DAC, hardware latency or perceptual certification.')
                (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
                return report
            finally:
                if recorder is not None:
                    recorder.terminate();recorder.wait(timeout=5)
                if window is not None and not window.closed:
                    window.close()
                    deadline=time.monotonic()+5
                    while not window.closed and time.monotonic()<deadline:
                        qt.processEvents();time.sleep(.005)
                pulse.terminate()
                try:pulse.wait(timeout=5)
                except subprocess.TimeoutExpired:pulse.kill();pulse.wait()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.output),indent=2))
