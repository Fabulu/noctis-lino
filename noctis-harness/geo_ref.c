/* geo_ref.c -- Wave 6 geometry reference side A (C, real x87).
 *
 * Wave 4 ported the TOPOLOGY of prepare_nearstar and deliberately discarded
 * the values of the eleven float-argument draw sites.  This file computes
 * them.  It is a literal transcription of the geometry statements of
 * NOCTIS-0.CPP:4059-4376 (checked line for line against DL.CPP:545-750,
 * which is the copy the 1996 DL.EXE was built from and which differs only in
 * ways that draw nothing), with three things spelled out that C would
 * otherwise leave to the host toolchain:
 *
 * 1. THE ARITHMETIC IS AN INSTRUCTION SCHEDULE, NOT AN EXPRESSION.
 *    Borland C++ 3.1 with the 8087 at control word 133Fh keeps every
 *    intermediate of an expression in st(0) at 64-bit precision and stores
 *    exactly once, at the assignment.  Every geometry statement below is
 *    therefore written as an `ext` (long double, = the 80-bit type on this
 *    toolchain) chain with ONE cast to double at the end.  A gcc `double`
 *    transcription would silently narrow after every operation, which is the
 *    53-bit row of FLOATPOLICY.md's ladder.  --prec f64 selects that
 *    deliberately, as a control.
 *
 *    Where the 1996 source has two statements, this file has two stores.
 *    :4306/:4307 (`p_ray[n] = ...;` then `p_ray[n] *= avg_planet_sizing;`)
 *    is a real two-store sequence and is not fused.
 *
 * 2. nearstar_ray IS A `float`.  NOCTIS-0.H declares it binary32 and the
 *    quantisation is observable: it is the multiplicand of :4089's orb_seed
 *    for every planet of every star.
 *
 * 3. THE FLOAT-TO-INT CAST BOUNDARY IS THE OPEN QUESTION, SO IT IS A SWITCH.
 *    docs-notes/FLOATPOLICY.md 3.3 records it UNSETTLED: a C cast goes
 *    through Borland's __ftol (rounding control flipped to chop), while the
 *    37 hand-written fistp sites inherit 133Fh and round to nearest even.
 *    The eleven sites below are C-level implicit double->int conversions at
 *    a call boundary, so the documentary answer is chop -- but this file
 *    refuses to bake that in.  Two axes, four combinations:
 *
 *       --cast chop|near     rounding applied at the conversion
 *       --castsrc ext|f64    conversion applied to the live 80-bit value,
 *                            or to its binary64 rounding first
 *
 *    geo_grade.py measures all four and reports how far apart they are,
 *    instead of any of them being asserted.
 *
 * ---------------------------------------------------------------------------
 * THE ELEVEN FLOAT-ARGUMENT SITES, 17 DRAWS.  Registry pinned by Wave 4;
 * geo_grade.py greps this file and requires the count to still be eleven.
 * ---------------------------------------------------------------------------
 *   FSITE 4089   random  (300 * nearstar_ray)                        1 draw
 *   FSITE 4090   zrandom (10 * p_orb_seed[n])                        2
 *   FSITE 4091   zrandom (10 * p_orb_seed[n])                        2
 *   FSITE 4092   random  (p_orb_seed[n] + 10*fabs(p_orb_tilt[n]))    1
 *   FSITE 4093   random  (p_orb_seed[n])                             1
 *   FSITE 4094   zrandom (p_ray[n])                                  2
 *   FSITE 4195   zrandom (300 * p_ray[n])                            2
 *   FSITE 4196   zrandom (10 * p_orb_seed[q])                        2
 *   FSITE 4197   zrandom (10 * p_orb_seed[q])                        2
 *   FSITE 4198   random  (p_orb_seed[q] + 10*fabs(p_orb_tilt[q]))    1
 *   FSITE 4199   random  (p_orb_seed[n])   <- the PARENT's seed      1
 *
 * ---------------------------------------------------------------------------
 * WHAT GRADES THIS FILE, AND WHAT DOES NOT
 * ---------------------------------------------------------------------------
 * Nothing the 1996 machine prints.  Recon for this wave established that NO
 * GOES module emits any planetary geometry: of the eighteen shipped modules
 * only NOCTIS.EXE contains a floating-point printf conversion at all, and
 * DL.EXE -- the Wave 4 oracle -- contains none (its whole format-string set
 * is %d %ld %02d %u %s).  See geo_grade.py's ORACLE leg, which re-derives
 * that from the shipped binaries on every run rather than citing it.
 *
 * So geometry is graded by: this file against geo_spec.py (an independent
 * Python written from the draw table with exact dyadic arithmetic and no
 * hardware float at all), by the invariants in geo_grade.py, and by the
 * requirement that it not perturb the topology Wave 4 DID grade externally.
 * That last one is not a formality -- it is the only external hold on this
 * file, and it is a real one, because it is inherited from 4365/4365 DL
 * constraints and 4113/4113 catalogue records.
 *
 * Build:  gcc -O2 -fwrapv -o geo_ref.exe geo_ref.c -lm
 * Usage:  geo_ref <in.nsin> <out.geob> [--cast chop|near]
 *                 [--castsrc ext|f64] [--prec ext|f64] [--text]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifdef _MSC_VER
typedef __int32 i32;
typedef unsigned __int32 u32;
typedef __int16 i16t;
typedef unsigned __int64 u64;
#else
#include <stdint.h>
typedef int32_t  i32;
typedef uint32_t u32;
typedef int16_t  i16t;
typedef uint64_t u64;
#endif

/* ---------------------------------------------------------------------------
 * THE DELIBERATE BREAKS.  geo_grade.py compiles a second copy of this file
 * with each -D below and REQUIRES it to fail the reference comparison.  They
 * are compile-time so the graded binary contains none of them.  Each is a
 * single-edit mistake a careful port would plausibly make:
 *
 * LIVE breaks -- geo_grade.py leg 7a requires each to be CAUGHT:
 *
 *   BREAK_F32RAY      nearstar_ray carried as a double, dropping the
 *                     binary32 quantisation NOCTIS-0.H declares.
 *   BREAK_FUSESIZING  :4306/:4307 fused into one expression, i.e. one store
 *                     where the original has two.
 *   BREAK_SPILL2      one intermediate of :4309's orb_ray chain stored to a
 *                     double mid-expression.  FLOATPOLICY.md's spill hazard,
 *                     at a site where both operands really are full-width.
 *   BREAK_ECCMUL      :4092's `/ 2000` turned into `* 0.0005`, the classic
 *                     strength reduction.  1/2000 is not a binary fraction,
 *                     so this is a different number.
 *
 * (A sixth candidate, rearranging :4092 to (2000-r)/2000, was built and
 *  measured and is NOT in the set: it produced zero differences over 14,112
 *  values.  That is an observation on one corpus, not a proof of inertness
 *  like the three below, so it is reported and not asserted.)
 *   BREAK_KEY8        :4310's n<8 boundary flipped to n<=8.
 *
 * INERT breaks -- geo_grade.py leg 7b requires each to change NOTHING, which
 * is a positive claim about the routine and not an absence of evidence.  If
 * a later wave makes one of these values live, the claim fails loudly:
 *
 *   BREAK_SPILL       one intermediate of :4089 stored to a double.  Inert
 *                     because 3*(n*n+1) is at most 1203 (11 bits) and
 *                     nearstar_ray is a binary32 (24 bits), so the product
 *                     needs 35 bits and a binary64 holds it exactly.
 *   BREAK_PARENTSEED  :4199 reads p_orb_seed[q] instead of the parent's [n].
 *                     Inert because phase F overwrites p_ray[q] for every
 *                     moon before anything reads it: the DRAW is live, the
 *                     VALUE is dead.
 *   BREAK_ZORDER      :4094's two draw sites evaluated right to left.  Inert
 *                     because phase G overwrites p_ring[n] for every planet,
 *                     and n < nop at :4094, so that value is dead too.  The
 *                     stream position after the statement is unchanged, so
 *                     nothing downstream moves either.
 * ------------------------------------------------------------------------ */

