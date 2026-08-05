/* fb_ref.c -- Wave 5, implementer 2.  The C reference for the Noctis buffer
 * model, palette pipeline, present path and tick period.
 *
 * WRITTEN FROM THE 1996 SOURCES, NOT FROM THE LINO:
 *   NOCTIS-D.H:25-56      buffer sizes
 *   NOCTIS.CPP:2163-2171  the farmalloc order (adaptor appended, NOCTIS-0.CPP:53)
 *   NOCTIS-0.CPP:166-241  range8088, tavola_colori
 *   NOCTIS-0.CPP:1151-1200 shade
 *   NOCTIS-0.CPP:307-345  pcopy, pclear (QUADWORDS dwords, not 64000 bytes)
 *   NOCTIS-0.CPP:6418-6420 snapshot's DAC scaling, tmppal[c]*4
 *   NOCTIS.CPP:604-628    digit_at, including its txtr[-6..-1] underflow
 *   NOCTIS-D.H:171-176    the quadrant bitfield
 *
 * It never reads work/fb*.txt and it never reads fb_layout.py.  fb_layout.py
 * DERIVES the layout by parsing NOCTIS-D.H and NOCTIS.CPP; this file
 * TRANSCRIBES it.  The two disagreeing is the point of the kind-5 compare.
 *
 * build:
 *   gcc -std=c99 -O2 -Wall -Wextra -o fb_ref.exe fb_ref.c
 * sabotage builds add exactly one -DBREAK_* each; see BREAKS[] below.
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
#define LOWPAD 16

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

static int rbase[NREG], rpad[NREG];
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

#define CANARY_MAGIC 0xA5A5A5A5u

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

/* the RAW unit.  Under one-per-unit this must equal nw_get; that identity is
 * exactly the property Decision 1 claims and BREAK_PACK4 destroys. */
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

/* n_globes_map is declared `char` (signed) at NOCTIS-0.CPP:1004 and is
 * right-shifted at NOCTIS-1.CPP:4241,4364.  8->32 sign extension is a
 * mask-test-subtract, not a cast. */
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

/* ---------------------------------------------------------------- layout */

static void layout_init(void)
{
    int i, cur = LOWPAD;
    for (i = 0; i < NREG; i++) {
        rpad[i] = cur;
        cur += PAD;
        rbase[i] = cur;
        cur += rsize[i];
    }
    nw_top = cur + PAD;
}

/* --------------------------------------------------------------- canaries
 * Debug-build tool only.  Release pads are zero, which is the faithful state;
 * the poison changes what a class-C read-overrun samples, so grading runs use
 * the release build.  LINOBUF 3. */

static void canary_poison(void)
{
    int i, j;
    for (i = 0; i < NREG; i++)
        for (j = 0; j < PAD; j++)
            nw_unit_put(rpad[i] + j, CANARY_MAGIC);
    for (j = 0; j < LOWPAD; j++) nw_unit_put(j, CANARY_MAGIC);
    for (j = 0; j < PAD; j++) nw_unit_put(nw_top - PAD + j, CANARY_MAGIC);
}

/* Restore the RELEASE state: pads are zero.  This is not cosmetic.  The
 * poison is 0xA5A5A5A5, so a class-C read overrun that lands in a pad reads
 * 0xA5 = 165 instead of 0 -- and the page scenario's sea texture DOES land in
 * the pad (5 of its 32000 texels).  Grading runs must use the release state,
 * exactly as LINOBUF 3 warns; leaving the poison in place made the C and
 * Python page dumps disagree in precisely those 5 units. */
static void canary_clear(void)
{
    int i, j;
    for (i = 0; i < NREG; i++)
        for (j = 0; j < PAD; j++) nw_unit_put(rpad[i] + j, 0);
    for (j = 0; j < LOWPAD; j++) nw_unit_put(j, 0);
    for (j = 0; j < PAD; j++) nw_unit_put(nw_top - PAD + j, 0);
}

/* returns number of pad units that differ; fills out[2*NREG] with
 * (expected, actual) per region for FBDUMP kind 6 */
