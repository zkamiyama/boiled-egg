"""Exact reviewed WSOLA budget and same-output cost edits; keep the prior package audit intact."""
from pathlib import Path
import audit

CHANGES = {
    'src/engine.cpp': (
        '302fa71eb60cdfc8889f8b2f0ad3125b256dc2d1554d3893dc2dd4d150b92f12',
        '11424ebdd51e05eed0f727ea86dc7573a9f58b0afa11e67141bc94f04dc6aef8'),
    'src/engine.hpp': (
        '7b3e1f8ba60b150f4f499fe748148b1495d03ecb91edfadd27564d8af945f80e',
        'eb76fd256ab270fe80aa68199788f67be630ebe0a46508cbf376bf6c16b8f445'),
}


def check_runtime(reference: Path, current: Path) -> dict:
    expected = {**audit.directory(reference, 'src'), **audit.directory(reference, 'include')}
    for path, (old, new) in CHANGES.items():
        if expected.get(path) != old:
            raise ValueError('unknown duration reference runtime: ' + path)
        expected[path] = new
    if expected != {**audit.directory(current, 'src'), **audit.directory(current, 'include')}:
        raise ValueError('runtime differs beyond fixed duration corrections')
    return expected


def source_contract(main: Path, donor: Path, current: Path, package_reference: Path,
                    duration_reference: Path, host_reference: Path | None = None) -> dict:
    # The extra immutable reference must itself pass the original package scope.
    parent = audit.packaging_source_contract(main, donor, duration_reference,
                                            package_reference, host_reference)
    runtime = check_runtime(duration_reference, current)
    protected = dict(runtime)
    for prefix in ('adapters', 'eval', 'research'):
        files = audit.directory(duration_reference, prefix)
        if not files or files != audit.directory(current, prefix):
            raise ValueError('protected duration ' + prefix + ' tree changed')
        protected.update(files)
    return dict(protected_sha256=protected, donor_runtime_sha256=parent['donor_runtime_sha256'],
                protected_files=len(protected), runtime_files=len(runtime),
                source_profile='fixed-wsola-budget-overlap-cost-v1',
                allowed_runtime_change={k: dict(before=v[0], after=v[1]) for k, v in CHANGES.items()})