/* ======================================================================= */
/* the 80-bit type and the control word                                    */
/* ======================================================================= */

typedef long double ext;

#if defined(__GNUC__) && (defined(__i386__) || defined(__x86_64__))
static unsigned short cw_save;
static void x87_enter (void) {
    unsigned short cw = 0x133F;                 /* PC=64, RC=nearest, masked */
    __asm__ __volatile__ ("fnstcw %0" : "=m" (cw_save));
    __asm__ __volatile__ ("fldcw %0" : : "m" (cw));
}
static void x87_leave (void) {
    __asm__ __volatile__ ("fldcw %0" : : "m" (cw_save));
}
static unsigned short x87_cw (void) {
    unsigned short cw;
    __asm__ __volatile__ ("fnstcw %0" : "=m" (cw));
    return cw;
}
#else
#error "geo_ref.c needs a gcc-family x86 toolchain: long double must be the 80-bit type"
#endif

/* --prec f64 is the CONTROL, not a mode anyone should use: it narrows every
   intermediate to binary64, i.e. it is what a plain double transcription
   does.  geo_grade.py requires it to DIFFER from the real schedule. */
static int prec_f64 = 0;
#define STEP(v)   (prec_f64 ? (ext)(double)(v) : (ext)(v))

/* ======================================================================= */
/* Wave 1: Borland's LCG, byte-pinned from NOCTIS.EXE                      */
/* ======================================================================= */

