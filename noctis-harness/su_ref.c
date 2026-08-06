/* su_ref.c -- Wave 7a C oracle for Noctis IV's surface().
 *
 * PROVENANCE
 * ----------
 * Transliterated from  C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP
 * (surface() :4766-5196, the painters :4488-4756, ssmooth/lssmooth
 * :4380-4441, psmooth_grays :480, pclear :332, the generators :1075-1107,
 * shade :1151, tavola_colori :179) and from PITAGORA.H:136.
 *
 * NOT from noctis-iv-lr, which PORTPLAN disqualifies for this function.
 * NOT from su_spec.py: su_spec.py models the x87 with exact rationals, this
 * file uses the hardware.  Agreement between them is therefore evidence about
 * the FLOAT MODEL, not just about the transliteration.
 *
 * WHAT MAKES THIS A DIFFERENT WITNESS FROM su_spec.py
 *   * long double is the 80-bit x87 format on x86-64 MinGW, so every
 *     intermediate really is rounded to a 64-bit significand by hardware.
 *   * fsin / fcos / fistp are executed, not modelled.  Borland's cos()
 *     returns in ST(0), so the caller sees an EXTENDED result, not a double;
 *     that is reproduced here and is why libm is not used (see -DUSE_LIBM,
 *     which exists only so the size of the hazard can be measured).
 *   * the control word is set to 133Fh, the value Wave 3 lifted out of the
 *     shipped binary's ML fragment.
 *
 * The 16-bit target is modelled explicitly: `int` in the DOS build is 16 bits,
 * far pointers do 16-bit offset arithmetic inside a segment, and farmalloc
 * hands back seg:0004.  pseg[] is that segment; the 64,800-byte map is at
 * pseg[4].
 *
 * Build:  gcc -O2 -fno-fast-math -o su_ref.exe su_ref.c -lm
 * Usage:  su_ref.exe corpus.txt out.bin
 *   corpus line:  id type seedval_hex64 colorbase secs_scaled plwp owner r g b
 *   out record :  64800 map | 32400 overlay | 768 tmppal | 4+4 draw counts
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

typedef int16_t   i16;
typedef uint16_t  u16;
typedef int32_t   i32;
typedef uint32_t  u32;
typedef uint64_t  u64;
typedef long double ld;

#define PB 4
#define OV 4
#define MAPBYTES 64800
#define OVLBYTES 32400

static const double DEGD = 3.14159265358979323846 / 180.0;   /* PITAGORA.H:136 */
#define M_PI_D 3.14159265358979323846

static unsigned char pseg[65536];
static unsigned char oseg[65536];
static unsigned char tmppal[768];

/* ---- the painter parameter globals (NOCTIS-0.CPP:4444) ---------------- */
static i16 g_c, g_gr, g_r, g_g, g_b, g_cr, g_cx, g_cy;
static float g_a;
static float kfract = 2.0f;
static signed char lave, crays;
static u16 g_px, g_py, vptr;
static i16 QUADWORDS = 16000;

/* ---- x87 ------------------------------------------------------------- */

static void set_cw(unsigned short cw)
{
    __asm__ __volatile__("fldcw %0" : : "m"(cw));
}

#if defined(USE_LIBM_D)
/* the hazard a port most plausibly walks into: double-precision libm instead
   of Borland's cos(), which returns an EXTENDED value in ST(0). */
static ld x_sin(ld x) { return (ld)sin((double)x); }
static ld x_cos(ld x) { return (ld)cos((double)x); }
#elif defined(USE_LIBM)
static ld x_sin(ld x) { return sinl(x); }
static ld x_cos(ld x) { return cosl(x); }
#else
static ld x_sin(ld x) { ld r; __asm__("fsin" : "=t"(r) : "0"(x)); return r; }
static ld x_cos(ld x) { ld r; __asm__("fcos" : "=t"(r) : "0"(x)); return r; }
#endif

/* FISTP word under RC=00: round to nearest even.  wave() is the only caller. */
static i16 x_fistp16(ld x)
{
    short r;
    __asm__ __volatile__("fistps %0" : "=m"(r) : "t"(x) : "st");
    return (i16)r;
}

/* Borland's (long) cast: __ftol, chop, keep the low 32 bits, never saturate */
static i32 ftol32(ld x)
{
    long long t;
    if (x >= 9.2233720368547758e18L || x <= -9.2233720368547758e18L)
        t = (long long)0x8000000000000000ULL;
    else
        t = (long long)x;                       /* C truncates toward zero */
    return (i32)(u32)((u64)t & 0xFFFFFFFFULL);
}

/* double -> `unsigned` (16 bit here): __ftol then keep AX */
static u16 d2u16(ld x)
{
    long long t;
    if (x >= 9.2233720368547758e18L || x <= -9.2233720368547758e18L)
        t = (long long)0x8000000000000000ULL;
    else
        t = (long long)x;
    return (u16)((u64)t & 0xFFFFULL);
}

/* ---- the two generators ---------------------------------------------- */

