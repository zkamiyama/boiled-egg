import os,unittest,heapq
from pathlib import Path
import numpy as np
from experiment import Kernel,render,derivatives,wrap
LIB=os.environ.get('BOILED_EGG_PHASE_HEAP_LIBRARY')
class GradientTests(unittest.TestCase):
    def test_affine_gradient(self):
        f=np.arange(19)*.2;n=np.arange(7)*.4;p=wrap(n[:,None]+f[None,:])
        dt,df,back=derivatives(p,8,256)
        np.testing.assert_allclose(df,.2,atol=2e-15)
        np.testing.assert_allclose(dt[:,0],.05,atol=2e-15)
    def test_invalid(self):
        for x in (np.full(100,np.nan),np.zeros((10,0))):
            with self.assertRaises(ValueError):render(x,48000)
    def test_heap_matches_independent_exhaustive_priority(self):
        self.assertIsNotNone(LIB,'compile bridge and set BOILED_EGG_PHASE_HEAP_LIBRARY')
        rng=np.random.default_rng(72109)
        for bins in (5,33,129):
            k=Kernel(LIB,bins)
            try:
                for _ in range(20):
                    m,pm=rng.integers(0,10,(2,bins)).astype(float);dt,pdt,df,pp,p=rng.normal(size=(5,bins))
                    got,n=k.process(m,pm,dt,pdt,df,pp,p,17,1.5)
                    remaining=set(np.flatnonzero(m>max(m.max(),pm.max())*1e-6));todo=[(pm[i],0,i) for i in remaining]
                    expected=p.copy();vertical=0
                    while remaining:
                        top=max(todo,key=lambda a:(a[0],-a[1],-a[2]));todo.remove(top);w,age,i=top
                        if age==0:
                            if i in remaining:
                                expected[i]=pp[i]+8.5*(dt[i]+pdt[i]);remaining.remove(i);todo.append((m[i],1,i))
                        else:
                            for j in (i-1,i+1):
                                if j in remaining:
                                    expected[j]=expected[i]+(j-i)*.75*(df[i]+df[j]);remaining.remove(j);todo.append((m[j],1,j));vertical+=1
                    np.testing.assert_allclose(got,wrap(expected),atol=1e-12);self.assertEqual(n,vertical)
            finally:k.close()
    def test_identity_and_stereo(self):
        rng=np.random.default_rng(8021);x=rng.normal(0,.1,7001);stereo=np.c_[x,-.5*x]
        for mode in ('locked','trapezoid','heap'):
            y,_=render(stereo,48000,mode=mode,kernel_path=LIB,window=512)
            np.testing.assert_allclose(y,stereo,atol=1e-14)
            y,s=render(stereo,48000,time=1.3,pitch=.75,mode=mode,kernel_path=LIB,window=512)
            self.assertEqual(len(y),round(len(x)*1.3));np.testing.assert_allclose(y[:,1],-.5*y[:,0],atol=1e-14)
    def test_kernel_shape_guard(self):
        k=Kernel(LIB,5)
        try:
            z=np.zeros(4)
            with self.assertRaises(ValueError):k.process(z,z,z,z,z,z,z,1,1)
        finally:k.close()
    def test_fractional_short_duration(self):
        for time in (.5,2.):
            for pitch in (.5,2.):
                y,_=render(np.ones(1),48000,time=time,pitch=pitch,kernel_path=LIB)
                self.assertEqual(len(y),int(np.floor(time+.5)));self.assertTrue(np.isfinite(y).all())
    def test_silence_short_and_reproducible(self):
        for n in (1,31,7001):
            x=np.zeros((n,2));a,_=render(x,48000,time=2,mode='heap',kernel_path=LIB)
            b,_=render(x,48000,time=2,mode='heap',kernel_path=LIB)
            self.assertFalse(np.any(a));np.testing.assert_array_equal(a,b)
if __name__=='__main__':unittest.main()