#define MULT    0x015A4E35u
#define DIVISOR 0x8000

static u32  rnd_state = 1;
static long ns_draws;
static long ns_float_draws;         /* draws taken at the eleven sites */
static int  ns_in_fsite;

static void brtl_srand (unsigned seed) { rnd_state = (u32)(seed & 0xFFFFu); }

static long brtl_rand (void)
{
    ns_draws++;
    if (ns_in_fsite) ns_float_draws++;
    rnd_state = rnd_state * MULT + 1u;
    return (long)((rnd_state >> 16) & 0x7FFFu);
}

static int brtl_random (i16t n)
{
    long r = brtl_rand();                       /* drawn even when n == 0 */
    i32  p = (i32)((u32)r * (u32)(i32)n);
    return (int)(i16t)(p / DIVISOR);
}

static i16t i16 (long v) { return (i16t)(u32)v; }

/* ---------------------------------------------------------------- casts -- */

static int cast_near   = 0;         /* 0 = chop (__ftol), 1 = round-nearest */
static int castsrc_f64 = 0;         /* 1 = narrow to binary64 before cast   */

/* Out of range yields the x87 integer indefinite 0x80000000, whose low 16
   bits are 0.  That is real behaviour on this boundary, not an error. */
static i16t ftoi16 (ext v)
{
    i32 l;
    if (castsrc_f64) v = (ext)(double)v;
    if (!(v > (ext)-2147483649.0L && v < (ext)2147483648.0L) || v != v)
        l = (i32)0x80000000;
    else if (cast_near) {
        /* fistp dword with the rounding control left at 00: nearest, ties
           to even.  Written arithmetically so it does not depend on the
           host's rint() honouring the x87 word. */
        ext f = v < 0 ? -v : v;
        ext fl = (ext)(long long)f;             /* f < 2^31, exact */
        ext fr = f - fl;
        long long m = (long long)fl;
        if (fr > 0.5L) m += 1;
        else if (fr == 0.5L) { if (m & 1) m += 1; }
        l = (i32)(v < 0 ? -m : m);
    } else
        l = (i32)(long long)v;                  /* C truncates toward zero */
    return (i16t)(u32)l;
}

#define RANDI(n)    brtl_random (i16 ((long)(n)))
#define RANDF(e)    (ns_in_fsite = 1, r_tmp = brtl_random (ftoi16 (e)), ns_in_fsite = 0, r_tmp)

static int r_tmp;

/* NOCTIS-0.CPP:3987  float zrandom (int range) { return random - random; }
   Wave 2: LEFT TO RIGHT, first draw minus second, subtracted as 16-bit int
   and only then widened.  The float return type is lossless here -- the
   difference is always an int16. */
static ext zrand_n (i16t range)
{
    int a = brtl_random (range);
    int b = brtl_random (range);
    return (ext)(float)(i16t)(u32)(long)(a - b);
}
#define ZRANDI(n)   zrand_n (i16 ((long)(n)))
#define ZRANDF(e)   (ns_in_fsite = 1, z_tmp = zrand_n (ftoi16 (e)), ns_in_fsite = 0, z_tmp)

static ext z_tmp;

/* ======================================================================= */
/* constant tables, NOCTIS-0.CPP 922-985 / NOCTIS-D.H 140-144              */
/* ======================================================================= */

#define star_classes  12
#define planet_types  10
#define maxbodies     80

static int  class_ray   [star_classes] = { 5000, 15000, 300, 20000, 15000,
                                           1000, 3000, 2000, 4000, 1500,
                                           30000, 250 };
static int  class_rayvar[star_classes] = { 2000, 10000, 200, 15000, 5000,
                                           1000, 3000, 500, 5000, 10000,
                                           1000, 10 };
static char class_planets[star_classes] = { 12, 18, 8, 15, 20, 3, 0, 1,
                                            7, 20, 2, 5 };
static int  planet_possiblemoons[] = { 1, 1, 2, 3, 2, 2, 18, 2, 3, 20, 20 };

static const double planet_orb_scaling = 5.0;
static const double avg_planet_sizing  = 2.4;
static const double moon_orb_scaling   = 12.8;
static const double avg_moon_sizing    = 1.8;

static double avg_planet_ray[] = { 0.007, 0.003, 0.010, 0.011, 0.010,
                                   0.008, 0.064, 0.009, 0.012, 0.125,
                                   5.000 };

/* PITAGORA.H:136.  A binary64 constant in the original; the decimal below
   is the shortest round-trip spelling of that same double. */
static const double deg = 3.14159265358979323846 / 180.0;

/* ======================================================================= */
/* the globals                                                             */
/* ======================================================================= */

