/* grv_ref.c -- Wave 7b C oracle for the Noctis-IV ground renderer.
 *
 * PROVENANCE
 * ----------
 * Transliterated from C:\programmieren\noctis\niv-plus\source\NOCTIS-1.CPP
 * (hpoint :63-93).  NOT derived from work/walk.txt (the lino port) and NOT
 * from grv_spec.py (the Python spec): both are written from the same DOS
 * text in separate passes and compared, never merged.
 *
 * FLOAT MODEL
 * -----------
 * long double is the 80-bit x87 format on x86-64 MinGW, so every live value
 * is rounded to a 64-bit significand by hardware - exactly what Borland's
 * x87 does.  The original narrows to float32 ONLY on assignment to a `float`
 * variable (h1..h4, icx, icz, py); those casts are written explicitly here as
 * (float).  The integer->float conversions of `-((long)s<<11)` are exact for
 * every surf byte (<= 522240, well inside float32's 24-bit range), so the
 * narrow points that matter are the two stores to `py`.
 *
 * m200[k] = k*200 (NOCTIS-0.CPP:1029, "numeri da 0 a 199, moltiplicati per
 * 200").  qid = 1.0/16384 (NOCTIS-0.CPP:1042, a DOUBLE).
 *
 * Build:  gcc -O2 -fno-fast-math -o grv_ref.exe grv_ref.c
 * Usage:  grv_ref.exe corpus.txt out.bin
 *   corpus line:  px pz s1 s2 s3 s4      (six signed decimals)
 *   out record :  one int32 per case = the binary32 bit pattern of py
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
typedef long double ld;

/* m200[k] = k*200, k = 0..199 (NOCTIS-0.CPP:1029). */
static u32 m200[200];
static void init_m200(void) { int k; for (k = 0; k < 200; k++) m200[k] = (u32)(k * 200); }

/* qid = 1.0/16384, declared DOUBLE in the original. */
static const ld QID = 1.0L / 16384.0L;

/* The 200x200 altimetry.  Exactly 40,000 bytes (WAVE7B_PLAN).  hpoint reads
 * four bytes per call: cpos, cpos+1, cpos+200, cpos+201.  Row/col are pinned
 * to 0..198 in the corpus so all four corners stay in-bounds - the honest,
 * in-game-reachable subset (iperifie never walks the far edge under feet). */
#define SURF_BYTES 40000
static unsigned char surf[SURF_BYTES];

static i32 surf_at(long o) { return (long)surf[(u32)o]; }

/* hpoint - NOCTIS-1.CPP:63-93.  Returns py's binary32 bit pattern as i32. */
static i32 hpoint_bits(long px, long pz)
{
    long cpos;
    ld h1, h2, h3, h4, icx, icz, py;
    i32 out;

    cpos = (long)m200[(u32)(pz >> 14) & 0xFFFFu] + (long)(px >> 14);

    /* h1..h4 are float in the source; the (long)<<11 is exact, and the
     * negation is exact, so the (float) cast loses nothing for surf<=255.
     * Modelled as (float) then widened back to ld for the chain. */
    h1 = (ld)(float)(-((long)surf_at(cpos)     << 11));
    h2 = (ld)(float)(-((long)surf_at(cpos + 1) << 11));
    h3 = (ld)(float)(-((long)surf_at(cpos + 201) << 11));
    h4 = (ld)(float)(-((long)surf_at(cpos + 200) << 11));

    /* icx,icz are float (assigned from `px & 16383`, a long). */
    icx = (ld)(float)(px & 16383);
    icz = (ld)(float)(pz & 16383);

    /* The branch test `icx+icz<16384` is float+float compared to int; both
     * operands are integers < 16384 so the sum is exact and the decision is
     * deterministic - no float tolerance touches it. */
    if (icx + icz < 16384.0L) {
        /* py = h1 + (h2-h1)*(icx*qid);  py += (h4-h1)*(icz*qid);
         * icx*qid is double (float promoted to double); the whole RHS is
         * double; narrowing to float happens ONLY at the py store. */
        py = h1 + (h2 - h1) * (icx * QID);
        py = (ld)(float)py + (h4 - h1) * (icz * QID);   /* py += ... */
    } else {
        py = h3 + (h4 - h3) * ((16384.0L - icx) * QID);
        py = (ld)(float)py + (h2 - h3) * ((16384.0L - icz) * QID);
    }
    {   float f = (float)py;
        memcpy(&out, &f, 4);
    }
    return out;
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
        long px, pz, s1, s2, s3, s4;
        i32 bits;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%ld %ld %ld %ld %ld %ld",
                   &px, &pz, &s1, &s2, &s3, &s4) != 6) continue;
        memset(surf, 0, sizeof surf);
        {   long cpos = (long)m200[(u32)(pz >> 14) & 0xFFFFu] + (long)(px >> 14);
            long o;
            if ((u32)cpos < SURF_BYTES) surf[(u32)cpos] = (unsigned char)s1;
            o = cpos + 1;   if ((u32)o < SURF_BYTES) surf[(u32)o] = (unsigned char)s2;
            o = cpos + 201; if ((u32)o < SURF_BYTES) surf[(u32)o] = (unsigned char)s3;
            o = cpos + 200; if ((u32)o < SURF_BYTES) surf[(u32)o] = (unsigned char)s4;
        }
        bits = hpoint_bits(px, pz);
        fwrite(&bits, 4, 1, fo);
    }
    fclose(fi); fclose(fo);
    return 0;
}
