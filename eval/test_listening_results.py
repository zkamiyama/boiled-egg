"""Bookkeeping fixtures only: made-up ratings must never be quality evidence."""
import json
from pathlib import Path
import unittest

import calibrated_listening as l
import comparison_contract as c
import listening_results as r
import test_calibrated_listening as helper


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.f = helper.ListeningTests('runTest')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.run_raw(); self.pack = self.f.root / 'pack'
        self.info = l.make_pack(self.f.raw, self.f.cal, self.pack)
        self.index_hash = c.fingerprint(self.pack / r.INDEX)
        self.public, self.key = r.verify_pack(self.pack, self.index_hash)

    def submit(self, name, rows):
        path = self.f.root / (name + '.json')
        c.json_write(path, dict(pack_id=self.info['pack_id'], ratings=rows))
        return dict(listener_id=name, path=str(path))

    def complete(self, trial, scores, dimension='naturalness'):
        return [dict(trial=trial, choice=choice, dimension=dimension,
                     rating=scores[row['candidate']])
                for (t, choice), row in self.key.items() if t == trial]

    def run_summary(self, submissions):
        return r.summarize(self.pack, submissions, self.f.root / 'report', self.index_hash)

    def test_zero_responses_never_become_zero_quality_or_neutral_scores(self):
        report = self.run_summary([])
        self.assertEqual(report['listening_status'], 'no_responses')
        self.assertEqual(report['explicit_ratings'], 0)
        self.assertIsNone(report['quality_selection'])
        self.assertTrue(all(x['listener_balanced_mean'] is None for x in report['candidate_means']))
        self.assertTrue(all(x['listener_balanced_delta'] is None for x in report['paired']))

    def test_partial_panels_are_retained_but_not_scored(self):
        trial = self.public['trials'][0]
        row = dict(trial=trial['trial'], choice=trial['choices'][0]['label'], dimension='attack', rating=4)
        report = self.run_summary([self.submit('L1', [row])])
        self.assertEqual(report['explicit_ratings'], 1)
        self.assertEqual(report['complete_panels'], 0)
        self.assertEqual(len(report['incomplete_panels']), 1)
        self.assertTrue(all(x['listener_balanced_mean'] is None for x in report['candidate_means']))

    def test_equal_listener_weight_not_equal_total_rating_weight(self):
        trials = [t['trial'] for t in self.public['trials']]
        rows1 = sum([self.complete(t, {'engine_A':5, 'engine_B':1}) for t in trials], [])
        rows2 = self.complete(trials[0], {'engine_A':1, 'engine_B':5})
        report = self.run_summary([self.submit('L1', rows1), self.submit('L2', rows2)])
        pair = next(x for x in report['paired'] if x['dimension']=='naturalness')
        self.assertEqual(pair['listener_balanced_delta'], 0)
        self.assertEqual((pair['higher'], pair['lower'], pair['matched_complete_panels']), (2,1,3))
        means = [x for x in report['candidate_means'] if x['dimension']=='naturalness']
        self.assertEqual([x['listener_balanced_mean'] for x in means], [3,3])
        self.assertIsNone(report['quality_selection'])

    def test_wrong_pack_and_duplicate_listener_rejected_before_output(self):
        one = self.submit('L1', [])
        with self.assertRaises(ValueError):self.run_summary([one,one])
        with self.assertRaises(ValueError):self.run_summary([one,dict(one,listener_id='L2')])
        c.json_write(Path(one['path']), dict(pack_id='wrong',ratings=[]))
        with self.assertRaises(ValueError):self.run_summary([one])
        self.assertFalse((self.f.root/'report').exists())

    def test_audio_and_player_edits_are_detected(self):
        for name in ('listener/index.html', self.public['trials'][0]['choices'][0]['file']):
            path = self.pack / (name if name.startswith('listener/') else 'listener/'+name)
            before = path.read_bytes(); path.write_bytes(before+b'changed')
            with self.assertRaisesRegex(ValueError,'pack file'):r.verify_pack(self.pack)
            path.write_bytes(before)
        r.verify_pack(self.pack)

    def test_extra_missing_and_escaped_files_rejected(self):
        path = self.pack/'listener/extra.txt';path.write_text('unexpected')
        with self.assertRaises(ValueError):r.verify_pack(self.pack)
        path.unlink()
        original = self.pack/'listener/index.html'; data=original.read_bytes();original.unlink()
        with self.assertRaises(ValueError):r.verify_pack(self.pack)
        target=self.f.root/'outside.html';target.write_bytes(data);original.symlink_to(target)
        with self.assertRaises(ValueError):r.verify_pack(self.pack)

    def test_sealed_key_swap_cannot_relabel_rendered_candidates(self):
        key_path=self.pack/'organizer/key.json'; key=json.loads(key_path.read_text())
        for row in key['choices']:row['candidate'] = 'invented_candidate_'+row['candidate']
        c.json_write(key_path,key)
        (self.pack/r.INDEX).unlink();r.seal_pack(self.pack)
        with self.assertRaisesRegex(ValueError,'rendered candidate'):r.verify_pack(self.pack)
        with self.assertRaisesRegex(ValueError,'separately recorded'):r.verify_pack(self.pack,self.index_hash)

    def test_old_or_resealed_pack_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError,'already sealed'):r.seal_pack(self.pack)
        (self.pack/r.INDEX).unlink()
        with self.assertRaises(FileNotFoundError):r.verify_pack(self.pack)

    def test_nan_boolean_and_unknown_answers_rejected(self):
        row=self.complete(self.public['trials'][0]['trial'], {'engine_A':3,'engine_B':3})[0]
        for changes in ({'rating':float('nan')},{'rating':True},{'dimension':'invented'},{'choice':'Z'}):
            # JSON's NaN extension is intentionally generated only as a negative fixture.
            path=self.f.root/'invalid.json'; path.write_text(json.dumps(dict(pack_id=self.info['pack_id'],ratings=[dict(row,**changes)])))
            with self.assertRaises(ValueError):self.run_summary([dict(listener_id='L1',path=str(path))])
        self.assertFalse((self.f.root/'report').exists())

    def test_existing_output_is_not_destroyed(self):
        out=self.f.root/'report';out.mkdir();(out/'keep').write_text('important')
        with self.assertRaises(ValueError):self.run_summary([])
        self.assertEqual((out/'keep').read_text(),'important')


if __name__=='__main__':unittest.main()