static double ap_target_x, ap_target_y, ap_target_z;
static int    ap_target_class;
static float  ap_target_ray;
static int    ap_target_spin;
#ifdef BREAK_F32RAY
static double ap_target_ray_d, nearstar_ray_d;
#define RAY_EXT  ((ext)nearstar_ray_d)
#else
#define RAY_EXT  ((ext)nearstar_ray)
#endif

static double nearstar_x, nearstar_y, nearstar_z;
static int    nearstar_class;
static float  nearstar_ray;
static int    nearstar_nop, nearstar_nob;
static double nearstar_identity;

static char   p_type   [maxbodies];
static int    p_owner  [maxbodies];
static char   p_moonid [maxbodies];
static double p_ring   [maxbodies];
static double p_tilt   [maxbodies];
static double p_ray    [maxbodies];
static double p_orb_ray[maxbodies];
static double p_orb_seed[maxbodies];
static double p_orb_tilt[maxbodies];
static double p_orb_orient[maxbodies];
static double p_orb_ecc[maxbodies];

/* ======================================================================= */
/* the identity and the seed (Wave 3 / Wave 4, unchanged)                  */
/* ======================================================================= */

static ext ident_ext (double x, double y, double z)
{
    ext v = (ext)x;
    v = v / (ext)100000;
    v = v * (ext)y;
    v = v / (ext)100000;
    v = v * (ext)z;
    v = v / (ext)100000;
    return v;
}

static unsigned ident_chop16 (double x, double y, double z)
{
    ext v = ident_ext (x, y, z);
    i32 l;
    if (!(v > (ext)-2147483649.0L && v < (ext)2147483648.0L) || v != v)
        l = (i32)0x80000000;
    else
        l = (i32)(long long)v;
    return (unsigned)((u32)l & 0xFFFFu);
}

static i32 seed_from_xyz (i32 x, i32 y, i32 z)
{
    i32 t = x % 10000;
    t = (i32)((u32)t * (u32)y);
    t = t % 10000;
    t = (i32)((u32)t * (u32)z);
    t = t % 10000;
    return t;
}

/* ======================================================================= */
/* NOCTIS-0.CPP:3968-3983                                                  */
/* ======================================================================= */

static void extract_ap_target_infos (void)
{
    brtl_srand (ident_chop16 (ap_target_x, ap_target_y, ap_target_z));
    ap_target_class = RANDI (star_classes);
    /* :3973  ap_target_ray is a float, so this stores binary32. */
    {
        ext v = (ext)(float)class_ray[ap_target_class]
              + (ext)(float)RANDI (class_rayvar[ap_target_class]);
        v = STEP (v) * (ext)0.001;
#ifdef BREAK_F32RAY
        ap_target_ray_d = (double)v;            /* no binary32 quantisation */
#endif
        ap_target_ray = (float)v;
    }
    ap_target_spin = 0;
    if (ap_target_class == 11) ap_target_spin = RANDI (30) + 1;
    if (ap_target_class ==  7) ap_target_spin = RANDI (12) + 1;
    if (ap_target_class ==  2) ap_target_spin = RANDI ( 4) + 1;
}

static int starnop (double x, double y, double z)
{
    int r;
    brtl_srand ((unsigned) seed_from_xyz ((i32)x, (i32)y, (i32)z));
    r  = RANDI (class_planets[ap_target_class] + 1);
    r += RANDI (2);
    r -= RANDI (2);
    if (r < 0) r = 0;
    return r;
}

/* ======================================================================= */
/* prepare_nearstar, geometry included                                     */
/* ======================================================================= */

static int forced_class = -1;
static i32 forced_seed  = -1;

