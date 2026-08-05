/* brtl_oracle.c - C reference for Borland C++ 3.1's rand/random/srand,
 * the LCG that lays out every star system in Noctis IV.
 *
 * PROVENANCE, WHICH IS THE WHOLE POINT: this file is transcribed from
 *     C:\programmieren\noctis\niv-lr\src\brtl.cpp
 * a third party's independent reading of the game, made without reference
 * to us.  Its companion, brtl_oracle.py, is transcribed from the DOS
 * machine code in NOCTIS.EXE instead, and emulates the 0x3E19 long-multiply
 * helper instruction by instruction.  Neither file may be derived from the
 * other; that is what makes agreement between them evidence rather than
 * a tautology.
 *
 * niv-lr, verbatim:
 *
 *     static int32_t brtl_seed = 1;
 *     void    brtl_srand(uint16_t seed) { brtl_seed = seed; }
 *     int16_t brtl_rand() {
 *         brtl_seed = brtl_seed * ((int32_t) 0x015a4e35) + 1;
 *         return (int16_t) (brtl_seed >> 16) & 0x7FFF;
 *     }
 *     int16_t brtl_random(int16_t num) {
 *         return (int16_t) (((int32_t) brtl_rand() * num)
 *                           / (((uint16_t) 0x7FFF) + 1));
 *     }
 *
 * Two deliberate departures from that text, both to remove undefined
 * behaviour from the REFERENCE rather than to change the semantics:
 *
 *   1. The state is uint32_t here, not int32_t.  The multiply overflows on
 *      essentially every call, and signed overflow is UB in C - an oracle
 *      that is itself UB proves nothing.  Unsigned wrap is the defined
 *      spelling of the same low-32 truncation the 8086 helper performs.
 *      Signedness of the multiply is unobservable in a low-32 product.
 *
 *   2. The divide is done on an int32_t product with the C99 rule that
 *      integer division truncates TOWARD ZERO.  This is the one place the
 *      whole port can be silently wrong: >>15 floors instead, which agrees
 *      for every non-negative num and disagrees for essentially every
 *      negative one.  Negative num is reachable through zrandom().
 *
 * Both departures are CHECKED at runtime, not asserted in a comment:
 *   - extract_nivlr() reproduces niv-lr's int16 cast + mask literally and
 *     is compared against the uint32 form on every single draw;
 *   - the 32x32 product in brtl_random is computed in int64_t and the
 *     truncation to 32 bits is verified to be lossless on every draw,
 *     which proves the "no narrowing needed" lemma over the whole int16
 *     argument domain rather than arguing for it.
 *
 * Emits the four Wave 1 lanes in the binding interchange format:
 *   header: 8 units, WRITTEN LAST, little-endian uint32
 *     u0 0x42525431 "BRT1"  u1 lane  u2 N1  u3 N2
 *     u4 records=N1*N2      u5 2     u6 records*2  u7 0x0DEFACED
 *   payload from byte 32: per record (value, state_after), 2 units.
 *
 * usage: brtl_oracle.exe <outdir> [suffix]      default suffix "-c"
 *        writes <outdir>/brtl-sweep<suffix>.bin  and the other three.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define MULT       0x015A4E35u
#define MAGIC      0x42525431u
#define SENTINEL   0x0DEFACEDu
#define DIVISOR    0x8000

/* ------------------------------------------------------------------ core */

static uint32_t brtl_seed = 1;          /* initial state, read out of the
                                         * shipped NOCTIS.EXE at DS:395A */

static int      lemma_violations = 0;   /* narrowing lemma  (must stay 0) */
static int      extract_violations = 0; /* niv-lr equivalence (must stay 0) */

/* niv-lr's extraction, spelled exactly as it is written there.  Kept as a
 * separate pure function so it can be diffed against the uint32 form. */
static int extract_nivlr(uint32_t state) {
    int32_t s = (int32_t) state;        /* niv-lr's int32_t brtl_seed */
    return (int16_t) (s >> 16) & 0x7FFF;
}

/* srand as the DOS binary spells it: the argument is a 16-bit int and the
 * high word of the state is EXPLICITLY stored as zero (c7 06 5c 39 00 00).
 * Zero-extend, never sign-extend. */
static void brtl_srand(uint16_t seed) {
    brtl_seed = (uint32_t) seed;
}

/* The same thing reached from a full 32-bit argument, which is what the
 * L.in.oleum port receives (lino has no 16-bit parameter to truncate it for
 * us).  Lane 4 exists to prove this mask is present on the lino side. */
