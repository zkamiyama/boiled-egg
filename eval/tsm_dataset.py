#!/usr/bin/env python3
"""Utilities for the Roberts/Paliwal TSM subjective-quality test set.

The dataset files themselves are not redistributed from this repository. This
module builds a local manifest, computes deterministic objective diagnostics,
renders boiled egg at matched ratios, and fits a deliberately modest MOS proxy.
The proxy is an engineering triage aid, not the published OMOQ implementation
and not a substitute for controlled listening tests.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import soundfile as sf
from scipy import signal, stats

EPS = 1.0e-12
AUDIO_SUFFIXES = {".wav", ".wave"}


@dataclasses.dataclass(frozen=True)
class DatasetPaths:
    root: Path
    references: Path
    processed: Path
    scores_csv: Path
    manifest_csv: Path


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for item in zf.infolist():
            target = (destination / item.filename).resolve()
            if target != base and base not in target.parents:
                raise ValueError(f"unsafe ZIP member: {item.filename}")
        zf.extractall(destination)


def _all_audio(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.casefold() in AUDIO_SUFFIXES)


def _slug(text: str) -> str:
    text = text.casefold().replace("\\", "/")
    text = Path(text).name
    text = re.sub(r"\.(wav|wave)$", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _boundary_prefix(candidate: str, reference: str) -> bool:
    c = Path(candidate).stem.casefold()
    r = Path(reference).stem.casefold()
    if not c.startswith(r):
        return False
    return len(c) == len(r) or c[len(r)] in "_.- ()[]"


def _audio_info(path: Path) -> tuple[int, int, int]:
    info = sf.info(path)
    return int(info.frames), int(info.samplerate), int(info.channels)


def _guess_method(path: Path, processed_root: Path) -> str:
    known = {
        "elastique": "Elastique", "elastiquepro": "Elastique",
        "fuzzytsm": "FuzzyTSM", "fuzzy": "FuzzyTSM",
        "nmftsm": "NMFTSM", "nmf": "NMFTSM",
    }
    parts = [p.casefold() for p in path.relative_to(processed_root).parts[:-1]]
    stem = path.stem.casefold()
    for token in [*reversed(parts), stem]:
        compact = re.sub(r"[^a-z0-9]+", "", token)
        for needle, canonical in known.items():
            if needle in compact:
                return canonical
    return Path(parts[-1]).name if parts else "unknown"


def _find_dataset_subtree(root: Path, expected_count: int | None = None) -> Path:
    candidates: list[tuple[int, int, Path]] = []
    for p in [root, *[q for q in root.rglob("*") if q.is_dir()]]:
        count = len(_all_audio(p))
        if count:
            exact = int(expected_count is not None and count == expected_count)
            candidates.append((exact, -len(p.parts), p))
    if not candidates:
        raise FileNotFoundError(f"no WAV files under {root}")
    candidates.sort(reverse=True)
    return candidates[0][2]


def _read_score_rows(scores_csv: Path) -> tuple[list[dict[str, str]], list[str]]:
    with scores_csv.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        rows = [{str(k): ("" if v is None else str(v).strip()) for k, v in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def _detect_mos_column(rows: Sequence[dict[str, str]], fields: Sequence[str]) -> str:
    preferred = ("MeanOS", "Mean_OS", "MOS", "MeanMOS", "Mean MOS", "Final MOS", "mean_os", "meanmos", "mos")
    normalized = {re.sub(r"[^a-z0-9]+", "", f.casefold()): f for f in fields}
    for name in preferred:
        key = re.sub(r"[^a-z0-9]+", "", name.casefold())
        if key in normalized:
            return normalized[key]
    best: tuple[int, str] | None = None
    for field in fields:
        numeric = 0
        in_range = 0
        for row in rows[: min(len(rows), 1000)]:
            try:
                value = float(row.get(field, ""))
            except ValueError:
                continue
            numeric += 1
            if 0.0 <= value <= 5.5:
                in_range += 1
        score = in_range * 2 + numeric
        if ("mos" in field.casefold() or "mean" in field.casefold()) and score:
            score += 10000
        if best is None or score > best[0]:
            best = (score, field)
    if best is None or best[0] <= 0:
        raise ValueError("could not detect MOS column")
    return best[1]


def _row_audio_tokens(row: dict[str, str]) -> set[str]:
    out: set[str] = set()
    for value in row.values():
        if not value:
            continue
        low = value.casefold().replace("\\", "/")
        if ".wav" in low or ".wave" in low:
            for match in re.findall(r"[^,;\t\"']+\.(?:wav|wave)", low):
                name = Path(match.strip()).name
                out.add(name)
                out.add(Path(name).stem)
                out.add(_slug(name))
    return out


def _score_index(rows: Sequence[dict[str, str]]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        for token in _row_audio_tokens(row):
            index[token].append(idx)
    return index


def _match_score_row(processed: Path, method: str, ratio: float, rows: Sequence[dict[str, str]], index: dict[str, list[int]]) -> int | None:
    keys = [processed.name.casefold(), processed.stem.casefold(), _slug(processed.name)]
    candidates: set[int] = set()
    for key in keys:
        candidates.update(index.get(key, []))
    if len(candidates) == 1:
        return next(iter(candidates))
    method_slug = _slug(method)
    best: tuple[float, int] | None = None
    for idx in candidates:
        blob = " ".join(rows[idx].values()).casefold()
        score = 0.0
        if processed.name.casefold() in blob:
            score += 100.0
        if processed.stem.casefold() in blob:
            score += 50.0
        if method_slug and method_slug in _slug(blob):
            score += 10.0
        numbers = []
        for token in re.findall(r"(?<!\d)(?:0?\.\d+|[01](?:\.\d+)?)(?!\d)", blob):
            try:
                numbers.append(float(token))
            except ValueError:
                pass
        if numbers:
            if min(abs(v - ratio) for v in numbers) < 0.015:
                score += 5.0
            if min(abs((1.0 / v if v else 999.0) - ratio) for v in numbers) < 0.015:
                score += 4.0
        if best is None or score > best[0]:
            best = (score, idx)
    return best[1] if best and best[0] > 0 else None


def import_dataset(ref_zip: Path, test_zip: Path, scores_csv: Path, destination: Path, *, expected_references: int = 20, expected_processed: int = 240) -> DatasetPaths:
    destination = destination.resolve()
    raw = destination / "raw"
    references_unpack = raw / "reference"
    processed_unpack = raw / "processed"
    if references_unpack.exists():
        shutil.rmtree(references_unpack)
    if processed_unpack.exists():
        shutil.rmtree(processed_unpack)
    _safe_extract(ref_zip, references_unpack)
    _safe_extract(test_zip, processed_unpack)
    references_root = _find_dataset_subtree(references_unpack, expected_references)
    processed_root = _find_dataset_subtree(processed_unpack, expected_processed)
    references = _all_audio(references_root)
    processed = _all_audio(processed_root)
    if len(references) != expected_references:
        raise ValueError(f"expected {expected_references} references, found {len(references)}")
    if len(processed) != expected_processed:
        raise ValueError(f"expected {expected_processed} processed files, found {len(processed)}")

    local_scores = destination / "TSM_MOS_Scores.csv"
    local_scores.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(scores_csv, local_scores)
    score_rows, fields = _read_score_rows(local_scores)
    mos_column = _detect_mos_column(score_rows, fields)
    sindex = _score_index(score_rows)
    ref_meta = []
    for ref in references:
        frames, sr, channels = _audio_info(ref)
        ref_meta.append((ref, frames, sr, channels))

    manifest_rows: list[dict[str, object]] = []
    unmatched_audio: list[str] = []
    unmatched_scores = 0
    for test in processed:
        matches = [meta for meta in ref_meta if _boundary_prefix(test.name, meta[0].name)]
        if not matches:
            test_slug = _slug(test.name)
            matches = [meta for meta in ref_meta if test_slug.startswith(_slug(meta[0].name))]
        if not matches:
            unmatched_audio.append(str(test))
            continue
        matches.sort(key=lambda m: len(m[0].stem), reverse=True)
        ref, ref_frames, ref_sr, ref_channels = matches[0]
        test_frames, test_sr, test_channels = _audio_info(test)
        ratio = (test_frames / test_sr) / (ref_frames / ref_sr)
        method = _guess_method(test, processed_root)
        score_idx = _match_score_row(test, method, ratio, score_rows, sindex)
        mos: float | None = None
        if score_idx is not None:
            try:
                mos = float(score_rows[score_idx][mos_column])
            except (ValueError, KeyError):
                mos = None
        if mos is None or not math.isfinite(mos):
            unmatched_scores += 1
        item_hash = hashlib.sha1(f"{ref.name}\0{method}\0{test.name}\0{ratio:.9f}".encode()).hexdigest()[:14]
        manifest_rows.append({
            "item_id": item_hash, "method": method, "ratio": f"{ratio:.9f}",
            "mos": "" if mos is None else f"{mos:.9f}",
            "reference_path": ref.relative_to(destination).as_posix(),
            "processed_path": test.relative_to(destination).as_posix(),
            "reference_name": ref.name, "processed_name": test.name,
            "reference_frames": ref_frames, "processed_frames": test_frames,
            "reference_samplerate": ref_sr, "processed_samplerate": test_sr,
            "reference_channels": ref_channels, "processed_channels": test_channels,
            "score_row": "" if score_idx is None else score_idx, "mos_column": mos_column,
        })
    if unmatched_audio:
        raise ValueError(f"could not match {len(unmatched_audio)} processed files to references")
    if len(manifest_rows) != expected_processed:
        raise ValueError(f"manifest contains {len(manifest_rows)} rows, expected {expected_processed}")
    manifest = destination / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    method_counts = Counter(str(r["method"]) for r in manifest_rows)
    reference_counts = Counter(str(r["reference_name"]) for r in manifest_rows)
    ratio_values = sorted(float(r["ratio"]) for r in manifest_rows)
    report = {
        "reference_count": len(references), "processed_count": len(processed),
        "score_row_count": len(score_rows),
        "matched_mos_count": len(manifest_rows) - unmatched_scores,
        "unmatched_mos_count": unmatched_scores, "mos_column": mos_column,
        "methods": dict(sorted(method_counts.items())),
        "references_with_case_count": dict(sorted(reference_counts.items())),
        "ratio_min": min(ratio_values), "ratio_max": max(ratio_values),
        "ratio_clusters": ratio_clusters(ratio_values), "manifest": str(manifest),
    }
    (destination / "IMPORT_REPORT.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return DatasetPaths(destination, references_root, processed_root, local_scores, manifest)


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ratio_clusters(values: Iterable[float], tolerance: float = 0.025) -> list[dict[str, float | int]]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        if not clusters or abs(value - float(np.median(clusters[-1]))) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [{"median": float(np.median(g)), "minimum": float(min(g)), "maximum": float(max(g)), "count": len(g)} for g in clusters]


def _mono(audio: np.ndarray) -> np.ndarray:
    return audio.astype(np.float64, copy=False) if audio.ndim == 1 else np.mean(audio, axis=1, dtype=np.float64)


def _resample_audio(audio: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    if source_sr == target_sr:
        return audio.astype(np.float64, copy=False)
    divisor = math.gcd(source_sr, target_sr)
    return signal.resample_poly(audio, target_sr // divisor, source_sr // divisor, axis=0).astype(np.float64, copy=False)


def _interp_time(matrix: np.ndarray, frames: int) -> np.ndarray:
    if matrix.shape[1] == frames:
        return matrix
    if matrix.shape[1] <= 1:
        return np.repeat(matrix, frames, axis=1)
    old = np.linspace(0.0, 1.0, matrix.shape[1])
    new = np.linspace(0.0, 1.0, frames)
    return np.vstack([np.interp(new, old, row) for row in matrix])


def _interp_vector(values: np.ndarray, frames: int) -> np.ndarray:
    if len(values) == frames:
        return values
    if len(values) <= 1:
        return np.full(frames, float(values[0]) if len(values) else 0.0)
    return np.interp(np.linspace(0.0, 1.0, frames), np.linspace(0.0, 1.0, len(values)), values)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    # Correlation must not mutate caller features (including overlapping views).
    # _best_shift reuses those arrays across candidate shifts and later metrics.
    x = np.array(a[:n], dtype=np.float64, copy=True)
    y = np.array(b[:n], dtype=np.float64, copy=True)
    x -= np.mean(x); y -= np.mean(y)
    denom = np.linalg.norm(x) * np.linalg.norm(y)
    if denom < EPS:
        return 1.0 if np.linalg.norm(x - y) < 1.0e-9 else 0.0
    return float(np.dot(x, y) / denom)


def _best_shift(a: np.ndarray, b: np.ndarray, max_shift: int) -> int:
    best = (-float("inf"), 0)
    for shift in range(-max_shift, max_shift + 1):
        if shift < 0: aa, bb = a[-shift:], b[: len(b) + shift]
        elif shift > 0: aa, bb = a[: len(a) - shift], b[shift:]
        else: aa, bb = a, b
        if len(aa) >= 4:
            value = _corr(aa, bb)
            if value > best[0]: best = (value, shift)
    return best[1]


def _shift_pair(a: np.ndarray, b: np.ndarray, shift: int) -> tuple[np.ndarray, np.ndarray]:
    if shift < 0: return a[:, -shift:], b[:, : b.shape[1] + shift]
    if shift > 0: return a[:, : a.shape[1] - shift], b[:, shift:]
    return a, b


def _stft_features(audio: np.ndarray, sr: int) -> dict[str, np.ndarray]:
    n_fft = 1024 if sr >= 16000 else 512
    hop = n_fft // 4
    if len(audio) < n_fft: audio = np.pad(audio, (0, n_fft - len(audio)))
    _, _, z = signal.stft(audio, fs=sr, window="hann", nperseg=n_fft, noverlap=n_fft-hop, nfft=n_fft, boundary="zeros", padded=True)
    mag = np.abs(z) + EPS
    frame_energy = np.sqrt(np.mean(mag * mag, axis=0)) + EPS
    unit = mag / frame_energy[None, :]
    log_unit = 20.0 * np.log10(np.maximum(unit, 1.0e-5))
    positive = np.maximum(0.0, np.diff(log_unit, axis=1, prepend=log_unit[:, :1]))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    hf_weight = np.sqrt(np.clip(freqs / max(freqs[-1], 1.0), 0.0, 1.0))[:, None]
    onset = np.mean(positive * (0.25 + hf_weight), axis=0)
    flux = np.mean(positive, axis=0)
    if len(frame_energy) >= 5:
        window = min(31, max(5, (len(frame_energy) // 2) * 2 - 1))
        envelope = signal.savgol_filter(np.log(frame_energy + EPS), window, 2, mode="interp")
    else:
        envelope = np.log(frame_energy + EPS)
    centroid = np.sum(freqs[:, None] * mag, axis=0) / np.sum(mag, axis=0)
    centroid_oct = np.log2(np.maximum(centroid, 20.0) / 440.0)
    chroma = np.zeros((12, mag.shape[1]), dtype=np.float64)
    valid = freqs >= 40.0
    midi = np.rint(69.0 + 12.0 * np.log2(np.maximum(freqs[valid], 1.0) / 440.0)).astype(int)
    for bin_idx, note in zip(np.flatnonzero(valid), midi): chroma[note % 12] += mag[bin_idx]
    chroma /= np.sum(chroma, axis=0, keepdims=True) + EPS
    return {"mag": mag, "unit": unit, "log_unit": log_unit, "onset": onset, "flux": flux, "envelope": envelope, "centroid_oct": centroid_oct, "chroma": chroma}


def _sharpness(onset: np.ndarray) -> float:
    x = np.maximum(np.asarray(onset, dtype=np.float64), 0.0)
    if len(x) == 0 or np.sum(x) < EPS: return 0.0
    threshold = np.quantile(x, 0.90)
    top = x[x >= threshold]
    return float(np.mean(top) / (np.mean(x) + EPS))


def _mid_side_diagnostics(audio: np.ndarray) -> tuple[float, float]:
    if audio.ndim != 2 or audio.shape[1] < 2: return 0.0, 0.0
    left = audio[:, 0].astype(np.float64); right = audio[:, 1].astype(np.float64)
    mid = (left + right) / math.sqrt(2.0); side = (left - right) / math.sqrt(2.0)
    ratio_db = 10.0 * math.log10((np.mean(side * side) + EPS) / (np.mean(mid * mid) + EPS))
    return ratio_db, _corr(left, right)


def compute_metrics(reference_path: Path, test_path: Path, *, analysis_sr: int = 22050) -> dict[str, float | int]:
    ref, ref_sr = sf.read(reference_path, always_2d=True, dtype="float32")
    test, test_sr = sf.read(test_path, always_2d=True, dtype="float32")
    ref_frames, test_frames = len(ref), len(test)
    duration_ratio = (test_frames / test_sr) / (ref_frames / ref_sr)
    ref_rms = float(np.sqrt(np.mean(np.square(ref, dtype=np.float64)) + EPS))
    test_rms = float(np.sqrt(np.mean(np.square(test, dtype=np.float64)) + EPS))
    rms_delta_db = 20.0 * math.log10((test_rms + EPS) / (ref_rms + EPS))
    ref_ms, ref_lr = _mid_side_diagnostics(ref); test_ms, test_lr = _mid_side_diagnostics(test)
    rf = _stft_features(_resample_audio(_mono(ref), ref_sr, analysis_sr), analysis_sr)
    tf = _stft_features(_resample_audio(_mono(test), test_sr, analysis_sr), analysis_sr)
    target_frames = max(8, rf["log_unit"].shape[1])
    for key in ("unit", "log_unit", "chroma"): tf[key] = _interp_time(tf[key], target_frames)
    for key in ("onset", "flux", "envelope", "centroid_oct"): tf[key] = _interp_vector(tf[key], target_frames)
    max_shift = min(12, max(1, target_frames // 20))
    shift = _best_shift(rf["onset"], tf["onset"], max_shift)
    rlog, tlog = _shift_pair(rf["log_unit"], tf["log_unit"], shift)
    runit, tunit = _shift_pair(rf["unit"], tf["unit"], shift)
    rchroma, tchroma = _shift_pair(rf["chroma"], tf["chroma"], shift)
    def shifted_vectors(key: str) -> tuple[np.ndarray, np.ndarray]:
        aa, bb = _shift_pair(np.asarray(rf[key])[None, :], np.asarray(tf[key])[None, :], shift)
        return aa[0], bb[0]
    ronset, tonset = shifted_vectors("onset"); rflux, tflux = shifted_vectors("flux")
    renv, tenv = shifted_vectors("envelope"); rcent, tcent = shifted_vectors("centroid_oct")
    chroma_frame_corrs = [_corr(rchroma[:, i], tchroma[:, i]) for i in range(rchroma.shape[1])]
    return {
        "reference_frames": ref_frames, "test_frames": test_frames,
        "reference_samplerate": int(ref_sr), "test_samplerate": int(test_sr),
        "duration_ratio": duration_ratio, "rms_delta_db": rms_delta_db,
        "log_spectral_distance_db": float(np.sqrt(np.mean(np.square(rlog - tlog)))),
        "spectral_convergence": float(np.linalg.norm(runit - tunit) / (np.linalg.norm(runit) + EPS)),
        "chroma_corr": float(np.mean(chroma_frame_corrs)) if chroma_frame_corrs else 0.0,
        "onset_corr": _corr(ronset, tonset), "spectral_flux_corr": _corr(rflux, tflux),
        "envelope_corr": _corr(renv, tenv),
        "centroid_mae_octaves": float(np.mean(np.abs(rcent - tcent))),
        "transient_sharpness_log_ratio": float(math.log((_sharpness(tonset)+1.0e-6)/(_sharpness(ronset)+1.0e-6))),
        "normalized_alignment_shift_frames": int(shift),
        "mid_side_ratio_delta_db": test_ms - ref_ms, "lr_corr_delta": test_lr - ref_lr,
    }


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8"); return
    fields = list(rows[0]); fields.extend(sorted({k for row in rows for k in row} - set(fields)))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def benchmark_manifest(dataset_root: Path, manifest_csv: Path, output_csv: Path, *, jobs: int = 1) -> list[dict[str, object]]:
    del jobs
    rows = read_manifest(manifest_csv); out: list[dict[str, object]] = []
    for idx, row in enumerate(rows, 1):
        item: dict[str, object] = dict(row)
        item.update(compute_metrics(dataset_root / row["reference_path"], dataset_root / row["processed_path"]))
        out.append(item)
        if idx % 20 == 0: print(f"baseline metrics: {idx}/{len(rows)}", flush=True)
    write_csv(output_csv, out); return out


def _cluster_id(value: float, centers: Sequence[float]) -> int:
    return int(np.argmin(np.abs(np.asarray(centers) - value)))


def render_boiled_egg(dataset_root: Path, manifest_csv: Path, cli: Path, output_root: Path, output_manifest: Path, *, block_frames: int | None = None) -> list[dict[str, object]]:
    del block_frames
    baseline = read_manifest(manifest_csv)
    centers = [float(x["median"]) for x in ratio_clusters(float(r["ratio"]) for r in baseline)]
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in baseline: grouped[(row["reference_name"], _cluster_id(float(row["ratio"]), centers))].append(row)
    output_root.mkdir(parents=True, exist_ok=True); rows: list[dict[str, object]] = []
    for idx, ((reference_name, _cluster), source_rows) in enumerate(sorted(grouped.items()), 1):
        reference = dataset_root / source_rows[0]["reference_path"]
        ratio = float(np.median([float(r["ratio"]) for r in source_rows]))
        expected_mos_by_method: dict[str, float] = {}
        for method in sorted({r["method"] for r in source_rows}):
            vals = [float(r["mos"]) for r in source_rows if r["method"] == method and r["mos"]]
            if vals: expected_mos_by_method[method] = float(np.mean(vals))
        safe_ref = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(reference_name).stem)
        out_path = output_root / f"{safe_ref}__r{ratio:.6f}.wav"
        command = [str(cli), str(reference), str(out_path), "--time", f"{ratio:.9f}", "--pitch", "0"]
        started = time.perf_counter(); completed = subprocess.run(command, capture_output=True, text=True); elapsed = time.perf_counter() - started
        if completed.returncode != 0: raise RuntimeError(f"boiled egg CLI failed for {reference_name} ratio {ratio}:\n{completed.stdout}\n{completed.stderr}")
        frames, sr, channels = _audio_info(out_path)
        row: dict[str, object] = {
            "item_id": hashlib.sha1(f"boiled-egg\0{reference_name}\0{ratio:.9f}".encode()).hexdigest()[:14],
            "method": "boiled-egg", "ratio": f"{ratio:.9f}",
            "reference_path": source_rows[0]["reference_path"],
            "processed_path": out_path.relative_to(dataset_root).as_posix(),
            "reference_name": reference_name, "processed_name": out_path.name,
            "processed_frames": frames, "processed_samplerate": sr, "processed_channels": channels,
            "render_seconds": elapsed,
        }
        for method, mos in expected_mos_by_method.items(): row[f"dataset_mos_{_slug(method)}"] = mos
        rows.append(row); print(f"boiled egg render: {idx}/{len(grouped)}", flush=True)
    write_csv(output_manifest, rows); return rows


def benchmark_boiled_egg(dataset_root: Path, render_manifest: Path, output_csv: Path) -> list[dict[str, object]]:
    rows = read_manifest(render_manifest); out: list[dict[str, object]] = []
    for idx, row in enumerate(rows, 1):
        item: dict[str, object] = dict(row)
        item.update(compute_metrics(dataset_root / row["reference_path"], dataset_root / row["processed_path"]))
        out.append(item)
        if idx % 10 == 0: print(f"boiled egg metrics: {idx}/{len(rows)}", flush=True)
    write_csv(output_csv, out); return out


MODEL_FEATURES = ("log_spectral_distance_db", "spectral_convergence", "chroma_distance", "onset_distance", "flux_distance", "envelope_distance", "centroid_mae_octaves", "transient_abs_log_ratio", "abs_rms_delta_db", "abs_mid_side_ratio_delta_db", "abs_lr_corr_delta")


def _model_vector(row: dict[str, str | object]) -> list[float]:
    def value(key: str, default: float = 0.0) -> float:
        try:
            x = float(row.get(key, default)); return x if math.isfinite(x) else default
        except (TypeError, ValueError): return default
    return [value("log_spectral_distance_db"), value("spectral_convergence"), 1.0-value("chroma_corr"), 1.0-value("onset_corr"), 1.0-value("spectral_flux_corr"), 1.0-value("envelope_corr"), value("centroid_mae_octaves"), abs(value("transient_sharpness_log_ratio")), abs(value("rms_delta_db")), abs(value("mid_side_ratio_delta_db")), abs(value("lr_corr_delta"))]


@dataclasses.dataclass
class RidgeModel:
    mean: np.ndarray; scale: np.ndarray; weights: np.ndarray; ridge: float
    def predict(self, x: np.ndarray) -> np.ndarray:
        z = (x-self.mean)/self.scale
        return np.column_stack([np.ones(len(z)), z]) @ self.weights


def _fit_ridge(x: np.ndarray, y: np.ndarray, ridge: float) -> RidgeModel:
    mean = np.mean(x, axis=0); scale = np.std(x, axis=0); scale[scale < 1.0e-9] = 1.0
    design = np.column_stack([np.ones(len(x)), (x-mean)/scale])
    penalty = np.eye(design.shape[1]); penalty[0,0] = 0.0
    weights = np.linalg.solve(design.T@design + ridge*penalty, design.T@y)
    return RidgeModel(mean, scale, weights, ridge)


def _safe_pearson(a: np.ndarray, b: np.ndarray) -> float:
    return 0.0 if len(a)<3 or np.std(a)<EPS or np.std(b)<EPS else float(stats.pearsonr(a,b).statistic)


def _safe_spearman(a: np.ndarray, b: np.ndarray) -> float:
    return 0.0 if len(a)<3 or np.std(a)<EPS or np.std(b)<EPS else float(stats.spearmanr(a,b).statistic)


def fit_mos_proxy(baseline_rows: Sequence[dict[str, str]]) -> tuple[RidgeModel, dict[str, object], list[dict[str, object]]]:
    usable = [r for r in baseline_rows if r.get("mos", "") not in ("", None)]
    x = np.asarray([_model_vector(r) for r in usable], dtype=np.float64)
    y = np.asarray([float(r["mos"]) for r in usable], dtype=np.float64)
    groups = np.asarray([r["reference_name"] for r in usable]); unique_groups = sorted(set(groups.tolist()))
    candidate_results = []
    for ridge in (0.1,1.0,10.0,100.0):
        predictions = np.full(len(y), np.nan)
        for group in unique_groups:
            test_mask = groups == group; train_mask = ~test_mask
            if np.sum(train_mask) < x.shape[1]+2: continue
            predictions[test_mask] = _fit_ridge(x[train_mask], y[train_mask], ridge).predict(x[test_mask])
        valid = np.isfinite(predictions)
        candidate_results.append((float(np.sqrt(np.mean(np.square(predictions[valid]-y[valid])))), ridge, predictions))
    candidate_results.sort(key=lambda item: item[0]); rmse, ridge, predictions = candidate_results[0]
    valid = np.isfinite(predictions); clipped = np.clip(predictions,1.0,5.0)
    diagnostics: dict[str, object] = {
        "purpose": "engineering triage only; not the published OMOQ", "features": list(MODEL_FEATURES),
        "ridge": ridge, "group_cv": "leave-one-reference-out", "rows": int(np.sum(valid)),
        "rmse_unclipped": rmse, "rmse_clipped": float(np.sqrt(np.mean(np.square(clipped[valid]-y[valid])))),
        "mae_clipped": float(np.mean(np.abs(clipped[valid]-y[valid]))),
        "pearson": _safe_pearson(y[valid], clipped[valid]), "spearman": _safe_spearman(y[valid], clipped[valid]),
    }
    cv_rows = [{"item_id": s.get("item_id",""), "reference_name": s.get("reference_name",""), "method": s.get("method",""), "ratio": s.get("ratio",""), "mos": truth, "proxy_mos_cv": pred, "proxy_error": pred-truth} for s,truth,pred in zip(usable,y,clipped)]
    return _fit_ridge(x,y,ridge), diagnostics, cv_rows


def summarize(baseline_metrics_csv: Path, boiled_metrics_csv: Path, output_dir: Path) -> dict[str, object]:
    baseline = read_manifest(baseline_metrics_csv); boiled = read_manifest(boiled_metrics_csv)
    model, model_diag, cv_rows = fit_mos_proxy(baseline); write_csv(output_dir/"mos_proxy_cross_validation.csv", cv_rows)
    bx = np.asarray([_model_vector(r) for r in boiled],dtype=np.float64); bpred = np.clip(model.predict(bx),1.0,5.0)
    predicted_rows: list[dict[str, object]] = []
    for row,prediction in zip(boiled,bpred):
        item: dict[str, object] = dict(row); item["proxy_mos"] = float(prediction); predicted_rows.append(item)
    write_csv(output_dir/"boiled_egg_metrics_with_proxy_mos.csv", predicted_rows)
    baseline_by_method: dict[str,dict[str,object]] = {}
    for method in sorted({r["method"] for r in baseline}):
        rows = [r for r in baseline if r["method"]==method]
        baseline_by_method[method] = {
            "count": len(rows), "mos_mean": float(np.mean([float(r["mos"]) for r in rows if r.get("mos")])),
            "mos_median": float(np.median([float(r["mos"]) for r in rows if r.get("mos")])),
            "lsd_mean": float(np.mean([float(r["log_spectral_distance_db"]) for r in rows])),
            "onset_corr_mean": float(np.mean([float(r["onset_corr"]) for r in rows])),
            "transient_abs_log_ratio_mean": float(np.mean([abs(float(r["transient_sharpness_log_ratio"])) for r in rows])),
        }
    report: dict[str,object] = {
        "baseline_rows": len(baseline), "boiled_egg_rows": len(boiled), "baseline_by_method": baseline_by_method,
        "boiled_egg_proxy_mos": {"mean": float(np.mean(bpred)), "median": float(np.median(bpred)), "minimum": float(np.min(bpred)), "maximum": float(np.max(bpred))},
        "mos_proxy_validation": model_diag, "metric_correlations_with_mos": {},
    }
    correlations = {}; y = np.asarray([float(r["mos"]) for r in baseline if r.get("mos")],dtype=np.float64)
    for field in ("log_spectral_distance_db","spectral_convergence","chroma_corr","onset_corr","spectral_flux_corr","envelope_corr","centroid_mae_octaves","transient_sharpness_log_ratio","rms_delta_db"):
        values = np.asarray([float(r[field]) for r in baseline if r.get("mos")],dtype=np.float64)
        correlations[field] = {"pearson": _safe_pearson(values,y), "spearman": _safe_spearman(values,y)}
    report["metric_correlations_with_mos"] = correlations
    output_dir.mkdir(parents=True,exist_ok=True); (output_dir/"summary.json").write_text(json.dumps(report,indent=2,sort_keys=True),encoding="utf-8")
    lines = ["# Roberts/Paliwal TSM test-set benchmark","","This report is generated locally. Dataset audio and MOS files are not committed.","",f"- Baseline processed signals: **{len(baseline)}**",f"- boiled egg matched renders: **{len(boiled)}**",f"- Experimental proxy MOS: **{np.mean(bpred):.3f} mean**, **{np.median(bpred):.3f} median**, range **{np.min(bpred):.3f}–{np.max(bpred):.3f}**","","## Dataset systems","","| System | n | Mean MOS | Median MOS | Mean LSD (dB) | Mean onset corr | Mean |transient log-ratio| |","|---|---:|---:|---:|---:|---:|---:|"]
    for method,values in baseline_by_method.items(): lines.append(f"| {method} | {values['count']} | {values['mos_mean']:.3f} | {values['mos_median']:.3f} | {values['lsd_mean']:.3f} | {values['onset_corr_mean']:.3f} | {values['transient_abs_log_ratio_mean']:.3f} |")
    lines += ["","## MOS-proxy validation","","The proxy is a small ridge model over transparent diagnostics. It is **not** the published OMOQ and must not be reported as a perceptual score without this qualification.","",f"- Validation: leave-one-reference-out",f"- RMSE: **{model_diag['rmse_clipped']:.3f}**",f"- MAE: **{model_diag['mae_clipped']:.3f}**",f"- Pearson: **{model_diag['pearson']:.3f}**",f"- Spearman: **{model_diag['spearman']:.3f}**","","## Interpretation","","Use the per-file CSVs to locate regressions. Accept a backend only when controlled listening results and transient/harmonic diagnostics improve without violating realtime gates.",""]
    (output_dir/"SUMMARY.md").write_text("\n".join(lines),encoding="utf-8"); return report
