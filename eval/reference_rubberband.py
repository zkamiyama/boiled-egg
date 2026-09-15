"""Evaluation-only direct Rubber Band C-API adapter; never linked into product.

Independent API glue, not copied DSP. Uses the public v3.3 C ABI and the installed
library supplied explicitly by the caller. Offline study+process includes the
library's own start/end compensation. No fitted shift, normalization or trimming.
Rubber Band is GPL/commercially dual licensed; do not bundle its library here.
"""
from __future__ import annotations
import ctypes as c
from pathlib import Path

import numpy as np

from comparison_contract import Request, fingerprint


class Reference:
    def __init__(self, library: Path):
        self.path=Path(library).resolve(strict=True)
        self.sha256=fingerprint(self.path)
        self.lib=c.CDLL(str(self.path))
        self.P=c.POINTER(c.c_float)
        H,U,PP=c.c_void_p,c.c_uint,c.POINTER(self.P)
        signatures={
            'rubberband_new':([U,U,c.c_int,c.c_double,c.c_double],H),
            'rubberband_delete':([H],None),
            'rubberband_get_engine_version':([H],c.c_int),
            'rubberband_set_expected_input_duration':([H,U],None),
            'rubberband_set_max_process_size':([H,U],None),
            'rubberband_study':([H,PP,U,c.c_int],None),
            'rubberband_process':([H,PP,U,c.c_int],None),
            'rubberband_available':([H],c.c_int),
            'rubberband_retrieve':([H,PP,U],U),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.lib,name);fn.argtypes=args;fn.restype=result

    def render(self, audio: np.ndarray, rate: int, request: Request, engine: int=3,
               formant: str='off', block: int=4096) -> tuple[np.ndarray,dict]:
        x=np.asarray(audio)
        if (x.ndim!=2 or x.shape[1] not in (1,2) or not 0<len(x)<2**32 or
            rate not in (44100,48000,88200,96000) or not np.isfinite(x).all() or
            engine not in (2,3) or formant not in ('off','preserved') or
            type(block) is not int or not 1<=block<=4096):
            raise ValueError('invalid reference signal/controls')
        if fingerprint(self.path)!=self.sha256:raise ValueError('library identity changed')
        planar=np.array(x.T,dtype=np.float32,order='C',copy=True)
        if not np.isfinite(planar).all():raise ValueError('float32 conversion overflow')
        before=planar.tobytes()
        # Public enum values: ProcessOffline=0, ThreadingNever, PitchHighQuality,
        # ChannelsTogether; optional EngineFiner and FormantPreserved.
        options=0x00010000|0x02000000|0x10000000|(0x20000000 if engine==3 else 0)|(0x01000000 if formant=='preserved' else 0)
        h=self.lib.rubberband_new(rate,x.shape[1],options,request.duration_ratio,request.pitch_ratio)
        if not h:raise RuntimeError('reference creation failed')
        chunks=[];written=0;expected=request.target_frames(len(x))
        try:
            actual=self.lib.rubberband_get_engine_version(h)
            if actual!=engine:raise RuntimeError('library did not instantiate requested R2/R3 engine')
            self.lib.rubberband_set_expected_input_duration(h,len(x))
            self.lib.rubberband_set_max_process_size(h,block)
            for start in range(0,len(x),block):
                n=min(block,len(x)-start)
                pointers=(self.P*x.shape[1])(*(ch[start:].ctypes.data_as(self.P) for ch in planar))
                self.lib.rubberband_study(h,pointers,n,int(start+n==len(x)))
            buffer=np.zeros((x.shape[1],block),dtype=np.float32)
            out=(self.P*x.shape[1])(*(ch.ctypes.data_as(self.P) for ch in buffer))
            for start in range(0,len(x),block):
                n=min(block,len(x)-start)
                pointers=(self.P*x.shape[1])(*(ch[start:].ctypes.data_as(self.P) for ch in planar))
                self.lib.rubberband_process(h,pointers,n,int(start+n==len(x)))
                while (available:=self.lib.rubberband_available(h))>0:
                    retrieved=self.lib.rubberband_retrieve(h,out,min(block,available))
                    if not 0<retrieved<=min(block,available):raise RuntimeError('invalid/no retrieval progress')
                    written+=retrieved
                    if written>expected+4*rate:raise RuntimeError('unexpected unbounded reference output')
                    chunks.append(buffer[:,:retrieved].T.copy())
            if self.lib.rubberband_available(h)!=-1:raise RuntimeError('offline reference not fully drained')
            result=np.concatenate(chunks,axis=0) if chunks else np.empty((0,x.shape[1]),dtype=np.float32)
            if not np.isfinite(result).all() or planar.tobytes()!=before:raise RuntimeError('nonfinite or mutated input')
            if fingerprint(self.path)!=self.sha256:raise RuntimeError('reference library changed during processing')
            return result,dict(engine=actual,formant=formant,options_hex=hex(options),block=block,
                mode='offline-study-and-process',library=str(self.path),library_sha256=self.sha256,
                expected_frames=expected,actual_frames=len(result),duration_error_frames=len(result)-expected,
                alignment='library offline compensation; no fitted shift or extra trim/pad',
                adapter_sha256=fingerprint(Path(__file__)))
        finally:
            self.lib.rubberband_delete(h)
