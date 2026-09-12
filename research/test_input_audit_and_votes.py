"""Synthetic correctness tests; no dataset, listening results or MOS transfer."""
from __future__ import annotations

import csv
import io
import json
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_tsm_inputs as audit
import score_blind_votes as votes


def csv_file(path: Path, fields: list[str], rows: list[dict]) -> Path:
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def wav_bytes(rate: int = 48000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros((4800, channels)), rate, format='WAV', subtype='PCM_16')
    return buffer.getvalue()


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ref = self.root/'reference.zip'
        self.test = self.root/'processed.zip'
        self.scores = self.root/'scores.csv'
        self.fields = ['test_name', 'ref_name', 'ref_loc', 'method', 'TSM', 'MeanOS']
        self.rows = [dict(test_name='source_Elastique_100_per.wav', ref_name='source.wav',
                          ref_loc='Source/Voice/', method='Elastique', TSM='100', MeanOS='4')]
        self.zip(self.ref, {'source.wav': wav_bytes()})
        self.zip(self.test, {self.rows[0]['test_name']: wav_bytes()})
        self.save_scores()

    def zip(self, path, items):
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in items.items():
                archive.writestr(name, data)

    def save_scores(self):
        csv_file(self.scores, self.fields, self.rows)

    def run_audit(self):
        return audit.audit(self.ref, self.test, self.scores)

    def test_exact_pairs_and_fingerprints(self):
        report = self.run_audit()
        self.assertTrue(report['four_way_inputs_ready'])
        self.assertEqual(report['ready_derived_elastique_pairs'], 1)
        self.assertEqual(report['inputs']['scores']['sha256'], audit.fingerprint(self.scores))
        self.assertEqual(report['reference_only_sources'][0]['locations'], ['Source/Voice/'])
        json.dumps(report, allow_nan=False)

    def test_training_reference_not_substituted(self):
        self.zip(self.ref, {'source_train.wav': wav_bytes()})
        report = self.run_audit()
        self.assertFalse(report['four_way_inputs_ready'])
        self.assertEqual(report['ready_processed_pairs'], 0)
        self.assertEqual(report['missing_reference_files'], ['source.wav'])

    def test_unknown_processed_is_not_fuzzy_matched(self):
        self.zip(self.test, {'source_Elastique_100.1_per.wav': wav_bytes()})
        report = self.run_audit()
        self.assertEqual(report['matched_score_rows'], 0)
        self.assertFalse(report['four_way_inputs_ready'])

    def test_unprovided_catalog_conditions_are_not_missing_inputs(self):
        extra = dict(self.rows[0], test_name='other_Elastique_100_per.wav', ref_name='other.wav')
        self.rows.append(extra)
        self.save_scores()
        self.assertTrue(self.run_audit()['four_way_inputs_ready'])

    def test_rate_and_channel_mismatch(self):
        for rate, channels in [(44100, 1), (48000, 2)]:
            with self.subTest(rate=rate, channels=channels):
                self.zip(self.test, {self.rows[0]['test_name']: wav_bytes(rate, channels)})
                report = self.run_audit()
                self.assertEqual(report['ready_processed_pairs'], 0)
                self.assertEqual(len(report['rate_or_channel_mismatches']), 1)

    def test_duplicate_score_and_nonfinite_factor(self):
        for rows in [[self.rows[0], self.rows[0]], [dict(self.rows[0], TSM='nan')]]:
            csv_file(self.scores, self.fields, rows)
            with self.assertRaises(ValueError):
                self.run_audit()

    def test_zip_traversal_and_ambiguous_basename(self):
        cases = [{'../not_audio.txt': b'x', 'source.wav': wav_bytes()},
                 {'a/source.wav': wav_bytes(), 'b/SOURCE.wav': wav_bytes()}]
        for items in cases:
            self.zip(self.ref, items)
            with self.assertRaises(ValueError):
                self.run_audit()

    def test_symlink_member_rejected(self):
        with zipfile.ZipFile(self.ref, 'w') as archive:
            item = zipfile.ZipInfo('source.wav')
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(item, b'target.wav')
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_no_audio_and_empty_catalog(self):
        self.zip(self.ref, {'note.txt': b'none'})
        with self.assertRaises(ValueError):
            self.run_audit()
        csv_file(self.scores, self.fields, [])
        with self.assertRaises(ValueError):
            audit.score_rows(self.scores)


class VotesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root/'answer_key.csv'
        self.ballot = self.root/'choices.csv'
        self.identity = 'a'*64
        self.key_fields = ['trial', 'pack_id', 'category', 'formant', 'semitones', 'A', 'B', 'C']
        self.key_rows = [dict(trial='1', pack_id=self.identity, category='voice', formant='harmonic',
                             semitones='-3', A='general', B='transient', C='multires'),
                         dict(trial='2', pack_id=self.identity, category='solo', formant='harmonic',
                             semitones='3', A='multires', B='general', C='transient')]
        self.vote_fields = ['trial', 'pack_id', 'overall', 'attack', 'tone']
        self.vote_rows = [dict(trial='1', pack_id=self.identity, overall='A', attack='C', tone=''),
                          dict(trial='2', pack_id=self.identity, overall='A', attack='', tone='B')]
        self.save()

    def save(self):
        csv_file(self.key, self.key_fields, self.key_rows)
        csv_file(self.ballot, self.vote_fields, self.vote_rows)

    def decode(self, **kwargs):
        return votes.decode(self.key, [('listener01', self.ballot)], **kwargs)

    def test_trial_specific_mapping_and_denominators(self):
        rows, summary = self.decode()
        self.assertEqual(summary['submitted_votes'], 4)
        self.assertEqual(summary['missing_votes'], 2)
        self.assertTrue(summary['identity_verified'])
        overall = [r['system'] for r in rows if r['criterion'] == 'overall']
        self.assertEqual(overall, ['general', 'multires'])
        group = next(g for g in summary['groups'] if g['dimension'] == 'all' and g['criterion'] == 'overall')
        self.assertEqual(group['counts'], dict(general=1, multires=1, transient=0))
        self.assertEqual(group['selection_fractions']['general'], .5)

    def test_missing_trial_counted_not_invented(self):
        self.vote_rows = self.vote_rows[:1]
        self.save()
        rows, summary = self.decode()
        self.assertEqual(summary['submitted_votes'], 2)
        self.assertTrue(all(r['status'] == 'missing' for r in rows if r['trial'] == 2))

    def test_no_votes_has_null_fractions(self):
        for row in self.vote_rows:
            row.update(overall='', attack='', tone='')
        self.save()
        _, report = self.decode()
        self.assertEqual(report['status'], 'no_submitted_preferences')
        self.assertTrue(all(v is None for g in report['groups'] for v in g['selection_fractions'].values()))
        json.dumps(report, allow_nan=False)

    def test_legacy_requires_explicit_opt_in(self):
        self.key_fields.remove('pack_id')
        self.vote_fields.remove('pack_id')
        for row in self.key_rows+self.vote_rows:
            del row['pack_id']
        self.save()
        with self.assertRaises(ValueError):
            self.decode()
        self.assertFalse(self.decode(allow_unbound=True)[1]['identity_verified'])

    def test_wrong_pack_rejected_even_with_legacy_opt_in(self):
        self.vote_rows[1]['pack_id'] = 'b'*64
        self.save()
        with self.assertRaises(ValueError):
            self.decode(allow_unbound=True)

    def test_duplicate_and_unknown_ballot_trials(self):
        original = self.vote_rows[1]['trial']
        for trial in ['1', '01', '3', '0', '-1', 'nan']:
            self.vote_rows[1]['trial'] = trial
            self.save()
            with self.assertRaises(ValueError):
                self.decode()
        self.vote_rows[1]['trial'] = original

    def test_invalid_label_and_duplicate_system(self):
        self.vote_rows[0]['overall'] = 'general'
        self.save()
        with self.assertRaises(ValueError):
            self.decode()
        self.vote_rows[0]['overall'] = 'A'
        self.key_rows[0]['B'] = 'general'
        self.save()
        with self.assertRaises(ValueError):
            self.decode()

    def test_changed_system_set_and_duplicate_key_trial(self):
        self.key_rows[1]['C'] = 'other'
        self.save()
        with self.assertRaises(ValueError):
            self.decode()
        self.key_rows[1]['C'] = 'transient'
        self.key_rows[1]['trial'] = '1'
        self.save()
        with self.assertRaises(ValueError):
            self.decode()

    def test_identical_votes_by_distinct_listeners_are_allowed(self):
        second = self.root/'second.csv'
        second.write_bytes(self.ballot.read_bytes())
        _, report = votes.decode(self.key, [('one', self.ballot), ('two', second)])
        self.assertEqual(report['listeners'], 2)
        self.assertEqual(report['submitted_votes'], 8)

    def test_repeated_listener_or_file_rejected(self):
        second = self.root/'second.csv'
        second.write_bytes(self.ballot.read_bytes())
        for ballots in [[('one', self.ballot), ('one', second)],
                        [('one', self.ballot), ('two', self.ballot)], []]:
            with self.assertRaises(ValueError):
                votes.decode(self.key, ballots)

    def test_require_complete(self):
        with self.assertRaises(ValueError):
            self.decode(require_complete=True)
        for row in self.vote_rows:
            row.update(overall='A', attack='B', tone='C')
        self.save()
        self.assertEqual(self.decode(require_complete=True)[1]['missing_votes'], 0)

    def test_four_way_key(self):
        self.key_fields.append('D')
        for row in self.key_rows:
            row['D'] = 'derived_elastique'
        self.vote_rows[0]['tone'] = 'D'
        self.save()
        rows, report = self.decode()
        self.assertIn('derived_elastique', report['systems'])
        self.assertEqual(rows[2]['system'], 'derived_elastique')

    def test_csv_duplicate_columns_and_ragged_rows(self):
        for text in ['trial,overall,overall,attack,tone\n1,A,A,B,C\n',
                     'trial,overall,attack,tone\n1,A,B\n']:
            self.ballot.write_text(text)
            with self.assertRaises(ValueError):
                self.decode(allow_unbound=True)

    def test_report_refuses_overwrite(self):
        rows, report = self.decode()
        output = self.root/'result'
        votes.write_report(output, rows, report)
        self.assertEqual(json.loads((output/'summary.json').read_text())['submitted_votes'], 4)
        with self.assertRaises(ValueError):
            votes.write_report(output, rows, report)


if __name__ == '__main__':
    unittest.main()
