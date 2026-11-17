"""Static narration-to-visual contract regression tests (no render)."""
import unittest
from benchmarks.crumple_zone.semantic_contract import CLAIMS, audit

class SemanticContractTests(unittest.TestCase):
    def test_all_claims_have_known_scenes(self):
        self.assertTrue(all(not row["missing_scenes"] for row in audit()))
    def test_no_unverified_claim_is_marked_pass(self):
        self.assertTrue(all(row["status"] != "PASS" for row in audit()))
    def test_comparison_narrates_visible_rebound_and_interior_deformation(self):
        import json
        from pathlib import Path

        plan = Path(__file__).resolve().parents[1] / "examples/experiments/crumple-zone-speech-plan.json"
        beats = json.loads(plan.read_text())["variants"][0]["beats"]
        narration = " ".join(beat["narration_en"] for beat in beats).lower()
        assert all(phrase in narration for phrase in ("bounces back", "cabin stays intact"))
        assert all(phrase not in narration for phrase in ("seat belts", "airbags", "average force"))
        assert all(claim.phrase in narration for claim in CLAIMS)
