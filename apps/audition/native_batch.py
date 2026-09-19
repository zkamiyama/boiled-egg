"""Finite same-anchor comparison of all six native C++ transport modes.

This renders from source PCM, never from another algorithm's output. Freeze is
owned by the native renderer. No gain/lag fitting, hidden policy changes or
hardware output are involved. An incomplete mode never publishes a WAV result.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import soundfile as sf
from native import NATIVE_MODES, Transport, library_path


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def render_batch(source, source_rate, directory, position, seconds, speed=0.,
                 pitch=0., policy=0, formant=0., output_rate=48000,
                 library=None, cancel=None, progress=None):
    """One owner thread. `progress` receives bounded per-mode progress notices.

    Snapshot current loaded audio rather than reopening a potentially modified
    pathname. Source/output clocks and memory are verified for every native run.
    A set cancellation event cancels all unstarted modes and removes partial WAVs.
    """
    if not all(math.isfinite(v) for v in (position, seconds, speed, pitch, formant)):
        raise ValueError('Finite position, duration and controls required')
    if (not .1 <= seconds <= 120 or not 0 <= speed <= 4 or abs(pitch) > 24
            or policy not in (0, 1, 2) or abs(formant) > 12 or (not policy and formant)):
        raise ValueError('Native comparison controls outside declared range')
    if (not isinstance(source_rate, int) or not 8000 <= source_rate <= 192000
            or output_rate not in (44100, 48000, 96000)):
        raise ValueError('Unsupported source or output rate')
    x = np.asarray(source, dtype='float32')
    if (x.ndim != 2 or x.shape[1] not in (1, 2) or not len(x)
            or x.size > 32_000_000 or not np.isfinite(x).all() or np.max(np.abs(x)) > 16
            or not 0 <= position <= len(x)):
        raise ValueError('Finite mono/stereo source and in-range anchor required')
    x = np.array(x, dtype='<f4', order='C', copy=True)
    x.setflags(write=False)
    pcm_sha = hashlib.sha256(memoryview(x).cast('B')).hexdigest()
    native = library_path(library)  # Missing library is not an alternate engine.
    binary_sha = _sha(native)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    total = round(seconds * output_rate)
    plan = dict(schema='boiled-egg.native-comparison.v1', source_pcm_sha256=pcm_sha,
                source_frames=len(x), source_rate=source_rate, channels=x.shape[1],
                source_position=position, output_rate=output_rate, output_frames=total,
                speed=speed, pitch_semitones=pitch, formant_policy=policy,
                formant_semitones=formant, library_sha256=binary_sha,
                evaluator_sha256=_sha(__file__),
                notes='Native transport modes, not legacy SDK/research equivalents; '
                      'independent fresh histories; no normalization or alignment.')
    _json(directory / 'plan.json', plan)
    rows = []
    for label, mode in NATIVE_MODES:
        row = dict(index=mode, mode=label, status='pending')
        path = directory / f'native-{mode}.wav'
        receipt_path = path.with_suffix('.wav.json')
        created = []
        if cancel is not None and cancel.is_set():
            row.update(status='cancelled', reason='Native comparison cancelled')
        elif mode >= 3 and policy:
            row.update(status='unsupported', reason='Time-domain formant policy unsupported; no fallback')
        else:
            try:
                with Transport(x, source_rate, mode, policy, output_rate, native) as handle:
                    handle.set(speed, pitch, formant)
                    handle.seek(position)
                    before = handle.info()
                    peak = 0.
                    with path.open('xb') as raw:
                        created.append(path)
                        with sf.SoundFile(raw, mode='w', format='WAV', subtype='FLOAT',
                                          channels=x.shape[1], samplerate=output_rate) as stream:
                            for offset in range(0, total, 1024):
                                if cancel is not None and cancel.is_set():
                                    raise InterruptedError('Native comparison cancelled')
                                audio = handle.render(min(1024, total - offset))
                                if not np.isfinite(audio).all():
                                    raise ValueError('Nonfinite native output')
                                peak = max(peak, float(np.max(np.abs(audio))))
                                stream.write(audio)
                    after = handle.info()
                if cancel is not None and cancel.is_set():
                    raise InterruptedError('Native comparison cancelled')
                info = sf.info(path)
                expected_position = min(len(x), position + speed * total * source_rate / output_rate)
                if (info.frames != total or info.channels != x.shape[1]
                        or info.samplerate != output_rate or info.subtype != 'FLOAT'
                        or after['output_frames'] != total
                        or abs(after['source_position'] - expected_position) > 1e-7
                        or before['owned_bytes'] != after['owned_bytes']
                        or (speed == 0 and after['source_position'] != position)):
                    raise ValueError('Native output metadata, source clock or memory contract failed')
                receipt = dict(plan, mode=label, mode_index=mode, peak=peak,
                               final_source_position=after['source_position'],
                               synthesis_frames=after['synthesis_frames'],
                               owned_bytes=after['owned_bytes'], output_sha256=_sha(path))
                # Exclusive creation: only files created by this attempt are removed.
                with receipt_path.open('x', encoding='utf-8') as stream:
                    created.append(receipt_path)
                    json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.write('\n')
                row.update(status='passed', output=path.name, receipt=receipt)
            except Exception as exc:
                for created_path in reversed(created):
                    created_path.unlink(missing_ok=True)
                row.update(status='cancelled' if isinstance(exc, InterruptedError) else 'failed',
                           reason=str(exc))
        rows.append(row)
        if progress is not None:
            progress(dict(completed=len(rows), total=len(NATIVE_MODES), mode=label, status=row['status']))
    if _sha(native) != binary_sha:
        raise ValueError('Native library changed during rendering; comparison not accepted')
    report = dict(plan, source_name='Loaded source PCM', results=rows,
                  complete=len(rows) == len(NATIVE_MODES),
                  all_passed=all(r['status'] == 'passed' for r in rows))
    _json(directory / 'comparison.json', report)
    return report
