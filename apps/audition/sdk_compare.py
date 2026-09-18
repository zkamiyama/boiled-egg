"""Render the existing SDK's actual modes, never replace them with native hold.

This finite-file comparison is deliberately separate from output-driven playback.
No arbitrary subprocess commands, hidden fallback, gain fitting or padding.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import threading
import time
import numpy as np
import soundfile as sf
from native import ROOT

SDK_MODES = (
    ('SDK WSOLA / General', 'wsola', 'general'),
    ('SDK WSOLA / Transient', 'wsola', 'transient'),
    ('SDK WSOLA / Efficient', 'wsola', 'efficient'),
    ('SDK PV / General', 'pv', 'general'),
    ('SDK PV / Transient', 'pv', 'transient'),
)

def cli_path(explicit=None):
    requested=explicit or os.getenv('BOILED_EGG_SDK_CLI')
    candidates=[Path(requested)] if requested else [ROOT/p/'boiled_egg_backend_cli' for p in ('build-sdk','build','bin')]
    for p in candidates:
        if p.is_file():return p.resolve()
    raise FileNotFoundError('Build the SDK with spectral ON into build-sdk, or set BOILED_EGG_SDK_CLI.')

def validate(index, speed, pitch, policy, formant):
    if type(index) is not int or index not in range(len(SDK_MODES)):raise ValueError('Unknown SDK mode')
    if policy not in ('off','harmonic','monophonic'):raise ValueError('Unknown policy')
    if not all(math.isfinite(v) for v in (speed,pitch,formant)):raise ValueError('Finite controls required')
    backend=SDK_MODES[index][1]
    lo,hi,limit=(.25,4.,24.) if backend=='wsola' else (.5,2.,12.)
    if not lo<=speed<=hi or abs(pitch)>limit:raise ValueError(f'Existing {backend} SDK: speed {lo}..{hi}, pitch +/-{limit} st. Speed0 requires the separate native transport.')
    if abs(formant)>12 or (policy=='off' and formant!=0):raise ValueError('Formant shift requires an enabled policy')
    if backend=='wsola' and policy!='off':raise ValueError('Existing WSOLA does not preserve formants; no fallback')
    return backend

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def render(source, destination, index, speed, pitch, policy='off', formant=0.,
           executable=None, cancel: threading.Event | None=None):
    backend=validate(index,speed,pitch,policy,formant)
    exe=cli_path(executable);source=Path(source);destination=Path(destination)
    sidecar=destination.with_suffix(destination.suffix+'.json')
    if any(p.exists() or p.is_symlink() for p in (destination,sidecar)):raise FileExistsError('Never overwrite comparison audio or receipt')
    metadata=sf.info(source)
    if metadata.channels not in (1,2) or metadata.frames==0:raise ValueError('Nonempty mono/stereo required')
    if metadata.frames/metadata.samplerate/speed>120:raise ValueError('Comparison output is limited to120 seconds; select a shorter source')
    if backend=='pv' and metadata.samplerate not in (44100,48000,88200,96000):raise ValueError('SDK PV supports44.1/48/88.2/96k; no implicit conversion')
    audio,rate=sf.read(source,dtype='float32',always_2d=True)
    if not np.isfinite(audio).all():raise ValueError('Nonfinite input')
    # Private conversion accepts FLAC/etc without modifying the source file.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='boiled-egg-sdk-') as tmp:
        incoming=Path(tmp)/'input.wav';outgoing=Path(tmp)/'output.wav'
        sf.write(incoming,audio,rate,subtype='FLOAT')
        command=[str(exe),str(incoming),str(outgoing),'--backend',backend,'--quality',SDK_MODES[index][2],
                 '--formant',policy,'--time',format(1/speed,'.17g'),'--pitch-semitones',str(pitch),
                 '--formant-semitones',str(formant),'--block','64']
        if backend=='pv':command+=['--allow-experimental']
        env=os.environ.copy();env['LD_LIBRARY_PATH']=str(exe.parent)+os.pathsep+str(ROOT/'lib')+os.pathsep+env.get('LD_LIBRARY_PATH','')
        with tempfile.TemporaryFile(mode='w+b') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env)
            start=time.monotonic()
            try:
                while process.poll() is None:
                    if cancel and cancel.wait(.03):raise InterruptedError('SDK render cancelled')
                    if not cancel:time.sleep(.03)
                    if time.monotonic()-start>300:raise TimeoutError('SDK render timeout')
            except BaseException:
                process.terminate()
                try:process.wait(3)
                except subprocess.TimeoutExpired:process.kill();process.wait()
                raise
            log.seek(0);output=log.read().decode('utf-8','replace')
        if process.returncode:raise RuntimeError(output[-4000:])
        result=sf.info(outgoing);y,_=sf.read(outgoing,always_2d=True)
        expected=round(metadata.frames*float(np.float32(1/speed)))
        if result.samplerate!=rate or result.channels!=metadata.channels or abs(result.frames-expected)>1 or result.subtype!='FLOAT' or not np.isfinite(y).all():raise ValueError('SDK output failed format/duration/finiteness check')
        # Exclusive write and retained receipt; raw PCM is not normalized.
        with destination.open('xb') as stream:stream.write(outgoing.read_bytes())
    receipt=dict(mode=SDK_MODES[index][0],speed=speed,pitch_semitones=pitch,policy=policy,formant_semitones=formant,
                 input_sha256=sha(source),output_sha256=sha(destination),executable_sha256=sha(exe),
                 output_frames=result.frames,rate=rate,channels=result.channels,peak=float(abs(y).max()),stdout=output)
    with sidecar.open('x') as stream:stream.write(json.dumps(receipt,indent=2)+'\n')
    return receipt
