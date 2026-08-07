/* gr_ref.c -- Wave 7b C oracle for build_surface() + SURFACE.BIN.
 *
 * PROVENANCE
 * ----------
 * Transliterated from C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP
 * (build_surface :1948-2731, rockyground :1545, smoothterrain :1530,
 * SURFACE.BIN read :3722, write :4992, global_surface_seed :3671) and
 * NOCTIS-0.CPP (fast_srand/fast_random :1075, flandom :1109).
 *
 * NOT from noctis-iv-lr.  NOT from gr_spec.py: gr_spec.py models the x87
 * with exact rationals, this file uses the hardware.  Agreement between
 * them is evidence about the FLOAT MODEL, not just the transliteration.
 *
 * WHAT MAKES THIS A DIFFERENT WITNESS FROM gr_spec.py
 *   * long double is the 80-bit x87 format, so every intermediate really is
 *     rounded to a 64-bit significand by hardware.
 *   * The control word is 133Fh, the value Wave 3 lifted from the binary.
 *   * __ftol is modelled as a C truncation (chop), matching Borland's
 *     implementation.
 *
 * Build:  gcc -O2 -fno-fast-math -o gr_ref.exe gr_ref.c -lm
 * Usage:  gr_ref.exe corpus.txt out.bin
 *
 * Output records (in corpus order, varying size by kind):
 *   sbbin: 40 bytes (the packed SURFACE.BIN)
 *   seed:   4 bytes (the int32 chop)
 *   build: 40000 + 40000 + 16 bytes (map + objects + fast_n/brtl_n/fast_h/brtl_h)
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

#define PS_BYTES   40000
#define OC_BYTES   40000
#define ROCS_BYTE  0x00          /* ROCKS=0, nr_of_objects=0 -> all zero */
#define M_PI_D     3.14159265358979323846

/* ---- x87 ------------------------------------------------------------- */

static void set_cw(unsigned short cw)
{
    __asm__ __volatile__("fldcw %0" : : "m"(cw));
}

/* Borland's (long) cast: __ftol, chop, keep the low 32 bits */
static i32 ftol32(ld x)
{
    long long t;
    if (x >= 9.2233720368547758e18L || x <= -9.2233720368547758e18L)
        t = (long long)0x8000000000000000ULL;
    else
        t = (long long)x;               /* C truncates toward zero */
    return (i32)(u32)((u64)t & 0xFFFFFFFFULL);
}

/* ---- the two generators ---------------------------------------------- */

static u32 flat_rnd_seed;
static u32 brtl_state = 1;
static long fast_n, brtl_n;
static u32 fast_h, brtl_h;

#define FNV_OFF  0x811C9DC5u
#define FNV_PR   0x01000193u

static u32 fnv_one(u32 h, u32 v)
{
    int k;
    for (k = 0; k < 4; k++) {
        h = ((h ^ (v & 0xFF)) * FNV_PR) & 0xFFFFFFFFu;
        v >>= 8;
    }
    return h;
}

static void fast_srand(i32 seed)
{
    u32 s = (u32)seed;
    flat_rnd_seed = (s & 0xFFFF0000u) | ((s & 0xFFFFu) | 3u);
}

static u32 fast_random(u32 mask)
{
    u64 p = (u64)flat_rnd_seed * (u64)flat_rnd_seed;
    u32 eax = (u32)p, edx = (u32)(p >> 32);
    unsigned char al = (unsigned char)((eax & 0xFF) + (edx & 0xFF));
    eax = (eax & 0xFFFFFF00u) | al;
    flat_rnd_seed += eax;
    return eax & mask;
}

static u32 fast_raw(u32 mask)
{
    u32 v = fast_random(mask);
    fast_n++;
    fast_h = fnv_one(fast_h, v);
    return v;
}

static void bsrand(u16 s) { brtl_state = s; }

static i16 brand(void)
{
    brtl_state = brtl_state * 0x015A4E35u + 1u;
    return (i16)((brtl_state >> 16) & 0x7FFFu);
}

