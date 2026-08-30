#!/usr/bin/env python3
from pathlib import Path
import csv
ROOT=Path(__file__).resolve().parents[1]; metrics=ROOT/'results'/'synthetic'/'metrics.csv'; bench=ROOT/'results'/'realtime_bench.csv'; out=ROOT/'results'/'SUMMARY.md'; lines=['# Evaluation summary','']
if metrics.exists():
 rows=list(csv.DictReader(metrics.open()));lines+=['## Synthetic correctness',''];lines += [f"- {r['case']}: duration_error={r.get('duration_error_frames','')}, pitch_cents={r.get('pitch_error_cents','')}, alias_db={r.get('alias_rejection_db','')}" for r in rows]
if bench.exists():
 rows=list(csv.DictReader(bench.open())); worst=max(rows,key=lambda r:float(r['p99_deadline_fraction']));lines+=['','## Realtime benchmark','',f"- Worst p99/deadline: **{float(worst['p99_deadline_fraction']):.2f}x** ({worst['sample_rate']} Hz, {worst['block']} frames, {worst['pitch_st']} st)."]
lines+=['','The current engine is a research baseline; next milestone is a phase-vocoder/transient-aware backend.'];out.write_text('\n'.join(lines)+'\n');print(out)
