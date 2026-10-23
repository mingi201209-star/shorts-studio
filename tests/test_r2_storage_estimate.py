"""Pure conservative Cloudflare R2 Standard cost forecasts (no cloud I/O)."""
import pytest

from shorts_studio.r2_storage_estimate import forecast_r2_standard


def quote(**changes):
    base = {
        "sample_frame_artifact_sizes_bytes": [1_775_033, 1_868_225, 1_824_444],
        "frames_per_video": 900,
        "videos_to_keep": 1,
        "existing_storage_bytes": 0,
        "other_new_assets_bytes": 50_000_000,
        "existing_class_a_ops": 10,
        "planned_class_a_ops": 900,
        "existing_class_b_ops": 20,
        "planned_class_b_ops": 900,
        "usd_to_krw": "1500",
        "committed_r2_krw_this_month": 0,
    }
    base.update(changes)
    return base


def test_real_sample_size_forecast_is_conservative_and_inert():
    r = forecast_r2_standard(**quote())
    assert r["status"] == "ESTIMATE_ONLY"
    assert r["estimated_frame_storage_bytes"] == 1_868_225 * 900 * 2
    assert r["projected_total_storage_bytes"] == r["estimated_frame_storage_bytes"] + 50_000_000
    assert r["billable_storage_gb_month"] == 0
    assert r["projected_r2_krw_with_25pct_margin"] == 0
    assert r["within_r2_allocation"] is True
    assert r["authorized_to_create_bucket"] is False
    assert r["provider_spend_cap_enforced"] is False


def test_28_episodes_with_month_long_retention_include_billable_storage():
    r = forecast_r2_standard(**quote(videos_to_keep=28))
    assert r["projected_total_storage_bytes"] > 90_000_000_000
    assert r["billable_storage_gb_month"] >= 84
    assert 0 < r["projected_r2_krw_with_25pct_margin"] < 3000
    assert r["within_r2_allocation"] is True


def test_large_archive_exceeds_r2_budget():
    r = forecast_r2_standard(**quote(videos_to_keep=60))
    assert r["within_r2_allocation"] is False
    assert r["authorized_to_create_bucket"] is False


def test_class_a_billable_request_rounding_counts_full_million_block():
    r = forecast_r2_standard(**quote(
        existing_class_a_ops=1_000_000, planned_class_a_ops=1))
    assert r["billable_class_a_million_blocks"] == 1
    assert r["projected_r2_krw_with_25pct_margin"] > 3000
    assert r["within_r2_allocation"] is False


def test_class_b_billable_request_rounding_counts_full_million_block():
    r = forecast_r2_standard(**quote(
        existing_class_b_ops=10_000_000, planned_class_b_ops=1))
    assert r["billable_class_b_million_blocks"] == 1
    assert r["projected_r2_krw_with_25pct_margin"] > 0


def test_existing_storage_and_existing_committed_cost_must_count():
    r = forecast_r2_standard(**quote(
        existing_storage_bytes=10_000_000_000,
        committed_r2_krw_this_month=2900))
    assert r["billable_storage_gb_month"] >= 4
    assert r["within_r2_allocation"] is False


@pytest.mark.parametrize("key,value", [
    ("sample_frame_artifact_sizes_bytes", []),
    ("sample_frame_artifact_sizes_bytes", [True]),
    ("sample_frame_artifact_sizes_bytes", [100, 0]),
    ("sample_frame_artifact_sizes_bytes", "1000"),
    ("videos_to_keep", 0),
    ("videos_to_keep", 61),
    ("frames_per_video", -1),
    ("frames_per_video", True),
    ("existing_storage_bytes", -1),
    ("other_new_assets_bytes", -10),
    ("planned_class_b_ops", -1),
    ("usd_to_krw", "NaN"),
    ("usd_to_krw", "-1500"),
    ("usd_to_krw", True),
    ("committed_r2_krw_this_month", -1),
])
def test_unverifiable_size_count_or_fx_blocks(key, value):
    with pytest.raises(ValueError):
        forecast_r2_standard(**quote(**{key: value}))
