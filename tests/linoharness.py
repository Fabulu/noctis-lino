"""Shared plumbing for the galaxy-hash regression tests.

Everything here is mechanism, not judgement: driving the compiler, driving a
compiled program, compiling and running the C reference, and a tiny check
recorder so each test reports every assertion instead of dying on the first.

Two rules of this project are baked in and must not be worked around:

  * The compiler and the compiled programs are GUI-subsystem binaries. They
    are never waited on. lino_build.ps1 and linorun.ps1 poll for artifacts and
    kill the process; nothing here ever calls the .exe directly.
  * No path may contain "--". The lino argument parser splits on it and then
    reports a bogus "error reading cpu pack". That is why generated sources
    live in tests/gen and never in a scratchpad directory.

One language trap worth knowing: an underscore inside a lino string literal
{ like_this } is emitted as a SPACE in the resulting filename. Every generated
program name and result file name here is therefore underscore-free.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GEN = os.path.join(HERE, "gen")

BUILD_PS1 = os.path.join(REPO, "lino_build.ps1")
RUN_PS1 = os.path.join(HERE, "linorun.ps1")

WORK = os.path.join(REPO, "work")
HARNESS = os.path.join(REPO, "noctis-harness")

STOCK_COMPILER = os.path.join(REPO, "main", "compiler.exe")
EXT_COMPILER = os.path.join(REPO, "main", "lib", "gen", "compiler114m.exe")
STOCK_CPU = "i386"
EXT_CPU = "i386m"

M32 = 0xFFFFFFFF


# --------------------------------------------------------------- process glue

def _powershell(script, args):
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script] + args
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def gen_dir():
    os.makedirs(GEN, exist_ok=True)
    return GEN


def build(src, compiler=EXT_COMPILER, cpu=EXT_CPU, timeout_sec=120):
    """Compile a lino source. Returns (rc, output). rc 0 == OK."""
    return _powershell(BUILD_PS1, ["-Src", src, "-Compiler", compiler,
                                   "-Cpu", cpu, "-TimeoutSec", str(timeout_sec)])


def errorlog_for(src):
    """The compiler drops errorlog.txt beside the source it was given."""
    path = os.path.join(os.path.dirname(os.path.abspath(src)), "errorlog.txt")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def run(exe, out_bin, timeout_sec=60):
    """Run a compiled lino program and collect the file it writes.

    Returns (rc, output, blob). blob is None unless a fresh file appeared.
    """
    rc, out = _powershell(RUN_PS1, ["-Exe", exe, "-Out", out_bin,
                                    "-TimeoutSec", str(timeout_sec)])
    blob = None
    if rc == 0 and os.path.exists(out_bin):
        with open(out_bin, "rb") as fh:
            blob = fh.read()
    return rc, out.strip(), blob


def build_and_run(src, out_bin, compiler=EXT_COMPILER, cpu=EXT_CPU):
    """Compile then run, returning (blob, exe_path, note). blob None on failure."""
    exe = os.path.splitext(src)[0] + ".exe"
    for stale in (exe, out_bin):
        if os.path.exists(stale):
            os.remove(stale)
    rc, out = build(src, compiler, cpu)
    if rc != 0:
        return None, exe, "build failed: " + out.strip()
    rc, out, blob = run(exe, out_bin)
    if blob is None:
        return None, exe, "run failed: " + out
    return blob, exe, out


def gcc_build_and_run(c_src, exe_name, out_name, cwd=None):
    """Compile a C reference with gcc and run it. Returns (blob, note)."""
    cwd = cwd or gen_dir()
    if shutil.which("gcc") is None:
        return None, "gcc not on PATH - the C side of the comparison cannot be built"
    exe = os.path.join(cwd, exe_name)
    out = os.path.join(cwd, out_name)
    for stale in (exe, out):
        if os.path.exists(stale):
            os.remove(stale)
    p = subprocess.run(["gcc", "-O2", "-Wall", "-o", exe, c_src],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=cwd)
    if p.returncode != 0:
        return None, "gcc failed: " + (p.stdout or "") + (p.stderr or "")
    p = subprocess.run([exe], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=cwd)
    if p.returncode != 0 or not os.path.exists(out):
        return None, "C reference did not produce %s: %s" % (out_name, p.stdout)
    with open(out, "rb") as fh:
        return fh.read(), (p.stdout or "").strip()


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


# --------------------------------------------------------------- byte scanning

IMUL_EBX = b"\xF7\xEB"      # signed   32x32 -> edx:eax
MUL_EBX = b"\xF7\xE3"       # unsigned 32x32 -> edx:eax


def opcode_sites(exe_path, pattern):
    with open(exe_path, "rb") as fh:
        blob = fh.read()
    return blob, [m.start() for m in re.finditer(re.escape(pattern), blob)]


# --------------------------------------------------------------- lino emitting

def setconst(var, uval):
    """Load an arbitrary 32-bit value into a variable.

    L.in.oleum literals are signed, so anything with the top bit set is loaded
    by subtracting its two's-complement magnitude; 0x80000000 needs two steps
    because its magnitude does not fit a positive literal.
    """
    uval &= M32
    if uval < 0x80000000:
        return "\tA = 0; A + %d;\t\t[%s] = A;\n" % (uval, var)
    neg = 0x100000000 - uval
    if neg <= 2147483647:
        return "\tA = 0; A - %d;\t\t[%s] = A;\n" % (neg, var)
    return "\tA = 0; A - 2147483647; A - 1;\t[%s] = A;\n" % var


DUMP = """
\t[File Name]\t= result file name;
\t[File Position] = 0;
\t[File Command]\t= WRITE;
\t[Block Pointer] = results;
\t[Block Size]\t= %(units)s;
\t[Block Size]\t* BYTES PER UNIT;
\tisocall;

