import unittest
import cost_audit as c

class CostAuditTests(unittest.TestCase):
    def test_median_of_cell_means_not_best_ratio(self):
        self.assertEqual(c.median_cost([100, 1, 100], [120, 120, 1]), 1.2)
        self.assertEqual(c.median_cost([10, 20, 30], [40, 40, 40]), 2.)
    def test_invalid_means_rejected(self):
        for a in ([0,1,2], [1,2], [1,2,float('nan')], [-1,1,2]):
            with self.assertRaises(ValueError):c.median_cost(a, [1,2,3])
    def test_history_includes_warmup_and_output_hash(self):
        row=dict(repeat=1,rate=48000,quality=0,policy=0,block=32,index=0,warmup=1,fingerprint=7,wall_ns=100)
        c.exact_history([row],[dict(row,wall_ns=200)])
        for b in ([], [dict(row,fingerprint=8)], [dict(row,warmup=0)], [dict(row,index=1)]):
            with self.assertRaises(ValueError):c.exact_history([row],b)

if __name__=='__main__':unittest.main()
