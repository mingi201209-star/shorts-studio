"""Static narration-to-visual contract regression tests (no render)."""
import unittest
from benchmarks.crumple_zone.semantic_contract import CLAIMS, audit

class SemanticContractTests(unittest.TestCase):
    def test_all_claims_have_known_scenes(self):
        self.assertTrue(all(not row["missing_scenes"] for row in audit()))
    def test_no_unverified_claim_is_marked_pass(self):
        self.assertTrue(all(row["status"] != "PASS" for row in audit()))
    def test_restraints_are_not_silently_accepted(self):
        x = next(c for c in CLAIMS if "seat belts" in c.phrase)
        self.assertEqual(x.status, "NOT_VERIFIED")
        self.assertIn("X4", x.scene_ids)
    def test_average_force_requires_explicit_evidence(self):
        x = next(c for c in CLAIMS if "average force" in c.phrase)
        self.assertIn("average force", x.required_visible_action.lower())
if __name__ == "__main__":
    unittest.main()