\t[File Name]\t= result file name;
\t[File Position] = 0;
\t[File Command]\t= SET SIZE;
\t[File Size]\t= %(units)s;
\t[File Size]\t* BYTES PER UNIT;
\tisocall;

\tend;
"""


# --------------------------------------------------------------- check recorder

class Check(object):
    """Records every assertion so one failure does not hide the next."""

    def __init__(self, title):
        self.title = title
        self.failures = []
        self.n = 0
        print("=" * 72)
        print(title)
        print("=" * 72)

    def note(self, text):
        print("  --  %s" % text)

    def ok(self, cond, label, detail=""):
        self.n += 1
        if cond:
            print("  ok  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
        else:
            print("  FAIL %s%s" % (label, ("  [%s]" % detail) if detail else ""))
            self.failures.append(label)
        return bool(cond)

    def eq(self, got, want, label):
        return self.ok(got == want, label, "got %r want %r" % (got, want))

    def done(self):
        print()
        if self.failures:
            print("RESULT: FAIL - %d of %d checks failed" % (len(self.failures), self.n))
            for f in self.failures:
                print("        - %s" % f)
            return 1
        print("RESULT: PASS - %d checks" % self.n)
        return 0


def compare_records(check, sets, label="implementations"):
    """N-way bit-exact comparison. sets is {name: [records]}."""
    import itertools
    names = list(sets)
    sizes = {n: len(sets[n]) for n in names}
    if len(set(sizes.values())) != 1:
        check.ok(False, "%s agree on record count" % label, repr(sizes))
        return False
    # NOT ok(True): agreeing on zero records is agreement about nothing, and a
    # producer that emits nothing agrees with every other producer that emits
    # nothing. tests/w5audit.py rule A flagged the unconditional form.
    check.ok(sizes[names[0]] > 0,
             "all %d %s produced %d records, and the record set is not empty"
             % (len(names), label, sizes[names[0]]))
    all_ok = True
    for a, b in itertools.combinations(names, 2):
        bad = [i for i in range(sizes[a]) if sets[a][i] != sets[b][i]]
        if bad:
            all_ok = False
            detail = "%d/%d differ, first at index %d: %r vs %r" % (
                len(bad), sizes[a], bad[0], sets[a][bad[0]], sets[b][bad[0]])
        else:
            detail = ""
        check.ok(not bad, "%s == %s bit for bit" % (a, b), detail)
    return all_ok


def main_guard(fn):
    """Run a test's main() and exit with its status."""
    sys.exit(fn())
