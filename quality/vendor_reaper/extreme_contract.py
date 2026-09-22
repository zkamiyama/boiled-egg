"""Explicit extended-range comparison; the old primary Request is unchanged."""
from __future__ import annotations
import ctypes as C
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import contract as h

PRESETS = ('Lowest', 'Lower', 'Low', 'Most', 'High', 'Higher', 'Highest')
PRO = {f'pro_{name.lower()}': (9, i, 'élastique 3.3.3 Pro',
       f'Preserve Formants ({name} Pitches)') for i, name in enumerate(PRESETS, 1)}
VENDOR = {'pro_off': (9, 0, 'élastique 3.3.3 Pro', 'Normal'), **PRO}
SDK = {'sdk_wsola': ('wsola', 'general', 'off'),
       'sdk_pv_off': ('pv', 'general', 'off'),
       'sdk_pv_transient': ('pv', 'transient', 'off'),
       'sdk_harmonic': ('pv', 'general', 'harmonic'),
       'sdk_monophonic': ('pv', 'general', 'monophonic')}

@dataclass(frozen=True)
class Request:
    duration_ratio: float = 1.
    semitones: float = 0.
    duration_tolerance_frames: int = 0

    def __post_init__(self):
        for x, lo, hi in ((self.duration_ratio, .25, 4.), (self.semitones, -24., 24.)):
            if type(x) not in (int, float) or not math.isfinite(x) or not lo <= x <= hi:
                raise ValueError('outside explicitly bounded extreme comparison')
        if type(self.duration_tolerance_frames) is not int or self.duration_tolerance_frames != 0:
            raise ValueError('exact length required')

    @property
    def pitch_ratio(self): return 2.**(self.semitones/12.)

    def target_frames(self, frames):
        if type(frames) is not int or frames <= 0: raise ValueError('invalid frame count')
        return math.floor(frames*self.duration_ratio+.5)


def job(identifier, source, output, rate, frames, request, engine):
    if not re.fullmatch(r'[A-Za-z0-9_+.-]+', identifier): raise ValueError('unsafe ID')
    if engine not in VENDOR or rate not in (48000, 96000): raise ValueError('unknown explicit mode/rate')
    for path in (output, output.with_suffix('.json'), output.with_suffix('.rpp')):
        if path.exists() or path.is_symlink(): raise ValueError('refuse overwrite')
    mode, sub, name, subname = VENDOR[engine]
    return dict(id=identifier, input=str(source.resolve(strict=True)), output=str(output.resolve()),
                directory=str(output.resolve().parent), stem=output.stem,
                receipt=str(output.with_suffix('.json').resolve()), project=str(output.with_suffix('.rpp').resolve()),
                rate=rate, input_frames=frames, output_frames=request.target_frames(frames),
                semitones=request.semitones, time_ratio=request.duration_ratio,
                mode=mode, submode=sub, mode_name=name, submode_name=subname)


def verify(j, plan_sha):
    r=json.loads(Path(j['receipt']).read_text())
    expected={'status':'complete','id':j['id'],'plan_sha256':plan_sha,'version':h.VERSION,
              'mode_name':j['mode_name'],'submode_name':j['submode_name'],
              'targets':j['output'],'render_format':'ZXZhdyAAAA=='}
    if any(r.get(k)!=v for k,v in expected.items()): raise ValueError('host identity mismatch')
    for part, values in {
        'take': {'I_PITCHMODE':j['mode']*65536+j['submode'],'D_PITCH':j['semitones'],
                 'D_PLAYRATE':1/j['time_ratio'],'B_PPITCH':1,'D_VOL':1,'D_PAN':0,'D_STARTOFFS':0},
        'item': {'D_POSITION':0,'D_LENGTH':j['output_frames']/j['rate'],'D_VOL':1,
                 'D_FADEINLEN':0,'D_FADEOUTLEN':0,'B_LOOPSRC':0},
        'project': {'RENDER_NORMALIZE':0,'RENDER_DITHER':0,'RENDER_TAILFLAG':0,'RENDER_CHANNELS':1,
                    'RENDER_SRATE':j['rate'],'RENDER_STARTPOS':0,'RENDER_ENDPOS':j['output_frames']/j['rate']}
    }.items():
        for key,value in values.items():
            got=r.get(part,{}).get(key)
            if type(got) not in (int,float) or not math.isfinite(got) or abs(got-value)>1e-10:
                raise ValueError('host readback mismatch '+part+'/'+key)
    source=h.c.inspect_audio(Path(j['input'])); audio=h.c.inspect_audio(Path(j['output']))
    errors=h.c.output_checks(source,audio,Request(j['time_ratio'],j['semitones']))
    if errors or audio['rms']<=1e-8: raise ValueError('invalid output '+repr(errors))
    if not Path(j['project']).is_file(): raise ValueError('missing saved project')
    return r,audio


