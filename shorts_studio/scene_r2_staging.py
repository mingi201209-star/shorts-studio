"""Opt-in, offline-only staging of each rendered scene clip through the
already-reviewed R2 verified-handoff primitives (shorts_studio.r2_handoff).

PR #65 (the r2_handoff package itself) deliberately scoped OUT any renderer
hook: "No renderer hook... Existing project entry points... renderer...
do not need modification." This module honors that: it never modifies
anything under shorts_studio/r2_handoff/, it only ever calls that package's
already-tested, already-reviewed public functions from a separate caller
-- the render engine's own trust boundary and r2_handoff's own trust
boundary stay exactly as independently reviewed.

Only the STAGE half of the handoff is implemented here: plan_source() +
stage_source() + StateStore.create_job(). That is a pure, local operation --
it hashes and chunks the rendered clip, copies the chunks into a private,
permission-locked spool, and records a durable SQLite job -- with NO network
call and NO credential of any kind read, exactly like running
`python -m shorts_studio.r2_handoff plan --save-plan` by hand. The actual
upload (`r2_handoff apply --apply`) is intentionally NOT reimplemented here:
it requires a human-audited ~/.config/shorts-studio/wrangler-audit.json and
a real `wrangler login` (see shorts_studio/r2_handoff/oauth.py), neither of
which this module creates, bypasses, or has any way to test in this
environment. stage_scene_clip() returns the job_id precisely so an operator
who HAS completed that audit can run the existing, unmodified CLI:

    python -m shorts_studio.r2_handoff apply --job <job_id> --apply \\
        --wrangler /path/to/wrangler --audit-file ~/.config/shorts-studio/wrangler-audit.json

Never enabled by default: Project.enable_r2_scene_staging defaults to False
(see models.py) and every existing manifest/render is completely unaffected.
"""
from __future__ import annotations

import math
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .r2_handoff.contracts import HandoffError, Limits, plan_id, plan_source
from .r2_handoff.staging import stage_source, validate_staged
from .r2_handoff.state import StateStore

_NAMESPACE_SAFE = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")
_DEFAULT_NAMESPACE_PREFIX = "renders"
_DEFAULT_CHUNK_BYTES = 33554432  # matches r2_handoff.contracts.Limits' own default


class R2StagingConfigError(RuntimeError):
    """Project.enable_r2_scene_staging is True but required configuration
    (account/bucket) is missing. Fails loudly rather than silently skipping
    a staging step the manifest explicitly asked for."""


def slugify_namespace(text: str, *, prefix: str = _DEFAULT_NAMESPACE_PREFIX) -> str:
    """Turn a free-form project title into a namespace r2_handoff's own
    identity() check accepts: [a-z0-9]+(?:[-/][a-z0-9]+)*, <=80 chars.
    Content-addressed chunk keys mean every scene in a project can safely
    share one namespace -- there is no filename collision risk."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    namespace = f"{prefix}/{slug}" if slug else prefix
    namespace = namespace[:80].rstrip("-")
    return namespace if _NAMESPACE_SAFE.fullmatch(namespace) else prefix


@dataclass(frozen=True)
class R2StagingConfig:
    account_id: str
    bucket: str
    namespace: str
    state_root: Path
    chunk_bytes: int = _DEFAULT_CHUNK_BYTES
    deadline_hours: float = 2.0


def config_from_env(*, namespace: str) -> R2StagingConfig:
    """Reads SHORTS_R2_ACCOUNT_ID / SHORTS_R2_BUCKET (required) and
    SHORTS_R2_STATE_ROOT (optional) -- infra configuration belongs in the
    environment, not in a creative content manifest. Raises
    R2StagingConfigError, never silently disables staging, if the project
    asked for it but the environment isn't configured."""
    account_id = os.environ.get("SHORTS_R2_ACCOUNT_ID")
    bucket = os.environ.get("SHORTS_R2_BUCKET")
    if not account_id or not bucket:
        raise R2StagingConfigError(
            "enable_r2_scene_staging is on but SHORTS_R2_ACCOUNT_ID and/or "
            "SHORTS_R2_BUCKET are not set in the environment -- set both, "
            "or turn enable_r2_scene_staging off"
        )
    state_root = Path(os.environ.get("SHORTS_R2_STATE_ROOT")
                       or Path.home() / ".local/state/shorts-studio/r2-handoff")
    return R2StagingConfig(account_id=account_id, bucket=bucket, namespace=namespace,
                           state_root=state_root)


