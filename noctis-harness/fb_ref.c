/* fb_ref.c -- Wave 5-corrective, implementer 2.  The C reference for the
 * Noctis buffer model, palette pipeline, present path and tick period.
 *
 * WRITTEN FROM THE 1996 SOURCES, NOT FROM THE LINO:
 *   NOCTIS-D.H:25-56      buffer sizes
 *   NOCTIS.CPP:2163-2171  the farmalloc order (adaptor appended, NOCTIS-0.CPP:53)
 *   NOCTIS-0.CPP:166-241  range8088, tavola_colori
 *   NOCTIS-0.CPP:1151-1200 shade  -- note the DESTINATION PARAMETER
 *   NOCTIS-0.CPP:307-345  pcopy, pclear (QUADWORDS dwords, not 64000 bytes)
 *   NOCTIS-0.CPP:4485     spot     -- class A, 16-bit DI
 *   NOCTIS-0.CPP:4715     cirrus   -- class A, 16-bit BX BEFORE the shift
 *   NOCTIS-0.CPP:6418-6420 snapshot's DAC scaling, tmppal[c]*4
 *   NOCTIS.CPP:604-628    digit_at, including its txtr[-6..-1] underflow
 *   TDPOLYGS.H:2684       polymap's es:[0xFA00] tinta stash (alias 8)
 *   NOCTIS-D.H:171-176    the quadrant bitfield
 *
 * It never reads work/fb*.txt and it never reads fb_layout.py.  fb_layout.py
 * DERIVES the layout by parsing the 1996 sources; this file TRANSCRIBES it.
 * The two disagreeing is the point of the kind-5 compare.
 *
 * WAVE 5-CORRECTIVE
 *   * FBDUMP v2: a TAG in header unit 8, kind 5 unit 2 DEFINED as base+size,
 *     kind 6 replaced, kinds 7/9/10 added.
 *   * The pads split into TAIL (guard) and SUB (allowance): 11 pads, 22 zones.
 *   * The canary is 4 units per pad, every one read back or produced by the
 *     walker.  v1's 18 units were literals on both sides and could not fail.
 *   * shade() takes its destination buffer, because 14 of its 21 call sites
 *     pass surface_palette.
 *   * class A is masked at the DOS truncation point, against the SEGMENT
 *     ORIGIN.  Allocation size cannot reproduce a wrap.
 *   * tavola_colori's filter is modular unsigned, and a `char` filter of 200
 *     is -56.
 *
 * build:
 *   gcc -std=c99 -O2 -Wall -Wextra -o fb_ref.exe fb_ref.c
 * sabotage builds add exactly one -DBREAK_* each; see BREAKS in fb_compare.py.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>

/* ------------------------------------------------------------ NOCTIS-D.H */

#define OM_BYTES   7340
#define GL_BYTES   22586
#define GL_BREST   10182
#define ST_BYTES   64800
#define PL_BYTES   65552
#define PS_BYTES   40000
#define OC_BYTES   40000
#define SC_BYTES   65540
#define PV_BYTES   20480
#define DM2_BYTES   9360
#define OFF_DIGIMAP2 (-60776L)

#define PAD    16
#define ZONE    8
#define LOWPAD 16

/* Borland's far-heap block header sits below the block and the pointer it
 * hands back has offset 4 inside its own segment.  adaptor is A000:0000. */
#ifdef BREAK_SEGADDRBASE
#define SEG_OFFSET 0
#else
#define SEG_OFFSET 4
#endif
#define ADAPTOR_SEG_OFFSET 0

#define WRAP16 65536

/* one Noctis byte per 32-bit unit, so a byte offset IS a unit offset */
#define NREG 9
enum {
    R_N_OFFSETS_MAP = 0, R_N_GLOBES_MAP, R_S_BACKGROUND, R_P_BACKGROUND,
    R_P_SURFACEMAP, R_OBJECTSCHART, R_PVFILE, R_ADAPTED, R_ADAPTOR
};

static const char *rname[NREG] = {
    "n_offsets_map", "n_globes_map", "s_background", "p_background",
    "p_surfacemap", "objectschart", "pvfile", "adapted", "adaptor"
};
static const int rsize[NREG] = {
    OM_BYTES, GL_BYTES + GL_BREST, ST_BYTES, PL_BYTES,
    PS_BYTES, OC_BYTES, PV_BYTES, SC_BYTES,
#ifdef BREAK_SHRINKADAPTOR
    64000
#else
    SC_BYTES
#endif
};

static int rbase[NREG], rpad[NREG], rsegoff[NREG];
static int nw_top;

/* the workspace.  Under BREAK_PACK4 it is physically packed 4 bytes per unit,
 * which is the whole point of that sabotage. */
#ifdef BREAK_PACK4
static uint32_t *NWSTORE;
#else
static uint32_t *NW;
#endif

static uint32_t *FB;    /* [Display Origin]: 64000 units of 00RRGGBB */
static uint32_t PAL[256];

/* Two magics, because the pads have TWO JOBS and a single magic makes a
 * legitimate write indistinguishable from a violation. */
#define PGUARD 0xA5A5A5A5u   /* TAIL: a write here is a VIOLATION */
#define PALLOW 0x5A5A5A5Au   /* SUB:  a write here may be EXPECTED */

/* ------------------------------------------------------------ byte access */

static void nw_put(int off, int v)
{
#ifdef BREAK_PACK4
    int u = off >> 2, ph = (off & 3) * 8;
    NWSTORE[u] = (NWSTORE[u] & ~(0xFFu << ph)) | ((uint32_t)(v & 255) << ph);
#else
    NW[off] = (uint32_t)(v & 255);
#endif
}

static int nw_get(int off)
{
#ifdef BREAK_PACK4
    return (int)((NWSTORE[off >> 2] >> ((off & 3) * 8)) & 255);
#else
    return (int)(NW[off] & 255);
#endif
}

static uint32_t nw_unit(int off)
{
#ifdef BREAK_PACK4
    return NWSTORE[off >> 2];
#else
    return NW[off];
#endif
}

static void nw_unit_put(int off, uint32_t v)
{
#ifdef BREAK_PACK4
    NWSTORE[off >> 2] = v;
#else
    NW[off] = v;
#endif
}

static int nw_get_signed(int off)
{
    int v = nw_get(off);
    return (v & 0x80) ? v - 256 : v;
}

/* NOCTIS-D.H:171-176.  Four 2-bit fields in one byte. */
static int quad_get(int off, int field) { return (nw_get(off) >> (2 * field)) & 3; }
static void quad_set(int off, int field, int v)
{
    int b = nw_get(off);
    b = (b & ~(3 << (2 * field))) | ((v & 3) << (2 * field));
    nw_put(off, b);
}

/* ------------------------------------------------------------------- FNV */

static uint32_t fnv_init(void) { return 0x811C9DC5u; }
static uint32_t fnv_unit(uint32_t h, uint32_t v)
{
    int i;
    for (i = 0; i < 4; i++) {
        h = (h ^ (v & 0xFFu)) * 0x01000193u;
        v >>= 8;
    }
    return h;
}
static uint32_t fnv_range(int base, int n)
{
    uint32_t h = fnv_init();
    int i;
    for (i = 0; i < n; i++) h = fnv_unit(h, (uint32_t)nw_get(base + i));
    return h;
}

/* ---------------------------------------------------------------- layout */

static void layout_init(void)
{
    int i, cur = LOWPAD;
    for (i = 0; i < NREG; i++) {
        rpad[i] = cur;
        cur += PAD;
        rbase[i] = cur;
        rsegoff[i] = (i == R_ADAPTOR) ? ADAPTOR_SEG_OFFSET : SEG_OFFSET;
        cur += rsize[i];
    }
    nw_top = cur + PAD;
}

static int segbase(int r) { return rbase[r] - rsegoff[r]; }

/* THE address primitive class A needs.  The wrap is taken against the SEGMENT
 * ORIGIN, not the buffer base.  Allocation size cannot do this. */
static int seg_index(int r, int off) { return segbase(r) + (off & 0xFFFF); }

static int region_at(int nw);
static int region_at(int nw)
{
    int i;
    for (i = 0; i < NREG; i++)
        if (nw >= rbase[i] && nw < rbase[i] + rsize[i]) return i;
    return -1;
}

