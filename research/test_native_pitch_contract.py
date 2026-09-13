"""Contract tests use synthetic receipts; they are NOT native zplane evidence."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_pitch_contract as n

class ContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.suite=self.root/'suite'
        with patch.object(n,'NAMES',('harmonics',)),patch.object(n,'RATES',(48000,)),patch.object(n,'SHIFTS',(0,)):
            self.manifest=n.prepare(self.suite)
        self.receipt=json.loads((self.suite/'receipt-template.json').read_text())
        self.path=self.root/'receipt.json'
    def valid_fixture(self):
        r=self.receipt
        r.update(host_version='synthetic contract fixture',engine_name='NOT A NATIVE RENDER',engine_version='fixture',engine_mode='fixture',host_executable_sha256='a'*64,engine_formant_settings={'off':'fixture off','harmonic':'fixture preserve'})
        for row,request in zip(r['records'],self.manifest['requests']):
            target=self.suite/row['output'];target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((self.suite/request['source']).read_bytes());row['output_sha256']=n.digest(target)
    def run_score(self):
        self.path.write_text(json.dumps(self.receipt));return n.score(self.suite,self.path,self.suite)
    def test_blank_template_not_a_measurement(self):
        with self.assertRaisesRegex(ValueError,'missing native'):self.run_score()
    def test_calibrated_identity_receipt(self):
        self.valid_fixture();r=self.run_score()
        self.assertEqual(len(r['rows']),1);self.assertLess(r['rows'][0]['partial_envelope_error_db'],1e-8)
        self.assertEqual(r['listening_status'],'not_listened');self.assertIn('declared_external_receipt',r['provenance_status'])
    def test_derived_pipeline_not_relabeled_native(self):
        self.valid_fixture();self.receipt['pipeline']='TSM+resampling'
        with self.assertRaisesRegex(ValueError,'pipeline'):self.run_score()
    def test_duplicate_or_missing_cell(self):
        self.valid_fixture();original=copy.deepcopy(self.receipt['records'])
        for rows in ([],original+original):
            self.receipt['records']=rows
            with self.assertRaises(ValueError):self.run_score()
    def test_wrong_identity(self):
        self.valid_fixture();self.receipt['pack_id']='b'*64
        with self.assertRaisesRegex(ValueError,'identity'):self.run_score()
    def test_settings_mismatch(self):
        self.valid_fixture();self.receipt['records'][0]['pitch_ratio']=1.5
        with self.assertRaisesRegex(ValueError,'settings'):self.run_score()
    def test_tampered_audio(self):
        self.valid_fixture();path=self.suite/self.receipt['records'][0]['output'];path.write_bytes(path.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'hash'):self.run_score()
    def test_wrong_length_even_with_updated_hash(self):
        self.valid_fixture();r=self.receipt['records'][0];path=self.suite/r['output'];sf.write(path,np.ones(100),48000,subtype='FLOAT');r['output_sha256']=n.digest(path)
        with self.assertRaisesRegex(ValueError,'length'):self.run_score()
    def test_external_paths_and_links_rejected(self):
        out=self.root/'outside.wav';out.write_bytes(b'no');(self.suite/'escape.wav').symlink_to(out)
        for path in ('../outside.wav',str(out),'escape.wav'):
            with self.assertRaises(ValueError):n.inside(self.suite,path)
    def test_existing_suite_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'exists'):n.prepare(self.suite)

if __name__=='__main__':unittest.main()
