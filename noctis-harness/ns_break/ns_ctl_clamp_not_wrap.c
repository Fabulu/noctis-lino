/* ns_ref.c -- Wave 4 reference side A.
 *
 * A LITERAL transcription of NOCTIS-0.CPP:3968-4376 (Noctis IV Plus, 1996),
 * expression for expression, line for line.  It is deliberately ugly: the
 * point of this file is that a reader can put it next to the DOS source and
 * check it token by token, so nothing is tidied, renamed or restructured.
 *
 * Subject lines, from C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP:
 *
 *      3968-3983  extract_ap_target_infos()
 *      3987       zrandom()
 *      4002-4041  search_id_code()          (phase H, consumes no draws)
 *      4047-4057  starnop()
 *      4059-4376  prepare_nearstar()
 *
 * Constant tables, same file: 922-930 (class_ray/class_rayvar/class_planets),
 * 976 (planet_possiblemoons), 978-985 (the scalings and avg_planet_ray).
 * star_classes=12, planet_types=10, maxbodies=20*avgmoons=80 from NOCTIS-D.H
 * 140-144.
 *
 * ---------------------------------------------------------------------------
 * THE FOUR THINGS THAT ARE NOT A LITERAL TRANSCRIPTION, AND WHY
 * ---------------------------------------------------------------------------
 *
 * 1. int is 16 bits in the DOS build.  Every argument to random() is narrowed
 *    explicitly through i16(), and every value random() returns is narrowed
 *    the same way.  Nothing is left to this compiler's int.
 *
 * 2. A double or float argument to random() goes through Borland's __ftol
 *    (chop to a 32-bit long) and is then read as the low 16 bits.  ftoi16()
 *    spells that out in two explicit steps.  LR's one-step (int) cast is
 *    undefined behaviour at exactly these sites, so it is not used.
 *
 * 3. Signed overflow.  `seed * 0x015A4E35` overflows a signed 32-bit int.
 *    THIS FILE MUST BE BUILT WITH -fwrapv.  Without it gcc -O2 is entitled
 *    to assume the overflow cannot happen and miscompiles the LCG into a
 *    plausible wrong galaxy.  ns_diff.py builds a second copy without the
 *    flag and REQUIRES it to differ; if that ever stops differing, the flag
 *    has stopped mattering and we want to know.
 *
 * 4. GEOMETRY IS COMPUTED IN DOUBLE, not on an 80-bit x87 stack with the
 *    DOS instruction schedule.  This is a declared approximation, not an
 *    oversight.  It is safe because the complete topology of a system --
 *    nop, nob, and every body's type, owner and moonid -- is provably
 *    independent of every float value in the routine: every draw whose
 *    result selects a branch, a count or a type takes an INTEGER argument
 *    (see the site registry below), and random(n) consumes exactly one
 *    rand() for every n including 0 and negative n.  The eleven float-
 *    argument sites therefore change drawn VALUES that nothing reads back.
 *    ns_diff.py proves this rather than asserting it: --jitter perturbs
 *    nearstar_ray and requires the topology digest not to move.
 *    The identity itself is NOT in this bucket -- it is computed on the
 *    real x87 at 64-bit precision, see ident_ext() below.
 *
 * ---------------------------------------------------------------------------
 * THE ELEVEN FLOAT-ARGUMENT DRAW SITES  (values discarded by the port)
 * ---------------------------------------------------------------------------
 *      NOCTIS-0.CPP:4089   random  (300 * nearstar_ray)
 *      NOCTIS-0.CPP:4090   zrandom (10 * p_orb_seed[n])
 *      NOCTIS-0.CPP:4091   zrandom (10 * p_orb_seed[n])
 *      NOCTIS-0.CPP:4092   random  (p_orb_seed[n] + 10*fabs(p_orb_tilt[n]))
 *      NOCTIS-0.CPP:4093   random  (p_orb_seed[n])
 *      NOCTIS-0.CPP:4094   zrandom (p_ray[n])
 *      NOCTIS-0.CPP:4195   zrandom (300 * p_ray[n])
 *      NOCTIS-0.CPP:4196   zrandom (10 * p_orb_seed[q])
 *      NOCTIS-0.CPP:4197   zrandom (10 * p_orb_seed[q])
 *      NOCTIS-0.CPP:4198   random  (p_orb_seed[q] + 10*fabs(p_orb_tilt[q]))
 *      NOCTIS-0.CPP:4199   random  (p_orb_seed[n])    <- the PARENT's seed
 * Exactly eleven.  ns_diff.py greps this file and asserts the count.
 *
 * Build:  gcc -O2 -fwrapv -o ns_ref.exe ns_ref.c -lm
 * Usage:  ns_ref <in.nsin> <out.nstopo> [--digest] [--starmap PATH]
 *                [--identchop ext|f64] [--jitter EPS]
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

/* ======================================================================= */
/* Wave 1: Borland's LCG, from the pinned bytes of NOCTIS.EXE.             */
/*   srand   @15953  state = arg & FFFF, high word explicitly zeroed       */
/*   rand    @15970  state = state*0x015A4E35 + 1 ; return (state>>16)&7FFF*/
/*   random  @82487  movsx both, imul 32x32, cwd/idiv by 0x8000            */
/* ======================================================================= */

