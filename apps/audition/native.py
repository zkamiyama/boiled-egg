"""ctypes binding for the experimental C++ file-transport module.

All native operations for one instance must be made by one owner thread.
The GUI routes commands to a dedicated worker; it never calls render itself.
"""
from __future__ import annotations
import ctypes as C
import os
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
class Config(C.Structure):
    _fields_ = [(n,C.c_uint32) for n in ('struct_size','version','source_rate','output_rate','channels','mode','formant_policy','max_block_frames')]
class Event(C.Structure):
    _fields_ = [('offset',C.c_uint32),('parameter',C.c_uint32),('ramp_frames',C.c_uint32),('reserved',C.c_uint32),('value',C.c_double)]
class Info(C.Structure):
    _fields_ = [(n,C.c_uint32) for n in ('struct_size','version','capabilities','ended')] + [(n,C.c_uint64) for n in ('output_frames','source_frames','synthesis_frames','analysis_frames')] + [(n,C.c_double) for n in ('source_position','analysis_anchor','speed','pitch_semitones','formant_semitones')] + [(n,C.c_uint32) for n in ('window_frames','hop_frames')] + [('owned_bytes',C.c_uint64)]
NATIVE_MODES = (
    ('PV Classic — native spectral hold',0),
    ('PV Locked — native spectral hold',1),
    ('PV Transient — native spectral hold',2),
    ('WSOLA — native time-domain hold',3),
    ('WSOLA Transient — native time-domain hold',4),
    ('WSOLA Efficient — native time-domain hold',5),
)

def library_path(explicit: str | Path | None = None) -> Path:
    requested=explicit or os.getenv('BOILED_EGG_TRANSPORT_LIBRARY')
    if requested:
        path=Path(requested)
        if not path.is_file():raise FileNotFoundError(f'Explicit native library not found: {path}')
        return path.resolve()
    candidates=[]
    for name in ('libboiled_egg_transport.so','libboiled_egg_transport.dylib','boiled_egg_transport.dll'):
        for directory in ('build-transport','build-transport/Release','lib'):
            candidates.append(ROOT/directory/name)
    for p in candidates:
        if p.is_file(): return p.resolve()
    raise FileNotFoundError('Native transport not built. Run cmake -S sdk/transport -B build-transport -DCMAKE_BUILD_TYPE=Release, then cmake --build build-transport.')

class Transport:
    def __init__(self, audio: np.ndarray, rate: int, mode: int = 1, policy: int = 0,
                 output_rate: int | None = None, library: str | Path | None = None):
        self.path=library_path(library); self.lib=C.CDLL(str(self.path)); self.handle=None
        fp=C.POINTER(C.c_float)
        self.lib.be_transport_default_config.argtypes=[C.c_uint32,C.c_uint32];self.lib.be_transport_default_config.restype=Config
        self.lib.be_transport_create.argtypes=[C.POINTER(Config),fp,C.c_uint64,C.POINTER(C.c_int)];self.lib.be_transport_create.restype=C.c_void_p
        self.lib.be_transport_render.argtypes=[C.c_void_p,fp,C.c_uint32,C.POINTER(Event),C.c_uint32];self.lib.be_transport_render.restype=C.c_int
        self.lib.be_transport_seek.argtypes=[C.c_void_p,C.c_double];self.lib.be_transport_seek.restype=C.c_int
        self.lib.be_transport_get_info.argtypes=[C.c_void_p,C.POINTER(Info)];self.lib.be_transport_get_info.restype=C.c_int
        self.lib.be_transport_destroy.argtypes=[C.c_void_p];self.lib.be_transport_destroy.restype=None
        x=np.asarray(audio,dtype=np.float32)
        if x.ndim==1:x=x[:,None]
        if x.ndim!=2 or not 1<=x.shape[1]<=8 or not np.isfinite(x).all(): raise ValueError('Finite audio with 1..8 channels required')
        x=np.ascontiguousarray(x);self.channels=x.shape[1];self.rate=output_rate or rate
        cfg=self.lib.be_transport_default_config(rate,self.channels)
        cfg.output_rate=self.rate;cfg.mode=mode;cfg.formant_policy=policy
        self.block_limit=cfg.max_block_frames
        result=C.c_int()
        self.handle=self.lib.be_transport_create(C.byref(cfg),x.ctypes.data_as(fp),len(x),C.byref(result))
        if not self.handle:self._check(result.value)
    @staticmethod
    def _check(code: int):
        if code:raise ValueError({1:'Invalid native audio, parameter or block',2:'Unsupported mode/policy/rate: no fallback',3:'Native allocation failed',4:'Native internal failure'}.get(code,f'Native error {code}'))
    def _alive(self):
        if not self.handle:raise RuntimeError('Transport is closed')
    def close(self):
        if self.handle:self.lib.be_transport_destroy(self.handle);self.handle=None
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def render(self, frames: int, events: list[tuple[int,int,float,int]] = ()) -> np.ndarray:
        self._alive()
        if not 0<=frames<=self.block_limit:raise ValueError('Block out of bounds')
        for offset,param,value,ramp in events:
            if not 0<=offset<=frames or not 0<=param<=2 or not 0<=ramp<2**32:raise ValueError('Invalid event fields')
        batch=(Event*len(events))(*(Event(offset,param,ramp,0,value) for offset,param,value,ramp in events))
        y=np.empty((frames,self.channels),dtype=np.float32)
        self._check(self.lib.be_transport_render(self.handle,y.ctypes.data_as(C.POINTER(C.c_float)),frames,batch,len(batch)))
        return y
    def set(self,speed: float, pitch: float, formant: float = 0., ramp: int = 0):
        self.render(0,[(0,0,speed,ramp),(0,1,pitch,ramp),(0,2,formant,ramp)])
    def seek(self,source_frame: float):
        self._alive();self._check(self.lib.be_transport_seek(self.handle,source_frame))
    def info(self) -> dict:
        self._alive();value=Info();value.struct_size=C.sizeof(value)
        self._check(self.lib.be_transport_get_info(self.handle,C.byref(value)))
        return {key:getattr(value,key) for key,_ in Info._fields_}