static int canary_check(uint32_t *out)
{
    int i, j, bad = 0;
    for (i = 0; i < NREG; i++) {
        uint32_t actual = CANARY_MAGIC;
        int diff = 0;
        for (j = 0; j < PAD; j++) {
            uint32_t v = nw_unit(rpad[i] + j);
            if (v != CANARY_MAGIC) { diff++; actual = v; }
        }
        out[2 * i + 0] = CANARY_MAGIC;
        out[2 * i + 1] = actual;
        bad += diff;
    }
    return bad;
}

/* ------------------------------------------------------------- Borland LCG
 * Wave 1's result, reused not rebuilt: state = state*0x015A4E35 + 1,
 * rand() = (state >> 16) & 0x7FFF.  Used only to make the page scenario
 * deterministic; nothing here grades the generator. */

static uint32_t lcg_state;
static void lcg_srand(unsigned s) { lcg_state = s & 0xFFFFu; }
static int lcg_rand(void)
{
    lcg_state = lcg_state * 0x015A4E35u + 1u;
    return (int)((lcg_state >> 16) & 0x7FFF);
}

/* ---------------------------------------------------------------- palette */

static unsigned char range8088[64 * 3];
static unsigned char pal6[768];     /* tmppal */
static unsigned char curpal6[768];  /* what the DAC holds */
static int upload_lo = -1, upload_hi = -1;

static void range8088_init(void)
{
    int i;
    for (i = 0; i < 64; i++) {
        range8088[3 * i + 0] = (unsigned char)i;
        range8088[3 * i + 1] = (unsigned char)i;
        range8088[3 * i + 2] = (unsigned char)i;
    }
}

/* NOCTIS-0.CPP:179-241.  src == NULL means the self-copy case
 * `tavola_colori(tmppal + 3*first, first, n, ...)`: source aliases
 * destination, the copy is a no-op, the filter runs in place. */
static void tavola_colori(const unsigned char *src, unsigned first, unsigned n,
                          signed char fr, signed char fg, signed char fb)
{
    unsigned c, cc = 0, n3 = n * 3, c0 = first * 3;
    unsigned temp;

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
        temp = pal6[c]; temp *= (unsigned)(int)fr; temp /= 63;
#ifndef BREAK_NOCLAMP
        if (temp > 63) temp = 63;
#endif
        pal6[c] = (unsigned char)temp; c++;
        temp = pal6[c]; temp *= (unsigned)(int)fg; temp /= 63;
#ifndef BREAK_NOCLAMP
        if (temp > 63) temp = 63;
#endif
        pal6[c] = (unsigned char)temp; c++;
        temp = pal6[c]; temp *= (unsigned)(int)fb; temp /= 63;
#ifndef BREAK_NOCLAMP
        if (temp > 63) temp = 63;
#endif
        pal6[c] = (unsigned char)temp; c++;
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
}

/* NOCTIS-0.CPP:1151-1200.  All accumulators are `float`, so every step is
 * rounded to single precision.  The store to palette_buffer[] is a C
 * float->unsigned char conversion, i.e. TRUNCATION toward zero -- lino's `=,`
 * rounds to nearest, which is why this is a named trap. */
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

static void shade(unsigned char *buf, int first_color, int number_of_colors,
                  float sr, float sg, float sb, float fr, float fg, float fb)
{
    int count = number_of_colors;
    float k = (float)(1.00 / (double)number_of_colors);
    float dr = (fr - sr) * k, dg = (fg - sg) * k, db = (fb - sb) * k;
    int i = first_color * 3;
    while (count) {
        buf[i + 0] = shade_place(sr);
        buf[i + 1] = shade_place(sg);
        buf[i + 2] = shade_place(sb);
        sr += dr; sg += dg; sb += db;
        i += 3; count--;
    }
}

/* The 6->8 choice, made once, here.  x4 because the game's own snapshot()
 * writes tmppal[c]*4 (NOCTIS-0.CPP:6418) -- measured in the shipped captures
 * as 768/768 palette bytes congruent to 0 mod 4. */
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
 * (16000 - 1440), and hard-coding 64000 bytes gets the HUD visor wrong. */
static int QUADWORDS = 16000;

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

/* NOCTIS-0.CPP:1204 copia/areaclear family, reduced to what Wave 5 needs */
static void areaclear(int base, int x, int y, int l, int a, int color)
{
    int j, i;
    for (j = 0; j < a; j++)
        for (i = 0; i < l; i++)
            nw_put(base + 320 * (y + j) + x + i, color);
}

