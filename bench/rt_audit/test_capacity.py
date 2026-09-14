"""Calibrate the practical acceptance statistic, not fabricated audio performance."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import capacity as c
import run_matrix


def rows(times):
    return [dict(index=i,wall_ns=v,period_ns=100,output_hash=f'{i:x}') for i,v in enumerate(times)]


class EnvelopeTests(unittest.TestCase):
    def test_per_state_minimum_is_not_a_fictitious_continuous_success(self):
        result, _ = c.replay_envelope([rows([40,200]),rows([200,40]),rows([200,200])],.8)
        self.assertTrue(result['every_state_observed_within_budget'])
        self.assertEqual(result['worst_state_best_ratio'],.4)
        self.assertEqual(result['actual_all_period_runs'],[])
        self.assertEqual(result['raw_period_exceedances'],4)
        self.assertEqual(result['states_by_success_count']['1'],2)
        self.assertEqual(result['worst_state_second_best_ratio'],2.)
    def test_one_heavy_state_cannot_hide_behind_an_easy_global_minimum(self):
        result,_=c.replay_envelope([rows([1,150]),rows([2,140]),rows([1,160])],.8)
        self.assertFalse(result['every_state_observed_within_budget'])
        self.assertEqual(result['worst_state_best_ratio'],1.4)
        self.assertEqual(result['states_by_success_count']['0'],1)
    def test_actual_success_and_margins_remain_separate(self):
        result,_=c.replay_envelope([rows([70,70]),rows([90,70]),rows([500,60])],.8)
        self.assertEqual(result['actual_all_budget_runs'],[1])
        self.assertEqual(result['actual_all_period_runs'],[1,2])
        self.assertEqual(result['raw_max_ratio'],5.)
        self.assertEqual(result['raw_budget_exceedances'],2)
        self.assertEqual(result['raw_period_exceedances'],1)
    def test_replay_count_and_history_are_not_optional(self):
        trial=rows([50,60])
        for bad in ([trial], [trial,trial,trial[:-1]], [[],[],[]]):
            with self.assertRaises(ValueError):c.replay_envelope(bad,.8)
        for field,value in (('index',9),('period_ns',110),('output_hash','deadbeef')):
            trials=[copy.deepcopy(trial) for _ in range(3)];trials[1][0][field]=value
            with self.assertRaisesRegex(ValueError,'history'):c.replay_envelope(trials,.8)
    def test_zero_or_invalid_clock_cannot_be_a_fast_success(self):
        for value in (0,-1,float('nan'),50.):
            with self.assertRaises(ValueError):c.replay_envelope([rows([value])]*3,.8)
        for value in (0,1.1,float('inf')):
            with self.assertRaises(ValueError):c.replay_envelope([rows([50])]*3,value)
    def test_fractional_period_and_budget_boundary(self):
        trials=[rows([80,81]) for _ in range(3)]
        result,_=c.replay_envelope(trials,.8)
        self.assertFalse(result['every_state_observed_within_budget'])
        self.assertEqual(result['states_by_success_count'],{'0':1,'1':0,'2':0,'3':1})
    def test_strict_predeclared_policy(self):
        self.assertEqual(c.validate_policy(c.DEFAULT_POLICY),c.DEFAULT_POLICY)
        for field,value in (('repeats',5),('repeats',True),('budget_fraction',0),
                            ('budget_fraction',float('nan')),('minimum_steady_calls',0),
                            ('maximum_relative_regression',.5)):
            bad=dict(c.DEFAULT_POLICY);bad[field]=value
            with self.assertRaises(ValueError):c.validate_policy(bad)
        with self.assertRaises(ValueError):c.validate_policy({**c.DEFAULT_POLICY,'ignore_outliers':True})


class CapacityPipelineTests(unittest.TestCase):
    def test_full_plan_receipts_capacity_and_mutation(self):
        """A mocked executable still exercises real runner, receipts and analyzer."""
        from analyze import FIELDS
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);probe=root/'fixture-probe';probe.write_text('fixture, not an executable')
            dependency=root/'fixture-lib';dependency.write_text('dependency')
            policy=root/'policy.json';policy.write_text(json.dumps({**c.DEFAULT_POLICY,'minimum_steady_calls':2}))
            from argparse import Namespace
            args=Namespace(output=root/'run',count=2,probe=[f'fixture={probe}'],matrix='capacity',
                           policy=policy,dependency=[dependency])
            def execute(cmd,stdout,stderr,**unused):
                rate,block,shift=map(int,cmd[-3:]);repeat=int(cmd[3])
                warmup=(rate//2+block-1)//block
                meta=dict(schema='boiled-egg.rt-audit.v1',repeat=repeat,rate=rate,block=block,shift=shift,
                    count=2,requested_warmup=200,warmup=warmup,latency_frames=0,pinned_cpu=0,policy=0,
                    workload='dsp',schedule='saturated',bracket='wall',errors=0,output_fingerprint='1')
                stderr.write(json.dumps(meta));stderr.flush()
                writer=csv.DictWriter(stdout,fieldnames=FIELDS);writer.writeheader()
                for i in range(warmup+2):
                    period=(i+1)*block*10**9//rate-i*block*10**9//rate
                    writer.writerow(dict(index=i,cold=int(i<warmup),cpu_ns=-1,wall_ns=50,outer_ns=70,
                        period_ns=period,wake_late_ns=-1,response_ns=-1,slack_ns=0,release_miss=0,status=0,output_hash='1'))
                stdout.flush()
                from subprocess import CompletedProcess
                return CompletedProcess(cmd,0)
            with patch.object(run_matrix.subprocess,'run',side_effect=execute), \
                 patch.object(run_matrix,'snapshot',return_value={'fixture':True}):
                run_matrix.run(args)
            result,envelopes=c.report(args.output)
            self.assertEqual(len(result['cells']),28)
            self.assertEqual(len(envelopes),56)
            self.assertTrue(result['labels'][0]['capacity_observed'])
            self.assertFalse(result['hard_realtime_qualified'])
            self.assertFalse(result['automatic_promotion'])
            self.assertEqual(result['labels'][0]['actual_runs'],84)
            first=next(args.output.glob('*.csv'));first.write_text(first.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'tampered'):c.report(args.output)
    def test_runner_refuses_inadequate_count_before_creating_output(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);probe=root/'probe';probe.write_text('x')
            args=Namespace(output=root/'out',count=1,probe=[f'x={probe}'],matrix='capacity',policy=None,dependency=[])
            with self.assertRaisesRegex(ValueError,'count below'):run_matrix.run(args)
            self.assertFalse(args.output.exists())

if __name__=='__main__': unittest.main()
