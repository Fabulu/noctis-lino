/* grv_walk_ref.c -- Wave 7b C oracle for iperificie's grid-walk call sequence.
 *
 * Transliterated VERBATIM from NOCTIS-1.CPP:1393-1471.  Emits the ordered
 * (x,z) fragment-call sequence packed one per int32 (x | (z<<16)), prefixed
 * by the count, per corpus case.  Not derived from grv_walk_spec.py: a
 * separate pass, compared.
 *
 * Verbatim source quirks reproduced: single `if (b<0) b+=360;` (no mod 360);
 * quadrant 4 line 1452 uses ipfz (not ipfx) as the x-loop bound.
 *
 * Build: gcc -O2 -o grv_walk_ref.exe grv_walk_ref.c
 * Run:   grv_walk_ref.exe corpus.txt out.bin
 *   corpus line: ipfx ipfz beta add
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

typedef int32_t i32;

static i32 *outbuf = NULL;
static int outcap = 0, outn = 0;

static void emit(i32 x, i32 z)
{
    if (outn >= outcap) { outcap = outcap ? outcap * 2 : 1024; outbuf = realloc(outbuf, outcap * sizeof(i32)); }
    outbuf[outn++] = (x & 0xFFFF) | ((z & 0xFFFF) << 16);
}

static void run_case(int ipfx, int ipfz, int beta, int add, FILE *fo)
{
    int b = beta, x, z;
    if (b < 0) b += 360;
    outn = 0;

    if (b < 45 || b >= 315) {
        for (z = 199; z >= ipfz - add; ) {
            for (x = 0; x < ipfx; ) { emit(x, z); x++; }
            for (x = 199; x >= ipfx; ) { emit(x, z); x--; }
            z--;
        }
    } else if (b >= 135 && b < 225) {
        for (z = 0; z <= ipfz + add; ) {
            for (x = 0; x < ipfx; ) { emit(x, z); x++; }
            for (x = 199; x >= ipfx; ) { emit(x, z); x--; }
            z++;
        }
    } else if (b >= 45 && b < 135) {
        for (x = 0; x <= ipfx + add; ) {
            for (z = 199; z > ipfz; ) { emit(x, z); z--; }
            for (z = 0; z <= ipfz; ) { emit(x, z); z++; }
            x++;
        }
    } else {  /* b >= 225 && b < 315 */
        for (x = 199; x >= ipfz - add; ) {       /* SOURCE BUG: ipfz not ipfx */
            for (z = 199; z > ipfz; ) { emit(x, z); z--; }
            for (z = 0; z <= ipfz; ) { emit(x, z); z++; }
            x--;
        }
    }
    i32 cnt = outn;
    fwrite(&cnt, 4, 1, fo);
    if (outn) fwrite(outbuf, 4, outn, fo);
}

int main(int argc, char **argv)
{
    FILE *fi, *fo;
    char line[256];
    if (argc < 3) { fprintf(stderr, "usage: grv_walk_ref corpus.txt out.bin\n"); return 2; }
    fi = fopen(argv[1], "r");
    fo = fopen(argv[2], "wb");
    if (!fi || !fo) { perror("open"); return 2; }
    while (fgets(line, sizeof line, fi)) {
        int ipfx, ipfz, beta, add;
        if (line[0] == '#' || line[0] == '\n') continue;
        if (sscanf(line, "%d %d %d %d", &ipfx, &ipfz, &beta, &add) != 4) continue;
        run_case(ipfx, ipfz, beta, add, fo);
    }
    free(outbuf);
    fclose(fi); fclose(fo);
    return 0;
}
