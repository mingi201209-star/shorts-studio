"""Private Linux request supervisor. Holds inherited ownership until descendants stop.

The coordinator's write end of a lifeline pipe is never inherited by this
supervisor or its worker. EOF therefore detects coordinator death even SIGKILL.
No credentials enter arguments or output; the worker receives its private env.
"""
import os
import select
import signal
import subprocess
import sys


def main():
    lifeline, limit = int(sys.argv[1]), int(sys.argv[2])
    command = sys.argv[3:]
    if limit >= 0:
        launcher = ("import os,resource,sys; n=int(sys.argv[1]); "
                    "resource.setrlimit(resource.RLIMIT_FSIZE,(n,n)); "
                    "os.execvpe(sys.argv[2],sys.argv[2:],os.environ)")
        command = [sys.executable, "-c", launcher, str(limit), *command]
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        while True:
            ended = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if ended is not None:
                break
            ready, _, _ = select.select([lifeline], [], [], .025)
            if ready and not os.read(lifeline, 1):
                break
    finally:
        # The leader is deliberately not reaped until its group is terminated,
        # preventing PID reuse and covering descendants after leader exit.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        code = child.wait()
        os.close(lifeline)
    return code if code >= 0 else 128-code


if __name__ == "__main__":
    raise SystemExit(main())
