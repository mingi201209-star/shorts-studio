"""Bounded private subprocess capture; never includes child output in errors."""
from __future__ import annotations

import os
import resource
import selectors
import signal
import subprocess
import time

from .contracts import HandoffError


def bounded_run(argv, *, env, timeout, capture_output=True, text=True, max_file_bytes=None):
    def file_limit():
        resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_bytes, max_file_bytes))
    p = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         stdin=subprocess.DEVNULL, start_new_session=True,
                         preexec_fn=file_limit if max_file_bytes is not None else None)
    buffers = [bytearray(), bytearray()]
    end = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(p.stdout, selectors.EVENT_READ, 0)
            selector.register(p.stderr, selectors.EVENT_READ, 1)
            while selector.get_map():
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise HandoffError("CHILD_TIMEOUT")
                for key, _ in selector.select(min(remaining, 0.1)):
                    raw = os.read(key.fileobj.fileno(), 65536)
                    if not raw:
                        selector.unregister(key.fileobj)
                        continue
                    buffers[key.data].extend(raw)
                    if len(buffers[key.data]) > 2**20:
                        raise HandoffError("CHILD_OUTPUT_LIMIT")
            try:
                p.wait(timeout=max(0.001, end-time.monotonic()))
            except subprocess.TimeoutExpired:
                raise HandoffError("CHILD_TIMEOUT") from None
        return subprocess.CompletedProcess(argv, p.returncode,
                buffers[0].decode("utf-8", errors="replace"),
                buffers[1].decode("utf-8", errors="replace"))
    finally:
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait()
        p.stdout.close()
        p.stderr.close()