#define MULT    0x015A4E35u
#define DIVISOR 0x8000

static u32 rnd_state = 1;

/* every draw the port takes passes through here and nowhere else */
static long ns_draws;
static long ns_phase_draws[8];
static int  ns_phase;          /* 0 prelude, 1 A .. 7 G */
static long ns_extra_draws;    /* extract_ap_target_infos + starnop */
static int  ns_counting;       /* 0 while outside prepare_nearstar */
static long ns_budget = 100000;
static int  ns_over_budget;

static void brtl_srand (unsigned seed)
{
    rnd_state = (u32)(seed & 0xFFFFu);      /* c7 06 5c 39 .. ; a3 5a 39 */
}

/* The per-draw ledger.  Every entry is (NOCTIS-0.CPP line, argument as it
   reached random() after narrowing, value returned).  A desynchronised
   stream shows up here with an exact address -- "system 412, draw 97, we
   are at line 4213 and the reference is at 4201" -- instead of as a
   percentage. */
static FILE *ledger_fp;
static int   ledger_site;

static long brtl_rand (void)
{
    if (ns_counting) {
        ns_draws++;
        ns_phase_draws[ns_phase]++;
        if (ns_draws > ns_budget) ns_over_budget = 1;
    } else {
        ns_extra_draws++;
    }
    rnd_state = rnd_state * MULT + 1u;
    return (long)((rnd_state >> 16) & 0x7FFFu);
}

/* n has ALREADY been narrowed to int16 by the caller (movsx word [bp+6]) */
static int brtl_random (i16t n)
{
    long r = brtl_rand();                       /* drawn even when n == 0 */
    i32  p = (i32)((u32)r * (u32)(i32)n);       /* imul eax,edx : low 32  */
    int  v = (int)(i16t)(p / DIVISOR);          /* idiv: toward zero      */
    if (ledger_fp && ns_counting) {
        i32 e[3];
        e[0] = ledger_site; e[1] = (i32) n; e[2] = (i32) v;
        fwrite (e, 4, 3, ledger_fp);
    }
    return v;
}

/* --------------------------------------------------------- narrowings -- */

static i16t i16 (long v)
{
    return (i16t)(u32)v;                        /* -fwrapv makes this defined */
}

/* Borland's __ftol: FISTP dword with the chop rounding mode, then the
   caller reads AX.  An out-of-range value yields the x87 integer
   indefinite 0x80000000, which is real behaviour and not an error. */
static i16t ftoi16 (double d)
{
    i32 l;
    if (!(d > -2147483649.0 && d < 2147483648.0) || d != d)
        l = (i32)0x80000000;
    else
        l = (i32)(long long)d;                  /* C truncates toward zero */
    if (l >  32767) return  32767;
    if (l < -32768) return -32768;
    return (i16t)l;
}

/* Every draw site carries its NOCTIS-0.CPP line number.  That number is the
   site's identity in the ledger and in every failure message. */
#define RANDI(L,n)   (ledger_site = (L), brtl_random (i16 ((long)(n))))
#define RANDF(L,d)   (ledger_site = (L), brtl_random (ftoi16 ((double)(d))))

/* NOCTIS-0.CPP:3987  float zrandom (int range) { return random-random; }
   Wave 2 settled the operand order as LEFT TO RIGHT: first draw minus
   second.  Borland's int subtraction is 16-bit, so the difference wraps
   before it is widened to float. */
static double zrand_n (int site, i16t range)
{
    int a, b;
    ledger_site = site; a = brtl_random (range);
    ledger_site = site; b = brtl_random (range);
    return (double)(i16t)(u32)(long)(a - b);
}
#define ZRANDI(L,n)  zrand_n ((L), i16 ((long)(n)))
#define ZRANDF(L,d)  zrand_n ((L), ftoi16 ((double)(d)))

/* ======================================================================= */
/* the constant tables, NOCTIS-0.CPP 922-985 / NOCTIS-D.H 140-144          */
/* ======================================================================= */

#define star_classes  12
#define planet_types  10
#define avgmoons       4
#define maxbodies     (20 * avgmoons)          /* 80 */

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

/* PITAGORA.H:136 */
static const double deg = 3.14159265358979323846 / 180.0;

/* ======================================================================= */
/* the globals, NOCTIS-0.CPP 932-950 and NOCTIS-0.H 120-199                */
/* ======================================================================= */

