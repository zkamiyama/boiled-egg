import csv,itertools,tempfile,unittest
from pathlib import Path
import compare_legacy as audit

class LegacyTests(unittest.TestCase):
    def write(self,path,rows):
        with path.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(audit.KEYS+audit.VALUES);w.writerows(rows)
    def test_complete_exact_rows(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a.csv',Path(d)/'b.csv'
            rows=[(*k,26000,1999,1999,k[2] if not k[3] else 0,123) for k in itertools.product((44100,48000,88200,96000),(32,257),(-12,0,12),(0,1))]
            self.write(a,rows);self.write(b,list(reversed(rows)))
            self.assertEqual(audit.compare(a,b),{'cases':48,'partition_pairs':24,'exact':True})
            for bad in (rows[:-1],rows+rows[:1],[(*rows[0][:-1],999),*rows[1:]]):
                self.write(b,bad)
                with self.assertRaises(ValueError):audit.compare(a,b)
    def test_partition_and_metadata_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a.csv',Path(d)/'b.csv'
            rows=[(*k,26000,1999,1999,0,k[1]) for k in itertools.product((44100,48000,88200,96000),(32,257),(-12,0,12),(0,1))]
            self.write(a,rows);self.write(b,rows)
            with self.assertRaisesRegex(ValueError,'partition'):audit.compare(a,b)
            self.write(a,rows[:-1]+[(*rows[-1][:-5],0,1,1,0,123)])
            with self.assertRaises(ValueError):audit.read(a)
            a.write_text('rate,hash\n48000,1\n')
            with self.assertRaises(ValueError):audit.read(a)
if __name__=='__main__':unittest.main()
