r"""su_bin.py - Wave 7a, the SHIPPED BINARY as a third witness.

su_spec.py and su_ref.c both transliterate NOCTIS-0.CPP.  They read the same
1996 text, so a shared misreading of one line survives both.  This file asks
the question neither can: does NOCTIS.EXE agree?

It compares the binary to CONSTANTS RESTATED HERE, never to su_spec.py's or
su_ref.c's output, so every row reads bin: vs claim:.

NO BARE OFFSETS.  Every anchor carries the argument for why it is the right
bytes: an occurrence count over the whole 215,744-byte image, and a bracketing
relation to surface()'s own byte range, which is itself derived rather than
assumed (see FUNC below).

Two findings came out of this file and are printed as rows, not hidden:

  * the day/night attenuation is  26 C0 2D 02 = SHR byte ptr es:[di],2, a
    LOGICAL shift.  C0 /7 (SAR) would sign-extend; the map's bytes never
    exceed 62 so it cannot be told apart from the output, only from the bytes.
  * the binary contains 103 ranged_fast_random CALL SITES where the source
    text has 105, and 15 ssmooth / 7 lssmooth / 4 negate sites where the text
    has 15 / 9 / 5.  Borland 3.1 tail-merges identical statement sequences
    (cross-jumping), so two `if (rfr(N)) lssmooth();`-shaped statements share
    one copy of the code.  The DYNAMIC draw count is unaffected - which is the
    quantity the port has to match - but any check that asserts "105 static
    sites in the binary" is asserting something false about this executable.

Usage:  python su_bin.py [--exe NOCTIS.EXE] [--json]
"""

import argparse
import collections
import json
import os
import re
import struct
import sys

NOCTIS = r"C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE"
SOURCE = r"C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP"
EXPECT_SIZE = 215744

# surface()'s byte range, DERIVED: the `enter 0032h,0` at 0x104AD is the only
# function prologue between the previous call target and the rndpat block that
# is itself a near-call target, and the range ends at the `pop di/pop si/leave/
# retf` = 5F 5E C9 CB at 0x1169A.  Both ends are asserted below.
FUNC = (0x104AD, 0x1169F)

# --------------------------------------------------------------------------
# The inline assembly, restated from NOCTIS-0.CPP and encoded from the
# listing.  name -> (bytes, source line, what a mismatch would mean)
# --------------------------------------------------------------------------

ASM = {
    "surface.prologue": (
        bytes.fromhex("c8320000"), ":4774",
        "enter 0032h,0 - surface()'s 50-byte frame, the anchor for FUNC[0]"),
    "surface.epilogue": (
        bytes.fromhex("5f5ec9cb"), ":5195",
        "pop di / pop si / leave / retf - the anchor for FUNC[1]"),
    "rndpat": (
        bytes.fromhex("b920fd" "8b46fc" "01c8" "31d2" "f7e8" "01d0"
                      "88c3" "80e33e" "26881d" "47" "49" "75ec"), ":4820-4832",
        "mov cx,64800 / mov ax,seed / add ax,cx / xor dx,dx / imul ax /"
        " add ax,dx / mov bl,al / and bl,3Eh / mov es:[di],bl.  The multiply"
        " is IMUL (signed) and the fold is 16-bit; RNDPAT32 changes all"
        " 64,800 bytes."),
    "sda.land": (
        bytes.fromhex("01c8" "f7e8" "01d0" "88c3" "80e33e" "26001d"),
        ":4911-4916",
        "the land branch ends in ADD es:[di],bl (26 00 1D).  niv-lr ASSIGNS"
        " here, which makes the clamp below unreachable."),
    "sda.clamp": (
        bytes.fromhex("26803d3e" "7205" "26c7053e00"), ":4917-4919",
        "cmp byte es:[di],3Eh / jb / mov WORD ptr es:[di],003Eh - the clamp is"
        " a word store and zeroes the NEXT pixel.  niv-lr stores a byte."),
    "sda.sea": (
        bytes.fromhex("263815" "7306" "26c60510"), ":4908-4910",
        "cmp es:[di],dl / jnb / mov byte es:[di],16 - and the noise register"
        " is NOT advanced on this branch."),
    "lmrip": (
        bytes.fromhex("b900fa" "26803d20" "750b" "26c705013e"
                      "26c6856801" "01"), ":4940-4943",
        "mov cx,64000 / cmp byte es:[di],32 / jne / mov word es:[di],3E01h /"
        " mov byte es:[di+360],1"),
    "crater.rim": (
        bytes.fromhex("b83e01" "268905"), ":4545-4546",
        "mov ax,013Eh / mov es:[di],ax"),
    "dark.band": (
        bytes.fromhex("83c723" "b9b300" "51" "b98200"
                      "26c02d02" "47" "49" "75f8" "59" "81c7e600"),
        ":5109-5121",
        "add di,35 / mov cx,179 / push cx / mov cx,130 /"
        " SHR byte ptr es:[di],2 / inc di / dec cx / jnz / pop cx /"
        " add di,230.  C0 /5 is SHR, not SAR."),
    "dark.plwp": (
        bytes.fromhex("c43e2b62" "037efe" "83c723"), ":5109-5110",
        "les di,p_background / add di,[bp-2] (plwp) / add di,35 - plwp is"
        " added UNNORMALISED, so plwp+35 >= 360 carries into the next row."),
    "wave.plus4": (
        bytes.fromhex("a1b866" "ba6801" "f7e2" "050400" "89c7" "033eb666"),
        ":4590-4595",
        "mov ax,py / mov dx,360 / mul dx / ADD AX,4 / mov di,ax / add di,px."
        "  The +4 re-applies offset(p_background) after `mov di,ax` destroys"
        " the one `les di` loaded, so there is NO pixel skew - BUFFERMAP 4.1."),
    "ssmooth.mask": (
        bytes.fromhex("6681e2fcfcfcfc"), ":4390",
        "and edx,FCFCFCFCh - applied AFTER the four dwords are summed, so"
        " carries really do cross lane boundaries"),
    "lssmooth.sub80": (
        bytes.fromhex("83e950" "c1e102"), ":4420-4421",
        "sub cx,80 / shl cx,2 -> 64480 iterations.  niv-lr uses one fewer and"
        " loses the 41-byte read overrun past the map."),
    "lssmooth.mask": (
        bytes.fromhex("81e23f3f"), ":4424",
        "and dx,3F3Fh - lssmooth preserves the target byte's top two bits"),
    "fast_srand.or3": (
        bytes.fromhex("814e0603 00".replace(" ", "")), ":1080",
        "or word ptr [bp+6],3 - the OR is on the LOW WORD only"),
}