/* ------------------------------------------------------ pads: 11, 22 zones
 *
 * The 16 units between two blocks ARE the upper block's far-heap header in
 * DOS, and offset == 4 means the upper block's header occupies the four bytes
 * immediately below its base -- exactly the bytes a wrap or a negative index
 * reaches.  So the gap splits by OWNERSHIP:
 *
 *   TAIL(k)  = gap + 0..+7    owned by region k      guard    PGUARD
 *   SUB(k+1) = gap + 8..+15   owned by region k+1    allowance PALLOW
 *              SUB(k+1)+4..+7 is region k+1's segment offsets 0..3
 */

#define NPAD 11
#define NZONE 22

static int padbase[NPAD];

typedef struct { int base, len, owner, role; } Zone;   /* role 0 TAIL, 1 SUB */
static Zone zones[NZONE];
static int nzones;

static void zones_init(void)
{
    int i, j, n = 0;
    padbase[0] = 0;
    for (i = 0; i < NREG; i++) padbase[i + 1] = rpad[i];
    padbase[NREG + 1] = nw_top - PAD;

    for (i = 0; i < NPAD; i++) {
        int tail_owner = -1, sub_owner = -1;
        for (j = 0; j < NREG; j++) {
            if (rbase[j] + rsize[j] == padbase[i]) tail_owner = j;
            if (rbase[j] == padbase[i] + PAD) sub_owner = j;
        }
#ifdef BREAK_PADONEMAGIC
        zones[n].base = padbase[i]; zones[n].len = PAD;
        zones[n].owner = tail_owner; zones[n].role = 0; n++;
#else
        zones[n].base = padbase[i]; zones[n].len = ZONE;
        zones[n].owner = tail_owner; zones[n].role = 0; n++;
        zones[n].base = padbase[i] + ZONE; zones[n].len = ZONE;
        zones[n].owner = sub_owner; zones[n].role = 1; n++;
#endif
    }
    nzones = n;
}

static uint32_t zone_magic(const Zone *z) { return z->role ? PALLOW : PGUARD; }

static int zone_of(int off)
{
    int i;
    for (i = 0; i < nzones; i++)
        if (off >= zones[i].base && off < zones[i].base + zones[i].len) return i;
    return -1;
}

/* The allowance table.  Three entries, each with its citation.  A SUB unit
 * named here is COUNTED when it changes, not forbidden. */
static const char *allowed(const Zone *z, int off)
{
    int rel = off - z->base;
    if (z->owner < 0) return NULL;
    if (z->role == 1 && z->owner == R_P_SURFACEMAP && rel >= 2 && rel <= 7)
        return "digit_at txtr[-6..-1], NOCTIS.CPP:614-628";
    if (z->role == 0 && z->owner == R_PVFILE && rel == 0)
        return "loadpv writes 1 past pvfile_c, NOCTIS-0.CPP:2383-2391";
    if (z->role == 1 && rel >= 4 && rel <= 7)
        return "the region's own segment offsets 0..3";
    return NULL;
}

static void poison_pads(void)
{
    int i, j;
    for (i = 0; i < nzones; i++)
        for (j = 0; j < zones[i].len; j++)
            nw_unit_put(zones[i].base + j, zone_magic(&zones[i]));
}

static void zero_pads(void)
{
    int i, j;
    for (i = 0; i < nzones; i++)
        for (j = 0; j < zones[i].len; j++)
            nw_unit_put(zones[i].base + j, 0);
}

/* The two-sided check.
 *   (i)  VIOLATION  -- a unit not on the allowance list that no longer carries
 *        its zone's magic.  Named by region and offset.
 *   (ii) EXPECTATION -- an allowance-listed unit that changed.  COUNTED, not
 *        forbidden, so a build that never performs the legitimate write FAILS.
 */
static int walk_pads(int *n_expect, int *first_off, int *first_pad)
{
    int i, j, viol = 0;
    if (n_expect) *n_expect = 0;
    if (first_off) *first_off = -1;
    if (first_pad) *first_pad = 0;
    for (i = 0; i < nzones; i++) {
#ifdef BREAK_PAD9WALK
        /* walk only the nine REGION pads: the low pad and the top pad go
         * unwatched, which is what an rtab-driven walker does */
        {
            int p, seen = 0;
            for (p = 1; p <= NREG; p++)
                if (zones[i].base == padbase[p] || zones[i].base == padbase[p] + ZONE)
                    seen = 1;
            if (!seen) continue;
        }
#endif
        for (j = 0; j < zones[i].len; j++) {
            int off = zones[i].base + j;
            if (nw_unit(off) == zone_magic(&zones[i])) continue;
            if (allowed(&zones[i], off)) { if (n_expect) (*n_expect)++; continue; }
            viol++;
            if (first_off && *first_off < 0) {
                *first_off = off;
                /* which pad, 1-based */
                { int p; for (p = 0; p < NPAD; p++)
                        if (off >= padbase[p] && off < padbase[p] + PAD)
                            if (first_pad) *first_pad = p + 1; }
            }
        }
    }
    return viol;
}

/* --------------------------------------------------------------- canary v2
 *
 * v1 was 2 units per region in which BOTH fields were the literal 0xA5A5A5A5,
 * written by construction on both sides.  A clean run and a completely
 * stubbed-out mechanism produced a bit-identical dump -- including, measured,
 * the sabotage whose stated defect was "a canary check that can never fire".
 *
 * v2 is 4 units per pad and every one is read back out of NW or produced by
 * the walker:
 *   0 clean_read  NW[padbase + PROBESLOT] after poisoning
 *   1 dirty_read  the same address after storing WITNESS
 *   2 fired       pad index + 1 the walker reported
 *   3 at          NW offset of the first difference the walker reported
 *
 * WITNESS(i) is region-specific, so copy-pasting one answer fails.
 * PROBESLOT(i) sweeps the pad, so a walker that only checks the last unit
 * fails.  The +1 is not cosmetic: with slot 0 on pad 0 the `at` field is 0 in
 * both the clean and the stubbed case.
 */
/* The slot sweeps the pad, so a walker that only checks the last unit fails;
 * and it SKIPS allowance-listed units, because a probe that lands on one is
 * counted rather than flagged and the record would then say "not fired" for a
 * perfectly good walker.  Deriving the slot from the allowance table also
 * means an implementation with the WRONG allowance table probes a different
 * address and the `at` field moves -- one more thing this record can catch. */
static int probeslot(int i)
{
    int k;
    for (k = 0; k < PAD; k++) {
        int s = ((i * 7) + 1 + k) % PAD;
        int off = padbase[i] + s;
        int zi = zone_of(off);
        if (zi < 0) continue;
        if (!allowed(&zones[zi], off)) return s;
    }
    return 0;
}
static uint32_t witness(int i) { return 0xC0DE0000u | (uint32_t)i; }

static int canary_v2(uint32_t *out)
{
    int i, bad = 0;
    for (i = 0; i < NPAD; i++) {
        int off = padbase[i] + probeslot(i);
        int nexp, first, firstpad, viol;
        uint32_t clean, dirty;
        poison_pads();
#ifdef BREAK_CANSTUBPOISON
        zero_pads();
#endif
        clean = nw_unit(off);
        nw_unit_put(off, witness(i));
#ifdef BREAK_CANSTUBCHECK
        viol = 0; nexp = 0; first = -1; firstpad = 0;
        (void)viol;
#else
        viol = walk_pads(&nexp, &first, &firstpad);
        (void)viol; (void)nexp;
#endif
        dirty = nw_unit(off);
#ifdef BREAK_CANCONSTACTUAL
        /* v1's actual defect, transplanted: the "actual" field is written by
         * CONSTRUCTION rather than read back out of NW */
        { int zi = zone_of(off); dirty = (zi >= 0) ? zone_magic(&zones[zi]) : PGUARD; }
#endif
        out[4 * i + 0] = clean;
        out[4 * i + 1] = dirty;
        out[4 * i + 2] = (uint32_t)((first == off) ? firstpad : 0);
        out[4 * i + 3] = (uint32_t)(first < 0 ? 0 : first);
        if (out[4 * i + 2] == 0) bad++;
    }
    zero_pads();
    return bad;
}

/* ------------------------------------------------------------- Borland LCG */

static uint32_t lcg_state;
static void lcg_srand(unsigned s) { lcg_state = s & 0xFFFFu; }
static int lcg_rand(void)
{
    lcg_state = lcg_state * 0x015A4E35u + 1u;
    return (int)((lcg_state >> 16) & 0x7FFF);
}

/* ---------------------------------------------------------------- palette */