static i16 brandom(i16 n)
{
    i32 r = (i32)brand();
    i32 prod = (i32)((u32)r * (u32)(i32)n);
    brtl_n++;
    return (i16)(prod / 0x8000);
}

static i16 brandom_led(i16 n)
{
    i16 v = brandom(n);
    brtl_h = fnv_one(brtl_h, (u32)(i32)v);
    return v;
}

/* ---- the buffers ----------------------------------------------------- */

static unsigned char smap[PS_BYTES];
static unsigned char objs[OC_BYTES];
static unsigned char txtr[65536];

static void reset_buffers(void)
{
    memset(smap, 0, PS_BYTES);
    memset(objs, 0, OC_BYTES);
    memset(txtr, 16, 65535);          /* _fmemset (txtr, 16, 65535) :1968 */
    txtr[65535] = 0;
}

/* ---- fnv-1a over a byte buffer ---- */

static u32 fnv_bytes(const unsigned char *p, long n)
{
    u32 h = FNV_OFF;
    long i;
    for (i = 0; i < n; i++)
        h = ((h ^ p[i]) * FNV_PR) & 0xFFFFFFFFu;
    return h;
}

/* ---- smoothterrain :1530 -------------------------------------------- */

static void smoothterrain(int rounding)
{
    int r;
    for (r = 0; r < rounding; r++) {
        i32 i;
        for (i = 0; i < 39799; i++) {
            int n = smap[i] + smap[i+1] + smap[i+200] + smap[i+201];
            smap[i] = (unsigned char)(n >> 2);
        }
    }
}

/* ---- x87 transcendental wrappers (match Borland's x87 usage) -------- */

static ld x_sqrt(ld x) { ld r; __asm__("fsqrt" : "=t"(r) : "0"(x)); return r; }
static ld x_sin(ld x)  { ld r; __asm__("fsin"  : "=t"(r) : "0"(x)); return r; }
static ld x_cos(ld x)  { ld r; __asm__("fcos"  : "=t"(r) : "0"(x)); return r; }

/* ---- round_hill :1494 ----------------------------------------------- */

static void round_hill(int cx, int cz, unsigned ur, float h, float hmax,
                       signed char allowcanyons)
{
    int x, z;
    int r = (int)ur;
    if (r < 0) r = -r;                 /* abs(r) for range bounds */
    /* v = (float)r / M_PI_2 -> float32 store */
    float v = (float)((ld)(float)r / (M_PI_D / 2));
    for (x = cx - r; x < cx + r; x++)
        for (z = cz - r; z < cz + r; z++) {
            if (x > -1 && z > -1 && x < 200 && z < 200) {
                float dx = (float)(x - cx);
                float dz = (float)(z - cz);
                /* d = sqrt(dx*dx + dz*dz) -> float32 */
                float d = (float)x_sqrt((ld)dx * (ld)dx + (ld)dz * (ld)dz);
                /* y = cos(d / v) * h -> float32 */
                float y = (float)(x_cos((ld)d / (ld)v) * (ld)h);
                if (y >= 0) {
                    int idx = 200 * z + x;
                    /* y += surfacemap[idx] -> float32 */
                    y = (float)((ld)y + (ld)smap[idx]);
                    if (allowcanyons) {
                        if (y > 127)
                            y = (float)(254 - (ld)y);   /* LR-REJECTED canyon mirror */
                    } else {
                        if (y > hmax) y = hmax;
                    }
                    smap[idx] = (unsigned char)ftol32((ld)y);
                }
            }
        }
}

/* ---- std_crater :1561 ----------------------------------------------- */

