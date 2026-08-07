/* grv_ref.c -- Wave 7b C oracle for the Noctis-IV ground renderer.
 *
 * PROVENANCE
 * ----------
 * Transliterated from C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP
 *   hpoint   :63-93
 *   fragment :1028-1142  (the ground-tile vertex + depth + c1 path)
 * and NOCTIS-0.CPP:1075-1107 (fast_srand/fast_random), NOCTIS-0.CPP:1029/1042
 * (m200, qid).  NOT derived from work/walk.txt or grv_spec.py: separate
 * transliterations, compared and never merged.
 *
 * FLOAT MODEL
 * -----------
 * long double is the 80-bit x87 format; every live value is rounded to a
 * 64-bit significand by hardware, exactly what Borland's x87 does under
 * FEnter's 133Fh.  Narrowing to float32 happens ONLY on assignment to a
 * `float` variable (h1..h4 in hpoint; dx/dz/hpdep in fragment); those casts
 * are written explicitly as (float).  fragment's depth is the EXACT-REQUIRED
 * chop `depth = (long)(hpdep) >> 14` (WAVE7B_PLAN float site #1) - modelled
 * here by the C (long) cast, which truncates toward zero, then >>14.
 *
 * fragment's six vy corner heights and c1 are INTEGER outputs (-(surf<<11)
 * is exact in float32; c1 is integer shade), so they are graded as integers.
 * The float computation lives in depth (sqrt + chop), which both sides model.
 *
 * OUTPUT: each corpus row carries an opcode:
 *   op 1 (hpoint):    px pz s1 s2 s3 s4                 -> py binary32 bits
 *   op 2 (fragment):  x z posx posz s1 s2 s3 s4 shd ssh seed branch
 *                     -> 8 ints: depth, vy0..vy5, c1
 * The dump is opcode-prefixed (9 words/case): [op, v0..v7] (hpoint pads).
 *
 * Build:  gcc -O2 -fno-fast-math -o grv_ref.exe grv_ref.c -lm
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

typedef int16_t  i16;
typedef uint16_t u16;
typedef int32_t  i32;
typedef uint32_t u32;
typedef uint64_t u64;
typedef long double ld;

static u32 m200[200];
static void init_m200(void) { int k; for (k = 0; k < 200; k++) m200[k] = (u32)(k * 200); }
static const ld QID = 1.0L / 16384.0L;

#define SURF_BYTES 40000
static unsigned char surf[SURF_BYTES];

/* ---- fast_random LCG (NOCTIS-0.CPP:1075-1107) ---- */
static u32 flat_rnd_seed;
static void fast_srand(i32 seed) {
    u32 s = (u32)seed;
    flat_rnd_seed = (s & 0xFFFF0000u) | ((s & 0xFFFFu) | 3u);
}
static u32 fast_random(u32 mask) {
    u64 p = (u64)flat_rnd_seed * (u64)flat_rnd_seed;
    u32 eax = (u32)p, edx = (u32)(p >> 32);
    unsigned char al = (unsigned char)((eax & 0xFF) + (edx & 0xFF));
    eax = (eax & 0xFFFFFF00u) | al;
    flat_rnd_seed += eax;
    return eax & mask;
}

static i32 hpoint_bits(long px, long pz)
{
    long cpos = (long)m200[(u32)(pz >> 14)] + (long)(px >> 14);
    ld h1, h2, h3, h4, icx, icz, py;
    i32 out;
    h1 = (ld)(float)(-((long)surf[cpos]       << 11));
    h2 = (ld)(float)(-((long)surf[cpos + 1]   << 11));
    h3 = (ld)(float)(-((long)surf[cpos + 201] << 11));
    h4 = (ld)(float)(-((long)surf[cpos + 200] << 11));
    icx = (ld)(float)(px & 16383);
    icz = (ld)(float)(pz & 16383);
    if (icx + icz < 16384.0L) {
        py = h1 + (h2 - h1) * (icx * QID);
        py = (ld)(float)py + (h4 - h1) * (icz * QID);
    } else {
        py = h3 + (h4 - h3) * ((16384.0L - icx) * QID);
        py = (ld)(float)py + (h2 - h3) * ((16384.0L - icz) * QID);
    }
    { float f = (float)py; memcpy(&out, &f, 4); }
    return out;
}

