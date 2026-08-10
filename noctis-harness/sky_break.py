r"""Generate and qualify one-edit C sky mutants in private sandboxes.

The source contains named ``#define SKY_MUT_* 0`` switches.  A generated
mutant changes exactly one zero to one; the corpus, Python oracle, offset map,
and driver invocation remain unchanged.  Every kill is reported as a named
corpus row plus a named SKY1 record/field, never only as an aggregate hash.

Two requested mutants are deliberately listed but not claimed killable.  The
pure horizon float reassociation was exhausted over all 7,680 valid
``byte,row`` pairs (byte 0..63, row 0..119), including the night /2 variants;
it is observationally identical after chop.  Its realistic replacement is
HORIZON_INT_DIV_FIRST, which performs ``(byte/120)*row`` in integer domain.

The zero-denominator mutant likewise is not claimed
killable.  In cloudy_sky the denominator is zero only at x=-r,y=-r, while the
paint predicate there is sqrt(1.2*r*r)<r, false for every source radius
r=5..29.  The tight reachable bound is den^2=1 at r=5,x=-5,y=-4.  The
replacement CLOUD_NO_SCALE64 mutant is witnessed on the canonical
``ocean_11draw_b_min_denominator`` row and exercises that reachable pixel.

Usage:
  python sky_break.py --list
  python sky_break.py --emit OCEAN_12_DRAWS path/to/mutant.c
  python sky_break.py [--only NAME] [--keep DIR]
"""

from __future__ import print_function

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import sky_corpus as C
import sky_grade as G
import sky_spec as S


TESTS = os.path.join(ROOT, "tests")
WORK = os.path.join(ROOT, "work")
LINO_BUILD = os.path.join(ROOT, "lino_build.ps1")
LINO_RUN = os.path.join(TESTS, "w7arun.ps1")
LINO_COMPILER = os.path.join(ROOT, "main", "lib", "gen", "compiler114m.exe")
LINO_CPU = "i386m"
LINO_LIBS = (
    "fbmem.txt", "fbpal.txt", "pgfp.txt", "spmem.txt", "spbg.txt",
    "brtl.txt", "mul64frag.txt", "suseed.txt", "surng.txt", "subuf.txt",
    "susm.txt", "sky.txt",
)
FP_LIBS = ("fpabi.txt", "fpctl.txt", "fpx87.txt", "fpconv.txt")
ASSETS = ("globes.map", "offsets.map")


# name: (corpus row, target kind, phase, body unit or None, description)
MUTANTS = {
    "OCEAN_12_DRAWS": ("ocean_11draw_a", S.LEDGER, 3, 1,
        "one extra pre-cloud BRTL draw"),
    "TYPE5_9_DRAWS": ("thin_type5_sixdraw", S.LEDGER, 3, 1,
        "three extra type-5 pre-cloud BRTL draws"),
    "REMOVE_ALBEDO": ("ocean_11draw_b_min_denominator", S.LEDGER, 3, None,
        "cloud density omits +albedo"),
    "CLOUD_NO_SCALE64": ("ocean_11draw_b_min_denominator", S.PRE_HORIZON, 0, None,
        "reachable den^2=1 cloud pixel omits the source *64"),
    "BYTE_SMOOTH": ("ocean_11draw_a", S.PRE_HORIZON, 0, None,
        "byte-wise average replaces the DOS dword-carry smoother"),
    "OUT_OF_PLACE": ("ocean_11draw_a", S.PRE_HORIZON, 0, None,
        "smoother reads a snapshot instead of its in-place output"),
    "SS_STRIDE_320": ("ocean_11draw_a", S.PRE_HORIZON, 0, None,
        "ssmooth uses stride 320 instead of 360"),
    "PS_STRIDE_360": ("venus_psmooth_only", S.PRE_HORIZON, 0, None,
        "psmooth_grays uses stride 360 instead of 320"),
    "LS_DROP_RIGHT": ("venus_tail_hostile", S.PRE_HORIZON, 0, None,
        "lssmooth drops i+1 and i+361"),
    "LS_CLAMP_TAIL": ("venus_tail_hostile", S.PRE_HORIZON, 0, None,
        "lssmooth clamps readable tail accesses"),
    "HORIZON_119": ("ocean_night", S.FINAL_SBG, 0, None,
        "horizon row count 120 -> 119"),
    "HORIZON_121": ("ocean_night", S.FINAL_SBG, 0, None,
        "horizon row count 120 -> 121"),
    "HORIZON_WIDTH_359": ("ocean_night", S.FINAL_SBG, 0, None,
        "horizon width 360 -> 359"),
    "HORIZON_WIDTH_361": ("ocean_night", S.FINAL_SBG, 0, None,
        "horizon width 360 -> 361"),
    "HORIZON_NO_NIGHT_HALF": ("ocean_night", S.FINAL_SBG, 0, None,
        "night horizon omits divide by two"),
    "HORIZON_INT_DIV_FIRST": ("ocean_night", S.FINAL_SBG, 0, None,
        "premature integer division computes (byte/120)*row"),
    "ATMOSPHERE_BUFFER": ("ocean_airless_pair", S.PALETTE, 0, None,
        "fill byte is confused with the atmosphere boolean"),
    "PALETTE_TO_PAL6": ("ocean_night", S.PALETTE, 0, None,
        "shade destination redirects from srfpal6 to pal6"),
    "ROUND_CHOP": ("smoke_airless_type1", S.PALETTE, 0, None,
        "round-to-nearest replaces a float-to-byte chop"),
    "REMOVE_T3_NIGHT_GOTO": ("ocean_night", S.PALETTE, 0, None,
        "type-3 night special-palette control transfer is removed"),
    "WRONG_RNG_SEED": ("ocean_11draw_a", S.LEDGER, 1, 5,
        "both RNG streams receive seed+1"),
    "WRONG_RNG_STREAM": ("thin_type5_sixdraw", S.LEDGER, 2, None,
        "type-5 colour draws use the fast-state object"),
    "STALE_TYPE5_BRIGHTNESS": ("thin_type5_sixdraw", S.SCALARS, 0, 0,
        "type-5 final brightness stays stale while frozen pre-switch sb keeps palette exact"),
    "NO_QW_RESTORE": ("ocean_11draw_a", S.GUARDS, 0, 9,
        "painter leaves QUADWORDS at st_bytes/4"),
    "SBG_OOB": ("smoke_airless_type1", S.GUARDS, 0, 3,
        "one semantic SBG write targets offset 64800"),
    "WIDE_SCALE_FLOATS": ("float_store_palette_witness", S.PALETTE, 0, 66,
        "dfs, sb, and saturation remain binary64; palette byte 267 is wrong"),
}

