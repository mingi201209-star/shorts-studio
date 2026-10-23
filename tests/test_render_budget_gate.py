"""Unit coverage for the inert remote-render spending preflight."""
from datetime import datetime, timedelta, timezone

import pytest

from shorts_studio.render_budget_gate import estimate_gpu_lease

NOW = datetime(2026, 10, 23, 7, 0, tzinfo=timezone.utc)


def good_quote():
    return {
        "quoted_at_utc": (NOW - timedelta(minutes=1)).isoformat(),
        "billing_month_utc": "2026-10",
        "gpu_pending_reserved_krw_this_month": "0",
        "gpu_usd_per_hour": "0.24",
        "instance_storage_usd_per_hour": "0.03",
        "transfer_usd_per_gb": "0.10",
        "billable_hours": "1.5",
        "transfer_gb": "2",
        "usd_to_krw": "1500",
        "gpu_spent_krw_this_month": "1000",
        "vps_cost_krw_this_month": "8000",
        "r2_cost_krw_this_month": "3000",
        "other_committed_krw_this_month": "0",
    }


def test_only_returns_an_estimate_never_a_provisioning_authorization():
    result = estimate_gpu_lease(good_quote(), now=NOW)
    assert result["status"] == "ESTIMATE_ONLY"
    assert result["within_planned_budget"] is True
    assert result["authorized_to_provision"] is False
    assert result["provider_spend_cap_enforced"] is False
    assert 0 < result["projected_gpu_krw_with_25pct_margin"] < 30000


@pytest.mark.parametrize("missing", [
    "gpu_usd_per_hour", "instance_storage_usd_per_hour",
    "transfer_usd_per_gb", "usd_to_krw", "r2_cost_krw_this_month",
])
def test_unknown_price_or_charge_is_not_treated_as_free(missing):
    q = good_quote()
    q.pop(missing)
    with pytest.raises(ValueError):
        estimate_gpu_lease(q, now=NOW)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-0.01", True, None])
def test_invalid_gpu_price_fails_closed(value):
    q = good_quote()
    q["gpu_usd_per_hour"] = value
    with pytest.raises(ValueError):
        estimate_gpu_lease(q, now=NOW)


@pytest.mark.parametrize("hours", ["0", "2.1", "100000", "-1"])
def test_out_of_bounds_single_lease_is_rejected(hours):
    q = good_quote()
    q["billable_hours"] = hours
    with pytest.raises(ValueError):
        estimate_gpu_lease(q, now=NOW)


def test_stale_quote_is_rejected():
    q = good_quote()
    q["quoted_at_utc"] = (NOW - timedelta(minutes=16)).isoformat()
    with pytest.raises(ValueError, match="older"):
        estimate_gpu_lease(q, now=NOW)


def test_future_quote_is_rejected():
    q = good_quote()
    q["quoted_at_utc"] = (NOW + timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError, match="future"):
        estimate_gpu_lease(q, now=NOW)


def test_no_gpu_remaining_blocks():
    q = good_quote()
    q["gpu_spent_krw_this_month"] = "30000"
    r = estimate_gpu_lease(q, now=NOW)
    assert r["within_planned_budget"] is False
    assert r["remaining_allowed_gpu_krw"] == 0


@pytest.mark.parametrize("key,value", [
    ("vps_cost_krw_this_month", "8001"),
    ("r2_cost_krw_this_month", "3001"),
    ("other_committed_krw_this_month", "1"),
])
def test_over_budget_fixed_fees_block(key, value):
    q = good_quote()
    q[key] = value
    assert estimate_gpu_lease(q, now=NOW)["within_planned_budget"] is False


def test_large_bandwidth_fee_blocks():
    q = good_quote()
    q["transfer_gb"] = "10000"
    assert estimate_gpu_lease(q, now=NOW)["within_planned_budget"] is False


def test_unknown_extra_fields_are_refused():
    q = good_quote()
    q["free_gpu_credits_unverified"] = "9999"
    with pytest.raises(ValueError):
        estimate_gpu_lease(q, now=NOW)


def test_missing_timezone_is_rejected():
    q = good_quote()
    q["quoted_at_utc"] = "2026-10-23T06:59:00"
    with pytest.raises(ValueError, match="timezone"):
        estimate_gpu_lease(q, now=NOW)


def test_pending_gpu_reservations_reduce_available_monthly_budget():
    q = good_quote()
    q["billing_month_utc"] = "2026-10"
    q["gpu_pending_reserved_krw_this_month"] = "28500"
    result = estimate_gpu_lease(q, now=NOW)
    assert result["remaining_allowed_gpu_krw"] == 500
    assert result["within_planned_budget"] is False


def test_pending_reservations_count_toward_combined_monthly_ceiling():
    q = good_quote()
    q["billing_month_utc"] = "2026-10"
    q["gpu_pending_reserved_krw_this_month"] = "6000"
    q["vps_cost_krw_this_month"] = "8000"
    q["r2_cost_krw_this_month"] = "3000"
    result = estimate_gpu_lease(q, now=NOW)
    assert result["remaining_allowed_gpu_krw"] == 23000
    assert result["within_planned_budget"] is True


def test_previous_month_quote_rejected_even_within_fifteen_minutes():
    boundary = datetime(2026, 11, 1, 0, 5, tzinfo=timezone.utc)
    q = good_quote()
    q["quoted_at_utc"] = (boundary - timedelta(minutes=10)).isoformat()
    q["billing_month_utc"] = "2026-11"
    q["gpu_pending_reserved_krw_this_month"] = "0"
    with pytest.raises(ValueError, match="billing month"):
        estimate_gpu_lease(q, now=boundary)


def test_reported_billing_month_must_match_current_utc_month():
    q = good_quote()
    q["billing_month_utc"] = "2026-09"
    q["gpu_pending_reserved_krw_this_month"] = "0"
    with pytest.raises(ValueError, match="billing month"):
        estimate_gpu_lease(q, now=NOW)
