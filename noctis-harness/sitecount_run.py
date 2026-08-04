# Build and run L.in.oleum programs without ever waiting on one.
#
# Two hard constraints from the environment, both encoded here so no caller has
# to remember them:
#
#   * The compiler is a GUI-subsystem binary. It paints over the terminal and
#     waits for a human. It is NEVER launched directly - only through
#     lino_build.ps1, which polls for the artifact and kills the process.
#   * A compiled lino program is the same shape of thing. So running one is
#     also poll-and-kill: launch detached, watch for the output file to appear
#     with a timestamp NEWER than launch, then kill.
#
# The mtime check is the load-bearing part. Without it a program that dies on
# startup "passes" by leaving the previous run's output in place, which is the
# single most likely way this whole track could lie to itself.

import os
import subprocess
import sys
import time

ROOT = r"C:\programmieren\linoleum"
BUILD = os.path.join(ROOT, "lino_build.ps1")
WORK = os.path.join(ROOT, "work")

STOCK_COMPILER = os.path.join(ROOT, "main", "compiler.exe")
PATCHED_COMPILER = os.path.join(ROOT, "main", "lib", "gen", "compiler114m.exe")


# The three interchangeable 32x32 -> 64 backends. Each exports the same two
# entry points, so a program picks one by which file is copied into
# work/mul64be.txt - the name its "libraries" period refers to. The compiler
# resolves a relative library name against the source directory first.
BACKENDS = {
    "frag": ("mul64frag.txt", STOCK_COMPILER, "i386"),
    "limb": ("mul64limb.txt", STOCK_COMPILER, "i386"),
    "star": ("mul64star.txt", PATCHED_COMPILER, "i386m"),
}
BACKEND_TARGET = os.path.join(WORK, "mul64be.txt")


class RunError(RuntimeError):
    pass


def select_backend(name):
    """Copy one backend into place. Returns (compiler, cpu) for the build."""
    src, compiler, cpu = BACKENDS[name]
    with open(os.path.join(WORK, src), "rb") as f:
        blob = f.read()
    with open(BACKEND_TARGET, "wb") as f:
        f.write(blob)
    return compiler, cpu


def build(src, compiler=STOCK_COMPILER, cpu="i386", quiet=False):
    """Compile src via lino_build.ps1. Returns the script's stdout line."""
    cmd = [
        "powershell", "-ExecutionPolicy", "Bypass", "-File", BUILD,
        "-Src", src, "-Compiler", compiler, "-Cpu", cpu,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "").strip()
    if not quiet:
        print(out)
    if p.returncode != 0 or not out.startswith("OK"):
        raise RunError("build failed for %s:\n%s\n%s" % (src, out, p.stderr))
    return out


def run(exe, outputs, timeout=30.0, args=None):
    """Launch exe, poll for every path in `outputs` to be rewritten, then kill.

    `outputs` may be a single path or a list. Each is deleted first (explicit
    literal path, never a variable path - the sandbox blocks some forms), and
    each must come back with st_mtime strictly newer than launch.
    """
    if isinstance(outputs, str):
        outputs = [outputs]
    # cwd is set to the exe's directory below, so a relative exe path would be
    # resolved against the wrong place. Pin everything down first.
    exe = os.path.abspath(exe)
    outputs = [os.path.abspath(p) for p in outputs]

    for path in outputs:
        if os.path.exists(path):
            os.remove(path)

    t0 = time.time()
    # Sleep past the filesystem timestamp granularity so "newer than t0" is
    # decidable rather than a coin flip on a fast program.
    time.sleep(0.05)

    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    proc = subprocess.Popen(
        [exe] + list(args or []),
        cwd=os.path.dirname(exe),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=si,
    )

    deadline = t0 + timeout
    ok = False
    try:
        while time.time() < deadline:
            time.sleep(0.15)
            fresh = 0
            for path in outputs:
                try:
                    if os.stat(path).st_mtime > t0:
                        fresh += 1
                except OSError:
                    pass
            if fresh == len(outputs):
                # Let the last write drain before killing.
                time.sleep(0.35)
                ok = True
                break
            if proc.poll() is not None:
                # Process ended; give the filesystem one more look.
                time.sleep(0.35)
                fresh = sum(
                    1 for path in outputs
                    if os.path.exists(path) and os.stat(path).st_mtime > t0
                )
                ok = fresh == len(outputs)
                break
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    if not ok:
        missing = [p for p in outputs
                   if not (os.path.exists(p) and os.stat(p).st_mtime > t0)]
        raise RunError("no fresh output from %s after %.1fs: %s"
                       % (exe, time.time() - t0, missing))
    return time.time() - t0


def build_and_run(src, outputs, compiler=STOCK_COMPILER, cpu="i386",
                  timeout=30.0, quiet=False):
    build(src, compiler=compiler, cpu=cpu, quiet=quiet)
    exe = os.path.splitext(src)[0] + ".exe"
    return run(exe, outputs, timeout=timeout)


def read_units(path, signed=True):
    """Read a .bin of 32-bit units as a list of ints."""
    import struct
    data = open(path, "rb").read()
    if len(data) % 4:
        raise RunError("%s is %d bytes, not a whole number of 32-bit units"
                       % (path, len(data)))
    fmt = "<%d%s" % (len(data) // 4, "i" if signed else "I")
    return list(struct.unpack(fmt, data))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: sitecount_run.py <src.txt> <out.bin> [compiler] [cpu]")
        sys.exit(2)
    src = sys.argv[1]
    out = sys.argv[2]
    comp = sys.argv[3] if len(sys.argv) > 3 else STOCK_COMPILER
    cpu = sys.argv[4] if len(sys.argv) > 4 else "i386"
    secs = build_and_run(src, out, compiler=comp, cpu=cpu)
    print("RAN  %s -> %s  %d bytes  %.1fs" % (src, out, os.path.getsize(out), secs))