static u32 flat_rnd_seed;
static u32 brtl_state = 1;
static long fast_n, brtl_n;

static void fast_srand(i32 seed)
{
    u32 s = (u32)seed;
    flat_rnd_seed = (s & 0xFFFF0000u) | ((s & 0xFFFFu) | 3u);
}

static u32 fast_random(u32 mask)
{
    u64 p = (u64)flat_rnd_seed * (u64)flat_rnd_seed;   /* mul edx */
    u32 eax = (u32)p, edx = (u32)(p >> 32);
    unsigned char al = (unsigned char)((eax & 0xFF) + (edx & 0xFF)); /* add al,dl */
    eax = (eax & 0xFFFFFF00u) | al;
    flat_rnd_seed += eax;
    return eax & mask;
}

static i16 rfr(i16 range)            /* ranged_fast_random, :1103 */
{
    long v;
    if (range <= 0) range = 1;
    v = (long)fast_random(0x7FFF);
    fast_n++;
    return (i16)(v % (long)range);
}

static u32 fast_raw(u32 mask) { u32 v = fast_random(mask); fast_n++; return v; }

static void bsrand(u16 s) { brtl_state = s; }

static i16 brand(void)               /* Borland rand(), from NOCTIS.EXE */
{
    brtl_state = brtl_state * 0x015A4E35u + 1u;
    return (i16)((brtl_state >> 16) & 0x7FFFu);
}

static i16 brandom(i16 n)            /* random(), file offset 0x14237 */
{
    i32 r = (i32)brand();
    i32 prod = (i32)((u32)r * (u32)(i32)n);       /* imul eax,edx : low 32 */
    brtl_n++;
    return (i16)(prod / 0x8000);                  /* idiv : toward zero */
}

/* ---- smoothing -------------------------------------------------------- */

static u32 rd32(const unsigned char *p) {
    return (u32)p[0] | ((u32)p[1] << 8) | ((u32)p[2] << 16) | ((u32)p[3] << 24);
}

static void ssmooth(void)
{
    u16 cx = (u16)((u16)(QUADWORDS << 2) - (u16)(360 << 2));
    u16 di = (u16)(PB + 360);
    while (cx) {
        u32 e = rd32(&pseg[(u16)(di - 360)]) + rd32(&pseg[di])
              + rd32(&pseg[(u16)(di + 360)]) + rd32(&pseg[(u16)(di + 720)]);
        unsigned char al;
        e &= 0xFCFCFCFCu;
        e >>= 2;
        al = (unsigned char)(e & 0xFF);
        al = (unsigned char)(al + ((e >> 8) & 0xFF));
        al = (unsigned char)(al + ((e >> 16) & 0xFF));
        al = (unsigned char)(al + ((e >> 24) & 0xFF));
        al >>= 2;
        pseg[di] = al;
        di++;
        cx--;
    }
}

static void lssmooth(void)
{
    /* LR-DIVERGENCE: niv-lr uses (QUADWORDS-80)*4 - 1.  Vanilla has no -1 and
     * the last iterations read 41 bytes past the map. */
    u16 cx = (u16)((u16)(QUADWORDS - 80) << 2);
    u16 di = PB;
    while (cx) {
        u16 dx = (u16)(pseg[di] | (pseg[(u16)(di + 1)] << 8));
        u16 bx;
        unsigned char al = (unsigned char)(dx & 0xFF), dl, dh, bl, bh;
        dx &= 0x3F3F;
        bx = (u16)(pseg[(u16)(di + 360)] | (pseg[(u16)(di + 361)] << 8));
        dl = (unsigned char)(dx & 0xFF); dh = (unsigned char)(dx >> 8);
        bx &= 0x3F3F;
        bl = (unsigned char)(bx & 0xFF); bh = (unsigned char)(bx >> 8);
        dl = (unsigned char)(dl + dh);
        al &= 0xC0;
        dl = (unsigned char)(dl + bl);
        dl = (unsigned char)(dl + bh);
        dl >>= 2;
        pseg[di] = (unsigned char)(al | dl);
        di++;
        cx--;
    }
}

static void psmooth_grays(void)
{
    u16 cx = (u16)((u16)(QUADWORDS << 2) - (u16)(320 << 2));
    u16 di = (u16)(PB + 320);
    while (cx) {
        u32 e = rd32(&pseg[(u16)(di - 320)]) + rd32(&pseg[di])
              + rd32(&pseg[(u16)(di + 320)]) + rd32(&pseg[(u16)(di + 640)]);
        unsigned char al;
        e &= 0xFCFCFCFCu;
        e >>= 2;
        al = (unsigned char)(e & 0xFF);
        al = (unsigned char)(al + ((e >> 8) & 0xFF));
        al = (unsigned char)(al + ((e >> 16) & 0xFF));
        al = (unsigned char)(al + ((e >> 24) & 0xFF));
        al >>= 2;
        pseg[di] = al;
        di++;
        cx--;
    }
}

