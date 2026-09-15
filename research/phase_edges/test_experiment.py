"""Independent graph/projection calibration. Not listening or MOS evidence."""
import importlib.util
import os
from pathlib import Path
import unittest
import numpy as np
import experiment as e
import consistency as p

EDGE=os.environ['BOILED_EGG_PHASE_EDGE_LIBRARY']
OLD=os.environ['BOILED_EGG_PHASE_HEAP_LIBRARY']

def load_old():
    spec=importlib.util.spec_from_file_location('old_phase_render',Path(__file__).parents[1]/'phase_gradient/experiment.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def exhaustive(mag,oldmag,dt,df,old,phase):
    threshold=1e-6*max(mag.max(),oldmag.max());unknown=mag>threshold;out=phase.copy()
    queue=[(float(oldmag[k]),0,k) for k in range(len(mag)) if unknown[k]]
    while unknown.any():
        # Deliberately linear exhaustive priority search, not a heap copy.
        i=max(range(len(queue)),key=lambda i:(queue[i][0],-queue[i][1],-queue[i][2]))
        w,age,k=queue.pop(i)
        candidates=[k] if age==0 else [q for q in (k-1,k+1) if 0<=q<len(mag)]
        for q in candidates:
            if not unknown[q]:continue
            out[q]=old[q]+dt[q] if age==0 else out[k]+(df[k] if q>k else -df[q])
            unknown[q]=False;queue.append((float(mag[q]),1,q))
    return e.wrap(out)


class EdgeTests(unittest.TestCase):
    def test_random_nonconservative_graph_oracle(self):
        rng=np.random.default_rng(9150)
        for n in (2,9,33):
            k=e.EdgeKernel(EDGE,n)
            try:
                for _ in range(30):
                    mag=rng.integers(0,7,n).astype(float);oldmag=rng.integers(0,7,n).astype(float)
                    dt=rng.normal(0,2,n);df=rng.normal(0,2,n-1);old=rng.normal(0,2,n);phase=rng.normal(0,2,n)
                    y,_=k.process(mag,oldmag,dt,df,old,phase)
                    np.testing.assert_allclose(y,exhaustive(mag,oldmag,dt,df,old,phase),atol=1e-13)
            finally:k.close()
    def test_nonaffine_identity_without_renderer_bypass(self):
        rng=np.random.default_rng(12);n=129;k=e.EdgeKernel(EDGE,n)
        try:
            phase=rng.uniform(-np.pi,np.pi,n);old=rng.uniform(-np.pi,np.pi,n)
            y,_=k.process(rng.uniform(.1,1,n),rng.uniform(.1,1,n),e.wrap(phase-old),e.wrap(np.diff(phase)),old,phase)
            np.testing.assert_allclose(e.wrap(y-phase),0,atol=1e-13)
        finally:k.close()
    def test_kernel_invalid_arrays(self):
        k=e.EdgeKernel(EDGE,9);a=np.ones(9)
        try:
            for df in (np.ones(9),np.full(8,np.nan)):
                with self.assertRaises(ValueError):k.process(a,a,a,df,a,a)
            with self.assertRaises(ValueError):k.process(-a,a,a,np.ones(8),a,a)
        finally:k.close()
    def test_inherited_comparators_remain_exact(self):
        x=np.random.default_rng(921).normal(0,.1,(6000,2));old=load_old()
        for mode in ('locked','heap'):
            a,_=old.render(x,48000,time=1.5,mode=mode,kernel_path=OLD)
            b,_=e.render(x,48000,time=1.5,mode=mode,kernel_path=OLD,edge_path=EDGE)
            np.testing.assert_array_equal(a,b)
    def test_identity_short_zero_and_odd(self):
        for length in (0,1,31,5001):
            x=np.random.default_rng(length).normal(0,.1,(length,2))
            for mode in e.MODES:
                y,_=e.render(x,48000,mode=mode,kernel_path=OLD,edge_path=EDGE)
                self.assertEqual(y.shape,x.shape);np.testing.assert_allclose(x,y,atol=1e-12)
    def test_silence_and_duration(self):
        for mode in e.MODES:
            for ratio in (.5,1.5,2):
                y,_=e.render(np.zeros((113,2)),96000,time=ratio,mode=mode,kernel_path=OLD,edge_path=EDGE)
                self.assertEqual(len(y),int(np.floor(113*ratio+.5)));self.assertFalse(np.any(y))
    def test_linked_antiphase(self):
        x=np.random.default_rng(922).normal(0,.1,5000)
        for mode in e.MODES:
            y,_=e.render(np.c_[x,-.5*x],48000,pitch=1.5,mode=mode,kernel_path=OLD,edge_path=EDGE)
            np.testing.assert_allclose(y[:,1],-.5*y[:,0],atol=1e-12)
    def test_renderer_invalid(self):
        for x in (np.zeros((10,0)),np.full(10,np.nan)):
            with self.assertRaises(ValueError):e.render(x,48000,kernel_path=OLD,edge_path=EDGE)
        for controls in ({'mode':'unknown'},{'time':3},{'pitch':0},{'window':123}):
            with self.assertRaises(ValueError):e.render(np.ones(100),48000,kernel_path=OLD,edge_path=EDGE,**controls)

class ProjectionTests(unittest.TestCase):
    def test_shared_projection_preserves_complex_channel_ratios(self):
        rng=np.random.default_rng(9);target=rng.normal(size=(4,5,2))+1j*rng.normal(size=(4,5,2))
        estimate=rng.normal(size=target.shape)+1j*rng.normal(size=target.shape)
        result=p.shared_phase_projection(target,estimate,target)
        np.testing.assert_allclose(abs(result),abs(target),atol=1e-14)
        np.testing.assert_allclose(result[:,:,0]/result[:,:,1],target[:,:,0]/target[:,:,1],atol=1e-14)
        # Exact projection's objective should be no worse than any sampled angle.
        optimum=np.sum(abs(result-estimate)**2,axis=2)
        for theta in np.linspace(-np.pi,np.pi,31):
            trial=np.sum(abs(target*np.exp(1j*theta)-estimate)**2,axis=2)
            self.assertTrue(np.all(optimum<=trial+1e-12))
    def test_zero_inner_product_keeps_previous(self):
        target=np.ones((2,3,2),complex);previous=target*1j
        result=p.shared_phase_projection(target,np.zeros_like(target),previous)
        np.testing.assert_array_equal(result,previous)
    def test_consistency_residual_decreases(self):
        n=128;w=np.hanning(n);starts=np.arange(0,512,16);length=900
        rng=np.random.default_rng(914);target=rng.normal(size=(len(starts),n//2+1,2))+1j*rng.normal(size=(len(starts),n//2+1,2))
        target[:,[0,-1]]=target[:,[0,-1]].real
        _,errors=p.refine(target,target,starts,w,length,8)
        self.assertTrue(np.all(np.diff(errors)<=1e-12),errors)
        self.assertLess(errors[-1],errors[0])
    def test_projection_validation(self):
        a=np.zeros((2,5,1),complex)
        with self.assertRaises(ValueError):p.refine(a,a,[0,1],np.ones(8),20,99)

if __name__=='__main__':unittest.main()
