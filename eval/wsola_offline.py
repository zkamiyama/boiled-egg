#!/usr/bin/env python3
"""Explicit finite-file WSOLA configuration study, NOT a realtime product mode.

All DSP is the actual supplied C ABI library. No signal-dependent preset choice,
backend fallback, learned score, gain/lag fitting, or input resampling is used.
"""
from __future__ import annotations
import argparse
import ctypes as ct
import io
import math
from pathlib import Path
import struct
import time
import numpy as np
import soundfile as sf
import comparison_contract as contract

PROFILES = ('default', 'wide_only', 'long_only', 'long_wide')
RATES = (48000, 96000)
MAX_BYTES = 3 * 96000 * 4 + 65536
F32P = ct.POINTER(ct.c_float)
U32P = ct.POINTER(ct.c_uint32)


class Config(ct.Structure):
    _fields_ = [(name, ct.c_uint32) for name in
                ('struct_size', 'abi_version', 'sample_rate', 'channels',
                 'max_block_size', 'window_frames', 'search_frames', 'fifo_frames')]


class Runtime(ct.Structure):
    _fields_ = [(name, ct.c_uint32) for name in
                ('struct_size', 'sample_rate', 'channels', 'max_block_size',
                 'realtime_latency_frames', 'realtime_tail_frames',
                 'parameter_quantum_frames', 'capabilities')]


def configuration(rate: int, block: int, profile: str, shift: float) -> tuple[int, int]:
    if rate not in RATES or block not in (32, 64, 1024):
        raise ValueError('scope: 48/96k and blocks32/64/1024 only')
    if profile not in PROFILES or not math.isfinite(shift) or not -12 <= shift <= 12:
        raise ValueError('explicit known profile and pitch[-12,+12] required')
    window, search = (1024, 128) if rate == 48000 else (1536, 192)
    if profile == 'wide_only': search = window // 4 - 1
    if profile.startswith('long_'): window = 4096 if rate == 48000 else 8192
    if profile == 'long_wide': search = rate // 50
    # Existing SDK scheduler cannot start if expected-search is negative.
    # This research host only exposes presets that avoid that unmodified path.
    if search > window / 2 / (2 ** (shift / 12)):
        raise ValueError('configuration exceeds supported startup search')
    return window, search


def samples(value: np.ndarray, rate: int) -> np.ndarray:
    x = np.asarray(value)
    if rate not in RATES or x.ndim != 1 or not 0 < len(x) <= 3 * rate:
        raise ValueError('nonempty mono48/96k input of at most3seconds required')
    if not np.isfinite(x).all() or float(np.max(np.abs(x))) > 1:
        raise ValueError('finite normalized input required; not clipped by host')
    if float(np.mean(x.astype(np.float64) ** 2)) <= 1e-16:
        raise ValueError('silent input is not a quality test')
    return np.ascontiguousarray(x, dtype=np.float32)


def read_input(path: Path) -> tuple[np.ndarray, int]:
    """Bounded RIFF preflight; use the same bytes for validation and decode."""
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or len(raw) < 44:
        raise ValueError('input byte limit or incomplete WAV')
    if raw[:4] != b'RIFF' or raw[8:12] != b'WAVE' or struct.unpack_from('<I', raw, 4)[0] != len(raw)-8:
        raise ValueError('exact RIFF/WAVE length required')
    chunks = {}; pos = 12
    while pos < len(raw):
        if pos+8 > len(raw): raise ValueError('truncated chunk header')
        name, size = struct.unpack_from('<4sI', raw, pos); pos += 8
        end = pos + size
        if end+(size & 1) > len(raw): raise ValueError('truncated chunk data/padding')
        if name in (b'fmt ', b'data'):
            if name in chunks: raise ValueError('duplicate format/data chunk')
            chunks[name] = raw[pos:end]
        pos = end + (size & 1)
    if set(chunks) != {b'fmt ', b'data'} or len(chunks[b'fmt ']) < 16:
        raise ValueError('missing format/data')
    tag, channels, rate, byte_rate, align, bits = struct.unpack_from('<HHIIHH', chunks[b'fmt '])
    if channels != 1 or rate not in RATES or (tag, bits) not in ((1, 16), (3, 32)):
        raise ValueError('mono PCM16/float32 48/96k WAV only')
    data = chunks[b'data']
    if align != bits//8 or byte_rate != rate*align or not data or len(data) % align:
        raise ValueError('invalid sample layout')
    if len(data)//align > 3*rate: raise ValueError('at most3seconds')
    x, actual_rate = sf.read(io.BytesIO(raw), dtype='float32')
    if actual_rate != rate or len(x) != len(data)//align:
        raise ValueError('decoder/header mismatch')
    return samples(x, rate), rate


