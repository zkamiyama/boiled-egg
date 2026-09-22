"""Exact reviewed WSOLA correctness edits; keep the prior package audit intact."""
from pathlib import Path
import audit

CHANGES = {
    'src/engine.cpp': (
        '302fa71eb60cdfc8889f8b2f0ad3125b256dc2d1554d3893dc2dd4d150b92f12',
        'ea065158a1e27754ddd29475f847e655a5a89a583a5c80cac8aacf12c8ed6c6d'),
    'src/engine.hpp': (
        '7b3e1f8ba60b150f4f499fe748148b1495d03ecb91edfadd27564d8af945f80e',
        '56bf89d5cd0501cc82ba5f91e8b015ebc5a5c6434ee271952e2687114f6f82d3'),
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
                source_profile='fixed-wsola-duration-and-start-bound-v1',
                allowed_runtime_change={k: dict(before=v[0], after=v[1]) for k, v in CHANGES.items()})
