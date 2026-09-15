"""Canonical operation numbers: JSON 1 and 1.0 are the same requested operation."""
from dataclasses import asdict
import json
import unittest

import candidate_evidence as e
import comparison_contract as c


class RequestNumberTests(unittest.TestCase):
    def test_integer_float_duration_has_same_evidence_key(self):
        a = c.Request.from_semitones(1, 7)
        b = c.Request.from_semitones(1.0, 7.0)
        self.assertEqual(e.operation_key(44100, 1, asdict(a)), e.operation_key(44100, 1, asdict(b)))
        self.assertEqual(json.dumps(asdict(a), sort_keys=True), json.dumps(asdict(b), sort_keys=True))

    def test_direct_constructor_has_one_canonical_json_form(self):
        self.assertEqual(json.dumps(asdict(c.Request(1, 1))), json.dumps(asdict(c.Request(1.0, 1.0))))
        self.assertIs(type(c.Request(1, 1).duration_ratio), float)
        self.assertIs(type(c.Request(1, 1).pitch_ratio), float)

    def test_boolean_and_string_are_not_numeric_controls(self):
        for d, p in ((True, 1), (1, True), ('1', 1), (1, '1')):
            with self.assertRaises(ValueError): c.Request(d, p)
        for st in (True, '7', None):
            with self.assertRaises(ValueError): c.Request.from_semitones(1, st)

    def test_json_roundtrip_preserves_exact_operation(self):
        for duration, st in ((1, 7), (1.25, -7), (0.8, 0)):
            r = c.Request.from_semitones(duration, st)
            again = c.Request(**json.loads(json.dumps(asdict(r))))
            self.assertEqual(e.digest(asdict(r)), e.digest(asdict(again)))
            self.assertEqual(r.target_frames(1001), again.target_frames(1001))

    def test_nearby_but_different_ratio_does_not_reuse_evidence(self):
        a = c.Request(1.0, 1.0); b = c.Request(1.00000001, 1.0)
        self.assertNotEqual(e.operation_key(44100, 1, asdict(a)), e.operation_key(44100, 1, asdict(b)))

    def test_rounding_tolerance_stays_an_integer_contract(self):
        for value in (True, 1.0, -1, 2):
            with self.assertRaises(ValueError): c.Request(1, 1, value)


if __name__=='__main__': unittest.main()
