import hashlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from shorts_studio.dual_mode_preview import Handler, byte_range


@pytest.fixture
def review(tmp_path):
    content = b"0123456789"
    (tmp_path / "clip.mp4").write_bytes(content)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "files": {
                    "clip.mp4": {
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content),
                        "mime": "video/mp4",
                        "title": "Fixture",
                        "frames": 2,
                    }
                },
                "timings": {"Fixture": 1.0},
            }
        )
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.proof_root = tmp_path
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", tmp_path
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_review_range_and_head_match_bound_bytes(review):
    base, _root = review
    request = urllib.request.Request(base + "/clip.mp4", headers={"Range": "bytes=2-5"})
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 206
        assert response.read() == b"2345"
        assert response.headers["Content-Range"] == "bytes 2-5/10"
        assert response.headers["Cache-Control"] == "no-store"
    with urllib.request.urlopen(
        urllib.request.Request(base + "/clip.mp4", method="HEAD"), timeout=5
    ) as response:
        assert response.status == 200
        assert response.headers["Content-Length"] == "10"
        assert response.read() == b""


def test_review_does_not_serve_changed_proof_or_arbitrary_paths(review):
    base, root = review
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(base + "/%2e%2e/manifest.json", timeout=5)
    assert error.value.code == 404
    (root / "clip.mp4").write_bytes(b"tampered")
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(base + "/clip.mp4", timeout=5)
    assert error.value.code == 503


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, (0, 9, False)),
        ("bytes=0-", (0, 9, True)),
        ("bytes=-3", (7, 9, True)),
        ("bytes=3-100", (3, 9, True)),
    ],
)
def test_byte_range(header, expected):
    assert byte_range(header, 10) == expected


@pytest.mark.parametrize("header", ["bytes=20-", "bytes=9-2", "bytes=-0", "bytes=0-1,3-4"])
def test_invalid_byte_range(header):
    with pytest.raises(ValueError):
        byte_range(header, 10)
