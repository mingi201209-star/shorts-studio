import pytest

from shorts_studio.studio_org.film_pipeline import finish_film
from shorts_studio.studio_org.ledger import TaskLedger


def test_encoding_refused_outside_github(tmp_path, monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    ledger = TaskLedger()
    with pytest.raises(RuntimeError, match='GitHub Actions'):
        finish_film(tmp_path, tmp_path, tmp_path / 'out', ledger)
    assert ledger.all() == []


def test_missing_native_never_creates_success(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    ledger = TaskLedger()
    with pytest.raises(ValueError, match='No actual native'):
        finish_film(tmp_path, tmp_path, tmp_path / 'out', ledger)
    assert ledger.all() == []
