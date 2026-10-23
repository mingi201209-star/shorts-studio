"""Explicit one-job CLI. No background startup, media production or publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .contracts import (
    HandoffError,
    Limits,
    RestoreRequest,
    manifest_key,
    plan_id,
    plan_source,
    require,
)
from .coordinator import Coordinator
from .oauth import OAuthConfig, _private_read, obtain_grant
from .staging import stage_source, validate_original, validate_staged
from .state import StateStore, bucket_lock
from .wrangler import WranglerBackend

FLAGS = {"authorized_to_cleanup_local": False, "production_concurrent_writes_allowed": False,
             "provider_spend_cap_enforced": False, "upload_authorized": False}


def _emit(data):
    print(json.dumps(data | FLAGS, sort_keys=True))


def _parser():
    parser = argparse.ArgumentParser(description="Explicit bounded R2 byte handoff, no auto-start")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply", "status", "resume", "verify"):
        p = commands.add_parser(name)
        p.add_argument("--state-root", type=Path,
                       default=Path.home()/".local/state/shorts-studio/r2-handoff")
        if name in {"plan", "verify"}:
            p.add_argument("--account", required=True)
            p.add_argument("--bucket", required=True)
            p.add_argument("--namespace", required=True)
            p.add_argument("--max-bytes", required=True, type=int)
            p.add_argument("--max-data-ops", required=True, type=int)
            p.add_argument("--max-token-fetches", required=True, type=int)
            p.add_argument("--deadline", required=True)
            p.add_argument("--chunk-bytes", type=int, default=33554432)
        if name == "plan":
            p.add_argument("--file", type=Path, required=True)
            p.add_argument("--expected-sha")
            p.add_argument("--save-plan", action="store_true", help="Stage locally; no network")
        if name in {"apply", "resume", "status"}:
            p.add_argument("--job", required=True)
        if name in {"apply", "resume"}:
            p.add_argument("--apply", action="store_true")
        if name == "resume":
            for option in ("new-max-bytes", "new-max-data-ops", "new-max-token-fetches"):
                p.add_argument("--"+option, type=int)
            p.add_argument("--new-deadline")
            p.add_argument("--reason")
        if name == "verify":
            p.add_argument("--manifest-key", required=True)
            p.add_argument("--expected-manifest-sha", required=True)
            p.add_argument("--destination", type=Path, required=True)
            p.add_argument("--read-remote", action="store_true")
        if name in {"apply", "resume", "verify"}:
            p.add_argument("--wrangler", type=Path)
            p.add_argument("--profile", default="default")
            p.add_argument("--audit-file", type=Path,
                           default=Path.home()/".config/shorts-studio/wrangler-audit.json")
    return parser


def _date(value):
    return datetime.fromisoformat(value)


def _limits(args):
    return Limits(args.max_bytes, args.max_data_ops, args.max_token_fetches,
                  _date(args.deadline), args.chunk_bytes)


def _coordinator(store, args, locks):
    home = Path.home()
    config = OAuthConfig(home, home/".config/.wrangler/config"/(args.profile+".toml"),
                         locks, args.profile, args.wrangler, args.audit_file)
    def factory(job):
        if store.status(job)["kind"] == "upload":
            staged, _ = store.load_job(job)
            account, bucket = staged.manifest.account_id, staged.manifest.bucket
        else:
            request, _ = store.load_verify_job(job)
            account, bucket = request.account_id, request.bucket
        def reserve(operation):
            opid = hashlib.sha256(operation.encode()).hexdigest()
            for kind in ("data", "token"):
                store.reserve(job, kind=kind, operation_id=opid,
                              utc_now=datetime.now(UTC), monotonic_now=time.monotonic())
        def remaining():
            return store.remaining(job, utc_now=datetime.now(UTC), monotonic_now=time.monotonic())
        try:
            audit = json.loads(_private_read(args.audit_file, home))
            missing_verified = audit.get("missing_key_message_verified") is True
        except (HandoffError, OSError, ValueError):
            missing_verified = False
        return WranglerBackend(args.wrangler, account_id=account, bucket=bucket, home=home,
            acquire=lambda: obtain_grant(config, now=datetime.now(UTC),
                                         timeout_seconds=min(30, remaining())),
            before_call=reserve, missing_key_verified=missing_verified, remaining=remaining)
    return Coordinator(store, factory, lock_root=locks)


def _run(args):
    root = args.state_root.absolute()
    locks = Path.home()/".config/shorts-studio/r2-locks"  # not caller-selected per job
    db = root/"jobs.sqlite"
    if args.command == "plan":
        limits = _limits(args)
        m = plan_source(args.file, account_id=args.account, bucket=args.bucket,
                        namespace=args.namespace, limits=limits, expected_sha256=args.expected_sha,
                        provenance={})
        status = "DRY_RUN"
        if args.save_plan:
            with bucket_lock(locks, account_id=m.account_id, bucket=m.bucket), StateStore(db) as store:
                try:
                    existing, _ = store.load_job(plan_id(m))
                except HandoffError as error:
                    if error.code != "UNKNOWN_JOB":
                        raise
                    staged = stage_source(args.file, root=root/"spool", planned=m)
                    store.create_job(staged, limits)
                else:
                    require(existing.source == args.file.absolute(), "PLAN_CHANGED")
                    validate_original(existing)
                    validate_staged(existing)
                status = "STAGED"
        _emit({"status": status, "plan_id": plan_id(m), "manifest_key": manifest_key(m),
                   "sha256": m.sha256, "size_bytes": m.size_bytes, "media_status": "MEDIA_QA_PENDING"})
        return
    if args.command == "status":
        with StateStore(db, readonly=True) as store:
            _emit(store.status(args.job))
        return
    if args.command == "verify":
        limits = _limits(args)
        RestoreRequest(args.account, args.bucket, args.namespace, args.manifest_key,
                       args.expected_manifest_sha, args.destination)
        if not args.read_remote:
            _emit({"status": "DRY_RUN", "operation": "verify", "manifest_key": args.manifest_key})
            return
    else:
        require(args.apply, "EXPLICIT_APPLY_REQUIRED")
        require(db.is_file(), "UNKNOWN_JOB")
    require(args.wrangler is not None and args.wrangler.is_absolute(), "WRANGLER_REQUIRED")
    with StateStore(db) as store:
        coordinator = _coordinator(store, args, locks)
        if args.command == "verify":
            receipt = coordinator.verify(account_id=args.account, bucket=args.bucket,
                namespace=args.namespace, manifest_key=args.manifest_key,
                expected_manifest_sha256=args.expected_manifest_sha,
                destination=args.destination, limits=limits)
        elif args.command == "apply":
            receipt = coordinator.apply(args.job)
        else:
            values = (args.new_max_bytes, args.new_max_data_ops, args.new_max_token_fetches,
                      args.new_deadline)
            extra = None
            if any(v is not None for v in values):
                require(all(v is not None for v in values) and bool(args.reason), "INVALID_EXTENSION")
                old = store.limits_for(args.job)
                extra = Limits(*values[:3], _date(values[3]), old.chunk_bytes, old.max_retries)
            receipt = coordinator.resume(args.job, limits=extra, operator_reason=args.reason)
        _emit(asdict(receipt))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if (os.environ.get("ANDROID_ROOT") or Path("/system/build.prop").exists()) and argv and \
                argv[0] not in {"status", "--help", "-h"}:
            raise HandoffError("ANDROID_BLOCKED")
        args = _parser().parse_args(argv)
        _run(args)
        return 0
    except SystemExit as error:
        return int(error.code)
    except KeyboardInterrupt:
        print("BLOCKED:FAILED_RETRYABLE", file=sys.stderr)
        return 4
    except HandoffError as error:
        print("BLOCKED:"+error.code, file=sys.stderr)
        if error.job_id is not None:
            _emit({"status": "BLOCKED", "code": error.code, "job_id": error.job_id})
        return 3 if error.code == "BUSY" else 4 if error.code == "FAILED_RETRYABLE" else 2
    except Exception:  # noqa: BLE001 - unexpected dependency errors must never expose secrets
        print("BLOCKED:INTERNAL_ERROR", file=sys.stderr)
        return 2