/* ------------------------------------------------------------ present path
 * expand adaptor -> FB through PAL, unrolled x4 (LINOBUF 5.4). */
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

/* ------------------------------------------------------------ digit_at
 * NOCTIS.CPP:604-628.  txtr is based at p_surfacemap and the loop's first
 * iteration writes txtr[-6] and txtr[-5], i.e. BELOW the buffer -- class B,
 * write-only, absorbed by the dead pad.  niv-lr "fixed" this by starting the
 * loop at n = 1 (noctis.cpp:643-646), silently dropping the top scanline of
 * every glyph.  BREAK_DIGITN1 reproduces that bug so the compare can catch it.
 */
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

/* ---------------------------------------------------------------- FBDUMP */

#define FBD_MAGIC 0x46424431u
enum { K_INDEXPAGE = 1, K_PALETTE6 = 2, K_LUT = 3, K_TICKLOG = 4, K_LAYOUT = 5, K_CANARY = 6 };

static void put_u32le(FILE *f, uint32_t v)
{
    fputc((int)(v & 255), f); fputc((int)((v >> 8) & 255), f);
    fputc((int)((v >> 16) & 255), f); fputc((int)((v >> 24) & 255), f);
}

static int fbdump(const char *path, int kind, const uint32_t *payload, int count,
                  int width, int height, int cpms, int ticks)
{
    FILE *f = fopen(path, "wb");
    int i;
    if (!f) { fprintf(stderr, "cannot write %s\n", path); return 0; }
    put_u32le(f, FBD_MAGIC); put_u32le(f, 1); put_u32le(f, (uint32_t)kind);
    put_u32le(f, (uint32_t)width); put_u32le(f, (uint32_t)height);
    put_u32le(f, (uint32_t)count); put_u32le(f, (uint32_t)cpms); put_u32le(f, (uint32_t)ticks);
    for (i = 0; i < 8; i++) put_u32le(f, 0);
    for (i = 0; i < count; i++) put_u32le(f, payload[i]);
    fclose(f);
    return 1;
}

/* ------------------------------------------------------------------ tick
 * period_counts = cpms*55 - (cpms*44505 + carry) / 596591, remainder carried.
 * 55 - 44505/596591 = 32768000/596591 ms = 65536/1193182 s exactly, and the
 * largest intermediate is cpms*44505 ~ 4.0e8, well inside 32 bits.  The naive
 * cpms*552086 overflows. */
static int32_t tick_carry;
static int32_t tick_period(int32_t cpms)
{
    int32_t num = cpms * 44505 + tick_carry;
    int32_t q = num / 596591;
    tick_carry = num - q * 596591;
    return cpms * 55 - q;
}

/* the wait predicate: the SIGN of the difference, never a timestamp compare.
 * [Counts] wraps every ~477 s, so an unsigned compare is the eight-minute bug. */
static int tick_expired(uint32_t now, uint32_t deadline)
{
#ifdef BREAK_TICKCMP
    return now >= deadline;
#else
    return (int32_t)(now - deadline) >= 0;
#endif
}

/* --------------------------------------------------------------- scenarios */

static void scenario_boot(void)
{
    memset(pal6, 0, sizeof pal6);
    memset(curpal6, 0, sizeof curpal6);
    tavola_colori(range8088, 0, 64, 16, 32, 63);   /* NOCTIS.CPP:2218 */
    tavola_colori(NULL, 0, 256, 64, 64, 64);       /* NOCTIS.CPP:2219, self-copy */
    lut_rebuild();
}

/* pinned; chosen to exercise shade's clamps.  Must match fb_pal.py's
 * SURFACE_ARGS exactly -- that agreement is part of the Tier 2 compare. */
