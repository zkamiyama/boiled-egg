#!/usr/bin/env python3
"""Install, relocate and execute the existing SDK's public C11/C++ contracts.

This is an integration check, not a hardware, DAW or general audio-quality test.
Only a new evidence directory is written; supplied build/source trees are not moved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'quality' / 'audition'))
from run_ctest import validate_inventory, validate_results


def hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def cache_options(build: Path) -> dict[str, str]:
    options = {}
    for line in (build / 'CMakeCache.txt').read_text(encoding='utf-8').splitlines():
        if not line or line.startswith(('#', '//')) or '=' not in line or ':' not in line.split('=', 1)[0]:
            continue
        key, value = line.split('=', 1)
        options[key.split(':', 1)[0]] = value
    return options


def require_build(options: dict[str, str], linkage: str, spectral: str) -> None:
    expected = {'BOILED_EGG_BUILD_SHARED': linkage == 'shared',
                'BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL': spectral == 'ON'}
    for key, value in expected.items():
        actual = options.get(key, '').upper()
        if actual not in ('ON', 'OFF', '1', '0', 'TRUE', 'FALSE'):
            raise ValueError(f'Missing or unsupported build option: {key}')
        if (actual in ('ON', '1', 'TRUE')) != value:
            raise ValueError(f'Build does not match declared {key}')


def run(build: Path, output: Path, linkage: str, spectral: str, configuration: str) -> dict:
    build = build.resolve(strict=True)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='boiled-egg.relocated-sdk.v1', status='failed', linkage=linkage,
                  spectral=spectral, configuration=configuration, platform=platform.platform(),
                  python=sys.version, commands=[], hardware_verified=False, daw_verified=False)
    env = os.environ.copy()
    # Don't satisfy this package check with another SDK on the loader search path.
    for key in ('LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH'):
        env.pop(key, None)
    def invoke(argv: list[str], name: str, require_success: bool = True) -> subprocess.CompletedProcess:
        start = time.perf_counter()
        result = subprocess.run(argv, env=env, cwd=output, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=180)
        (output / (name + '.log')).write_text(result.stdout, encoding='utf-8')
        report['commands'].append(dict(argv=argv, returncode=result.returncode,
                                      seconds=time.perf_counter()-start, log=name+'.log'))
        if require_success and result.returncode:
            raise RuntimeError(f'{name} failed ({result.returncode}); see {name}.log')
        return result
    try:
        options = cache_options(build)
        require_build(options, linkage, spectral)
        report['build_cache_sha256'] = hashlib.sha256((build/'CMakeCache.txt').read_bytes()).hexdigest()
        stage = output/'original prefix'
        moved = output/'relocated SDK'
        invoke(['cmake', '--install', str(build), '--config', configuration, '--prefix', str(stage)], 'install')
        before = hashes(stage)
        if not before or not (stage/'include/boiled_egg/boiled_egg.h').is_file():
            raise ValueError('Public SDK installation is absent')
        if any('research' in p.lower() or 'experimental' in p.lower()
               for p in before if p.startswith('include/')):
            raise ValueError('Private research header installed')
        stage.rename(moved)
        if stage.exists() or before != hashes(moved):
            raise ValueError('Relocation changed files or left original prefix')
        configs = list(moved.rglob('boiled_eggConfig.cmake'))
        if len(configs) != 1:
            raise ValueError('Expected exactly one installed CMake config')
        report['package_files'] = before
        report['original_prefix_absent'] = True
        for path in moved.rglob('*.cmake'):
            text = path.read_text(encoding='utf-8')
            if str(stage).replace('\\', '/') in text.replace('\\', '/') or str(build).replace('\\', '/') in text.replace('\\', '/'):
                raise ValueError('Installed metadata retains original prefix/build path')
        fixtures = output/'consumer sources'
        for name in ('backend_install', 'install_relocated'):
            shutil.copytree(ROOT/'tests'/name, fixtures/name)
        report['consumer_source_files'] = hashes(fixtures)
        if platform.system() == 'Windows':
            env['PATH'] = str(moved/'bin') + os.pathsep + env.get('PATH', '')
        args = ['cmake', '-S', str(fixtures/'install_relocated'),
                '-Dboiled_egg_DIR='+str(configs[0].parent), '-DEXPECT_LINKAGE='+linkage,
                '-DEXPECT_SPECTRAL='+('1' if spectral == 'ON' else '0'),
                '-DCMAKE_BUILD_TYPE='+configuration,
                '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF', '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF']
        # Negative control: an exported library is missing, so configure must fail.
        suffixes = ('.a', '.lib') if linkage == 'static' else ('.dll', '.dylib', '.so')
        libs = sorted(p for p in moved.rglob('*') if p.is_file() and
                      p.name in ('libboiled_egg.a', 'boiled_egg.lib', 'boiled_egg.dll',
                                 'libboiled_egg.so', 'libboiled_egg.dylib') and p.suffix in suffixes)
        if len(libs) != 1:
            raise ValueError(f'Expected exactly one {linkage} SDK binary: {libs}')
        library = libs[0]
        disabled = library.with_name(library.name+'.missing-control')
        library.rename(disabled)
        try:
            negative = invoke(args+['-B', str(output/'missing consumer')], 'missing-library', False)
            if negative.returncode == 0 or library.name not in negative.stdout or 'does not exist' not in negative.stdout:
                raise ValueError('Missing-library negative control did not fail for the expected reason')
        finally:
            disabled.rename(library)
        report['missing_library_rejected'] = True
        consumer_build = output/'consumer build'
        invoke(args+['-B', str(consumer_build)], 'consumer-configure')
        invoke(['cmake', '--build', str(consumer_build), '--config', configuration, '--parallel', '2'], 'consumer-build')
        ctest = ['ctest', '--test-dir', str(consumer_build), '-C', configuration]
        result = invoke(ctest+['--show-only=json-v1'], 'inventory')
        inventory = json.loads(result.stdout)
        names = validate_inventory(inventory, 5)
        junit = output/'consumer-tests.xml'
        invoke(ctest+['--verbose', '--output-on-failure', '--no-tests=error', '--output-junit', str(junit)], 'consumer-tests')
        validate_results(ET.parse(junit).getroot(), names)
        if hashes(moved) != before:
            raise ValueError('Installed package changed during consumer tests')
        report.update(status='passed', test_names=names, executed=5, skipped=0)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError, ET.ParseError) as exc:
        report['error'] = str(exc)
    finally:
        (output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--linkage', choices=('shared', 'static'), required=True)
    p.add_argument('--spectral', choices=('ON', 'OFF'), required=True)
    p.add_argument('--configuration', default='Release')
    a = p.parse_args()
    try:
        result = run(a.build, a.output, a.linkage, a.spectral, a.configuration)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({k: result[k] for k in ('status', 'linkage', 'spectral')}))
    return 0 if result['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