def _upload_limits(size_bytes: int, chunk_bytes: int, deadline_hours: float) -> Limits:
    """The minimum (max_data_ops, max_token_fetches) r2_handoff's own
    Limits.validate_for(mode="upload") requires is 4*chunk_count+4 -- use
    exactly that rather than an arbitrary larger number, so a caller can see
    directly from these limits how many real operations an eventual apply
    would need."""
    chunk_count = max(1, math.ceil(size_bytes / chunk_bytes))
    ops = 4 * chunk_count + 4
    return Limits(
        max_bytes=max(size_bytes, 1), max_data_ops=ops, max_token_fetches=ops,
        deadline_utc=datetime.now(UTC) + timedelta(hours=deadline_hours), chunk_bytes=chunk_bytes,
    )


def stage_scene_clip(clip: Path, *, config: R2StagingConfig) -> dict:
    """Hash, chunk, and durably stage `clip` for a future R2 upload. No
    network call; no credential is read. Idempotent: staging the same clip
    bytes again returns the same job_id instead of re-copying.

    If StateStore.create_job raises AFTER stage_source has already copied
    the chunks into the spool (verified by a real interrupted-retry test:
    without this cleanup, a crash in that narrow window leaves an orphaned
    spool directory that a later retry never reuses or removes, since
    stage_source's own plan_id-prefixed tempfile.mkdtemp always creates a
    fresh directory), the just-created spool is removed before re-raising
    so a retry starts clean instead of leaking disk space on every failed
    attempt. This narrows but does not eliminate the window: a hard process
    kill (SIGKILL) between the two calls cannot be caught by any exception
    handler and can still leak one spool directory -- a disk-space concern
    only, never data loss or a duplicate/incorrect job.

    On the reuse path (a job for this exact content already exists), the
    existing spool is re-verified with validate_staged before reporting
    success: without this, a job row surviving in the database while its
    spool directory was deleted or corrupted out from under it (by anything
    external to this module -- a disk cleanup script, manual intervention)
    would silently report "STAGED" again on the next render even though the
    durable copy that claim depends on no longer exists or no longer
    matches the manifest. A HandoffError (typically INTEGRITY_FAILED) now
    propagates instead of a false success."""
    clip = Path(clip)
    size_bytes = clip.stat().st_size
    limits = _upload_limits(size_bytes, config.chunk_bytes, config.deadline_hours)
    manifest = plan_source(
        clip, account_id=config.account_id, bucket=config.bucket, namespace=config.namespace,
        limits=limits, expected_sha256=None,
        provenance={"producer": "shorts_studio.render", "scene_asset": clip.name},
    )
    job_id = plan_id(manifest)
    config.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with StateStore(config.state_root / "jobs.sqlite") as store:
        try:
            existing, _ = store.load_job(job_id)
        except HandoffError as error:
            if error.code != "UNKNOWN_JOB":
                raise
            staged = stage_source(clip, root=config.state_root / "spool", planned=manifest)
            try:
                store.create_job(staged, limits)
            except BaseException:
                shutil.rmtree(staged.spool, ignore_errors=True)
                raise
        else:
            validate_staged(existing)
    return {
        "status": "STAGED", "job_id": job_id, "sha256": manifest.sha256,
        "size_bytes": manifest.size_bytes, "namespace": config.namespace,
        "limits": asdict(limits) | {"deadline_utc": limits.deadline_utc.isoformat()},
    }
