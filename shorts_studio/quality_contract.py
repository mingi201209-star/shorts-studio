"""Fail-closed evidence audit for an episode's narration-to-footage contract.

This module never declares technical or editorial acceptance; it only reports
whether each narration beat has independently verifiable evidence attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import hashlib


@dataclass(frozen=True)
class Beat:
    beat_id: str
    start_ms: int
    end_ms: int
    narration: str
    visual_claim: str
    footage_path: str | None = None
    footage_sha256: str | None = None
    editorial_review: str = "NOT_EVALUATED"


@dataclass(frozen=True)
class AuditResult:
    status: str
    findings: tuple[str, ...]


def audit_beats(beats: Iterable[Beat], *, root: Path) -> AuditResult:
    """Audit every beat; PASS means evidence complete, never video acceptance.

    All file references must stay inside ``root``. Empty episodes fail closed.
    Editorial review must be an explicit PASS; technical QA remains separate.
    """
    try:
        root = root.resolve()
    except (OSError, RuntimeError):
        return AuditResult("HOLD", ("episode: evidence root cannot be resolved",))
    items = list(beats)
    findings: list[str] = []
    if not items:
        return AuditResult("HOLD", ("episode: no narration beats",))
    seen: set[str] = set()
    previous_end = 0
    for beat in items:
        prefix = beat.beat_id or "<unnamed>"
        if not beat.beat_id or beat.beat_id in seen:
            findings.append(f"{prefix}: missing or duplicate beat id")
        seen.add(beat.beat_id)
        if beat.start_ms < previous_end or beat.end_ms <= beat.start_ms:
            findings.append(f"{prefix}: invalid or overlapping timing")
        if beat.start_ms != previous_end:
            findings.append(f"{prefix}: timeline gap or unordered beat")
        previous_end = max(previous_end, beat.end_ms)
        if not beat.narration.strip() or not beat.visual_claim.strip():
            findings.append(f"{prefix}: missing narration or visual claim")
        if not beat.footage_path or not beat.footage_sha256:
            findings.append(f"{prefix}: footage path or SHA256 missing")
        else:
            try:
                candidate = (root / beat.footage_path).resolve()
                valid_candidate = candidate.is_relative_to(root) and candidate.is_file()
            except (OSError, RuntimeError):
                valid_candidate = False
            if not valid_candidate:
                findings.append(f"{prefix}: footage missing or outside evidence root")
            elif len(beat.footage_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in beat.footage_sha256
            ):
                findings.append(f"{prefix}: invalid SHA256")
            else:
                digest = hashlib.sha256()
                try:
                    with candidate.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                except OSError:
                    findings.append(f"{prefix}: footage unreadable during audit")
                else:
                    if digest.hexdigest() != beat.footage_sha256:
                        findings.append(f"{prefix}: footage SHA256 mismatch")
        if beat.editorial_review != "PASS":
            findings.append(f"{prefix}: editorial review not PASS")
    return AuditResult("HOLD" if findings else "EVIDENCE_COMPLETE", tuple(findings))