static void std_crater(unsigned char *map, int cx, int cz, int r,
                       int lim_h, float h_factor, float h_raiser, long align)
{
    int x, z;
    ld h = (ld)r * (ld)h_factor;
    r = abs(r);
    { ld fr = (ld)r;
    for (x = cx - r; x < cx + r; x++)
        for (z = cz - r; z < cz + r; z++) {
            if (x > -1 && z > -1 && x < align && z < align) {
                ld dx = (ld)(x - cx), dz = (ld)(z - cz);
                ld d = x_sqrt(dx * dx + dz * dz);
                if (d <= fr) {
                    ld y = x_sin(M_PI_D * (d / fr)) * h;
                    if (h_raiser != 1.0f)
                        y = (y > 0) ? powl(y, (ld)h_raiser) : (ld)0;
                    { long idx = align * (long)z + x;
                      y += (ld)map[idx];
                      if (y < 0) y = 0;
                      if (y > lim_h) y = lim_h;
                      map[idx] = (unsigned char)(long long)y;
                    }
                }
            }
        }}
}

/* ---- srf_darkline :1589 --------------------------------------------- */

static void srf_darkline(unsigned char *map, int length,
                         int x_trend, int z_trend, long align)
{
    int fx = brandom_led((i16)align), fz = brandom_led((i16)align);
    long mapsize = align * align;
    while (length) {
        fx += brandom_led(3) + x_trend;
        fz += brandom_led(3) + z_trend;
        { long location = align * (long)fz + fx;
          if (location > 0 && location < mapsize) map[location] >>= 1; }
        length--;
    }
}

/* ---- rockyground :1545 ---------------------------------------------- */

static void rockyground(int roughness, int rounding, i16 level)
{
    i32 i;
    int alvl = abs((int)level);

    for (i = 0; i < PS_BYTES; i++)
        smap[i] = (unsigned char)brandom_led((i16)roughness);

    smoothterrain(rounding);

    for (i = 0; i < PS_BYTES; i++) {
        int v = smap[i];
        if (v >= alvl) {
            v += level;
            if (v > 127) v = 127;
            smap[i] = (unsigned char)v;
        } else {
            smap[i] = 0;
        }
    }
}

/* ---- felisian_srf_darkline :1605 ----------------------------------- */

static void felisian_srf_darkline(unsigned char *map, int length,
                                  int x_trend, int z_trend, long align)
{
    int fx = brandom_led((i16)align), fz = brandom_led((i16)align);
    int deviation = brandom_led(25) - 50;
    int variability = 2 + brandom_led(10);
    long mapsize = align * align;
    while (length) {
        fx += brandom_led(3) + x_trend;
        fz += brandom_led(3) + z_trend;
        deviation += brandom_led((i16)variability) - (variability >> 1);
        { long location = align * (long)fz + fx;
          if (location > 0 && location < mapsize) {
              int peak = (int)map[location] + deviation;
              if (peak < 0) peak = 0;
              if (peak > 127) peak = 127;
              map[location] = (unsigned char)peak;
              if (location+1 < mapsize) map[location+1] = (unsigned char)peak;
              if (location-1 > 0) map[location-1] = (unsigned char)peak;
              if (location+align < mapsize) map[location+align] = (unsigned char)peak;
              if (location-align > 0) map[location-align] = (unsigned char)peak;
          }}
        length--;
    }
}

/* ---- the type switch :2054-2581 ------------------------------------ */

