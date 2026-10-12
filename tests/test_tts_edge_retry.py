"""Regression coverage for the Edge TTS endpoint shim and handshake retry.

The render-smoke runs on PR #45 died before any gate ran: Microsoft began
answering the synthesis websocket on the legacy host with 403 (edge-tts issue
#490) and `_synthesize_sentence` made exactly one call. These tests drive the
real `_synthesize_sentence` against a fake `edge_tts.Communicate`, so the
behaviour is exercised without the network."""
from __future__ import annotations

import asyncio

import sys
import types

import aiohttp
import pytest

import shorts_studio.tts as tts


def _handshake_403():
    return aiohttp.WSServerHandshakeError(
        request_info=None, history=(), status=403, message="Invalid response status"
    )


def _install_fake_edge(monkeypatch, failures_before_success, error_factory=_handshake_403, fail_midstream=False):
    state = {"calls": 0, "sleeps": []}

    class FakeCommunicate:
        def __init__(self, text, voice, **kwargs):
            self.text = text

        async def stream(self):
            state["calls"] += 1
            failing = state["calls"] <= failures_before_success
            if failing and not fail_midstream:
                raise error_factory()
            yield {"type": "audio", "data": b"AAAA"}
            yield {"type": "WordBoundary", "offset": 1_000_000, "duration": 2_000_000, "text": "빗길"}
            if failing:
                raise error_factory()
            yield {"type": "audio", "data": b"BBBB"}

    async def fake_sleep(seconds):
        state["sleeps"].append(seconds)

    # `_synthesize_sentence` imports edge_tts lazily, and other test modules
    # leave their own doubles in sys.modules, so install this one explicitly.
    fake_edge = types.ModuleType("edge_tts")
    fake_edge.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge)
    monkeypatch.setattr(tts, "_use_current_edge_endpoint", lambda: False)
    monkeypatch.setattr(tts.asyncio, "sleep", fake_sleep)
    return state


def _run():
    return asyncio.run(tts._synthesize_sentence("빗길", "voice", "+0%", "+0Hz", "+0%"))


def test_transient_handshake_403_is_retried_with_backoff(monkeypatch):
    state = _install_fake_edge(monkeypatch, failures_before_success=2)
    audio, words = _run()
    assert state["calls"] == 3
    assert state["sleeps"] == [2.0, 4.0]
    assert audio == b"AAAABBBB"
    assert [(w.text, w.start, w.end) for w in words] == [("빗길", 0.1, pytest.approx(0.3))]


def test_failed_attempt_never_leaks_partial_audio_or_boundaries(monkeypatch):
    """An attempt that dies mid-stream must contribute nothing: the returned
    audio and word timings come from one single complete synthesis."""
    state = _install_fake_edge(monkeypatch, failures_before_success=1, fail_midstream=True)
    audio, words = _run()
    assert state["calls"] == 2
    assert audio == b"AAAABBBB"
    assert len(words) == 1


def test_persistent_outage_fails_closed_with_the_real_error(monkeypatch):
    state = _install_fake_edge(monkeypatch, failures_before_success=10**6)
    with pytest.raises(aiohttp.WSServerHandshakeError) as excinfo:
        _run()
    assert excinfo.value.status == 403
    assert state["calls"] == tts._EDGE_MAX_ATTEMPTS
    assert state["sleeps"] == [2.0, 4.0, 8.0, 16.0]


def test_non_network_errors_are_not_retried(monkeypatch):
    state = _install_fake_edge(monkeypatch, failures_before_success=10**6, error_factory=lambda: ValueError("bad voice"))
    with pytest.raises(ValueError, match="bad voice"):
        _run()
    assert state["calls"] == 1
    assert state["sleeps"] == []


TOKEN = "TESTTOKEN"


def _install_fake_edge_package(monkeypatch, wss_url):
    package = types.ModuleType("edge_tts")
    package.__path__ = []
    communicate = types.ModuleType("edge_tts.communicate")
    communicate.WSS_URL = wss_url
    constants = types.ModuleType("edge_tts.constants")
    constants.TRUSTED_CLIENT_TOKEN = TOKEN
    package.communicate = communicate
    package.constants = constants
    monkeypatch.setitem(sys.modules, "edge_tts", package)
    monkeypatch.setitem(sys.modules, "edge_tts.communicate", communicate)
    monkeypatch.setitem(sys.modules, "edge_tts.constants", constants)
    return communicate


def test_legacy_endpoint_is_replaced_by_the_one_edge_uses(monkeypatch):
    communicate = _install_fake_edge_package(
        monkeypatch,
        "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=" + TOKEN,
    )
    assert tts._use_current_edge_endpoint() is True
    assert communicate.WSS_URL == (
        "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
        "?Ocp-Apim-Subscription-Key=" + TOKEN
    )
    assert tts._use_current_edge_endpoint() is False


def test_an_edge_tts_release_with_its_own_endpoint_is_left_untouched(monkeypatch):
    shipped = "wss://example.invalid/some/future/endpoint?key=1"
    communicate = _install_fake_edge_package(monkeypatch, shipped)
    assert tts._use_current_edge_endpoint() is False
    assert communicate.WSS_URL == shipped


def test_a_provider_without_the_edge_tts_layout_is_left_alone(monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", types.ModuleType("edge_tts"))
    monkeypatch.delitem(sys.modules, "edge_tts.communicate", raising=False)
    assert tts._use_current_edge_endpoint() is False


def test_installed_edge_tts_is_the_layout_the_shim_expects():
    """Guards the shim against a silent no-op: the real installed package must
    expose the two names it reads."""
    import importlib.util
    for name in ("communicate", "constants"):
        assert importlib.util.find_spec("edge_tts." + name) is not None
    source = importlib.util.find_spec("edge_tts.communicate").loader.get_source("edge_tts.communicate")
    assert "WSS_URL" in source
