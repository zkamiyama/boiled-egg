"""Evaluation-only constant-ratio render contract (roadmap #15 / #16).

Duration means output/input frames, never playback speed. No automatic engine
fallback, output alignment, padding, resampling, limiting or gain matching.
Metadata success is NOT perceptual quality or sample-accurate alignment evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import numpy as np
import soundfile as sf

SCHEMA = "boiled-egg.comparison-contract.v1"


def fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def json_write(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


@dataclass(frozen=True)
class Request:
    duration_ratio: float = 1.0
    pitch_ratio: float = 1.0
    # Predeclared rounding allowance, not a post-measurement trim policy.
    duration_tolerance_frames: int = 1

    def __post_init__(self) -> None:
        for value in (self.duration_ratio, self.pitch_ratio):
            if not math.isfinite(value) or not 0.5 <= value <= 2.0:
                raise ValueError("primary comparison range is finite [0.5, 2] for both ratios")
        if type(self.duration_tolerance_frames) is not int or not 0 <= self.duration_tolerance_frames <= 1:
            raise ValueError("rounding allowance must be 0 or 1 frame; no free duration fitting")

    @classmethod
    def from_semitones(cls, duration: float, semitones: float) -> Request:
        if not math.isfinite(semitones) or not -12 <= semitones <= 12:
            raise ValueError("pitch must be finite and within +/-12 semitones")
        return cls(duration, 2.0 ** (semitones / 12.0))

    def target_frames(self, frames: int) -> int:
        return math.floor(frames * self.duration_ratio + 0.5)


def inspect_audio(path: Path) -> dict[str, Any]:
    info = sf.info(path)
    if info.frames < 1 or info.samplerate not in (44100, 48000, 88200, 96000) or info.channels not in (1, 2):
        raise ValueError("expected nonempty mono/stereo 44.1/48/88.2/96-kHz audio")
    if info.format not in ("WAV", "WAVEX") or info.subtype not in ("PCM_16", "FLOAT"):
        raise ValueError("comparison input/output must be PCM16 or float32 WAV, no implicit transcoding")
    peak, energy, samples = 0.0, 0.0, 0
    with sf.SoundFile(path) as stream:
        for block in stream.blocks(blocksize=65536, dtype="float64", always_2d=True):
            if not np.isfinite(block).all():
                raise ValueError("nonfinite audio")
            peak = max(peak, float(np.max(np.abs(block))))
            energy += float(np.sum(block * block))
            samples += block.size
    if not math.isfinite(energy):
        raise ValueError("nonfinite audio energy")
    return dict(frames=info.frames, sample_rate=info.samplerate, channels=info.channels,
                format=info.format, subtype=info.subtype, peak=peak,
                rms=math.sqrt(energy / samples), sha256=fingerprint(path))


def output_checks(source: dict, output: dict, request: Request) -> list[str]:
    errors = []
    for key in ("sample_rate", "channels"):
        if source[key] != output[key]:
            errors.append(f"changed {key}")
    if output["subtype"] != "FLOAT":
        errors.append("output is not float32 WAV")
    delta = output["frames"] - request.target_frames(source["frames"])
    if abs(delta) > request.duration_tolerance_frames:
        errors.append(f"duration mismatch: {delta:+d} frames")
    return errors


@dataclass(frozen=True)
class Engine:
    name: str
    kind: str
    executable: str
    quality: str = "general"
    formant: str = "off"
    block: int = 32

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.name):
            raise ValueError("engine name must be a safe, unique label")
        if self.kind not in ("boiled_egg", "spectral", "ffmpeg_rubberband"):
            raise ValueError("unsupported engine; no fallback")
        if self.quality not in ("general", "transient") or type(self.block) is not int or not 1 <= self.block <= 1024:
            raise ValueError("invalid quality/block")
        allowed = {"boiled_egg": ("off",), "spectral": ("off", "harmonic", "monophonic"),
                   "ffmpeg_rubberband": ("off", "preserved")}
        if self.formant not in allowed[self.kind]:
            raise ValueError("unsupported formant policy; not silently replaced by off")
        if self.kind != "spectral" and self.quality != "general":
            raise ValueError("quality selection is only exposed by the spectral adapter")

    def command(self, executable: str, source: Path, output: Path, request: Request) -> list[str]:
        number = lambda v: format(v, ".17g")
        if self.kind == "boiled_egg":
            return [executable, str(source), str(output), "--time", number(request.duration_ratio),
                    "--pitch", number(12 * math.log2(request.pitch_ratio)), "--block", str(self.block)]
        if self.kind == "spectral":
            if request.duration_ratio * request.pitch_ratio > 2.0:
                raise ValueError("spectral coupled ratio exceeds 2; unsupported, not clamped")
            return [executable, str(source), str(output), "--backend", "pv", "--allow-experimental",
                    "--quality", self.quality, "--formant", self.formant, "--time", number(request.duration_ratio),
                    "--pitch-ratio", number(request.pitch_ratio), "--block", str(self.block)]
        # FFmpeg wraps Rubber Band's realtime API, NOT the direct CLI offline pass.
        # 1/tempo is passed to rubberband_new and rubberband_set_time_ratio.
        formant = "shifted" if self.formant == "off" else "preserved"
        options = (f"rubberband=tempo={number(1 / request.duration_ratio)}:pitch={number(request.pitch_ratio)}"
                   f":transients=crisp:detector=compound:phase=laminar:window=standard:smoothing=off"
                   f":formant={formant}:pitchq=quality:channels=together")
        return [executable, "-nostdin", "-n", "-hide_banner", "-loglevel", "error", "-i", str(source),
                "-map", "0:a:0", "-vn", "-af", options, "-map_metadata", "-1", "-c:a", "pcm_f32le", str(output)]

    def probe(self) -> dict[str, Any]:
        candidate = shutil.which(self.executable)
        if candidate is None:
            raise FileNotFoundError(f"requested executable unavailable: {self.executable}")
        path = Path(candidate).resolve(strict=True)
        result: dict[str, Any] = dict(config=asdict(self), executable=str(path), sha256=fingerprint(path),
            mode="rubberband-realtime-filter" if self.kind == "ffmpeg_rubberband" else "streaming-CLI-finalized",
            alignment="engine output as emitted; no fitted offset, no post trim/pad",
            alignment_verified=False, full_library_identity=False, dependencies={},
            engine_end_handling="legacy CLI caps excess to target" if self.kind == "boiled_egg" else
                "spectral CLI exact stream-length check" if self.kind == "spectral" else "FFmpeg filter as emitted")
        flag = ["-version"] if self.kind == "ffmpeg_rubberband" else ["--list-backends"] if self.kind == "spectral" else []
        proc = subprocess.run([str(path), *flag], capture_output=True, text=True, timeout=15)
        result["version_or_capability_probe"] = dict(command=[str(path), *flag], returncode=proc.returncode,
                                                    stdout=proc.stdout, stderr=proc.stderr)
        if self.kind == "ffmpeg_rubberband":
            help_result = subprocess.run([str(path), "-hide_banner", "-h", "filter=rubberband"],
                                         capture_output=True, text=True, timeout=15)
            text = help_result.stdout + help_result.stderr
            if "Apply time-stretching and pitch-shifting" not in text:
                raise ValueError("requested FFmpeg build lacks rubberband filter")
            result["filter_help"] = text
        elif self.kind == "spectral" and (proc.returncode or "backend=pv status=experimental" not in proc.stdout):
            raise ValueError("spectral preview is unavailable; opt-in build required")
        # Trusted local evaluation tools only. ldd is never run on fetched unknown files.
        # Capture all resolved shared libraries, not just the CLI hash.
        if os.name == "posix" and shutil.which("ldd"):
            dep = subprocess.run(["ldd", str(path)], capture_output=True, text=True, timeout=15)
            result["dependency_probe"] = dict(returncode=dep.returncode, stdout=dep.stdout, stderr=dep.stderr)
            dependencies = {}
            for line in dep.stdout.splitlines():
                match = re.search(r"(?:=>\s+)?(/\S+)", line)
                if match:
                    item = Path(match.group(1)).resolve()
                    if item.is_file():
                        dependencies[str(item)] = fingerprint(item)
            result["dependencies"] = dependencies
            result["full_library_identity"] = dep.returncode == 0 and bool(dependencies) and "not found" not in dep.stdout
        return result


def identity_unchanged(probe: dict) -> bool:
    values = {probe["executable"]: probe["sha256"], **probe["dependencies"]}
    try:
        return all(fingerprint(Path(p)) == h for p, h in values.items())
    except OSError:
        return False


def render_case(engine: Engine, probe: dict, source: Path, request: Request, destination: Path,
                timeout: float = 120.0) -> dict:
    """Retain a receipt and raw outputs on failure; never reuse an old directory."""
    destination.mkdir(parents=True, exist_ok=False)
    output = destination / "output.wav"
    receipt: dict[str, Any] = dict(schema=SCHEMA, status="failed", engine=engine.name,
        request=asdict(request), source=str(source.resolve()), command=None, errors=[], output=None,
        provenance_sha256=hashlib.sha256(json.dumps(probe, sort_keys=True).encode()).hexdigest())
    json_write(destination / "started.json", receipt)
    before = None
    try:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("invalid timeout")
        if engine != Engine(**probe["config"]) or not identity_unchanged(probe):
            raise ValueError("engine/configuration identity changed")
        source = source.resolve(strict=True)
        before = inspect_audio(source)
        receipt["source_metadata"] = before
        receipt["expected_frames"] = request.target_frames(before["frames"])
        cmd = engine.command(probe["executable"], source, output, request)
        receipt["command"] = cmd
        with (destination / "stdout.log").open("w") as stdout, (destination / "stderr.log").open("w") as stderr:
            process = subprocess.run(cmd, stdout=stdout, stderr=stderr, timeout=timeout, check=False)
        receipt["returncode"] = process.returncode
        if output.is_symlink():
            raise ValueError("output unexpectedly became a symlink")
        if output.exists():
            receipt["raw_output_sha256"] = fingerprint(output)
            receipt["output"] = inspect_audio(output)
            receipt["errors"].extend(output_checks(before, receipt["output"], request))
            receipt["duration_error_frames"] = receipt["output"]["frames"] - receipt["expected_frames"]
        else:
            receipt["errors"].append("no output created")
        if process.returncode:
            receipt["errors"].append(f"renderer exit {process.returncode}")
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        receipt["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if before is not None:
            try:
                if fingerprint(source) != before["sha256"]:
                    receipt["errors"].append("input changed during render")
            except OSError:
                receipt["errors"].append("input disappeared during render")
        if not identity_unchanged(probe):
            receipt["errors"].append("engine dependency changed during render")
        receipt["status"] = "passed" if not receipt["errors"] else "failed"
        json_write(destination / "receipt.json", receipt)
    return receipt


def verify_case(directory: Path) -> dict:
    receipt = json.loads((directory / "receipt.json").read_text())
    if receipt.get("schema") != SCHEMA or receipt.get("status") != "passed" or receipt.get("errors"):
        raise ValueError("failed/incomplete render cannot be scored")
    actual = inspect_audio(directory / "output.wav")
    if actual != receipt["output"] or actual["sha256"] != receipt["raw_output_sha256"]:
        raise ValueError("render changed since verification")
    request = Request(**receipt["request"])
    if output_checks(receipt["source_metadata"], actual, request):
        raise ValueError("receipt violates duration/format contract")
    return receipt