static void scenario_surface(void)
{
    const int cb = 128;
    const float r1 = 3.25f, g1 = 5.50f, b1 = 7.75f;
    const float r2 = 19.50f, g2 = 24.75f, b2 = 33.00f;
    const float r3 = 66.25f, g3 = -2.50f, b3 = 48.125f;
    const signed char brt = 64;
    scenario_boot();
    /* Steps 1-2 make the upload-from-zero rule observable.  shade() writes
     * tmppal without uploading; NOCTIS.CPP:3777 re-filters the sky band
     * 64..127 every frame, and because the upload runs from colour ZERO it is
     * that sky call which carries the band-0 change to the DAC. */
    shade(pal6, 0, 64, 8.0f, 8.0f, 8.0f, 40.0f, 52.0f, 63.0f);
    tavola_colori(NULL, 64, 64, 48, 52, 63);
    shade(pal6, cb + 0, 16, 0.0f, 0.0f, 0.0f, r1, g1, b1);
    shade(pal6, cb + 16, 16, r1, g1, b1, r2, g2, b2);
    shade(pal6, cb + 32, 16, r2, g2, b2, r3, g3, b3);
    shade(pal6, cb + 48, 16, r3, g3, b3, 64.0f, 64.0f, 64.0f);
    tavola_colori(NULL, (unsigned)cb, 64, brt, brt, brt);
    lut_rebuild();
}

/* The page scenario.  Deterministic, exercises the model rather than a
 * renderer: QUADWORDS-limited clear, a glyph raster through the dead pad, a
 * sea-texture read sweep that overruns n_globes_map into s_background, the
 * tinta/escrescenze scratch, an areaclear on the VISIBLE page, and pcopy. */
