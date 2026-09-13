"""Deterministic diagnostic-accounting fixtures; not measured performance."""
import csv,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import summarize_rt_tail_probe as probe
class TailAccountingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.rows=[]
        for i in range(8):
            row={k:0 for k in probe.FIELDS};row.update(repeat=1,profile=2,rate=48000,block=480,pitch=1.,input='normal',instrument=1,index=i,cpu_ns=100000,wall_ns=120000)
            self.rows.append(row)
        self.rows[0]['cpu_ns']=20000000;self.rows[5]['cpu_ns']=30000000
    def save(self,name='run.csv'):
        path=self.root/name
        with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=probe.FIELDS);w.writeheader();w.writerows(self.rows)
        return path
    def test_cold_and_steady_misses_remain_separate(self):
        r=probe.analyze([self.save()],.02);cold,steady=r['summaries']
        self.assertEqual(cold['cpu_misses'],1);self.assertEqual(steady['cpu_misses'],1)
        self.assertEqual(steady['cpu_max_us'],30000);self.assertEqual(steady['wall_misses'],0)
    def test_duplicate_and_incomplete_indices_rejected(self):
        p=self.save()
        with self.assertRaises(ValueError):probe.analyze([p,p],.02)
        self.rows[4]['index']=7
        with self.assertRaises(ValueError):probe.analyze([self.save()],.02)
    def test_nonfinite_and_excessive_warmup_rejected(self):
        with self.assertRaises(ValueError):probe.analyze([self.save()],1)
        self.rows[1]['output_energy']=float('nan')
        with self.assertRaises(ValueError):probe.analyze([self.save()],.02)
    def test_repeat_index_overlap_is_not_guessed(self):
        paths=[]
        for n in (1,2,3):
            for r in self.rows:r['repeat']=n
            paths.append(self.save(f'{n}.csv'))
        r=probe.analyze(paths,.02)['repeat_overlap'][0]
        self.assertEqual(r['total_events'],3);self.assertEqual(r['shared_all_three'],1)
if __name__=='__main__':unittest.main()