static void pclear(unsigned char pattern)
{
    memset(&pseg[PB], pattern, (size_t)QUADWORDS * 4);
}

/* ---- painters --------------------------------------------------------- */

static void spot(void)
{
    u16 di = (u16)(PB + g_py + g_px);
    unsigned char al = (unsigned char)(pseg[di] + (unsigned char)(g_gr & 0xFF));
    if (al >= 0x3E) al = 0x3E;
    pseg[di] = al;
}

static void cirrus(void)
{
    u16 bx = (u16)((u16)(g_py + g_px) >> 1);
    u16 di = (u16)(OV + bx);
    unsigned char al = (unsigned char)(oseg[di] + (unsigned char)(g_gr & 0xFF));
    if (al >= 0x1F) al = 0x1F;
    oseg[di] = al;
}

#define ALOOP for (g_a = 0.0f; (double)g_a < 2.0 * M_PI_D; \
                   g_a = (float)((ld)g_a + (ld)4 * (ld)DEGD))

static void permanent_storm(void)
{
    for (g_g = 1; g_g < g_cr; g_g++) {
        ALOOP {
            g_px = d2u16((ld)g_cx + (ld)g_g * x_cos((ld)g_a));
            g_py = d2u16((ld)g_cy + (ld)g_g * x_sin((ld)g_a));
            g_py = (u16)(g_py * 360);
            spot();
        }
    }
}

static void storm(void)
{
    for (g_g = 1; g_g < g_cr; g_g++) {
        ALOOP {
            g_px = d2u16((ld)g_cx + (ld)g_g * x_cos((ld)g_a));
            g_py = d2u16((ld)g_cy + (ld)g_g * x_sin((ld)g_a));
            g_py = (u16)(g_py * 360);
            cirrus();
        }
    }
}

static void volcano(void)
{
    ALOOP {
        g_b = g_gr;
        for (g_g = (i16)(g_cr / 2); g_g < g_cr; g_g++) {
            g_px = d2u16((ld)g_cx + x_cos((ld)g_a) * (ld)g_g);
            g_py = d2u16((ld)g_cy + x_sin((ld)g_a) * (ld)g_g);
            g_py = (u16)(g_py * 360);
            spot();
            g_gr--;
            if (g_gr < 0) g_gr = 0;
        }
        g_gr = g_b;
    }
}

static void crater(void)
{
    ALOOP {
        ld ca = x_cos((ld)g_a), sa = x_sin((ld)g_a);
        for (g_gr = 0; g_gr < g_cr; g_gr++) {
            u16 di;
            unsigned char al, ah;
            g_px = d2u16((ld)g_cx + ca * (ld)g_gr);
            g_py = d2u16((ld)g_cy + sa * (ld)g_gr);
            vptr = (u16)(g_px + (u16)(360 * g_py));
            di = (u16)(PB + vptr);
            al = pseg[di];
            ah = (unsigned char)((unsigned char)(g_gr & 0xFF) >> (lave & 0xFF));
            if (al < ah) al = 0; else al = (unsigned char)(al - ah);
            pseg[di] = al;
        }
        {
            u16 di = (u16)(PB + vptr);
            pseg[di] = 0x3E;                    /* mov ax,013Eh ; mov [di],ax */
            pseg[(u16)(di + 1)] = 0x01;
        }
        if (crays && !brandom(crays)) {
            g_b = (i16)((2 + brandom(2)) * g_cr);
            if (g_cy - g_b > 0 && g_cy + g_b < 179) {
                for (g_gr = (i16)(g_cr + 1); g_gr < g_b; g_gr++) {
                    u16 di;
                    unsigned char al;
                    g_px = d2u16((ld)g_cx + ca * (ld)g_gr);
                    g_py = d2u16((ld)g_cy + sa * (ld)g_gr);
                    vptr = (u16)(g_px + (u16)(360 * g_py));
                    di = (u16)(PB + vptr);
                    al = (unsigned char)(pseg[di] + (unsigned char)(g_cr & 0xFF));
                    if (al >= 0x3E) al = 0x3E;
                    pseg[di] = al;
                }
            }
        }
    }
}

static void band(void)
{
    u16 di = (u16)(PB + g_py);
    unsigned char ah = (unsigned char)(g_g & 0xFF);
    u32 n = (u16)g_cr;
    if (n == 0) n = 65536;
    while (n--) {
        unsigned char al = pseg[di];
        al = (al < ah) ? 0 : (unsigned char)(al - ah);
        pseg[di] = al;
        di++;
    }
}

static void wave(void)
{
    u16 bx = (u16)g_cy;
    g_px = 360;
    do {
        ld t = x_sin((ld)(i16)g_px * (ld)g_a) * (ld)g_cr;
        g_py = (u16)x_fistp16(t);
        g_py = (u16)(g_py + bx);
        {
            u16 ax = (u16)(g_py * 360);
            u16 di;
            ax = (u16)(ax + 4);                 /* BUFFERMAP 4.1: no skew */
            di = (u16)(ax + g_px);
            pseg[di] = 0;
        }
        g_px--;
    } while (g_px);
}

