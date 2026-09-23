import unittest
from unittest.mock import patch
import experiment as e

class ExperimentTests(unittest.TestCase):
    def test_provenance_is_not_the_ring_experiment(self):
        with patch.object(e.replay,'identity') as check:
            with self.assertRaises(ValueError):e.check_plan({'experiment':'pv-ring-cost-v1'})
            check.assert_not_called()
            p={'experiment':e.EXPERIMENT,'protocol_commit':e.PROTOCOL}
            e.check_plan(p);check.assert_called_once_with(p)
        self.assertEqual(e.replay.BASE,e.BASE)

    def test_partial_or_failed_cost_cannot_qualify(self):
        for data in ({},{'mode':'quality','integrity_pass':True},{'mode':'cost','integrity_pass':False}):
            self.assertFalse(e.cost_decision(data)['qualified'])
        with self.assertRaises(ValueError):e.cost_decision({'mode':'cost','integrity_pass':True,'pairs':[]})

    def test_streaming_and_fixed_cost_are_separate(self):
        pairs=[dict(io=i,ratio=1.4 if i==1 else .9) for i in (1,2) for _ in range(32)]
        r=e.cost_decision(dict(mode='cost',integrity_pass=True,pairs=pairs,cost_goal_pass=False))
        self.assertTrue(r['qualified']);self.assertFalse(r['original_pooled_gate'])
        self.assertFalse(r['streaming_control']['goal_pass']);self.assertFalse(r['hard_realtime_qualified'])
        pairs[-1]['ratio']=1.3
        self.assertFalse(e.cost_decision(dict(mode='cost',integrity_pass=True,pairs=pairs,cost_goal_pass=False))['qualified'])

if __name__=='__main__':unittest.main()