static void scenario_page(void)
{
    int adapted = rbase[R_ADAPTED], adaptor = rbase[R_ADAPTOR];
    int globes = rbase[R_N_GLOBES_MAP], surf = rbase[R_P_SURFACEMAP];
    int i, u, v, texel;

    QUADWORDS = 16000;
    pclear(adaptor, 0);
    /* NOCTIS.CPP:2206 steady state: QUADWORDS -= 1440, so page ops cover
     * 14560 dwords = 58240 bytes = 182 rows, NOT 64000 bytes.  The clear
     * pattern is deliberately NON-ZERO: with a zero pattern the cleared and
     * the never-cleared parts of a fresh page are indistinguishable, and the
     * BREAK_QUADWORDS sabotage slips through unnoticed.  The pattern is a
     * probe, not a claim about the game -- NOCTIS-1.CPP:5021 clears to 0. */
    QUADWORDS = 16000 - 1440;
    pclear(adapted, 7);

    /* seed the sea/horizon texture region and the map beyond it, so a read
     * overrun is observable rather than reading zeros either way */
    lcg_srand(1996);
    for (i = 0; i < 32768; i++) nw_put(globes + i, lcg_rand() & 63);
    for (i = 0; i < 4096; i++) nw_put(rbase[R_S_BACKGROUND] + i, 128 + (lcg_rand() & 63));

    /* sea texture sampled with the 16-bit texel address, V driven past row 127
     * so texels 32768..65535 read PAST n_globes_map -- class C.  Under
     * farmalloc order that lands on s_background, which is what DOS gave it. */
    for (i = 0; i < 32000; i++) {
        u = (i * 517) & 0xFFFF;
        v = (i * 1031) & 0xFFFF;
        texel = texel_addr(u, v);
        nw_put(adapted + i, nw_get(globes + texel));
    }

    /* a glyph, rastered exactly as digit_at does, txtr based at p_surfacemap */
    digit_at('A', 64 + 40, 1);
    /* copy the glyph window into the page so it is observable in kind 1 */
    for (i = 0; i < 9216; i++) nw_put(adapted + 32000 + i, nw_get(surf + 256 * 0 - 5 + i));

    /* tinta / escrescenze scratch.  LINOBUF alias 8: under farmalloc offset 4
     * these are VISIBLE pixels, row 199 columns 316-317.  niv-lr relocated
     * them to 64000; BREAK_TINTA64000 reproduces that divergence. */
#ifdef BREAK_TINTA64000
    nw_put(adapted + 64000, 0x37); nw_put(adapted + 64001, 0x5B);
#else
    nw_put(adapted + 63996, 0x37); nw_put(adapted + 63997, 0x5B);
#endif

    /* vanilla's type-9 substellar case and areaclear write the VISIBLE page,
     * not the surface buffer.  Keep both pages real. */
    areaclear(adaptor, 2, 191, 316, 7, 64 + 63);

    QUADWORDS = 16000;
    pcopy(adaptor, adapted);
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
    uint32_t *buf;
    int i, j;

    printf("fb_ref.c -- C reference for the Wave 5 buffer model\n");
    printf("build flags:");
#ifdef BREAK_SHIFTOR
    printf(" BREAK_SHIFTOR");
#endif
#ifdef BREAK_UPLOADFIRST
    printf(" BREAK_UPLOADFIRST");
#endif
#ifdef BREAK_ROUNDSHADE
    printf(" BREAK_ROUNDSHADE");
#endif
#ifdef BREAK_NOCLAMP
    printf(" BREAK_NOCLAMP");
#endif
#ifdef BREAK_NOSELF
    printf(" BREAK_NOSELF");
#endif
#ifdef BREAK_DIGITN1
    printf(" BREAK_DIGITN1");
#endif
#ifdef BREAK_TINTA64000
    printf(" BREAK_TINTA64000");
#endif
#ifdef BREAK_PACK4
    printf(" BREAK_PACK4");
#endif
#ifdef BREAK_QUADWORDS
    printf(" BREAK_QUADWORDS");
#endif
#ifdef BREAK_TICKCMP
    printf(" BREAK_TICKCMP");
#endif
#ifdef BREAK_SHRINKADAPTOR
    printf(" BREAK_SHRINKADAPTOR");
#endif
#ifdef BREAK_OVERRUN
    printf(" BREAK_OVERRUN=%d", BREAK_OVERRUN);
#endif
    printf(" (none listed = clean)\n\n");

    layout_init();
#ifdef BREAK_PACK4
    NWSTORE = calloc((size_t)(nw_top / 4 + 2), sizeof(uint32_t));
#else
    NW = calloc((size_t)nw_top, sizeof(uint32_t));
#endif
    FB = calloc(64000, sizeof(uint32_t));
    range8088_init();

    printf("layout (transcribed from NOCTIS-D.H + NOCTIS.CPP farmalloc order):\n");
    for (i = 0; i < NREG; i++)
        printf("  %d %-14s base %6d size %6d end %6d pad %6d\n",
               i, rname[i], rbase[i], rsize[i], rbase[i] + rsize[i], rpad[i]);
    printf("  NW top %d units = %d bytes\n\n", nw_top, nw_top * 4);

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
        req(nw_get(1001) == 0x83, "B4 quadrant set nr_of_objects=3 object2_class=2 -> 0x83 (got 0x%02X)", nw_get(1001));
    }
    /* the decisive one: a byte offset IS a unit offset */
    {
        int okid = 1;
        for (i = 0; i < 16; i++) { nw_put(2000 + i, 0x10 + i); }
        for (i = 0; i < 16; i++) if (nw_unit(2000 + i) != (uint32_t)(0x10 + i)) okid = 0;
        req(okid, "B5 one byte per unit: raw unit at offset k equals the byte at k");
    }
    printf("\n");

    printf("canary:\n");
    canary_poison();
    buf = calloc(2 * NREG, sizeof(uint32_t));
    req(canary_check(buf) == 0, "C1 clean check reports zero differing pad units");
#ifdef BREAK_OVERRUN
    nw_unit_put(rbase[BREAK_OVERRUN] + rsize[BREAK_OVERRUN], 0xDEADBEEFu);
    {
        int bad = canary_check(buf);
        req(bad == 0, "C2 after a one-unit overrun of %s the check STILL reports zero (got %d)",
            rname[BREAK_OVERRUN], bad);
        for (i = 0; i < NREG; i++)
            if (buf[2 * i + 1] != CANARY_MAGIC)
                printf("        canary fired: region %d %s expected %08X actual %08X\n",
                       i, rname[i], buf[2 * i], buf[2 * i + 1]);
    }
#else
    {
        int bad;
        nw_unit_put(rbase[R_N_GLOBES_MAP] + rsize[R_N_GLOBES_MAP], 0xDEADBEEFu);
        bad = canary_check(buf);
        req(bad == 1, "C2 a deliberate one-unit overrun of n_globes_map fires exactly one unit (got %d)", bad);
        req(buf[2 * R_S_BACKGROUND + 1] == 0xDEADBEEFu,
            "C2 it is caught in the pad ahead of s_background (actual %08X)", buf[2 * R_S_BACKGROUND + 1]);
        nw_unit_put(rbase[R_N_GLOBES_MAP] + rsize[R_N_GLOBES_MAP], CANARY_MAGIC);
    }
