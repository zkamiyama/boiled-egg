"""Exact opt-in formant-detail scope; all predecessor contracts remain active."""
from pathlib import Path
import audit
import duration_scope
CHANGES = {'include/boiled_egg/backend.h': ('d23f568195a418a83f2e5d05557f164a714ec730c85e256134ef615c4301fe8d', '97e42ebb6e8384366ed02fbd7674ace53d0feb313e391117f2c9c26ddbe8a172'), 'src/backend.cpp': ('168ff95bcfc02e44d77dbd30e541279f9ecaf906dc06ad8912b76b9c36469615', '3ee58b68b09ebec001761bf65d1b78d2d0fec5041dfcb364e129bbaecb0e1cd2'), 'src/spectral_backend.cpp': ('8c4423882c10f2a44c7dbb9fd4a3052a495fb5be7ff0bd2ed4368f72c3274096', '569686898e391aac952ab739841e47ba58a3459d4646e5ac03a28ac7cf8e27fe')}

def check_runtime(reference: Path, current: Path) -> dict:
    expected={**audit.directory(reference,'src'),**audit.directory(reference,'include')}
    for path,(old,new) in CHANGES.items():
        if expected.get(path)!=old:raise ValueError('unknown formant reference: '+path)
        expected[path]=new
    if expected!={**audit.directory(current,'src'),**audit.directory(current,'include')}:
        raise ValueError('runtime differs beyond reviewed formant option')
    return expected

def source_contract(main,donor,current,package_reference,duration_reference,formant_reference,host):
    parent=duration_scope.source_contract(main,donor,formant_reference,package_reference,duration_reference,host)
    runtime=check_runtime(formant_reference,current);protected=dict(runtime)
    for prefix in ('adapters','eval','research'):
        expected=audit.directory(formant_reference,prefix)
        if not expected or expected!=audit.directory(current,prefix):raise ValueError('protected formant '+prefix+' changed')
        protected.update(expected)
    return dict(protected_sha256=protected,donor_runtime_sha256=parent['donor_runtime_sha256'],
        protected_files=len(protected),runtime_files=len(runtime),source_profile='explicit-formant-low-detail-v1',
        allowed_runtime_change={k:dict(before=v[0],after=v[1]) for k,v in CHANGES.items()})