/* fragment: grades depth (exact chop), six vy corner heights (int), c1 (int).
 * FAITHFUL surf reads: vy and c1 read p_surfacemap at h1, h1+1, h1+200,
 * h1+201, h1+sh_delta.  The caller has already placed s1..s4 + ssh into surf
 * (ssh LAST, so it overwrites a corner when sh_delta coincides with one -
 * exactly what the real fragment sees).  out[0]=depth, out[1..6]=vy, out[7]=c1. */
static void fragment_case(long x, long z, i32 posx_bits, i32 posz_bits,
                          long shd, long seed, long branch, i32 *out)
{
    float posx, posz;
    float dx, dz, hpdep;
    long vx0, vx1, vz0, vz2;
    float fvx0, fvx1, fvz0, fvz2;
    long depth, h1, c1;
    long b1, b2, b3, b4, bsh;
    memcpy(&posx, &posx_bits, 4);
    memcpy(&posz, &posz_bits, 4);

    vx0 = x << 14; vx1 = (x + 1) << 14; vz0 = z << 14; vz2 = (z + 1) << 14;
    fvx0 = (float)vx0; fvx1 = (float)vx1; fvz0 = (float)vz0; fvz2 = (float)vz2;

    {   ld half = ((ld)fvx0 + (ld)fvx1) * 0.5L;
        dx = (float)((ld)posx - half);
    }
    {   ld half = ((ld)fvz0 + (ld)fvz2) * 0.5L;
        dz = (float)((ld)posz - half);
    }
    {   ld dd = (ld)dx * (ld)dx + (ld)dz * (ld)dz;
        hpdep = (float)sqrtl(dd);
    }
    depth = ((long)hpdep) >> 14;
    depth -= 1; if (depth < 0) depth = 0;

    h1 = x + z * 200;
    b1  = (long)surf[(u32)(h1)];
    b2  = (long)surf[(u32)(h1 + 1)];
    b4  = (long)surf[(u32)(h1 + 200)];
    b3  = (long)surf[(u32)(h1 + 201)];
    bsh = (long)surf[(u32)(h1 + shd)];
    out[1] = -(b1 << 11);   /* vy1[0] = h1   */
    out[2] = -(b2 << 11);   /* vy1[1] = h1+1 */
    out[3] = -(b4 << 11);   /* vy1[2] = h4   */
    out[4] = -(b2 << 11);   /* vy2[0] = h2   */
    out[5] = -(b3 << 11);   /* vy2[1] = h3   */
    out[6] = -(b4 << 11);   /* vy2[2] = h4   */

    if (branch == 0) { fast_srand((i32)(h1 + seed)); c1 = 8 + (long)fast_random(7); }
    else             { c1 = b1 - bsh; }
    if (c1 < 0) c1 = 0;
    c1 += depth >> 1;
    if (c1 > 32) c1 = 32;

    out[0] = (i32)depth;
    out[7] = (i32)c1;
}

static void place(long cpos, long s1, long s2, long s3, long s4)
{
    long o;
    memset(surf, 0, sizeof surf);
    if ((u32)cpos < SURF_BYTES) surf[(u32)cpos] = (unsigned char)s1;
    o = cpos + 1;   if ((u32)o < SURF_BYTES) surf[(u32)o] = (unsigned char)s2;
    o = cpos + 201; if ((u32)o < SURF_BYTES) surf[(u32)o] = (unsigned char)s3;
    o = cpos + 200; if ((u32)o < SURF_BYTES) surf[(u32)o] = (unsigned char)s4;
}

