"""The R2 VPS token bootstrap requires an actual local terminal, not MCP logs."""
from pathlib import Path
import os
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "configure_r2_remote.sh"


def test_remote_r2_secret_bootstrap_must_be_interactive(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        text=True,
        input="",
        capture_output=True,
        env={**os.environ, "HOME": str(tmp_path)},
        timeout=5,
    )
    assert result.returncode == 2
    assert "interactive terminal required" in result.stderr
    assert not (tmp_path / ".config").exists()


def test_remote_r2_bootstrap_has_valid_bash_syntax():
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
