"""Mechanism for test_floatcontract.py: sandbox, probe source, build, run.

Two rules from the rest of the suite are kept here:

  * TESTS NEVER TOUCH work/. Every run copies the four engine sources -
    fpabi.txt, fpctl.txt, fpx87.txt and fpchains.txt - out of work/fp into a
    fresh sandbox under tests/gen and builds there. The code under test is
    still the code in work/fp: a regression there fails this test. But work/fp
    keeps whatever the pipeline left in it, including fpstarout.bin, which
    this test deliberately never opens.
  * NOTHING IS EVER WAITED ON. lino_build.ps1 and linorun.ps1 poll and kill.

WHY fpchains.txt IS REGENERATED AND NOT JUST COPIED. It is the output of
tools/genfp.py, and it is checked in so a reviewer can read bytes instead of
a generator. Both halves of that arrangement are worth guarding, so the
sandbox regenerates it from work/fp/fpsched.txt and the test asserts the
result is byte-identical to the checked-in file before building against it.

THE PROBE. One L.in.oleum programme, generated here with the star count
substituted in, running the same coordinate list through fourteen batteries.
Everything the test needs to distinguish is a battery: precision control,
rounding control, spilled intermediates, a permuted operand order, a
perturbed significand, and the same chain again after an isocall. One binary
for all of them means no battery can differ because of how it was built.

THE FILE-NAME TRAP. An underscore inside a lino string literal is emitted as
a SPACE, so every generated name here is underscore-free.

THE MID-BRACKET ISOCALL WRITES ITS OWN FILE, tfpiso.bin, and not the result
file. linorun.ps1 stops the programme the moment a fresh result file appears,
so an early write to the result file would truncate the run - the output
would look plausible and be short.
"""

import os
import re
import shutil
import subprocess
import sys

import linoharness as L

FPWORK = os.path.join(L.WORK, "fp")
GENFP = os.path.join(L.REPO, "tools", "genfp.py")

LIBS = ("fpabi.txt", "fpctl.txt", "fpx87.txt")
SCHED = "fpsched.txt"
CHAINS = "fpchains.txt"

STEM = "tfpcontract"

# (name, what it is, the requirement in one word)
#   exact     - must reproduce the catalogue for every record
#   break     - must NOT, and by a predicted amount
#   measured  - recorded, not asserted to fail; see test_floatcontract
BATTERIES = [
    ("NsIdentity, CW 133F", "exact"),
    ("NsIdentity, operands permuted", "exact"),
    ("NsIdentity, ambient word (FEnter skipped)", "break"),
    ("NsIdentity, CW 123F  PC=53", "break"),
    ("NsIdentity, CW 103F  PC=24", "break"),
    ("NsIdentity, CW 1F3F  RC=chop", "break"),
    ("NsIdentitySpill3, one store mid-chain", "break"),
    ("NsIdentitySpillAll, a store per operation", "break"),
    ("IsThereIdentity, the lookup formula", "break"),
    ("TBYTE round trip after op 1, no flip", "exact"),
    ("one binary64 ULP (ext bit 11) after op 1", "break"),
    ("one EXTENDED ULP (ext bit 0) after op 1", "measured"),
    ("one ULP of the final binary64", "break"),
    ("NsIdentity again, after an isocall", "exact"),
]
NBAT = len(BATTERIES)
ISOBAT = NBAT - 1

# The two source-level breaks. Each mutates ONE engine source in the sandbox
# and nothing else, so what fails is attributable.
BREAK_NONE, BREAK_NOCW, BREAK_SPILL = "good", "nocw", "spilled"


# --------------------------------------------------------------- the mutations

def break_nocw(text):
    """Delete every `fldcw [FCW]` from fpctl - FEnter's and FLoadCW's.

    This is the "documenting the control word instead of stating it" bug, and
    it has to remove both or the second one puts back what the first stopped
    installing. What is left still SAVES the ambient word and still restores
    it, so the programme looks well behaved; it simply computes under
    whatever the runtime handed it. On win32 that is 0E7Fh - the C runtime's
    027Fh with 0C00h ORed in by the L.in.oleum stub, i.e. 53-bit precision
    and rounding toward zero. The probe reports the word it actually found,
    so the test predicts this break from a measurement rather than from a
    story about win32.
    """
    pat = "D9 AF <dFCW mtp bytesperunit>"
    n = text.count(pat)
    return text.replace(pat, "90" + " " * (len(pat) - 2)), n


