"""One exact length-four edit after all previously accepted runtime scopes."""
from pathlib import Path
import audit
import fft_stage_scope
CHANGES = {'src/experimental/pv/fft.cpp': ('bf6a0c99952c1983f611488f5cb029c77d5dd5858c86f122853f79a70a870b5c', 'fe63eae1e8113c71d40a0da519108ad6be723d4bcf48ce3f1297899077f18333')}

def check_runtime(reference: Path,current: Path) -> dict:
    expected={**audit.directory(reference,'src'),**audit.directory(reference,'include')}
    for path,(old,new) in CHANGES.items():
        if expected.get(path)!=old:raise ValueError('unknown FFT-four reference: '+path)
        expected[path]=new
    if expected!={**audit.directory(current,'src'),**audit.directory(current,'include')}:
        raise ValueError('runtime differs beyond exact length-four FFT batching')
    return expected

def source_contract(main,donor,current,package,duration,formant,ring,fft,four,host):
    parent=fft_stage_scope.source_contract(main,donor,four,package,duration,formant,ring,fft,host)
    runtime=check_runtime(four,current);protected=dict(runtime)
    for prefix in ('adapters','eval','research'):
        expected=audit.directory(four,prefix)
        if not expected or expected!=audit.directory(current,prefix):
            raise ValueError('protected FFT-four '+prefix+' changed')
        protected.update(expected)
    return dict(protected_sha256=protected,donor_runtime_sha256=parent['donor_runtime_sha256'],
        protected_files=len(protected),runtime_files=len(runtime),source_profile='exact-pv-fft-length-four-v1',
        allowed_runtime_change={k:dict(before=v[0],after=v[1]) for k,v in CHANGES.items()})