NOT_APPLICABLE = {
    "ZERO_DENOM_ZERO": (
        "no create_sky corpus row can execute den==0: denominator zero "
        "requires (-r,-r), which fails sqrt(1.2*r*r)<r for r=5..29"),
    "HORIZON_ORDER": (
        "exhaustive source-domain proof over b=0..63,row=0..119: "
        "chop(f32(b*row/120)) equals chop(f32(f32(b/120)*row)) in all "
        "7680 pairs; night /2 variants also agree (first difference needs "
        "invalid sky byte b=70 at row 108)")
}


# Lino mutations are exact substitutions over copied production libraries.
# Tuple layout: (witness, kind, phase, body-unit-or-None, source file,
#                ((old, new), ...), description).
# Multiple substitutions are allowed only when they form one semantic edit
# whose faithful spelling necessarily has more than one instruction site
# (currently WRONG_RNG_SEED only).  Every old token must occur exactly once.

_SSMOOTH = '''"SU ssmooth"
	A = nw; A + [SUpbase]; [SUsp] = A;
	[SUsi] = SSFROM;
	B = NSS;
    "SU ss u"
	C = [SUsp]; C + [SUsi]; C - 360;
	=> SU dw at; E = D;
	C + 360; => SU dw at; E + D;
	C + 360; => SU dw at; E + D;
	C + 360; => SU dw at; E + D;

	E & 0FCFCFCFCh;
	E > 2;
	A = E; A & 0FFh;
	D = E; D > 8; D & 0FFh; A + D; A & 0FFh;
	E > 16;
	D = E; D & 0FFh; A + D; A & 0FFh;
	D = E; D > 8; D & 0FFh; A + D; A & 0FFh;
	A > 2;

	C = [SUsp]; C + [SUsi];
	[C] = A;
	[SUsi]+;
	B ^ SU ss u;
	end;'''

_SSMOOTH_BYTE = '''"SU ssmooth"
	A = nw; A + [SUpbase]; [SUsp] = A;
	[SUsi] = SSFROM;
	B = NSS;
    "SU ss u"
	C = [SUsp]; C + [SUsi]; C - 360; A=[C]; A&0FFh; E=A;
	C + 360; A=[C]; A&0FFh; E+A;
	C + 360; A=[C]; A&0FFh; E+A;
	C + 360; A=[C]; A&0FFh; E+A;
	E '/ 4; A=E;
	C = [SUsp]; C + [SUsi]; [C] = A;
	[SUsi]+;
	B ^ SU ss u;
	end;'''

_SSMOOTH_OUT = '''"SU ssmooth"
	A = nw; A + [SUpbase]; [SUsp] = A;
	[SUsi] = SSFROM;
	B = NSS;
    "SU ss out u"
	C = [SUsp]; C + [SUsi]; C - 360;
	=> SU dw at; E = D;
	C + 360; => SU dw at; E + D;
	C + 360; => SU dw at; E + D;
	C + 360; => SU dw at; E + D;
	E & 0FCFCFCFCh; E > 2;
	A = E; A & 0FFh;
	D = E; D > 8; D & 0FFh; A + D; A & 0FFh;
	E > 16; D = E; D & 0FFh; A + D; A & 0FFh;
	D = E; D > 8; D & 0FFh; A + D; A & 0FFh; A > 2;
	C=grskhdump; C+2300000; C+[SUsi]; [C]=A;
	[SUsi]+; B ^ SU ss out u;
	[SUsi]=SSFROM; B=NSS;
    "SU ss out copy"
	C=grskhdump; C+2300000; C+[SUsi]; A=[C];
	C=[SUsp]; C+[SUsi]; [C]=A;
	[SUsi]+; B ^ SU ss out copy;
	end;'''

_W_AT = '''"SU w at"
	D = [C plus 1]; D & 0FFh; D < 8;
	A = [C plus 0]; A & 0FFh; D + A;
	end;'''

_W_AT_DROP_RIGHT = '''"SU w at"
	D = [C plus 0]; D & 0FFh;
	A = D; A < 8; D + A;
	end;'''