static void fracture(float max_latitude)
{
    float px, py;
    g_a = (float)((ld)brandom(360) * (ld)DEGD);
    g_gr++;
    px = (float)g_cx;
    py = (float)g_cy;
    do {
        i16 k = (i16)(brandom(g_g) - brandom(g_g));
        g_a = (float)((ld)g_a + (ld)k * (ld)DEGD);
        px = (float)((ld)px + (ld)kfract * x_cos((ld)g_a));
        if ((double)px > 359) px = (float)((ld)px - 360);
        if ((double)px < 0)   px = (float)((ld)px + 360);
        py = (float)((ld)py + (ld)kfract * x_sin((ld)g_a));
        if ((double)py > (double)max_latitude - 1) py = (float)((ld)py - (ld)max_latitude);
        if ((double)py < 0) py = (float)((ld)py + (ld)max_latitude);
        vptr = d2u16((ld)px + (ld)(u16)(360 * d2u16((ld)py)));
        {
            u16 di = (u16)(PB + vptr);
            pseg[di] = (unsigned char)(pseg[di] >> (unsigned char)g_b);
        }
        g_gr--;
    } while (g_gr);
}

static void negate(void)
{
    u16 di = PB;
    i32 cx = MAPBYTES;
    while (cx--) { pseg[di] = (unsigned char)(0x3E - pseg[di]); di++; }
}

static void contrast(float kt, float kq, float thrshld)
{
    unsigned c;
    for (c = 0; c < 64800; c++) {
        g_a = (float)pseg[PB + c];
        g_a = (float)((ld)g_a - (ld)thrshld);
        if ((double)g_a > 0) g_a = (float)((ld)g_a * (ld)kt);
        else                 g_a = (float)((ld)g_a * (ld)kq);
        g_a = (float)((ld)g_a + (ld)thrshld);
        if ((double)g_a < 0) g_a = 0;
        if ((double)g_a > 63) g_a = 63;
        pseg[PB + c] = (unsigned char)(long long)g_a;
    }
}

static void randoface(i16 range, i16 upon)
{
    unsigned c;
    for (c = 0; c < 64800; c++) {
        g_gr = (i16)pseg[PB + c];
        if ((upon > 0 && g_gr >= upon) || (upon < 0 && g_gr <= -upon)) {
            g_gr = (i16)(g_gr + brandom(range));
            g_gr = (i16)(g_gr - brandom(range));
            if (g_gr > 63) g_gr = 63;
            if (g_gr < 0) g_gr = 0;
            pseg[PB + c] = (unsigned char)g_gr;
        }
    }
}

static void crater_juice(void)
{
    lave  = (signed char)brandom(3);
    crays = (signed char)(brandom(3) * 2);
    for (g_c = 0; g_c < g_r; g_c++) {
        g_cx = brandom(360);
        g_cr = (i16)(2 + brandom((i16)(1 + g_r - g_c)));
        while (g_cr > 20) g_cr -= 10;
        g_cy = (i16)(brandom((i16)(178 - 2 * g_cr)) + g_cr);
        crater();
        if (g_cr > 15) lssmooth();
    }
}

static void atm_cyclon(void)
{
    g_b = 0;
    while (g_cr > 0) {
        g_px = d2u16((ld)g_cx + (ld)g_cr * x_cos((ld)g_a));
        g_py = d2u16((ld)g_cy + (ld)g_cr * x_sin((ld)g_a));
        g_py = (u16)(g_py * 360); cirrus();
        g_px = (u16)(g_px + brandom(4)); cirrus();
        g_py = (u16)(g_py + 359); cirrus();
        g_px = (u16)(g_px - brandom(4)); cirrus();
        g_py = (u16)(g_py + 361); cirrus();
        g_px = (u16)(g_px + brandom(4)); cirrus();
        g_b++;
        g_b = (i16)(g_b % g_g);
        if (!g_b) g_cr--;
        g_a = (float)((ld)g_a + (ld)6 * (ld)DEGD);
    }
}

/* ---- palette ---------------------------------------------------------- */

static const unsigned char planet_rgb_and_var[] = {
    60,30,15,20,  40,50,40,25,  32,32,32,32,  16,32,48,40,  32,40,32,20,
    32,32,32,32,  32,32,32,32,  32,40,48,24,  40,40,40,30,  50,25,10,20,
    40,40,40,40 };

