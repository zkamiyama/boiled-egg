import copy
import unittest
import compare as v


def rows(mode='cost'):
    result=[]
    for spec in v.specifications(mode):
        n=spec['rate']*2;block=spec['block'];count=(n+block-1)//block
        scale=.25*(.8 if spec['side']=='after' else 1)
        services=[scale*min(block,n-j*block)/spec['rate'] for j in range(count)]
        info=dict(rate=spec['rate'],channels=spec['channels'],io=spec['io'],detail=spec['detail'],repeat=spec['repeat'],
            frames=n,latency=0,tail=0,energy=1,peak=.1,proportional_error=0,
            input_blocks=count,services=services,service_seconds=sum(services),max_service_seconds=max(services),
            setup_seconds=.01,flush_seconds=0,service_period_exceedances=0)
        result.append(dict(spec,status='complete',info=info,pcm_sha256='a'*64,receipt_sha256='b'*64,metrics=dict(test=1)))
    return result

class ComparisonTests(unittest.TestCase):
    def test_complete_grid_and_fixed_cost(self):
        for mode,size in (('quality',192),('cost',384)):
            r=rows(mode);self.assertEqual(len(r),size);summary=v.assess(r,mode)
            self.assertTrue(summary['integrity_pass']);self.assertEqual(summary['pcm_pairs'],size//2)
            if mode=='cost':self.assertTrue(summary['cost_goal_pass']);self.assertAlmostEqual(summary['median_ratio'],.8)
    def test_missing_extra_duplicate_rejected(self):
        r=rows('quality')
        for rr in ([],r[:-1],r+[r[0]]):
            with self.assertRaises(ValueError):v.assess(rr,'quality')
    def test_failed_and_fake_complete_receipts(self):
        r=rows('quality');r[0]['status']='failed';self.assertFalse(v.assess(r,'quality')['integrity_pass'])
        r[0]['status']='complete';del r[0]['pcm_sha256'];self.assertFalse(v.assess(r,'quality')['integrity_pass'])
    def test_silent_nonfinite_and_stereo_not_success(self):
        for field,value in (('energy',0),('peak',float('nan')),('frames',1)):
            r=rows('quality');r[0]['info'][field]=value;self.assertFalse(v.assess(r,'quality')['integrity_pass'])
        r=rows();index=next(i for i,x in enumerate(r) if x['channels']==2)
        r[index]['info']['proportional_error']=.01;self.assertFalse(v.assess(r,'cost')['integrity_pass'])
    def test_wrong_timing_cannot_pass(self):
        for field,value in (('input_blocks',0),('service_seconds',.001),('max_service_seconds',0),('service_period_exceedances',1)):
            r=rows('quality');r[0]['info'][field]=value;self.assertFalse(v.assess(r,'quality')['integrity_pass'])
    def test_changed_pcm_or_metadata_blocked(self):
        r=rows('quality');r[1]['pcm_sha256']='c'*64;self.assertFalse(v.assess(r,'quality')['integrity_pass'])
        r=rows('quality');r[1]['info']['tail']=1;self.assertFalse(v.assess(r,'quality')['integrity_pass'])
    def test_slow_cost_is_not_integrity_failure_or_success(self):
        r=rows()
        for item in r:
            if item['side']=='after':
                info=item['info'];info['services']=[x*2 for x in info['services']]
                info['service_seconds']=sum(info['services']);info['max_service_seconds']=max(info['services'])
        summary=v.assess(r,'cost');self.assertTrue(summary['integrity_pass']);self.assertFalse(summary['cost_goal_pass'])
    def test_short_final_callback_uses_own_period(self):
        r=rows();item=next(x for x in r if x['io']==2)
        info=item['info'];n=info['frames']+1;info['latency']=1;info['frames']=n
        info['services'].append(2/item['rate']);info['input_blocks']+=1
        info['service_seconds']=sum(info['services']);info['max_service_seconds']=max(info['services'])
        # Duration below the nominal block period still misses the one-sample period.
        with self.assertRaisesRegex(ValueError,'exceedance'):v.validate_row(item)
        info['service_period_exceedances']=1;v.validate_row(item)

if __name__=='__main__':unittest.main()
