"""GUARDS: the toolchain galaxy2.txt needs, and the fact that a wrong pairing
of compiler and CPU pack fails loudly instead of quietly producing a binary.

galaxy2.txt is only buildable by the patched compiler114m.exe together with the
extended pack -Cpu i386m. Its header states three things this test pins down:

  1. The extended toolchain is installed and both packs under main/cpu match
     tools/buildpack.py's in-memory output exactly. A stale manual copy cannot
     silently pass this guard.
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

TOOLS = os.path.join(L.REPO, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
from buildpack import build_i386m, build_x64  # noqa: E402
from genf64ops import I386_PADDING, X64_PADDING, enumerate_block  # noqa: E402
from packtool import Pack  # noqa: E402


PRISTINE = os.path.join(L.REPO, "PRISTINE.sha256")
PACK_INSTALLED = os.path.join(L.REPO, "main", "cpu", "i386m.bin")
PACK_X64 = os.path.join(L.REPO, "main", "cpu", "x64.bin")
PACK_STOCK = os.path.join(L.REPO, "main", "cpu", "i386.bin")
COMPILER_SOURCE = os.path.join(L.REPO, "main", "lib", "gen", "compiler114m.txt")
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
    c.ok(have_installed,
         "extended pack installed where the compiler reads it (main/cpu/i386m.bin)",
         "" if have_installed else "MISSING - run tools/buildpack.py, then copy "
                                   "tools/i386m.bin to main/cpu/i386m.bin")

    have_x64 = os.path.exists(PACK_X64)
    have_stock = os.path.exists(PACK_STOCK)
    c.ok(have_x64, "extended x64 pack installed", PACK_X64)
    c.ok(have_stock, "protected stock i386 pack present", PACK_STOCK)
    if have_installed and have_x64 and have_stock:
        stock_blob = open(PACK_STOCK, "rb").read()
        i386m_blob = open(PACK_INSTALLED, "rb").read()
        x64_blob = open(PACK_X64, "rb").read()
        generated_i386m = build_i386m()
        generated_x64 = build_x64()
        c.ok(i386m_blob == generated_i386m,
             "installed i386m pack is generator-exact",
             "installed %s vs generated %s" %
             (hashlib.sha256(i386m_blob).hexdigest()[:16],
              hashlib.sha256(generated_i386m).hexdigest()[:16]))
        c.ok(x64_blob == generated_x64,
             "installed x64 pack is generator-exact",
             "installed %s vs generated %s" %
             (hashlib.sha256(x64_blob).hexdigest()[:16],
              hashlib.sha256(generated_x64).hexdigest()[:16]))
        i386m = Pack(i386m_blob)
        x64 = Pack(x64_blob)
        c.ok((i386m.align, i386m.count, len(i386m_blob)) ==
             (48, 6510, 312488),
             "i386m has the 6,510-record binary64 layout",
             "align=%d count=%d bytes=%d" %
             (i386m.align, i386m.count, len(i386m_blob)))
        c.ok((x64.align, x64.count, len(x64_blob)) ==
             (145, 6510, 943958),
             "x64 has the 6,510-record binary64 layout",
             "align=%d count=%d bytes=%d" %
             (x64.align, x64.count, len(x64_blob)))
        c.ok(i386m_blob[:len(stock_blob)] == stock_blob,
             "i386m preserves the protected 6,241-record stock prefix")
        i386_suffix = b"".join(enumerate_block(
            alignment=i386m.align, padding=I386_PADDING,
            terminator=i386m.ter))
        x64_suffix = b"".join(enumerate_block(
            alignment=x64.align, padding=X64_PADDING,
            terminator=x64.ter))
        c.ok(i386m_blob[-len(i386_suffix):] == i386_suffix,
             "i386m binary64 suffix is generator-exact")
        c.ok(x64_blob[-len(x64_suffix):] == x64_suffix,
             "x64 binary64 suffix is generator-exact")

        c.ok(len(i386_suffix) == 27 * i386m.align
             and len(x64_suffix) == 27 * x64.align,
             "binary64 suffixes contain 24 arithmetic and 3 conversion records")
        direct_signatures = (
            b"\xDC\x87D2.4", b"\xDC\xA7D2.4",
            b"\xDC\x8FD2.4", b"\xDC\xB7D2.4",
        )
        c.ok(all(signature in i386_suffix for signature in direct_signatures)
             and all(signature in x64_suffix for signature in direct_signatures),
             "binary64 suffixes contain direct-source +:, -:, *:, /: records")

    compiler_source = open(COMPILER_SOURCE, "r", encoding="utf-8").read()
    c.ok(
        "ip records\t= 638 mtp 3;" in compiler_source
        and "[up length] = 638 mtp 3;" in compiler_source
        and "? a < 83 mtp 9 relating ip quickreference" in compiler_source
        and "cpu pack = 6510" in compiler_source
        and all("q%d =" % index in compiler_source for index in range(76, 83))
        and all(marker in compiler_source for marker in (
            "q76 = { +:\t}; extend upto: 7;   6;  6;",
            "q77 = { -:\t}; extend upto: 7;   6;  6;",
            "q78 = { *:\t}; extend upto: 7;   6;  6;",
            "q79 = { /:\t}; extend upto: 7;   6;  6;",
        )),
        "compiler metadata owns direct-source exact arithmetic and 6,510 patterns")

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
