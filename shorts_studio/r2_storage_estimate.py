"""Conservative R2 Standard storage/operation forecast, never a cloud action.

Usage is treated as held for a full month, regardless of proposed short
retention. 2x largest observed compressed artifact bytes per frame is an
uncertainty allowance, NOT a guaranteed bound on future frames or objects.
Cloudflare Standard prices are those documented 2026-10-01; reverify before
any purchase. There is no cloud SDK, credential, network, file or bill access.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING

R2_MONTHLY_ALLOCATION_KRW = 3_000
STORAGE_FREE_GB_MONTH = 10
CLASS_A_FREE_OPERATIONS = 1_000_000
CLASS_B_FREE_OPERATIONS = 10_000_000
GB_DECIMAL = 1_000_000_000
MILLION = 1_000_000
SAMPLE_UNCERTAINTY_MULTIPLIER = 2
BILLING_UNCERTAINTY_MULTIPLIER = Decimal("1.25")
STORAGE_RATE_USD_PER_GB_MONTH = Decimal("0.015")
CLASS_A_RATE_USD_PER_MILLION = Decimal("4.50")
CLASS_B_RATE_USD_PER_MILLION = Decimal("0.36")


def _count(value: object, name: str, *, upper: int = 10**15) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= upper:
        raise ValueError(f"{name} must be a nonnegative bounded integer")
    return value


def _ceil_units(value: int, unit: int) -> int:
    return (value + unit - 1) // unit


def forecast_r2_standard(
    *,
    sample_frame_artifact_sizes_bytes: list[int],
    frames_per_video: int,
    videos_to_keep: int,
    existing_storage_bytes: int,
    other_new_assets_bytes: int,
    existing_class_a_ops: int,
    planned_class_a_ops: int,
    existing_class_b_ops: int,
    planned_class_b_ops: int,
    usd_to_krw: str | int | Decimal,
    committed_r2_krw_this_month: int,
) -> dict:
    """Estimate full-month R2 Standard upper-planning-cost, no authorization.

    All samples must be measured bytes from independently existing artifacts.
    Zipped CI artifacts are only a planning proxy, not exact native PNG bytes.
    Input existing storage, ops, other assets, and committed invoices MUST be
    supplied by operator; no fabricated accounting or ignored hidden charges.
    """
    sizes = sample_frame_artifact_sizes_bytes
    if not isinstance(sizes, list) or not 1 <= len(sizes) <= 25:
        raise ValueError("sample sizes must be a list of one to 25 positive measured bytes")
    for size in sizes:
        if _count(size, "sample_frame_artifact_sizes_bytes", upper=10**12) <= 0:
            raise ValueError("sample bytes must be positive")
    frames = _count(frames_per_video, "frames_per_video", upper=18_000)
    videos = _count(videos_to_keep, "videos_to_keep", upper=60)
    if not frames or not videos:
        raise ValueError("frames and video count must be positive")

    existing_bytes = _count(existing_storage_bytes, "existing_storage_bytes")
    other_bytes = _count(other_new_assets_bytes, "other_new_assets_bytes")
    existing_a = _count(existing_class_a_ops, "existing_class_a_ops")
    planned_a = _count(planned_class_a_ops, "planned_class_a_ops")
    existing_b = _count(existing_class_b_ops, "existing_class_b_ops")
    planned_b = _count(planned_class_b_ops, "planned_class_b_ops")
    committed = _count(committed_r2_krw_this_month, "committed_r2_krw_this_month")
    if isinstance(usd_to_krw, bool):
        raise ValueError("usd_to_krw must be finite positive numeric")
    try:
        fx = Decimal(str(usd_to_krw))
    except (InvalidOperation, TypeError) as error:
        raise ValueError("usd_to_krw must be finite positive numeric") from error
    if not fx.is_finite() or not 0 < fx <= 1_000_000:
        raise ValueError("usd_to_krw must be finite positive numeric")

    estimated_frame_bytes = max(sizes) * SAMPLE_UNCERTAINTY_MULTIPLIER * frames * videos
    projected_total_bytes = existing_bytes + other_bytes + estimated_frame_bytes
    if projected_total_bytes > 10**15:
        raise ValueError("projected storage volume too large to estimate")
    billed_gb_month = max(
        0, _ceil_units(projected_total_bytes, GB_DECIMAL) - STORAGE_FREE_GB_MONTH
    )
    a_million = _ceil_units(
        max(0, existing_a + planned_a - CLASS_A_FREE_OPERATIONS), MILLION
    )
    b_million = _ceil_units(
        max(0, existing_b + planned_b - CLASS_B_FREE_OPERATIONS), MILLION
    )
    usd = (
        Decimal(billed_gb_month) * STORAGE_RATE_USD_PER_GB_MONTH
        + Decimal(a_million) * CLASS_A_RATE_USD_PER_MILLION
        + Decimal(b_million) * CLASS_B_RATE_USD_PER_MILLION
    )
    conservative_krw = int(
        (usd * fx * BILLING_UNCERTAINTY_MULTIPLIER).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    remaining = max(0, R2_MONTHLY_ALLOCATION_KRW - committed)
    return {
        "status": "ESTIMATE_ONLY",
        "estimated_frame_storage_bytes": estimated_frame_bytes,
        "projected_total_storage_bytes": projected_total_bytes,
        "billable_storage_gb_month": billed_gb_month,
        "billable_class_a_million_blocks": a_million,
        "billable_class_b_million_blocks": b_million,
        "projected_r2_krw_with_25pct_margin": conservative_krw,
        "remaining_r2_budget_krw_before_estimate": remaining,
        "within_r2_allocation": (
            committed < R2_MONTHLY_ALLOCATION_KRW and conservative_krw <= remaining
        ),
        "estimate_is_guaranteed_maximum": False,
        "authorized_to_create_bucket": False,
        "provider_spend_cap_enforced": False,
    }
