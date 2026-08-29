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
import re
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
LAYERS_SOURCE = os.path.join(L.REPO, "main", "lib", "gen", "layers.txt")
VHGUI_SOURCE = os.path.join(L.WORK, "vhgui.txt")
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

    low16_start = compiler_source.index('      "pp found"')
    low16_end = compiler_source.index(
        '      "pp exact low16 mask fallback"', low16_start)
    low16_codegen = compiler_source[low16_start:low16_end]
    low16_markers = (
        "? [i386m target] != yes -> pp exact low16 mask fallback;",
        "? a != q16 -> pp exact low16 mask fallback;",
        "? [op1 class] != register -> pp exact low16 mask fallback;",
        "? [op2 class] != immediate -> pp exact low16 mask fallback;",
        "? [op2 value] != 65535 -> pp exact low16 mask fallback;",
        "? [op1 regid] = 0 -> pp exact low16 eax;",
        "? [op1 regid] = 1 -> pp exact low16 ebx;",
        "? [op1 regid] = 2 -> pp exact low16 ecx;",
        "? [op1 regid] = 3 -> pp exact low16 edx;",
        "? [op1 regid] = 4 -> pp exact low16 esi;",
        "d = C0h; -> pp exact low16 emit;",
        "d = DBh; -> pp exact low16 emit;",
        "d = C9h; -> pp exact low16 emit;",
        "d = D2h; -> pp exact low16 emit;",
        "d = F6h;",
        "[bpos] + 3;",
        "[byte] = 0Fh; => cat byte;",
        "[byte] = B7h; => cat byte;",
        "[byte] = d; => cat byte;",
    )
    positions = [low16_codegen.find(marker) for marker in low16_markers]
    c.ok(
        all(position >= 0 for position in positions)
        and positions == sorted(positions)
        and compiler_source.count('"pp exact low16 mask fallback"') == 1,
        "i386m register low16 codegen is guarded and emits exact MOVZX bytes")

    pending_fold_markers = (
        "pp pending cd = 1;",
        "pp pending cd position = 1;",
        "pp pending registers = 5;",
        "? [inst plus 0] != ampersand -> pp pending cd mismatch;",
        "? [op1 regid] != 2 -> pp pending cd mismatch;",
        "? [op2 value] != 65535 -> pp pending cd mismatch;",
        "? [bpos] != [pp pending cd position] -> pp pending cd mismatch;",
        "[byte] = 0Fh; => cat byte;",
        "[byte] = B7h; => cat byte;",
        "[byte] = CAh; => cat byte;",
        "? a != ip quickreference -> pp exact pending cd fallback;",
        "? [op2 regid] != 3 -> pp exact pending cd fallback;",
        "[pp pending cd position] = [bpos];",
        '"pp flush pending cd"',
        "[byte] = 8Bh; => cat byte;",
    )
    c.ok(
        all(marker in compiler_source for marker in pending_fold_markers)
        and compiler_source.count("[pp pending cd] = no;") == 4
        and compiler_source.count("=> pp flush pending cd;") == 5
        and compiler_source.count('"pp flush pending cd"') == 1,
        "i386m adjacent C = D low16 fold is guarded and flushes every code boundary")

    delta_markers = (
        "pp delta layer marker = { cl2lrexacti386mdeltacopy };",
        "pp prior code label position = 1;",
        "[pp prior code label position] = minus 1;",
        "? [pass] != code pass -> register code label;",
        "? [i386m target] != yes -> note prior code label;",
        "[target string] = pp delta layer marker;",
        "=> pp exact delta layer copy;",
        "[pp prior code label position] = [bpos];",
        '"pp exact delta layer copy"',
        "a - [pp prior code label position];",
        "? a != 26 -> pp exact delta layer restore;",
        "? [bbss] < 26 -> pp exact delta layer restore;",
        "[target string] = vector pp delta layer scalar;",
        "c = 26;",
        "c ^ pp exact delta layer compare;",
        "[target string] = vector pp delta layer exact;",
        "c = 23;",
        "c ^ pp exact delta layer write;",
    )
    delta_start = compiler_source.index("pp delta layer marker =")
    delta_end = compiler_source.index("tag extend upto", delta_start)
    delta_data = compiler_source[delta_start:delta_end]
    scalar_values = (
        "8Bh; ACh; 87h; 00h; 00h; 00h; 00h;",
        "89h; ACh; 9Fh; 00h; 00h; 00h; 00h;",
        "43h; 40h; 49h; 0Fh; 85h; E9h; FFh; FFh; FFh;",
        "59h; 5Bh; 58h;",
    )
    exact_values = (
        "29h; D8h; 8Dh; 1Ch; 9Fh; 8Dh; 6Dh; 00h;",
        "8Bh; 2Ch; 83h; 89h; 2Bh; 8Dh; 5Bh; 04h;",
        "49h; 0Fh; 85h; F1h; FFh; FFh; FFh;",
    )
    c.ok(
        all(marker in compiler_source for marker in delta_markers)
        and all(value in delta_data for value in scalar_values + exact_values)
        and compiler_source.count('"pp exact delta layer copy"') == 1,
        "i386m marked layer copy requires the exact scalar signature and emits exact delta bytes")

    layers_source = open(LAYERS_SOURCE, "r", encoding="utf-8").read()
    layer_loop = layers_source[
        layers_source.index('"CL2LR Scanline"'):
        layers_source.index('"CL2LR No Region"')]
    c.ok(
        layers_source.count('"CL2LR exact i386m delta copy"') == 1
        and layer_loop.count('"CL2LR Pixel"') == 1
        and "[B] = [A]; B+; A+;" in layer_loop
        and "C ^ CL2LR Pixel;" in layer_loop
        and "<-- C;\n\t<-- B;\n\t<-- A;\n"
            '    "CL2LR exact i386m delta copy"' in layer_loop
        and "{" not in layer_loop,
        "shared layer source marks only the exact scalar loop after its three pops")

    vhgui_compiler_markers = (
        "pp vhgui compose marker = { vhguiexacti386mblockoffsetcompose };",
        "pp vhgui fixed2x marker = { vhguiexacti386mblockoffsetfixed2x };",
        "pp exact island scalar = 1;",
        "pp exact island candidate = 1;",
        "pp exact island length = 1;",
        '"examine vhgui compose marker"',
        '"examine vhgui fixed2x marker"',
        "[pp exact island length] = 168;",
        "[pp exact island length] = 210;",
        '"pp exact marked island"',
        "? a != [pp exact island length] -> pp exact marked island restore;",
        "? [bbss] < a -> pp exact marked island restore;",
        "[target string] = [pp exact island scalar];",
        "[target string] = [pp exact island candidate];",
        "c ^ pp exact marked island compare;",
        "c ^ pp exact marked island write;",
    )

    def exact_vector(name, next_name):
        start = compiler_source.index("\tvector " + name + " =")
        end = compiler_source.index("\n\t" + next_name, start)
        values = re.findall(r"\b([0-9A-Fa-f]{2})h;", compiler_source[start:end])
        return bytes(int(value, 16) for value in values)

    vhgui_vectors = {
        "compose-scalar": exact_vector(
            "pp vhgui compose scalar", "vector pp vhgui compose exact ="),
        "compose-exact": exact_vector(
            "pp vhgui compose exact", "vector pp vhgui fixed2x scalar ="),
        "fixed2x-scalar": exact_vector(
            "pp vhgui fixed2x scalar", "vector pp vhgui fixed2x exact ="),
        "fixed2x-exact": exact_vector(
            "pp vhgui fixed2x exact", "tag extend upto"),
    }
    vhgui_vector_hashes = {
        name: (len(blob), hashlib.sha256(blob).hexdigest())
        for name, blob in vhgui_vectors.items()
    }
    c.ok(
        all(marker in compiler_source for marker in vhgui_compiler_markers)
        and compiler_source.count('"pp exact marked island"') == 1
        and vhgui_vector_hashes == {
            "compose-scalar": (
                168, "58a5a84d89386f4a91f34eebf89c77d8ec2a5c714bbf23b30ce77a8f05328539"),
            "compose-exact": (
                168, "cbb526557bad82ac4204e8c3b20576b9e8273f1a41414e2399c4e5847c8c16cf"),
            "fixed2x-scalar": (
                210, "ac8aa2793208832a3a4102ff5a106189acc210030e343211e1de1eca23a34f79"),
            "fixed2x-exact": (
                210, "7030af1aa854f8b57b792915c14e196352b746c4101cdcf98142f98ef48b8536"),
        },
        "i386m marked GUI islands require full exact signatures and equal-size vectors")

    vhgui_source = open(VHGUI_SOURCE, "r", encoding="utf-8").read()
    compose_marker = '"VHGUI exact i386m block offset compose"'
    fixed2x_marker = '"VHGUI exact i386m block offset fixed2x"'
    compose_source = vhgui_source[
        vhgui_source.index('"VHGUI compose pixel"'):
        vhgui_source.index(compose_marker)]
    fixed2x_source = vhgui_source[
        vhgui_source.index('"VHGUI 2x pixel"'):
        vhgui_source.index(fixed2x_marker)]
    c.ok(
        vhgui_source.count(compose_marker) == 1
        and vhgui_source.count(fixed2x_marker) == 1
        and "A = [C]; A + pal; [D] = [A];" in compose_source
        and "C + 4; D + 4; [VHGUIx]-;" in compose_source
        and "? A < 200 -> VHGUI compose row;\n\tend;\n    " + compose_marker
            in vhgui_source
        and "[D] = A; [D plus 1] = A; [E] = A; [E plus 1] = A;"
            in fixed2x_source
        and "C + 4; D + 8; E + 8; [VHGUIx]-;" in fixed2x_source
        and "? A < 200 -> VHGUI 2x row;\n\tend;\n    " + fixed2x_marker
            in vhgui_source
        and "{" not in compose_source + fixed2x_source,
        "shared VHGUI loops keep every Lino operation and add only exact zero-byte markers")

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