static unsigned char range8088[64 * 3];
static unsigned char pal6[768];      /* tmppal          (unsigned char) */
static unsigned char curpal6[768];   /* what the DAC holds */
static unsigned char srfpal6[768];   /* surface_palette (char, read unsigned) */
static unsigned char retpal6[768];   /* return_palette  */
/* retpal6 and region_at are part of the model's surface, referenced by the
 * self-test below and by the KSELF fields; keep them addressable. */
static int upload_lo = -1, upload_hi = -1;

#define MAXUP 32
static int up_a[MAXUP], up_b[MAXUP], n_up;

#define MAXMARK 16
static uint32_t mk_pal[MAXMARK], mk_cur[MAXMARK];
static int n_mark;

static uint32_t fnv_buf(const unsigned char *b, int n)
{
    uint32_t h = fnv_init();
    int i;
    for (i = 0; i < n; i++) h = fnv_unit(h, (uint32_t)b[i]);
    return h;
}

static void pal_mark(void)
{
    if (n_mark >= MAXMARK) return;
    mk_pal[n_mark] = fnv_buf(pal6, 768);
    mk_cur[n_mark] = fnv_buf(curpal6, 768);
    n_mark++;
}

static void range8088_init(void)
{
    int i;
    for (i = 0; i < 64; i++) {
        range8088[3 * i + 0] = (unsigned char)i;
        range8088[3 * i + 1] = (unsigned char)i;
        range8088[3 * i + 2] = (unsigned char)i;
    }
}

/* `char filtro_rosso` is SIGNED under Borland's default.  A caller that passes
 * 200 does not get 200; it gets -56.  Pinned scenario step 7 constructs
 * exactly that. */
static int schar(int f) { return (int)(signed char)(f & 0xFF); }

/* The DOS-16 filter.  `unsigned temp` is 16 bits under Borland; `temp *= f`
 * converts a signed char to unsigned and multiplies mod 65536; `temp /= 63` is
 * an UNSIGNED divide.  Since |v*f| <= 255*128 = 32640 < 65536, every negative
 * product lands in [32896,65535], divides to at least 522, and CLAMPS to 63 --
 * so a 32-bit `unsigned` gives the same answer, which is what makes this file
 * and fb_pal.py comparable at all.  BREAK_PYFILT is the floor-division form
 * fb_pal.py used to carry; it is wrong for every negative filter. */
static int filter_one(int v, int f)
{
#ifdef BREAK_DIV64
    int div = 64;
#else
    int div = 63;
#endif
    long temp;
#ifdef BREAK_PYFILT
    {
        long p = (long)v * (long)f;
        temp = (p >= 0) ? p / div : -(((-p) + div - 1) / div);   /* floor */
    }
#else
    temp = (long)(((unsigned)((int)v * (int)f)) & 0xFFFFu) / (unsigned)div;
#endif
#ifndef BREAK_NOCLAMP
    if (temp > 63) temp = 63;
#endif
    return (int)(temp & 0xFF);
}

/* NOCTIS-0.CPP:179-241.  src == NULL means the self-copy case
 * `tavola_colori(tmppal + 3*first, first, n, ...)`: source aliases
 * destination, the copy is a no-op, the filter runs in place.
 *
 * The DESTINATION is always tmppal, whatever the first argument says -- that
 * argument is the SOURCE (NOCTIS-0.CPP:186).  Do NOT "fix" this symmetrically
 * with shade's destination parameter. */
static void tavola_colori(const unsigned char *src, unsigned first, unsigned n,
                          int fr_in, int fg_in, int fb_in)
{
    unsigned c, cc = 0, n3 = n * 3, c0 = first * 3;
    int f[3];
    f[0] = schar(fr_in); f[1] = schar(fg_in); f[2] = schar(fb_in);

    if (src) {
        c = c0;
        while (cc < n3) pal6[c++] = src[cc++];
    }
#ifdef BREAK_NOSELF
    else {
        for (c = c0; c < c0 + n3; c++) pal6[c] = 0;
    }
#endif

    c = c0;
    while (c < c0 + n3) {
        int k;
        for (k = 0; k < 3; k++) { pal6[c] = (unsigned char)filter_one(pal6[c], f[k]); c++; }
    }

    /* the asm tail: mov cx, first*3; add cx, n*3; mov al,0; out 0x3c8,al
     * -- the upload ALWAYS starts at colour zero. */
#ifdef BREAK_UPLOADFIRST
    upload_lo = (int)c0;
#else
    upload_lo = 0;
#endif
    upload_hi = (int)(c0 + n3);
    for (c = (unsigned)upload_lo; c < (unsigned)upload_hi; c++) curpal6[c] = pal6[c];
    if (n_up < MAXUP) { up_a[n_up] = upload_lo; up_b[n_up] = upload_hi; n_up++; }
}

/* `tavola_colori(surface_palette, first, n, w, w, w)` -- the shape 14 of
 * shade's callers set up.  The whole point of surface_palette is that the
 * SOURCE is the unfiltered original, so two successive fades do not compound.
 * BREAK_SELFSOURCE reproduces the compounding. */
static void fade_from(const unsigned char *srcbuf, unsigned first, unsigned n,
                      int fr, int fg, int fb)
{
#ifdef BREAK_SELFSOURCE
    (void)srcbuf;
    tavola_colori(NULL, first, n, fr, fg, fb);
#else
    tavola_colori(srcbuf + 3 * first, first, n, fr, fg, fb);
#endif
}

/* NOCTIS-0.CPP:1151-1200.  All accumulators are `float`.  The store to
 * palette_buffer[] is a C float->unsigned char conversion, i.e. TRUNCATION
 * toward zero -- lino's `=,` rounds to nearest, which is why this is a trap. */
static unsigned char shade_place(float v)
{
    if (v >= 0 && v < 64) {
#ifdef BREAK_ROUNDSHADE
        return (unsigned char)(int)(v + 0.5f);
#else
        return (unsigned char)(int)v;
#endif
    }
    /* the original's inverted clamp; provably equivalent to a plain clamp */
    return (unsigned char)(v > 0 ? 63 : 0);
}

/* `void shade (unsigned char far *palette_buffer, ...)`.  14 of its 21 call
 * sites pass surface_palette, 7 pass tmppal.  BREAK_IGNOREDST is the Wave 5
 * defect: the destination hard-coded to tmppal, which cannot express two
 * thirds of the game's shade calls.
 *
 * Detail that must not be lost: surface_palette and return_palette are
 * declared `char` (signed) but shade takes `unsigned char far *`, so the
 * STORES are unsigned and every read is through tavola_colori's
 * `unsigned char *`.  No sign extension ever occurs. */
static void shade(unsigned char *buf, int first_color, int number_of_colors,
                  float sr, float sg, float sb, float fr, float fg, float fb)
{
    int count = number_of_colors;
    float k = (float)(1.00 / (double)number_of_colors);
    float dr = (fr - sr) * k, dg = (fg - sg) * k, db = (fb - sb) * k;
    int i = first_color * 3;
#ifdef BREAK_IGNOREDST
    buf = pal6;
#endif
    while (count) {
        buf[i + 0] = shade_place(sr);
        buf[i + 1] = shade_place(sg);
        buf[i + 2] = shade_place(sb);
        sr += dr; sg += dg; sb += db;
        i += 3; count--;
    }
}

/* The 6->8 choice, made once, here.  x4 because the game's own snapshot()
 * writes tmppal[c]*4 (NOCTIS-0.CPP:6418). */
static void lut_rebuild(void)
{
    int i;
    for (i = 0; i < 256; i++) {
        unsigned r = curpal6[3 * i + 0], g = curpal6[3 * i + 1], b = curpal6[3 * i + 2];
#ifdef BREAK_SHIFTOR
        r = (r << 2) | (r >> 4); g = (g << 2) | (g >> 4); b = (b << 2) | (b >> 4);
#else
        r *= 4; g *= 4; b *= 4;
#endif
        PAL[i] = (r << 16) | (g << 8) | b;
    }
}

/* ------------------------------------------------------------- page ops
 * NOCTIS-0.CPP:307-345.  Both walk QUADWORDS DWORDS, not 64000 bytes.
 * QUADWORDS is a VARIABLE: it steady-states at 14560 after NOCTIS.CPP:2206
 * (16000 - 1440).  At 14560 mask_pixels' DI runs 2884..61123, under 65536, so
 * class-A site A3's wrap is UNREACHABLE. */
#define QW_DECLARED 16000
#define QW_STEADY   14560
static int QUADWORDS = QW_DECLARED;