static double ap_target_x, ap_target_y, ap_target_z;
static int    ap_target_class;
static float  ap_target_ray;
static int    ap_target_spin;

static double nearstar_x, nearstar_y, nearstar_z;
static int    nearstar_class;
static float  nearstar_ray;
static int    nearstar_spin;
static int    nearstar_nop, nearstar_nob, nearstar_labeled;
static double nearstar_identity;

static char   nearstar_p_type      [maxbodies];
static int    nearstar_p_owner     [maxbodies];
static char   nearstar_p_moonid    [maxbodies];
static double nearstar_p_ring      [maxbodies];
static double nearstar_p_tilt      [maxbodies];
static double nearstar_p_ray       [maxbodies];
static double nearstar_p_orb_ray   [maxbodies];
static double nearstar_p_orb_seed  [maxbodies];
static double nearstar_p_orb_tilt  [maxbodies];
static double nearstar_p_orb_orient[maxbodies];
static double nearstar_p_orb_ecc   [maxbodies];

static double jitter = 0.0;      /* the float-independence control */

/* ======================================================================= */
/* the identity, on the real x87 at 64-bit precision                       */
/*                                                                         */
/* NOCTIS-0.CPP:4078   nearstar_identity = x/100000*y/100000*z/100000       */
/*                                                                         */
/* Borland compiled this as five operations and ONE store, with the         */
/* intermediate never leaving the stack:                                    */
/*   fild x / fidiv 1e5 / fild y / fmulp / fidiv 1e5 / fild z / fmulp       */
/*   / fidiv 1e5 / fstp id            (Wave 3, docs-notes/FLOATPOLICY.md)   */
/* long double on this toolchain IS the 80-bit type, and the control word   */
/* is forced to 133Fh (64-bit precision, round to nearest) so this is the   */
/* same arithmetic and not an approximation of it.                          */
/* ======================================================================= */

#if defined(__GNUC__) && (defined(__i386__) || defined(__x86_64__))
#define HAVE_X87 1
static unsigned short cw_save;
static void x87_enter (void) {
    unsigned short cw = 0x133F;
    __asm__ __volatile__ ("fnstcw %0" : "=m" (cw_save));
    __asm__ __volatile__ ("fldcw %0" : : "m" (cw));
}
static void x87_leave (void) {
    __asm__ __volatile__ ("fldcw %0" : : "m" (cw_save));
}
#else
#define HAVE_X87 0
static void x87_enter (void) {}
static void x87_leave (void) {}
#endif

typedef long double ext;

static ext ident_ext (double x, double y, double z)
{
    ext v;
    x87_enter();
    v = (ext)x;
    v = v / (ext)100000;      /* fidiv */
    v = v * (ext)y;           /* fmulp */
    v = v / (ext)100000;
    v = v * (ext)z;
    v = v / (ext)100000;
    x87_leave();
    return v;
}

/* chop the LIVE extended value to a long, then read the low 16 bits.
   identchop_f64 == 1 instead rounds to binary64 first, which is what
   NOCTIS.CPP:1244+1257 does (it stores into ap_target_id before calling
   srand) and therefore what the catalogue's 'S' class tags record. */
static int identchop_f64 = 0;

static unsigned ident_chop16 (double x, double y, double z)
{
    ext v = ident_ext (x, y, z);
    double d;
    i32 l;
    if (identchop_f64) { d = (double)v; v = (ext)d; }
    if (!(v > (ext)-2147483649.0 && v < (ext)2147483648.0) || v != v)
        l = (i32)0x80000000;
    else
        l = (i32)(long long)v;
    return (unsigned)((u32)l & 0xFFFFu);
}

/* ======================================================================= */
/* the seed, NOCTIS-0.CPP:4080 and :4051                                   */
/*                                                                         */
/*   srand ((long)x%10000*(long)y%10000*(long)z%10000)                     */
/*                                                                         */
/* *, / and % are all the same precedence and associate LEFT TO RIGHT, so  */
/* this is  ((((x%10000)*y)%10000)*z)%10000  -- a chain of remainders, NOT  */
/* a product of three remainders.  The (long) casts are the identity        */
/* function here: nearstar_x/y/z are doubles holding exact integers         */
/* produced by the galaxy hash, and ns_corpus.py asserts that for every     */
/* star it grades rather than assuming it.                                  */
/* The intermediate is a 32-bit long and it overflows on most real stars;   */
/* that wrap is part of the answer.  -fwrapv again.                         */
/* ======================================================================= */

