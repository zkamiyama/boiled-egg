import csv
import tempfile
import unittest
from pathlib import Path
import verify_integration as v

class IntegrationTests(unittest.TestCase):
    def write(self, path, rows):
        with path.open('w', newline='') as stream:
            writer=csv.writer(stream);writer.writerow([*v.FIELDS,'frames','hash']);writer.writerows(rows)
    def rows(self):
        return [(*key,8193,i+1) for i,key in enumerate(sorted(v.expected_keys()))]
    def test_complete_grid_and_exact_replay(self):
        self.assertEqual(len(v.expected_keys()),156)
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.csv',Path(tmp)/'b.csv';rows=self.rows()
            self.write(a,rows);self.write(b,list(reversed(rows)))
            self.assertEqual(v.compare_replays(a,b)['total_pairs'],156)
    def test_missing_duplicate_and_changed_output_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.csv',Path(tmp)/'b.csv';rows=self.rows();self.write(a,rows)
            for wrong in (rows[:-1],rows+rows[:1],[(*rows[0][:-1],99999),*rows[1:]]):
                self.write(b,wrong)
                with self.assertRaises(ValueError):v.compare_replays(a,b)
    def test_nonpositive_frames_and_wrong_columns_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.csv';rows=self.rows();self.write(a,[(*rows[0][:-2],0,1),*rows[1:]])
            with self.assertRaises(ValueError):v.read_replay(a)
            a.write_text('rate,hash\n48000,1\n')
            with self.assertRaises(ValueError):v.read_replay(a)
    def test_source_coverage_and_content_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            for root in (a,b):
                (root/'src').mkdir(parents=True);(root/'include').mkdir()
                (root/'src/kernel.cpp').write_text('kernel\n');(root/'include/api.h').write_text('ABI\n')
            self.assertEqual(len(v.source_check(a,b)),2)
            (b/'src/kernel.cpp').write_text('changed\n')
            with self.assertRaises(ValueError):v.source_check(a,b)
            (b/'src/kernel.cpp').unlink()
            with self.assertRaises(ValueError):v.source_check(a,b)
if __name__=='__main__':unittest.main()
