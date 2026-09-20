import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pvdr_phase_reference as p
import nsdgt_foundation as nsg
import comparison_contract as contract


def dense_reference(z,m,centers,alpha,method,seed=20260920):
    """Independent slow equation reference: sorted candidate list, no native FFT/heap."""
    k=m//2+1;n=len(centers);c=np.asarray(z,dtype=np.complex128).reshape(n,m)
    mag=np.abs(c[:,:k]);phase=np.angle(c[:,:k]);omega=2*np.pi*np.arange(k)/m
    principal=lambda x:x-2*np.pi*np.floor(x/(2*np.pi)+.5)
    slopes=principal(np.diff(phase,axis=0)-np.diff(centers)[:,None]*omega)/np.diff(centers)[:,None]+omega
    dt=np.empty_like(phase);dt[0]=slopes[0];dt[-1]=slopes[-1];dt[1:-1]=(slopes[:-1]+slopes[1:])/2
    differences=principal(np.diff(phase,axis=1));df=np.empty_like(phase)
    df[:,0]=differences[:,0];df[:,-1]=differences[:,-1];df[:,1:-1]=(differences[:,:-1]+differences[:,1:])/2
    result_phase=phase.copy();pred=np.full((n,k),-3,dtype=np.int32)
    def random_phase(j,b):
        mask=(1<<64)-1;v=(seed^(j<<32)^b)+0x9e3779b97f4a7c15;v&=mask
        v=((v^(v>>30))*0xbf58476d1ce4e5b9)&mask;v=((v^(v>>27))*0x94d049bb133111eb)&mask;v^=v>>31
        return 2*np.pi*(v>>11)*2.**-53-np.pi
    for j in range(1,n):
        hop=round(alpha*centers[j])-round(alpha*centers[j-1])
        if method==p.METHODS[0]:result_phase[j]=principal(result_phase[j-1]+hop*slopes[j-1]);pred[j]=-1;continue
        threshold=1e-6*max(mag[j].max(),mag[j-1].max());todo=set(np.flatnonzero(mag[j]>threshold).tolist())
        candidates=[(float(mag[j-1,b]),0,b) for b in todo]
        for b in set(range(k))-todo:result_phase[j,b]=random_phase(j,b);pred[j,b]=-2
        while todo:
            candidates.sort(key=lambda item:(-item[0],item[1],item[2]));_,current,b=candidates.pop(0)
            if not current:
                if b not in todo:continue
                result_phase[j,b]=principal(result_phase[j-1,b]+hop*(dt[j-1,b]+dt[j,b])/2)
                pred[j,b]=-1;todo.remove(b);candidates.append((float(mag[j,b]),1,b))
            else:
                for neighbour in (b+1,b-1):
                    if neighbour not in todo:continue
                    result_phase[j,neighbour]=principal(result_phase[j,b]+(neighbour-b)*alpha*(df[j,b]+df[j,neighbour])/2)
                    pred[j,neighbour]=b;todo.remove(neighbour);candidates.append((float(mag[j,neighbour]),1,neighbour))
    out=np.zeros_like(c);out[:,:k]=mag*np.exp(1j*result_phase)
    out[:,0]=np.copysign(mag[:,0],c[:,0].real);out[:,m//2]=np.copysign(mag[:,-1],c[:,m//2].real)
    out[:,k:]=np.conj(out[:,1:m//2][:,::-1])
    return out.ravel(),pred.ravel(),dt.ravel(),df.ravel()


def random_coeff(m,n,seed=123):
    rng=np.random.default_rng(seed);k=m//2+1
    mag=10**rng.uniform(-9,1,(n,k));ph=rng.uniform(-np.pi,np.pi,(n,k))
    z=np.zeros((n,m),complex);z[:,:k]=mag*np.exp(1j*ph);z[:,0]=mag[:,0];z[:,m//2]=-mag[:,-1]
    z[:,k:]=np.conj(z[:,1:m//2][:,::-1]);return z.astype(np.complex64).ravel()

class NativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(os.environ['BE_PHASE_LIBRARY']).resolve(strict=True)
        cls.phase=p.Phase(cls.path,contract.fingerprint(cls.path))
        cls.nsgpath=Path(os.environ['BE_NSG_LIBRARY']).resolve(strict=True)
        cls.native=nsg.Native(cls.nsgpath,contract.fingerprint(cls.nsgpath))
    def test_dense_priority_and_gradients(self):
        largest=0
        for m,centers,alpha,method in itertools.product((16,32,64),([0,3,6,9,12,15],[0,1,4,6,10,13]),p.ALPHAS,p.METHODS):
            z=random_coeff(m,len(centers));native=self.phase(z,m,centers,alpha,method);reference=dense_reference(z,m,centers,alpha,method)
            err=float(np.max(np.abs(native[0]-reference[0]))/max(1,np.max(np.abs(z))));largest=max(largest,err)
            self.assertLess(err,3e-6);np.testing.assert_array_equal(native[1],reference[1])
            np.testing.assert_allclose(native[2],reference[2],atol=1e-12,rtol=1e-12)
            np.testing.assert_allclose(native[3],reference[3],atol=1e-12,rtol=1e-12)
        if os.environ.get('PG_EVIDENCE'):
            root=Path(os.environ['PG_EVIDENCE']);root.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(root/'dense-controls.npz',input=z,native=native[0],reference=reference[0],predecessors=native[1],dt=native[2],df=native[3])
            contract.json_write(root/'dense-controls.json',dict(cases=36,max_normalized_complex_error=largest))
    def test_phase_origin_analytic(self):
        m=64;centers=[0,1,2,3];z=np.zeros((len(centers),m),complex)
        for j,a in enumerate(centers):
            for k in range(1,m//2):
                magnitude=(2 if k==8 else 1)*(2 if j else 1) if 7<=k<=9 else 1e-9
                z[j,k]=magnitude*np.exp(1j*(.2*a+.3*(k-8)));z[j,m-k]=np.conj(z[j,k])
        y,pred,dt,df,info,_=self.phase(z.ravel(),m,centers,2,p.METHODS[1])
        y=y.reshape(len(centers),m);self.assertGreater(info['frequency_edges'],0)
        for j in range(1,len(centers)):
            for k in range(7,10):self.assertLess(abs(np.angle(y[j,k]*np.exp(-1j*(.4*j+.6*(k-8))))),2e-6)
    def test_magnitude_and_real_symmetry(self):
        z=random_coeff(64,5)
        for method in p.METHODS:
            y,*_=self.phase(z,64,[0,2,4,6,8],4,method)
            np.testing.assert_allclose(np.abs(y),np.abs(z),rtol=3e-6,atol=1e-8)
            r=y.reshape(5,64);np.testing.assert_array_equal(r[:,33:],np.conj(r[:,1:32][:,::-1]))
            self.assertTrue(np.all(r[:,(0,32)].imag==0))
    def test_no_hidden_input_bypass(self):
        x=.2*np.sin(2*np.pi*61*np.arange(257)/22050);centers=list(range(0,257,8));windows=[np.hanning(64)]*len(centers)
        shape=nsg.pack(len(x),128,centers,windows);z,_,_=self.native.call(True,x,shape)
        zz,*_=self.phase(z,128,centers,1,p.METHODS[1]);y,_,_=self.native.call(False,zz,shape)
        quiet,*_=self.phase(z*.5,128,centers,1,p.METHODS[1]);half,_,_=self.native.call(False,quiet,shape)
        np.testing.assert_allclose(half,y*.5,rtol=3e-6,atol=1e-7)
        erased,*_=self.phase(z*0,128,centers,1,p.METHODS[1]);zero,_,_=self.native.call(False,erased,shape)
        self.assertTrue(np.all(zero==0));self.assertTrue(np.any(y))
    def test_repeat_seed_and_trace(self):
        z=random_coeff(32,5);args=(z,32,[0,2,4,6,8],2,p.METHODS[1])
        r=self.phase(*args);s=self.phase(*args)
        for i in range(4):np.testing.assert_array_equal(r[i],s[i])
        t=self.phase(*args,seed=9);self.assertTrue(np.any(t[0]!=r[0]));np.testing.assert_array_equal(t[1],r[1])
    def test_invalid_and_no_partial_output(self):
        z=random_coeff(32,4)
        for centers,alpha,method in (([0,1,1,3],2,p.METHODS[1]),([1,2,3,4],2,p.METHODS[1]),([0,1,2,3],.5,p.METHODS[1]),([0,1,2,3],2,'auto')):
            with self.assertRaises(ValueError):self.phase(z,32,centers,alpha,method)
        for val in (np.nan,np.inf):
            broken=z.copy();broken[3]=val
            with self.assertRaises(ValueError):self.phase(broken,32,[0,1,2,3],2,p.METHODS[1])
        broken=z.copy();broken[3]+=1
        with self.assertRaises(ValueError):self.phase(broken,32,[0,1,2,3],2,p.METHODS[1])
        with self.assertRaises(ValueError):self.phase(z,32,[0,1,2,3],2,p.METHODS[1],budget=1)
        with self.assertRaises(ValueError):p.Phase(self.path,'0'*64)

class Calibration(unittest.TestCase):
    def test_schedule_clocks_and_coverage(self):
        for alpha,name in itertools.product(p.ALPHAS,p.SCHEDULES):
            a,w=p.schedule(22050,alpha,name);self.assertEqual(a[0],0);self.assertEqual(a[-1],22049)
            self.assertTrue(all(v>u for u,v in zip(a,a[1:])))
            d=np.zeros(22050*alpha)
            for center,win in zip(a,w):
                ix=alpha*center+np.arange(len(win))-len(win)//2;good=(ix>=0)&(ix<len(d));d[ix[good]]+=win[good]**2
            self.assertGreater(d.min(),1e-8);self.assertLess(d.max()/d.min(),1e6)
    def test_frequency_and_event_faults(self):
        for f in (61,1000):
            t=np.arange(22050)/22050;v=.2*np.sin(2*np.pi*f*t)
            self.assertLess(abs(p.metrics.tone_error(v,22050,f)),.1)
            self.assertGreater(abs(p.metrics.tone_error(.2*np.sin(2*np.pi*f*2**(50/1200)*t),22050,f)),49)
        truth,meta=p.fixture('impulse');center=meta['center'];late=np.roll(truth,220)
        m=p.event_diagnostics(late,truth,center);self.assertAlmostEqual(m['centroid_vs_oracle_ms'],220/22050*1000)
        z=p.event_diagnostics(np.zeros_like(truth),truth,center);self.assertIsNone(z['centroid_vs_oracle_ms'])
        x,meta=p.fixture('tone61')
        with self.assertRaises(ValueError):p.measure(x,np.zeros_like(x),meta,1)
    def test_full_grid_not_success_subset(self):
        rows=[dict(zip(('family','alpha','schedule','method','repeat'),key),status='failed',errors=['injected'])
            for key in itertools.product(p.FAMILIES,p.ALPHAS,p.SCHEDULES,p.METHODS,range(3))]
        self.assertEqual(len(rows),288);result=p.assess(rows);self.assertFalse(result['integrity_pass']);self.assertIsNone(result['profiles'])
        for bad in (rows[:-1],rows+[rows[0]],[]):
            with self.assertRaises(ValueError):p.assess(bad)
    def test_complete_status_without_evidence_is_blocked(self):
        rows=[dict(zip(('family','alpha','schedule','method','repeat'),key),status='complete',errors=[])
            for key in itertools.product(p.FAMILIES,p.ALPHAS,p.SCHEDULES,p.METHODS,range(3))]
        result=p.assess(rows);self.assertFalse(result['integrity_pass']);self.assertIsNone(result['profiles'])
        self.assertEqual(result['decision'],'blocked_malformed_receipt')
    def test_spectral_oracle_scale(self):
        x,meta=p.fixture('impulse1000');self.assertEqual(p.spectral_error(x,x,meta['center'])['full'],0)
        self.assertAlmostEqual(p.spectral_error(2*x,x,meta['center'])['full'],1,places=12)
        changed=x.copy();changed[3]+=.1;self.assertNotEqual(p.digest(x,'<f4'),p.digest(changed,'<f4'))

if __name__=='__main__':unittest.main()