static void prepare_nearstar (void)
{
    int n, c, q, r, s, t;
    double key_radius;

    nearstar_class = ap_target_class;
    nearstar_x = ap_target_x;
    nearstar_y = ap_target_y;
    nearstar_z = ap_target_z;
    nearstar_ray = ap_target_ray;
#ifdef BREAK_F32RAY
    nearstar_ray_d = ap_target_ray_d;
#endif

    if (forced_class >= 0) nearstar_class = forced_class;

    nearstar_identity = (double) ident_ext (nearstar_x, nearstar_y, nearstar_z);
    {
        i32 sd = (forced_seed >= 0) ? forced_seed
               : seed_from_xyz ((i32)nearstar_x, (i32)nearstar_y, (i32)nearstar_z);
        brtl_srand ((unsigned) sd);
    }

    /* The counters are reset HERE, between starnop() and the prelude draw.
       starnop runs first and takes three draws of its own; folding them in
       would pollute the accounting (WAVE4_NEARSTAR.md section 1). */
    ns_draws = 0;
    ns_float_draws = 0;

    nearstar_nop = RANDI (class_planets[nearstar_class] + 1);

    /* --------- phase A : :4086-4107 ----------------------------------- */
    for (n = 0; n < nearstar_nop; n++) {
        p_owner[n] = -1;

        /* :4088  p_orb_orient[n] = (double)deg * (double)random(360) */
        {
            ext v = (ext)deg * (ext)RANDI (360);
            p_orb_orient[n] = (double)v;
        }

        /* :4089  3*(n*n+1)*nearstar_ray + (float)random(300*nearstar_ray)/100
           The int factor is computed in 16-bit int: 3*(20*20+1) = 1203, so
           it cannot overflow for any class_planets entry.  The ARGUMENT can
           overflow int16 and that wrap is Wave 1's finding, kept. */
        {
            ext a = (ext)(3 * (n*n + 1)) * RAY_EXT;
            ext arg = (ext)300 * RAY_EXT;
            ext b = (ext)(float)RANDF (STEP (arg));
            b = STEP (b) / (ext)100;
#ifdef BREAK_SPILL
            a = (ext)(double) a;                /* the spill */
#endif
            p_orb_seed[n] = (double)(STEP (a) + STEP (b));
        }

        /* :4090  zrandom (10*p_orb_seed[n]) / 500 */
        {
            ext arg = (ext)10 * (ext)p_orb_seed[n];
            ext v = ZRANDF (STEP (arg));
            p_tilt[n] = (double)(STEP (v) / (ext)500);
        }
        /* :4091  zrandom (10*p_orb_seed[n]) / 5000 */
        {
            ext arg = (ext)10 * (ext)p_orb_seed[n];
            ext v = ZRANDF (STEP (arg));
            p_orb_tilt[n] = (double)(STEP (v) / (ext)5000);
        }
        /* :4092  1 - random(p_orb_seed[n] + 10*fabs(p_orb_tilt[n])) / 2000 */
        {
            ext ab = (ext)10 * (ext)fabsl ((ext)p_orb_tilt[n]);
            ext arg = (ext)p_orb_seed[n] + STEP (ab);
            ext v = (ext)RANDF (STEP (arg));
#ifdef BREAK_ECCMUL
            p_orb_ecc[n] = (double)((ext)1 - STEP (v * (ext)0.0005));
#elif defined(BREAK_ECCORDER)
            p_orb_ecc[n] = (double)(STEP ((ext)2000 - v) / (ext)2000);
#else
            p_orb_ecc[n] = (double)((ext)1 - STEP (v / (ext)2000));
#endif
        }
        /* :4093  random(p_orb_seed[n]) * 0.001 + 0.01 */
        {
            ext v = (ext)RANDF ((ext)p_orb_seed[n]);
            v = STEP (v * (ext)0.001);
            p_ray[n] = (double)(v + (ext)0.01);
        }
        /* :4094  zrandom(p_ray[n]) * (1 + (double)random(1000)/100)
           The only statement in the routine with two draw sites in it; C
           leaves the order of * unspecified, so it is forced to source
           order with temporaries.  The VALUE is dead -- phase G overwrites
           p_ring for every planet -- but the four draws are live. */
        {
#ifdef BREAK_ZORDER
            ext rr = (ext)RANDI (1000);
            ext zr = ZRANDF ((ext)p_ray[n]);
#else
            ext zr = ZRANDF ((ext)p_ray[n]);
            ext rr = (ext)RANDI (1000);
#endif
            ext k  = (ext)1 + STEP (rr / (ext)100);
            p_ring[n] = (double)(STEP (zr) * STEP (k));
        }

        if (nearstar_class != 8)
            p_type[n] = (char) RANDI (planet_types);
        else {
            if (RANDI (2)) {
                p_type[n] = 10;
                p_orb_tilt[n] = (double)((ext)p_orb_tilt[n] * (ext)100);
            } else
                p_type[n] = (char) RANDI (planet_types);
        }
        if (nearstar_class == 2 || nearstar_class == 7 || nearstar_class == 15)
            p_orb_seed[n] = (double)((ext)p_orb_seed[n] * (ext)10);
    }

    /* --------- phase B : :4111-4115 ----------------------------------- */
    if (!nearstar_class) {
        if (RANDI (4) == 2) p_type[2] = 3;
        if (RANDI (4) == 2) p_type[3] = 3;
        if (RANDI (4) == 2) p_type[4] = 3;
    }

    /* --------- phase C : :4120-4140 ----------------------------------- */
    for (n = 0; n < nearstar_nop; n++) {
        switch (nearstar_class) {
            case 2:  while (p_type[n] == 3) p_type[n] = (char) RANDI (10); break;
            case 5:  while (p_type[n] == 6 || p_type[n] == 9)
                         p_type[n] = (char) RANDI (10);
                     break;
            case 7:  p_type[n] = 9; break;
            case 9:  while (p_type[n] != 0 && p_type[n] != 6 && p_type[n] != 9)
                         p_type[n] = (char) RANDI (10);
                     break;
            case 11: while (p_type[n] != 1 && p_type[n] != 7)
                         p_type[n] = (char) RANDI (10);
        }
    }

    /* --------- phase D : :4145-4168 ----------------------------------- */
    for (n = 0; n < nearstar_nop; n++) {
        switch (p_type[n]) {
            case 0: if (RANDI (8)) p_type[n]++; break;
            case 3: if ((n < 2) || (n > 6) || (nearstar_class && RANDI (4))) {
                        if (RANDI (2)) p_type[n]++; else p_type[n]--;
                    }
                    break;
            case 7: if (n < 7) { if (RANDI (2)) p_type[n]--; else p_type[n] -= 2; }
                    break;
        }
    }

    /* --------- phase E : :4172-4260 ----------------------------------- */
    nearstar_nob = nearstar_nop;
    if (nearstar_class == 2 || nearstar_class == 7 || nearstar_class == 15)
        goto no_moons;

    for (n = 0; n < nearstar_nop; n++) {
        s = p_type[n];
        if (n < 2) { t = 0; if (s == 10) t = RANDI (3); }
        else       t = RANDI (planet_possiblemoons[s] + 1);
        if (nearstar_nob + t > maxbodies) t = maxbodies - nearstar_nob;
        for (c = 0; c < t; c++) {
            q = nearstar_nob + c;
            p_owner[q]  = n;
            p_moonid[q] = (char) c;

            /* :4194 */
            p_orb_orient[q] = (double)((ext)deg * (ext)RANDI (360));

            /* :4195  (c*c+4)*p_ray[n] + (float)zrandom(300*p_ray[n])/100 */
            {
                ext a = (ext)(c*c + 4) * (ext)p_ray[n];
                ext arg = (ext)300 * (ext)p_ray[n];
                ext b = ZRANDF (STEP (arg));
                b = STEP (b) / (ext)100;
                p_orb_seed[q] = (double)(STEP (a) + STEP (b));
            }
            /* :4196 */
            {
                ext arg = (ext)10 * (ext)p_orb_seed[q];
                ext v = ZRANDF (STEP (arg));
                p_tilt[q] = (double)(STEP (v) / (ext)50);
            }
            /* :4197 */
            {
                ext arg = (ext)10 * (ext)p_orb_seed[q];
                ext v = ZRANDF (STEP (arg));
                p_orb_tilt[q] = (double)(STEP (v) / (ext)500);
            }
            /* :4198 */
            {
                ext ab = (ext)10 * (ext)fabsl ((ext)p_orb_tilt[q]);
                ext arg = (ext)p_orb_seed[q] + STEP (ab);
                ext v = (ext)RANDF (STEP (arg));
                p_orb_ecc[q] = (double)((ext)1 - STEP (v / (ext)2000));
            }
            /* :4199  reads the PARENT's seed, index n, not q. */
            {
#ifdef BREAK_PARENTSEED
                ext v = (ext)RANDF ((ext)p_orb_seed[q]);
#else
                ext v = (ext)RANDF ((ext)p_orb_seed[n]);
#endif
                v = STEP (v * (ext)0.05);
                p_ray[q] = (double)(v + (ext)0.1);
            }
            p_ring[q] = 0;

            p_type[q] = (char) RANDI (planet_types);
            r = p_type[q];
            if (r == 9 && s != 10) r = 2;
            if (r == 6 && s <  9)  r = 5;
            if (n > 7 && RANDI (c)) r = 7;          /* random(0) still draws */
            if (n > 9 && RANDI (c)) r = 7;
            if (r == 2 || r == 3 || r == 4 || r == 8) {
                if (s != 6 && s < 9) r = 1;
            }
            if (r == 3 && s < 9) {
                if (n > 7) r = 7;
                if (nearstar_class && RANDI (4)) r = 5;
                if (nearstar_class == 2 || nearstar_class == 7 ||
                    nearstar_class == 11) r = 8;
            }
            if (r == 7 && n <= 5) r = 1;
            if ((nearstar_class == 2 || nearstar_class == 5 ||
                 nearstar_class == 7 || nearstar_class == 11) && RANDI (n))
                r = 7;
            p_type[q] = (char) r;
        }
        nearstar_nob += t;
    }

    /* --------- phase F : :4300-4341, exactly 4 draws per body ---------- */
no_moons:
    {
        ext kr = RAY_EXT * (ext)planet_orb_scaling;
        key_radius = (double)kr;
    }
    if (nearstar_class ==  8) key_radius = (double)((ext)key_radius * (ext)2);
    if (nearstar_class ==  2) key_radius = (double)((ext)key_radius * (ext)16);
    if (nearstar_class ==  7) key_radius = (double)((ext)key_radius * (ext)18);
    if (nearstar_class == 11) key_radius = (double)((ext)key_radius * (ext)20);

    for (n = 0; n < nearstar_nop; n++) {
        ext avg = (ext)avg_planet_ray[(int)p_type[n]];
        /* :4306 */
        {
            ext v = STEP (avg * ZRANDI (100));
            v = STEP (v / (ext)200);
#ifdef BREAK_FUSESIZING
            /* one store where the original has two */
            p_ray[n] = (double)((avg + v) * (ext)avg_planet_sizing);
#else
            p_ray[n] = (double)(avg + v);
            /* :4307 -- a SEPARATE statement, therefore a second store */
            p_ray[n] = (double)((ext)p_ray[n] * (ext)avg_planet_sizing);
#endif
        }
        /* :4309 */
        {
            ext v = STEP ((ext)key_radius * ZRANDI (100));
#ifdef BREAK_SPILL2
            v = (ext)(double) v;                /* the spill */
#endif
            v = STEP (v / (ext)500);
            p_orb_ray[n] = (double)((ext)key_radius + v);
        }
        /* :4310 -- second store */
        p_orb_ray[n] = (double)((ext)p_orb_ray[n] + STEP ((ext)key_radius * avg));
#ifdef BREAK_KEY8
        if (n <= 8)
#else
        if (n < 8)
#endif
                   key_radius = (double)((ext)key_radius + (ext)p_orb_ray[n]);
        else       key_radius = (double)((ext)key_radius
                                         + STEP ((ext)0.22 * (ext)p_orb_ray[n]));
    }

    n = nearstar_nop;
    while (n < nearstar_nob) {
        q = 0;
        c = p_owner[n];
        key_radius = (double)((ext)p_ray[c] * (ext)moon_orb_scaling);
        while (n < nearstar_nob && p_owner[n] == c) {
            ext avg = (ext)avg_planet_ray[(int)p_type[n]];
            {
                ext v = STEP (avg * ZRANDI (100));
                v = STEP (v / (ext)200);
                p_ray[n] = (double)(avg + v);
            }
            p_ray[n] = (double)((ext)p_ray[n] * (ext)avg_moon_sizing);
            {
                ext v = STEP ((ext)key_radius * ZRANDI (100));
                v = STEP (v / (ext)250);
                p_orb_ray[n] = (double)((ext)key_radius + v);
            }
            p_orb_ray[n] = (double)((ext)p_orb_ray[n] + STEP ((ext)key_radius * avg));
            if (q < 2)
                key_radius = (double)((ext)key_radius + (ext)p_orb_ray[n]);
            if (q >= 2 && q < 8)
                key_radius = (double)((ext)key_radius
                                      + STEP ((ext)0.12 * (ext)p_orb_ray[n]));
            if (q >= 8)
                key_radius = (double)((ext)key_radius
                                      + STEP ((ext)0.025 * (ext)p_orb_ray[n]));
            q++;
            n++;
        }
    }

    /* --------- phase G : :4345-4361, exactly 2 draws per planet -------- */
    for (n = 0; n < nearstar_nop; n++) {
        {
            ext v = STEP ((ext)0.75 * (ext)p_ray[n]);
            v = v * (ext)(2 + RANDI (3));
            p_ring[n] = (double)v;
        }
        s = p_type[n];
        if (s != 6 && s != 9) { if (RANDI (5)) p_ring[n] = 0; }
        else                  { if (RANDI (2)) p_ring[n] = 0; }
    }
}