/* Two spellings of the same expression, and the build proves they agree.
 *
 * SEED_SIGNED is the naive one: an i32 running value multiplied by the next
 * coordinate.  That overflows a signed 32-bit int on most real stars -- 3179
 * of the 4194 in the recon's corpus -- and signed overflow is undefined, so
 * this spelling is only meaningful under -fwrapv.
 *
 * The default spelling does the multiply in u32, where wrapping is defined
 * by the standard, and reinterprets.  It needs no flags and has no UB.
 *
 * ns_diff.py --overflow builds both and REQUIRES them to agree.  That is the
 * check that matters: it proves the wrap is the semantics we mean, rather
 * than merely proving that a compiler flag changes something.
 */
static i32 seed_from_xyz (i32 x, i32 y, i32 z)
{
    i32 t;
    t = x % 10000;                              /* C %: toward zero */
#ifdef SEED_SIGNED
    t = t * y;
    t = t % 10000;
    t = t * z;
#else
    t = (i32)((u32)t * (u32)y);
    t = t % 10000;
    t = (i32)((u32)t * (u32)z);
#endif
    t = t % 10000;
    return t;
}

/* ======================================================================= */
/* phase H: search_id_code, NOCTIS-0.CPP:4002-4041.  No draws.             */
/* ======================================================================= */

static unsigned char *smap;
static long smap_len;
static const double idscale = 0.00001;

static long search_id_code (double id_code, char type)
{
    long pos = 4;
    long off;
    double id_low  = id_code - idscale;
    double id_high = id_code + idscale;
    if (!smap) return -1;
    for (off = 4; off + 32 <= smap_len; off += 32) {
        if ((char)smap[off + 29] == type) {
            double v;
            memcpy (&v, smap + off, 8);
            if (v > id_low && v < id_high) return pos;
        }
        pos += 32;
    }
    return -1;
}

/* ======================================================================= */
/* NOCTIS-0.CPP:3968-3983                                                  */
/* ======================================================================= */

static void extract_ap_target_infos (void)
{
    brtl_srand (ident_chop16 (ap_target_x, ap_target_y, ap_target_z));

    ap_target_class = RANDI (3972, star_classes);
    ap_target_ray = (float)(((float)class_ray[ap_target_class]
                    + (float)RANDI (3973, class_rayvar[ap_target_class])) * 0.001);

    ap_target_spin = 0;
    if (ap_target_class == 11) ap_target_spin = RANDI (3980, 30) + 1;
    if (ap_target_class ==  7) ap_target_spin = RANDI (3981, 12) + 1;
    if (ap_target_class ==  2) ap_target_spin = RANDI (3982,  4) + 1;
}

/* ======================================================================= */
/* NOCTIS-0.CPP:4047-4057                                                  */
/* ======================================================================= */

static int starnop (double star_x, double star_y, double star_z)
{
    int r;
    brtl_srand ((unsigned)seed_from_xyz ((i32)star_x, (i32)star_y, (i32)star_z));
    r  = RANDI (4052, class_planets[ap_target_class] + 1);
    r += RANDI (4053, 2);
    r -= RANDI (4054, 2);
    if (r < 0) r = 0;
    return r;
}

/* ======================================================================= */
/* NOCTIS-0.CPP:4059-4376                                                  */
/* ======================================================================= */

static int forced_class = -1;      /* NSIN i3 override */
static i32 forced_seed  = -1;      /* NSIN i4 override */

