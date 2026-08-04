"""Build and run L.in.oleum programmes without letting one take the terminal.

Both halves of this are hazards rather than conveniences:

  * the compiler is a GUI-subsystem binary that paints over the console and
    waits for a human, so it is only ever driven through lino_build.ps1,
    which polls for the artifact and kills the process;
  * a compiled programme is the same kind of binary, so it is started
    detached, watched for its output file appearing with a timestamp newer
    than the launch, and then killed. Nothing ever waits on one.

Imported by the starmap_* referees; not interesting on its own.
"""

import os
import subprocess
import sys
import time

ROOT = r"C:\programmieren\linoleum"
WORK = os.path.join(ROOT, "work")
BUILD = os.path.join(ROOT, "lino_build.ps1")
COMPILER = os.path.join(ROOT, r"main\lib\gen\compiler114m.exe")


def build(src, cpu="i386m", compiler=COMPILER, timeout=300):
    """Compile `src`. Returns (ok, output)."""
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", BUILD,
           "-Src", src, "-Compiler", compiler, "-Cpu", cpu]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def run(exe, outputs, timeout=600, poll=0.25, settle=0.6):
    """Start `exe` detached, wait for every path in `outputs` to be rewritten,
    then kill it. Returns (ok, seconds, message)."""
    outputs = list(outputs)
    started = time.time()
    for o in outputs:
        # A stale artifact from a previous run would be mistaken for success.
        if os.path.exists(o):
            os.remove(o)

    cwd = os.path.dirname(exe)
    proc = subprocess.Popen([exe], cwd=cwd,
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        while time.time() - started < timeout:
            time.sleep(poll)
            if all(os.path.exists(o) and os.path.getmtime(o) > started - 1
                   for o in outputs):
                time.sleep(settle)      # let the last write land
                return True, time.time() - started, "ok"
            if proc.poll() is not None:
                missing = [o for o in outputs if not os.path.exists(o)]
                if missing:
                    return False, time.time() - started, f"exited, missing {missing}"
        return False, time.time() - started, "timeout"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


def build_and_run(name, outputs, timeout=600):
    src = os.path.join(WORK, name + ".txt")
    exe = os.path.join(WORK, name + ".exe")
    ok, msg = build(src)
    print(f"build {name}: {msg}")
    if not ok:
        return False
    err = os.path.join(WORK, name + ".err")
    if os.path.exists(err):
        os.remove(err)
    ok, secs, msg = run(exe, outputs, timeout=timeout)
    print(f"run   {name}: {msg} in {secs:.1f}s")
    if os.path.exists(err):
        print(f"  *** {name} wrote {err} - an isocall failed")
        return False
    return ok


if __name__ == "__main__":
    name = sys.argv[1]
    outs = [os.path.join(WORK, a) for a in sys.argv[2:]]
    sys.exit(0 if build_and_run(name, outs) else 1)
