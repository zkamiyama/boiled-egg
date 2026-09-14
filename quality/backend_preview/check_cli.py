#!/usr/bin/env python3
"""CLI option/calibration smoke: no external audio, third-party engine or MOS."""
import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile
import wave


def check(cli: Path, spectral: bool) -> int:
    def run(*args):
        return subprocess.run([str(cli), *map(str,args)], capture_output=True, text=True, timeout=30)
    inventory=run('--list-backends')
    assert inventory.returncode==0,inventory.stderr
    assert 'backend=wsola status=stable' in inventory.stdout
    assert ('backend=pv status='+('experimental' if spectral else 'unavailable')) in inventory.stdout
    checks=1
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);src=root/'input.wav'
        with wave.open(str(src),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
            w.writeframes(b''.join(struct.pack('<h',(i%101-50)*100) for i in range(6001)))
        initial=hashlib.sha256(src.read_bytes()).digest()
        common=['--backend','pv','--allow-experimental','--quality','transient','--formant','harmonic']
        invalid=[['--pitch-ratio','1','--pitch-semitones','0'],['--formant-ratio','1','--formant-semitones','0'],
                 ['--time','nan'],['--block','0'],['--quality','unknown']]
        for flags in invalid:
            dst=root/'bad.wav';p=run(src,dst,*flags)
            assert p.returncode!=0 and not dst.exists(),(flags,p.stdout,p.stderr)
            checks+=1
        alias=root/'alias.wav';alias.symlink_to(src)
        assert run(src,alias).returncode!=0
        assert hashlib.sha256(src.read_bytes()).digest()==initial
        checks+=1
        if spectral:
            a,b=root/'ratio.wav',root/'semitones.wav'
            assert run(src,a,*common,'--pitch-ratio','2','--formant-ratio','0.5').returncode==0
            assert run(src,b,*common,'--pitch-semitones','12','--formant-semitones','-12').returncode==0
            assert a.read_bytes()==b.read_bytes()
            assert run(src,root/'denied.wav','--backend','pv').returncode!=0
            checks+=2
        else:
            dst=root/'disabled.wav';assert run(src,dst,*common).returncode!=0 and not dst.exists();checks+=1
    return checks

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cli',type=Path,required=True);p.add_argument('--spectral',choices=('ON','OFF'),required=True)
    a=p.parse_args();print(check(a.cli.resolve(strict=True),a.spectral=='ON'),'CLI checks passed')
