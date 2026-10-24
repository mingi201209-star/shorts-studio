"""W1: independently audit actual MP4 bytes against the native production report."""
import hashlib
import json

from shorts_studio.quality_artifact_audit import audit_film


def report(expected_hash):
    shots = (
        "hook_warning", "road_cut", "tire_contact",
        "rumble_mechanism", "shoulder_location", "driver_response",
    )
    return {
        "technical_status": "PASS", "sha256": expected_hash, "source_sha256": "a" * 64,
        "frames": 900, "duration": 30, "resolution": [1080, 1920],
        "samples": 32, "decoded_unique_video_frames": 900,
        "render_frame_seconds": [2.0] * 900,
        "sum_native_render_seconds": 1800.0, "encode_seconds": 15.0,
        "maximum_silence_seconds": .4, "total_silence_seconds": .8,
        "loudness": {"integrated_lufs": -16.8},
        "native_frames": [
            {"frame": n, "sha256": f"{n:064x}", "rgb_sha256": f"{n + 1000:064x}"}
            for n in range(1, 901)
        ],
        "semantic_visual_qa": {"status": "PASS", "results": [
            {"shot": x, "status": "PASS", "margin": .06} for x in shots
        ]},
        "original_video_qa": {"status": "PASS", "results": {
            x: {"status": "PASS"} for x in (
                "visual_activity", "black_opening", "captions_visible",
            )
        }},
        "physics_validated": False, "upload_authorized": False,
    }


def valid_probe():
    return {
        "format": {"duration": "30.000000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080,
             "height": 1920, "r_frame_rate": "30/1", "nb_read_frames": "900"},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000",
             "channels": 1},
        ],
    }


def test_actual_video_bytes_and_native_report_are_both_required(tmp_path):
    video = tmp_path / "episode2.mp4"
    video.write_bytes(b"not-real-video" * 8500)
    original = report(hashlib.sha256(video.read_bytes()).hexdigest())
    result = audit_film(video, original, probe_fn=lambda _: valid_probe())
    assert result["status"] == "EVIDENCE_VALIDATED"
    assert result["sha256_checked"] is True
    assert result["native_technical_status"] == "PASS"
    assert result["original_semantic_status"] == "PASS"
    assert result["human_review"]["status"] == "NOT_REVIEWED"
    assert result["editorial_decision"] == "HOLD"
    assert result["upload_authorized"] is False


def test_failed_or_missing_bytes_are_never_validated(tmp_path):
    video = tmp_path / "episode2.mp4"
    video.write_bytes(b"x" * 101000)
    original = report("a" * 64)
    assert audit_film(video, original, probe_fn=lambda _: valid_probe())["status"] == "EVIDENCE_REJECTED"
    video.unlink()
    assert audit_film(video, original, probe_fn=lambda _: valid_probe())["status"] == "EVIDENCE_REJECTED"


def test_fake_or_partial_mp4_format_and_final_qa_are_rejected(tmp_path):
    video = tmp_path / "episode2.mp4"
    video.write_bytes(b"x" * 101000)
    original = report(hashlib.sha256(video.read_bytes()).hexdigest())
    bad = valid_probe()
    bad["streams"][0]["nb_read_frames"] = "899"
    assert audit_film(video, original, probe_fn=lambda _: bad)["status"] == "EVIDENCE_REJECTED"
    original["semantic_visual_qa"]["results"][1]["status"] = "NOT_EVALUATED"
    assert audit_film(video, original, probe_fn=lambda _: valid_probe())["status"] == "EVIDENCE_REJECTED"


def test_corrupted_report_cannot_promote_upstream_reject_to_validated(tmp_path):
    video = tmp_path / "episode2.mp4"
    video.write_bytes(b"y" * 101000)
    original = report(hashlib.sha256(video.read_bytes()).hexdigest())
    original["upload_authorized"] = True
    assert audit_film(video, original, probe_fn=lambda _: valid_probe())["status"] == "EVIDENCE_REJECTED"
