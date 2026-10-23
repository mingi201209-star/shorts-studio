"""Pinned Wrangler OAuth acquisition. Never implement token rotation ourselves."""
from __future__ import annotations

import json
import os
import stat
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .contracts import HandoffError, _unique_pairs, require
from .process import bounded_run
from .staging import digest_file, private_dir
from .state import profile_lock


@dataclass(frozen=True)
class OAuthConfig:
    home: Path
    config_file: Path
    lock_root: Path
    profile: str
    wrangler: Path
    audit_file: Path | None = None


class OAuthGrant:
    __slots__ = ("_token", "expiry")

    def __init__(self, token: str, expiry: datetime):
        self._token = token
        self.expiry = expiry

    def __repr__(self):
        return "OAuthGrant(<private>)"

    def __reduce__(self):
        raise TypeError("OAuth grants cannot be serialized")


def base_environment(home: Path) -> dict[str, str]:
    return {"HOME": str(home), "PATH": os.defpath + ":/usr/local/bin",
            "LANG": "C.UTF-8", "WRANGLER_SEND_METRICS": "false", "WRANGLER_LOG": "error"}


def data_environment(grant: OAuthGrant, *, home: Path) -> dict[str, str]:
    return base_environment(home) | {"CLOUDFLARE_API_TOKEN": grant._token}


def _private_read(path: Path, home: Path) -> bytes:
    path, home = Path(path).absolute(), Path(home).absolute()
    require(path.is_relative_to(home), "AUTH_REQUIRED")
    parent = path.parent
    while parent.is_relative_to(home):
        require(not parent.is_symlink(), "AUTH_REQUIRED")
        info = parent.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
                not info.st_mode & 0o077, "AUTH_REQUIRED")
        if parent == home:
            break
        parent = parent.parent
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                not info.st_mode & 0o077 and info.st_size <= 2**20, "AUTH_REQUIRED")
        raw = handle.read(2**20+1)
        require(len(raw) <= 2**20, "AUTH_REQUIRED")
        return raw


def _config(config: OAuthConfig):
    expected = config.home / ".config/.wrangler/config" / (config.profile + ".toml")
    require(config.config_file.absolute() == expected.absolute(), "AUTH_REQUIRED")
    return tomllib.loads(_private_read(config.config_file, config.home).decode())


def obtain_grant(config: OAuthConfig, *, now: datetime, operation_seconds: int = 90,
                 runner=bounded_run, timeout_seconds: float = 30) -> OAuthGrant:
    try:
        require(now.tzinfo is not None and type(operation_seconds) is int and
                0 < operation_seconds <= 90 and 0 < timeout_seconds <= 30, "AUTH_REQUIRED")
        private_dir(config.home)
        with profile_lock(config.lock_root, profile=config.profile):
            _config(config)
            # Live operation is gated on a separately audited, private installation.
            # Merely trusting a version string does not establish safe disk logging
            # or refresh-token replacement behavior in the installed distribution.
            require(config.audit_file is not None, "AUTH_REQUIRED")
            audit = json.loads(_private_read(config.audit_file, config.home),
                               object_pairs_hook=_unique_pairs)
            require(audit.get("version") == "4.152.0" and
                    audit.get("credentials_write_private") is True and
                    audit.get("secrets_logging_safe") is True and
                    audit.get("entrypoint_sha256") == digest_file(config.wrangler), "AUTH_REQUIRED")
            argv = [str(config.wrangler), "auth", "token", "--json"]
            if config.profile != "default":
                argv.extend(["--profile", config.profile])
            result = runner(argv, env=base_environment(config.home), timeout=timeout_seconds,
                            capture_output=True, text=True)
            require(result.returncode == 0 and len(result.stdout) <= 2**20 and
                    len(result.stderr) <= 2**20, "AUTH_REQUIRED")
            data = json.loads(result.stdout, object_pairs_hook=_unique_pairs)
            fresh = _config(config)
            token = data.get("token")
            require(data.get("type") == "oauth" and type(token) is str and
                    0 < len(token) <= 8192 and all(ord(c) >= 33 for c in token) and
                    fresh.get("oauth_token") == token, "AUTH_REQUIRED")
            expiry = datetime.fromisoformat(fresh["expiration_time"])
            require(expiry.tzinfo is not None, "AUTH_REQUIRED")
            require((expiry-now).total_seconds() >= operation_seconds+30, "WAIT_AUTH_WINDOW")
            return OAuthGrant(token, expiry)
    except HandoffError as error:
        if error.code == "WAIT_AUTH_WINDOW" or error.code == "BUSY":
            raise
        raise HandoffError("AUTH_REQUIRED") from None
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise HandoffError("AUTH_REQUIRED") from None