#endif
    canary_clear();   /* back to the release state before anything is graded */
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
        /* exact: 4096 * cpms * 32768000 / 596591 */
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

    printf("scenarios:\n");
    if (!load_digimap2(supports)) {
        printf("  FAIL  D0 could not read digimap2 from %s\n", supports);
        failures++;
    } else {
        req(1, "D0 digimap2 loaded from SUPPORTS.NCT (%d units)", DM2_BYTES / 4);
    }
    scenario_surface();
    printf("  pal6[0:12]   "); for (i = 0; i < 12; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  pal6[189:192]"); for (i = 189; i < 192; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  pal6[384:396]"); for (i = 384; i < 396; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  pal6[573:576]"); for (i = 573; i < 576; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  lut[0:4]      %08X %08X %08X %08X\n", PAL[0], PAL[1], PAL[2], PAL[3]);
    printf("  upload span   [%d,%d)\n", upload_lo, upload_hi);

    scenario_page();
    present_expand();
    {
        int okexp = 1;
        for (i = 0; i < 64000; i++)
            if (FB[i] != PAL[nw_get(rbase[R_ADAPTOR] + i)]) { okexp = 0; break; }
        req(okexp, "E1 expand invariant FB[i] == PAL[adaptor[i]] holds for all 64000");
    }
    printf("\n");

    /* dumps */
    {
        uint32_t *pay = malloc(sizeof(uint32_t) * 64000);
        snprintf(path, sizeof path, "%s/fb-ref-layout.bin", outdir);
        for (i = 0; i < NREG; i++) {
            pay[4 * i + 0] = (uint32_t)rbase[i]; pay[4 * i + 1] = (uint32_t)rsize[i];
            pay[4 * i + 2] = (uint32_t)rpad[i];  pay[4 * i + 3] = (uint32_t)i;
        }
        fbdump(path, K_LAYOUT, pay, 4 * NREG, 0, 0, 0, 0);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-pal6.bin", outdir);
        for (i = 0; i < 768; i++) pay[i] = pal6[i];
        fbdump(path, K_PALETTE6, pay, 768, 0, 0, 0, 0);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-lut.bin", outdir);
        for (i = 0; i < 256; i++) pay[i] = PAL[i];
        fbdump(path, K_LUT, pay, 256, 0, 0, 0, 0);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-adapted.bin", outdir);
        for (i = 0; i < 64000; i++) pay[i] = (uint32_t)nw_get(rbase[R_ADAPTED] + i);
        fbdump(path, K_INDEXPAGE, pay, 64000, 320, 200, 0, 0);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-adaptor.bin", outdir);
        for (i = 0; i < 64000; i++) pay[i] = (uint32_t)nw_get(rbase[R_ADAPTOR] + i);
        fbdump(path, K_INDEXPAGE, pay, 64000, 320, 200, 0, 0);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-glyph.bin", outdir);
        for (i = 0; i < 9216; i++) pay[i] = (uint32_t)nw_get(rbase[R_P_SURFACEMAP] - 5 + i);
        fbdump(path, K_INDEXPAGE, pay, 9216, 256, 36, 0, 0);
        printf("wrote %s\n", path);

        /* The CANARY record is a DEBUG-BUILD artifact by definition (LINOBUF 3:
         * release pads are zero and the check is compiled out).  Dumping it
         * from the release state would emit expected=A5A5A5A5 actual=0 for
         * every region -- nine spurious fires.  So poison, check, dump, and
         * restore the release state.  A clean debug check is therefore
         * expected==actual==A5A5A5A5, which is what a passing kind-6 record
         * looks like.  Everything graded above was dumped BEFORE this, in the
         * release state, so the poison cannot leak into a page compare. */
        snprintf(path, sizeof path, "%s/fb-ref-canary.bin", outdir);
        canary_poison();
        canary_check(pay);
        canary_clear();
        fbdump(path, K_CANARY, pay, 2 * NREG, 0, 0, 0, 0);
        printf("wrote %s\n", path);
        free(pay);
    }

    printf("\nRESULT: %s  (%d failures)\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