class Native:
    """Single-owner synchronous host of an explicitly selected trusted library."""
    def __init__(self, library: Path, sha256: str):
        self.path = library.resolve(strict=True)
        if contract.fingerprint(self.path) != sha256:
            raise ValueError('library hash mismatch before loading')
        self.sha256 = sha256
        self.lib = ct.CDLL(str(self.path))
        signatures = {
            'default_config': ([ct.c_uint32, ct.c_uint32], Config),
            'abi_version': ([], ct.c_uint32),
            'create': ([ct.POINTER(Config), ct.POINTER(ct.c_int)], ct.c_void_p),
            'destroy': ([ct.c_void_p], None),
            'reset': ([ct.c_void_p], ct.c_int),
            'set_pitch_ratio': ([ct.c_void_p, ct.c_float], ct.c_int),
            'push': ([ct.c_void_p, ct.POINTER(F32P), ct.c_uint32, U32P], ct.c_int),
            'pull': ([ct.c_void_p, ct.POINTER(F32P), ct.c_uint32, U32P], ct.c_int),
            'available': ([ct.c_void_p], ct.c_uint32),
            'flush': ([ct.c_void_p], ct.c_int),
            'is_drained': ([ct.c_void_p], ct.c_int),
            'get_runtime_info': ([ct.c_void_p, ct.POINTER(Runtime)], ct.c_int),
            'input_latency_frames': ([ct.c_void_p], ct.c_uint32),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.lib, 'boiledegg_' + name)
            fn.argtypes, fn.restype = args, result
        if self.lib.boiledegg_abi_version() != 1:
            raise ValueError('unsupported C ABI')

    def render(self, value: np.ndarray, rate: int, shift: float, profile: str,
               block: int, reset_check: bool = False) -> tuple[np.ndarray, dict]:
        x = samples(value, rate)
        window, search = configuration(rate, block, profile, shift)
        c = self.lib.boiledegg_default_config(rate, 1)
        if c.struct_size != ct.sizeof(Config) or c.abi_version != 1:
            raise ValueError('configuration ABI shape changed')
        c.max_block_size, c.window_frames, c.search_frames = block, window, search
        c.fifo_frames = 262144
        started = time.perf_counter(); error = ct.c_int()
        handle = self.lib.boiledegg_create(ct.byref(c), ct.byref(error))
        if not handle or error.value: raise RuntimeError(f'create failed:{error.value}')
        creation_seconds = time.perf_counter() - started
        try:
            info = Runtime(); info.struct_size = ct.sizeof(info)
            if self.lib.boiledegg_get_runtime_info(handle, ct.byref(info)):
                raise RuntimeError('runtime metadata failed')
            metadata = {n: int(getattr(info, n)) for n, _ in info._fields_}
            metadata.update(window_frames=window, search_frames=search, fifo_frames=c.fifo_frames,
                            input_latency_frames=self.lib.boiledegg_input_latency_frames(handle),
                            creation_seconds=creation_seconds, execution='offline', profile=profile,
                            backend='actual_sdk_wsola', time_ratio=1, formant='off')
            if self.lib.boiledegg_set_pitch_ratio(handle, ct.c_float(2 ** (shift/12))):
                raise RuntimeError('pitch rejected')
            output = self._stream(handle, x, block)
            if reset_check:
                if self.lib.boiledegg_reset(handle): raise RuntimeError('reset failed')
                again = self._stream(handle, x, block)
                if not np.array_equal(output, again): raise RuntimeError('reset changed output')
        finally:
            self.lib.boiledegg_destroy(handle)
        metadata['host_render_seconds'] = time.perf_counter() - started
        return output, metadata

    def _stream(self, handle, x: np.ndarray, block: int) -> np.ndarray:
        # Enough output for exactly time1; no normalization, fitting or truncation.
        y = np.empty(len(x), dtype=np.float32); scratch = np.empty(block, dtype=np.float32)
        op = (F32P * 1)(scratch.ctypes.data_as(F32P)); offset = 0; calls = 0
        def pull() -> int:
            nonlocal offset, calls
            n = ct.c_uint32()
            rc = self.lib.boiledegg_pull(handle, op, block, ct.byref(n)); calls += 1
            if rc or n.value > block or offset+n.value > len(y):
                raise RuntimeError('invalid native pull/length')
            y[offset:offset+n.value] = scratch[:n.value]; offset += n.value
            return n.value
        pos = 0
        while pos < len(x):
            count = min(block, len(x)-pos); accepted = ct.c_uint32()
            ip = (F32P*1)(ct.cast(x.ctypes.data+pos*4, F32P))
            rc = self.lib.boiledegg_push(handle, ip, count, ct.byref(accepted)); calls += 1
            if rc not in (0, 3) or accepted.value > count: raise RuntimeError('native push failed')
            pos += accepted.value; pulled = 0
            while self.lib.boiledegg_available(handle):
                n = pull(); pulled += n
                if not n: raise RuntimeError('available but pull stalled')
            if not accepted.value and not pulled: raise RuntimeError('stream stalled')
            if calls > len(x)*4+10000: raise RuntimeError('bounded host progress exceeded')
        if self.lib.boiledegg_flush(handle): raise RuntimeError('flush failed')
        while not self.lib.boiledegg_is_drained(handle):
            if not pull(): raise RuntimeError('EOF stalled')
            if calls > len(x)*4+10000: raise RuntimeError('bounded EOF exceeded')
        if offset != len(y) or not np.isfinite(y).all() or np.mean(y.astype(float)**2) <= 1e-16:
            raise RuntimeError('partial, nonfinite or zero native output')
        return y


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--library', type=Path, required=True); p.add_argument('--library-sha256', required=True)
    p.add_argument('--execution', choices=['offline'], required=True)
    p.add_argument('--allow-experimental', action='store_true')
    p.add_argument('--profile', choices=PROFILES, required=True)
    p.add_argument('--pitch-semitones', type=float, default=0)
    p.add_argument('--block', type=int, default=64)
    args = p.parse_args(); created = False
    try:
        args.output.mkdir(parents=True, exist_ok=False); created = True
        if not args.allow_experimental: raise ValueError('explicit research opt-in required')
        before = contract.fingerprint(args.input)
        x, rate = read_input(args.input)
        native = Native(args.library, args.library_sha256)
        y, metadata = native.render(x, rate, args.pitch_semitones, args.profile, args.block)
        if before != contract.fingerprint(args.input): raise ValueError('input changed')
        out = args.output/'output.wav'; sf.write(out, y, rate, subtype='FLOAT')
        contract.json_write(args.output/'report.json', dict(status='complete', input_sha256=before,
            output=contract.inspect_audio(out), library_sha256=native.sha256,
            metadata=metadata, quality_selection=None, realtime_qualified=False))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        if created:
            contract.json_write(args.output/'report.json', dict(status='blocked', errors=[str(exc)],
                quality_selection=None))
        print(str(exc)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