/* ======================================================================= */
/* NSIN in, GEOB out                                                       */
/*                                                                         */
/* GEOB header  (8 u32):  'GEOB' 1 nrec 8  cast castsrc prec 0             */
/* per record   (4 u32):  class nop nob draws                              */
/* then nob * 8 little-endian binary64, in the order                       */
/*   orb_orient orb_seed tilt orb_tilt orb_ecc ray orb_ray ring            */
/* ======================================================================= */

#define NSIN_MAGIC   0x4E53494Eu
#define GEOB_MAGIC   0x47454F42u
#define NSIN_STRIDE  8
#define GEO_FIELDS   8

int main (int argc, char **argv)
{
    const char *inpath = NULL, *outpath = NULL;
    int text = 0, i;
    FILE *fi, *fo;
    u32 hdr[4], nrec, k;

    for (i = 1; i < argc; i++) {
        if      (!strcmp (argv[i], "--cast")    && i+1 < argc)
            cast_near   = !strcmp (argv[++i], "near");
        else if (!strcmp (argv[i], "--castsrc") && i+1 < argc)
            castsrc_f64 = !strcmp (argv[++i], "f64");
        else if (!strcmp (argv[i], "--prec")    && i+1 < argc)
            prec_f64    = !strcmp (argv[++i], "f64");
        else if (!strcmp (argv[i], "--text")) text = 1;
        else if (!inpath) inpath = argv[i];
        else outpath = argv[i];
    }
    if (!inpath || !outpath) {
        fprintf (stderr, "usage: geo_ref <in.nsin> <out.geob> "
                 "[--cast chop|near] [--castsrc ext|f64] [--prec ext|f64]\n");
        return 2;
    }

    x87_enter();
    if ((x87_cw() & 0x0F3F) != (0x133F & 0x0F3F)) {
        fprintf (stderr, "geo_ref: control word did not take: %04X\n", x87_cw());
        return 4;
    }
    /* FLOATPOLICY 3.6: fstp qword writes eight bytes low half first.  Prove
       the host agrees before any number below is believed. */
    {
        double one = 1.0; u32 halves[2];
        memcpy (halves, &one, 8);
        if (halves[0] != 0x00000000u || halves[1] != 0x3FF00000u) {
            fprintf (stderr, "geo_ref: binary64 1.0 is not 00000000/3FF00000\n");
            return 4;
        }
        if (sizeof (ext) < 10) {
            fprintf (stderr, "geo_ref: long double is not the 80-bit type\n");
            return 4;
        }
    }

    fi = fopen (inpath, "rb");
    if (!fi) { fprintf (stderr, "geo_ref: cannot open %s\n", inpath); return 2; }
    if (fread (hdr, 4, 4, fi) != 4 || hdr[0] != NSIN_MAGIC || hdr[3] != NSIN_STRIDE) {
        fprintf (stderr, "geo_ref: %s is not NSIN\n", inpath); return 2;
    }
    nrec = hdr[2];

    fo = fopen (outpath, text ? "w" : "wb");
    if (!fo) { fprintf (stderr, "geo_ref: cannot write %s\n", outpath); return 2; }

    if (!text) {
        u32 oh[8];
        oh[0] = GEOB_MAGIC; oh[1] = 1; oh[2] = nrec; oh[3] = GEO_FIELDS;
        oh[4] = (u32) cast_near; oh[5] = (u32) castsrc_f64;
        oh[6] = (u32) prec_f64;  oh[7] = 0;
        fwrite (oh, 4, 8, fo);
    }

    for (k = 0; k < nrec; k++) {
        i32 in[NSIN_STRIDE];
        int b;
        if (fread (in, 4, NSIN_STRIDE, fi) != NSIN_STRIDE) {
            fprintf (stderr, "geo_ref: short record %lu\n", (unsigned long)k);
            return 2;
        }
        ap_target_x = (double) in[0];
        ap_target_y = (double) in[1];
        ap_target_z = (double) in[2];
        forced_class = in[3];
        forced_seed  = in[4];

        memset (p_type, 0, sizeof p_type);
        memset (p_owner, 0, sizeof p_owner);
        memset (p_moonid, 0, sizeof p_moonid);
        ns_draws = ns_float_draws = 0;
        ns_in_fsite = 0;

        extract_ap_target_infos ();
        if (forced_class >= 0) ap_target_class = forced_class;
        (void) starnop (ap_target_x, ap_target_y, ap_target_z);
        prepare_nearstar ();

        if (text) {
            fprintf (fo, "# rec %lu class %d nop %d nob %d draws %ld float %ld\n",
                     (unsigned long)k, nearstar_class, nearstar_nop,
                     nearstar_nob, ns_draws, ns_float_draws);
            for (b = 0; b < nearstar_nob; b++)
                fprintf (fo, "%lu %d %d %d %.17g %.17g %.17g %.17g %.17g %.17g %.17g %.17g\n",
                         (unsigned long)k, b, (int)p_type[b], p_owner[b],
                         p_orb_orient[b], p_orb_seed[b], p_tilt[b], p_orb_tilt[b],
                         p_orb_ecc[b], p_ray[b], p_orb_ray[b], p_ring[b]);
        } else {
            u32 rh[4];
            rh[0] = (u32) nearstar_class;
            rh[1] = (u32) nearstar_nop;
            rh[2] = (u32) nearstar_nob;
            rh[3] = (u32) ns_draws;
            fwrite (rh, 4, 4, fo);
            for (b = 0; b < nearstar_nob; b++) {
                double row[GEO_FIELDS];
                row[0] = p_orb_orient[b]; row[1] = p_orb_seed[b];
                row[2] = p_tilt[b];       row[3] = p_orb_tilt[b];
                row[4] = p_orb_ecc[b];    row[5] = p_ray[b];
                row[6] = p_orb_ray[b];    row[7] = p_ring[b];
                fwrite (row, 8, GEO_FIELDS, fo);
            }
        }
    }

    fclose (fi);
    fclose (fo);
    x87_leave();
    return 0;
}