static void the_switch(int type, int sctype, int albedo)
{
    int n, cx, cz, cr;
    float hf, hr, ht;

    switch (type) {
    case 1: {
        n = brandom_led(5);
        if (n <= 2) rockyground(25, 4 + brandom_led(4), 0);
        if (n == 3) rockyground(5 + brandom_led(5), 1, 1);
        if (n == 4) rockyground(10, 2, (i16)(-brandom_led(5)));
        n = brandom_led(48) + 32 - albedo;
        if (n > 30) n = 30;
        if (n < 0) n = 0;
        while (n) {
            hf = (float)((ld)brandom_led(32) * 0.01);
            hr = (float)((ld)(brandom_led(20) + 5) * 0.075);
            { int t_r = brandom_led(50) + 5;
              int t_cz = brandom_led(200);
              int t_cx = brandom_led(200);
              std_crater(smap, t_cx, t_cz, t_r, 127, hf, hr, 200); }
            n--;
        }
        n = brandom_led(48) + 64 - albedo;
        if (n < 0) n = 0;
        hf = 0.35f;
        while (n) {
            cx = brandom_led(200); cz = brandom_led(200);
            cr = brandom_led(32) + 10;
            std_crater(txtr, cx, cz, cr, 31, hf, 1.0f, 256);
            if (cr % 2) std_crater(txtr, cx+cr/3, cz+cr/3, -cr, 31, hf, 1.0f, 256);
            n--;
        }
        n = brandom_led(100);
        while (n) { srf_darkline(txtr, brandom_led(1000), -1, -1, 256); n--; }
        brandom_led(2); brandom_led(2);
        brandom_led(500); brandom_led(300);
        break; }
    case 2: {
        rockyground(10, 1, 0);
        n = albedo + brandom_led(100);
        while (n) {
            { float t_h = (float)(brandom_led(50) + 10);
              int t_r = brandom_led(100) + 50;
              int t_cz = brandom_led(200);
              int t_cx = brandom_led(200);
              round_hill(t_cx, t_cz, t_r, t_h, 0.0f, 1); }
            n--;
        }
        if (brandom_led(2) == 0) {
            n = albedo + brandom_led(200) - brandom_led(100);
            hf = (float)((ld)brandom_led(10) * 0.02);
            if (n < 0) n = 0;
            while (n) {
                cx = brandom_led(256); cz = brandom_led(256);
                cr = brandom_led(8) + 8;
                if (brandom_led(2)) std_crater(txtr, cx, cz, -cr, 31, hf, 1.0f, 256);
                else std_crater(txtr, cx, cz, cr, 31, hf, 1.0f, 256);
                n--;
            }
        } else {
            n = albedo + brandom_led(500);
            { int ptr = brandom_led(2000);
              while (n) { srf_darkline(txtr, brandom_led(ptr), -1, -1, 256); n--; } }
        }
        brandom_led(500); brandom_led(2); brandom_led(150);
        break; }
    case 4: {
        { i16 t_lvl = (i16)(-brandom_led(5));
          int t_rnd = 3 + brandom_led(3);
          rockyground(15, t_rnd, t_lvl); }
        n = brandom_led(15);
        while (n) {
            float fl1, fl2;
            hf = (float)(brandom_led(15) + 7);
            fl1 = (float)((ld)(float)brandom_led(32767) * 0.000030518);
            hr = (float)((ld)hf * ((ld)fl1 * 3.5 + 3.5));
            fl2 = (float)((ld)(float)brandom_led(32767) * 0.000030518);
            ht = (float)((ld)hr * ((ld)fl2 * 0.2 + 0.3));
            if (ht > 127) ht = 127;
            { int t_cz = brandom_led(200);
              int t_cx = brandom_led(200);
              round_hill(t_cx, t_cz, (unsigned)ftol32((ld)hf), hr, ht, 0); }
            n--;
        }
        smoothterrain(1 + brandom_led(2));
        n = 64 - albedo;
        hf = 0.25f;
        while (n) {
            cx = brandom_led(150) + 25; cz = brandom_led(150) + 25;
            cr = brandom_led(10) + 15;
            std_crater(txtr, cx, cz, -cr, 31, hf, 1.0f, 256);
            n--;
        }
        brandom_led(200); brandom_led(2); brandom_led(200);
        break; }
    case 5: {
        if (brandom_led(2)) {
            n = 5 + brandom_led(10);
            if (albedo > 48) n /= 2;
            rockyground(n, 1, 0);
        } else {
            n = 15 + brandom_led(32);
            if (albedo > 48) n /= 2;
            rockyground(n, 1, (i16)(-brandom_led(24)));
        }
        n = brandom_led(68) - albedo;
        if (n > 10) n = 10;
        if (n < 1) n = 1;
        while (n) {
            hf = (float)((ld)brandom_led(5) * 0.015);
            hr = (float)((ld)(brandom_led(10) + 10) * 0.27);
            { int t_r = brandom_led(35) + 5;
              int t_cz = brandom_led(200);
              int t_cx = brandom_led(200);
              std_crater(smap, t_cx, t_cz, t_r, 127, hf, hr, 200); }
            n--;
        }
        brandom_led(400); brandom_led(250); brandom_led(2);
        if (albedo > 40 && albedo <= 50) {
            brandom_led(2); brandom_led(5); brandom_led(5);
            hf = (float)((ld)brandom_led(5) * 0.01);
            hr = (float)((ld)(brandom_led(5) + 5) * 0.5);
            { int t_r = 100 + brandom_led(10);
              int t_cz = 90 + brandom_led(20);
              int t_cx = 90 + brandom_led(20);
              std_crater(smap, t_cx, t_cz, t_r, 127, hf, hr, 200); }
        }
        { int ptr = brandom_led(1500) + 500;
          n = albedo * 5;
          while (n) { srf_darkline(txtr, brandom_led(ptr), -1, -1, 256); n--; } }
        break; }
    case 7: {
        rockyground(10 - (albedo / 8), 0, (i16)(20 + brandom_led(100)));
        n = albedo - brandom_led(albedo) + 10;
        while (n) {
            felisian_srf_darkline(smap, brandom_led(500), -1, -1, 200);
            n--;
        }
        n = albedo + brandom_led(200) - brandom_led(100);
        if (n < 0) n = 0;
        while (n) {
            cx = brandom_led(192) + 32; cz = brandom_led(192) + 32;
            cr = brandom_led(16) + 16;
            std_crater(txtr, cx, cz, -cr, 31, 0.15f, 1.0f, 256);
            n--;
        }
        n = (albedo + brandom_led(100) - brandom_led(50)) / 2;
        if (n < 0) n = 0;
        while (n) {
            { int t_zt = -brandom_led(2);
              int t_xt = -brandom_led(2);
              int t_len = brandom_led(100);
              srf_darkline(txtr, t_len, t_xt, t_zt, 256); }
            n--;
        }
        brandom_led(400); brandom_led(200); brandom_led(2);
        break; }
    case 8: {
        if (albedo < 20) {
            int ptr = 100 - albedo;
            while (ptr) {
                hr = (float)brandom_led(300);
                { int t_r = brandom_led(5) + 2;
                  int t_cz = brandom_led(150) + 25;
                  int t_cx = brandom_led(150) + 25;
                  round_hill(t_cx, t_cz, t_r, hr + 1, 127, 0); }
                ptr--;
            }
            smoothterrain(2 + brandom_led(3));
        }
        { int ptr = (100 - albedo) * 2;
          while (ptr) {
              { float t_h = (float)(brandom_led(25) + 1);
                int t_r = brandom_led(25) + 1;
                int t_cz = brandom_led(200);
                int t_cx = brandom_led(200);
                round_hill(t_cx, t_cz, t_r, t_h, 0.0f, 1); }
              ptr--;
          }}
        brandom_led(300); brandom_led(300); brandom_led(2);
        if (albedo > 40) {
            brandom_led(2);
            smoothterrain(1 + brandom_led(10));
        }
        break; }
    }
}

