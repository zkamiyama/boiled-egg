"""Exact ring-address scope, chained through every accepted predecessor."""
from pathlib import Path
import audit
import formant_scope
CHANGES = {'src/experimental/pv/pv_rt.cpp': ('c79aba1eefca528ebab198bdd2a1bb57a9fb149ed5c2c2b952cd49c239687c41', '7aeafc61d018001e61014eb0d5eb473e70958f45a9c38826c945efb05f6d0949'), 'src/experimental/pv/pv_execution.inc': ('1d91b63ce1ce311d8f240379f2dc0a281d6ba98b2b0798ba31979a2762eb1d0e', '6334496384347a632b65f00a0ccf753b8ad76656a5c409535a923db5b0392a59')}
ADDITIONS = {'src/experimental/pv/ring_index.hpp': 'be934fabb894ab0ed1963eb625d019eeedec7fde2c6b346d59e0d0b4143c0140'}

def check_runtime(reference: Path,current: Path) -> dict:
    expected={**audit.directory(reference,'src'),**audit.directory(reference,'include')}
    for path,(old,new) in CHANGES.items():
        if expected.get(path)!=old:raise ValueError('unknown ring reference: '+path)
        expected[path]=new
    for path,digest in ADDITIONS.items():
        if path in expected:raise ValueError('ring helper already in reference')
        expected[path]=digest
    if expected!={**audit.directory(current,'src'),**audit.directory(current,'include')}:
        raise ValueError('runtime differs beyond exact ring addresses')
    return expected

def source_contract(main,donor,current,package,duration,formant,ring,host):
    parent=formant_scope.source_contract(main,donor,ring,package,duration,formant,host)
    runtime=check_runtime(ring,current);protected=dict(runtime)
    for prefix in ('adapters','eval','research'):
        expected=audit.directory(ring,prefix)
        if not expected or expected!=audit.directory(current,prefix):raise ValueError('protected ring '+prefix+' changed')
        protected.update(expected)
    return dict(protected_sha256=protected,donor_runtime_sha256=parent['donor_runtime_sha256'],
        protected_files=len(protected),runtime_files=len(runtime),source_profile='exact-pv-ring-address-v1',
        allowed_runtime_change={k:dict(before=v[0],after=v[1]) for k,v in CHANGES.items()},
        allowed_runtime_additions=ADDITIONS)