static void prepare_nearstar (void)
{
    int n, c, q, r, s, t;
    double key_radius;

    /* the !_delay branch, taken for a freshly reached star */
    nearstar_class = ap_target_class;
    nearstar_x = ap_target_x;
    nearstar_y = ap_target_y;
    nearstar_z = ap_target_z;
    nearstar_ray = ap_target_ray;
    nearstar_spin = ap_target_spin;

    if (forced_class >= 0) nearstar_class = forced_class;

    nearstar_ray = (float)(nearstar_ray + jitter);   /* the control, normally 0 */

    /* :4078 */
    nearstar_identity = (double) ident_ext (nearstar_x, nearstar_y, nearstar_z);

    /* :4080 */
    {
        i32 sd = (forced_seed >= 0) ? forced_seed
               : seed_from_xyz ((i32)nearstar_x, (i32)nearstar_y, (i32)nearstar_z);
        brtl_srand ((unsigned)sd);
    }

    ns_counting = 1;
    ns_phase = 0;
    /* :4082 */
    nearstar_nop = RANDI (4082, class_planets[nearstar_class] + 1);

    /* --------- phase A : NOCTIS-0.CPP:4086-4107 ------------------------ */
    ns_phase = 1;
    for (n = 0; n < nearstar_nop; n++) {
        nearstar_p_owner[n]      = -1;
        nearstar_p_orb_orient[n] = (double) deg * (double) RANDI (4088, 360);
        nearstar_p_orb_seed[n]   = 3 * (n*n+1) * (double)nearstar_ray
                                 + (double) RANDF (4089, 300 * (double)nearstar_ray) / 100;
        nearstar_p_tilt[n]       = ZRANDF (4090, 10 * nearstar_p_orb_seed[n]) / 500;
        nearstar_p_orb_tilt[n]   = ZRANDF (4091, 10 * nearstar_p_orb_seed[n]) / 5000;
        nearstar_p_orb_ecc[n]    = 1 - (double) RANDF (4092, nearstar_p_orb_seed[n]
                                     + 10 * fabs (nearstar_p_orb_tilt[n])) / 2000;
        nearstar_p_ray[n]        = (double) RANDF (4093, nearstar_p_orb_seed[n]) * 0.001 + 0.01;
        /* :4094 is the ONLY expression in the routine with two draw sites in
           it, and C leaves the order of * unspecified.  Forced to source
           order with temporaries.  ns_mkbreak.py swaps them and ns_diff.py
           requires the topology digest not to move -- the value changes,
           the tree does not. */
        {
            double zr = ZRANDF (4094, nearstar_p_ray[n]);
            double rr = (double) RANDI (4094, 1000);
            nearstar_p_ring[n] = zr * (1 + rr / 100);
        }
        if (nearstar_class != 8)
            nearstar_p_type[n] = (char) RANDI (4096, planet_types);
        else {
            if (RANDI (4098, 2)) {
                nearstar_p_type[n] = 10;
                nearstar_p_orb_tilt[n] *= 100;
            } else
                nearstar_p_type[n] = (char) RANDI (4103, planet_types);
        }
        if (nearstar_class == 2 || nearstar_class == 7 || nearstar_class == 15)
            nearstar_p_orb_seed[n] *= 10;
    }

    /* --------- phase B : NOCTIS-0.CPP:4111-4115 ------------------------
       All three ifs evaluate.  The writes land at indices 2,3,4 whether or
       not nop reaches them; when it does not they are inert, because every
       later reader of p_type[k] for k >= nop writes it first. */
    ns_phase = 2;
    if (!nearstar_class) {
        if (RANDI (4112, 4) == 2) nearstar_p_type[2] = 3;
        if (RANDI (4113, 4) == 2) nearstar_p_type[3] = 3;
        if (RANDI (4114, 4) == 2) nearstar_p_type[4] = 3;
    }

    /* --------- phase C : NOCTIS-0.CPP:4120-4140 ------------------------
       while-loops with NO iteration cap.  Class 9 accepts 3 of 10 and has
       been observed re-rolling 109 times in one system. */
    ns_phase = 3;
    for (n = 0; n < nearstar_nop; n++) {
        switch (nearstar_class) {
            case 2:  while (nearstar_p_type[n] == 3)
                         nearstar_p_type[n] = (char) RANDI (4123, 10);
                     break;
            case 5:  while (nearstar_p_type[n] == 6 ||
                            nearstar_p_type[n] == 9)
                         nearstar_p_type[n] = (char) RANDI (4127, 10);
                     break;
            case 7:  nearstar_p_type[n] = 9;
                     break;
            case 9:  while (nearstar_p_type[n] != 0 &&
                            nearstar_p_type[n] != 6 &&
                            nearstar_p_type[n] != 9)
                         nearstar_p_type[n] = (char) RANDI (4134, 10);
                     break;
            case 11: while (nearstar_p_type[n] != 1 &&
                            nearstar_p_type[n] != 7)
                         nearstar_p_type[n] = (char) RANDI (4138, 10);
        }
        if (ns_over_budget) return;
    }

    /* --------- phase D : NOCTIS-0.CPP:4145-4168 ------------------------
       The || and && in case 3 SHORT-CIRCUIT.  random(4) fires only when
       2 <= n <= 6 and the class is non-zero. */
    ns_phase = 4;
    for (n = 0; n < nearstar_nop; n++) {
        switch (nearstar_p_type[n]) {
            case 0:
                if (RANDI (4148, 8))
                    nearstar_p_type[n] ++;
                break;
            case 3:
                if ((n < 2) || (n > 6) || (nearstar_class && RANDI (4152, 4))) {
                    if (RANDI (4153, 2))
                        nearstar_p_type[n]++;
                    else
                        nearstar_p_type[n]--;
                }
                break;
            case 7:
                if (n < 7) {
                    if (RANDI (4161, 2))
                        nearstar_p_type[n] --;
                    else
                        nearstar_p_type[n] -= 2;
                }
                break;
        }
    }

    /* --------- phase E : NOCTIS-0.CPP:4172-4260 ------------------------ */
    ns_phase = 5;
    nearstar_nob = nearstar_nop;

    if (nearstar_class == 2 || nearstar_class == 7 || nearstar_class == 15)
        goto no_moons;

    for (n = 0; n < nearstar_nop; n++) {
        s = nearstar_p_type[n];
        if (n < 2) {
            t = 0;
            if (s == 10)
                t = RANDI (4183, 3);
        } else
            t = RANDI (4186, planet_possiblemoons[s] + 1);
        /* the clamp removes BODIES, never draws */
        if (nearstar_nob + t > maxbodies)
            t = maxbodies - nearstar_nob;
        for (c = 0; c < t; c++) {
            q = nearstar_nob + c;
            nearstar_p_owner[q]      = n;
            nearstar_p_moonid[q]     = (char) c;
            nearstar_p_orb_orient[q] = (double) deg * (double) RANDI (4194, 360);
            nearstar_p_orb_seed[q]   = (c*c+4) * nearstar_p_ray[n]
                                     + (double) ZRANDF (4195, 300 * nearstar_p_ray[n]) / 100;
            nearstar_p_tilt[q]       = ZRANDF (4196, 10 * nearstar_p_orb_seed[q]) / 50;
            nearstar_p_orb_tilt[q]   = ZRANDF (4197, 10 * nearstar_p_orb_seed[q]) / 500;
            nearstar_p_orb_ecc[q]    = 1 - (double) RANDF (4198, nearstar_p_orb_seed[q]
                                         + 10 * fabs (nearstar_p_orb_tilt[q])) / 2000;
            /* :4199 reads the PARENT's seed, index n, not q.  The value is
               dead but the draw is live. */
            nearstar_p_ray[q]        = (double) RANDF (4199, nearstar_p_orb_seed[n]) * 0.05 + 0.1;
            nearstar_p_ring[q]       = 0;
            nearstar_p_type[q]       = (char) RANDI (4201, planet_types);
            r = nearstar_p_type[q];
            if (r == 9 && s != 10) r = 2;
            if (r == 6 && s <  9)  r = 5;
            /* c == 0 on the first moon: random(0) STILL draws */
            if (n > 7 && RANDI (4213, c)) r = 7;
            if (n > 9 && RANDI (4214, c)) r = 7;
            if (r == 2 || r == 3 || r == 4 || r == 8) {
                if (s != 6 && s < 9)
                    r = 1;
            }
            /* reaching the random(4) below needs r==3 and s<9, and the test
               above has already rewritten r to 1 unless s == 6 exactly */
            if (r == 3 && s < 9) {
                if (n > 7)
                    r = 7;
                if (nearstar_class && RANDI (4238, 4))
                    r = 5;
                if (nearstar_class == 2 ||
                    nearstar_class == 7 ||
                    nearstar_class == 11)
                    r = 8;
            }
            if (r == 7 && n <= 5) r = 1;
            if ((nearstar_class == 2 || nearstar_class == 5 ||
                 nearstar_class == 7 || nearstar_class == 11)
                 && RANDI (4255, n)) r = 7;
            nearstar_p_type[q] = (char) r;
        }
        nearstar_nob += t;
    }

    /* --------- phase F : NOCTIS-0.CPP:4300-4341 ------------------------
       exactly 4 * nob draws: 2 zrandom per planet and 2 per moon */
no_moons:
    ns_phase = 6;
    key_radius = nearstar_ray * planet_orb_scaling;
    if (nearstar_class ==  8) key_radius *= 2;
    if (nearstar_class ==  2) key_radius *= 16;
    if (nearstar_class ==  7) key_radius *= 18;
    if (nearstar_class == 11) key_radius *= 20;
    for (n = 0; n < nearstar_nop; n++) {
        nearstar_p_ray[n] = avg_planet_ray[(int)nearstar_p_type[n]]
                          + avg_planet_ray[(int)nearstar_p_type[n]] * ZRANDI (4308, 100) / 200;
        nearstar_p_ray[n] *= avg_planet_sizing;
        nearstar_p_orb_ray[n] = key_radius + key_radius * ZRANDI (4310, 100) / 500;
        nearstar_p_orb_ray[n] += key_radius * avg_planet_ray[(int)nearstar_p_type[n]];
        if (n < 8)
            key_radius += nearstar_p_orb_ray[n];
        else
            key_radius += 0.22 * nearstar_p_orb_ray[n];
    }

    n = nearstar_nop;
    while (n < nearstar_nob) {
        q = 0;
        c = nearstar_p_owner[n];
        key_radius = nearstar_p_ray[c] * moon_orb_scaling;
        while (n < nearstar_nob && nearstar_p_owner[n] == c) {
            nearstar_p_ray[n] = avg_planet_ray[(int)nearstar_p_type[n]]
                              + avg_planet_ray[(int)nearstar_p_type[n]] * ZRANDI (4331, 100) / 200;
            nearstar_p_ray[n] *= avg_moon_sizing;
            nearstar_p_orb_ray[n] = key_radius + key_radius * ZRANDI (4333, 100) / 250;
            nearstar_p_orb_ray[n] += key_radius * avg_planet_ray[(int)nearstar_p_type[n]];
            if (q < 2) key_radius += nearstar_p_orb_ray[n];
            if (q >= 2 && q < 8) key_radius += 0.12 * nearstar_p_orb_ray[n];
            if (q >= 8) key_radius += 0.025 * nearstar_p_orb_ray[n];
            q++;
            n++;
        }
    }

    /* --------- phase G : NOCTIS-0.CPP:4345-4361 ------------------------
       exactly 2 * nop draws */
    ns_phase = 7;
    for (n = 0; n < nearstar_nop; n++) {
        nearstar_p_ring[n] = 0.75 * nearstar_p_ray[n] * (2 + RANDI (4348, 3));
        s = nearstar_p_type[n];
        if (s != 6 && s != 9) {
            if (RANDI (4354, 5))
                nearstar_p_ring[n] = 0;
        } else {
            if (RANDI (4358, 2))
                nearstar_p_ring[n] = 0;
        }
    }
    ns_counting = 0;
}

