#!/usr/bin/env python3
"""Run a complete declared CTest suite; zero/disabled/missing tests fail closed."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def validate_inventory(inventory: dict, expected: int) -> list[str]:
    tests = inventory.get('tests')
    if expected <= 0 or not isinstance(tests, list) or len(tests) != expected:
        raise ValueError(f'Expected {expected} CTests, found {len(tests) if isinstance(tests, list) else "no inventory"}')
    names = []
    for test in tests:
        name = test.get('name')
        if not isinstance(name, str) or not name or not test.get('command'):
            raise ValueError('Missing test name or executable command')
        if any(p.get('name') == 'DISABLED' and p.get('value') not in (False, 'FALSE', 'OFF', '0', 0)
               for p in test.get('properties', [])):
            raise ValueError(f'Disabled CTest: {name}')
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError('Duplicate CTest names')
    return names


def validate_results(suite: ET.Element, names: list[str]) -> None:
    cases = suite.findall('testcase')
    actual = [case.get('name') for case in cases]
    if sorted(actual) != sorted(names) or len(actual) != len(set(actual)):
        raise ValueError('Executed CTest names differ from the declared inventory')
    if (suite.tag != 'testsuite' or int(suite.get('tests', '-1')) != len(names)
            or any(int(suite.get(k, '-1')) != 0 for k in ('failures', 'disabled', 'skipped'))):
        raise ValueError('CTest contains failed, disabled, skipped or missing results')
    for case in cases:
        if case.get('status') != 'run' or any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped')):
            raise ValueError('CTest did not execute successfully: ' + str(case.get('name')))


def run(build: Path, expected: int) -> None:
    command = ['ctest', '--test-dir', str(build.resolve())]
    inventory = json.loads(subprocess.check_output(command + ['--show-only=json-v1'], text=True))
    names = validate_inventory(inventory, expected)
    print(f'Confirmed {len(names)} enabled, executable CTests in {build}', flush=True)
    report = build.resolve() / 'Testing' / 'audition-complete.xml'
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)  # Never accept a result left by an older run.
    subprocess.run(command + ['--output-on-failure', '--no-tests=error',
                              '--output-junit', str(report)], check=True)
    validate_results(ET.parse(report).getroot(), names)
    print(f'Confirmed {len(names)} executed passes (zero skips)', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--expected', type=int, required=True)
    a = p.parse_args()
    run(a.build, a.expected)
