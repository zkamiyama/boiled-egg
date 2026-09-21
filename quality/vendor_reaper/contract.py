"""Small external-host adapter; no proprietary engine is extracted or linked."""
from __future__ import annotations
import json, math, os, subprocess, sys, time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'eval'))
import comparison_contract as c

VERSION='7.80/linux-x86_64'
PROFILES={
 'elastique_pro_off':(9,0,'élastique 3.3.3 Pro','Normal'),
 'elastique_pro_preserve':(9,4,'élastique 3.3.3 Pro','Preserve Formants (Most Pitches)'),
 'elastique_soloist':(11,0,'élastique 3.3.3 Soloist','Monophonic'),
}

def lua(value):
    if isinstance(value,str):
        if any(ord(ch)<32 for ch in value):raise ValueError('control character in script value')
        return json.dumps(value,ensure_ascii=False)
    if isinstance(value,bool):return 'true' if value else 'false'
    if isinstance(value,(int,float)) and math.isfinite(value):return repr(value)
    if isinstance(value,list):return '{'+','.join(lua(v) for v in value)+'}'
    if isinstance(value,dict):return '{'+','.join('['+lua(str(k))+']='+lua(v) for k,v in value.items())+'}'
    raise ValueError('unsupported Lua value')

def job(identifier,source,out,rate,frames,shift,profile,time_ratio=1.):
    req=c.Request.from_semitones(time_ratio,shift)
    if profile not in PROFILES:raise ValueError('unknown explicit profile')
    if rate not in (48000,96000) or type(frames)!=int or frames<=0:raise ValueError('invalid rate/frames')
    if out.exists():raise ValueError('refuse overwrite')
    mode,sub,name,subname=PROFILES[profile]
    return dict(id=identifier,input=str(source.resolve(strict=True)),output=str(out.resolve()),
        directory=str(out.resolve().parent),stem=out.stem,receipt=str(out.with_suffix('.json').resolve()),
        project=str(out.with_suffix('.rpp').resolve()),rate=rate,input_frames=frames,
        output_frames=req.target_frames(frames),semitones=shift,time_ratio=time_ratio,
        mode=mode,submode=sub,mode_name=name,submode_name=subname)

def render(reaper,profile,jobs,out,plan_sha,display=':97',timeout=1200):
    out.mkdir(parents=True,exist_ok=False)
    spec=dict(version=VERSION,jobs=jobs,plan_sha256=plan_sha,inventory=str(out/'inventory.json'),
              maps=str(out/'loaded-maps.txt'),done=str(out/'done.json'))
    # Call only with a dedicated profile; never remove trial/license state.
    profile=Path(profile).resolve(strict=True)
    table=out/'jobs.lua';table.write_text('return '+lua(spec)+'\n',encoding='utf-8')
    c.json_write(out/'jobs.json',spec)
    env=dict(os.environ,DISPLAY=display,BE_REAPER_JOB_FILE=str(table))
    argv=[str(reaper),'-newinst','-nosplash','-new','-cfgfile',str(profile),str(Path(__file__).with_name('render_batch.lua'))]
    start=time.perf_counter()
    with (out/'process.log').open('w') as log:
        p=subprocess.Popen(argv,stdout=log,stderr=log,env=env,start_new_session=True)
        try:rc=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=10);rc=-999
    report=dict(argv=argv,returncode=rc,wall_seconds=time.perf_counter()-start,proprietary_runtime_ci=False)
    try:
        report['batch']=json.loads((out/'done.json').read_text())
    except (OSError,ValueError) as exc:
        report['batch']=None;report['batch_error']=str(exc)
    c.json_write(out/'process.json',report)
    return report

def require_process(report,expected):
    """A valid WAV cannot excuse a crashed or incomplete host process."""
    try:
        if type(report['returncode']) is not int or report['returncode']!=0:
            raise ValueError('REAPER process failed')
        batch=report['batch']
        if type(batch['attempts']) is not int or type(batch['completed']) is not int:
            raise ValueError('malformed batch counters')
        if batch['attempts']!=expected or batch['completed']!=expected:
            raise ValueError('incomplete REAPER batch')
    except (KeyError,TypeError) as exc:
        raise ValueError('missing REAPER process evidence') from exc


def verify(job,plan_sha):
    r=json.loads(Path(job['receipt']).read_text())
    if r['status']!='complete' or r['id']!=job['id'] or r['plan_sha256']!=plan_sha:raise ValueError('failed or mismatched host receipt')
    if r['version']!=VERSION or r['mode_name']!=job['mode_name'] or r['submode_name']!=job['submode_name']:raise ValueError('engine mismatch')
    for key,v in {'I_PITCHMODE':job['mode']*65536+job['submode'],'D_PITCH':job['semitones'],'D_PLAYRATE':1/job['time_ratio'],'B_PPITCH':1,'D_VOL':1,'D_STARTOFFS':0}.items():
        if r['take'].get(key)!=v:raise ValueError('take mismatch '+key)
    for key,v in {'RENDER_NORMALIZE':0,'RENDER_DITHER':0,'RENDER_TAILFLAG':0,'RENDER_CHANNELS':1,'RENDER_SRATE':job['rate']}.items():
        if r['project'].get(key)!=v:raise ValueError('render mismatch '+key)
    if r['targets']!=job['output'] or r['render_format']!='ZXZhdyAAAA==':raise ValueError('target mismatch')
    src=c.inspect_audio(Path(job['input'])); dst=c.inspect_audio(Path(job['output']))
    errors=c.output_checks(src,dst,c.Request.from_semitones(job['time_ratio'],job['semitones']))
    if errors or dst['rms']<=1e-8:raise ValueError('invalid audio: '+str(errors))
    return r,dst
