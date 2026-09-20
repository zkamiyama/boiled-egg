import copy
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
import nsdgt_foundation as n
import comparison_contract as c

class Foundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(os.environ['BE_NSG_LIBRARY']).resolve(strict=True)
        cls.native=n.Native(cls.path,c.fingerprint(cls.path))
    def small(self):
        centers=[0,4,8,12,16];windows=[np.linspace(-.2,.8,7+(i%2)) for i in range(5)]
        return n.pack(17,16,centers,windows)
    def test_fixed_grid_and_coverage(self):
        self.assertEqual(len(n.grid()),288);self.assertEqual(len(set(n.grid())),288)
        for rate,length,_,sched in n.grid()[::8]:
            m={22050:1024,48000:2048,96000:4096}[rate]
            centers,windows=n.schedule(length,m,sched);shape=n.pack(length,m,centers,windows)
            _,_,d,_=n.reference(n.source(length,rate,'dc'),shape)
            self.assertGreater(d.min(),1e-8);self.assertLessEqual(d.max()/d.min(),1e6)
    def test_direct_dft_reference(self):
        shape=self.small();x=n.source(17,48000,'noise');z,_,_=self.native.call(True,x,shape)
        direct=[]
        cfg,frames,win=shape
        for f in frames:
            for k in range(cfg.fft_size):
                v=0j
                for r in range(f.window_length):
                    t=r-f.window_length//2;l=f.center+t
                    if 0<=l<len(x):v+=complex(x[l])*win[f.window_offset+r]*np.exp(-2j*np.pi*k*t/cfg.fft_size)
                direct.append(v)
        self.assertLess(float(np.max(np.abs(z-direct))),3e-6)
        if os.environ.get('NSG_EVIDENCE'):
            folder=Path(os.environ['NSG_EVIDENCE']);folder.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(folder/'direct-dft.npz',input=x,coefficients=z,direct=np.array(direct),windows=win,centers=np.array([f.center for f in frames]))
    def test_erasure_and_scale_no_hidden_original(self):
        shape=self.small();x=n.source(17,48000,'noise');z,_,_=self.native.call(True,x,shape)
        y,_,_=self.native.call(False,np.zeros_like(z),shape);self.assertTrue(np.all(y==0))
        y,_,_=self.native.call(False,z*.25,shape);self.assertLess(np.max(np.abs(y-.25*x)),3e-6)
        self.assertGreater(np.max(np.abs(y-x)),.01)
    def test_projection_and_symmetry(self):
        shape=self.small();z=n.source(80,48000,'noise')
        y,_,_=self.native.call(False,z,shape);p,_,_=self.native.call(True,y,shape)
        yy,_,_=self.native.call(False,p,shape);pp,_,_=self.native.call(True,yy,shape)
        self.assertLess(np.max(np.abs(p-pp)),3e-6);self.assertGreater(np.max(np.abs(p-z)),.01)
        x=n.source(17,48000,'tone61');z,_,_=self.native.call(True,x,shape)
        for frame in z.reshape(-1,16):self.assertLess(np.max(np.abs(frame-np.conj(frame[np.mod(-np.arange(16),16)]))),3e-6)
    def test_invalid_shape_window_hash(self):
        with self.assertRaises(ValueError):n.Native(self.path,'0'*64)
        for centers,windows in [([0,0],[np.ones(3)]*2),([-1],[np.ones(3)]),([0],[np.ones(33)]),([0],[np.array([0,np.nan,1])]),([0],[np.ones(3)*2])]:
            with self.assertRaises(ValueError):n.pack(17,32,centers,windows)
        with self.assertRaises(ValueError):n.pack(17,33,[0],[np.ones(3)])
        with self.assertRaises(ValueError):self.native.call(True,np.zeros(18),self.small())
        with self.assertRaises(ValueError):self.native.call(True,np.full(17,np.inf),self.small())
    def test_hole_conditioning_budget(self):
        x=np.ones(17,dtype=np.complex64)*.1
        for shape,code in [(n.pack(17,16,[8],[np.ones(3)]),4),(n.pack(17,32,[8],[np.ones(19)*1e-6]),5),(n.pack(17,32,[8],[np.ones(19)],budget=1),3)]:
            with self.assertRaises(n.NativeError) as e:self.native.call(True,x,shape)
            self.assertEqual(e.exception.code,code)
    def test_zero_distinct_from_nonzero_failure(self):
        shape=self.small();x=np.zeros(17,dtype=np.complex64)
        z,_,_=self.native.call(True,x,shape);y,_,_=self.native.call(False,z,shape)
        self.assertTrue(n.diagnostics(x,z,y,shape,n.reference(x,shape))['zero'])
        bad=np.ones(17,dtype=np.complex64)*.1
        with self.assertRaises(ValueError):n.diagnostics(bad,z,y,shape,n.reference(bad,shape))
    def test_numerical_fault_detection(self):
        shape=self.small();x=n.source(17,48000,'noise');ref=n.reference(x,shape)
        z,_,_=self.native.call(True,x,shape);y,_,_=self.native.call(False,z,shape)
        self.assertLess(n.diagnostics(x,z,y,shape,ref)['peak_relative_error'],3e-6)
        with self.assertRaises(ValueError):n.diagnostics(x,z,y*1.01,shape,ref)
        with self.assertRaises(ValueError):n.diagnostics(x,z*np.exp(.1j),y,shape,ref)
    def test_failed_grid_and_numeric_forgery(self):
        rows=[dict(index=i,repeat=r,status='failed') for i,r in itertools.product(range(288),range(3))]
        self.assertFalse(n.assess(rows)['passed'])
        for wrong in ([],rows[:-1],rows+[rows[0]]):
            with self.assertRaises(ValueError):n.assess(wrong)
        for row in rows:row.update(status='complete',output_sha256='a'*64,coeff_sha256='b'*64,metrics={})
        self.assertFalse(n.assess(rows)['passed'])
        for row in rows:row['metrics']={k:0. for k in ('peak_relative_error','l2_relative_error','coefficient_error','reference_synthesis_error','energy_error')}
        self.assertTrue(n.assess(rows)['passed'])
        rows[1]['metrics']['energy_error']=float('nan');self.assertFalse(n.assess(rows)['passed'])
    def test_repeat_and_independent_instance(self):
        shape=self.small();x=n.source(17,48000,'noise')
        a,_,_=self.native.call(True,x,shape);b,_,_=n.Native(self.path,c.fingerprint(self.path)).call(True,x,shape)
        np.testing.assert_array_equal(a,b)
    def test_failure_receipt_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);plan=root/'plan.json';plan.write_text('{}');out=root/'out'
            result=n.run(plan,'0'*64,out);self.assertFalse(result['passed']);self.assertIsNone(result['quality_selection'])
            first=c.fingerprint(out/'summary.json')
            with self.assertRaises(FileExistsError):n.run(plan,'0'*64,out)
            self.assertEqual(first,c.fingerprint(out/'summary.json'))

if __name__=='__main__':unittest.main()
