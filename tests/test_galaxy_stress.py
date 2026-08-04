"""GUARDS: the *% form of the galaxy hash on coordinates the 343-sector
acceptance sweep can never reach - including the ones that make its three
cutoff branches execute at all.

Every sector coordinate on the real grid is a multiple of 100000, so on that
grid the multiply only ever sees a narrow, well-behaved family of operands and
the cutoff comparisons never fire. Two consequences:

  * flag bit 1 is not merely untaken on the grid, it is UNREACHABLE there:
    100000 % 32 == 0 and 2**17 % 32 == 0, so temp_x is always a multiple of 32,
    while the cutoff constant 50000 % 32 == 16. The `A | 1` branch cannot run.
    A brute scan of k in [-90, 90] - 5,929,741 sectors - finds no flag of any
    kind. So test_galaxy.py leaves all three branches, and the whole
    signed/unsigned boundary of the multiply, unexercised.
  * a *% that was wrong only for operands at 0x80000000, or only when the
    product's high half is negative, would sail through the acceptance test.

This test therefore drives the same arithmetic with arbitrary 32-bit sector
coordinates: the signed extremes, sums that wrap to zero, the 0x1FFFF mask
boundary, coordinates searched out to force each cutoff flag, and a
deterministic pseudorandom spread. Four independent implementations must agree
on all of them.

    stressm   L.in.oleum, `A *% B; A + B;`   compiler114m.exe + -Cpu i386m
    stressf   L.in.oleum, inline { F7 EB }   stock toolchain
    stressc   C, int64_t, gcc
    spec      tests/galaxyspec.py, bignum

BRANCH COVERAGE IS ASSERTED, not hoped for: the vector table must produce at
least one case with each of flags 1, 2 and 4, and one with flags 0. If someone
trims the table, the coverage check fails rather than the suite quietly going
back to testing one straight line through the code.

HOW IT FAILS: a *% whose high half is wrong at the sign boundary shows up here
as a mismatch against C and the bignum reference while galaxy2.exe still passes
test_galaxy.py - which is exactly the regression this file exists to catch.

RUN: python tests/test_galaxy_stress.py   (needs gcc on PATH)
"""

import os
import struct
import sys

import galaxyspec as S
import linoharness as L


M32 = 0xFFFFFFFF
MIN32, MAX32 = 0x80000000, 0x7FFFFFFF
SEC = S.SECTORSIZE

# Coordinates found by search that make each cutoff branch fire. temp_y and
# temp_z depend on the multiply, so these also pin the fold's exact value.
FLAG_Y = [(-1423, 0, -1473), (-1408, 0, 117), (-1393, 0, -1174),
          (-1320, 0, 1095), (-1308, 0, 189)]
FLAG_Z = [(-1413, 1007, 0), (-1406, -1114, 0), (-1371, 1354, 0),
          (-1320, 459, 0), (-1222, 247, 0)]

ADVERSARIAL = [
    (0, 0, 0),
    (1, 1, 1),
    (M32, M32, M32),                            # -1, -1, -1
    (MAX32, MAX32, MAX32),
    (MIN32, MIN32, MIN32),
    (MIN32, 0, MIN32),                          # sum_xz wraps to exactly 0
    (MIN32, M32, MAX32),
    (MAX32, MIN32, M32),
    (M32, 1, MIN32),
    (0x0001FFFF, 0, 0),                         # either side of the mask
    (0x00020000, 0, 0),
    (50000, 50000, 50000),
    (0xFFFF0000, 0x0000FFFF, 0x80000001),
    (0x7FFFFFFE, 0x00000002, 0xFFFFFFFE),
    (0xAAAAAAAA, 0x55555555, 0xCCCCCCCC),
    (0x00000020, 0xFFFFFFE0, 0x00008000),
    (2147483647, 1, 1),
    (1, 2147483647, 1),
    (1, 1, 2147483647),
    # sect_x + sect_z == 0 makes temp_x == sect_x, so sect_x == 50000 fires
    # flag 1 - the branch that is unreachable on the real sector grid.
    (50000, 0, (-50000) & M32),
    (50000, 7, (-50000) & M32),
    (50000, (-50000) & M32, (-50000) & M32),
]


def pseudorandom(n, seed=0x5EED1234):
    """A fixed LCG, so the vector table is identical on every machine and run."""
    out, x = [], seed
    for _ in range(n):
        trip = []
        for _ in range(3):
            x = (1103515245 * x + 12345) & M32
            trip.append(x)
        out.append(tuple(trip))
    return out


def vectors():
    v = [(kx * SEC, ky * SEC, kz * SEC) for kx, ky, kz in FLAG_Y + FLAG_Z]
    v += ADVERSARIAL
    v += pseudorandom(48)
    return [tuple(a & M32 for a in t) for t in v]


# --------------------------------------------------------------- lino emitters

