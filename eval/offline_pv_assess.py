#!/usr/bin/env python3
"""Apply predeclared paired stop conditions; never infer overall naturalness.

This post-run assessor evaluates the recorded protocol thresholds. It does not
change the frozen renderer, input grid, or measurements, and never fits outputs.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import statistics
import comparison_contract as c
import offline_pv_benchmark as b


def finite(x) -> float:
    if isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x):
        raise ValueError('nonfinite/missing numeric metric')
    return float(x)


def paired_failures(candidate: dict, control: dict) -> list[str]:
    reasons=[]
    if not candidate.get('rendered') or not candidate.get('repeat_pcm_equal'):
        return ['incomplete or nondeterministic render']
    if not control.get('rendered') or not control.get('repeat_pcm_equal'):
        return ['paired control incomplete or nondeterministic']
    m=candidate['metrics'];base=control['metrics']
    if finite(m['rms'])<=1e-8:reasons.append('silent output')
    finite(m['peak'])
    if candidate['family']=='low':
        if abs(finite(m['pitch_error_cents']))>5:reasons.append('pitch exceeds 5 cents')
    if candidate['family']=='bursts':
        if len(m['events'])!=2 or len(base['events'])!=2:raise ValueError('missing event metrics')
        for i,(event,reference) in enumerate(zip(m['events'],base['events'])):
            if abs(finite(event['position_error_ms']))-abs(finite(reference['position_error_ms']))>1:
                reasons.append(f'event{i} absolute position error worsened >1ms')
            if finite(event['width_ms'])>1.2*finite(reference['width_ms']):
                reasons.append(f'event{i} energy width worsened >20%')
    return reasons


def assess(summary: dict) -> dict:
    if summary.get('schema')!='boiled-egg.offline-pv-screen.v1':raise ValueError('wrong experiment schema')
    grid={'sources':[{'metadata':{'family':f,'rate':r}} for r in b.RATES for f in b.FAMILIES],
          'shifts':list(b.SHIFTS),'engines':list(b.ENGINES),'repeats':3,'expected_runs':630}
    b.validate_grid(summary['rows'],grid)
    cells=summary['cells']
    keys=[(v['family'],v['rate'],v['shift'],v['engine']) for v in cells]
    expected={(f,r,s,e) for f in b.FAMILIES for r in b.RATES for s in b.SHIFTS for e in b.ENGINES}
    if len(keys)!=210 or len(set(keys))!=210 or set(keys)!=expected:raise ValueError('incomplete/duplicate cell grid')
    bykey=dict(zip(keys,cells));pairs=[];engines={}
    for v in cells:
        if v['engine'] in ('offline_8','offline_32'):
            base=bykey[(v['family'],v['rate'],v['shift'],'offline_0')]
            errors=paired_failures(v,base)
            row={k:v[k] for k in ('family','rate','shift','engine')};row['stop_reasons']=errors
            if v.get('rendered') and base.get('rendered'):
                row['wall_cost_ratio']=finite(v['median_wall_seconds'])/finite(base['median_wall_seconds'])
                objective=v['renderer']['magnitude_residual'];initial=base['renderer']['magnitude_residual'][0]
                row.update(initial_magnitude_residual=finite(initial),final_magnitude_residual=finite(objective[-1]))
                if initial>0:row['objective_reduction_fraction']=1-finite(objective[-1])/finite(initial)
                if 'undesired_energy_fraction' in v['metrics']:
                    row['undesired_energy_delta']=finite(v['metrics']['undesired_energy_fraction'])-finite(base['metrics']['undesired_energy_fraction'])
            pairs.append(row)
    stops=[p for p in pairs if p['stop_reasons']]
    for engine in b.ENGINES:
        selected=[v for v in cells if v['engine']==engine];good=[v for v in selected if v.get('rendered')]
        low=[abs(finite(v['metrics']['pitch_error_cents'])) for v in good if v['family']=='low']
        positions=[abs(finite(e['position_error_ms'])) for v in good if v['family']=='bursts' for e in v['metrics']['events']]
        widths=[finite(e['width_ms']) for v in good if v['family']=='bursts' for e in v['metrics']['events']]
        station=[v for v in good if v['family'] in ('low','harmonic','close') and v['shift']!=0]
        engines[engine]=dict(rendered_settings=len(good),expected_settings=30,
            repeat_equal_settings=sum(v.get('repeat_pcm_equal',False) for v in selected),
            low_tone_pitch_pass=sum(p<=5 for p in low),low_tone_count=len(low),
            max_abs_pitch_cents=max(low,default=None),max_abs_event_position_ms=max(positions,default=None),
            max_event_width_ms=max(widths,default=None),
            median_nonidentity_undesired_energy=statistics.median(v['metrics']['undesired_energy_fraction'] for v in station) if station else None,
            median_setting_wall_seconds=statistics.median(v['median_wall_seconds'] for v in good) if good else None,
            max_process_rss_kib=max((v['max_rss_kib'] for v in good),default=None))
    return dict(schema='boiled-egg.offline-pv-assessment.v1',plan_sha256=summary['plan_sha256'],
        complete_runs=sum(r['status']=='rendered' for r in summary['rows']),expected_runs=630,
        engines=engines,paired_cells=pairs,stopped_paired_cells=len(stops),
        decision='reject_product_promotion' if stops else 'research_only_pending_broader_confirmation',
        quality_selection=None,paired_thresholds=dict(pitch_cents=5,absolute_position_worsening_ms=1,width_worsening_fraction=.2),
        limitations=['exploratory synthetic constant-pitch screen; no independent natural-audio confirmation',
          'own magnitude residual is an optimization diagnostic, not independent quality',
          'whole-file fresh-process timings include I/O/startup; not callback capacity',
          'mono/formantOff/time1; no general stereo/formant/automation/freeze qualification'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('do not overwrite assessment')
    result=assess(json.loads(a.summary.read_text()))
    result.update(summary_sha256=c.fingerprint(a.summary),assessor_sha256=c.fingerprint(Path(__file__)))
    c.json_write(a.output,result);print(result['decision'],result['stopped_paired_cells'])

if __name__=='__main__':main()