/* ---- post-switch :2583-2599 — felisian crevasses + smoothing ------- */

static int g_liquid_water = 0;

static void post_switch(void)
{
    int n = brandom_led(5);
    if (n) {
        while (n) {
            felisian_srf_darkline(smap, brandom_led(500), -1, -1, 200);
            n--;
        }
        { i32 i;
          for (i = 200; i < 38800; i++) {
              int v = smap[i] + smap[i-1] + smap[i+1] + smap[i-200] + smap[i+200];
              smap[i] = (unsigned char)(v / 5);
          }}
    }
}

/* ---- objectschart inclination :2606-2615 --------------------------- */

static void objects_inclination(void)
{
    i32 i;
    for (i = 0; i < OC_BYTES; i++) {
        int v1 = (i+1 < PS_BYTES) ? smap[i+1] : 0;
        int v2 = (i+200 < PS_BYTES) ? smap[i+200] : 0;
        int incl = abs((int)smap[i] - v1) + abs((int)smap[i] - v2);
        unsigned nr = 0;
        if (incl < 20) nr = (unsigned)brandom_led(2);
        if (incl < 15) nr = (unsigned)brandom_led(3);
        if (incl < 10) nr = (unsigned)brandom_led(4);
        objs[i] = (objs[i] & 0xFC) | (nr & 3);
    }
}

