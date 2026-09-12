"""Exact vs measured-ratio accounting, provenance and actual renderer integration."""
import argparse,copy,csv,json,os,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_fuzzy_corpus as e

class FuzzyCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.refs=self.root/'refs';self.tests=self.root/'tests'
        self.refs.mkdir();self.tests.mkdir();self.catalog=self.root/'scores.csv'
        self.x=(.2*np.sin(2*np.pi*440*np.arange(6000)/48000)).astype('float32')
        sf.write(self.refs/'A.wav',self.x,48000,subtype='FLOAT')
        sf.write(self.tests/'A_Elastique_75_per.wav',self.x[:4500],48000,subtype='FLOAT')
        self.scores=[dict(test_name='A_Elastique_75_per.wav',ref_name='A.wav',ref_loc='Source/Voice/',method='Elastique',TSM='75',MeanOS='4')]
        self.save()
    def save(self):
        with self.catalog.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(self.scores[0]));w.writeheader();w.writerows(self.scores)
    def plan(self):return e.plan(self.refs,self.tests,self.catalog)
    def rows(self):
        _,_,cells=self.plan();rows=[]
        for c in cells:
            pairs=[(p,f) for f in e.FORMANTS for p in e.PROFILES]
            if c['family']=='derived':pairs.append((e.BASELINE,'not_applicable'))
            for p,f in pairs:rows.append(dict(**c,profile=p,formant=f,env=.5,onset=.7,rms=.2,peak=.3,duration_error_frames=0))
        return cells,rows
    def test_distinct_exact_and_measured_grids(self):
        sources,processed,cells=self.plan()
        self.assertEqual((len(sources),len(processed),len(cells)),(1,1,7))
        d=next(c for c in cells if c['family']=='derived')
        self.assertEqual(d['measured_ratio'],.75);self.assertEqual(d['category'],'voice')
        self.assertNotIn(d['pitch_semitones'],e.PITCHES)
    def test_stress_not_target(self):
        sf.write(self.tests/self.scores[0]['test_name'],np.tile(self.x,3),48000,subtype='FLOAT')
        self.assertEqual(self.plan()[2][-1]['scope'],'stress')
    def test_unknown_test_and_missing_reference(self):
        sf.write(self.tests/'wrong.wav',self.x,48000,subtype='FLOAT')
        with self.assertRaises(ValueError):self.plan()
        (self.tests/'wrong.wav').unlink();self.scores[0]['ref_name']='Missing.wav';self.save()
        with self.assertRaises(ValueError):self.plan()
    def test_wrong_rate_and_nonfinite_rejected(self):
        for x,rate in [(self.x,44100),(self.x*np.nan,48000)]:
            sf.write(self.tests/self.scores[0]['test_name'],x,rate,subtype='FLOAT')
            with self.assertRaises(ValueError):self.plan()
    def test_no_external_pair_rejected(self):
        self.scores[0]['method']='FuzzyTSM';self.save()
        with self.assertRaises(ValueError):self.plan()
    def test_external_baseline_not_duplicated_across_formants(self):
        cells,rows=self.rows();r=e.summarize(rows,cells,list(e.FORMANTS))
        self.assertEqual(r['dsp_renders'],105);self.assertEqual(r['derived_renders'],1)
        self.assertEqual(r['measurements'],106)
    def test_missing_duplicate_and_unexpected_rows(self):
        cells,rows=self.rows()
        for r in [rows[:-1],rows+rows[:1],[dict(rows[0],profile='fake')]+rows[1:]]:
            with self.assertRaises(ValueError):e.validate(r,cells,list(e.FORMANTS))
    def test_cell_metadata_nonfinite_duration_rejected(self):
        cells,rows=self.rows()
        for field,value in [('reference_sha256','wrong'),('control_ratio',1.234),('env',float('nan')),('duration_error_frames',1)]:
            changed=copy.deepcopy(rows);changed[0][field]=value
            with self.assertRaises(ValueError):e.validate(changed,cells,list(e.FORMANTS))
    def test_explicit_modes_not_profile_defaults(self):
        for p in e.PROFILES:
            cmd=e.command(Path('/pv'),Path('/multi'),Path('in'),Path('out'),p,'harmonic',.5,64)
            if p.startswith('fuzzy'):self.assertEqual(cmd[cmd.index('--mode')+1],p)
            if p=='multires':self.assertEqual(cmd[0],'/multi')
        with self.assertRaises(ValueError):e.command(Path('x'),Path('x'),Path('x'),Path('y'),'auto','off',1,64)
    @unittest.skipUnless(os.getenv('BOILED_EGG_PV_CLI') and os.getenv('BOILED_EGG_MULTIRES_CLI'),'real CLI paths required')
    def test_actual_full_grid_atomic_publication(self):
        a=argparse.Namespace(ref_dir=self.refs,test_dir=self.tests,catalog=self.catalog,
            pv_cli=Path(os.environ['BOILED_EGG_PV_CLI']),multires_cli=Path(os.environ['BOILED_EGG_MULTIRES_CLI']),
            source_commit='a'*40,block=64,workers=2,formants=list(e.FORMANTS),output=self.root/'result')
        r=e.run(a);self.assertEqual(r['exact_duration_renders'],106)
        self.assertEqual(r['listening_status'],'not_listened');self.assertFalse(r['mos_transfer'])
        self.assertEqual(len(list((a.output/'renders').rglob('*.wav'))),106)
        with self.assertRaises(ValueError):e.run(a)

if __name__=='__main__':unittest.main()
