import copy,itertools,unittest
import cost
class CostControls(unittest.TestCase):
    def fixture(self):
        rows=[]
        for i,c in enumerate(cost.grid()):
            for j,role in itertools.product(range(3),('baseline','candidate')):
                m=dict(input_frames=96000,output_frames=96000,input_blocks=3000,api_calls=3000,pulls=0,underruns=0,latency=1664,tail=1664,native_seconds=.03,wall_seconds=.04,warm_create_seconds=.001,window=1024)
                t=dict(mean=.00001,p99=.00002,max=.00003,over80=0,over100=0)
                rows.append(dict(case=i,repeat=j,role=role,status='complete',measurement=m,pcm_sha256='1'*64,calls=dict(t),services=dict(t)))
        return rows
    def test_grid(self):
        rows=cost.grid();self.assertEqual(len(rows),48);self.assertEqual(sum(r['mode']=='stream' for r in rows),32)
        self.assertEqual(len({tuple(sorted(r.items())) for r in rows}),48)
    def test_missing_duplicate(self):
        r=self.fixture()
        for rr in ([],r[:-1],r+[r[0]]):
            with self.assertRaises(ValueError):cost.assess(rr)
    def test_failed_execution(self):
        r=self.fixture();r[0]['status']='failed';self.assertFalse(cost.assess(r)['integrity'])
    def test_identity(self):
        s=cost.assess(self.fixture());self.assertTrue(s['integrity']);self.assertEqual(s['pcm_pairs'],144)
        self.assertFalse(s['hard_rt_qualified']);self.assertEqual(s['groups']['stream']['native_ratio_median'],1)
    def test_changed_pcm(self):
        r=self.fixture();r[1]['pcm_sha256']='2'*64
        with self.assertRaisesRegex(ValueError,'PCM'):cost.assess(r)
    def test_changed_contract(self):
        for key in ('output_frames','api_calls','latency','underruns'):
            r=self.fixture();r[1]['measurement'][key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):cost.assess(r)
    def test_invalid_timing(self):
        for v in (0,float('nan'),float('inf')):
            r=self.fixture()
            for row in r:row['measurement']['native_seconds']=v
            with self.subTest(value=v),self.assertRaises(ValueError):cost.assess(r)
    def test_regression_is_not_integrity_failure(self):
        r=self.fixture()
        for row in r:
            if row['role']=='candidate':row['measurement']['native_seconds']*=1.3
        s=cost.assess(r);self.assertTrue(s['integrity']);self.assertEqual(s['groups']['stream']['cost_pass'],0)
        self.assertEqual(s['groups']['rt']['cost_pass'],0)
    def test_single_nonfinite_repeat_is_not_hidden_by_median(self):
        r=self.fixture();r[1]['measurement']['native_seconds']=float('nan')
        with self.assertRaises(ValueError):cost.assess(r)
    def test_maximum_rule_separate_from_mean(self):
        r=self.fixture()
        for row in r:
            row['services']['max']=1.0
        result=cost.assess(r)
        self.assertTrue(all(v['best_mean_within_80pct'] for v in result['rt_diagnostics']))
        self.assertTrue(all(not v['best_max_within_80pct'] for v in result['rt_diagnostics']))
if __name__=='__main__':unittest.main()