/* ---- the build_surface prologue :1974-2053 -------------------------- */

static int build_prologue(i32 gseed, int ip_type, int sctype,
                          int albedo, int latitude)
{
    i16 cz, cx;
    int groundflares = 0;

    fast_srand(gseed);
    bsrand((u16)(gseed & 0xFFFF));

    cz = brandom_led(2);
    cx = brandom_led(100);
    if (cx > 97) groundflares = 2 + (2 * cz);
    if (cx > 45 && cx < 55) {
        if (ip_type == 3 && latitude > 75)
            groundflares = 2 + (2 * cz);
    }

    /* objectschart ROCKS fill — no draws */
    memset(objs, ROCS_BYTE, OC_BYTES);

    /* tree parameters — flandom() draws */
    brandom_led(32767);     /* treepeaking */
    brandom_led(3);         /* rootshade switch */
    brandom_led(30);        /* treeflares switch */
    brandom_led(15);        /* leafflares switch */
    brandom_led(32767);     /* treescaling flandom 1 */
    brandom_led(32767);     /* treescaling flandom 2 */
    brandom_led(32767);     /* treespreads flandom 1 */
    brandom_led(32767);     /* treespreads flandom 2 */
    brandom_led(32767);     /* branchwidth flandom */
    brandom_led(32767);     /* rootheight flandom */

    /* type-3 groundflares bump */
    if (ip_type == 3) {
        if (sctype != 4 && sctype != 3) { /* ICY=4, DESERT=3 */
            if (brandom_led(4))
                groundflares = 8;
        }
    }

    return groundflares;
}

/* ---- plains noise add :2280 ----------------------------------------- */

static void plains_noise_add(void)
{
    i32 i;
    for (i = 0; i < OC_BYTES; i++) {
        int v = smap[i] + (int)(fast_raw(3) & 0xFF);
        if (v > 255) v = 255;
        smap[i] = (unsigned char)v;
    }
}

/* ---- SURFACE.BIN pack ------------------------------------------------ */

static void pack_surface_bin(i16 lon, i16 lat,
                             i32 ax, i32 az, i32 ax2, i32 az2,
                             float px, float py, float pz,
                             float ua, float ub,
                             unsigned char *out)
{
    /* int16 lon at offset 0, int16 lat at offset 2 */
    memcpy(out + 0, &lon, 2);
    memcpy(out + 2, &lat, 2);
    /* int32 atl_x/z/x2/z2 at offsets 4/8/12/16 */
    memcpy(out + 4, &ax, 4);
    memcpy(out + 8, &az, 4);
    memcpy(out + 12, &ax2, 4);
    memcpy(out + 16, &az2, 4);
    /* float32 pos_x/y/z, user_alfa/beta at offsets 20/24/28/32/36 */
    memcpy(out + 20, &px, 4);
    memcpy(out + 24, &py, 4);
    memcpy(out + 28, &pz, 4);
    memcpy(out + 32, &ua, 4);
    memcpy(out + 36, &ub, 4);
}

/* ---- global_surface_seed chop --------------------------------------- */

