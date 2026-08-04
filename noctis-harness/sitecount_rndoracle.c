/* fast_random oracle, for cross-checking the L.in.oleum port.
 *
 * fast_srand and fast_random below are copied VERBATIM from
 * C:\programmieren\noctis\niv-lr\src\noctis-0.cpp lines 822-845 - a different
 * author's independent de-assembly of the same DOS inline assembly at
 * niv-plus/source/NOCTIS-0.CPP:1086-1101. Nothing in them is adapted, so this
 * file is an independent witness rather than a restatement of my own reading.
 *
 * Compile with -fwrapv: flat_rnd_seed is int32_t and "flat_rnd_seed += eax"
 * overflows it constantly. The DOS original is a 32-bit register add that
 * simply wraps; -fwrapv makes C agree without touching the copied lines.
 *
 *   gcc -O2 -fwrapv -o sitecount_rndoracle.exe sitecount_rndoracle.c
 *   sitecount_rndoracle.exe <out.bin> <draws> <seed> <mask>
 *
 * Output: two little-endian 32-bit units per draw - value, seed after.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

/* ---- verbatim from niv-lr/src/noctis-0.cpp:822-845 ---- */

int32_t flat_rnd_seed;

// Pseudo table selection.
// There are 4,294,967,295 possible tables, and about 20000 elements per table.
void fast_srand(int32_t seed) { flat_rnd_seed = ((uint32_t) seed) | 0x03u; }

// Extraction of a number: "mask" activates the bits.
// This is very sketchy!
int32_t fast_random(int32_t mask) {
    uint32_t eax = flat_rnd_seed;
    uint32_t edx = flat_rnd_seed;

    uint64_t result = ((uint64_t) eax) * ((uint64_t) edx);
    eax             = (result & 0xFFFFFFFFu);
    edx             = ((result >> 32u) & 0xFFFFFFFFu);
    uint8_t al      = (eax & 0xFFu);
    uint8_t dl      = (edx & 0xFFu);
    al += dl;
    eax = (eax & 0xFFFFFF00u) | al;
    flat_rnd_seed += eax;

    int32_t num = eax & ((uint32_t) (mask));
    return num;
}

/* ---- end verbatim ---- */

static void put32(FILE *f, uint32_t v) {
    fputc((int) (v & 0xFFu), f);
    fputc((int) ((v >> 8) & 0xFFu), f);
    fputc((int) ((v >> 16) & 0xFFu), f);
    fputc((int) ((v >> 24) & 0xFFu), f);
}

int main(int argc, char **argv) {
    const char *out = (argc > 1) ? argv[1] : "sitecount-rnd-c.bin";
    long draws = (argc > 2) ? strtol(argv[2], NULL, 0) : 4096;
    long seed = (argc > 3) ? strtol(argv[3], NULL, 0) : 12345;
    long mask = (argc > 4) ? strtol(argv[4], NULL, 0) : 0xFFFF;

    FILE *f = fopen(out, "wb");
    if (!f) {
        fprintf(stderr, "cannot write %s\n", out);
        return 1;
    }

    fast_srand((int32_t) seed);
    for (long i = 0; i < draws; i++) {
        int32_t v = fast_random((int32_t) mask);
        put32(f, (uint32_t) v);
        put32(f, (uint32_t) flat_rnd_seed);
    }
    fclose(f);
    printf("wrote %s: %ld draws, seed=%ld mask=0x%lX\n", out, draws, seed, mask);
    return 0;
}