static void shade(int first_color, int n, float sr, float sg, float sb,
                  float fr, float fg, float fb)
{
    int count = n;
    float k  = (float)(1.00L / (ld)(float)n);
    float dr = (float)(((ld)fr - (ld)sr) * (ld)k);
    float dg = (float)(((ld)fg - (ld)sg) * (ld)k);
    float db = (float)(((ld)fb - (ld)sb) * (ld)k);
    first_color *= 3;
    while (count) {
        if (sr >= 0 && sr < 64) tmppal[first_color + 0] = (unsigned char)(long long)sr;
        else tmppal[first_color + 0] = (sr > 0) ? 63 : 0;
        if (sg >= 0 && sg < 64) tmppal[first_color + 1] = (unsigned char)(long long)sg;
        else tmppal[first_color + 1] = (sg > 0) ? 63 : 0;
        if (sb >= 0 && sb < 64) tmppal[first_color + 2] = (unsigned char)(long long)sb;
        else tmppal[first_color + 2] = (sb > 0) ? 63 : 0;
        sr = (float)((ld)sr + (ld)dr);
        sg = (float)((ld)sg + (ld)dg);
        sb = (float)((ld)sb + (ld)db);
        first_color += 3;
        count--;
    }
}

static void tavola_colori(unsigned start, unsigned n,
                          signed char fr, signed char fg, signed char fb)
{
    int c, cc = 0;
    u16 temp;
    n *= 3;
    start *= 3;
    c = (int)start;
    while ((unsigned)cc < n) { tmppal[c] = tmppal[start + cc]; cc++; c++; }
    c = (int)start;
    while ((unsigned)c < n + start) {
        temp = (u16)(tmppal[c] * fr); temp /= 63; if (temp > 63) temp = 63;
        tmppal[c] = (unsigned char)temp; c++;
        temp = (u16)(tmppal[c] * fg); temp /= 63; if (temp > 63) temp = 63;
        tmppal[c] = (unsigned char)temp; c++;
        temp = (u16)(tmppal[c] * fb); temp /= 63; if (temp > 63) temp = 63;
        tmppal[c] = (unsigned char)temp; c++;
    }
}

/* ---- surface() -------------------------------------------------------- */

static i32 secs_scaled;          /* substituted (long)(k*secs); see su_secs.py */
static double g_secs;
static int    use_scaled;

static i32 secs_site(int k)   /* i32, NOT i16: (long)(k*secs) is a
                                 32-bit long and the division below must see
                                 all of it.  Narrowing here silently truncates
                                 the dividend. */
{
    i32 s = use_scaled ? secs_scaled : ftol32((ld)k * (ld)g_secs);
    return s;
}

static i16 cxsite(int k, i16 D)
{
    i32 s = secs_site(k);
    return (i16)((s / (i32)D) % 360);
}

static u16 the_seed;

static void rndpat(void)
{
    u16 ax = the_seed, cx = MAPBYTES, di = PB;
    while (cx) {
        i32 p;
        u16 dx;
        ax = (u16)(ax + cx);
        p = (i32)((i16)ax) * (i32)((i16)ax);       /* imul ax : signed */
        dx = (u16)((u32)p >> 16);
        ax = (u16)((u16)p + dx);
        pseg[di] = (unsigned char)(ax & 0x3E);
        di++; cx--;
    }
}

static void sda(void)
{
    /* LR-DIVERGENCE, the fatal one: vanilla ADDs the noise byte to the
     * already-smoothed terrain and clamps with a WORD store that zeroes the
     * neighbouring pixel; the noise register advances only on the land
     * branch.  niv-lr assigns, stores a byte, and advances unconditionally. */
    u16 ax = the_seed, cx = 64000, di = PB;
    unsigned char gl = (unsigned char)(g_g & 0xFF);
    while (cx) {
        if (pseg[di] < gl) {
            pseg[di] = 16;
        } else {
            i32 p; u16 dx; unsigned char bl, nv;
            ax = (u16)(ax + cx);
            p = (i32)((i16)ax) * (i32)((i16)ax);
            dx = (u16)((u32)p >> 16);
            ax = (u16)((u16)p + dx);
            bl = (unsigned char)(ax & 0x3E);
            nv = (unsigned char)(pseg[di] + bl);
            pseg[di] = nv;
            if (nv >= 0x3E) { pseg[di] = 0x3E; pseg[(u16)(di + 1)] = 0x00; }
        }
        di++; cx--;
    }
}

static void lmrip(void)
{
    u16 di = PB;
    i32 cx = 64000;
    while (cx--) {
        if (pseg[di] == 32) {
            pseg[di] = 0x01;
            pseg[(u16)(di + 1)] = 0x3E;
            pseg[(u16)(di + 360)] = 0x01;
        }
        di++;
    }
}

