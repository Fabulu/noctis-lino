#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
sp_ex1.py -- Wave 6b, EX1: the exactness proof, EXECUTED.

The claim.  The entire float content of the sphere pixel loop, per component
(NOCTIS-0.CPP:3106-3110 and :3246-3250), is

    fild  word ptr temp        ; sign-extended map byte, int16
    fmul  dword ptr mag_factor ; float32
    fistp word ptr temp        ; CW 133Fh -> round half to EVEN

dy is 8 bits with sign (measured range -87..+86), dx is 9 bits with sign
(-106..+105), and mag_factor has a 24-bit significand.  The exact product
therefore needs at most 33 significand bits, which is representable at
PC=64 -- so THE FMUL ROUNDS NOTHING and the single rounding in the chain is
the FISTP.  The result is a pure INTEGER function of (dy:int16,
mag_factor:uint32), and the sphere rasteriser leaves the float engine
entirely: no x87 fragments, no lino native floats, no 24-bit narrowing
hazard.

This is a provable claim, so the wave PROVES IT BY ENUMERATION rather than
asserting it.  sp_spec.rhe_scale computes it with integer arithmetic and no
float multiply at all; sp_ref.exe runs the real instructions at the real
control word on real hardware; this file compares them over

  (a) every mag_factor in the pinned corpus,
  (b) a pseudo-random sweep of float32 patterns in [0.001, 1.32],
  (c) THE ADVERSARIAL SET -- the float32 neighbours of (k+0.5)/dy, which is
      exactly where a float32 multiply and the exact chain disagree.

(c) is what makes this a check rather than a hope.  A control implementation
using a float32 multiply passes (a) and (b) and FAILS (c), and the control is
run here so nobody has to take that on trust.

THIS FILE RENDERS NO VERDICTS.  It prints counts.  tests/test_sphere.py
decides what they must be.

Usage:  python sp_ex1.py [--work DIR] [--cc gcc] [--quick]
"""

import argparse
import os
import random
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_spec as S                                            # noqa: E402


def live_values():
    """The map bytes that actually occur, both axes, from the shipped file."""
    draws, _, _, _ = S.decode_globes(S.asset("GLOBES.MAP"))
    v = set()
    for (_c, dx, dy) in draws:
        v.add(dx)
        v.add(dy)
    return sorted(v)


def corpus_mags(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for ln in f:
            for tok in ln.split():
                if tok.startswith("mag="):
                    try:
                        out.append(int(tok[4:], 16))
                    except ValueError:
                        pass
    return sorted(set(out))


def check_stream(f):
    """Streamed, never spooled.  The adversarial set is 18.1 MILLION
    comparisons; writing it to disk costs 360 MB per run and leaves an
    artifact behind, which is precisely the failure mode Wave 6a's O2
    records.  Nothing here touches the filesystem."""
    tot = diff = 0
    ex = []
    if True:
        for ln in f:
            if not ln.startswith("SCALE"):
                continue
            _, mb, dy, v = ln.split()
            mb, dy, v = int(mb, 16), int(dy), int(v)
            g = S.rhe_scale(dy, mb)
            tot += 1
            if g != v:
                diff += 1
                if len(ex) < 5:
                    ex.append((hex(mb), dy, v, g))
    return tot, diff, ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=os.path.join(HERE, "spwork"))
    ap.add_argument("--cc", default="gcc")
    ap.add_argument("--quick", action="store_true")
    x = ap.parse_args()
    W = x.work
    os.makedirs(W, exist_ok=True)
    exe = os.path.join(W, "sp_ref.exe")
    if not os.path.exists(exe):
        subprocess.run([x.cc, "-O2", "-std=gnu11", "-o", exe, "sp_ref.c",
                        "-lm"], check=True, cwd=HERE)

    lv = live_values()
    print("live map values: %d distinct, %d..%d" % (len(lv), lv[0], lv[-1]))

    sets = {}
    sets["corpus"] = corpus_mags(os.path.join(HERE, "sp_corpus.spc"))
    rng = random.Random(20260806)
    sets["random"] = sorted({struct.unpack("<I", struct.pack(
        "<f", rng.uniform(0.001, 1.32)))[0]
        for _ in range(300 if x.quick else 3000)})
    sets["adversarial"] = S.adversarial_mags(lv, per=1 if x.quick else 3)

    print("%-14s %10s %12s %10s   %s"
          % ("SET", "patterns", "compared", "differ", "note"))
    rc = 0
    for nm, pats in sets.items():
        if not pats:
            print("%-14s %10d  (EMPTY -- the set must not be empty)" % (nm, 0))
            rc = 1
            continue
        sp = os.path.join(W, "ex1_%s.set" % nm)
        with open(sp, "w", newline="\n") as f:
            f.write("\n".join("%08x" % b for b in pats) + "\n")
        for tag, extra in (("x87", []), ("f32control", ["--scalemul=f32"])):
            proc = subprocess.Popen([exe, "--scaleset=" + sp] + extra,
                                    stdout=subprocess.PIPE, cwd=HERE,
                                    text=True, bufsize=1 << 20)
            tot, diff, ex = check_stream(proc.stdout)
            proc.stdout.close()
            if proc.wait() != 0:
                raise SystemExit("sp_ex1: sp_ref.exe failed")
            note = ("MUST be 0" if tag == "x87"
                    else "CONTROL: MUST be non-zero")
            print("%-14s %10d %12d %10d   %s %s"
                  % (nm + "/" + tag, len(pats), tot, diff, note,
                     ex[:2] if ex else ""))
            if tag == "x87" and diff:
                rc = 1
            if tag == "f32control" and nm == "adversarial" and not diff:
                rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