BODY = """
\t[flags] = 0;

\tA = [sectx]; A + [sectz];\t\t[sumxz] = A;

\tA = [sumxz]; A & 1FFFFh; A + [sectx];\t[tempx] = A;
      ? [tempx] != CUTOFF -> no cutoff x %(n)d;
\tA = [flags]; A | 1;\t\t\t[flags] = A;
    "no cutoff x %(n)d"
\tA = [tempx]; A - CUTOFF;\t\t[tempx] = A;

%(mul1)s
\tA = [sumxz]; A + [accum];\t\t[idk] = A;

\tA = [accum]; A & 1FFFFh; A + [secty];\t[tempy] = A;
      ? [tempy] != CUTOFF -> no cutoff y %(n)d;
\tA = [flags]; A | 2;\t\t\t[flags] = A;
    "no cutoff y %(n)d"
\tA = [tempy]; A - CUTOFF;\t\t[tempy] = A;

%(mul2)s
\tA = [accum]; A & 1FFFFh; A + [sectz];\t[tempz] = A;
      ? [tempz] != CUTOFF -> no cutoff z %(n)d;
\tA = [flags]; A | 4;\t\t\t[flags] = A;
    "no cutoff z %(n)d"
\tA = [tempz]; A - CUTOFF;\t\t[tempz] = A;

\tA = [tempx]; A + [tempy]; A + [tempz];\t[netpos] = A;

\tA = results; A + [outIdx];
\tC = [tempx];  [A] = C;
\tA + 1; C = [tempy];  [A] = C;
\tA + 1; C = [tempz];  [A] = C;
\tA + 1; C = [netpos]; [A] = C;
\tA + 1; C = [flags];  [A] = C;
\tA = [outIdx]; A + PERSECTOR;\t\t[outIdx] = A;
"""

MUL_SPLIT = "\tA = [%s]; B = [%s]; A *%% B; A + B; [accum] = A;\n"
MUL_FRAG = ("\tA = [%s]; [fmA] = A;\n"
            "\tA = [%s]; [fmB] = A;\n"
            "\t=> FoldMul;\n"
            "\tA = [fmResult];\t\t\t\t[accum] = A;\n")

FRAG_SUB = """
"FoldMul"
    ( Signed 32x32 -> 64 multiply, high half folded into the low - the
      original's imul followed by "edx += eax". )

\tA = [fmA];
\tB = [fmB];
\t{
\t    F7 EB
\t}
\tA + D;
\t[fmResult] = A;

\tend;
"""


def emit_lino(path, progname, outname, cases, use_split):
    if use_split:
        m1, m2 = MUL_SPLIT % ("tempx", "sumxz"), MUL_SPLIT % ("tempy", "idk")
        extra = ""
    else:
        m1, m2 = MUL_FRAG % ("tempx", "sumxz"), MUL_FRAG % ("tempy", "idk")
        extra = "\tfmA\t= 0;\n\tfmB\t= 0;\n\tfmResult = 0;\n"

    o = ["\n      ( Generated by tests/test_galaxy_stress.py - do not edit. )\n"
         "      ( The galaxy hash driven over adversarial sector coordinates. )\n\n"]
    o.append('"directors"\n\n\tprogram name = { %s };\n\tunit = 32;\n\n' % progname)
    o.append('"constants"\n\n\tCUTOFF\t\t= %d;\n\tPERSECTOR\t= %d;\n\tNCASES\t\t= %d;\n\n'
             % (S.CUTOFF, S.PERSECTOR, len(cases)))
    o.append('"variables"\n\n\toutIdx\t= 0;\n\tsectx\t= 0;\n\tsecty\t= 0;\n\tsectz\t= 0;\n')
    o.append('\tsumxz\t= 0;\n\ttempx\t= 0;\n\ttempy\t= 0;\n\ttempz\t= 0;\n')
    o.append('\taccum\t= 0;\n\tidk\t= 0;\n\tnetpos\t= 0;\n\tflags\t= 0;\n')
    o.append(extra)
    o.append('\n\tresult file name = { %s };\n\n' % outname)
    o.append('"workspace"\n\n\tresults = NCASES multiplied PERSECTOR;\n\n')
    o.append('"programme"\n\n\t[outIdx] = 0;\n')
    for n, (sx, sy, sz) in enumerate(cases):
        o.append("\n\t( case %d )\n" % n)
        o.append(L.setconst("sectx", sx))
        o.append(L.setconst("secty", sy))
        o.append(L.setconst("sectz", sz))
        o.append(BODY % {"n": n, "mul1": m1, "mul2": m2})
    o.append(L.DUMP % {"units": "NCASES multiplied PERSECTOR"})
    if not use_split:
        o.append(FRAG_SUB)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(o))