static void the_switch(int type)
{
    i16 c;
    switch (type) {
    case 0: {
        u16 di; i32 cx;
        g_r = (i16)(rfr(3) + 5);
        for (g_c = 0; g_c < g_r; g_c++) ssmooth();
        di = PB; cx = MAPBYTES;
        while (cx--) { if (pseg[di] >= 28) pseg[di] = 62; di++; }
        g_r = (i16)(rfr(5) + 5);
        for (g_c = 0; g_c < g_r; g_c++) ssmooth();
        g_r = (i16)(5 + rfr(26));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cr = (i16)(5 + rfr(20));
            g_cx = rfr(360);
            g_cy = (i16)(rfr(130) + 25);
            g_gr = (i16)(rfr((i16)(g_cr / 2)) + g_cr / 2 + 2);
            volcano();
        }
        g_r = (i16)(100 + rfr(100));
        g_b = (i16)(rfr(3) + 1);
        g_g = 360;
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cx = rfr(360); g_cy = rfr(180); g_gr = rfr(100);
            fracture(180.0f);
        }
        lssmooth();
        break; }
    case 1:
        if (rfr(2)) ssmooth();
        g_r = (i16)(10 + rfr(41));
        crater_juice();
        lssmooth();
        if (!rfr(5)) negate();
        break;
    case 2:
        g_r = (i16)(5 + rfr(25));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cr = (i16)(rfr(20) + 1);
            g_cy = (i16)(rfr((i16)(178 - 2 * g_cr)) + g_cr);
            if (brandom(2) == 0) {
                g_cx = cxsite(10, (i16)(rfr(3600) + 180));
                g_gr = (i16)(rfr(12) + 2);
                storm();
            } else {
                g_gr = (i16)(rfr(15) + 3);
                g_py = (u16)(g_cy * 360); g_cr = (i16)(g_cr * 360);
                g_g = (i16)(1 + rfr(g_gr));
                band();
            }
        }
        if (!rfr(3)) negate();
        break;
    case 3:
        g_r = (i16)(rfr(3) + 4);
        g_g = (i16)(26 + rfr(3) - rfr(5));
        for (g_c = 0; g_c < g_r; g_c++) ssmooth();
        sda();
        g_r = (i16)(20 + rfr(40));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_gr = (i16)(rfr(5) + 1);
            g_cr = (i16)(rfr(10) + 10);
            if (rfr(3)) g_cy = (i16)(rfr((i16)(172 - 2 * g_cr)) + g_cr + 2);
            else        g_cy = (i16)(60 + rfr(10) - rfr(10));
            g_cx = cxsite(1, (i16)(rfr(360) + 180));
            g_g  = (i16)(rfr(5) + 7);
            g_a  = (float)((ld)rfr(360) * (ld)DEGD);
            atm_cyclon();
        }
        break;
    case 4:
        ssmooth();
        if (rfr(2)) ssmooth();
        lmrip();
        g_r = rfr(30);
        if (g_r > 20) g_r = (i16)(g_r * 10);
        g_b = (i16)(rfr(3) + 1);
        g_g = (i16)(200 + rfr(300));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cx = rfr(360); g_cy = rfr(180); g_gr = (i16)(50 + rfr(100));
            fracture(180.0f);
        }
        g_r = (i16)(rfr(25) + 1); crater_juice();
        lssmooth();
        if (rfr(2)) lssmooth();
        break;
    case 5: {
        float kt, kq, thr;
        g_r = (i16)(rfr(3) + 4);
        for (g_c = 0; g_c < g_r; g_c++) ssmooth();
        /* arguments evaluate RIGHT TO LEFT (Borland cdecl) */
        thr = (float)(25 + rfr(3));
        kq  = (float)((ld)(float)rfr(350) / 100 + (ld)4.0);
        kt  = (float)((ld)(float)rfr(200) / 900 + (ld)0.6);
        contrast(kt, kq, thr);
        { i16 upon = (i16)(-20 * (rfr(3) + 1));
          i16 rng  = (i16)(5 + rfr(3));
          randoface(rng, upon); }
        g_r = (i16)(5 + rfr(5));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cr = (i16)(5 + rfr(10));
            g_cx = rfr(360);
            g_cy = (i16)(rfr(145) + 15);
            g_gr = (i16)(rfr((i16)(g_cr / 2)) + 2);
            volcano();
        }
        g_r = (i16)(5 + rfr(5));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cr = (i16)(rfr(30) + 1);
            g_cy = (i16)(rfr((i16)(178 - 2 * g_cr)) + g_cr);
            g_cx = cxsite(60, (i16)(rfr(3600) + 360));
            g_gr = (i16)(rfr(2) + 1);
            permanent_storm();
        }
        for (g_c = 0; g_c < 10000; g_c++) {
            g_gr = (i16)(rfr(10) + 10);
            g_px = (u16)rfr(360);
            g_py = (u16)rfr(10);
            g_py = (u16)(g_py * 360); spot();
            g_px = (u16)rfr(360);
            g_py = (u16)(i16)(125 - rfr(10));
            g_py = (u16)(g_py * 360); spot();
        }
        if (rfr(2)) ssmooth(); else lssmooth();
        break; }
    case 6:
        g_r = (i16)(3 + rfr(5));
        for (g_c = 0; g_c < g_r; g_c++) ssmooth();
        g_r = (i16)(50 + rfr(100));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cr = (i16)(rfr(10) + 1);
            g_cy = (i16)(rfr((i16)(178 - 2 * g_cr)) + g_cr);
            if (rfr(8)) {
                g_gr = (i16)(rfr(5) + 2);
                g_g  = (i16)(1 + rfr(g_gr));
                g_py = (u16)(g_cy * 360);
                g_cr = (i16)(g_cr * 360);
                band();
            } else {
                g_a = (float)((ld)(5 + rfr(10)) / 30);
                g_cr = (i16)(g_cr / 4 + 1);
                wave();
            }
        }
        g_r = (i16)(50 + rfr(100));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cr = (i16)(rfr(15) + 1);
            g_cy = (i16)(rfr((i16)(178 - 2 * g_cr)) + g_cr);
            g_cx = cxsite(60, (i16)(rfr(8000) + 360));
            g_gr = (i16)(rfr(2) + 1);
            if (rfr(10)) g_cr = (i16)(g_cr / 2 + 1);
            else         g_gr = (i16)(g_gr * 3);
            storm();
        }
        lssmooth();
        if (!rfr(3)) negate();
        break;
    case 7:
        g_r = (i16)(5 + rfr(5));
        for (g_c = 0; g_c < g_r; g_c++) ssmooth();
        g_r = (i16)(10 + rfr(50));
        g_g = (i16)(5 + rfr(20));
        g_b = (i16)(rfr(2) + 1);
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cx = rfr(360); g_cy = rfr(180); g_gr = rfr(300);
            fracture(180.0f);
        }
        if (rfr(2)) lssmooth();
        { i16 rng = (i16)(1 + rfr(10)); randoface(rng, 1); }
        if (rfr(2)) negate();
        break;
    case 8:
        g_r = (i16)(rfr(10) + 1);
        for (g_c = 0; g_c < g_r; g_c++) lssmooth();
        g_r = (i16)(100 + rfr(50));
        for (g_c = 0; g_c < g_r; g_c++) {
            g_cr = (i16)(rfr(5) + 1);
            g_gr = (i16)(rfr(5) + 1);
            g_cx = rfr(360);
            g_cy = (i16)(rfr((i16)(178 - 2 * g_cr)) + g_cr);
            permanent_storm();
        }
        if (rfr(2)) negate();
        break;
    case 9:
        pclear(0x1F);
        for (g_px = 0; g_px < 32400; g_px++) oseg[(u16)(OV + g_px)] = 0x1F;
        break;
    }
    (void)c;
}

