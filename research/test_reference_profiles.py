"""Reference-profile tools: integrity, blindness, scoring and real-CLI smoke."""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from unittest import mock

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_reference_profiles as evaluate
import make_reference_profile_pack as packs
import summarize_profile_ratings as ratings
from eval_multires_corpus import fingerprint


def write_csv(path, rows, fields=None):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.refs = self.root/'references'; self.refs.mkdir()
        self.evaluation = self.root/'evaluation'; self.evaluation.mkdir()
        self.catalog = self.root/'catalog.csv'
        self.source = self.refs/'Fixture.wav'
        self.x = (.2*np.sin(2*np.pi*440*np.arange(4800)/48000)).astype('float32')
        sf.write(self.source, self.x, 48000, subtype='FLOAT')
        write_csv(self.catalog, [dict(ref_name='Fixture.wav', ref_loc='Source/Voice/')])
        self.sources = evaluate.preflight(self.refs, self.catalog)
        self.rows = []
        for pitch in evaluate.PITCHES:
            for index, profile in enumerate(evaluate.PROFILES):
                relative = Path('renders')/f'{pitch:+d}'/f'{profile}.wav'
                path = self.evaluation/relative; path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(path, self.x*(1+index*.1), 48000, subtype='FLOAT')
                self.rows.append(dict(**self.sources[0], pitch_semitones=pitch,
                    control_ratio=float(np.float32(2**(pitch/12))), formant='harmonic', profile=profile,
                    env=.3+index*.1, onset=.8-index*.1, rms=.2, peak=.3, duration_error_frames=0,
                    render_path=relative.as_posix(), render_sha256=fingerprint(path)))
        self.summary = dict(schema=evaluate.SCHEMA, external_baseline='none', mos_transfer=False,
            sources=self.sources, formants=['harmonic'], corpus_label='synthetic correctness fixture',
            category_policy='copied from catalog', **evaluate.summarize(self.rows, self.sources, ['harmonic']))
        self.save_grid()

    def save_grid(self):
        write_csv(self.evaluation/'metrics.csv', self.rows)
        self.summary['metrics_sha256'] = fingerprint(self.evaluation/'metrics.csv')
        (self.evaluation/'summary.json').write_text(json.dumps(self.summary))

    def make_pack(self, name='pack', **kwargs):
        output = self.root/name
        result = packs.make_pack(self.evaluation, self.refs, output, 'harmonic', **kwargs)
        return output, result

    def rating_fixture(self):
        output, _ = self.make_pack()
        key = output/'analyst/answer_key.json'
        with (output/'listener/ratings.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        return key, rows

    def save_ratings(self, rows, name='responses.csv'):
        path = self.root/name
        write_csv(path, rows, packs.RATING_FIELDS)
        return path


class EvaluationTests(Fixture):
    def test_original_category_not_test_filename_heuristic(self):
        write_csv(self.catalog, [dict(ref_name='Fixture.wav', ref_loc='Source/Music/')])
        self.assertEqual(evaluate.preflight(self.refs,self.catalog)[0]['category'], 'music')

    def test_conflicting_category_rejected(self):
        write_csv(self.catalog, [dict(ref_name='Fixture.wav', ref_loc='Source/Music/'),
                                 dict(ref_name='Fixture.wav', ref_loc='Source/Voice/')])
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            evaluate.preflight(self.refs,self.catalog)

    def test_unknown_reference_rejected(self):
        write_csv(self.catalog, [dict(ref_name='Other.wav', ref_loc='Source/Music/')])
        with self.assertRaisesRegex(ValueError, 'absent'):
            evaluate.preflight(self.refs,self.catalog)

    def test_short_nonfinite_and_unsupported_audio_rejected(self):
        for audio,rate,subtype in [(self.x[:10],48000,'FLOAT'),
                                    (self.x*np.nan,48000,'FLOAT'),
                                    (self.x,8000,'FLOAT'), (self.x,48000,'DOUBLE')]:
            with self.subTest(rate=rate,subtype=subtype):
                sf.write(self.source,audio,rate,subtype=subtype)
                with self.assertRaises(ValueError): evaluate.preflight(self.refs,self.catalog)

    def test_complete_grid_required(self):
        self.assertEqual(evaluate.summarize(self.rows,self.sources,['harmonic'])['renders'],18)
        for rows in [self.rows[:-1], self.rows+[self.rows[0]]]:
            with self.assertRaises(ValueError): evaluate.summarize(rows,self.sources,['harmonic'])

    def test_antiphase_metrics_do_not_collapse_to_silence(self):
        mono = evaluate.measure(self.x[:,None], (.6*self.x)[:,None],48000)
        anti = evaluate.measure(np.c_[self.x,-self.x], np.c_[.6*self.x,-.6*self.x],48000)
        self.assertAlmostEqual(mono['env'],anti['env'],places=7)
        self.assertAlmostEqual(mono['onset'],anti['onset'],places=7)
        self.assertGreater(anti['rms'],.05)

    def test_preflight_fails_before_renderer_or_output(self):
        args = argparse.Namespace(source_commit='a'*40, workers=1, block=256,
            corpus_label='test', formants=['harmonic'], ref_dir=self.refs,
            pv_cli=self.source, multires_cli=self.source, catalog=self.catalog,
            output=self.root/'bad-result')
        sf.write(self.source,self.x[:2],48000,subtype='FLOAT')
        with mock.patch.object(evaluate.cf,'ProcessPoolExecutor') as executor:
            with self.assertRaises(ValueError): evaluate.run(args)
            executor.assert_not_called()
        self.assertFalse(args.output.exists())

    def test_renderer_metadata_failure_rejected(self):
        def bad_render(command, **kwargs):
            sf.write(command[2], self.x,44100,subtype='FLOAT')
            return subprocess.CompletedProcess(command,0,'','')
        job=(self.source,self.sources[0],self.source,self.source,self.root/'failed', ['harmonic'],256)
        with mock.patch.object(evaluate.subprocess,'run',side_effect=bad_render):
            with self.assertRaisesRegex(ValueError,'mismatch'): evaluate.source_job(job)

    @unittest.skipUnless(os.environ.get('BOILED_EGG_PV_CLI') and os.environ.get('BOILED_EGG_MULTIRES_CLI'),
                         'set CLI paths for real integration smoke')
    def test_real_cpp_all_profiles_pitches_and_formants(self):
        args=argparse.Namespace(source_commit='a'*40, workers=2, block=64,
            corpus_label='synthetic integration smoke', formants=list(evaluate.FORMANTS),
            ref_dir=self.refs, catalog=self.catalog,
            pv_cli=Path(os.environ['BOILED_EGG_PV_CLI']),
            multires_cli=Path(os.environ['BOILED_EGG_MULTIRES_CLI']), output=self.root/'real')
        result=evaluate.run(args)
        self.assertEqual(result['renders'],54)
        self.assertEqual(result['exact_duration_renders'],54)
        for mode in evaluate.FORMANTS:
            pack=self.root/('real-pack-'+mode)
            made=packs.make_pack(args.output,self.refs,pack,mode)
            self.assertEqual(made['trials'],6)
            self.assertEqual(ratings.collect(pack/'analyst/answer_key.json',
                [pack/'listener/ratings.csv'])['status'],'not_listened')


class PackTests(Fixture):
    def test_reproducible_and_balanced_exact_grid(self):
        one,result=self.make_pack('one'); two,_=self.make_pack('two')
        self.assertEqual(result['trials'],6)
        self.assertEqual((one/'analyst/answer_key.json').read_bytes(),(two/'analyst/answer_key.json').read_bytes())
        key=json.loads((one/'analyst/answer_key.json').read_text())
        self.assertEqual({t['pitch_semitones'] for t in key['trials']},set(evaluate.PITCHES))
        counts=Counter((label,p) for t in key['trials'] for label,p in t['labels'].items())
        self.assertTrue(all(n == 2 for n in counts.values()))
        for name,digest in key['listener_sha256'].items():
            self.assertEqual(fingerprint(one/'listener'/name),digest)

    def test_listener_has_no_system_or_source_key(self):
        output,_=self.make_pack()
        for path in (output/'listener').iterdir():
            if path.is_file():
                text=path.read_text()
                for secret in (*evaluate.PROFILES,'Fixture','answer_key','seed'):
                    self.assertNotIn(secret,text)

    def test_audio_shape_and_headroom(self):
        output,_=self.make_pack()
        for path in (output/'listener/audio').rglob('*.wav'):
            x,sr=sf.read(path,always_2d=True)
            self.assertEqual(x.shape,(4800,1)); self.assertEqual(sr,48000)
            self.assertLessEqual(np.max(np.abs(x)),.95004)

    def test_seed_changes_assignment(self):
        one,_=self.make_pack('one',seed=3); two,_=self.make_pack('two',seed=9)
        self.assertNotEqual((one/'analyst/answer_key.json').read_bytes(),(two/'analyst/answer_key.json').read_bytes())

    def test_missing_grid_not_silently_skipped(self):
        self.rows.pop(); self.save_grid()
        with self.assertRaises(ValueError): self.make_pack()
        self.assertFalse((self.root/'pack').exists())

    def test_tampered_metrics_rejected(self):
        with (self.evaluation/'metrics.csv').open('a') as stream: stream.write('\n')
        with self.assertRaisesRegex(ValueError,'fingerprint'): self.make_pack()

    def test_tampered_audio_not_published(self):
        (self.evaluation/self.rows[-1]['render_path']).write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'fingerprint'): self.make_pack()
        self.assertFalse((self.root/'pack').exists())

    def test_wrong_rate_rejected_even_with_updated_fingerprint(self):
        path=self.evaluation/self.rows[-1]['render_path']
        sf.write(path,self.x,44100,subtype='FLOAT')
        self.rows[-1]['render_sha256']=fingerprint(path);self.save_grid()
        with self.assertRaisesRegex(ValueError,'sample-rate mismatch'): self.make_pack()
        self.assertFalse((self.root/'pack').exists())

    def test_source_and_control_metadata_are_checked(self):
        for field,value in [('category','fake'),('control_ratio',1.234),('peak',float('nan')),
                             ('duration_error_frames',1)]:
            old=self.rows[0][field];self.rows[0][field]=value;self.save_grid()
            with self.assertRaises(ValueError): self.make_pack()
            self.rows[0][field]=old

    def test_external_baseline_cannot_be_relabelled(self):
        self.summary['external_baseline']='elastique';self.save_grid()
        with self.assertRaises(ValueError):self.make_pack()

    def test_overwrite_and_insufficient_category_refused(self):
        output,_=self.make_pack()
        original=(output/'analyst/answer_key.json').read_bytes()
        with self.assertRaises(ValueError):self.make_pack()
        self.assertEqual(original,(output/'analyst/answer_key.json').read_bytes())
        with self.assertRaises(ValueError):self.make_pack('other',per_category=2)

    def test_path_traversal_and_symlinks_rejected(self):
        outside=self.root/'outside.wav'; outside.write_text('outside')
        link=self.refs/'escape.wav';link.symlink_to(outside)
        for relative in ['../outside.wav',str(outside),'escape.wav','..\\outside.wav']:
            with self.assertRaises(ValueError):packs.inside(self.refs,relative)

    def test_category_html_is_escaped(self):
        text=packs.player([dict(trial_id='T001',category='<script>alert(1)</script>',pitch_semitones=3)],'x')
        self.assertIn('&lt;script&gt;',text)
        self.assertNotIn('<script>alert(1)',text)

    @unittest.skipUnless(shutil.which('node'), 'Node.js needed for player CSV round-trip')
    def test_player_javascript_csv_roundtrip(self):
        text=packs.player([dict(trial_id='T001',category='voice',pitch_semitones=3)],'fixture-pack')
        script=text.split('<script>')[1].split('</script>')[0]
        prefix="""
const fs=require('fs');let csv='';
const controls={listener:{value:'listener,"one"'},export:{},status:{}};
global.document={addEventListener(){},getElementById:id=>controls[id],
 querySelector:s=>({value:s.includes('data-notes')?'comma, quote" and newline\\nnext':'4'}),
 createElement:()=>({click(){}})};
global.Blob=class{constructor(parts){csv=parts.join('')}};
global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.setTimeout=()=>{};
"""
        js=self.root/'player.js';js.write_text(prefix+script+"\ndocument.getElementById('export').onclick();process.stdout.write(csv);\n")
        result=subprocess.run(['node',str(js)],capture_output=True,text=True,check=True)
        parsed=list(csv.DictReader(result.stdout.splitlines(keepends=True)))
        self.assertEqual(len(parsed),3)
        self.assertEqual(parsed[0]['listener_id'],'listener,"one"')
        self.assertEqual(parsed[0]['notes'],'comma, quote" and newline\nnext')
        self.assertEqual(parsed[0]['overall'],'4')


