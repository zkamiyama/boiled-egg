"""Integrity and routing tests, not fabricated benchmark/listening evidence."""
import csv,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import summarize_execution_bench as b
import check_execution_quality as q

class BenchTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.rows={};self.paths=[]
        for repeat in (1,2,3):
            rows=[]
            for key in sorted(b.expected('host')):
                rate,ch,block,shift,profile,variant=key;value=200 if variant=='scalar' else 100
                rows.append(dict(zip(b.KEYS,key),repeat=repeat,callbacks=1200,cpu_mean_us=value/2,
                    cpu_p99_us=value,cpu_max_us=value*20,wall_p99_us=value+1,wall_max_us=value*21,
                    cpu_p99_ratio=value/(1e6*block/rate),frame_overruns=0,underruns=0,
                    cpu_misses=1,wall_misses=2,latency_frames=2688))
            self.rows[repeat]=rows;self.paths.append(self.root/f'{repeat}.csv')
        self.save()
    def save(self):
        for repeat,path in enumerate(self.paths,1):
            with path.open('w',newline='') as s:
                w=csv.DictWriter(s,fieldnames=list(self.rows[repeat][0]));w.writeheader();w.writerows(self.rows[repeat])
    def test_complete_and_keep_misses(self):
        result=b.summarize(self.paths,'host');self.assertEqual(result['cells_per_repeat'],288)
        self.assertTrue(all(r['median_p99_reduction_pct']==50 for r in result['paired_improvements']))
        self.assertTrue(all(r['cpu_deadline_misses']==432 for r in result['raw_extremes']))
        self.assertTrue(all(r['largest_raw_cpu_max_ratio']>1 for r in result['raw_extremes']))
    def test_missing_cell(self):
        self.rows[2].pop();self.save()
        with self.assertRaisesRegex(ValueError,'incomplete'):b.summarize(self.paths,'host')
    def test_duplicate_cell(self):
        self.rows[2].append(self.rows[2][0]);self.save()
        with self.assertRaisesRegex(ValueError,'duplicate'):b.summarize(self.paths,'host')
    def test_duplicate_repeat(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):b.summarize([self.paths[0]]*3,'host')
    def test_nonfinite_and_wrong_ratio(self):
        for value in (float('nan'),123.0):
            self.rows[1][0]['cpu_p99_ratio']=value;self.save()
            with self.assertRaises(ValueError):b.summarize(self.paths,'host')
    def test_dsp_overrun_not_hidden(self):
        self.rows[3][0]['frame_overruns']=1;self.save()
        with self.assertRaisesRegex(ValueError,'underrun'):b.summarize(self.paths,'host')
    def test_quality_wrapper_really_routes_scheduled(self):
        output=self.root/'quality.json'
        def gate(build,path):
            cmd=q.q.e.command(build,Path('in.wav'),Path('out.wav'),'fuzzy','harmonic',.5,48000,'candidate')
            self.assertEqual(cmd[-4:],['--execution','scheduled','--simd','on'])
            return dict(rows=[],failed=[])
        original=q.q.e.command
        with patch.object(q.q,'run',side_effect=gate):result=q.run(self.root,output)
        self.assertIs(q.q.e.command,original);self.assertFalse(result['thresholds_changed'])
        self.assertEqual(json.loads(output.read_text())['execution'],'scheduled')

if __name__=='__main__':unittest.main()
