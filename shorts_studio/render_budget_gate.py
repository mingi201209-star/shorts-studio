"""Inert estimate-only guard for separately authorized GPU pilots.

This module never provisions, stops, pays for, or connects to a cloud service.
An estimate is not an enforceable provider spending limit.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
from pathlib import Path

MONTHLY_CEILING_KRW = 50_000
GPU_ALLOCATION_KRW = 30_000
VPS_ALLOCATION_KRW = 8_000
R2_ALLOCATION_KRW = 3_000
CONTINGENCY_KRW = 9_000
MAX_QUOTED_AGE = timedelta(minutes=15)
MAX_SINGLE_LEASE_HOURS = Decimal("2")
UNCERTAINTY_FACTOR = Decimal("1.25")
FIELDS = frozenset({
    "quoted_at_utc",
    "billing_month_utc",
    "gpu_pending_reserved_krw_this_month",
    "gpu_usd_per_hour",
    "instance_storage_usd_per_hour",
    "transfer_usd_per_gb",
    "billable_hours",
    "transfer_gb",
    "usd_to_krw",
    "gpu_spent_krw_this_month",
    "vps_cost_krw_this_month",
    "r2_cost_krw_this_month",
    "other_committed_krw_this_month",
})


def _money(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"missing or invalid numeric field: {name}")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"missing or invalid numeric field: {name}") from error
    if not result.is_finite() or result < 0:
        raise ValueError(f"missing or invalid numeric field: {name}")
    return result


def estimate_gpu_lease(quote: dict, *, now: datetime | None = None) -> dict:
    """Validate a complete recent operator quote; compute a non-binding estimate.

    Unknown charges are NOT zero: missing/extra fields are rejected. The operator
    must separately confirm provider fees, limits, teardown, and invoice status.
    """
    if not isinstance(quote, dict) or set(quote) != FIELDS:
        raise ValueError("quote must contain exactly the documented fields")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    try:
        quoted = datetime.fromisoformat(quote["quoted_at_utc"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("quoted_at_utc must be ISO-8601 with timezone") from error
    if quoted.tzinfo is None:
        raise ValueError("quoted_at_utc must have timezone")
    age = now.astimezone(timezone.utc) - quoted.astimezone(timezone.utc)
    if not timedelta(0) <= age <= MAX_QUOTED_AGE:
        raise ValueError("GPU quote is future-dated or older than fifteen minutes")

    current_month = now.astimezone(timezone.utc).strftime("%Y-%m")
    quoted_month = quoted.astimezone(timezone.utc).strftime("%Y-%m")
    if quote["billing_month_utc"] != current_month or quoted_month != current_month:
        raise ValueError("billing month mismatch or quote crosses a UTC month boundary")

    fields = {
        k: _money(v, k) for k, v in quote.items()
        if k not in {"quoted_at_utc", "billing_month_utc"}
    }
    hours = fields["billable_hours"]
    fx = fields["usd_to_krw"]
    if not 0 < hours <= MAX_SINGLE_LEASE_HOURS or fx <= 0:
        raise ValueError("invalid lease duration, single-lease cap or FX rate")

    vps = fields["vps_cost_krw_this_month"]
    r2 = fields["r2_cost_krw_this_month"]
    spent_gpu = fields["gpu_spent_krw_this_month"]
    pending_gpu = fields["gpu_pending_reserved_krw_this_month"]
    committed_gpu = spent_gpu + pending_gpu
    other = fields["other_committed_krw_this_month"]

    usd_estimate = (
        (fields["gpu_usd_per_hour"] + fields["instance_storage_usd_per_hour"]) * hours
        + fields["transfer_usd_per_gb"] * fields["transfer_gb"]
    )
    reserved_krw = int(
        (usd_estimate * fx * UNCERTAINTY_FACTOR).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    remaining_gpu = max(0, GPU_ALLOCATION_KRW - committed_gpu)
    remaining_total = max(
        0, MONTHLY_CEILING_KRW - CONTINGENCY_KRW - vps - r2 - other - committed_gpu
    )
    available = min(remaining_gpu, remaining_total)
    within_budget = (
        vps <= VPS_ALLOCATION_KRW
        and r2 <= R2_ALLOCATION_KRW
        and other == 0
        and committed_gpu < GPU_ALLOCATION_KRW
        and reserved_krw > 0
        and reserved_krw <= available
    )
    return {
        "status": "ESTIMATE_ONLY",
        "within_planned_budget": bool(within_budget),
        "projected_gpu_krw_with_25pct_margin": reserved_krw,
        "remaining_allowed_gpu_krw": int(available),
        "pending_gpu_reserved_krw_this_month": int(pending_gpu),
        "billing_month_utc": current_month,
        "total_monthly_ceiling_krw": MONTHLY_CEILING_KRW,
        "provider_spend_cap_enforced": False,
        "authorized_to_provision": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quote", type=Path, required=True)
    args = parser.parse_args()
    try:
        quote = json.loads(args.quote.read_text(encoding="utf-8"))
        result = estimate_gpu_lease(quote)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "BLOCK", "reason": str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["within_planned_budget"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
