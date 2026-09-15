"""Validated binding for the research-only no-allocation interpolation kernel."""
import ctypes as c
import numpy as np
class Mapper:
    def __init__(self,path):
        self.lib=c.CDLL(str(path));self.ptr=c.POINTER(c.c_double)
        self.lib.transient_map.argtypes=[self.ptr,self.ptr,c.c_uint,self.ptr,self.ptr,c.c_uint]
        self.lib.transient_map.restype=c.c_int
    def __call__(self,positions,t,u):
        q,t,u=[np.ascontiguousarray(v,dtype=np.float64) for v in (positions,t,u)]
        if q.ndim!=1 or t.ndim!=1 or u.shape!=t.shape or len(t)<2 or max(len(q),len(t))>=2**32:
            raise ValueError('invalid map dimensions')
        out=np.empty_like(q)
        if self.lib.transient_map(t.ctypes.data_as(self.ptr),u.ctypes.data_as(self.ptr),len(t),q.ctypes.data_as(self.ptr),out.ctypes.data_as(self.ptr),len(q)):
            raise ValueError('invalid map coordinates')
        if not np.isfinite(out).all():raise ValueError('nonfinite map')
        return out
