"""_download must retry transient server errors (rate limiting, brief
outages) with bounded backoff -- this is a real production issue: Wikimedia
returned HTTP 429 on a real render-smoke run after repeated CI renders in a
short window. Permanent client errors must fail immediately, not waste the
recovery budget retrying something that can never succeed.
"""
import urllib.error
import pytest
import shorts_studio.render as R

class FakeResponse:
    def __init__(self, data=b"ok"): self.data = data; self._sent = False
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n=-1):
        if self._sent: return b""
        self._sent = True
        return self.data

def test_retries_transient_429_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    calls = {"n": 0}
    def fake_urlopen(req, timeout=60):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return FakeResponse()
    monkeypatch.setattr(R.urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "f.jpg"
    result = R._download("https://example.com/x.jpg", out)
    assert result == out
    assert out.read_bytes() == b"ok"
    assert calls["n"] == 3

def test_permanent_404_fails_immediately_without_retry(tmp_path, monkeypatch):
    slept = []
    monkeypatch.setattr(R.time, "sleep", lambda s: slept.append(s))
    calls = {"n": 0}
    def fake_urlopen(req, timeout=60):
        calls["n"] += 1
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(R.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        R._download("https://example.com/missing.jpg", tmp_path / "f.jpg")
    assert calls["n"] == 1
    assert slept == []

def test_exhausting_retries_on_persistent_429_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    def fake_urlopen(req, timeout=60):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(R.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        R._download("https://example.com/x.jpg", tmp_path / "f.jpg", max_attempts=3)