class RatingTests(Fixture):
    def test_blank_template_is_not_a_result(self):
        key,rows=self.rating_fixture()
        result=ratings.collect(key,[self.save_ratings(rows)])
        self.assertEqual(result['status'],'not_listened')
        self.assertEqual(result['complete_triplets'],0)
        self.assertIsNone(result['scores']['overall']['multires']['listener_balanced_mean'])
        self.assertFalse(result['automatic_promotion'])

    def test_complete_response_is_mapped_correctly(self):
        key,rows=self.rating_fixture(); mapping=json.loads(key.read_text())
        score={'general':'2','transient':'3','multires':'5'}
        lookup={t['trial_id']:t['labels'] for t in mapping['trials']}
        for row in rows:
            row['listener_id']='L1'
            row.update({c:score[lookup[row['trial_id']][row['label']]] for c in packs.CRITERIA})
        result=ratings.collect(key,[self.save_ratings(rows)])
        self.assertEqual(result['status'],'complete_for_submitted_listeners')
        self.assertEqual(result['complete_triplets'],6)
        self.assertEqual(result['scores']['overall']['multires']['mean_delta_vs_transient'],2)

    def test_incomplete_triplet_excluded_and_reported(self):
        key,rows=self.rating_fixture()
        rows[0]['listener_id']='L1'; rows[0].update({c:'4' for c in packs.CRITERIA})
        result=ratings.collect(key,[self.save_ratings(rows)])
        self.assertEqual(result['status'],'partial');self.assertEqual(result['complete_triplets'],0)
        self.assertEqual(len(result['incomplete_trials']),1)

    def test_bad_scores_and_missing_listener_rejected(self):
        key,rows=self.rating_fixture()
        for value in ['0','6','nan','3.5','']:
            sample=copy.deepcopy(rows); sample[0]['listener_id']='L1'
            sample[0].update({c:'4' for c in packs.CRITERIA}); sample[0]['overall']=value
            with self.assertRaises(ValueError):ratings.collect(key,[self.save_ratings(sample)])
        rows[0].update({c:'4' for c in packs.CRITERIA})
        with self.assertRaises(ValueError):ratings.collect(key,[self.save_ratings(rows)])

    def test_duplicate_wrong_pack_unknown_label_rejected(self):
        key,rows=self.rating_fixture()
        for field,value in [('pack_id','wrong'),('trial_id','T999'),('label','D')]:
            changed=copy.deepcopy(rows);changed[0][field]=value
            with self.assertRaises(ValueError):ratings.collect(key,[self.save_ratings(changed)])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            ratings.collect(key,[self.save_ratings(rows+rows[:1])])

    def test_listener_weight_not_number_of_trials(self):
        key,rows=self.rating_fixture()
        response=[]
        for listener,count,score in [('L1',18,'1'),('L2',3,'5')]:
            for row in copy.deepcopy(rows[:count]):
                row['listener_id']=listener;row.update({c:score for c in packs.CRITERIA});response.append(row)
        result=ratings.collect(key,[self.save_ratings(response)])
        self.assertEqual(result['complete_triplets'],7)
        self.assertEqual(result['scores']['overall']['general']['listener_balanced_mean'],3)
        self.assertEqual(result['coverage']['L2']['complete_trials'],1)


if __name__ == '__main__':
    unittest.main()
