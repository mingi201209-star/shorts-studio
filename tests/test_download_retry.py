"""_download must retry transient server errors (rate limiting, brief
outages) with bounded backoff -- this is a real production issue: Wikimedia
returned HTTP 429 on a real render-smoke run after repeated CI renders in a
short window. Permanent client errors must fail immediately, not waste the
recovery budget retrying something that can never succeed.
"""
import time
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


class SlowTrickleResponse:
    """Every read() returns quickly (well under any per-read socket timeout)
    but the cumulative wall-clock time across many small reads adds up --
    the exact shape of a real production hang: a Radium Girls render's
    asset download stalled for 18+ minutes on a scene's first (uncached)
    asset, far past the 4-attempt/60s-each budget _download appears to
    promise, because `urlopen(..., timeout=N)` only ever bounds a single
    read, never the whole transfer."""
    def __init__(self, chunk=b"x", n_chunks=1000, delay=0.02):
        self.chunk = chunk; self.n_chunks = n_chunks; self.delay = delay; self._sent = 0
    def read(self, n=-1):
        if self._sent >= self.n_chunks:
            return b""
        time.sleep(self.delay)
        self._sent += 1
        return self.chunk

def test_copy_with_deadline_raises_on_slow_trickle(tmp_path):
    src = SlowTrickleResponse(n_chunks=1000, delay=0.02)
    with (tmp_path / "f.jpg").open("wb") as dst:
        with pytest.raises(TimeoutError):
            R._copy_with_deadline(src, dst, deadline_seconds=0.1)

def test_copy_with_deadline_succeeds_within_budget(tmp_path):
    src = SlowTrickleResponse(chunk=b"ok", n_chunks=1, delay=0.0)
    out = tmp_path / "f.jpg"
    with out.open("wb") as dst:
        R._copy_with_deadline(src, dst, deadline_seconds=1.0)
    assert out.read_bytes() == b"ok"

def test_download_never_hangs_on_a_persistent_slow_trickle(tmp_path, monkeypatch):
    """End-to-end: a server that never finishes within the wall-clock
    deadline must be treated like any other transient failure (retried,
    then raised after exhausting attempts) -- never left running forever,
    which is exactly what happened in production before _copy_with_deadline
    existed (a bare shutil.copyfileobj has no such cap).

    Uses a fake monotonic clock (advanced by each read()) rather than a real
    time.sleep-based delay: _download's own retry backoff also calls
    time.sleep, and that and _copy_with_deadline's read-delay simulation
    would otherwise fight over the same monkeypatched time.sleep (patching
    it to a no-op to skip the real backoff would silently erase the
    trickle's simulated delay too, since both go through the same `time`
    module)."""
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R, "_DOWNLOAD_DEADLINE_SECONDS", 0.05)
    fake_clock = {"t": 0.0}
    monkeypatch.setattr(R.time, "monotonic", lambda: fake_clock["t"])
    class FakeClockTrickleResponse:
        def __init__(self): self._sent = 0
        def read(self, n=-1):
            if self._sent >= 1000:
                return b""
            fake_clock["t"] += 0.02
            self._sent += 1
            return b"x"
    class SlowCtx:
        def __enter__(self): return FakeClockTrickleResponse()
        def __exit__(self, *a): return False
    calls = {"n": 0}
    def fake_urlopen(req, timeout=60):
        calls["n"] += 1
        return SlowCtx()
    monkeypatch.setattr(R.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(TimeoutError):
        R._download("https://example.com/slow.png", tmp_path / "f.jpg", max_attempts=3)
    assert calls["n"] == 3
