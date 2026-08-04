/* oracle.c - ground truth for Noctis IV's galaxy hash.
 *
 * Lifted from noctis-iv-lr src/noctis-0.cpp sky(), lines ~2376-2423, which
 * is itself a translation of the original DOS code's hand-encoded 386
 * instructions (db 0x66 prefixes around imul, with edx:eax folded via
 * "edx += eax").
 *
 * Every sector of space is 100000 units on a side and holds at most one
 * star, whose position is a pure hash of the sector's integer coordinates.
 * There is no star table anywhere - the galaxy is this function.
 *
 * Differences from the in-game version, both deliberate:
 *
 *   1. The game does "continue" the moment a coordinate hashes to exactly
 *      50000 (meaning "no star here"). We compute all three coordinates
 *      unconditionally and report the cutoffs as flag bits instead, so the
 *      arithmetic gets exercised on every sector rather than only on the
 *      ones that happen to hold a star.
 *
 *   2. The rarity_factor gate is omitted. It runs through sqrt() and a
 *      truncation to int16, so it belongs to the floating-point domain and
 *      is tested separately. This file is pure integer, and pure integer is
 *      the part we can demand bit-exactness from.
 *
 * All arithmetic is done in uint32_t so wrapping is well defined; operands
 * are cast to int32_t only where the original takes a SIGNED product. That
 * signedness is load-bearing: sector coordinates go negative, and an
 * unsigned multiply yields a different high word, hence a different galaxy.
 *
 * Output: 5 little-endian int32 per sector - temp_x, temp_y, temp_z,
 * netpos, flags.
 */

#include <stdio.h>
#include <stdint.h>

#define CUTOFF   50000
#define SECTOR   100000
#define KMIN     (-3)
#define KMAX     3

/* One 32x32->64 signed multiply with the high half folded into the low,
 * exactly as the original's imul + "edx += eax" does. */
static uint32_t fold_mul(int32_t a, int32_t b) {
    int64_t  result = (int64_t) a * (int64_t) b;
    uint32_t lo     = (uint32_t) (result & 0xFFFFFFFFu);
    uint32_t hi     = (uint32_t) (result >> 32);
    return hi + lo;
}

int main(void) {
    FILE *out = fopen("oracle.bin", "wb");
    if (!out) { perror("oracle.bin"); return 1; }

    long count = 0;

    for (int32_t kx = KMIN; kx <= KMAX; kx++) {
        for (int32_t ky = KMIN; ky <= KMAX; ky++) {
            for (int32_t kz = KMIN; kz <= KMAX; kz++) {
                int32_t sect_x = kx * SECTOR;
                int32_t sect_y = ky * SECTOR;
                int32_t sect_z = kz * SECTOR;

                uint32_t sum_xz = (uint32_t) sect_x + (uint32_t) sect_z;
                uint32_t flags  = 0;

                uint32_t temp_x = (sum_xz & 0x0001FFFFu) + (uint32_t) sect_x;
                if (temp_x == CUTOFF) { flags |= 1u; }
                temp_x -= CUTOFF;

                uint32_t accum = fold_mul((int32_t) temp_x, (int32_t) sum_xz);

                uint32_t idk = sum_xz + accum;

                uint32_t temp_y = (accum & 0x0001FFFFu) + (uint32_t) sect_y;
                if (temp_y == CUTOFF) { flags |= 2u; }
                temp_y -= CUTOFF;

                accum = fold_mul((int32_t) temp_y, (int32_t) idk);

                uint32_t temp_z = (accum & 0x0001FFFFu) + (uint32_t) sect_z;
                if (temp_z == CUTOFF) { flags |= 4u; }
                temp_z -= CUTOFF;

                uint32_t netpos = temp_x + temp_y + temp_z;

                uint32_t rec[5] = { temp_x, temp_y, temp_z, netpos, flags };
                fwrite(rec, sizeof(uint32_t), 5, out);
                count++;
            }
        }
    }

    fclose(out);
    printf("oracle.bin: %ld sectors, %ld bytes\n", count, count * 20);
    return 0;
}