typedef struct {
    int id, type, colorbase, plwp, owner, nr, ng, nb;
    double seedval;
    i32 secs_scaled;
    int use_scaled;
    double secs;
} Case;

static void surface(Case *k, i32 *out_rt, i32 *out_rot, i32 *out_ts, i32 *out_te)
{
    i16 QW = QUADWORDS;
    signed char knot1 = 0, brt;
    float r1,r2,r3,g1,g2,g3,b1,b2,b3;
    i16 rt, rot, plwp = (i16)k->plwp;
    int type = k->type;
    i16 rr, gg, bb, cc;
    int i;

    memset(pseg, 0, sizeof pseg);
    memset(oseg, 0, sizeof oseg);
    fast_n = brtl_n = 0;
    use_scaled = k->use_scaled;
    secs_scaled = k->secs_scaled;
    g_secs = k->secs;

    if (type == 10) return;

    fast_srand(ftol32((ld)k->seedval + 4112));
    rt = (i16)(10 * (rfr(50) + 1) + 10 * rfr(25) + rfr(250) + 41);
    rot = (i16)ftol32((ld)k->secs / (ld)rt);
    rot = (i16)(rot % 360);
    *out_rt = rt; *out_rot = rot;

    fast_srand(ftol32((ld)k->seedval * 10));
    the_seed = (u16)fast_raw(0xFFFF);

    bsrand(the_seed);
    rndpat();
    memset(&oseg[OV], 0, OVLBYTES);
    bsrand(the_seed);                 /* :4844 - UNGRADED, idempotent */
    QUADWORDS = 16200;

    the_switch(type);

    if (type == 3 || type == 5)
        for (i = 0; i < MAPBYTES; i++) pseg[PB + i] >>= 1;

    if (type == 3) { if (rfr(2)) lssmooth(); else ssmooth(); }

    { unsigned pxi, pyi;
      for (pxi = 0, pyi = 0; pxi < 32400; pyi += 2, pxi++) {
          unsigned v = pseg[PB + pyi] + oseg[OV + pxi];
          pseg[PB + pyi] = (unsigned char)v;
          if (pseg[PB + pyi] > 0x3E) pseg[PB + pyi] = 0x3E;
          v = pseg[PB + pyi + 1] + oseg[OV + pxi];
          pseg[PB + pyi + 1] = (unsigned char)v;
          if (pseg[PB + pyi + 1] > 0x3E) pseg[PB + pyi + 1] = 0x3E;
      } }

    if (type == 2) { if (!brandom(3)) { psmooth_grays(); knot1 = 1; } }

    { i16 ts = (i16)(plwp + 35), te;
      if (ts >= 360) ts = (i16)(ts - 360);
      te = (i16)(ts + 130);
      if (te >= 360) te = (i16)(te - 360);
      *out_ts = ts; *out_te = te; }
    { u16 di = (u16)(PB + plwp + 35);
      int row, col;
      for (row = 0; row < 179; row++) {
          for (col = 0; col < 130; col++) { pseg[di] = (unsigned char)(pseg[di] >> 2); di++; }
          di = (u16)(di + 230);
      } }

    if (type == 2) {
        if (knot1) ssmooth();
        else { g_r = (i16)(3 + rfr(5));
               for (g_c = 0; g_c < g_r; g_c++) ssmooth(); }
    }
    if (type == 6) for (g_c = 0; g_c < 3; g_c++) if (rfr(2)) ssmooth();
    if (type == 9) for (g_c = 0; g_c < 6; g_c++) ssmooth();

    if (k->colorbase == 255) { QUADWORDS = QW; return; }

    type <<= 2;
    rr = planet_rgb_and_var[type + 0];
    gg = planet_rgb_and_var[type + 1];
    bb = planet_rgb_and_var[type + 2];
    cc = planet_rgb_and_var[type + 3];
    rr = (i16)(((i16)(rr << 1) + (i16)k->nr) >> 1);
    gg = (i16)(((i16)(gg << 1) + (i16)k->ng) >> 1);
    bb = (i16)(((i16)(bb << 1) + (i16)k->nb) >> 1);
    /* left-to-right: the first draw is added, the second subtracted */
    r1 = (float)(rr + brandom(cc) - brandom(cc));
    g1 = (float)(gg + brandom(cc) - brandom(cc));
    b1 = (float)(bb + brandom(cc) - brandom(cc));
    r2 = (float)(rr + brandom(cc) - brandom(cc));
    g2 = (float)(gg + brandom(cc) - brandom(cc));
    b2 = (float)(bb + brandom(cc) - brandom(cc));
    r3 = (float)(rr + brandom(cc) - brandom(cc));
    g3 = (float)(gg + brandom(cc) - brandom(cc));
    b3 = (float)(bb + brandom(cc) - brandom(cc));
    r1 = (float)((ld)r1 * (ld)0.25); g1 = (float)((ld)g1 * (ld)0.25); b1 = (float)((ld)b1 * (ld)0.25);
    r2 = (float)((ld)r2 * (ld)0.75); g2 = (float)((ld)g2 * (ld)0.75); b2 = (float)((ld)b2 * (ld)0.75);
    r3 = (float)((ld)r3 * (ld)1.25); g3 = (float)((ld)g3 * (ld)1.25); b3 = (float)((ld)b3 * (ld)1.25);
    type >>= 2;
    shade(k->colorbase + 0,  16, 0, 0, 0, r1, g1, b1);
    shade(k->colorbase + 16, 16, r1, g1, b1, r2, g2, b2);
    shade(k->colorbase + 32, 16, r2, g2, b2, r3, g3, b3);
    shade(k->colorbase + 48, 16, r3, g3, b3, 64, 64, 64);
    brt = (signed char)k->owner;
    if (brt == -1) brt = (signed char)k->id;
    if (brt <= 4) brt = 64; else brt = (signed char)(64 - (4 * (brt - 4)));
    tavola_colori((unsigned)k->colorbase, 64, brt, brt, brt);
    QUADWORDS = QW;
}

