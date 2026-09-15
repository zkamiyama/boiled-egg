"""Roadmap B: exact-configuration render receipts and operation evidence.

Evaluation glue only. No vendor source, automatic fallback or product linking.
Passing a two-second tone diagnostic authorizes exploratory listening for that
exact operation, NOT alignment, formant fidelity, human quality or RT claims.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any

import numpy as np
import scipy
import soundfile as sf

import comparison_contract as c
from reference_rubberband import Reference
from calibrate_external import OPERATIONS, pitch_cents


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def inside(root: Path, relative: str) -> Path:
    p = (root / relative).resolve(strict=True)
    if root.resolve() not in p.parents:
        raise ValueError('evidence path escapes root')
    return p


@dataclass(frozen=True)
class Candidate:
    name: str
    kind: str
    path: str
    quality: str = 'general'
    formant: str = 'off'
    block: int = 32
    generation: int = 3

    def __post_init__(self):
        if self.formant != 'off':
            raise ValueError('this operation-eligibility implementation supports Off only; no policy substitution')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', self.name):
            raise ValueError('invalid candidate name')
        if self.kind == 'rubberband_direct':
            if (self.quality != 'general' or type(self.generation) is not int or self.generation not in (2,3)
                    or type(self.block) is not int or not 1 <= self.block <= 4096):
                raise ValueError('invalid explicit direct-reference configuration')
        else:
            self.cli()  # Reuse exact A-stage engine validation.
            if self.generation != 3:
                raise ValueError('generation only applies to direct Rubber Band')

    def cli(self) -> c.Engine:
        return c.Engine(self.name, self.kind, self.path, self.quality, self.formant, self.block)

    def probe(self) -> dict:
        if self.kind != 'rubberband_direct':
            backend = self.cli().probe()
            files = {backend['executable']: backend['sha256'], **backend['dependencies']}
        else:
            ref = Reference(Path(self.path))
            # Only explicitly supplied trusted local libraries are probed.
            dep = subprocess.run(['ldd', str(ref.path)], capture_output=True, text=True, timeout=15)
            if dep.returncode or 'not found' in dep.stdout:
                raise ValueError('cannot resolve direct reference dependencies')
            files = {str(ref.path): ref.sha256}
            for line in dep.stdout.splitlines():
                match = re.search(r'(?:=>\s+)?(/\S+)', line)
                if match:
                    path = Path(match.group(1)).resolve(strict=True)
                    files[str(path)] = c.fingerprint(path)
            backend = dict(library=str(ref.path), mode='offline-study-and-process', generation=self.generation,
                           dependency_probe=dep.stdout, formant=self.formant, block=self.block,
                           version_scope='generation verified at construction; file hashes identify installed build')
        wrappers = {str(Path(module.__file__).resolve()): c.fingerprint(Path(module.__file__))
                    for module in (c, __import__('reference_rubberband'), __import__('calibrate_external'))}
        wrappers[str(Path(__file__).resolve())] = c.fingerprint(Path(__file__))
        return dict(config=asdict(self), backend=backend, files=files, wrappers=wrappers,
                    software=dict(numpy=np.__version__, scipy=scipy.__version__, soundfile=sf.__version__),
                    alignment_verified=False, formant_fidelity_verified=False)


def stable(probe: dict) -> bool:
    try:
        return all(c.fingerprint(Path(p)) == h for p,h in {**probe['files'], **probe['wrappers']}.items())
    except OSError:
        return False


def render(candidate: Candidate, probe: dict, source: Path, request: c.Request, case: Path) -> dict:
    if candidate != Candidate(**probe['config']) or not stable(probe):
        raise ValueError('candidate/configuration identity changed')
    if candidate.kind != 'rubberband_direct':
        receipt = c.render_case(candidate.cli(), probe['backend'], source, request, case)
    else:
        case.mkdir(parents=True, exist_ok=False)
        receipt = dict(schema=c.SCHEMA, engine=candidate.name, request=asdict(request),
                       source=str(source.resolve()), status='failed', errors=[], output=None,
                       command=None, mode='offline-direct-C-API')
        c.json_write(case/'started.json', receipt)
        before = None
        try:
            before = c.inspect_audio(source)
            receipt['source_metadata'] = before
            receipt['expected_frames'] = request.target_frames(before['frames'])
            x,rate = sf.read(source, dtype='float32', always_2d=True)
            y,details = Reference(Path(candidate.path)).render(x, rate, request,
                candidate.generation, candidate.formant, candidate.block)
            sf.write(case/'output.wav', y, rate, subtype='FLOAT')
            actual = c.inspect_audio(case/'output.wav')
            receipt.update(output=actual, raw_output_sha256=actual['sha256'], details=details,
                           duration_error_frames=actual['frames']-receipt['expected_frames'])
            receipt['errors'].extend(c.output_checks(before, actual, request))
        except (ValueError, RuntimeError, OSError) as exc:
            receipt['errors'].append(f'{type(exc).__name__}: {exc}')
        finally:
            if before is not None and c.fingerprint(source) != before['sha256']:
                receipt['errors'].append('source changed')
    if not stable(probe):
        receipt['errors'].append('candidate changed during render')
    receipt['candidate_identity'] = digest(probe)
    receipt['status'] = 'failed' if receipt['errors'] else 'passed'
    c.json_write(case/'receipt.json', receipt)
    return receipt


def operation_key(rate: int, channels: int, request: dict) -> str:
    r = c.Request(**request)
    return digest([rate, channels, asdict(r)])


def case_key(name: str, rate: int, channels: int, request: dict) -> str:
    return digest([name, operation_key(rate, channels, request)])


def panel_validate(panel: list[Candidate]) -> None:
    if not panel or len({p.name for p in panel}) != len(panel):
        raise ValueError('unique nonempty candidate panel required')


def calibrate(panel: list[Candidate], root: Path, rates=(44100,48000,96000), channels=(1,2),
              operations=OPERATIONS) -> dict:
    panel_validate(panel)
    if (not rates or len(set(rates)) != len(rates) or not set(rates) <= {44100,48000,88200,96000}
            or not channels or len(set(channels)) != len(channels) or not set(channels) <= {1,2}):
        raise ValueError('invalid calibration dimensions')
    requests = [asdict(c.Request.from_semitones(t,p)) for t,p in operations]
    if not requests or len({digest(r) for r in requests}) != len(requests):
        raise ValueError('unique calibration operations required')
    probes = {p.name:p.probe() for p in panel}
    root.mkdir(parents=True, exist_ok=False); (root/'sources').mkdir()
    source_meta = {}
    for rate in rates:
        for ch in channels:
            tone = .125*np.sin(2*np.pi*440*np.arange(rate*2)/rate)
            x = tone[:,None] if ch==1 else np.c_[tone,-.5*tone]
            path = root/'sources'/f'{rate}-{ch}.wav';sf.write(path,x,rate,subtype='FLOAT')
            source_meta[f'{rate}-{ch}'] = dict(path=str(path.relative_to(root)), metadata=c.inspect_audio(path))
    plan = dict(schema='boiled-egg.operation-plan.v1', probes=probes, rates=list(rates), channels=list(channels),
                requests=requests, sources=source_meta, threshold_cents=5., stereo_relative_threshold=1e-5,
                time_exclusion_seconds=.25, pitch_metric_sha256=c.fingerprint(Path(__import__('calibrate_external').__file__)))
    c.json_write(root/'plan.json', plan)
    rows=[]
    for rate in rates:
        for ch in channels:
            source = root/source_meta[f'{rate}-{ch}']['path']
            for rq in requests:
                request = c.Request(**rq)
                for p in panel:
                    key = case_key(p.name,rate,ch,rq); case = root/'cases'/key
                    receipt=render(p,probes[p.name],source,request,case)
                    row=dict(candidate=p.name,rate=rate,channels=ch,request=rq,key=key,
                             case=str(case.relative_to(root)), receipt_sha256=c.fingerprint(case/'receipt.json'),
                             eligible=False,cents_error=None,stereo_relative_error=None,errors=list(receipt['errors']))
                    if receipt['status']=='passed':
                        y,_=sf.read(case/'output.wav',dtype='float64',always_2d=True)
                        try:
                            row['cents_error']=pitch_cents(y[:,0],rate,440*request.pitch_ratio)
                            if abs(row['cents_error'])>plan['threshold_cents']:
                                row['errors'].append('dominant-frequency calibration failed')
                            if ch==2:
                                row['stereo_relative_error']=float(np.sqrt(np.sum((y[:,1]+.5*y[:,0])**2)/max(np.sum(y[:,0]**2),1e-30)))
                                if row['stereo_relative_error']>plan['stereo_relative_threshold']:
                                    row['errors'].append('linked-channel calibration failed')
                        except ValueError as exc:row['errors'].append(str(exc))
                    row['eligible']=not row['errors'];rows.append(row)
        print('calibrated rate',rate,'rows',len(rows),flush=True)
    c.json_write(root/'rows.json', rows)
    report=dict(schema='boiled-egg.operation-evidence.v1',plan_sha256=c.fingerprint(root/'plan.json'),
                rows_sha256=c.fingerprint(root/'rows.json'),rows=len(rows),eligible=sum(r['eligible'] for r in rows),
                passed=all(r['eligible'] for r in rows),identities_stable=all(stable(p) for p in probes.values()),
                alignment_verified=False,formant_fidelity_verified=False,listening_status='not_listened',
                scope='Exact-operation 440Hz/anti-phase diagnostic only. Not a quality rank or native-zplane comparison.')
    c.json_write(root/'summary.json',report)
    return report


def verify_calibration(root: Path) -> tuple[dict,dict]:
    root=root.resolve(strict=True)
    report=json.loads((root/'summary.json').read_text());plan=json.loads((root/'plan.json').read_text())
    if (report.get('schema')!='boiled-egg.operation-evidence.v1' or not report.get('identities_stable')
            or c.fingerprint(root/'plan.json')!=report['plan_sha256']
            or c.fingerprint(root/'rows.json')!=report['rows_sha256']):
        raise ValueError('invalid calibration identity or integrity')
    rows=json.loads((root/'rows.json').read_text())
    expected={case_key(name,rate,ch,rq) for name in plan['probes'] for rate in plan['rates']
              for ch in plan['channels'] for rq in plan['requests']}
    keys=[r['key'] for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected or len(rows)!=report['rows']:
        raise ValueError('incomplete/duplicate calibration grid')
    for source in plan['sources'].values():
        if c.inspect_audio(inside(root,source['path']))!=source['metadata']:
            raise ValueError('changed calibration input')
    for row in rows:
        name=row['candidate'];rq=row['request']
        if case_key(name,row['rate'],row['channels'],rq)!=row['key']:
            raise ValueError('calibration operation identity')
        case=inside(root,row['case'])
        if c.fingerprint(case/'receipt.json')!=row['receipt_sha256']:
            raise ValueError('changed calibration receipt')
        receipt=json.loads((case/'receipt.json').read_text())
        source=plan['sources'][f"{row['rate']}-{row['channels']}"]['metadata']
        if receipt['request']!=rq or receipt['candidate_identity']!=digest(plan['probes'][name]) or receipt.get('source_metadata')!=source:
            raise ValueError('receipt source/configuration does not match plan')
        if row['eligible']:
            c.verify_case(case)
            if row['errors'] or row['cents_error'] is None or not math.isfinite(row['cents_error']) or abs(row['cents_error'])>5:
                raise ValueError('failed pitch diagnostic relabeled eligible')
            if row['channels']==2 and (row['stereo_relative_error'] is None or not math.isfinite(row['stereo_relative_error']) or row['stereo_relative_error']>1e-5):
                raise ValueError('failed stereo diagnostic relabeled eligible')
        elif receipt.get('output') is not None and c.inspect_audio(case/'output.wav')!=receipt['output']:
            raise ValueError('failed raw output changed')
    if report['eligible']!=sum(r['eligible'] for r in rows) or report['passed']!=all(r['eligible'] for r in rows):
        raise ValueError('incorrect aggregate calibration status')
    return plan,{r['key']:r for r in rows}


def require_eligible(plan: dict, rows: dict, probe: dict, rate: int, channels: int, request: c.Request) -> str:
    name=probe['config']['name']
    if name not in plan['probes'] or plan['probes'][name]!=probe:
        raise ValueError('uncalibrated candidate/configuration')
    key=case_key(name,rate,channels,asdict(request))
    if key not in rows or not rows[key]['eligible']:
        raise ValueError('requested operation is untested or failed calibration')
    return key
