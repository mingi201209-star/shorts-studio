"""One-object, temporary OAuth Wrangler R2 pilot, never a production worker.

No API keys or OAuth bearer tokens are printed. Local source survives all outcomes.
Wrangler R2 PUT has NO conditional If-None-Match contract, so no concurrent
production writers may use this pilot. S3 conditional-transfer module remains
the preferred long-lived backend when scoped S3 API credentials are available.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
from typing import Callable

from shorts_studio.r2_verified_transfer import IntegrityError, _digest_file, plan_upload

_BUCKET_PATTERN = re.compile(r"(?=.{3,63}$)[a-z0-9][a-z0-9.-]*[a-z0-9]\Z")
_NOT_FOUND_PHRASE = "the specified key does not exist."
_MINIMUM_TOKEN_LIFETIME = timedelta(minutes=3)


def _is_android() -> bool:
    return bool(os.environ.get("ANDROID_ROOT") or Path("/system/build.prop").exists())


def _oauth_env(config: Path, now: datetime) -> dict[str, str]:
    """Pass a short-lived existing Cloudflare OAuth access token via process env.

    API calls are only allowed while the previously authorized access token is
    valid. This does not refresh credentials or provide unattended automation.
    """
    cfg = Path(config)
    if cfg.is_symlink() or not cfg.is_file():
        raise ValueError("OAuth credentials missing or unsafe")
    if cfg.stat().st_mode & 0o077:
        raise ValueError("OAuth credential file permissions are too broad")
    try:
        content = tomllib.loads(cfg.read_text(encoding="utf-8"))
        token = content["oauth_token"]
        expiry = datetime.fromisoformat(content["expiration_time"].replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError, OSError) as exc:
        raise ValueError("OAuth credential file invalid") from exc
    if not isinstance(token, str) or not token.strip() or expiry.tzinfo is None:
        raise ValueError("OAuth credential token or expiry invalid")
    if expiry <= now + _MINIMUM_TOKEN_LIFETIME:
        raise ValueError("OAuth access token expired or too close to expiry")
    env = dict(os.environ)
    # Tool CLI does not currently recognize OAuth config in headless SSH sessions,
    # but accepts its already-valid bearer token in an environment variable.
    # Never put this token in argv, stdout or a log file.
    env.pop("CLOUDFLARE_API_KEY", None)
    env.pop("CLOUDFLARE_EMAIL", None)
    env["CLOUDFLARE_API_TOKEN"] = token
    return env


def _call(runner, argv: list[str], env: dict[str, str]):
    try:
        return runner(argv, env=env, timeout=90, capture_output=True, text=True)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Wrangler remote request timed out") from exc


def _verified_file(path: Path, *, sha: str, size: int) -> None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size != size:
        raise IntegrityError("remote byte count differs")
    if _digest_file(path) != sha:
        raise IntegrityError("remote SHA-256 mismatch")


def upload_via_wrangler(
    source: Path,
    *,
    bucket: str,
    prefix: str,
    max_bytes: int,
    oauth_config: Path,
    wrangler: str,
    apply: bool = False,
    runner: Callable | None = None,
    now: datetime | None = None,
) -> dict:
    """Dry-run or explicitly stage + upload/readback one original remote file.

    Source file is never moved/deleted. Create-only is not atomic via Wrangler:
    therefore this method is limited to a single owner-invoked pilot, never
    automated concurrent jobs. Unknown GET errors block PUT instead of
    guessing the object is missing.
    """
    plan = plan_upload(source, prefix=prefix, max_bytes=max_bytes)
    if not isinstance(bucket, str) or _BUCKET_PATTERN.fullmatch(bucket) is None:
        raise ValueError("invalid R2 bucket")
    if not apply:
        return plan
    if _is_android():
        raise ValueError("Android may not be used as the remote media worker")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if not isinstance(wrangler, str) or not wrangler:
        raise ValueError("Wrangler binary path required")
    runner = runner or subprocess.run
    env = _oauth_env(Path(oauth_config), now)
    remote = f"{bucket}/{plan['key']}"
    with tempfile.TemporaryDirectory(prefix="shorts-r2-pilot-") as tmp:
        checked = Path(tmp) / "checked-remote.bin"
        get_args = [wrangler, "r2", "object", "get", remote, "--remote",
                    "--file", str(checked)]
        result = _call(runner, get_args, env)
        if result.returncode == 0:
            _verified_file(checked, sha=plan["sha256"], size=plan["size_bytes"])
            return {
                **plan,
                "status": "VERIFIED_EXISTING",
                "verified_remote_sha256": plan["sha256"],
                "remote_version_pinned": False,
                "production_concurrent_writes_allowed": False,
            }
        # Only this literal missing-key error permits attempting PUT.
        # All other errors (auth, wrong bucket, rate limit) are fail-closed.
        if _NOT_FOUND_PHRASE not in (result.stderr + result.stdout).lower():
            raise RuntimeError("remote preflight GET failed (not proven missing)")
        if _digest_file(Path(source)) != plan["sha256"]:
            raise RuntimeError("source changed after dry-run planning")
        put_args = [wrangler, "r2", "object", "put", remote, "--remote",
                    "--file", str(source), "--content-type",
                    "application/octet-stream", "--force"]
        put_result = _call(runner, put_args, env)
        if put_result.returncode != 0:
            raise RuntimeError("remote PUT failed")
        # No CLI status or remote metadata alone proves content integrity.
        readback = _call(runner, get_args, env)
        if readback.returncode != 0:
            raise RuntimeError("remote read-back GET failed")
        _verified_file(checked, sha=plan["sha256"], size=plan["size_bytes"])
        if _digest_file(Path(source)) != plan["sha256"]:
            raise IntegrityError("source mutated while uploading")
        return {
            **plan,
            "status": "VERIFIED",
            "verified_remote_sha256": plan["sha256"],
            "remote_version_pinned": False,
            "production_concurrent_writes_allowed": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R2 OAuth Wrangler bounded remote pilot")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--max-bytes", required=True, type=int)
    parser.add_argument("--wrangler", required=True)
    parser.add_argument("--oauth-config", type=Path,
                        default=Path.home() / ".config/.wrangler/config/default.toml")
    parser.add_argument("--apply", action="store_true",
                        help="Perform ONE remote PUT/GET; never silently spend R2 usage")
    args = parser.parse_args(argv)
    try:
        result = upload_via_wrangler(
            args.file, bucket=args.bucket, prefix=args.prefix,
            max_bytes=args.max_bytes, oauth_config=args.oauth_config,
            wrangler=args.wrangler, apply=args.apply,
        )
    except Exception as exc:
        # Never echo SDK/stdout/stderr exceptions (which may contain auth data).
        print(f"BLOCKED:{type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
