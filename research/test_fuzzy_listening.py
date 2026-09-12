"""Pack fingerprinting, blind metadata and the actual JavaScript -> vote decoder."""
import csv,json,shutil,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import make_fuzzy_listening as m
import test_fuzzy_corpus as fixture
import score_blind_votes as votes

class ListeningTests(unittest.TestCase):
    save=fixture.FuzzyCorpusTests.save
    def setUp(self):
        fixture.FuzzyCorpusTests.setUp(self)
        (self.refs/'A.wav').rename(self.refs/'SecretFixture.wav');self.scores[0]['ref_name']='SecretFixture.wav';self.save()
        sources,processed,cells=m.e.plan(self.refs,self.tests,self.catalog)
        self.evaluation=self.root/'evaluation';self.evaluation.mkdir();rows=[]
        for c in cells:
            folder=self.evaluation/'renders'/c['condition_id'];folder.mkdir(parents=True)
            pairs=[(p,'harmonic') for p in m.e.PROFILES]
            if c['family']=='derived':pairs.append((m.e.BASELINE,'not_applicable'))
            for p,f in pairs:
                path=folder/(p+'_'+f+'.wav');fixture.sf.write(path,self.x,48000,subtype='FLOAT')
                rows.append(dict(**c,profile=p,formant=f,env=.5,onset=.8,rms=.1,peak=.2,duration_error_frames=0,
                    peak_channel=0,peak_time_seconds=0.,samples_above_unity=0,render_path=path.relative_to(self.evaluation).as_posix(),render_sha256=m.e.fingerprint(path)))
        with (self.evaluation/'metrics.csv').open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        summary=dict(schema=m.e.SCHEMA,mos_transfer=False,complete=True,formants=['harmonic'],sources=sources,cells=cells,
            metrics_sha256=m.e.fingerprint(self.evaluation/'metrics.csv'),**m.e.summarize(rows,cells,['harmonic']))
        (self.evaluation/'summary.json').write_text(json.dumps(summary))
    def make(self,kind='candidate',name='pack'):
        p=self.root/name;r=m.make_pack(self.evaluation,self.refs,p,kind,1);return p,r
    def test_separation_and_reproducibility(self):
        a,r=self.make();b,_=self.make(name='other')
        self.assertEqual(r['trials'],6)
        self.assertEqual((a/'analyst/answer_key.csv').read_bytes(),(b/'analyst/answer_key.csv').read_bytes())
        for p in (a/'listener').iterdir():
            if p.is_file():
                for secret in ['SecretFixture','fuzzy','multires','transient','derived_elastique','answer_key']:
                    self.assertNotIn(secret,p.read_text())
        for relative,digest in r['listener_sha256'].items():self.assertEqual(m.e.fingerprint(a/'listener'/relative),digest)
    def test_derived_pack_only_available_ratios(self):
        a,r=self.make('derived');self.assertEqual(r['trials'],1)
        self.assertIn(m.e.BASELINE,r['profiles'])
    def test_blank_template_is_not_listening_evidence(self):
        a,_=self.make();_,r=votes.decode(a/'analyst/answer_key.csv',[('L1',a/'listener/votes.csv')])
        self.assertTrue(r['identity_verified']);self.assertEqual(r['submitted_votes'],0)
    def test_audio_hash_and_output_replacement_refused(self):
        a,_=self.make()
        with self.assertRaises(ValueError):self.make()
        next((self.evaluation/'renders').rglob('*.wav')).write_bytes(b'tampered')
        with self.assertRaises(ValueError):self.make(name='bad')
        self.assertFalse((self.root/'bad').exists())
    @unittest.skipUnless(shutil.which('node'),'Node needed for actual export')
    def test_javascript_export_decodes_against_key(self):
        a,r=self.make();script=(a/'listener/index.html').read_text().split('<script>')[1].split('</script>')[0]
        prefix="""let csv='';const controls={export:{},status:{}};
global.document={addEventListener(){},getElementById:id=>controls[id],querySelector:()=>({value:'A'}),createElement:()=>({click(){}})};
global.Blob=class{constructor(parts){csv=parts.join('')}};global.URL={createObjectURL:()=>'',revokeObjectURL(){}};global.setTimeout=()=>{};
"""
        js=self.root/'test.js';js.write_text(prefix+script+"\ndocument.getElementById('export').onclick();process.stdout.write(csv);\n")
        response=subprocess.run(['node',str(js)],capture_output=True,text=True,check=True)
        ballot=self.root/'export.csv';ballot.write_text(response.stdout)
        _,result=votes.decode(a/'analyst/answer_key.csv',[('L1',ballot)],require_complete=True)
        self.assertEqual(result['submitted_votes'],18)
        self.assertEqual(result['pack_id'],r['pack_id'])

if __name__=='__main__':unittest.main()
