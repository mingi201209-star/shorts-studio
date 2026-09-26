"""Regression guard for the retention-engine rollout (Idea Gate,
First-Second Hook, Information Change, Story Progression, Ending Payoff,
Runtime Discipline): every manifest written before this contract existed
must keep validating and reporting exactly as before, because
strict_retention_contract defaults to False and none of them set it.
"""
import json
import os
from pathlib import Path

import pytest

from shorts_studio.project import load_project
from shorts_studio.final_video_qa import verify_source_budget, verify_retention_contract

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

# The Titanic manifest lives on content/titanic-fourth-funnel, a sibling
# branch not merged into this one -- fetched into the scratchpad for local
# regression testing only (see TITANIC_REGRESSION_MANIFEST env var). Skipped
# automatically when that file isn't present (e.g. a clean checkout of just
# this branch, or CI, which only has this branch's own examples/).
TITANIC_REGRESSION_MANIFEST = os.environ.get("TITANIC_REGRESSION_MANIFEST")


@pytest.mark.parametrize("name", ["comet.json", "radium_girls.json"])
def test_existing_manifest_still_validates_and_has_the_flag_off_by_default(name):
    project = load_project(str(EXAMPLES_DIR / name))
    assert getattr(project, "strict_retention_contract", None) is False
    # These manifests predate the contract and are not expected to satisfy
    # it -- that is fine, because it never gates them (opt-in only).
    if getattr(project, "strict_source_diversity", False):
        budget = verify_source_budget(project)
        assert budget["status"] == "PASS", budget


def test_titanic_manifest_still_validates_and_has_the_flag_off_by_default():
    if not TITANIC_REGRESSION_MANIFEST or not Path(TITANIC_REGRESSION_MANIFEST).is_file():
        pytest.skip("TITANIC_REGRESSION_MANIFEST not set to a local copy of the sibling branch's manifest")
    project = load_project(TITANIC_REGRESSION_MANIFEST)
    assert getattr(project, "strict_retention_contract", None) is False
    budget = verify_source_budget(project)
    assert budget["status"] == "PASS", budget


@pytest.mark.parametrize("name", ["comet.json", "radium_girls.json"])
def test_new_retention_functions_never_raise_on_a_legacy_manifest_even_when_run_directly(name):
    """The new checks must be safe to call on ANY manifest shape, including
    one written long before info_role/narration_plan roles existed for it --
    they should return a structured FAIL/NOT_EVALUATED, never throw."""
    project = load_project(str(EXAMPLES_DIR / name))
    result = verify_retention_contract(project)
    assert result["status"] in ("PASS", "FAIL")
    for check_name, check in result["checks"].items():
        assert check["status"] in ("PASS", "FAIL", "NOT_EVALUATED"), (check_name, check)
