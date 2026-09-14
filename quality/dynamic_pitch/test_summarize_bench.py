"""Simulated timing rows calibrate the gate; these are not performance evidence."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import summarize_bench as summary

class CapacitySummaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.paths=[Path(self.tmp.name)/f'repeat-{r}.csv' for r in (1,2,3)]
        self.rows={r:[dict(repeat=r,rate=96000,quality=1,policy=1,block=32,index=i,
                          warmup=int(i<2),wall_ns=100000,fingerprint=i) for i in range(1202)] for r in (1,2,3)}
        self.grid=patch.object(summary,'GRID',{(96000,1,1,32)})
        self.grid.start();self.addCleanup(self.grid.stop)
    def write(self):
        for r,path in enumerate(self.paths,1):
            with path.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['repeat',*summary.KEYS,'index','warmup','wall_ns','fingerprint'])
                writer.writeheader();writer.writerows(self.rows[r])
    def result(self):self.write();return summary.summarize(self.paths)
    def test_capacity_success_does_not_hide_one_raw_miss(self):
        self.rows[1][100]['wall_ns']=1000000
        row=self.result()['rows'][0]
        self.assertTrue(row['capacity_pass']);self.assertEqual(row['raw_deadline_misses'],1)
        self.assertEqual(row['full_successful_runs'],2);self.assertGreater(row['raw_max_ratio'],1)
    def test_same_heavy_state_fails_all_replicas(self):
        for r in (1,2,3):self.rows[r][100]['wall_ns']=300000
        result=self.result();self.assertFalse(result['passed'])
        self.assertAlmostEqual(result['rows'][0]['state_best_worst_ratio'],.9)
    def test_changed_fingerprint_cannot_match_different_work(self):
        self.rows[2][100]['fingerprint']+=1
        with self.assertRaisesRegex(ValueError,'different processing'):self.result()
    def test_warmup_cannot_be_moved_to_hide_an_outlier(self):
        self.rows[1][0]['warmup']=0;self.rows[1][100]['warmup']=1
        with self.assertRaisesRegex(ValueError,'contiguous prefix'):self.result()
    def test_no_warmup_or_missing_state_rejected(self):
        self.rows[1]=self.rows[1][2:]
        for i,row in enumerate(self.rows[1]):row['index']=i
        with self.assertRaisesRegex(ValueError,'nonempty'):self.result()
    def test_duplicate_repeat_and_extra_configuration_rejected(self):
        self.write()
        with self.assertRaisesRegex(ValueError,'duplicate'):summary.summarize([self.paths[0]]*3)
        self.rows[1][100]['block']=33
        with self.assertRaisesRegex(ValueError,'invalid measurement'):self.result()

if __name__=='__main__':unittest.main()
