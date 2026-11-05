import hashlib

from shorts_studio.quality_contract import Beat, audit_beats


def beat(data, *, review="PASS", path="shot.mp4", start=0, end=1000):
    return Beat("shot1", start, end, "Wheel hits rumble strip", "Driver steers", path,
                hashlib.sha256(data).hexdigest(), review)


def test_complete_evidence_is_not_video_approval(tmp_path):
    (tmp_path / "shot.mp4").write_bytes(b"real footage bytes")
    result = audit_beats([beat(b"real footage bytes")], root=tmp_path)
    assert result.status == "EVIDENCE_COMPLETE"
    assert not result.findings


def test_missing_editorial_review_holds(tmp_path):
    (tmp_path / "shot.mp4").write_bytes(b"video")
    result = audit_beats([beat(b"video", review="NOT_EVALUATED")], root=tmp_path)
    assert result.status == "HOLD"
    assert "editorial review not PASS" in result.findings[0]


def test_wrong_hash_holds(tmp_path):
    (tmp_path / "shot.mp4").write_bytes(b"different")
    result = audit_beats([beat(b"expected")], root=tmp_path)
    assert "SHA256 mismatch" in result.findings[0]


def test_missing_footage_holds(tmp_path):
    result = audit_beats([beat(b"missing")], root=tmp_path)
    assert result.status == "HOLD"


def test_path_escape_holds(tmp_path):
    result = audit_beats([beat(b"x", path="../outside.mp4")], root=tmp_path)
    assert result.status == "HOLD"


def test_empty_episode_holds(tmp_path):
    assert audit_beats([], root=tmp_path).status == "HOLD"


def test_timing_gap_holds(tmp_path):
    (tmp_path / "shot.mp4").write_bytes(b"x")
    assert audit_beats([beat(b"x", start=100)], root=tmp_path).status == "HOLD"


def test_duplicate_ids_hold(tmp_path):
    (tmp_path / "shot.mp4").write_bytes(b"x")
    assert audit_beats([beat(b"x"), beat(b"x", start=1000, end=2000)], root=tmp_path).status == "HOLD"


def test_unreadable_footage_holds_instead_of_crashing(tmp_path, monkeypatch):
    from pathlib import Path

    (tmp_path / "shot.mp4").write_bytes(b"x")
    original_open = Path.open

    def blocked_open(path, *args, **kwargs):
        if path.name == "shot.mp4":
            raise PermissionError("simulated unreadable file")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", blocked_open)
    result = audit_beats([beat(b"x")], root=tmp_path)
    assert result.status == "HOLD"
    assert any("unreadable during audit" in finding for finding in result.findings)