/* phase H, split out so it can be run only where NSIN asks for it */
static void phase_h (void)
{
    int n;
    nearstar_labeled = 0;
    for (n = 1; n <= nearstar_nob; n++)
        if (search_id_code (nearstar_identity + n, 'P') != -1)
            nearstar_labeled++;
}

/* ======================================================================= */
/* NSIN / NSTOPO                                                           */
/* ======================================================================= */

#define NSIN_MAGIC   0x4E53494Eu
#define NSTOPO_MAGIC 0x4E53544Fu
#define NSIN_STRIDE  8
#define NSTOPO_STRIDE 100

static u32 fnv_lo, fnv_hi;   /* FNV-1a 64, split */

static void fnv_reset (u64 *h) { *h = 14695981039346656037ULL; }
static void fnv_u32 (u64 *h, u32 v)
{
    int k;
    for (k = 0; k < 4; k++) {
        *h ^= (unsigned char)((v >> (8*k)) & 0xFF);
        *h *= 1099511628211ULL;
    }
}

int main (int argc, char **argv)
{
    const char *inpath = NULL, *outpath = NULL;
    const char *smpath = "C:\\programmieren\\noctis\\niv-plus\\data\\STARMAP.BIN";
    int digest = 0, i;
    FILE *fi, *fo;
    u32 hdr[4];
    u32 nrec, k;
    u32 *rec;
    u64 dg[star_classes];
    long dgn[star_classes];

    for (i = 1; i < argc; i++) {
        if (!strcmp (argv[i], "--digest")) digest = 1;
        else if (!strcmp (argv[i], "--starmap") && i+1 < argc) smpath = argv[++i];
        else if (!strcmp (argv[i], "--identchop") && i+1 < argc)
            identchop_f64 = !strcmp (argv[++i], "f64");
        else if (!strcmp (argv[i], "--jitter") && i+1 < argc) jitter = atof (argv[++i]);
        else if (!strcmp (argv[i], "--ledger") && i+1 < argc) {
            ledger_fp = fopen (argv[++i], "wb");
            if (!ledger_fp) { fprintf (stderr, "ns_ref: cannot write ledger\n"); return 2; }
        }
        else if (!inpath) inpath = argv[i];
        else outpath = argv[i];
    }
    if (!inpath || !outpath) {
        fprintf (stderr, "usage: ns_ref <in.nsin> <out.nstopo> [--digest]"
                         " [--starmap PATH] [--identchop ext|f64] [--jitter E]\n");
        return 2;
    }

    fi = fopen (inpath, "rb");
    if (!fi) { fprintf (stderr, "ns_ref: cannot open %s\n", inpath); return 2; }
    if (fread (hdr, 4, 4, fi) != 4) { fprintf (stderr, "ns_ref: short header\n"); return 2; }
    if (hdr[0] != NSIN_MAGIC) {
        fprintf (stderr, "ns_ref: %s is not NSIN (magic %08lX, want %08lX)\n",
                 inpath, (unsigned long)hdr[0], (unsigned long)NSIN_MAGIC);
        return 2;
    }
    if (hdr[1] != 1 || hdr[3] != NSIN_STRIDE) {
        fprintf (stderr, "ns_ref: NSIN version %lu stride %lu unsupported\n",
                 (unsigned long)hdr[1], (unsigned long)hdr[3]);
        return 2;
    }
    nrec = hdr[2];

    /* phase H needs the catalogue; load it once */
    {
        FILE *fs = fopen (smpath, "rb");
        if (fs) {
            fseek (fs, 0, SEEK_END);
            smap_len = ftell (fs);
            fseek (fs, 0, SEEK_SET);
            smap = (unsigned char *) malloc ((size_t) smap_len);
            if (smap && fread (smap, 1, (size_t) smap_len, fs) != (size_t) smap_len)
                { free (smap); smap = NULL; }
            fclose (fs);
        }
    }

    fo = fopen (outpath, "wb");
    if (!fo) { fprintf (stderr, "ns_ref: cannot write %s\n", outpath); return 2; }

    for (k = 0; k < star_classes; k++) { fnv_reset (&dg[k]); dgn[k] = 0; }

    {
        u32 oh[8];
        oh[0] = NSTOPO_MAGIC; oh[1] = 1; oh[2] = nrec; oh[3] = NSTOPO_STRIDE;
        oh[4] = (u32) digest; oh[5] = 1; oh[6] = 0; oh[7] = 0;
        fwrite (oh, 4, 8, fo);
    }

    rec = (u32 *) malloc (NSTOPO_STRIDE * 4);

    for (k = 0; k < nrec; k++) {
        i32 in[NSIN_STRIDE];
        i32 sd;
        int b;
        if (fread (in, 4, NSIN_STRIDE, fi) != NSIN_STRIDE) {
            fprintf (stderr, "ns_ref: short record %lu\n", (unsigned long)k);
            return 2;
        }
        ap_target_x = (double) in[0];
        ap_target_y = (double) in[1];
        ap_target_z = (double) in[2];
        forced_class = in[3];
        forced_seed  = in[4];

        memset (nearstar_p_type,   0, sizeof nearstar_p_type);
        memset (nearstar_p_owner,  0, sizeof nearstar_p_owner);
        memset (nearstar_p_moonid, 0, sizeof nearstar_p_moonid);

        ns_draws = ns_extra_draws = 0;
        ns_over_budget = 0;
        for (b = 0; b < 8; b++) ns_phase_draws[b] = 0;
        ns_counting = 0;

        if (ledger_fp) {
            i32 mark[3];
            mark[0] = -1; mark[1] = (i32) k; mark[2] = 0;
            fwrite (mark, 4, 3, ledger_fp);
        }

        extract_ap_target_infos ();
        if (forced_class >= 0) ap_target_class = forced_class;
        {
            int snop = starnop (ap_target_x, ap_target_y, ap_target_z);
            prepare_nearstar ();
            nearstar_labeled = -1;
            if (in[6] & 1) phase_h ();

            sd = (forced_seed >= 0) ? forced_seed
               : seed_from_xyz ((i32)nearstar_x, (i32)nearstar_y, (i32)nearstar_z);

            memset (rec, 0, NSTOPO_STRIDE * 4);
            rec[0] = (u32) in[0];
            rec[1] = (u32) in[1];
            rec[2] = (u32) in[2];
            rec[3] = (u32) nearstar_class;
            rec[4] = (u32) (sd & 0xFFFF);
            rec[5] = (u32) nearstar_nop;
            rec[6] = (u32) nearstar_nob;
            rec[7] = (u32) snop;
            rec[8] = (u32) nearstar_labeled;
            {
                u64 bits;
                memcpy (&bits, &nearstar_identity, 8);
                rec[9]  = (u32) (bits & 0xFFFFFFFFu);
                rec[10] = (u32) ((bits >> 32) & 0xFFFFFFFFu);
            }
            rec[11] = (u32) ns_draws;
            for (b = 0; b < 8; b++) rec[12 + b] = (u32) ns_phase_draws[b];
            for (b = 0; b < maxbodies; b++) {
                if (b >= nearstar_nob) { rec[20 + b] = 0xFFFFFFFFu; continue; }
                {
                    u32 ty = (u32) (nearstar_p_type[b] & 0xFF);
                    u32 ow = (u32) ((nearstar_p_owner[b] + 1) & 0xFF);
                    u32 mi = (b >= nearstar_nop)
                           ? (u32) (nearstar_p_moonid[b] & 0xFF) : 0u;
                    rec[20 + b] = ty | (ow << 8) | (mi << 16);
                }
            }
            if (ns_over_budget) {
                fprintf (stderr, "ns_ref: DRAW BUDGET EXCEEDED at record %lu\n",
                         (unsigned long)k);
                return 3;
            }
        }
        if (digest) {
            int cl = nearstar_class;
            if (cl >= 0 && cl < star_classes) {
                for (b = 0; b < NSTOPO_STRIDE; b++) fnv_u32 (&dg[cl], rec[b]);
                dgn[cl]++;
            }
        } else {
            fwrite (rec, 4, NSTOPO_STRIDE, fo);
        }
    }

    if (digest) {
        for (k = 0; k < star_classes; k++) {
            u32 two[3];
            two[0] = (u32) (dg[k] & 0xFFFFFFFFu);
            two[1] = (u32) ((dg[k] >> 32) & 0xFFFFFFFFu);
            two[2] = (u32) dgn[k];
            fwrite (two, 4, 3, fo);
        }
    }

    fclose (fi);
    fclose (fo);
    if (ledger_fp) fclose (ledger_fp);
    (void) fnv_lo; (void) fnv_hi;
    return 0;
}