static void pclear(int base, int pattern)
{
    int i, n = QUADWORDS * 4;
#ifdef BREAK_QUADWORDS
    n = 64000;
#endif
    for (i = 0; i < n; i++) nw_put(base + i, pattern);
}

static void pcopy(int dest, int sorg)
{
    int i, n = QUADWORDS * 4;
#ifdef BREAK_QUADWORDS
    n = 64000;
#endif
    for (i = 0; i < n; i++) nw_put(dest + i, nw_get(sorg + i));
}

static void areaclear(int base, int x, int y, int l, int a, int color)
{
    int j, i;
    for (j = 0; j < a; j++)
        for (i = 0; i < l; i++)
            nw_put(base + 320 * (y + j) + x + i, color);
}

/* ------------------------------------------------------------ present path */
static void present_expand(void)
{
    int i;
    int src = rbase[R_ADAPTOR];
    for (i = 0; i < 64000; i += 4) {
        FB[i + 0] = PAL[nw_get(src + i + 0)];
        FB[i + 1] = PAL[nw_get(src + i + 1)];
        FB[i + 2] = PAL[nw_get(src + i + 2)];
        FB[i + 3] = PAL[nw_get(src + i + 3)];
    }
}

/* ================================================================= class A
 *
 * The mask goes WHERE THE DOS CODE TRUNCATES, not at the final address:
 *     ((py+px) mod 65536) >> 1   !=   ((py+px) >> 1) mod 65536
 * so spot's error on a wrap is 65536 and cirrus' is 32768.  A single "mask the
 * final index" helper would silently halve cirrus' error and still be wrong.
 */

enum { SITE_SPOT = 1, SITE_CIRRUS = 2, SITE_CRATER = 3, SITE_ALIAS8 = 4, NSITE = 5 };
static long site_calls[NSITE], site_wraps[NSITE];
static uint32_t site_mfnv[NSITE], site_nfnv[NSITE];
static int site_contain_fail;

static void site_init(void)
{
    int i;
    for (i = 0; i < NSITE; i++) {
        site_calls[i] = site_wraps[i] = 0;
        site_mfnv[i] = site_nfnv[i] = fnv_init();
    }
    site_contain_fail = 0;
}

/* The containment assertion the debug build carries: a masked address must lie
 * in [base(B), base(B)+size(B)) or in B's own SUB zone. */
static int contained(int r, int nw)
{
    int zi;
    if (nw >= rbase[r] && nw < rbase[r] + rsize[r]) return 1;
    zi = zone_of(nw);
    return (zi >= 0 && zones[zi].owner == r && zones[zi].role == 1);
}

static int site_note(int site, int r, int masked, int naive)
{
    site_calls[site]++;
    if (masked != naive) site_wraps[site]++;
    site_mfnv[site] = fnv_unit(site_mfnv[site], (uint32_t)masked);
    site_nfnv[site] = fnv_unit(site_nfnv[site], (uint32_t)naive);
    if (!contained(r, masked)) site_contain_fail++;
    return masked;
}

/* NOCTIS-0.CPP:4485.  les di,p_background / add di,py / add di,px -- DI is
 * 16 bits and already holds the pointer's own offset 4. */
static int spot_index(int px, int py)
{
    int naive = segbase(R_P_BACKGROUND) + SEG_OFFSET + py + px;
#ifdef BREAK_MASKSPOT
    int masked = naive;
#else
    int masked = seg_index(R_P_BACKGROUND, SEG_OFFSET + py + px);
#endif
    return site_note(SITE_SPOT, R_P_BACKGROUND, masked, naive);
}

/* NOCTIS-0.CPP:4715.  mov bx,py / add bx,px / shr bx,1 / es:[bx+di] -- the
 * truncation is on (py+px) BEFORE the shift; the offset is added after. */
static int cirrus_index(int px, int py)
{
    int base = segbase(R_OBJECTSCHART);
    int naive = base + SEG_OFFSET + ((py + px) >> 1);
#if defined(BREAK_MASKCIRRUSADDR)
    int masked = base + (((SEG_OFFSET + ((py + px) >> 1))) & 0xFFFF);
#elif defined(BREAK_MASKCIRRUS)
    int masked = naive;
#else
    int masked = base + SEG_OFFSET + (((py + px) & 0xFFFF) >> 1);
#endif
    return site_note(SITE_CIRRUS, R_OBJECTSCHART, masked, naive);
}

/* alias 8.  TDPOLYGS.H:2684 -- `les ax, adapted` then `mov es:[0xFA00], al`.
 * ES is the SEGMENT of adapted and the pointer's own offset is discarded, so
 * this is the SAME primitive with a constant index, not a special case. */
#define ALIAS8_SEGOFF 0xFA00
static int alias8_index(void)
{
    int naive = rbase[R_ADAPTED] + ALIAS8_SEGOFF;
    int masked = seg_index(R_ADAPTED, ALIAS8_SEGOFF);
    return site_note(SITE_ALIAS8, R_ADAPTED, masked, naive);
}

/* ------------------------------------------------------------ digit_at
 * NOCTIS.CPP:604-628.  txtr is based at p_surfacemap and the loop's first
 * iteration writes txtr[-6] and txtr[-5], i.e. BELOW the buffer -- which lands
 * in p_surfacemap's own SUB zone, on the allowance list.  niv-lr "fixed" this
 * by starting the loop at n = 1, silently dropping the top scanline of every
 * glyph AND the whole six-unit underflow signature. */
static uint32_t digimap2[DM2_BYTES / 4];
static const uint32_t pp32[32] = {
    0x00000001u, 0x00000002u, 0x00000004u, 0x00000008u,
    0x00000010u, 0x00000020u, 0x00000040u, 0x00000080u,
    0x00000100u, 0x00000200u, 0x00000400u, 0x00000800u,
    0x00001000u, 0x00002000u, 0x00004000u, 0x00008000u,
    0x00010000u, 0x00020000u, 0x00040000u, 0x00080000u,
    0x00100000u, 0x00200000u, 0x00400000u, 0x00800000u,
    0x01000000u, 0x02000000u, 0x04000000u, 0x08000000u,
    0x10000000u, 0x20000000u, 0x40000000u, 0x80000000u
};

static int load_digimap2(const char *supports_nct)
{
    FILE *f = fopen(supports_nct, "rb");
    long size;
    if (!f) return 0;
    fseek(f, 0, SEEK_END);
    size = ftell(f);
    fseek(f, size + OFF_DIGIMAP2, SEEK_SET);
    if (fread(digimap2, 1, DM2_BYTES, f) != DM2_BYTES) { fclose(f); return 0; }
    fclose(f);
    return 1;
}

