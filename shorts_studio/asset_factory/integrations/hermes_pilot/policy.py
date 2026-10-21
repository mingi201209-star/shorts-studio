"""Pure host capacity / spend-zero admission guards for offline mock work."""

import math
from dataclasses import dataclass

_GIB = 1024**3
_MIB = 1024**2


@dataclass(frozen=True)
class ResourceView:
    mem_available_bytes: int
    disk_free_ratio: float
    pending_proposals: int
    accepted_this_session: int
    active_mock_workers: int
    codex_processes: int


def assess_ingress(view: ResourceView) -> str:
    """Decide whether to admit one more mock-only request from trusted metrics."""
    if not isinstance(view, ResourceView):
        raise ValueError("trusted host resource snapshot required")  # noqa: TRY004
    for name in ("mem_available_bytes", "pending_proposals", "accepted_this_session",
                 "active_mock_workers", "codex_processes"):
        number = getattr(view, name)
        if type(number) is not int or number < 0:
            raise ValueError("invalid host metric")
    free = view.disk_free_ratio
    if type(free) not in (float, int) or not math.isfinite(free) or not 0 <= free <= 1:
        raise ValueError("invalid disk free ratio")
    if view.mem_available_bytes < 512 * _MIB:
        return "blocked_memory"
    if view.disk_free_ratio < 0.15:
        return "blocked_disk"
    if view.pending_proposals >= 20 or view.accepted_this_session >= 3:
        return "blocked_capacity"
    if view.active_mock_workers >= 1 or view.codex_processes > 0:
        return "blocked_worker"
    if view.mem_available_bytes < _GIB:
        return "warn_memory"
    return "allow"