int main(int argc, char **argv)
{
    FILE *fi, *fo;
    char line[512];
    if (argc < 3) { fprintf(stderr, "usage: grv_ref corpus.txt out.bin\n"); return 2; }
    init_m200();
    fi = fopen(argv[1], "r");
    fo = fopen(argv[2], "wb");
    if (!fi || !fo) { perror("open"); return 2; }
    while (fgets(line, sizeof line, fi)) {
        long op;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%ld", &op) != 1) continue;
        if (op == 1) {
            long px, pz, s1, s2, s3, s4, cpos;
            i32 b;
            sscanf(line, "%*ld %ld %ld %ld %ld %ld %ld",
                   &px, &pz, &s1, &s2, &s3, &s4);
            cpos = (long)m200[(u32)(pz >> 14)] + (long)(px >> 14);
            place(cpos, s1, s2, s3, s4);
            b = hpoint_bits(px, pz);
            { i32 rec[9] = {1, b, 0, 0, 0, 0, 0, 0, 0}; fwrite(rec, 4, 9, fo); }
        } else if (op == 2) {
            long x, z, s1, s2, s3, s4, shd, ssh, seed, branch;
            i32 posx = 0, posz = 0, outv[8];
            unsigned int posxi, poszi;
            sscanf(line, "%*ld %ld %ld %u %u %ld %ld %ld %ld %ld %ld %ld %ld",
                   &x, &z, &posxi, &poszi, &s1, &s2, &s3, &s4,
                   &shd, &ssh, &seed, &branch);
            posx = (i32)posxi; posz = (i32)poszi;
            {   long cpos = x + z * 200;
                long o;
                place(cpos, s1, s2, s3, s4);
                o = cpos + shd; if ((u32)o < SURF_BYTES) surf[(u32)o] = (unsigned char)ssh;
            }
            fragment_case(x, z, posx, posz, shd, seed, branch, outv);
            { i32 rec[9] = {2, outv[0], outv[1], outv[2], outv[3],
                            outv[4], outv[5], outv[6], outv[7]};
              fwrite(rec, 4, 9, fo); }
        } else if (op == 5) {
            /* p_Forward: delta sbn cbn calf px pz -- binary32 bit patterns */
            unsigned int db, sb, cb, ca, pxb, pzb;
            i32 npx, npz;
            float delta, sbn, cbn, calf, px, pz;
            sscanf(line, "%*ld %u %u %u %u %u %u",
                   &db, &sb, &cb, &ca, &pxb, &pzb);
            memcpy(&delta, &db, 4); memcpy(&sbn, &sb, 4);
            memcpy(&cbn, &cb, 4); memcpy(&calf, &ca, 4);
            memcpy(&px, &pxb, 4); memcpy(&pz, &pzb, 4);
            {   ld prodx = (ld)delta * (ld)sbn;      /* left-assoc, as C does */
                prodx = prodx * (ld)calf;
                ld prodz = (ld)delta * (ld)cbn;
                prodz = prodz * (ld)calf;
                float nx = (float)((ld)px - prodx);
                float nz = (float)((ld)pz + prodz);
                memcpy(&npx, &nx, 4); memcpy(&npz, &nz, 4);
            }
            { i32 rec[9] = {5, npx, npz, 0, 0, 0, 0, 0, 0}; fwrite(rec, 4, 9, fo); }
        } else if (op == 6) {
            /* change_angle_of_view: alfa beta dpp -- binary32 bit patterns.
             * Emits pcosbeta, psinbeta, tcosbeta, tsinbeta, pcosalfa, psinalfa,
             * tcosalfa, tsinalfa.  The C source computes the angle beta*deg in
             * DOUBLE (float promoted * double deg), so the arg is the binary64
             * product; sin/cos then run at extended. */
            static const double DDEG = 3.14159265358979323846 / 180.0;
            unsigned int ab, bb, db;
            float alfa, beta, dpp;
            i32 outv[8];
            sscanf(line, "%*ld %u %u %u", &ab, &bb, &db);
            memcpy(&alfa, &ab, 4); memcpy(&beta, &bb, 4); memcpy(&dpp, &db, 4);
            {
                double barg = (double)beta * DDEG, aarg = (double)alfa * DDEG;
                ld sb = sinl((ld)barg), cb = cosl((ld)barg);
                ld sa = sinl((ld)aarg), ca = cosl((ld)aarg);
                float f;
                f = (float)(cb * (ld)dpp); memcpy(&outv[0], &f, 4);
                f = (float)(sb * (ld)dpp); memcpy(&outv[1], &f, 4);
                f = (float)cb;             memcpy(&outv[2], &f, 4);
                f = (float)sb;             memcpy(&outv[3], &f, 4);
                f = (float)(ca * (ld)dpp); memcpy(&outv[4], &f, 4);
                f = (float)(sa * (ld)dpp); memcpy(&outv[5], &f, 4);
                f = (float)ca;             memcpy(&outv[6], &f, 4);
                f = (float)sa;             memcpy(&outv[7], &f, 4);
            }
            { i32 rec[9] = {6, outv[0], outv[1], outv[2], outv[3],
                            outv[4], outv[5], outv[6], outv[7]};
              fwrite(rec, 4, 9, fo); }
        }
    }
    fclose(fi); fclose(fo);
    return 0;
}