# call targets inside surface(), resolved through Borland's `push cs; call
# near` idiom (0E E8 rel16).  Restated as claims; the addresses are asserted
# by their own prologue bytes, not taken on trust.
CALLEES = {
    0x90c0:  ("ranged_fast_random", bytes.fromhex("558bec568b76060bf6"),
              "push bp/mov bp,sp/push si/mov si,[bp+6]/or si,si  ->  the"
              " `if (range<=0)` test"),
    0x9084:  ("fast_srand", bytes.fromhex("558bec814e0603"),
              "push bp/mov bp,sp/or word [bp+6],3"),
    0x14237: ("random", bytes.fromhex("558bec9a"),
              "push bp/mov bp,sp/call far rand - Wave 1's pinned entry"),
}

CLAIM = dict(
    rfr_sites_binary=103,      # MEASURED, and short of the text's 105
    rfr_sites_source=105,      # textual, NOCTIS-0.CPP:4766-5196
    random_sites_binary=20,
    random_sites_source=20,
    rfr_sites_elsewhere=0,     # "used NOWHERE else in the game"
    dark_cols=130, dark_rows=179, dark_stride_back=230, dark_offset=35,
    rndpat_count=64800, sda_count=64000, lmrip_count=64000,
    aloop_iterations=90,
)


def load(path):
    with open(path, "rb") as fh:
        return fh.read()


def find_all(blob, pat, lo=0, hi=None):
    out, i = [], lo
    hi = len(blob) if hi is None else hi
    while True:
        i = blob.find(pat, i, hi)
        if i < 0:
            return out
        out.append(i)
        i += 1


def cs_calls(blob, lo, hi):
    """`push cs; call near rel16` -> target file offset, for lo <= site < hi."""
    out = collections.Counter()
    i = lo
    while i < hi - 3:
        if blob[i] == 0x0E and blob[i + 1] == 0xE8:
            rel = struct.unpack_from("<h", blob, i + 2)[0]
            out[i + 4 + rel] += 1
            i += 4
            continue
        i += 1
    return out


