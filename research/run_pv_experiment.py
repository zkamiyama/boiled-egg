#!/usr/bin/env python3
"""Render and score independent PV research variants on the TSM test set."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval")); sys.path.insert(0, str(ROOT / "research"))
from tsm_dataset import _model_vector, compute_metrics, fit_mos_proxy, ratio_clusters, read_manifest, write_csv
from pv_reference import process


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--dataset",type=Path,default=ROOT/"data"/"external"/"tsm_test")
    parser.add_argument("--baseline-metrics",type=Path,default=ROOT/"results"/"tsm_test"/"baseline_metrics.csv")
    parser.add_argument("--results",type=Path,default=ROOT/"results"/"pv_experiment")
    parser.add_argument("--modes",nargs="+",default=["classic","locked","transient","adaptive"]); parser.add_argument("--limit",type=int,default=0)
    args=parser.parse_args(); dataset=args.dataset.resolve(); results=args.results.resolve(); results.mkdir(parents=True,exist_ok=True)
    manifest=read_manifest(dataset/"manifest.csv"); centers=[float(c["median"]) for c in ratio_clusters(float(r["ratio"]) for r in manifest)]
    grouped: dict[tuple[str,int],list[dict[str,str]]]=defaultdict(list)
    for row in manifest:
        cluster=int(np.argmin(np.abs(np.asarray(centers)-float(row["ratio"])))); grouped[(row["reference_name"],cluster)].append(row)
    cases=sorted(grouped.items()); cases=cases[:args.limit] if args.limit else cases
    baseline_rows=read_manifest(args.baseline_metrics); model,validation,_=fit_mos_proxy(baseline_rows); output_rows=[]
    for mode in args.modes:
        mode_dir=results/"audio"/mode; mode_dir.mkdir(parents=True,exist_ok=True)
        for index,((reference_name,_cluster),source_rows) in enumerate(cases,1):
            ratio=float(np.median([float(r["ratio"]) for r in source_rows])); reference=dataset/source_rows[0]["reference_path"]
            audio,sr=sf.read(reference,always_2d=True,dtype="float32"); out_path=mode_dir/f"{Path(reference_name).stem}__r{ratio:.6f}.wav"
            started=time.perf_counter(); output=process(audio,sr,ratio,mode); elapsed=time.perf_counter()-started
            sf.write(out_path,output,sr,subtype="FLOAT"); metrics=compute_metrics(reference,out_path)
            row={"mode":mode,"reference_name":reference_name,"ratio":ratio,"output_path":out_path.relative_to(results).as_posix(),"render_seconds":elapsed}; row.update(metrics); output_rows.append(row)
            print(f"{mode}: {index}/{len(cases)}",flush=True)
    x=np.asarray([_model_vector(r) for r in output_rows],dtype=np.float64); predictions=np.clip(model.predict(x),1.0,5.0)
    for row,prediction in zip(output_rows,predictions): row["proxy_mos"]=float(prediction)
    write_csv(results/"metrics.csv",output_rows); by_mode={}
    for mode in args.modes:
        rows=[r for r in output_rows if r["mode"]==mode]
        by_mode[mode]={"count":len(rows),"proxy_mos_mean":float(np.mean([r["proxy_mos"] for r in rows])),"proxy_mos_median":float(np.median([r["proxy_mos"] for r in rows])),"lsd_mean":float(np.mean([r["log_spectral_distance_db"] for r in rows])),"onset_corr_mean":float(np.mean([r["onset_corr"] for r in rows])),"transient_abs_log_ratio_mean":float(np.mean([abs(r["transient_sharpness_log_ratio"]) for r in rows])),"render_realtime_factor_mean":float(np.mean([r["render_seconds"]/max(r["test_frames"]/r["test_samplerate"],1.0e-9) for r in rows]))}
    summary={"warning":"offline Python research prototype; proxy MOS is not OMOQ","mos_proxy_validation":validation,"modes":by_mode}
    (results/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True),encoding="utf-8")
    lines=["# Offline phase-vocoder research experiment","","These are independent Python prototypes, not the realtime product core.","","| Mode | n | Proxy MOS mean | Proxy MOS median | LSD mean | Onset corr | |transient log-ratio| | Mean render RTF |","|---|---:|---:|---:|---:|---:|---:|---:|"]
    for mode,v in by_mode.items(): lines.append(f"| {mode} | {v['count']} | {v['proxy_mos_mean']:.3f} | {v['proxy_mos_median']:.3f} | {v['lsd_mean']:.3f} | {v['onset_corr_mean']:.3f} | {v['transient_abs_log_ratio_mean']:.3f} | {v['render_realtime_factor_mean']:.3f} |")
    (results/"SUMMARY.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__=="__main__": main()