int main(int argc, char **argv)
{
    FILE *fi, *fo;
    char line[512];
    set_cw(0x133F);
    if (argc < 3) { fprintf(stderr, "usage: su_ref corpus.txt out.bin\n"); return 2; }
    fi = fopen(argv[1], "r");
    fo = fopen(argv[2], "wb");
    if (!fi || !fo) { perror("open"); return 2; }
    while (fgets(line, sizeof line, fi)) {
        Case k; unsigned long long sbits; i32 rt=0, rot=0, ts=0, te=0;
        long ss; int us;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%d %d %llx %d %ld %d %d %d %d %d %d",
                   &k.id, &k.type, &sbits, &k.colorbase, &ss, &us,
                   &k.plwp, &k.owner, &k.nr, &k.ng, &k.nb) != 11) continue;
        memcpy(&k.seedval, &sbits, 8);
        k.secs_scaled = (i32)ss;
        k.use_scaled = us;
        k.secs = 0.0;
        memset(tmppal, 0, sizeof tmppal);
        brtl_state = 1;
        surface(&k, &rt, &rot, &ts, &te);
        fwrite(&pseg[PB], 1, MAPBYTES, fo);
        fwrite(&oseg[OV], 1, OVLBYTES, fo);
        fwrite(tmppal, 1, 768, fo);
        { i32 v[6]; v[0]=(i32)fast_n; v[1]=(i32)brtl_n; v[2]=rt; v[3]=rot;
          v[4]=ts; v[5]=te; fwrite(v, 4, 6, fo); }
        fprintf(stderr, "case id=%d type=%d fast=%ld brtl=%ld rt=%d rot=%d ts=%d\n",
                k.id, k.type, fast_n, brtl_n, (int)rt, (int)rot, (int)ts);
    }
    fclose(fi); fclose(fo);
    return 0;
}