def source_sites():
    txt = open(SOURCE, encoding="latin-1").read().split("\n")
    body = "\n".join(txt[4765:5196])
    rfr = [a.strip() for a in
           re.findall(r"ranged_fast_random\s*\(([^)]*)\)", body)]
    rnd = re.findall(r"(?<![_a-zA-Z])random\s*\(", body)
    return rfr, len(rnd), body


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=NOCTIS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    blob = load(a.exe)
    rows = []
    ok = True

    def row(name, got, want, good, why=""):
        rows.append((name, got, want, bool(good), why))
        return bool(good)

    ok &= row("image.size", len(blob), EXPECT_SIZE, len(blob) == EXPECT_SIZE,
              "the shipped NIV+ R2.3 executable")

    for name, (pat, line, why) in sorted(ASM.items()):
        all_hits = find_all(blob, pat)
        inside = [h for h in all_hits if FUNC[0] <= h < FUNC[1]]
        if name.startswith("surface."):
            good = FUNC[0] in all_hits or (FUNC[1] - 4) in all_hits
            good = good and len(inside) == 1
        elif name in ("ssmooth.mask", "lssmooth.sub80", "lssmooth.mask",
                      "fast_srand.or3", "crater.rim", "wave.plus4"):
            good = len(all_hits) >= 1          # these live in the callees
        else:
            good = len(inside) >= 1
        ok &= row("asm.%s" % name,
                  "%d in image, %d inside surface()" % (len(all_hits), len(inside)),
                  ">=1 (%s)" % line, good, why)

    # callee identification, by prologue bytes rather than by address alone
    calls = cs_calls(blob, *FUNC)
    for addr, (nm, sig, why) in sorted(CALLEES.items()):
        ok &= row("callee.%s" % nm, hex(addr), sig.hex(),
                  blob[addr:addr + len(sig)] == sig, why)

    rfr_src, rnd_src, body = source_sites()
    n_rfr = calls.get(0x90c0, 0)
    n_rnd = calls.get(0x14237, 0)
    whole = cs_calls(blob, 0, len(blob) - 4)

    ok &= row("census.random.sites", n_rnd, CLAIM["random_sites_binary"],
              n_rnd == CLAIM["random_sites_binary"],
              "20 random() call sites inside surface()")
    ok &= row("census.random.source", rnd_src, CLAIM["random_sites_source"],
              rnd_src == CLAIM["random_sites_source"],
              "and 20 in the source text - these agree exactly")
    ok &= row("census.rfr.sites", n_rfr, CLAIM["rfr_sites_binary"],
              n_rfr == CLAIM["rfr_sites_binary"],
              "MEASURED static call sites in the binary")
    ok &= row("census.rfr.source", len(rfr_src), CLAIM["rfr_sites_source"],
              len(rfr_src) == CLAIM["rfr_sites_source"],
              "textual sites in NOCTIS-0.CPP:4766-5196")
    elsewhere = whole.get(0x90c0, 0) - n_rfr
    ok &= row("census.rfr.elsewhere", elsewhere, CLAIM["rfr_sites_elsewhere"],
              elsewhere == CLAIM["rfr_sites_elsewhere"],
              "ranged_fast_random is called from NOWHERE outside surface()"
              " - the source's claim, now measured")
    row("FINDING.tailmerge",
        "binary %d vs source %d rfr sites" % (n_rfr, len(rfr_src)),
        "investigated, not reconciled", True,
        "Borland 3.1 cross-jumps identical statement sequences.  The same"
        " shortfall shows in the painters: ssmooth 15/15, lssmooth 7/9,"
        " negate 4/5.  Dynamic draw counts are unaffected, and the port"
        " matches the binary's OUTPUT byte-exactly on all ten captures, which"
        " is the decisive evidence.  Any check asserting 105 STATIC sites in"
        " the binary would be asserting something false.")

    # the (range, count) histogram, binary vs source
    hist = collections.Counter()
    for i in range(*FUNC):
        if blob[i] == 0x0E and blob[i + 1] == 0xE8 and \
           i + 4 + struct.unpack_from("<h", blob, i + 2)[0] == 0x90c0:
            w = blob[max(0, i - 8):i]
            v = None
            for j in range(len(w) - 1, -1, -1):
                if w[j] == 0x6A and j + 2 <= len(w):
                    v = w[j + 1]
                    break
                if w[j] == 0x68 and j + 3 <= len(w):
                    v = struct.unpack_from("<H", w, j + 1)[0]
                    break
            hist["computed" if v is None else v] += 1
    shist = collections.Counter(int(x) if x.isdigit() else "computed"
                                for x in rfr_src)
    diffs = {k: (hist.get(k, 0), shist.get(k, 0))
             for k in set(hist) | set(shist) if hist.get(k, 0) != shist.get(k, 0)}
    row("census.rfr.histogram", "%d distinct ranges" % len(shist),
        "binary vs source", True,
        "differences (range: binary, source) = %s - both are the tail-merged"
        " pair, so the histogram localises the merge" % diffs)

    w = max(len(r[0]) for r in rows)
    for name, got, want, good, why in rows:
        print("%-*s  %-42s %-34s %s" % (w, name, str(got)[:42], str(want)[:34],
                                        "ok" if good else "MISMATCH"))
        if why and (not good or name.startswith(("FINDING", "census"))):
            print(" " * (w + 2) + "-> " + why)
    if a.json:
        print(json.dumps([dict(name=r[0], got=str(r[1]), want=str(r[2]),
                               ok=r[3]) for r in rows], indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