static i32 gseed_chop(double ray, float orb_ray, float orb_orient)
{
    /* (long)((ray + orb_ray + orb_orient) * 4112)
       All arithmetic in long double (x87 extended). */
    ld s = (ld)ray + (ld)orb_ray + (ld)orb_orient;
    ld p = s * (ld)4112.0;
    return ftol32(p);
}

/* ==================================================================== */
/* main                                                                 */
/* ==================================================================== */

int main(int argc, char **argv)
{
    FILE *fi, *fo;
    char line[512];
    set_cw(0x133F);
    if (argc < 3) {
        fprintf(stderr, "usage: gr_ref corpus.txt out.bin\n");
        return 2;
    }
    fi = fopen(argv[1], "r");
    fo = fopen(argv[2], "wb");
    if (!fi || !fo) { perror("open"); return 2; }

    while (fgets(line, sizeof line, fi)) {
        int kind;
        if (line[0] == '#' || line[0] == '\n') continue;
        kind = atoi(line);
        if (kind == 0) continue;

        if (kind == 1) {
            /* sbbin: pack 40 bytes */
            i16 lon, lat;
            i32 ax, az, ax2, az2;
            double px, py, pz, ua, ub;
            unsigned char buf[40];
            float fpx, fpy, fpz, fua, fub;
            sscanf(line, "1 %hd %hd %d %d %d %d %lg %lg %lg %lg %lg",
                   &lon, &lat, &ax, &az, &ax2, &az2,
                   &px, &py, &pz, &ua, &ub);
            fpx = (float)px; fpy = (float)py; fpz = (float)pz;
            fua = (float)ua; fub = (float)ub;
            pack_surface_bin(lon, lat, ax, az, ax2, az2,
                             fpx, fpy, fpz, fua, fub, buf);
            fwrite(buf, 1, 40, fo);
        } else if (kind == 2) {
            /* seed: chop */
            double ray, orbray, orb;
            i32 result;
            sscanf(line, "2 %lg %lg %lg", &ray, &orbray, &orb);
            result = gseed_chop(ray, (float)orbray, (float)orb);
            fwrite(&result, 4, 1, fo);
        } else if (kind == 3) {
            /* build: prologue + rockyground + optional noise */
            i32 gseed;
            int ip_type, sctype, albedo, latitude;
            int roughness, rounding, level, plains_noise;
            u32 rec[4];

            sscanf(line, "3 %d %d %d %d %d %d %d %d %d",
                   &gseed, &ip_type, &sctype, &albedo, &latitude,
                   &roughness, &rounding, &level, &plains_noise);

            fast_n = brtl_n = 0;
            fast_h = brtl_h = FNV_OFF;
            fast_h = brtl_h = FNV_OFF;
            reset_buffers();

            build_prologue(gseed, ip_type, sctype, albedo, latitude);

            /* Re-seed for the painters. */
            fast_srand(gseed);
            bsrand((u16)(gseed & 0xFFFF));

            the_switch(ip_type, sctype, albedo);

            /* post-switch: felisian crevasses + smoothing + inclination */
            g_liquid_water = 0;
            post_switch();
            objects_inclination();
            if (g_liquid_water) {
                i32 i;
                for (i = 0; i < OC_BYTES; i++)
                    if (!smap[i]) objs[i] &= 0xFC;
            }

            if (plains_noise)
                plains_noise_add();

            fwrite(smap, 1, PS_BYTES, fo);
            fwrite(objs, 1, OC_BYTES, fo);
            rec[0] = (u32)fast_n; rec[1] = (u32)brtl_n;
            rec[2] = fast_h; rec[3] = brtl_h;
            fwrite(rec, 4, 4, fo);
            fprintf(stderr, "build %ld: fast=%ld brtl=%ld fh=%u bh=%u\n",
                    (long)gseed, fast_n, brtl_n, fast_h, brtl_h);
        }
    }
    fclose(fi);
    fclose(fo);
    return 0;
}