def break_spill(text):
    """Insert one fstp/fld qword pair into NsIdentity, after the first fidiv.

    Not an arbitrary corruption: it is exactly what a backend that keeps the
    running value of an expression in a double temporary produces, and it is
    the mistake this whole wave exists to rule out. The referee predicts the
    result, so the break is graded rather than merely observed.
    """
    i = text.index('\n"NsIdentity"\n')
    j = text.index('"NsIdentityPermuted"')
    body = text[i:j]
    m = re.search(r"^.*\(fidiv.*\n", body, re.M)
    if not m:
        raise ValueError("no fidiv in NsIdentity")
    ins = ("\t    DD 9F <dFT0 mtp bytesperunit>         (BREAK fstp qword)\n"
           "\t    DD 87 <dFT0 mtp bytesperunit>         (BREAK fld  qword)\n")
    body = body[:m.end()] + ins + body[m.end():]
    return text[:i] + body + text[j:], 1


# ----------------------------------------------------------------- the sandbox

class Probe(object):
    """One sandbox: engine sources, a generated probe, a build and a run."""

    def __init__(self, nstar, flavour=BREAK_NONE):
        self.nstar = nstar
        self.flavour = flavour
        self.dir = os.path.join(L.gen_dir(), "tfp" + flavour)
        os.makedirs(self.dir, exist_ok=True)
        self.src = os.path.join(self.dir, STEM + ".txt")
        self.exe = os.path.join(self.dir, STEM + ".exe")
        self.inp = os.path.join(self.dir, "tfpin.bin")
        self.out = os.path.join(self.dir, "tfpout.bin")
        self.iso = os.path.join(self.dir, "tfpiso.bin")
        self.notes = []

    # -- sources ------------------------------------------------------------

    def install_sources(self):
        """Copy the libraries in, regenerate fpchains, apply the mutation.

        Returns (chains_identical_to_checked_in, mutation_count).
        """
        for lib in LIBS:
            shutil.copyfile(os.path.join(FPWORK, lib),
                            os.path.join(self.dir, lib))
        shutil.copyfile(os.path.join(FPWORK, SCHED),
                        os.path.join(self.dir, SCHED))
        gen = os.path.join(self.dir, CHAINS)
        p = subprocess.run([sys.executable, GENFP, SCHED, CHAINS],
                           cwd=self.dir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise RuntimeError("genfp.py failed: %s%s" % (p.stdout, p.stderr))
        with open(gen, "r", encoding="utf-8", errors="replace") as fh:
            fresh = fh.read()
        with open(os.path.join(FPWORK, CHAINS), "r",
                  encoding="utf-8", errors="replace") as fh:
            stored = fh.read()
        same = fresh == stored

        nmut = 0
        if self.flavour == BREAK_NOCW:
            path = os.path.join(self.dir, "fpctl.txt")
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                t = fh.read()
            t, nmut = break_nocw(t)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(t)
        elif self.flavour == BREAK_SPILL:
            fresh, nmut = break_spill(fresh)
            with open(gen, "w", encoding="utf-8") as fh:
                fh.write(fresh)

        with open(self.src, "w", encoding="utf-8") as fh:
            fh.write(source(self.nstar))
        return same, nmut

    # -- build and run ------------------------------------------------------

    def build(self):
        for stale in (self.exe, self.out, self.iso):
            if os.path.exists(stale):
                os.remove(stale)
        rc, msg = L.build(self.src)
        return rc == 0, msg.strip()

    def write_input(self, trips):
        import struct
        with open(self.inp, "wb") as fh:
            for (x, y, z) in trips:
                fh.write(struct.pack("<3i", x, y, z))

    def run(self, timeout=180):
        rc, msg, blob = L.run(self.exe, self.out, timeout_sec=timeout)
        return blob, msg

    # -- the third engine ---------------------------------------------------

    def cref(self):
        """A gcc-built hardware x87 witness over the same input file.

        Neither the port nor the model: a different compiler emitting the
        same instructions, on the same silicon. It exists because two
        implementations that agree can still both be wrong in the same way,
        and because a Python model of rounding is exactly the kind of thing
        that is wrong in a way only hardware notices.

        Returns ([bat133F, bat123F, bat103F], note) or (None, why-not).
        """
        import shutil
        import struct
        if shutil.which("gcc") is None:
            return None, "gcc is not on PATH"
        csrc = os.path.join(self.dir, "tfpcref.c")
        cexe = os.path.join(self.dir, "tfpcref.exe")
        cout = os.path.join(self.dir, "tfpcref.bin")
        with open(csrc, "w", encoding="utf-8") as fh:
            fh.write(CREF_C)
        for stale in (cexe, cout):
            if os.path.exists(stale):
                os.remove(stale)
        p = subprocess.run(["gcc", "-O1", "-Wall", "-o", cexe, csrc],
                           cwd=self.dir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode != 0:
            return None, "gcc failed: " + (p.stdout or "") + (p.stderr or "")
        p = subprocess.run([cexe], cwd=self.dir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode != 0 or not os.path.exists(cout):
            return None, "the C witness did not run: " + (p.stdout or "")
        with open(cout, "rb") as fh:
            blob = fh.read()
        n = len(blob) // 24
        v = struct.unpack("<%dQ" % (3 * n), blob)
        return [list(v[b * n:(b + 1) * n]) for b in range(3)], p.stdout.strip()


CREF_C = r"""/* tfpcref - the third engine. GENERATED by tests/fpdrive.py.
 *
 * Reads tfpin.bin (int32 x,y,z triples) and writes tfpcref.bin: the same
 * chain at control words 133F, 123F and 103F, as raw binary64 patterns,
 * three batteries back to back.
 *
 * The schedule below is the schedule, written out: five operations and one
 * store, with the running value never leaving st(0). gcc is told nothing
 * about what it computes, so it cannot helpfully rearrange it.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static double chain(int x, int y, int z, unsigned short cw)
{
    int k = 100000;
    unsigned short sav;
    double out;
    __asm__ volatile ("fnstcw %0" : "=m" (sav));
    __asm__ volatile ("fldcw %0" : : "m" (cw));
    __asm__ volatile (
        "fildl  %1\n\t"
        "fidivl %4\n\t"
        "fildl  %2\n\t"
        "fmulp  %%st,%%st(1)\n\t"
        "fidivl %4\n\t"
        "fildl  %3\n\t"
        "fmulp  %%st,%%st(1)\n\t"
        "fidivl %4\n\t"
        "fstpl  %0\n\t"
        : "=m" (out)
        : "m" (x), "m" (y), "m" (z), "m" (k));
    __asm__ volatile ("fldcw %0" : : "m" (sav));
    return out;
}

int main(void)
{
    static const unsigned short cws[3] = { 0x133F, 0x123F, 0x103F };
    FILE *f = fopen("tfpin.bin", "rb");
    long n, i;
    int *t;
    int b;
    if (!f) { fprintf(stderr, "no tfpin.bin\n"); return 2; }
    fseek(f, 0, SEEK_END);
    n = ftell(f) / 12;
    fseek(f, 0, SEEK_SET);
    t = (int *) malloc((size_t) n * 12);
    if (!t || fread(t, 12, (size_t) n, f) != (size_t) n) return 2;
    fclose(f);
    f = fopen("tfpcref.bin", "wb");
    if (!f) return 2;
    for (b = 0; b < 3; b++)
        for (i = 0; i < n; i++) {
            double d = chain(t[3*i], t[3*i+1], t[3*i+2], cws[b]);
            unsigned long long u;
            memcpy(&u, &d, 8);
            fwrite(&u, 8, 1, f);
        }
    fclose(f);
    printf("tfpcref: %ld triples x 3 control words\n", n);
    return 0;
}
"""


# ------------------------------------------------------------ the probe source

def source(nstar):
    return TEMPLATE % dict(
        stem=STEM, nstar=nstar, nbat=NBAT, isobat=ISOBAT, hdr=16,
        nins=3 * nstar, nouts=2 * nstar * NBAT)


TEMPLATE = r"""      ( *** %(stem)s - GENERATED by tests/fpdrive.py, do not edit ***

	The Wave 3 float contract, measured in one binary.

	Reads tfpin.bin: %(nstar)d int32 coordinate triples, one per
	catalogue record that the galaxy sweep offered exactly ONE
	candidate for.  The unambiguity is the point: no triple here can
	have been chosen because it reproduced its record.

	Runs %(nbat)d batteries over that list and writes tfpout.bin:
	%(hdr)d header units then %(nbat)d x %(nstar)d doubles.

	  0  NsIdentity at CW 133F - the original's word.  THE CLAIM.
	  1  the same arithmetic with the operands permuted.  Must score
	     identically: a test that keys on operand order rather than
	     on arithmetic passes every break below and fails this.
	  2  the AMBIENT control word - FEnter's saved one, reinstalled.
	     Header slot 2 says what that word was.
	  3  CW 123F, precision control 53 bits.
	  4  CW 103F, precision control 24 bits - L.in.oleum's own float
	     instructions.
	  5  CW 1F3F, 64 bits but rounding toward zero.
	  6  one intermediate narrowed to binary64 mid-chain.
	  7  a store after every operation.
	  8  the game's isthere() lookup formula - a real formula that
	     did not write the catalogue.  Required score: zero.
	  9  CONTROL.  The intermediate after operation 1 pushed through
	     a 10-byte TBYTE and pulled back.  An extended round trip is
	     lossless, so this must score like battery 0.  Without it,
	     10 and 11 could be blamed on the store rather than the bit.
	 10  BREAK.  Bit 11 of that intermediate's significand flipped -
	     one binary64 ULP, the last bit a double keeps.
	 11  MEASURED, not asserted.  Bit 0 flipped - one EXTENDED ULP,
	     2^-63 relative.  The oracle's resolution is coarser than
	     this; the test records what it actually is.
	 12  BREAK.  One ULP of the final binary64 itself.
	 13  NsIdentity again, run after a real isocall inside the
	     FEnter bracket.  Header slots 5 and 6 hold the control word
	     read immediately before and immediately after that isocall.

	The isocall in battery %(isobat)d writes tfpiso.bin and NOT the result
	file, because linorun.ps1 stops the programme as soon as a fresh
	result file appears.                                             )

"libraries"

	fpabi;
	fpctl;
	fpx87;
	fpchains;

"directors"

	program name = { %(stem)s };
	unit = 32;

"constants"

	NSTAR	= %(nstar)d;
	NBAT	= %(nbat)d;
	HDR	= %(hdr)d;
	ISOBAT	= %(isobat)d;

"variables"

	fcinput	 = { tfpin.bin };
	fcresult = { tfpout.bin };
	fcisofile = { tfpiso.bin };

	fciptr	= 0;
	fcoptr	= 0;
	fcns	= 0;
	fcbat	= 0;

	FCK100000 = 100000;
	FCT0	= 0;		( TBYTE scratch: 10 bytes over 3 units )
	FCT1	= 0;
	FCT2	= 0;

"workspace"

	fchead	= %(hdr)d;
	fcins	= %(nins)d;
	fcouts	= %(nouts)d;

"programme"

	[File Name]	= fcinput;
	[File Position]	= 0;
	[File Command]	= READ;
	[Block Pointer]	= fcins;
	[Block Size]	= %(nins)d;
	[Block Size]	* BYTES PER UNIT;
	isocall;

	( The ambient control word, before this programme says anything.
	  On win32 the runtime stub ORs 0C00h into it - RC=chop - and on
	  linux it does not touch it at all.  That difference is why
	  FEnter exists, so it is measured rather than described. )
	=> FCWRead;
	A = [FI];		[fchead plus 2] = A;

	[FCW] = FCWEXT;
	=> FEnter;
	A = [FCWSAV];		[fchead plus 3] = A;
	=> FCWRead;
	A = [FI];		[fchead plus 4] = A;

	( qword layout: fld1 must land 00000000h then 3FF00000h, or every
	  score below is meaningless for a reason that is not arithmetic )
	[FA0] = 0; [FA1] = 0;
	{
	    D9 E8				(fld1)
	    DD 9F <dFA0 mtp bytesperunit>	(fstp qword [edi+FA0*4])
	}
	A = [FA0];		[fchead plus 0] = A;
	A = [FA1];		[fchead plus 1] = A;

	[fchead plus 5] = 0;
	[fchead plus 6] = 0;

	A = fcouts; [fcoptr] = A;
	[fcbat] = 0;

    "fcbattery"

	=> fcsetcw;

      ? [fcbat] = ISOBAT -> fciso;
	-> fcstars;

    "fciso"

	=> FCWRead;
	A = [FI];		[fchead plus 5] = A;

	[File Name]	= fcisofile;
	[File Position]	= 0;
	[File Command]	= WRITE;
	[Block Pointer]	= fchead;
	[Block Size]	= HDR;
	[Block Size]	* BYTES PER UNIT;
	isocall;

	[File Name]	= fcisofile;
	[File Position]	= 0;
	[File Command]	= SET SIZE;
	[File Size]	= HDR;
	[File Size]	* BYTES PER UNIT;
	isocall;

	=> FCWRead;
	A = [FI];		[fchead plus 6] = A;

    "fcstars"

	A = fcins; [fciptr] = A;
	[fcns] = 0;

    "fconestar"

	E = [fciptr];
	A = [E];		[FJ0] = A;
	A = [E plus 1];		[FJ1] = A;
	A = [E plus 2];		[FJ2] = A;

	=> fcdispatch;

	E = [fcoptr];
	A = [FA0];		[E] = A;
	A = [FA1];		[E plus 1] = A;
	A = [fcoptr]; A + 2;	[fcoptr] = A;

	A = [fciptr]; A + 3;	[fciptr] = A;
	[fcns]+;
      ? [fcns] < NSTAR -> fconestar;

	[fcbat]+;
      ? [fcbat] < NBAT -> fcbattery;

	( put the stated word back before the closing measurements, so a
	  battery that changed it cannot be mistaken for a leak )
	[FCW] = FCWEXT;
	=> FLoadCW;

	=> FStackOK;
	A = [FI];		[fchead plus 7] = A;
	A = [FFLG];		[fchead plus 8] = A;
	[fchead plus 9]	 = NSTAR;
	[fchead plus 10] = NBAT;
	[fchead plus 11] = 0DEFACEDh;
	[fchead plus 12] = 0;
	[fchead plus 13] = 0;
	[fchead plus 14] = 0;
	[fchead plus 15] = 0;

	=> FLeave;

	[File Name]	= fcresult;
	[File Position]	= 0;
	[File Command]	= WRITE;
	[Block Pointer]	= fchead;
	[Block Size]	= HDR;
	[Block Size]	* BYTES PER UNIT;
	isocall;

	[File Name]	= fcresult;
	[File Position]	= HDR;
	[File Position] * BYTES PER UNIT;
	[File Command]	= WRITE;
	[Block Pointer]	= fcouts;
	[Block Size]	= %(nouts)d;
	[Block Size]	* BYTES PER UNIT;
	isocall;

	[File Name]	= fcresult;
	[File Position]	= 0;
	[File Command]	= SET SIZE;
	[File Size]	= %(nouts)d;
	[File Size]	+ HDR;
	[File Size]	* BYTES PER UNIT;
	isocall;

	end;

( ==================================================================== )
( the control word this battery runs under                              )
( ==================================================================== )

"fcsetcw"
      ? [fcbat] = 2 -> fccwambient;
      ? [fcbat] = 3 -> fccwdbl;
      ? [fcbat] = 4 -> fccwsgl;
      ? [fcbat] = 5 -> fccwchop;
	[FCW] = FCWEXT;
	=> FLoadCW;
	end;

    "fccwambient"
	A = [FCWSAV];	[FCW] = A;
	=> FLoadCW;
	end;

    "fccwdbl"
	[FCW] = FCWDBL;
	=> FLoadCW;
	end;

    "fccwsgl"
	[FCW] = FCWSGL;
	=> FLoadCW;
	end;

    "fccwchop"
	[FCW] = FCWEXTCHOP;
	=> FLoadCW;
	end;

( ==================================================================== )
( which schedule this battery runs                                      )
( ==================================================================== )

"fcdispatch"
      ? [fcbat] = 1 -> fcdperm;
      ? [fcbat] = 6 -> fcdspill3;
      ? [fcbat] = 7 -> fcdspillall;
      ? [fcbat] = 8 -> fcdisthere;
      ? [fcbat] = 9 -> fcdroundtrip;
      ? [fcbat] = 10 -> fcdflip11;
      ? [fcbat] = 11 -> fcdflip0;
      ? [fcbat] = 12 -> fcdfinal;
	=> NsIdentity;
	end;

    "fcdperm"
	=> NsIdentityPermuted;
	end;

    "fcdspill3"
	=> NsIdentitySpill3;
	end;

    "fcdspillall"
	=> NsIdentitySpillAll;
	end;

    "fcdisthere"
	=> IsThereIdentity;
	end;

    "fcdroundtrip"
	=> FCRoundTrip;
	end;

    "fcdflip11"
	=> FCFlip11;
	end;

    "fcdflip0"
	=> FCFlip0;
	end;

    "fcdfinal"
	=> FCFinalUlp;
	end;

( ==================================================================== )
( the perturbation schedules                                            )
( ==================================================================== )

      ( FCRoundTrip - NsIdentity with the intermediate after operation 1
	stored as a 10-byte TBYTE and reloaded.  An extended store keeps
	all 64 significand bits, so this is the identity function and
	must score exactly like battery 0. )

"FCRoundTrip"
	{
	    DB 87 <dFJ0 mtp bytesperunit>	(fild  x)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB BF <dFCT0 mtp bytesperunit>	(fstp  tbyte)
	    DB AF <dFCT0 mtp bytesperunit>	(fld   tbyte)
	    DB 87 <dFJ1 mtp bytesperunit>	(fild  y)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB 87 <dFJ2 mtp bytesperunit>	(fild  z)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DD 9F <dFA0 mtp bytesperunit>	(fstp  qword id)
	}
	end;

      ( FCFlip11 - the same round trip with bit 11 of the 64-bit
	significand XORed while the value sits in memory.  Bit 11 is the
	LAST bit a binary64 keeps, so this is one double ULP applied to
	an intermediate that in the real chain never reaches memory. )

"FCFlip11"
	{
	    DB 87 <dFJ0 mtp bytesperunit>	(fild  x)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB BF <dFCT0 mtp bytesperunit>	(fstp  tbyte)
	    81 B7 <dFCT0 mtp bytesperunit> 00 08 00 00	(xor dword,800h)
	    DB AF <dFCT0 mtp bytesperunit>	(fld   tbyte)
	    DB 87 <dFJ1 mtp bytesperunit>	(fild  y)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB 87 <dFJ2 mtp bytesperunit>	(fild  z)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DD 9F <dFA0 mtp bytesperunit>	(fstp  qword id)
	}
	end;

      ( FCFlip0 - bit 0 instead: one EXTENDED ULP, 2^-63 relative.  This
	is the finest edit the arithmetic can carry, and the point of
	measuring it is that the oracle grades a binary64, ten bits
	coarser.  What this battery scores is a property of the ORACLE,
	not of the engine. )

"FCFlip0"
	{
	    DB 87 <dFJ0 mtp bytesperunit>	(fild  x)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB BF <dFCT0 mtp bytesperunit>	(fstp  tbyte)
	    81 B7 <dFCT0 mtp bytesperunit> 01 00 00 00	(xor dword,1)
	    DB AF <dFCT0 mtp bytesperunit>	(fld   tbyte)
	    DB 87 <dFJ1 mtp bytesperunit>	(fild  y)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB 87 <dFJ2 mtp bytesperunit>	(fild  z)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DD 9F <dFA0 mtp bytesperunit>	(fstp  qword id)
	}
	end;

      ( FCFinalUlp - the exact chain, then one ULP of the RESULT.  This
	is the perturbation the oracle is guaranteed to see, and it is
	the floor the other two are measured against. )

"FCFinalUlp"
	{
	    DB 87 <dFJ0 mtp bytesperunit>	(fild  x)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB 87 <dFJ1 mtp bytesperunit>	(fild  y)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DB 87 <dFJ2 mtp bytesperunit>	(fild  z)
	    DE C9				(fmulp st1,st0)
	    DA B7 <dFCK100000 mtp bytesperunit>	(fidiv 100000)
	    DD 9F <dFA0 mtp bytesperunit>	(fstp  qword id)
	    81 B7 <dFA0 mtp bytesperunit> 01 00 00 00	(xor dword,1)
	}
	end;
"""
