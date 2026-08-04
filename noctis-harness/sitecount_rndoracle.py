# fast_random oracles, and the check that they agree with each other.
#
# fast_random is the second of Noctis IV's two genuine 32x32 -> 64 sites, and
# unlike the galaxy hash it had no oracle of any kind. It seeds every planet
# surface, every star name and every terrain feature, through roughly 168 call
# sites, so it has to be bit-exact or nothing in the universe matches.
#
# The trap in it is arithmetic, not 64-bit: "add al, dl" is an EIGHT-BIT add
# with no carry out. Only bits 32..39 of the product are ever consumed, and
# widening the fold to 32 bits produces a different, plausible sequence.
#
# Two independent oracles, deliberately not derived from each other:
#
#   py_draws()  written here from the DOS inline assembly at
#               niv-plus/source/NOCTIS-0.CPP:1086-1101, in Python exact
#               integers, so there is no 64-bit truncation to get wrong.
#   c_draws()   sitecount_rndoracle.c, whose fast_random is copied verbatim
#               from niv-lr/src/noctis-0.cpp:830-845 - a different author's
#               independent reading of the same assembly.
#
# These two must agree BEFORE any L.in.oleum output is compared against them.
# If they disagree, the assembly has been misread and no amount of Lino work
# is meaningful yet.
#
# Layout, shared with the Lino program: two 32-bit units per draw,
#   value, seed-after-the-draw.

import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(r"C:\programmieren\linoleum", "work")

PY_BIN = os.path.join(WORK, "sitecount-rnd-py.bin")
C_BIN = os.path.join(WORK, "sitecount-rnd-c.bin")
C_SRC = os.path.join(HERE, "sitecount_rndoracle.c")
C_EXE = os.path.join(HERE, "sitecount_rndoracle.exe")

DRAWS = 4096
SEED = 12345
MASK = 0xFFFF

M32 = 0xFFFFFFFF


def py_draws(draws=DRAWS, seed=SEED, mask=MASK):
    """From the DOS assembly:

        or word ptr seed, 3          <- low word only, but 3 fits there
        mov eax, flat_rnd_seed
        mov edx, flat_rnd_seed
        mul edx                      <- UNSIGNED 32x32 -> 64
        add al, dl                   <- 8-BIT add, no carry out
        add flat_rnd_seed, ax        <- 32-bit despite the "ax" mnemonic (66 prefix)
        and ax, mask
    """
    s = seed | 3
    out = []
    for _ in range(draws):
        product = (s * s) & 0xFFFFFFFFFFFFFFFF   # unsigned, exact
        eax = product & M32
        edx = (product >> 32) & M32
        al = (eax & 0xFF)
        dl = (edx & 0xFF)
        al = (al + dl) & 0xFF                    # 8-bit wrap
        eax = (eax & 0xFFFFFF00) | al
        s = (s + eax) & M32
        out.append(((eax & mask) & M32, s))
    return out


def build_c():
    cmd = ["gcc", "-O2", "-fwrapv", "-o", C_EXE, C_SRC]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("gcc failed:\n" + p.stdout + p.stderr)
    return C_EXE


def c_draws(draws=DRAWS, seed=SEED, mask=MASK, path=C_BIN):
    build_c()
    p = subprocess.run([C_EXE, path, str(draws), str(seed), str(mask)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("C oracle failed:\n" + p.stdout + p.stderr)
    blob = open(path, "rb").read()
    vals = struct.unpack("<%dI" % (len(blob) // 4), blob)
    return [(vals[i * 2], vals[i * 2 + 1]) for i in range(len(vals) // 2)]


def write_py(path=PY_BIN, draws=DRAWS, seed=SEED, mask=MASK):
    rows = py_draws(draws, seed, mask)
    blob = b"".join(struct.pack("<II", v, s) for v, s in rows)
    open(path, "wb").write(blob)
    return rows


if __name__ == "__main__":
    py = write_py()
    c = c_draws()
    print("python oracle : %s  %d draws" % (PY_BIN, len(py)))
    print("C oracle      : %s  %d draws" % (C_BIN, len(c)))

    if len(py) != len(c):
        print("FAIL: different lengths")
        sys.exit(1)
    bad = [i for i in range(len(py)) if py[i] != c[i]]
    print("agreement     : %d/%d draws identical" % (len(py) - len(bad), len(py)))
    if bad:
        i = bad[0]
        print("  first divergence at draw %d: py=%s c=%s" % (i, py[i], c[i]))
        sys.exit(1)

    print()
    print("golden vector, seed %d | 3, mask 0x%04X - first 16 draws:" % (SEED, MASK))
    print("  " + " ".join("%5d" % v for v, _ in py[:16]))
