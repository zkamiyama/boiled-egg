import csv
from pathlib import Path
import tempfile
import unittest
import audit as a

class AuditTests(unittest.TestCase):
    def table(self, path, kind, rows):
        keys,values={'c':(a.C_KEYS,('frames','audio_hash','metadata_hash')),
                     'cpp':(a.CPP_KEYS,('frames','audio_hash','latency','capabilities')),
                     'preview':(a.PREVIEW_KEYS,('frames','hash'))}[kind]
        with path.open('w',newline='') as f:
            w=csv.writer(f);w.writerow([*keys,*values]);w.writerows(rows)
    def test_grid_counts(self):
        self.assertEqual(len(a.expected('c')),288)
        self.assertEqual(len(a.expected('cpp')),12)
        self.assertEqual(len(a.expected('preview')),156)
    def test_missing_duplicate_wrong_hash_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            x,y=Path(d)/'x.csv',Path(d)/'y.csv'
            for kind,tail in [('c',(100,1234,5678)),('cpp',(100,1234,24,255)),('preview',(100,1234))]:
                rows=[(*k,*tail) for k in sorted(a.expected(kind))];self.table(x,kind,rows)
                self.table(y,kind,list(reversed(rows)));self.assertEqual(a.compare(x,y,kind),len(rows))
                for bad in (rows[:-1],rows+rows[:1],[(*rows[0][:-1],777),*rows[1:]]):
                    self.table(y,kind,bad)
                    with self.assertRaises(ValueError):a.compare(x,y,kind)
    def test_exports_are_additive_and_public_only(self):
        old={'boiledegg_create','boiledegg_destroy'};new=old|a.ADDITIONS
        a.export_contract(old,new)
        for bad in (new-{'boiledegg_create'},new|{'boiledegg_private_leak'},new|{'_Zfoo'},new-{'boiledegg_push_ramps'}):
            with self.assertRaises(ValueError):a.export_contract(old,bad)
    def test_source_scope_rejects_adapter_research_and_runtime_changes(self):
        with tempfile.TemporaryDirectory() as d:
            roots=[Path(d)/n for n in ('base','donor','new')]
            files=['adapters/plugin.cpp','eval/check.py','research/old.py','include/boiled_egg/boiled_egg.h',
                   'src/engine.cpp','src/engine.hpp','src/profile.cpp','src/backend.cpp']
            for r in roots:
                for f in files:
                    p=r/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(f+'\n')
            a.source_contract(*roots)
            for name in ('adapters/plugin.cpp','research/new.py','src/backend.cpp'):
                p=roots[2]/name;original=p.read_bytes() if p.exists() else None;p.write_text('changed')
                with self.assertRaises(ValueError):a.source_contract(*roots)
                if original is None:p.unlink()
                else:p.write_bytes(original)
    def test_bad_metadata_and_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';rows=[(*k,0,1234) for k in sorted(a.expected('preview'))]
            self.table(p,'preview',rows)
            with self.assertRaises(ValueError):a.read_grid(p,'preview')
            p.write_text('a,a\n1,2\n')
            with self.assertRaises(ValueError):a.read_grid(p,'preview')
if __name__=='__main__':unittest.main()