C_TMPL = r"""/* Generated by tests/test_galaxy_stress.py - do not edit.
   The galaxy hash in C, driven over the same adversarial coordinates. */
#include <stdio.h>
#include <stdint.h>
static uint32_t fold_mul(int32_t a, int32_t b) {
    int64_t r = (int64_t) a * (int64_t) b;
    return (uint32_t)(r >> 32) + (uint32_t)(r & 0xFFFFFFFFu);
}
static const uint32_t T[][3] = {
@@ROWS@@};
int main(void) {
    FILE *o = fopen("@@OUT@@", "wb");
    int n = sizeof(T)/sizeof(T[0]);
    if (!o) return 1;
    for (int i = 0; i < n; i++) {
        uint32_t sect_x = T[i][0], sect_y = T[i][1], sect_z = T[i][2];
        uint32_t sum_xz = sect_x + sect_z, flags = 0;
        uint32_t temp_x = (sum_xz & 0x1FFFFu) + sect_x;
        if (temp_x == 50000u) flags |= 1u;
        temp_x -= 50000u;
        uint32_t accum = fold_mul((int32_t)temp_x, (int32_t)sum_xz);
        uint32_t idk = sum_xz + accum;
        uint32_t temp_y = (accum & 0x1FFFFu) + sect_y;
        if (temp_y == 50000u) flags |= 2u;
        temp_y -= 50000u;
        accum = fold_mul((int32_t)temp_y, (int32_t)idk);
        uint32_t temp_z = (accum & 0x1FFFFu) + sect_z;
        if (temp_z == 50000u) flags |= 4u;
        temp_z -= 50000u;
        uint32_t netpos = temp_x + temp_y + temp_z;
        uint32_t rec[5] = { temp_x, temp_y, temp_z, netpos, flags };
        fwrite(rec, 4, 5, o);
    }
    fclose(o);
    printf("%d cases\n", n);
    return 0;
}
"""


def main():
    c = L.Check("test_galaxy_stress - the *% hash on coordinates the sweep cannot reach")
    gen = L.gen_dir()
    cases = vectors()
    c.note("%d adversarial sector coordinates" % len(cases))

    # ------------------------------------------------- 1. the vectors earn their keep
    spec = [S.hash_sector(*t) for t in cases]
    hist = {}
    for r in spec:
        hist[r[4]] = hist.get(r[4], 0) + 1
    c.note("flag histogram: %s" % sorted(hist.items()))
    for bit in (0, 1, 2, 4):
        c.ok(hist.get(bit, 0) > 0,
             "vector table exercises flags == %d" % bit,
             "%d cases" % hist.get(bit, 0))

    sets = {"spec": spec}

    # ------------------------------------------------------------ 2. the two linos
    src_m = os.path.join(gen, "tstrm.txt")
    emit_lino(src_m, "tstrm", "tstrm.bin", cases, use_split=True)
    blob, exe_m, note = L.build_and_run(src_m, os.path.join(gen, "tstrm.bin"),
                                        L.EXT_COMPILER, L.EXT_CPU)
    if not c.ok(blob is not None, "*% stress program builds and runs", note):
        return c.done()
    sets["stressm"] = S.unpack(blob)

    src_f = os.path.join(gen, "tstrf.txt")
    emit_lino(src_f, "tstrf", "tstrf.bin", cases, use_split=False)
    blob, exe_f, note = L.build_and_run(src_f, os.path.join(gen, "tstrf.bin"),
                                        L.STOCK_COMPILER, L.STOCK_CPU)
    if not c.ok(blob is not None, "{ F7 EB } stress program builds and runs", note):
        return c.done()
    sets["stressf"] = S.unpack(blob)

    # ----------------------------------------------------------------- 3. C side
    rows = "".join("    {0x%08Xu, 0x%08Xu, 0x%08Xu},\n" % t for t in cases)
    src_c = os.path.join(gen, "tstrc.c")
    with open(src_c, "w", encoding="utf-8") as fh:
        fh.write(C_TMPL.replace("@@ROWS@@", rows).replace("@@OUT@@", "tstrc.bin"))
    blob, note = L.gcc_build_and_run(src_c, "tstrc.exe", "tstrc.bin", cwd=gen)
    if not c.ok(blob is not None, "C stress reference compiles and runs", note or ""):
        return c.done()
    sets["stressc"] = S.unpack(blob)

    # --------------------------------------------------------- 4. four-way verdict
    L.compare_records(c, sets, "implementations")
    c.note("sha256 %s" % L.sha(S.pack(sets["stressm"])))

    # ------------------------------------- 5. the comparison is not vacuous
    # If every record were identical, agreement would prove nothing. It is not:
    distinct = len(set(sets["spec"]))
    c.ok(distinct == len(cases),
         "every case produces a distinct record", "%d distinct" % distinct)

    # The stress program is unrolled, so there are two multiply sites per case
    # rather than the two in galaxy2.txt's loop. Every one must be signed.
    _, imul = L.opcode_sites(exe_m, L.IMUL_EBX)
    _, mul = L.opcode_sites(exe_m, L.MUL_EBX)
    c.eq((len(imul), len(mul)), (2 * len(cases), 0),
         "*% stress binary: every multiply site is a signed imul ebx")

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
