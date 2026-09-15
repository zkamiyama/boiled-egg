import csv,hashlib,json,tempfile,unittest
from pathlib import Path
import audit_results as a

class AuditTests(unittest.TestCase):
    def test_pairs_and_losses_not_dropped(self):
        rows=[dict(source=str(i//3),rate=48000,ratio=float(i%3+1),seed=0,mode=m,score=float(i)+(1 if m=='new' else 0)) for i in range(6) for m in ('new','old')]
        s=a.paired(rows,'new','old','score');self.assertEqual(s['delta'],1.)
        self.assertEqual(s['losses'],6);self.assertEqual(s['ci95'],[1.,1.])
        with self.assertRaises(ValueError):a.paired(rows[:-1],'new','old','score')
    def test_complete_grid_and_hash_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'case';root.mkdir();journal=Path(tmp)/'case-journal';journal.mkdir()
            manifest=dict(suite='synthetic',jobs=[['synthetic','bank',48000,1.,0,None,'heap','events']],code={},sources={})
            identity=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
            (journal/'manifest.json').write_text(json.dumps(manifest))
            rows=[dict(source='bank',rate=48000,ratio=1.,seed=0,mode=m,score=0.) for m in a.MODES]
            def write(records):
                with (root/'measurements.csv').open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(records)
                (root/'summary.json').write_text(json.dumps(dict(suite='synthetic',rows=len(records),identity=identity,measurements_sha256=a.sha(root/'measurements.csv'))))
                (journal/'0000.json').write_text(json.dumps(dict(identity=identity,index=0,rows=records,sha256=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest())))
            write(rows);self.assertEqual(len(a.verify(root)[0]),7)
            write(rows[:-1])
            with self.assertRaisesRegex(ValueError,'grid'):a.verify(root)
            write(rows+rows[:1])
            with self.assertRaisesRegex(ValueError,'grid'):a.verify(root)
            write(rows);(root/'measurements.csv').write_text('corrupt')
            with self.assertRaisesRegex(ValueError,'hash'):a.verify(root)
if __name__=='__main__':unittest.main()