class Audio(C.Structure):
    _fields_=[(x,C.c_uint32) for x in ('struct_size','abi_version','sample_rate','channels','max_block_size','window_frames','search_frames','fifo_frames')]
class Backend(C.Structure):
    _fields_=[(x,C.c_uint32) for x in ('struct_size','version','backend_id','quality_mode','formant_policy','io_contract','flags')]+[(x,C.c_float) for x in ('initial_time_ratio','initial_pitch_ratio','initial_formant_ratio')]+[('reserved',C.c_uint32*2)]
class Info(C.Structure):
    _fields_=[(x,C.c_uint32) for x in ('struct_size','version','backend_id','status','feature_flags','quality_mode_mask','formant_policy_mask','min_sample_rate','max_sample_rate','max_channels','max_block_frames')]+[(x,C.c_float) for x in ('min_time_ratio','max_time_ratio','min_pitch_ratio','max_pitch_ratio','min_formant_ratio','max_formant_ratio')]+[('reserved',C.c_uint32*3)]


def expected_status(engine, request):
    if engine not in SDK: raise ValueError('unknown SDK engine')
    t=C.c_float(request.duration_ratio).value; p=C.c_float(request.pitch_ratio).value
    return 7 if SDK[engine][0]=='pv' and not (.5<=t<=2 and .5<=p<=2 and t*p<=2) else 0


class Capability:
    """Real C ABI validation, never a substitute for successful audio rendering."""
    def __init__(self, path, sha):
        if h.c.fingerprint(path)!=sha: raise ValueError('SDK identity changed')
        self.lib=C.CDLL(str(path.resolve(strict=True)))
        self.lib.boiledegg_default_config.argtypes=[C.c_uint32,C.c_uint32];self.lib.boiledegg_default_config.restype=Audio
        self.lib.boiledegg_default_backend_config.argtypes=[];self.lib.boiledegg_default_backend_config.restype=Backend
        self.lib.boiledegg_query_backend.argtypes=[C.c_uint32,C.POINTER(Info)];self.lib.boiledegg_query_backend.restype=C.c_int
        self.lib.boiledegg_validate_backend_config.argtypes=[C.POINTER(Audio),C.POINTER(Backend)];self.lib.boiledegg_validate_backend_config.restype=C.c_int
        self.inventory={}
        for bid in (0,1):
            info=Info();info.struct_size=C.sizeof(info)
            if self.lib.boiledegg_query_backend(bid,C.byref(info)): raise ValueError('query failed')
            if info.status!=(1 if bid==0 else 2): raise ValueError('expected stable WSOLA and experimental PV build')
            self.inventory[str(bid)]={k:getattr(info,k) for k,_ in info._fields_ if k!='reserved'}

    def validate(self, engine, rate, request):
        backend,quality,policy=SDK[engine]
        a=self.lib.boiledegg_default_config(rate,1);a.max_block_size=64
        b=self.lib.boiledegg_default_backend_config();b.backend_id=int(backend=='pv')
        b.quality_mode=int(quality=='transient');b.formant_policy={'off':0,'harmonic':1,'monophonic':2}[policy]
        b.io_contract=1;b.flags=int(backend=='pv');b.initial_time_ratio=request.duration_ratio;b.initial_pitch_ratio=request.pitch_ratio
        status=self.lib.boiledegg_validate_backend_config(C.byref(a),C.byref(b))
        if status!=expected_status(engine,request): raise ValueError('unexpected capability result')
        return dict(status=status,expected_status=expected_status(engine,request),
                    time_float32=b.initial_time_ratio,pitch_float32=b.initial_pitch_ratio,
                    engine=engine,rate=rate,block=64)
