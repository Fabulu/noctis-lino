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

static void reset_buffers(void)
{
    memset(smap, 0, PS_BYTES);
    memset(objs, 0, OC_BYTES);
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
            reset_buffers();

            build_prologue(gseed, ip_type, sctype, albedo, latitude);

            /* Re-seed for the painters.  In the real game this is
               landing_pt_lat * landing_pt_lon (:2051-2052); here we re-seed
               from gseed to keep the corpus self-contained — the painter
               algorithm is what is under test, not the seed derivation. */
            fast_srand(gseed);
            bsrand((u16)(gseed & 0xFFFF));

            rockyground(roughness, rounding, (i16)level);

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
