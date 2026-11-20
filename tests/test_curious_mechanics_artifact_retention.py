import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/curious-mechanics-final-assembly.yml"


def test_review_assembly_is_manual_and_retains_artifact_for_90_days():
    text = WORKFLOW.read_text()
    trigger = text.split("\npermissions:", 1)[0]
    assert re.search(r"(?m)^  workflow_dispatch:\s*$", trigger)
    assert not re.search(r"(?m)^  push:\s*$", trigger)
    assert re.search(r"(?m)^\s+retention-days:\s*90\s*$", text)
    assert "runs-on: ubuntu-24.04" in text


def test_missing_private_export_credentials_fail_before_ssh():
    text = WORKFLOW.read_text()
    assert "EXPORT_KEY" in text and "EXPORT_HOST" in text and "EXPORT_KNOWN_HOSTS" in text
    assert "assembly is blocked" in text
    assert text.index("assembly is blocked") < text.index("ssh -T")