def _lm(witness, kind, phase, field, source, old, new, why):
    edits = old if isinstance(old, tuple) else ((old, new),)
    return (witness, kind, phase, field, source, edits, why)


LINO_MUTANTS = {
    "OCEAN_12_DRAWS": _lm(
        "ocean_11draw_a", S.LEDGER, 3, 1, "sky.txt",
        "[GRSKdensity]=50; [GRSKsmoothing]=1; -> GR sky t3 pressure;",
        "=> GRSK flandom; [GRSKdensity]=50; [GRSKsmoothing]=1; -> GR sky t3 pressure;",
        "one extra OCEAN draw immediately before cloudy_sky"),
    "TYPE5_9_DRAWS": _lm(
        "thin_type5_sixdraw", S.LEDGER, 3, 1, "sky.txt",
        "[GRSKdensity]=10; [GRSKsmoothing]=2; [GRSKtmp]=2;",
        "=> GRSK flandom; => GRSK flandom; => GRSK flandom; [GRSKdensity]=10; [GRSKsmoothing]=2; [GRSKtmp]=2;",
        "three extra type-5 pre-cloud draws"),
    "REMOVE_ALBEDO": _lm(
        "ocean_11draw_b_min_denominator", S.LEDGER, 3, None, "sky.txt",
        "C = [GRSKdensity]; C + [GRSKalbedo]; => SU rnd; [GRSKn] = C;",
        "C = [GRSKdensity]; => SU rnd; [GRSKn] = C;",
        "cloud count omits +albedo"),
    "CLOUD_NO_SCALE64": _lm(
        "ocean_11draw_b_min_denominator", S.PRE_HORIZON, 0, None, "sky.txt",
        "=> GRSK k64; => GRSK x mul k; => GRSK store o; [GRSKx]=[GRSKo];\n\tA = nw; A + RSBG; A + [GRSKp]; C = [A]; C & 255;",
        "( BREAK reachable den2=1: omit source multiply by 64 ) => GRSK fa x; => GRSK store o; [GRSKx]=[GRSKo];\n\tA = nw; A + RSBG; A + [GRSKp]; C = [A]; C & 255;",
        "reachable minimum-denominator cloud pixel omits *64"),
    "BYTE_SMOOTH": _lm(
        "ocean_11draw_a", S.PRE_HORIZON, 0, None, "susm.txt",
        _SSMOOTH, _SSMOOTH_BYTE,
        "byte-wise average replaces dword-carry ssmooth"),
    "OUT_OF_PLACE": _lm(
        "ocean_11draw_a", S.PRE_HORIZON, 0, None, "susm.txt",
        _SSMOOTH, _SSMOOTH_OUT,
        "ssmooth writes a distant test-only scratch then copies back"),
    "SS_STRIDE_320": _lm(
        "ocean_11draw_a", S.PRE_HORIZON, 0, None, "sky.txt",
        '"GR sky cloud smooth one"\n\t[SUpbase]=RSBG; => SU ssmooth;',
        '"GR sky cloud smooth one"\n\t[SUpbase]=RSBG; => SU psmooth grays;',
        "cloud ssmooth dispatches to the 320-stride smoother"),
    "PS_STRIDE_360": _lm(
        "venus_psmooth_only", S.PRE_HORIZON, 0, None, "sky.txt",
        "[SUpbase] = RSBG; => SU psmooth grays;",
        "[SUpbase] = RSBG; => SU ssmooth;",
        "nebular psmooth dispatches to the 360-stride smoother"),
    "LS_DROP_RIGHT": _lm(
        "venus_tail_hostile", S.PRE_HORIZON, 0, None, "susm.txt",
        _W_AT, _W_AT_DROP_RIGHT,
        "lssmooth duplicates left pixels and drops i+1/i+361"),
    "LS_CLAMP_TAIL": _lm(
        "venus_tail_hostile", S.PRE_HORIZON, 0, None, "susm.txt",
        "C = [SUsp]; C + [SUsi]; C + 360;\n\t=> SU w at;\n\tD & 3F3Fh;",
        "C = [SUsp]; C + [SUsi]; C + 360;\n\tD=[SUsi]; D+360; ? D '< 64800 -> SU ls unclamped;\n\tC=[SUsp]; C+64799; D=[C]; D&0FFh; A=D; A<8; D+A; -> SU ls clamp done;\n    \"SU ls unclamped\" => SU w at;\n    \"SU ls clamp done\"\n\tD & 3F3Fh;",
        "lssmooth clamps both tail pixels to logical byte 64799"),
    "HORIZON_119": _lm(
        "ocean_night", S.FINAL_SBG, 0, None, "sky.txt",
        "GRSKHOR = 120;", "GRSKHOR = 119;", "horizon constant 120 -> 119"),
    "HORIZON_121": _lm(
        "ocean_night", S.FINAL_SBG, 0, None, "sky.txt",
        "GRSKHOR = 120;", "GRSKHOR = 121;", "horizon constant 120 -> 121"),
    "HORIZON_WIDTH_359": _lm(
        "ocean_night", S.FINAL_SBG, 0, None, "sky.txt",
        "? A '< 360 -> GR sky horizon col;", "? A '< 359 -> GR sky horizon col;",
        "horizon width 360 -> 359"),
    "HORIZON_WIDTH_361": _lm(
        "ocean_night", S.FINAL_SBG, 0, None, "sky.txt",
        "? A '< 360 -> GR sky horizon col;", "? A '< 361 -> GR sky horizon col;",
        "horizon width 360 -> 361"),
    "HORIZON_INT_DIV_FIRST": _lm(
        "ocean_night", S.FINAL_SBG, 0, None, "sky.txt",
        "C '* [GRSKshade]; C '/ GRSKHOR;",
        "C '/ GRSKHOR; C '* [GRSKshade];",
        "premature integer division performs (byte/120)*row"),
    "HORIZON_NO_NIGHT_HALF": _lm(
        "ocean_night", S.FINAL_SBG, 0, None, "sky.txt",
        "D=[GRSKnightzone]; ? D=0 -> GR sky horizon store; C '/ 2;",
        "D=[GRSKnightzone]; ? D=0 -> GR sky horizon store; ( BREAK omit /2 )",
        "night horizon omits divide by two"),
    "ATMOSPHERE_BUFFER": _lm(
        "ocean_airless_pair", S.PALETTE, 0, None, "sky.txt",
        "A=[GRSKatmosphere]; ? A != 0 -> GR sky sb air;",
        "A=[GRSKbrightness]; ? A != 0 -> GR sky sb air;",
        "fill/brightness byte is confused with atmosphere in sky scaling"),
    "PALETTE_TO_PAL6": _lm(
        "ocean_night", S.PALETTE, 0, None, "sky.txt",
        "[SHdstb]=srfpal6;", "[SHdstb]=pal6;",
        "palette shade destination redirects to pal6"),
    "ROUND_CHOP": _lm(
        "ocean_11draw_a", S.PRE_HORIZON, 0, None, "sky.txt",
        "[FS0]=[GRSKx]; => FLoadF32; => FToIntChop;",
        "[FS0]=[GRSKx]; => FLoadF32; => FToIntNear;",
        "cloud float-to-byte site rounds to nearest"),
    "REMOVE_T3_NIGHT_GOTO": _lm(
        "ocean_night", S.PALETTE, 0, None, "sky.txt",
        "A=[GRSKptype]; ? A != 3 -> GR sky pal nightdim;",
        "A=[GRSKptype]; -> GR sky pal nightdim;",
        "type-3 night special-palette control transfer is removed"),
    "WRONG_RNG_SEED": _lm(
        "ocean_11draw_a", S.LEDGER, 1, 5, "sky.txt",
        (("A=[GRSKseed]; => SU fast srand;", "A=[GRSKseed]; A+; => SU fast srand;"),
         ("A=[GRSKseed]; A & 0FFFFh; => SU srand;", "A=[GRSKseed]; A+; A & 0FFFFh; => SU srand;")),
        None, "both random streams receive seed+1"),
    "WRONG_RNG_STREAM": _lm(
        "thin_type5_sixdraw", S.LEDGER, 2, None, "sky.txt",
        '"GRSK random k mul al add y"\n\t=> GRSK flandom; [GRSKx]=[GRSKret]; => GRSK x mul k;',
        '"GRSK random k mul al add y"\n\t=> GRSK fast flandom; [GRSKx]=[GRSKret]; => GRSK x mul k;',
        "type-5 colour draws use the fast stream"),
    "STALE_TYPE5_BRIGHTNESS": _lm(
        "thin_type5_sixdraw", S.SCALARS, 0, 0, "sky.txt",
        "[GRSKbrightness]=[GRSKbrightness]; A=[GRSKbrightness]; A '* 65; A '/ 100; [GRSKbrightness]=A;",
        "[GRSKbrightness]=[GRSKbrightness]; ( BREAK stale type5 brightness )",
        "type-5 final brightness remains stale without changing frozen-sb palette"),
    "NO_QW_RESTORE_CLOUD": _lm(
        "ocean_11draw_a", S.GUARDS, 0, 9, "sky.txt",
        "[GRSKquadwords]=[GRSKqsave];", "( BREAK cloudy QUADWORDS restore removed )",
        "cloudy painter omits QUADWORDS restore"),
    "NO_QW_RESTORE_NEBULAR": _lm(
        "venus_tail_zero", S.GUARDS, 0, 9, "sky.txt",
        "[GRSKquadwords] = [GRSKqsave];", "( BREAK nebular QUADWORDS restore removed )",
        "nebular painter omits QUADWORDS restore"),
    "FLOAT_STORE_BOUNDARY": _lm(
        "double_expression_spill_witness", S.PALETTE, 0, 115, "sky.txt",
        "=> GRSK flandom; [GRSKx]=[GRSKret]; => GRSK x mul k;\n\t[FT0]=[FA0]; [FT1]=[FA1];",
        "=> GRSK flandom; [GRSKx]=[GRSKret]; => GRSK x mul k; => F32Narrow;\n\t[FT0]=[FA0]; [FT1]=[FA1];",
        "illicit helper-level binary32 spill changes PALETTE byte 462 53 -> 52"),
    "SBG_OOB_ADDR": _lm(
        "smoke_airless_type1", S.GUARDS, 0, 3, "sky.txt",
        "[GRSKwaddr]=[GRSKptr]; [GRSKwbyte]=C; => GRSK write sbg;",
        "[GRSKwaddr]=64800; [GRSKwbyte]=C; => GRSK write sbg;",
        "one requested SBG relative address targets offset 64800; checked writer remains authoritative"),
}

