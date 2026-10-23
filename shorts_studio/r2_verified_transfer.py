"""Fail-closed Cloudflare R2 object handoff for a separately configured remote worker.

Never removes its source, auto-creates a bucket, or runs a paid GPU.
DRY_RUN (default) performs no network operation and needs no cloud secrets.
The sole supported write is an explicit conditional, content-addressed PUT;
a complete remote GET + SHA-256 readback is required for VERIFIED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

_CHUNK = 1024 * 1024
_MAX_OBJECT_BYTES = 128 * 1024 * 1024  # Bounded initial pilot; no multipart.
_SUFFIXES = frozenset({
    ".mkv", ".mp4", ".png", ".json", ".blend", ".zip",
    ".wav", ".ass", ".srt", ".txt",
})
_BUCKET = re.compile(r"(?=.{3,63}$)[a-z0-9][a-z0-9.-]*[a-z0-9]\Z")
_PREFIX = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*\Z")
_ACCOUNT_ID = re.compile(r"[0-9a-fA-F]{32}\Z")


class IntegrityError(RuntimeError):
    """Remote data differs from its content-addressed object key."""


def _digest_file(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plan_upload(source: Path, *, prefix: str, max_bytes: int) -> dict:
    """Plan a strictly bounded immutable object name without network access."""
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError("source must be a regular non-symlinked existing file")
    if (type(max_bytes) is not int or not 0 < max_bytes <= _MAX_OBJECT_BYTES):
        raise ValueError("invalid per-file upload size limit")
    if (not isinstance(prefix, str) or len(prefix) > 80 or
            _PREFIX.fullmatch(prefix) is None):
        raise ValueError("unsafe storage prefix")
    if source.suffix.lower() not in _SUFFIXES:
        raise ValueError("file type not approved for media handoff")
    before = source.stat()
    if before.st_size == 0 or before.st_size > max_bytes:
        raise ValueError("source is empty or exceeds explicit size limit")
    digest = _digest_file(source)
    after = source.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        raise RuntimeError("source changed during hashing")
    suffix = source.suffix.lower()
    return {
        "status": "DRY_RUN",
        "sha256": digest,
        "size_bytes": before.st_size,
        "key": f"shorts-studio/{prefix}/{digest}{suffix}",
        "authorized_to_cleanup_local": False,
    }


def _error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    value = response.get("Error", {})
    if not isinstance(value, dict):
        return None
    code = value.get("Code")
    return code if isinstance(code, str) else None


def _verify_remote(client, bucket: str, key: str, expected_sha: str, size: int) -> None:
    """Read the entire actual remote content; ETag and metadata are insufficient."""
    result = client.get_object(Bucket=bucket, Key=key)
    body = result["Body"]
    digest = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = body.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
            if total > size:
                raise IntegrityError("remote byte count differs")
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()
    if total != size or digest.hexdigest() != expected_sha:
        raise IntegrityError("remote SHA-256 or byte count differs")


def upload_verified(
    client,
    source: Path,
    *,
    bucket: str,
    prefix: str,
    max_bytes: int,
    apply: bool = False,
) -> dict:
    """Create-once upload plus full remote read-back, never delete source.

    An existing object is accepted only if its bytes actually hash to the key.
    Unexpected errors (including AccessDenied/NoSuchBucket) fail closed.
    """
    plan = plan_upload(source, prefix=prefix, max_bytes=max_bytes)
    if not isinstance(bucket, str) or _BUCKET.fullmatch(bucket) is None:
        raise ValueError("invalid bucket name")
    if not apply:
        return plan
    if client is None:
        raise ValueError("a configured S3-compatible client is required for --apply")
    key = plan["key"]
    size = plan["size_bytes"]
    sha = plan["sha256"]
    client.head_bucket(Bucket=bucket)
    try:
        client.head_object(Bucket=bucket, Key=key)
    except Exception as error:
        if _error_code(error) not in {"404", "NoSuchKey", "NotFound"}:
            raise
    else:
        _verify_remote(client, bucket, key, sha, size)
        return {
            **plan,
            "status": "VERIFIED_EXISTING",
            "verified_remote_sha256": sha,
        }

    try:
        with Path(source).open("rb") as body:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentLength=size,
                Metadata={"sha256": sha},
                IfNoneMatch="*",  # Atomic create-only conditional R2 PUT.
                StorageClass="STANDARD",
            )
    except Exception as error:
        if _error_code(error) not in {"412", "PreconditionFailed"}:
            raise
        # Another writer won the race. Verify its bytes before accepting.
        _verify_remote(client, bucket, key, sha, size)
        return {
            **plan,
            "status": "VERIFIED_EXISTING",
            "verified_remote_sha256": sha,
        }
    _verify_remote(client, bucket, key, sha, size)
    return {
        **plan,
        "status": "VERIFIED",
        "verified_remote_sha256": sha,
    }


def _r2_client_from_env():
    """Load credentials only in explicit --apply; never print or persist them."""
    account_id = os.environ.get("R2_ACCOUNT_ID", "")
    if _ACCOUNT_ID.fullmatch(account_id) is None:
        raise ValueError("R2_ACCOUNT_ID must be a 32-hex account ID")
    access = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not access or not secret:
        raise ValueError("R2 access credentials must be configured on the remote server")
    try:
        import boto3
    except ImportError as error:
        raise RuntimeError("install boto3 on remote worker before --apply") from error
    return boto3.client(
        "s3",
        region_name="auto",
        endpoint_url=f"https://{account_id.lower()}.r2.cloudflarestorage.com",
        aws_access_key_id=access,
        aws_secret_access_key=secret,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify one bounded R2 artifact transfer")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--bucket", default=os.environ.get("R2_BUCKET", ""))
    parser.add_argument("--max-bytes", type=int, required=True)
    parser.add_argument("--apply", action="store_true",
                        help="EXPLICIT NETWORK WRITE, only after external cost authorization")
    args = parser.parse_args(argv)
    try:
        client = _r2_client_from_env() if args.apply else None
        result = upload_verified(
            client, args.file, bucket=args.bucket, prefix=args.prefix,
            max_bytes=args.max_bytes, apply=args.apply,
        )
    except Exception as error:
        # Never echo exception messages: SDK errors can contain private endpoints.
        print(f"BLOCKED:{type(error).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
