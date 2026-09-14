import copy
import unittest
from analyze import validate_row, miss_episodes, describe

class AuditCalibration(unittest.TestCase):
    def setUp(self):
        self.meta=dict(bracket='cpu',schedule='periodic',warmup=2,rate=96000,block=32)
        self.row=dict(index=0,cold=1,cpu_ns=50000,wall_ns=-1,outer_ns=52000,period_ns=333333,
            wake_late_ns=300000,response_ns=352000,slack_ns=-18667,release_miss=1,status=0)
    def test_small_cpu_does_not_hide_late_release(self):
        validate_row(self.row,0,self.meta)
        self.assertLess(self.row['cpu_ns'],self.row['period_ns'])
        self.assertEqual(self.row['release_miss'],1)
    def test_tampered_deadline_or_missing_measurement(self):
        for k,v in [('cpu_ns',-1),('wall_ns',0),('period_ns',333334),('response_ns',1),
                    ('cold',0),('release_miss',0),('status',1),('index',8)]:
            row=dict(self.row);row[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):validate_row(row,0,self.meta)
    def test_saturated_cannot_claim_periodic_results(self):
        meta=dict(self.meta,schedule='saturated')
        with self.assertRaises(ValueError):validate_row(self.row,0,meta)
        row=dict(self.row,wake_late_ns=-1,response_ns=-1,slack_ns=0,release_miss=0)
        validate_row(row,0,meta)
    def test_nearest_rank_retains_worst_sample(self):
        result=describe([1]*999+[10**9]);self.assertEqual(result['max_ns'],10**9)
        self.assertEqual(result['p99_ns'],1)
    def test_correlated_misses_report_episodes(self):
        self.assertEqual(miss_episodes([True,True,False,True]),dict(count=3,episodes=2,longest_run=2))
    def test_fractional_sample_period_is_not_constant_floor(self):
        meta=dict(self.meta,warmup=0)
        row=dict(self.row,index=2,cold=0,period_ns=333334,slack_ns=-18666)
        validate_row(row,2,meta)


# Synthetic receipt fixtures validate parsing, not performance.
class ReceiptIntegrity(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.cell=dict(name='fixture',label='fixture',repeat=1,rate=96000,block=32,shift=7,
            workload='dsp',schedule='periodic',bracket='cpu')
        self.meta=dict(self.cell,schema='boiled-egg.rt-audit.v1',count=1,warmup=1500,
            requested_warmup=0,latency_frames=0,errors=0,output_fingerprint='1')
        self.write()
    def write(self):
        import csv,json
        from analyze import FIELDS
        with (self.root/'fixture.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
            for i in range(1501):
                period=(i+1)*32*10**9//96000-i*32*10**9//96000
                writer.writerow(dict(index=i,cold=int(i<1500),cpu_ns=50,wall_ns=-1,outer_ns=52,
                    period_ns=period,wake_late_ns=0,response_ns=52,slack_ns=period-52,
                    release_miss=0,status=0,output_hash='1'))
        (self.root/'fixture.json').write_text(json.dumps(self.meta));self.sign()
    def sign(self):
        import json
        from analyze import digest
        (self.root/'fixture.receipt.json').write_text(json.dumps(dict(returncode=0,
            csv_sha256=digest(self.root/'fixture.csv'),metadata_sha256=digest(self.root/'fixture.json'))))
    def test_round_trip(self):
        from analyze import load_run
        result,code=load_run(self.root,self.cell,1)
        self.assertEqual(result['steady']['cpu_ns']['max_ns'],50)
        self.assertEqual(result['cold']['cpu_ns']['samples'],1500)
        self.assertEqual(len(code),64)
    def test_tampered_file(self):
        from analyze import load_run
        p=self.root/'fixture.csv';p.write_text(p.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'tampered'):load_run(self.root,self.cell,1)
    def test_truncated_signed_file(self):
        from analyze import load_run
        p=self.root/'fixture.csv';p.write_text('\n'.join(p.read_text().splitlines()[:-1])+'\n');self.sign()
        with self.assertRaisesRegex(ValueError,'incomplete'):load_run(self.root,self.cell,1)
    def test_wrong_configuration(self):
        from analyze import load_run
        with self.assertRaisesRegex(ValueError,'config'):load_run(self.root,dict(self.cell,rate=48000),1)

if __name__=='__main__':unittest.main()