# Stable public roster used by the durable sky test.  Keep this explicit
# count as a review gate: adding a guarded substitution without adding its
# canonical name to this module must fail static qualification.
REQUIRED_LINO_MUTANT_COUNT = 27
LINO_MUTANT_NAMES = tuple(sorted(LINO_MUTANTS))


def named_cases():
    return dict(C.CASES)


def source_text():
    with open(os.path.join(HERE, "sky_ref.c"), encoding="utf-8") as fh:
        return fh.read()


def mutant_text(name):
    if name not in MUTANTS and name not in NOT_APPLICABLE:
        raise KeyError("unknown sky mutant %s" % name)
    old = "#define SKY_MUT_%s 0" % name
    new = "#define SKY_MUT_%s 1" % name
    text = source_text()
    if text.count(old) != 1:
        raise RuntimeError("mutation marker is not unique: %s" % old)
    return text.replace(old, new, 1)


def write_mutant(name, path):
    text = mutant_text(name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def record_for(blob, case_id, kind, phase):
    for rec in S.decode_stream(blob):
        if rec.case_id == case_id and rec.kind == kind and rec.phase == phase:
            return rec
    raise AssertionError("record absent: case=%d kind=%d phase=%d" %
                         (case_id, kind, phase))


def target_diff(expected, actual, case, kind, phase, body_index):
    e = record_for(expected, case["case_id"], kind, phase)
    a = record_for(actual, case["case_id"], kind, phase)
    if body_index is None:
        return e.body != a.body
    return e.body[body_index] != a.body[body_index]


def mutation_invariant_error(name, expected, actual, case):
    if name == "STALE_TYPE5_BRIGHTNESS":
        wanted = record_for(expected, case["case_id"], S.PALETTE, 0)
        got = record_for(actual, case["case_id"], S.PALETTE, 0)
        if wanted.body != got.body:
            return "stale-brightness edit leaked into frozen pre-switch sb palette"
    return None


def qualify(name, keep=None):
    row_name, kind, phase, field, why = MUTANTS[name]
    rows = named_cases()
    if row_name not in rows:
        return False, "MISSING CORPUS WITNESS %s" % row_name
    case = rows[row_name]
    expected = S.encode_stream([S.SkyModel().run(case)])
    tmp = keep or tempfile.mkdtemp(prefix="sky_break_")
    made_tmp = keep is None
    try:
        os.makedirs(tmp, exist_ok=True)
        cpath = os.path.join(tmp, "sky_ref_%s.c" % name.lower())
        pristine_exe = os.path.join(tmp, "sky_ref_pristine.exe")
        pristine_output = os.path.join(tmp, "sky-pristine.bin")
        exe = os.path.join(tmp, "sky_ref_%s.exe" % name.lower())
        corpus = os.path.join(tmp, "sky-corpus.txt")
        output = os.path.join(tmp, "sky-output.bin")
        write_mutant(name, cpath)
        with open(corpus, "w", encoding="ascii", newline="\n") as fh:
            fh.write(C.encode_text([(row_name, case)]))
        cc = os.environ.get("CC", "gcc")
        subprocess.check_call([cc, "-std=c11", "-O2", "-Wall", "-Wextra",
                               "-Werror", "-o", pristine_exe,
                               os.path.join(HERE, "sky_ref.c"), "-lm"], cwd=ROOT)
        subprocess.check_call([pristine_exe, corpus, pristine_output, "--offsets",
                               os.path.join(ROOT, "work", "offsets.map")], cwd=ROOT)
        with open(pristine_output, "rb") as fh:
            pristine = fh.read()
        if pristine != expected:
            errors = G.compare_records(expected, pristine, "pristine/%s" % name)
            detail = errors[0] if errors else "raw framed bytes differ"
            return False, "PRISTINE WITNESS FAIL: %s" % detail
        subprocess.check_call([cc, "-std=c11", "-O2", "-Wall", "-Wextra",
                               "-Werror", "-o", exe, cpath, "-lm"], cwd=ROOT)
        subprocess.check_call([exe, corpus, output, "--offsets",
                               os.path.join(ROOT, "work", "offsets.map")], cwd=ROOT)
        with open(output, "rb") as fh:
            actual = fh.read()
        structural = G.compare_records(expected, actual, name)
        if not structural:
            return False, "NOT KILLED (entire framed stream agrees)"
        if not target_diff(expected, actual, case, kind, phase, field):
            return False, "stream differs, but not at declared record/field: %s" % structural[0]
        invariant = mutation_invariant_error(name, expected, actual, case)
        if invariant:
            return False, invariant
        field_text = "body" if field is None else "body[%d]" % field
        return True, "%s -> kind=%d phase=%d %s (%s)" % (
            row_name, kind, phase, field_text, why)
    finally:
        if made_tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def check_c_malformed(keep=None):
    """Require fail-closed corpus/replay rejection from the pristine C CLI."""
    tmp = keep or tempfile.mkdtemp(prefix="sky_bad_corpus_")
    made_tmp = keep is None
    failures = []
    try:
        os.makedirs(tmp, exist_ok=True)
        exe = os.path.join(tmp, "sky_ref_pristine.exe")
        cc = os.environ.get("CC", "gcc")
        subprocess.check_call([cc, "-std=c11", "-O2", "-Wall", "-Wextra",
                               "-Werror", "-o", exe,
                               os.path.join(HERE, "sky_ref.c"), "-lm"], cwd=ROOT)
        row_name, case = C.CASES[1]
        good = C.encode_text([(row_name, case)])
        units = C.case_units(case)
        valid_row = " ".join(C.signed_token(v) for v in units) + "\n"
        second = dict(case, case_id=case["case_id"] + 10000)

        malformed = {}
        malformed["truncated_row"] = (valid_row + " ".join(
            C.signed_token(v) for v in C.case_units(second)[:-1]) + "\n", None)
        overflow = list(C.case_units(second))
        overflow[1] = "2147483648"
        malformed["signed_i32_overflow"] = (valid_row + " ".join(
            str(v) if isinstance(v, str) else C.signed_token(v)
            for v in overflow) + "\n0\n", None)
        malformed["duplicate_id"] = (valid_row + valid_row + "0\n", None)
        bad_bg = list(C.case_units(second))
        bad_bg[28] = 7341
        malformed["bg_bytes_7341"] = (valid_row + " ".join(
            C.signed_token(v) for v in bad_bg) + "\n0\n", None)
        bad_flags = second["flags"] | S.GRADE_PALETTE | S.PALETTE_UNDEFINED
        bad_flag_units = list(C.case_units(second))
        bad_flag_units[2] = bad_flags
        malformed["contradictory_palette_flags"] = (valid_row + " ".join(
            C.signed_token(v) for v in bad_flag_units) + "\n0\n", None)
        malformed["trailing_tokens"] = (good + "1\n", None)

        replay = os.path.join(tmp, "oversized-replay.bin")
        with open(replay, "wb") as fh:
            fh.write(bytes(S.ST_BYTES + 1))
        page_name, page_case = next(
            (name, row) for name, row in C.CASES
            if row["flags"] & S.GRADE_PAGE)
        malformed["oversized_replay"] = (
            C.encode_text([(page_name, page_case)]), replay)

        for label, (text, replay_path) in sorted(malformed.items()):
            corpus = os.path.join(tmp, "%s.txt" % label)
            output = os.path.join(tmp, "%s.bin" % label)
            with open(corpus, "w", encoding="ascii", newline="\n") as fh:
                fh.write(text)
            cmd = [exe, corpus, output, "--offsets",
                   os.path.join(ROOT, "work", "offsets.map")]
            if replay_path:
                cmd.extend(["--replay", replay_path])
            ran = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
            if ran.returncode == 0:
                failures.append("%s accepted" % label)
            if os.path.exists(output):
                failures.append("%s left partial output" % label)
        return failures
    finally:
        if made_tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def lino_mutant_text(name):
    """Return (source filename, mutated text), rejecting any token drift."""
    if name not in LINO_MUTANTS:
        raise KeyError("unknown Lino sky mutant %s" % name)
    source = LINO_MUTANTS[name][4]
    path = os.path.join(WORK, source)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for old, new in LINO_MUTANTS[name][5]:
        count = text.count(old)
        if count != 1:
            raise RuntimeError("%s/%s edit token count %d, expected 1" %
                               (name, source, count))
        text = text.replace(old, new, 1)
    return source, text


def static_check_lino_mutants():
    failures = []
    if len(LINO_MUTANTS) != REQUIRED_LINO_MUTANT_COUNT:
        failures.append(("<roster>", "Lino mutant count %d, expected %d" %
                         (len(LINO_MUTANTS), REQUIRED_LINO_MUTANT_COUNT)))
    if len(LINO_MUTANT_NAMES) != len(set(LINO_MUTANT_NAMES)):
        failures.append(("<roster>", "Lino mutant names are not unique"))
    for name in LINO_MUTANT_NAMES:
        try:
            source, text = lino_mutant_text(name)
            if text == source_text():  # cheap impossible-change guard for sky.c mixups
                raise RuntimeError("mutated Lino text unexpectedly equals sky_ref.c")
            if not text.strip():
                raise RuntimeError("empty mutated source")
        except Exception as exc:
            failures.append((name, str(exc)))
    return failures


def _lino_run_dir(root, name, prefix="lm"):
    names = sorted(LINO_MUTANTS)
    if prefix not in ("lm", "lp"):
        raise RuntimeError("bad Lino sandbox prefix %s" % prefix)
    leaf = "%s%02d" % (prefix, names.index(name) + 1)
    path = os.path.abspath(os.path.join(root, leaf))
    root_abs = os.path.abspath(root)
    if os.path.commonpath([root_abs, path]) != root_abs:
        raise RuntimeError("mutant sandbox escaped requested root")
    if "--" in path or "_" in path:
        raise RuntimeError("Lino mutant path contains forbidden '--' or '_': %s" % path)
    return path


def _prepare_lino_mutant(name, case, root):
    run_dir = _lino_run_dir(root, name)
    if os.path.isdir(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(os.path.join(run_dir, "fp"))
    for lib in LINO_LIBS:
        shutil.copy2(os.path.join(WORK, lib), os.path.join(run_dir, lib))
    for lib in FP_LIBS:
        shutil.copy2(os.path.join(WORK, "fp", lib),
                     os.path.join(run_dir, "fp", lib))
    for asset in ASSETS:
        shutil.copy2(os.path.join(WORK, asset), os.path.join(run_dir, asset))

    source_name, mutated = lino_mutant_text(name)
    if source_name == "sky.txt":
        mutant_leaf = "skymut.txt"
        library_old, library_new = "\tsky;", "\tskymut;"
    elif source_name == "susm.txt":
        mutant_leaf = "susmut.txt"
        library_old, library_new = "\tsusm;", "\tsusmut;"
    else:
        raise RuntimeError("unsupported Lino mutation owner %s" % source_name)
    with open(os.path.join(run_dir, mutant_leaf), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(mutated)

    corpus = os.path.join(run_dir, "sky-corpus.txt")
    replay = os.path.join(run_dir, "sky-replay.bin")
    with open(corpus, "w", encoding="ascii", newline="\n") as fh:
        fh.write(C.encode_text([(name.lower(), case)]))
    with open(replay, "wb") as fh:
        fh.write(bytes(S.ST_BYTES))

    main_source = os.path.join(WORK, "skymain.txt")
    with open(main_source, encoding="utf-8") as fh:
        main = fh.read()
    if main.count(library_old) != 1:
        raise RuntimeError("skymain library token drift: %s" % library_old)
    main = main.replace(library_old, library_new, 1)
    relative = "GRSKHcorpname = { sky-corpus.txt };"
    if main.count(relative) != 1:
        raise RuntimeError(
            "skymain must use exactly one relative sky-corpus.txt literal")
    main_path = os.path.join(run_dir, "skymain.txt")
    with open(main_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(main)
    return run_dir, main_path, corpus, replay


def _prepare_lino_pristine(name, case, root):
    run_dir = _lino_run_dir(root, name, "lp")
    if os.path.isdir(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(os.path.join(run_dir, "fp"))
    for lib in LINO_LIBS:
        shutil.copy2(os.path.join(WORK, lib), os.path.join(run_dir, lib))
    for lib in FP_LIBS:
        shutil.copy2(os.path.join(WORK, "fp", lib),
                     os.path.join(run_dir, "fp", lib))
    for asset in ASSETS:
        shutil.copy2(os.path.join(WORK, asset), os.path.join(run_dir, asset))
    corpus = os.path.join(run_dir, "sky-corpus.txt")
    replay = os.path.join(run_dir, "sky-replay.bin")
    with open(corpus, "w", encoding="ascii", newline="\n") as fh:
        fh.write(C.encode_text([("pristine_" + name.lower(), case)]))
    with open(replay, "wb") as fh:
        fh.write(bytes(S.ST_BYTES))
    main_path = os.path.join(run_dir, "skymain.txt")
    shutil.copy2(os.path.join(WORK, "skymain.txt"), main_path)
    return run_dir, main_path, corpus, replay


def _run_powershell(script, args, cwd, timeout):
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", script] + list(args)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def qualify_lino(name, sandbox_root=None, timeout=900, keep=False):
    """Build/run one copied Lino mutant and verify its declared witness.

    The caller must serialize this with other Lino compiler users.  This
    function never invokes compiler.exe directly: lino_build.ps1 is the only
    build entry point and w7arun.ps1 is the only executable entry point.
    """
    if name in NOT_APPLICABLE:
        return True, "NOT-APPLICABLE: " + NOT_APPLICABLE[name]
    if name not in LINO_MUTANTS:
        return False, "unknown Lino mutant"
    row_name, kind, phase, field, _source, _edits, why = LINO_MUTANTS[name]
    rows = named_cases()
    if row_name not in rows:
        return False, "MISSING CORPUS WITNESS %s" % row_name
    case = rows[row_name]
    expected = S.encode_stream([S.SkyModel().run(case)])
    root = sandbox_root or os.path.join(TESTS, "gen", "w7bsky")
    os.makedirs(root, exist_ok=True)
    pristine_dir = None
    run_dir = None
    try:
        pristine_dir, pristine_main, _corpus, _replay = _prepare_lino_pristine(
            name, case, root)
        pristine_build = _run_powershell(
            LINO_BUILD,
            ["-Src", pristine_main, "-Compiler", LINO_COMPILER, "-Cpu", LINO_CPU,
             "-TimeoutSec", "300"], pristine_dir, 360)
        pristine_build_note = (((pristine_build.stdout or "") +
                                (pristine_build.stderr or "")).strip())
        if pristine_build.returncode:
            return False, "pristine Lino build failed: " + pristine_build_note[:500]
        pristine_exe = os.path.splitext(pristine_main)[0] + ".exe"
        pristine_out = os.path.join(pristine_dir, "sky-out.bin")
        pristine_run = _run_powershell(
            LINO_RUN,
            ["-Exe", pristine_exe, "-Out", pristine_out,
             "-TimeoutSec", str(timeout)], pristine_dir, timeout + 60)
        pristine_run_note = (((pristine_run.stdout or "") +
                              (pristine_run.stderr or "")).strip())
        if pristine_run.returncode or not os.path.isfile(pristine_out):
            return False, "pristine Lino first launch failed: " + pristine_run_note[:500]
        with open(pristine_out, "rb") as fh:
            pristine = fh.read()
        if pristine != expected:
            errors = G.compare_records(expected, pristine, "Lino/pristine/%s" % name)
            detail = errors[0] if errors else "raw framed bytes differ"
            return False, "PRISTINE WITNESS FAIL: %s" % detail

        run_dir, main, _corpus, _replay = _prepare_lino_mutant(
            name, case, root)
        build = _run_powershell(
            LINO_BUILD,
            ["-Src", main, "-Compiler", LINO_COMPILER, "-Cpu", LINO_CPU,
             "-TimeoutSec", "300"], run_dir, 360)
        build_note = ((build.stdout or "") + (build.stderr or "")).strip()
        if build.returncode:
            return False, "Lino build failed: " + build_note[:500]
        exe = os.path.splitext(main)[0] + ".exe"
        out = os.path.join(run_dir, "sky-out.bin")
        ran = _run_powershell(
            LINO_RUN,
            ["-Exe", exe, "-Out", out, "-TimeoutSec", str(timeout)],
            run_dir, timeout + 60)
        run_note = ((ran.stdout or "") + (ran.stderr or "")).strip()
        if ran.returncode or not os.path.isfile(out):
            return False, "Lino mutant first launch failed: " + run_note[:500]
        with open(out, "rb") as fh:
            actual = fh.read()
        errors = G.compare_records(expected, actual, "Lino/%s" % name)
        if not errors:
            return False, "NOT KILLED (entire framed stream agrees)"
        if not target_diff(expected, actual, case, kind, phase, field):
            return False, ("stream differs, but not at declared record/field: " +
                           errors[0])
        invariant = mutation_invariant_error(name, expected, actual, case)
        if invariant:
            return False, invariant
        field_text = "body" if field is None else "body[%d]" % field
        return True, "%s -> kind=%d phase=%d %s (%s)" % (
            row_name, kind, phase, field_text, why)
    except subprocess.TimeoutExpired:
        return False, "wrapper timeout"
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)
    finally:
        if pristine_dir and not keep:
            shutil.rmtree(pristine_dir, ignore_errors=True)
        if run_dir and not keep:
            shutil.rmtree(run_dir, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--emit", nargs=2, metavar=("NAME", "PATH"))
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--keep", help="keep generated source/exe/output in this directory")
    ap.add_argument("--lino", action="store_true",
                    help="also run the copied Lino one-edit mutation matrix")
    ap.add_argument("--lino-only", action="store_true",
                    help="run only the copied Lino matrix")
    ap.add_argument("--static-lino", action="store_true",
                    help="validate every guarded Lino substitution without building")
    ap.add_argument("--malformed", action="store_true",
                    help="run the pristine C fail-closed corpus/replay matrix")
    ap.add_argument("--lino-root", default=os.path.join(TESTS, "gen", "w7bsky"))
    ap.add_argument("--lino-timeout", type=int, default=900)
    ap.add_argument("--keep-lino", action="store_true")
    args = ap.parse_args()
    if args.list:
        print("C mutants:")
        for name in sorted(MUTANTS):
            print("%-28s %s" % (name, MUTANTS[name][0]))
        print("Lino mutants:")
        for name in sorted(LINO_MUTANTS):
            print("%-28s %s [%s]" %
                  (name, LINO_MUTANTS[name][0], LINO_MUTANTS[name][4]))
        for name, proof in sorted(NOT_APPLICABLE.items()):
            print("%-28s NOT-APPLICABLE: %s" % (name, proof))
        return 0
    if args.emit:
        write_mutant(args.emit[0], args.emit[1])
        print("emitted %s -> %s" % tuple(args.emit))
        return 0
    failures = []
    if args.malformed:
        malformed_fail = check_c_malformed(args.keep)
        for detail in malformed_fail:
            print("C MALFORMED FAIL  %s" % detail)
        if not malformed_fail:
            print("C malformed corpus/replay matrix: 7/7 PASS")
        failures.extend("C malformed: " + detail for detail in malformed_fail)
        if (not args.only and not args.lino and not args.lino_only and
                not args.static_lino):
            return 1 if failures else 0
    if args.static_lino:
        static_fail = static_check_lino_mutants()
        for name, detail in static_fail:
            print("LINO %-23s FAIL  %s" % (name, detail))
        if not static_fail:
            print("Lino guarded substitutions: %d/%d static PASS" %
                  (len(LINO_MUTANTS), len(LINO_MUTANTS)))
        failures.extend(name for name, _ in static_fail)
        if not args.lino and not args.lino_only:
            return 1 if failures else 0
    if not args.lino_only:
        selected = args.only or sorted(MUTANTS)
        for name in selected:
            if name in NOT_APPLICABLE:
                print("%-28s NOT-APPLICABLE  %s" % (name, NOT_APPLICABLE[name]))
                continue
            if name not in MUTANTS:
                print("%-28s UNKNOWN" % name)
                failures.append(name)
                continue
            ok, detail = qualify(name, args.keep)
            print("%-28s %-5s %s" % (name, "KILL" if ok else "FAIL", detail))
            if not ok:
                failures.append(name)
    if args.lino or args.lino_only:
        lino_selected = args.only or sorted(LINO_MUTANTS)
        for name in lino_selected:
            if name in NOT_APPLICABLE:
                print("LINO %-23s NOT-APPLICABLE  %s" %
                      (name, NOT_APPLICABLE[name]))
                continue
            ok, detail = qualify_lino(
                name, sandbox_root=args.lino_root,
                timeout=args.lino_timeout, keep=args.keep_lino)
            print("LINO %-23s %-5s %s" %
                  (name, "KILL" if ok else "FAIL", detail), flush=True)
            if not ok:
                failures.append("LINO/" + name)
    if failures:
        print("uncaught/blocked:", ", ".join(failures))
        return 1
    print("sky mutants: all selected applicable mutants killed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
