"""Fixed cohort, paired accounting and artifact-integrity regression tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from collections import Counter
import eval_innovation_confirmation as confirm
import summarize_phase_innovation as summary

class InnovationStudyTest(unittest.TestCase):
    def test_training_selection_is_fixed_balanced_and_order_independent(self):
        sources=[dict(stem=f'{c}-{i}',category=c) for c in ('voice','solo','music') for i in range(9)]
        selected=confirm.select_sources(sources)
        self.assertEqual(selected,confirm.select_sources(list(reversed(sources))))
        self.assertEqual(Counter(r['category'] for r in selected),{'voice':4,'solo':4,'music':4})
        self.assertEqual(len({r['stem'] for r in selected}),12)
        with self.assertRaises(ValueError):confirm.select_sources(sources[:3])
    def test_actual_pilot_not_old_csv_split(self):
        rows=[dict(source='Ardour_2',split='confirmation'),dict(source='Alto_Sax_15',split='development')]
        self.assertEqual(summary.confirmation_rows(rows),rows[1:])
        self.assertEqual(len(summary.PILOT_SOURCES),5)
    def test_paired_statistics_and_worst_case(self):
        rows=[]
        for i in range(6):
            for variant in ('baseline','refined'):
                rows.append(dict(source=f's{i//3}',condition=str(i),variant=variant,score=i+(2 if variant=='refined' else 0)))
        result=summary.paired(rows,'baseline','score',True)
        self.assertEqual(result['wins'],6);self.assertEqual(result['mean_delta'],2)
        self.assertEqual(result['ci95'],[2,2]);self.assertEqual(result['clusters'],2)
        result=summary.paired(rows,'baseline','score',False);self.assertEqual(result['losses'],6)
        with self.assertRaises(ValueError):summary.paired(rows[:-1],'baseline','score')
        with self.assertRaises(ValueError):summary.paired(rows+rows[:1],'baseline','score')
    def test_hash_header_and_nonfinite_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);table=root/'measurements.csv';manifest=root/'summary.json'
            def write(value):
                with table.open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=['source','variant','render_sha256','metric'])
                    w.writeheader();w.writerow(dict(source='s',variant='refined',render_sha256='a'*64,metric=value))
                manifest.write_text(json.dumps(dict(rows=1,measurements_sha256=summary.digest(table))))
            write(1.);rows,_=summary.read_report(root);self.assertEqual(rows[0]['metric'],1.)
            table.write_text(table.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'hash'):summary.read_report(root)
            write('nan')
            with self.assertRaisesRegex(ValueError,'nonfinite'):summary.read_report(root)
    def test_seed_ranges_are_disjoint_from_old_banks(self):
        self.assertEqual(confirm.SEEDS,tuple(range(120000,120008)))
        self.assertFalse(set(confirm.SEEDS)&set(range(93173,93281)))
        self.assertEqual(len(confirm.SHIFTS),6)

if __name__=='__main__':unittest.main()