static void digit_at(int digit, int color, int shader)
{
    int txtr = rbase[R_P_SURFACEMAP];
    int pixel_color = color % 64;
    int n, m, d, i;
    if (!(digit > 32 && digit <= 96)) return;
    d = (digit - 32) * 36;
#ifdef BREAK_DIGITN1
    for (n = 1; n < 36; n++) {
#else
    for (n = 0; n < 36; n++) {
#endif
        i = 256 * n - 5;
        nw_put(txtr + i - 1, 0);              /* txtr[-6] when n == 0 */
        for (m = 0; m < 32; m++) {
            if (digimap2[n + d] & pp32[m]) nw_put(txtr + i, pixel_color);
            else                           nw_put(txtr + i, 0);
            i++;
        }
        if (shader) pixel_color--;
    }
    nw_put(txtr + 256 * 36 - 6, 0);
}

/* ------------------------------------------------------------ texel address
 * TDPOLYGS.H:2817-2821.  texel = ((V>>8)&0xFF)*256 + ((U>>8)&0xFF), assembled
 * in the 16-bit BX, so it is confined to 0..65535 by construction. */
static int texel_addr(int u, int v) { return (((v >> 8) & 0xFF) * 256) + ((u >> 8) & 0xFF); }

/* ---------------------------------------------------------------- FBDUMP v2 */

#define FBD_MAGIC 0x46424431u
#define FBD_VERSION 2
enum { K_INDEXPAGE = 1, K_PALETTE6 = 2, K_LUT = 3, K_TICKLOG = 4, K_LAYOUT = 5,
       K_CANARY = 6, K_KSELF = 7, K_KFRM = 8, K_ZONES = 9, K_WRAPCOUNT = 10,
       K_SERVOLOG = 11 };
enum { T_ADAPTED = 1, T_ADAPTOR = 2, T_GLYPH = 3, T_PAL6 = 4, T_CURPAL6 = 5,
       T_LUT = 6, T_LAYOUT = 7, T_CANARY = 8, T_ZONES = 9, T_TICKLOG = 10,
       T_SERVOLOG = 11, T_WRAPCOUNT = 12, T_SELFCHECK = 13, T_FRAMECOST = 14 };

static void put_u32le(FILE *f, uint32_t v)
{
    fputc((int)(v & 255), f); fputc((int)((v >> 8) & 255), f);
    fputc((int)((v >> 16) & 255), f); fputc((int)((v >> 24) & 255), f);
}

static int fbdump(const char *path, int kind, const uint32_t *payload, int count,
                  int width, int height, int cpms, int ticks, int tag)
{
    FILE *f = fopen(path, "wb");
    int i;
    if (!f) { fprintf(stderr, "cannot write %s\n", path); return 0; }
    put_u32le(f, FBD_MAGIC); put_u32le(f, FBD_VERSION); put_u32le(f, (uint32_t)kind);
    put_u32le(f, (uint32_t)width); put_u32le(f, (uint32_t)height);
    put_u32le(f, (uint32_t)count); put_u32le(f, (uint32_t)cpms); put_u32le(f, (uint32_t)ticks);
    put_u32le(f, (uint32_t)tag);
    for (i = 0; i < 7; i++) put_u32le(f, 0);
    for (i = 0; i < count; i++) put_u32le(f, payload[i]);
    fclose(f);
    return 1;
}

/* ------------------------------------------------------------------ tick */
static int32_t tick_carry;
static int32_t tick_period(int32_t cpms)
{
    int32_t num = cpms * 44505 + tick_carry;
    int32_t q = num / 596591;
    tick_carry = num - q * 596591;
    return cpms * 55 - q;
}

static int tick_expired(uint32_t now, uint32_t deadline)
{
#ifdef BREAK_TICKCMP
    return now >= deadline;
#else
    return (int32_t)(now - deadline) >= 0;
#endif
}

/* ===================================================== LINOBUF 6.1 scenarios
 *
 * *** A TEST FIXTURE, NOT A CLAIM ABOUT THE GAME. ***
 *
 * Implemented from the normative text, not from fb_pal.py or fb_layout.py.
 * Every step exists to separate one implementation choice.
 */

static void scenario_surface(void)
{
    /* 1 */
    memset(pal6, 0, sizeof pal6);
    memset(curpal6, 0, sizeof curpal6);
    memset(srfpal6, 0, sizeof srfpal6);
    n_up = 0; n_mark = 0;
    range8088_init();
    pal_mark();
    /* 2 -- filter arithmetic */
    tavola_colori(range8088, 0, 64, 16, 32, 63);
    pal_mark();
    /* 3 -- chop vs round separates at the FIRST entry: delta = 63/64 exactly,
     *      so entry 1 is 0.984375 -> chop 0, round 1.  Uploads nothing. */
    shade(pal6, 0, 64, 0.0f, 0.0f, 0.0f, 63.0f, 63.0f, 63.0f);
    pal_mark();
    /* 4 -- the self-copy */
    tavola_colori(NULL, 192, 64, 50, 50, 50);
    pal_mark();
    /* 5 -- upload-from-zero */
    tavola_colori(range8088, 64, 64, 60, 55, 50);
    pal_mark();
    /* 6 -- the clamp's saturation value */
    shade(pal6, 160, 16, 19.50f, 24.75f, 33.00f, 66.25f, -2.50f, 48.125f);
    pal_mark();
    /* 7 -- trap 2: filter 200 is a signed char, -56 */
    tavola_colori(NULL, 0, 256, 200, 64, 64);
    pal_mark();
    /* 8 -- v*4 */
    lut_rebuild();
    pal_mark();
}

/* The NOCTIS-1.CPP:3050-3086 ladder, with its float arguments pinned.  Nine
 * rungs, every one into surface_palette. */
typedef struct { int first, n; float sr, sg, sb, fr, fg, fb; } Rung;
static const Rung LADDER[9] = {
    { 64, 64,  0, 0, 0,  60, 62, 64 },
    {  0, 44,  0, 0, 0,  40, 30, 20 },
    { 44, 20, 40, 30, 20, 55, 48, 41 },
    {128, 10,  0, 0, 0,  40, 30, 20 },
    {138, 44, 40, 30, 20, 22, 33, 44 },
    {182, 10, 22, 33, 44, 55, 48, 41 },
    {192, 10,  0, 0, 0,  40, 30, 20 },
    {202, 44, 40, 30, 20, 12, 50, 18 },
    {246, 10, 12, 50, 18, 55, 48, 41 },
};

/* SH-COMPOUND.  The first probe in this project that touches srfpal6 at all,
 * and the one that tests what the buffer is FOR.  Returns pal6's digest and
 * fills `want` with filter(ladder, 24) computed directly. */
static uint32_t scenario_compound(uint32_t *want_fnv, int *srf_nonzero)
{
    unsigned char snapshot[768];
    int i;
    uint32_t h;
    memset(pal6, 0, sizeof pal6);
    memset(curpal6, 0, sizeof curpal6);
    memset(srfpal6, 0, sizeof srfpal6);
    for (i = 0; i < 9; i++)
        shade(srfpal6, LADDER[i].first, LADDER[i].n,
              LADDER[i].sr, LADDER[i].sg, LADDER[i].sb,
              LADDER[i].fr, LADDER[i].fg, LADDER[i].fb);
    memcpy(snapshot, srfpal6, 768);
    *srf_nonzero = 0;
    for (i = 0; i < 768; i++) if (snapshot[i]) (*srf_nonzero)++;
    fade_from(srfpal6, 0, 256, 48, 48, 48);
    fade_from(srfpal6, 0, 256, 24, 24, 24);
    h = fnv_init();
    for (i = 0; i < 768; i++) h = fnv_unit(h, (uint32_t)filter_one(snapshot[i], 24));
    *want_fnv = h;
    return fnv_buf(pal6, 768);
}

/* The class-A wrap battery, on its real destinations.  Deterministic corpus;
 * the escape SHAPE is the one fb_wrap.py measures on the real generator --
 * px just below zero (stored to an `unsigned`, so 65536-k) with py = 360*row. */
static void wrap_battery(void)
{
    int row, k, px, py;
    for (row = 0; row < 180; row += 12) {
        py = (360 * row) & 0xFFFF;
        for (k = 1; k <= 32; k++) {
            px = (-k) & 0xFFFF;
            nw_put(spot_index(px, py), 0x3E);
        }
        for (k = 1; k <= 16; k++) {
            px = (-k) & 0xFFFF;
            nw_put(cirrus_index(px, py), 0x1F);
        }
    }
    for (row = 0; row < 180; row += 12) {
        static const int ctrl[4] = { 0, 1, 179, 359 };
        int j;
        py = (360 * row) & 0xFFFF;
        for (j = 0; j < 4; j++) {
            nw_put(spot_index(ctrl[j], py), 0x3E);
            nw_put(cirrus_index(ctrl[j], py), 0x1F);
        }
    }
}

static void scenario_page(void)
{
    int adapted = rbase[R_ADAPTED], adaptor = rbase[R_ADAPTOR];
    int globes = rbase[R_N_GLOBES_MAP], surf = rbase[R_P_SURFACEMAP];
    int i, u, v, texel, a8;

    /* 1 -- the RELEASE pad state.  5 of step 4's 32000 texels land in a pad,
     *      so poison left in place changes the page. */
    zero_pads();

    /* 2 -- QUADWORDS.  The clear pattern is deliberately NON-ZERO so the
     *      extent of the clear is observable at all. */
    QUADWORDS = QW_DECLARED;
    pclear(adaptor, 0);
    QUADWORDS = QW_STEADY;
    pclear(adapted, 7);

    /* 3 -- seed */
    lcg_srand(1996);
    for (i = 0; i < 32768; i++) nw_put(globes + i, lcg_rand() & 63);
    for (i = 0; i < 4096; i++) nw_put(rbase[R_S_BACKGROUND] + i, 128 + (lcg_rand() & 63));

    /* 4 -- sea texture, class C: texels 32768..65535 read PAST n_globes_map */
    for (i = 0; i < 32000; i++) {
        u = (i * 517) & 0xFFFF;
        v = (i * 1031) & 0xFFFF;
        texel = texel_addr(u, v);
        nw_put(adapted + i, nw_get(globes + texel));
    }

    /* 5 -- the raster loop, from n = 0 */
    digit_at('A', 64 + 40, 1);
    for (i = 0; i < 9216; i++) nw_put(adapted + 32000 + i, nw_get(surf + 256 * 0 - 5 + i));

    /* 6 -- alias 8, through seg_index.  63996, not 64000. */
    a8 = alias8_index();
#ifdef BREAK_TINTA64000
    nw_put(adapted + 64000, 0x37); nw_put(adapted + 64001, 0x5B);
#else
    nw_put(a8, 0x37); nw_put(a8 + 1, 0x5B);
#endif

    /* 7 -- the class-A wrap battery */
    wrap_battery();

    /* 8 -- present.  CORRECTION 5 to the draft fixture: the page flip must come
     *      BEFORE the HUD band, or the band is overwritten by the copy and the
     *      adaptor record is bit-identical to the adapted one -- which it was,
     *      measured, so step 9 was grading nothing. */
    QUADWORDS = QW_DECLARED;
    pcopy(adaptor, adapted);

    /* 9 -- vanilla's areaclear writes the VISIBLE page, after the flip */
    areaclear(adaptor, 2, 191, 316, 7, 64 + 63);
}

/* --------------------------------------------------------------- selftest */

static int failures;
static void req(int cond, const char *fmt, ...)
{
    va_list ap;
    printf(cond ? "  PASS  " : "  FAIL  ");
    va_start(ap, fmt); vprintf(fmt, ap); va_end(ap);
    printf("\n");
    if (!cond) failures++;
}

int main(int argc, char **argv)
{
    const char *outdir = (argc > 1) ? argv[1] : ".";
    const char *supports = (argc > 2) ? argv[2]
        : "C:\\programmieren\\noctis\\niv-plus\\data\\SUPPORTS.NCT";
    char path[1024];
    int i, j;
    int probe_viol = 0, probe_exp = 0, probe_first = -1, probe_pad = 0;
    uint32_t cmp_got = 0, cmp_want = 0;
    int srf_nonzero = 0;
    uint32_t canbad = 0;

    printf("fb_ref.c -- C reference for the Wave 5-corrective buffer model\n");
    printf("build flags:");
#define SHOW(x) do { printf(" " #x); } while (0)
#ifdef BREAK_SHIFTOR
    SHOW(BREAK_SHIFTOR);
#endif
#ifdef BREAK_UPLOADFIRST
    SHOW(BREAK_UPLOADFIRST);
#endif
#ifdef BREAK_ROUNDSHADE
    SHOW(BREAK_ROUNDSHADE);
#endif
#ifdef BREAK_NOCLAMP
    SHOW(BREAK_NOCLAMP);
#endif
#ifdef BREAK_NOSELF
    SHOW(BREAK_NOSELF);
#endif
#ifdef BREAK_DIGITN1
    SHOW(BREAK_DIGITN1);
#endif
#ifdef BREAK_TINTA64000
    SHOW(BREAK_TINTA64000);
#endif
#ifdef BREAK_PACK4
    SHOW(BREAK_PACK4);
#endif
#ifdef BREAK_QUADWORDS
    SHOW(BREAK_QUADWORDS);
#endif
#ifdef BREAK_TICKCMP
    SHOW(BREAK_TICKCMP);
#endif
#ifdef BREAK_SHRINKADAPTOR
    SHOW(BREAK_SHRINKADAPTOR);
#endif
#ifdef BREAK_DIV64
    SHOW(BREAK_DIV64);
#endif
#ifdef BREAK_PYFILT
    SHOW(BREAK_PYFILT);
#endif
#ifdef BREAK_IGNOREDST
    SHOW(BREAK_IGNOREDST);
#endif
#ifdef BREAK_SELFSOURCE
    SHOW(BREAK_SELFSOURCE);
#endif
#ifdef BREAK_MASKSPOT
    SHOW(BREAK_MASKSPOT);
#endif
#ifdef BREAK_MASKCIRRUS
    SHOW(BREAK_MASKCIRRUS);
#endif
#ifdef BREAK_MASKCIRRUSADDR
    SHOW(BREAK_MASKCIRRUSADDR);
#endif
#ifdef BREAK_SEGADDRBASE
    SHOW(BREAK_SEGADDRBASE);
#endif
#ifdef BREAK_PADONEMAGIC
    SHOW(BREAK_PADONEMAGIC);
#endif
#ifdef BREAK_PAD9WALK
    SHOW(BREAK_PAD9WALK);
#endif
#ifdef BREAK_CANSTUBCHECK
    SHOW(BREAK_CANSTUBCHECK);
#endif
#ifdef BREAK_CANSTUBPOISON
    SHOW(BREAK_CANSTUBPOISON);
#endif
#ifdef BREAK_CANCONSTACTUAL
    SHOW(BREAK_CANCONSTACTUAL);
#endif
#ifdef BREAK_LAYOUTEND
    SHOW(BREAK_LAYOUTEND);
#endif
#ifdef BREAK_OVERRUN
    printf(" BREAK_OVERRUN=%d", BREAK_OVERRUN);
#endif
    printf(" (none listed = clean)\n\n");

    layout_init();
    zones_init();
    site_init();
#ifdef BREAK_PACK4
    NWSTORE = calloc((size_t)(nw_top / 4 + 2), sizeof(uint32_t));
#else
    NW = calloc((size_t)nw_top, sizeof(uint32_t));
#endif
    FB = calloc(64000, sizeof(uint32_t));
    range8088_init();

    printf("layout (transcribed from NOCTIS-D.H + NOCTIS.CPP farmalloc order):\n");
    for (i = 0; i < NREG; i++)
        printf("  %d %-14s base %6d size %6d end %6d pad %6d segbase %6d window end %6d\n",
               i, rname[i], rbase[i], rsize[i], rbase[i] + rsize[i], rpad[i],
               segbase(i), segbase(i) + WRAP16);
    printf("  NW top %d units = %d bytes;  %d pads, %d zones\n\n",
           nw_top, nw_top * 4, NPAD, nzones);

    printf("byte semantics:\n");
    nw_put(1000, 300); req(nw_get(1000) == 44, "B1 store 300 -> 44 (got %d)", nw_get(1000));
    nw_put(1000, -1);  req(nw_get(1000) == 255, "B2 store -1 -> 255 (got %d)", nw_get(1000));
    nw_put(1000, 0xC0); req(nw_get_signed(1000) == -64, "B3 sign extend 0xC0 -> -64 (got %d)", nw_get_signed(1000));
    nw_put(1000, 0x3F); req(nw_get_signed(1000) == 63, "B3 sign extend 0x3F -> +63 (got %d)", nw_get_signed(1000));
    {
        int okq = 1;
        for (i = 0; i < 256; i++) {
            nw_put(1001, i);
            for (j = 0; j < 4; j++) if (quad_get(1001, j) != ((i >> (2 * j)) & 3)) okq = 0;
        }
        req(okq, "B4 quadrant bitfield get agrees with the byte for all 256 values");
        nw_put(1001, 0);
        quad_set(1001, 0, 3); quad_set(1001, 3, 2);
        req(nw_get(1001) == 0x83, "B4 quadrant set -> 0x83 (got 0x%02X)", nw_get(1001));
    }
    {
        int okid = 1;
        for (i = 0; i < 16; i++) { nw_put(2000 + i, 0x10 + i); }
        for (i = 0; i < 16; i++) if (nw_unit(2000 + i) != (uint32_t)(0x10 + i)) okid = 0;
        req(okid, "B5 one byte per unit: raw unit at offset k equals the byte at k");
    }
    printf("\n");

    printf("class A -- the 16-bit index wrap:\n");
    {
        int py = 61200, px = (-1) & 0xFFFF;
        int m, n;
        site_init();
        m = spot_index(px, py);
        n = segbase(R_P_BACKGROUND) + SEG_OFFSET + py + px;
        req(n - m == 65536 || site_wraps[SITE_SPOT] == 0,
            "A1 spot py=%d px=%d: masked NW %d, naive NW %d, delta %d", py, px, m, n, n - m);
        m = cirrus_index(px, py);
        n = segbase(R_OBJECTSCHART) + SEG_OFFSET + ((py + px) >> 1);
        req(n - m == 32768 || site_wraps[SITE_CIRRUS] == 0,
            "A1 cirrus, SAME inputs: masked NW %d, naive NW %d, delta %d -- half of "
            "spot's, because of the `shr bx,1` between the truncation and the address",
            m, n, n - m);
        {
            int rn = region_at(n), rm = region_at(m);
            req(rn != R_OBJECTSCHART,
                "A1 the UNMASKED cirrus address lands on %s, past the end of its own "
                "buffer; the masked one lands on %s",
                rn < 0 ? "a pad" : rname[rn], rm < 0 ? "a pad" : rname[rm]);
        }
        /* the four addresses that fold onto segment offsets 0..3 */
        {
            int lowok = 1, k;
            for (k = 1; k <= 4; k++) {
                int mm = spot_index((-k) & 0xFFFF, 0);
                int zi = zone_of(mm);
                if (mm != segbase(R_P_BACKGROUND) + (SEG_OFFSET - k)) lowok = 0;
                if (zi < 0 || zones[zi].owner != R_P_BACKGROUND || zones[zi].role != 1) lowok = 0;
            }
            req(lowok, "A2 py=0, px=65536-k for k=1..4 folds onto segment offsets 3,2,1,0 "
                       "-- NW %d..%d, p_background's own SUB zone, which is where DOS put "
                       "the far-heap header", segbase(R_P_BACKGROUND),
                segbase(R_P_BACKGROUND) + 3);
        }
        req(site_contain_fail == 0,
            "A3 containment: every masked address is inside its own region or its own "
            "SUB zone (%d failures)", site_contain_fail);
        /* alias 8 */
        {
            int a8 = alias8_index();
            int idx = a8 - rbase[R_ADAPTED];
            req(idx == 63996 && idx / 320 == 199 && idx % 320 == 316,
                "A4 alias 8: es:[0x%04X] with segoff %d is adapted[%d] = row %d col %d "
                "(niv-lr relocated it to %d)", ALIAS8_SEGOFF, rsegoff[R_ADAPTED], idx,
                idx / 320, idx % 320, ALIAS8_SEGOFF);
        }
        /* A7: snapshot()'s row loop, NOCTIS-0.CPP:6423, with `unsigned ptr` */
        {
            unsigned long p = 63680; int n2 = 0;
            while (p < 64000 && n2 < 1000) { n2++; p = (p - 320) & 0xFFFFFFFFul; }
            req(n2 == 200, "A5 A7's `ptr` is a TYPING requirement, not a mask: unsigned, "
                           "the loop runs %d rows and exits (0-320 = %lu >= 64000)",
                n2, (unsigned long)((0ul - 320ul) & 0xFFFFFFFFul));
        }
        site_init();
    }
    printf("\n");

    printf("pads -- 11 pads, 22 zones, two magics, a two-sided check:\n");
    {
        int nexp, first, fpad, viol;
        req(nzones == NZONE, "P1 %d zones (want %d)", nzones, NZONE);
        poison_pads();
        viol = walk_pads(&nexp, &first, &fpad);
        req(viol == 0 && nexp == 0, "P1 a freshly poisoned workspace reports 0 violations "
                                    "and 0 expectations (got %d, %d)", viol, nexp);
        /* the EXPECTATION probe: one glyph, nothing else */
        if (!load_digimap2(supports)) {
            printf("  FAIL  P2 could not read digimap2 from %s\n", supports);
            failures++;
        } else {
            poison_pads();
            digit_at('A', 64 + 40, 1);
            probe_viol = walk_pads(&probe_exp, &probe_first, &probe_pad);
            req(probe_viol == 0 && probe_exp == 6,
                "P2 one digit_at glyph: %d violations, %d expectations.  The EXACT count "
                "is asserted, so a build that never performs the legitimate write FAILS "
                "-- which BREAK_DIGITN1 does (it reports 0).", probe_viol, probe_exp);
        }
        /* the VIOLATION probe */
        poison_pads();
        nw_unit_put(rbase[R_N_GLOBES_MAP] + rsize[R_N_GLOBES_MAP], 0xDEADBEEFu);
        viol = walk_pads(&nexp, &first, &fpad);
        req(viol == 1 && first == rbase[R_N_GLOBES_MAP] + rsize[R_N_GLOBES_MAP],
            "P3 one unit past n_globes_map fires exactly one TAIL violation at NW %d "
            "(got %d violations, first at %d)",
            rbase[R_N_GLOBES_MAP] + rsize[R_N_GLOBES_MAP], viol, first);
        zero_pads();
    }
    printf("\n");

    printf("canary v2 -- 4 units per pad, none of them a literal:\n");
    {
        uint32_t can[4 * NPAD];
        int bad = canary_v2(can);
        canbad = (uint32_t)bad;
        req(bad == 0, "C1 every one of the %d pads reports its own probe fired (%d did not)",
            NPAD, bad);
        req(can[1] == witness(0) && can[2] == 1,
            "C1 pad 0: clean_read %08X, dirty_read %08X, fired %u, at %u -- the dirty "
            "read is READ BACK, not written by construction",
            can[0], can[1], can[2], can[3]);
        req(can[3] == (uint32_t)(padbase[0] + probeslot(0)) && can[3] != 0,
            "C1 the `at` field is a real NW offset (%u), and PROBESLOT's +1 keeps it "
            "non-zero on pad 0 -- without it a stubbed walker is indistinguishable",
            can[3]);
        zero_pads();
    }
    printf("\n");

    printf("tick:\n");
    {
        int32_t cpms = 9000, k;
        int64_t total = 0;
        int32_t mn = 0x7FFFFFFF, mx = 0;
        tick_carry = 0;
        for (k = 0; k < 4096; k++) {
            int32_t p = tick_period(cpms);
            total += p; if (p < mn) mn = p; if (p > mx) mx = p;
        }
        {
            int64_t want = ((int64_t)4096 * cpms * 32768000 + 596591 / 2) / 596591;
            req(total >= want - 1 && total <= want + 1,
                "T1 4096 ticks total %lld counts, exact %lld (within 1)", (long long)total, (long long)want);
        }
        req(mx - mn <= 1, "T1 period takes at most two adjacent values (%d..%d)", mn, mx);
        req(tick_expired(0x00000005u, 0xFFFFFFF0u) == 1, "T2 wrap: now=5 deadline=FFFFFFF0 is EXPIRED");
        req(tick_expired(0xFFFFFFF0u, 0x00000005u) == 0, "T2 wrap: now=FFFFFFF0 deadline=5 is NOT expired");
        req(tick_expired(0x80000000u, 0x7FFFFFFFu) == 1, "T2 sign boundary: 80000000 vs 7FFFFFFF is EXPIRED");
    }
    printf("\n");

    printf("palette -- LINOBUF 6.1 scenario \"surface\":\n");
    req(schar(200) == -56, "S1 `char` filtro 200 is -56 (got %d)", schar(200));
    req(filter_one(1, -56) == 63,
        "S1 v=1 f=-56: (1*-56) mod 65536 = 65480, /63 = 1039, clamp -> 63 (got %d)",
        filter_one(1, -56));
    {
        int wraps = 0, maxp = 0, v, f;
        for (v = 0; v < 64; v++) for (f = 0; f < 128; f++) {
            if (v * f >= 65536) wraps++;
            if (v * f > maxp) maxp = v * f;
        }
        req(wraps == 0, "S1 trap 2's 16-bit wrap is UNREACHABLE for every legal filter: "
                        "%d of 8192 (v,f) pairs wrap, max product %d < 65536", wraps, maxp);
    }
    {
        /* the destination parameter is GENERAL: 14 sites pass surface_palette,
         * 7 pass tmppal, and shade never writes return_palette in the game --
         * but the parameter must still express it. */
        memset(retpal6, 0, sizeof retpal6);
        memset(pal6, 0, sizeof pal6);
        shade(retpal6, 0, 2, 5.0f, 5.0f, 5.0f, 5.0f, 5.0f, 5.0f);
        req(retpal6[0] == 5 && retpal6[1] == 5 && pal6[0] == 0,
            "S1 shade's destination parameter is general: return_palette written "
            "(%d,%d), tmppal untouched (%d)", retpal6[0], retpal6[1], pal6[0]);
        /* and NO sign extension: srfpal6/retpal6 are `char` but shade stores
         * through `unsigned char far *` and tavola_colori reads through
         * `unsigned char *` */
        memset(srfpal6, 0, sizeof srfpal6);
        srfpal6[0] = 200;
        memset(pal6, 0, sizeof pal6);
        fade_from(srfpal6, 0, 1, 63, 63, 63);
        req(pal6[0] == 63,
            "S1 srfpal6 is read UNSIGNED: 200*63/63 = 200 -> clamp 63, not sign-extended "
            "to -56 (got %d)", pal6[0]);
    }
    scenario_surface();
    printf("  pal6[0:12]   "); for (i = 0; i < 12; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  pal6[480:492]"); for (i = 480; i < 492; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  curpal6[0:12]"); for (i = 0; i < 12; i++) printf(" %d", curpal6[i]); printf("\n");
    printf("  lut[0:4]      %08X %08X %08X %08X\n", PAL[0], PAL[1], PAL[2], PAL[3]);
    printf("  uploads      "); for (i = 0; i < n_up; i++) printf(" [%d,%d)", up_a[i], up_b[i]);
    printf("\n");

    /* SH-COMPOUND: what surface_palette is FOR */
    cmp_got = scenario_compound(&cmp_want, &srf_nonzero);
    req(srf_nonzero > 0, "S2 the ladder actually wrote surface_palette (%d nonzero of 768)",
        srf_nonzero);
    req(cmp_got == cmp_want,
        "S2 two successive fades do NOT compound: pal6 == filter(ladder, 24) exactly "
        "(fnv %08X vs %08X).  With shade's destination hard-coded to tmppal the ladder "
        "never reaches surface_palette and the fades read zeros; with a self-sourced "
        "fade they compound.", cmp_got, cmp_want);
    /* restore the surface scenario for the dumps */
    scenario_surface();
    printf("\n");

    printf("page scenario:\n");
    scenario_page();
    present_expand();
    {
        int okexp = 1;
        for (i = 0; i < 64000; i++)
            if (FB[i] != PAL[nw_get(rbase[R_ADAPTOR] + i)]) { okexp = 0; break; }
        req(okexp, "E1 expand invariant FB[i] == PAL[adaptor[i]] holds for all 64000");
    }
    req(site_wraps[SITE_SPOT] > 0 && site_wraps[SITE_CIRRUS] > 0,
        "E2 the wrap battery actually wrapped: spot %ld/%ld, cirrus %ld/%ld",
        site_wraps[SITE_SPOT], site_calls[SITE_SPOT],
        site_wraps[SITE_CIRRUS], site_calls[SITE_CIRRUS]);
    req(site_contain_fail == 0,
        "E2 and every masked address stayed contained (%d failures)", site_contain_fail);
    printf("\n");

    /* dumps */
    {
        uint32_t *pay = malloc(sizeof(uint32_t) * 64000);

        snprintf(path, sizeof path, "%s/fb-ref-layout.bin", outdir);
        for (i = 0; i < NREG; i++) {
            pay[4 * i + 0] = (uint32_t)rbase[i];
            pay[4 * i + 1] = (uint32_t)rsize[i];
#ifdef BREAK_LAYOUTEND
            pay[4 * i + 2] = (uint32_t)rpad[i];      /* the v1 ambiguity */
#else
            pay[4 * i + 2] = (uint32_t)(rbase[i] + rsize[i]);
#endif
            pay[4 * i + 3] = (uint32_t)i;
        }
        fbdump(path, K_LAYOUT, pay, 4 * NREG, 0, 0, 0, 0, T_LAYOUT);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-zones.bin", outdir);
        for (i = 0; i < nzones; i++) {
            pay[4 * i + 0] = (uint32_t)zones[i].base;
            pay[4 * i + 1] = (uint32_t)zones[i].len;
            pay[4 * i + 2] = (uint32_t)zones[i].owner;
            pay[4 * i + 3] = (uint32_t)zones[i].role;
        }
        fbdump(path, K_ZONES, pay, 4 * nzones, 0, 0, 0, 0, T_ZONES);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-pal6.bin", outdir);
        for (i = 0; i < 768; i++) pay[i] = pal6[i];
        fbdump(path, K_PALETTE6, pay, 768, 0, 0, 0, 0, T_PAL6);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-curpal6.bin", outdir);
        for (i = 0; i < 768; i++) pay[i] = curpal6[i];
        fbdump(path, K_PALETTE6, pay, 768, 0, 0, 0, 0, T_CURPAL6);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-lut.bin", outdir);
        for (i = 0; i < 256; i++) pay[i] = PAL[i];
        fbdump(path, K_LUT, pay, 256, 0, 0, 0, 0, T_LUT);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-adapted.bin", outdir);
        for (i = 0; i < 64000; i++) pay[i] = (uint32_t)nw_get(rbase[R_ADAPTED] + i);
        fbdump(path, K_INDEXPAGE, pay, 64000, 320, 200, 0, 0, T_ADAPTED);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-adaptor.bin", outdir);
        for (i = 0; i < 64000; i++) pay[i] = (uint32_t)nw_get(rbase[R_ADAPTOR] + i);
        fbdump(path, K_INDEXPAGE, pay, 64000, 320, 200, 0, 0, T_ADAPTOR);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-glyph.bin", outdir);
        for (i = 0; i < 9216; i++) pay[i] = (uint32_t)nw_get(rbase[R_P_SURFACEMAP] - 5 + i);
        fbdump(path, K_INDEXPAGE, pay, 9216, 256, 36, 0, 0, T_GLYPH);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-wrapcount.bin", outdir);
        {
            int n = 0, s;
            for (s = 1; s < NSITE; s++) {
                if (!site_calls[s]) continue;
                pay[n++] = (uint32_t)s;
                pay[n++] = (uint32_t)site_calls[s];
                pay[n++] = (uint32_t)site_wraps[s];
            }
            fbdump(path, K_WRAPCOUNT, pay, n, 0, 0, 0, 0, T_WRAPCOUNT);
        }
        printf("wrote %s\n", path);

        /* KSELF.  Field ids 1..99 are NORMATIVE and independently computable,
         * so they are GRADED; 100+ are port-local and are never graded. */
        snprintf(path, sizeof path, "%s/fb-ref-kself.bin", outdir);
        {
            int n = 0, a8 = seg_index(R_ADAPTED, ALIAS8_SEGOFF);
            int idx = a8 - rbase[R_ADAPTED];
            uint32_t glyph_nz = 0, upfnv = fnv_init(), palt = fnv_init(), curt = fnv_init();
            for (i = 0; i < 9216; i++)
                if (nw_get(rbase[R_P_SURFACEMAP] - 5 + i)) glyph_nz++;
            for (i = 0; i < n_up; i++) {
                upfnv = fnv_unit(upfnv, (uint32_t)up_a[i]);
                upfnv = fnv_unit(upfnv, (uint32_t)up_b[i]);
            }
            for (i = 0; i < n_mark; i++) {
                palt = fnv_unit(palt, mk_pal[i]);
                curt = fnv_unit(curt, mk_cur[i]);
            }
#define KF(id, val) do { pay[n++] = (uint32_t)(id); pay[n++] = (uint32_t)(val); } while (0)
            KF(1, nw_top);
            KF(2, nzones);
            KF(3, NPAD);
            KF(4, probe_viol);
            KF(5, probe_exp);
            KF(6, QW_STEADY);
            KF(7, a8);
            KF(8, idx / 320);
            KF(9, idx % 320);
            KF(10, site_mfnv[SITE_SPOT]);
            KF(11, site_nfnv[SITE_SPOT]);
            KF(12, site_mfnv[SITE_CIRRUS]);
            KF(13, site_nfnv[SITE_CIRRUS]);
            KF(14, glyph_nz);
            KF(15, curt);
            KF(16, srf_nonzero);
            KF(17, fnv_range(rbase[R_ADAPTED], 64000));
            KF(18, fnv_range(rbase[R_ADAPTOR], 64000));
            KF(19, fnv_range(rbase[R_P_SURFACEMAP] - 5, 9216));
            KF(20, canbad);
            KF(21, cmp_got);
            KF(22, palt);
            KF(23, upfnv);
            fbdump(path, K_KSELF, pay, n, 0, 0, 0, 0, T_SELFCHECK);
        }
        printf("wrote %s\n", path);

        /* CANARY v2.  A DEBUG-BUILD artifact by definition: it poisons, probes,
         * checks and restores the release state, and every graded page record
         * above was dumped BEFORE this. */
        snprintf(path, sizeof path, "%s/fb-ref-canary.bin", outdir);
        canary_v2(pay);
        fbdump(path, K_CANARY, pay, 4 * NPAD, 0, 0, 0, 0, T_CANARY);
        printf("wrote %s\n", path);
        free(pay);
    }

    printf("\nRESULT: %s  (%d failures)\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
