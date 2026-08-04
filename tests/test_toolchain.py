"""GUARDS: the toolchain galaxy2.txt needs, and the fact that a wrong pairing
of compiler and CPU pack fails loudly instead of quietly producing a binary.

galaxy2.txt is only buildable by the patched compiler114m.exe together with the
extended pack -Cpu i386m. Its header states three things this test pins down:

  1. The extended toolchain is installed and the pack in main/cpu matches the
     one tools/buildpack.py generates in tools/. Both files are gitignored and
     nothing in the repo copies one to the other, so a clean checkout - or a
     rebuild of the pack that forgets the copy - leaves the pack the compiler
     actually reads stale or absent. That is silent breakage today.
  2. Nothing under main/ has been modified: all six PRISTINE.sha256 entries
     still hash correctly. main/lib/gen/compiler.txt in particular is under a
     licence that forbids modification.
  3. Every wrong compiler/pack pairing refuses to build. This is what stops a
     *% source from being compiled by something that does not implement it.

HOW IT FAILS: if the pack is missing or out of date, check 1 fails with the two
sha256s side by side. If a mispairing ever starts producing an .exe, the matrix
check fails - and that .exe would be arithmetic nobody verified.

NOTE ON THE EXIT CODE: compiler114m.exe with the stock pack writes
"internal problem: invalid cpu pack" to errorlog.txt, which does not contain
the substring "error:" that lino_build.ps1 greps for, so the script exits 3 with
"Compiler may be showing a dialog" rather than exit 1 with the real reason. The
outcome is still non-zero and no .exe appears, so nothing unsafe happens; this
test asserts the invariant (non-zero, no binary) and reports the diagnosis
separately, so that fixing lino_build.ps1 will not spuriously break it.

RUN: python tests/test_toolchain.py
"""

import hashlib
import os
import shutil
import sys

import linoharness as L


PRISTINE = os.path.join(L.REPO, "PRISTINE.sha256")
PACK_INSTALLED = os.path.join(L.REPO, "main", "cpu", "i386m.bin")
PACK_BUILT = os.path.join(L.REPO, "tools", "i386m.bin")
SUBJECT = os.path.join(L.WORK, "galaxy2.txt")


def filesha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    c = L.Check("test_toolchain - extended toolchain present, mispairings refused")
    gen = L.gen_dir()

    # ---------------------------------------------------------- 1. prerequisites
    c.ok(os.path.exists(L.EXT_COMPILER),
         "patched compiler present", L.EXT_COMPILER)
    c.ok(os.path.exists(L.STOCK_COMPILER),
         "stock compiler present", L.STOCK_COMPILER)

    have_installed = os.path.exists(PACK_INSTALLED)
    have_built = os.path.exists(PACK_BUILT)
    c.ok(have_installed,
         "extended pack installed where the compiler reads it (main/cpu/i386m.bin)",
         "" if have_installed else "MISSING - run tools/buildpack.py, then copy "
                                   "tools/i386m.bin to main/cpu/i386m.bin")
    if have_installed and have_built:
        a, b = filesha(PACK_INSTALLED), filesha(PACK_BUILT)
        c.ok(a == b,
             "installed pack matches the one buildpack.py generates",
             "main/cpu %s vs tools %s" % (a[:16], b[:16]))
    elif have_installed:
        c.note("tools/i386m.bin absent - cannot cross-check the installed pack")

    # ---------------------------------------------------------- 2. main/ pristine
    bad = []
    with open(PRISTINE, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            want, _size, rel = line.split(None, 2)
            path = os.path.join(L.REPO, rel.replace("/", os.sep))
            if not os.path.exists(path):
                bad.append(rel + " (missing)")
            elif filesha(path).lower() != want.lower():
                bad.append(rel + " (hash changed)")
    c.ok(not bad, "all PRISTINE.sha256 files unmodified", ", ".join(bad))

    # ---------------------------------------------------------- 3. pairing matrix
    subject = os.path.join(gen, "tpair.txt")
    shutil.copyfile(SUBJECT, subject)
    exe = os.path.join(gen, "tpair.exe")

    def attempt(compiler, cpu):
        if os.path.exists(exe):
            os.remove(exe)
        rc, out = L.build(subject, compiler, cpu, timeout_sec=30)
        return rc, out.strip(), L.errorlog_for(subject), os.path.exists(exe)

    # positive control - without this the three negatives could all be passing
    # for the boring reason that the source no longer compiles at all.
    rc, out, log, built = attempt(L.EXT_COMPILER, L.EXT_CPU)
    c.ok(rc == 0 and built,
         "compiler114m + i386m builds the *% source (positive control)",
         out.splitlines()[0] if out else "no output")

    rc, out, log, built = attempt(L.STOCK_COMPILER, L.STOCK_CPU)
    c.ok(rc != 0 and not built,
         "stock compiler + i386 refuses the *% source", "rc=%d built=%s" % (rc, built))
    c.ok("unrecognized instruction" in log,
         "  ...and says so: 'unrecognized instruction'",
         " / ".join(l.strip() for l in log.splitlines() if l.strip())[:120])

    rc, out, log, built = attempt(L.EXT_COMPILER, L.STOCK_CPU)
    c.ok(rc != 0 and not built,
         "compiler114m + stock i386 pack refuses to build",
         "rc=%d built=%s" % (rc, built))
    c.ok("invalid cpu pack" in log,
         "  ...and errorlog names the real cause: 'invalid cpu pack'",
         " / ".join(l.strip() for l in log.splitlines() if l.strip())[:120])
    if rc == 3:
        c.note("lino_build.ps1 still misdiagnoses this as a timeout (known: it "
               "greps for 'error:', the pack message says 'internal problem:')")

    rc, out, log, built = attempt(L.STOCK_COMPILER, L.EXT_CPU)
    c.ok(rc != 0 and not built,
         "stock compiler + extended i386m pack refuses to build",
         "rc=%d built=%s" % (rc, built))
    c.note("stock+i386m diagnosis: " +
           (" / ".join(l.strip() for l in log.splitlines() if l.strip())[:120] or "(empty log)"))

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