static void brtl_srand_raw(uint32_t arg) {
    brtl_seed = arg & 0xFFFFu;
}

static void brtl_setstate(uint32_t state) {   /* lane 2 only; not a game API */
    brtl_seed = state;
}

static int32_t brtl_rand(void) {
    int a, b;
    brtl_seed = brtl_seed * MULT + 1u;        /* low 32 bits only */
    a = (int) ((brtl_seed >> 16) & 0x7FFFu);
    b = extract_nivlr(brtl_seed);
    if (a != b) { extract_violations++; }
    return (int32_t) a;
}

static int32_t brtl_random(int16_t num) {
    int32_t r = brtl_rand();                  /* [0, 32767], always drawn */
    int64_t wide = (int64_t) r * (int64_t) num;
    int32_t p = (int32_t) wide;               /* the low-32 product */
    int32_t q;

    if ((int64_t) p != wide) { lemma_violations++; }   /* provably never */

    q = p / DIVISOR;                          /* SIGNED, truncates to zero */

    if ((int32_t) (int16_t) q != q) { lemma_violations++; }  /* no narrowing */
    return q;
}

/* --------------------------------------------------------------- emitting */

typedef struct {
    uint32_t *buf;      /* records*2 units */
    uint32_t  records;
    uint32_t  fill;     /* units written so far */
} Lane;

static void lane_init(Lane *L, uint32_t records) {
    L->records = records;
    L->fill = 0;
    L->buf = (uint32_t *) malloc((size_t) records * 2u * sizeof(uint32_t));
    if (!L->buf) { fprintf(stderr, "out of memory\n"); exit(1); }
}

static void emit(Lane *L, int32_t value, uint32_t state) {
    L->buf[L->fill++] = (uint32_t) value;     /* two's complement for lane 3 */
    L->buf[L->fill++] = state;
}

static int lane_write(Lane *L, const char *path, uint32_t lane,
                      uint32_t n1, uint32_t n2) {
    uint32_t hdr[8];
    FILE *f;

    if (L->fill != L->records * 2u) {
        fprintf(stderr, "%s: filled %u units, expected %u\n",
                path, L->fill, L->records * 2u);
        return 1;
    }

    f = fopen(path, "wb");
    if (!f) { perror(path); return 1; }

    /* Payload first, header last - the same sequencing the lino side uses,
     * so that a file graded by mtime is complete when it is seen. */
    if (fseek(f, 32L, SEEK_SET) != 0) { perror("fseek"); fclose(f); return 1; }
    if (fwrite(L->buf, sizeof(uint32_t), L->fill, f) != L->fill) {
        perror("fwrite payload"); fclose(f); return 1;
    }

    hdr[0] = MAGIC;
    hdr[1] = lane;
    hdr[2] = n1;
    hdr[3] = n2;
    hdr[4] = L->records;
    hdr[5] = 2u;
    hdr[6] = L->records * 2u;
    hdr[7] = SENTINEL;

    if (fseek(f, 0L, SEEK_SET) != 0) { perror("fseek 0"); fclose(f); return 1; }
    if (fwrite(hdr, sizeof(uint32_t), 8, f) != 8) {
        perror("fwrite header"); fclose(f); return 1;
    }
    fclose(f);

    printf("  %-40s lane %u  %8u records  %10lu bytes\n",
           path, lane, L->records, (unsigned long) (32u + L->records * 8u));
    free(L->buf);
    L->buf = NULL;
    return 0;
}

/* ------------------------------------------------------------------ lanes */

/* lane 2 family table, fixed by fiat so both sides derive the same input
 * from the index alone. */
static const uint32_t FAM[5] = { 0x0000u, 0x0001u, 0x7FFFu, 0x8000u, 0xFFFFu };

/* lane 3 seeds */
static const uint32_t L3SEED[4] = { 0u, 1u, 12345u, 65535u };

/* lane 4 high halves; FFFF and 8000 carry the sign bit, C5A1 is arbitrary */
static const uint32_t L4HIGH[4] = { 0x0000u, 0xFFFFu, 0x8000u, 0xC5A1u };

static int lane1(const char *path) {          /* 65536 seeds x 16 draws */
    Lane L; uint32_t seed; int d;
    lane_init(&L, 65536u * 16u);
    for (seed = 0; seed < 65536u; seed++) {
        brtl_srand((uint16_t) seed);
        for (d = 0; d < 16; d++) {
            int32_t v = brtl_rand();
            emit(&L, v, brtl_seed);
        }
    }
    return lane_write(&L, path, 1u, 65536u, 16u);
}

