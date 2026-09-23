"""One exact FFT edit after the complete pinned ring/formant/duration scope."""
from pathlib import Path
import audit
import ring_scope
CHANGES = {'src/experimental/pv/fft.cpp': ('e29498183d75e15856a5deedadbf152b6948b19119f9fc7186577839d1c1adaf', 'bf6a0c99952c1983f611488f5cb029c77d5dd5858c86f122853f79a70a870b5c')}

def check_runtime(reference: Path,current: Path) -> dict:
    expected={**audit.directory(reference,'src'),**audit.directory(reference,'include')}
    for path,(old,new) in CHANGES.items():
        if expected.get(path)!=old:raise ValueError('unknown FFT-stage reference: '+path)
        expected[path]=new
    if expected!={**audit.directory(current,'src'),**audit.directory(current,'include')}:
        raise ValueError('runtime differs beyond exact first-stage FFT batching')
    return expected

def source_contract(main,donor,current,package,duration,formant,ring,fft,host):
    parent=ring_scope.source_contract(main,donor,fft,package,duration,formant,ring,host)
    runtime=check_runtime(fft,current);protected=dict(runtime)
    for prefix in ('adapters','eval','research'):
        expected=audit.directory(fft,prefix)
        if not expected or expected!=audit.directory(current,prefix):
            raise ValueError('protected FFT-stage '+prefix+' changed')
        protected.update(expected)
    return dict(protected_sha256=protected,donor_runtime_sha256=parent['donor_runtime_sha256'],
        protected_files=len(protected),runtime_files=len(runtime),source_profile='exact-pv-fft-first-stage-v1',
        allowed_runtime_change={k:dict(before=v[0],after=v[1]) for k,v in CHANGES.items()})
