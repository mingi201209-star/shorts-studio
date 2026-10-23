"""Bounded private subprocess capture; never includes child output in errors."""
from __future__ import annotations

import os
import selectors
import subprocess
import sys
import time
from pathlib import Path

from .contracts import HandoffError


def bounded_run(argv, *, env, timeout, capture_output=True, text=True, max_file_bytes=None):
    from .state import held_lock_fds
    reader, writer = os.pipe()
    command = [sys.executable, str(Path(__file__).with_name("worker.py")), str(reader),
               str(max_file_bytes if max_file_bytes is not None else -1), *argv]
    try:
        p = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, start_new_session=True,
                             pass_fds=(reader, *held_lock_fds()))
    except BaseException:
        os.close(reader)
        os.close(writer)
        raise
    os.close(reader)
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
        os.close(writer)  # EOF instructs the supervisor to stop its whole group
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # Never release inherited ownership by killing the supervisor while
            # a kernel-blocked worker still exists. It drains and releases later.
            pass
        p.stdout.close()
        p.stderr.close()