static int lane2(const char *path) {          /* 10 families x 65536 states */
    Lane L; uint32_t f, j, st; int32_t v;
    lane_init(&L, 10u * 65536u);
    for (f = 0; f < 10u; f++) {
        for (j = 0; j < 65536u; j++) {
            if (f < 5u) { st = (j << 16) | FAM[f]; }
            else        { st = (FAM[f - 5u] << 16) | j; }
            brtl_setstate(st);
            v = brtl_rand();
            emit(&L, v, brtl_seed);
        }
    }
    return lane_write(&L, path, 2u, 10u, 65536u);
}

static int lane3(const char *path) {          /* all 65536 int16 n */
    Lane L; uint32_t k; int si, d;
    lane_init(&L, 65536u * 8u);
    for (k = 0; k < 65536u; k++) {
        /* sign-extend k to 16-bit signed, spelled out rather than trusting
         * an implementation-defined narrowing conversion */
        int32_t wide = (k & 0x8000u) ? (int32_t) k - 65536 : (int32_t) k;
        int16_t n = (int16_t) wide;
        if ((int32_t) n != wide) { fprintf(stderr, "int16 range\n"); return 1; }
        for (si = 0; si < 4; si++) {
            brtl_srand((uint16_t) L3SEED[si]);
            for (d = 0; d < 2; d++) {
                int32_t v = brtl_random(n);
                emit(&L, v, brtl_seed);
            }
        }
    }
    return lane_write(&L, path, 3u, 65536u, 8u);
}

static int lane4(const char *path) {          /* the srand mask */
    Lane L; uint32_t j; int h;
    lane_init(&L, 65536u * 4u);
    for (j = 0; j < 65536u; j++) {
        for (h = 0; h < 4; h++) {
            int32_t v;
            brtl_srand_raw((L4HIGH[h] << 16) | j);
            v = brtl_rand();
            emit(&L, v, brtl_seed);
        }
    }
    return lane_write(&L, path, 4u, 65536u, 4u);
}

/* ------------------------------------------------------------------- main */

int main(int argc, char **argv) {
    const char *dir = (argc > 1) ? argv[1] : ".";
    const char *sfx = (argc > 2) ? argv[2] : "-c";
    char p[1024];
    int rc = 0;
    int i;

    /* Cheap self-checks on the primitives before 20 MB is committed to disk. */
    {
        static const int32_t GOLD1[10] = {
            346, 130, 10982, 1090, 11656, 7117, 17595, 6415, 22948, 31126
        };
        brtl_srand(1);
        for (i = 0; i < 10; i++) {
            int32_t v = brtl_rand();
            if (v != GOLD1[i]) {
                fprintf(stderr, "srand(1) draw %d: got %ld want %ld\n",
                        i, (long) v, (long) GOLD1[i]);
                return 2;
            }
        }
        /* state 0 -> 0*M+1 = 1, whose high half is 0: srand(0) must be
         * srand(1) shifted by exactly one draw. */
        brtl_srand(0);
        if (brtl_rand() != 0) { fprintf(stderr, "srand(0) draw 0 != 0\n"); return 2; }
        for (i = 0; i < 9; i++) {
            if (brtl_rand() != GOLD1[i]) {
                fprintf(stderr, "srand(0) is not srand(1) shifted\n"); return 2;
            }
        }
        /* the sign of the divide */
        brtl_srand(1);
        if (brtl_random(0) != 0) { fprintf(stderr, "random(0) != 0\n"); return 2; }
        if (brtl_seed == 1u) { fprintf(stderr, "random(0) did not draw\n"); return 2; }
        brtl_srand(1);
        for (i = 0; i < 64; i++) {
            int32_t v = brtl_random(-10);
            if (v > 0 || v <= -10) {
                fprintf(stderr, "random(-10) = %ld, outside (-10, 0]\n", (long) v);
                return 2;
            }
        }
    }

    printf("brtl_oracle (C, from niv-lr/src/brtl.cpp)\n");

    sprintf(p, "%s/brtl-sweep%s.bin", dir, sfx); rc |= lane1(p);
    sprintf(p, "%s/brtl-step%s.bin",  dir, sfx); rc |= lane2(p);
    sprintf(p, "%s/brtl-rand%s.bin",  dir, sfx); rc |= lane3(p);
    sprintf(p, "%s/brtl-srand%s.bin", dir, sfx); rc |= lane4(p);

    printf("  narrowing-lemma violations   : %d\n", lemma_violations);
    printf("  niv-lr extraction mismatches : %d\n", extract_violations);
    if (lemma_violations || extract_violations) { return 3; }
    return rc;
}
