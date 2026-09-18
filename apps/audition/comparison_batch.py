"""Same-input comparison of the five *actual* legacy SDK modes.

No normalization, fitted alignment, hidden policy changes or freeze emulation.
The source is snapshotted once. Unsupported/failed/cancelled modes remain in the
manifest instead of being dropped or replaced by a different algorithm.
"""
from __future__ import annotations
import json
import shutil
import threading
from pathlib import Path
import sdk_compare


def render_batch(source, directory, speed, pitch, policy='off', formant=0.,
                 executable=None, cancel: threading.Event | None = None):
    source = Path(source).resolve(strict=True)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    source_hash = sdk_compare.sha(source)
    snapshot = directory / ('source' + source.suffix)
    shutil.copyfile(source, snapshot)
    if sdk_compare.sha(snapshot) != source_hash:
        raise ValueError('Source changed during snapshot; no comparison accepted')
    results = []
    for index, (name, _, _) in enumerate(sdk_compare.SDK_MODES):
        row = dict(index=index, mode=name, status='pending')
        if cancel is not None and cancel.is_set():
            row.update(status='cancelled', reason='Comparison cancelled')
        else:
            try:
                sdk_compare.validate(index, speed, pitch, policy, formant)
            except ValueError as exc:
                row.update(status='unsupported', reason=str(exc))
            else:
                output = directory / f'mode-{index}.wav'
                try:
                    receipt = sdk_compare.render(snapshot, output, index, speed, pitch,
                                                 policy, formant, executable, cancel)
                    row.update(status='passed', output=output.name, receipt=receipt)
                except InterruptedError as exc:
                    row.update(status='cancelled', reason=str(exc))
                    if cancel is not None:
                        cancel.set()
                except Exception as exc:
                    row.update(status='failed', reason=str(exc))
        results.append(row)
    # Snapshot mutation is an audit failure, not a partly successful comparison.
    if sdk_compare.sha(snapshot) != source_hash:
        raise ValueError('Comparison input changed; results are invalid')
    report = dict(schema='boiled-egg.audition-comparison.v1',
                  source_name=source.name, source_sha256=source_hash,
                  speed=speed, pitch_semitones=pitch, policy=policy,
                  formant_semitones=formant, results=results,
                  complete=len(results) == len(sdk_compare.SDK_MODES),
                  all_passed=all(row['status'] == 'passed' for row in results),
                  notes='Actual SDK modes; not new transport modes or historical research algorithms.')
    with (directory/'comparison.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return report


def save_result(source, destination):
    """Copy a selected raw output and its receipt, never overwrite either file."""
    source, destination = Path(source), Path(destination)
    old_receipt = source.with_suffix(source.suffix+'.json')
    new_receipt = destination.with_suffix(destination.suffix+'.json')
    if any(p.exists() or p.is_symlink() for p in (destination, new_receipt)):
        raise FileExistsError('Destination audio or receipt already exists')
    receipt = json.loads(old_receipt.read_text(encoding='utf-8')) if old_receipt.is_file() else None
    expected = sdk_compare.sha(source)
    if receipt is not None and receipt['output_sha256'] != expected:
        raise ValueError('Selected output no longer matches its receipt')
    created = []
    try:
        with destination.open('xb') as out:
            created.append(destination)
            with source.open('rb') as inp:
                shutil.copyfileobj(inp, out)
        if sdk_compare.sha(destination) != expected:
            raise ValueError('Selected audio changed during copy')
        if receipt is not None:
            with new_receipt.open('x', encoding='utf-8') as out:
                created.append(new_receipt)
                json.dump(receipt, out, ensure_ascii=False, indent=2, allow_nan=False)
                out.write('\n')
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return destination
