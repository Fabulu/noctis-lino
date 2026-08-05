/* Independent oracle for RECON C on REAL x87 hardware.
 *
 * Runs the Noctis identity chain three ways over the charted stars:
 *   HW64  - long double (x87, control word forced to 0x133F: PC=64,
 *           round-nearest, all exceptions masked - the original's word)
 *   HW53  - the same chain with the x87 precision control set to 53 bits
 *           (0x123F), which is what a store-after-every-op double build does
 *   INT   - the exact integer product x*y*z (__int128) divided by 1e15 and
 *           rounded ONCE to double, with no floating point in the division
 *
 * Build: gcc -m32 -O1 -mfpmath=387 -o probe_w3c_x87.exe probe_w3c_x87.c
 * Run:   probe_w3c_x87.exe < hits.tsv          (x y z stored_hex per line)
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static unsigned short getcw(void) {
    unsigned short cw;
    __asm__ __volatile__("fnstcw %0" : "=m"(cw));
    return cw;
}
static void setcw(unsigned short cw) {
    __asm__ __volatile__("fldcw %0" : : "m"(cw));
}

/* the chain exactly as Borland compiles it: operands loaded from double
 * memory, everything else kept on the x87 stack, one store at the end. */
static double chain(double x, double y, double z) {
    long double t;
    __asm__ __volatile__(
        "fldl   %1\n\t"
        "fidivl %4\n\t"
        "fmull  %2\n\t"
        "fidivl %4\n\t"
        "fmull  %3\n\t"
        "fidivl %4\n\t"
        "fstpt  %0\n\t"
        : "=m"(t)
        : "m"(x), "m"(y), "m"(z), "m"(*(const int[]){100000})
        : "st");
    return (double)t;   /* the single narrowing store to nearstar_identity */
}

/* NEGATIVE CONTROL 1: the isthere() lookup formula, (x*is)*((y*is)*(z*is))
 * with is = the double nearest 1e-5. Same mathematical value, different
 * rounding schedule and a different divisor representation. */
static double chain_is(double x, double y, double z) {
    static const double is = 0.00001;
    long double t;
    __asm__ __volatile__(
        "fldl %1\n\t fmull %4\n\t"
        "fldl %2\n\t fmull %4\n\t"
        "fldl %3\n\t fmull %4\n\t"
        "fmulp %%st, %%st(1)\n\t"
        "fmulp %%st, %%st(1)\n\t"
        "fstpt %0\n\t"
        : "=m"(t) : "m"(x), "m"(y), "m"(z), "m"(is) : "st");
    return (double)t;
}

/* NEGATIVE CONTROL 2: chain A with ONE intermediate spilled to a 64-bit
 * double and reloaded - the transcription error a port makes by accident. */
static double chain_spill(double x, double y, double z) {
    static const int E5C = 100000;
    long double t; double mid;
    __asm__ __volatile__("fldl %1\n\t fidivl %3\n\t fmull %2\n\t fidivl %3\n\t"
                         "fstpl %0\n\t"
                         : "=m"(mid) : "m"(x), "m"(y), "m"(E5C) : "st");
    __asm__ __volatile__("fldl %1\n\t fmull %2\n\t fidivl %3\n\t fstpt %0\n\t"
                         : "=m"(t) : "m"(mid), "m"(z), "m"(E5C) : "st");
    return (double)t;
}

/* exact: (x*y*z) / 10^15, correctly rounded once, no FPU in the division */
typedef unsigned long long u64;
typedef __int128 i128;
typedef unsigned __int128 u128;

static double once53(long long x, long long y, long long z) {
    i128 p = (i128)x * (i128)y * (i128)z;
    int neg = p < 0;
    u128 n = neg ? (u128)(-p) : (u128)p;
    if (!n) return 0.0;
    /* value = n / 10^15 ; find e with 2^e <= v < 2^(e+1), take 53 bits */
    static const u128 D = (u128)1000000000000000ULL;
    int nb = 0; { u128 t = n; while (t) { t >>= 1; nb++; } }
    int db = 0; { u128 t = D; while (t) { t >>= 1; db++; } }
    int e = nb - db;
    /* compare n<<max(0,-e) with D<<max(0,e) without overflowing: use a
     * software long shift on a 256-bit staging pair. Values here are small
     * enough (n < 2^100, D < 2^50) that 128 bits suffices for e in range. */
    {
        u128 a = n, b = D;
        if (e >= 0) { if (e < 128) b <<= e; }
        else        { if (-e < 128) a <<= -e; }
        if (a < b) e--;
    }
    int sh = e - 53 + 1;                 /* want q = round(n / (D * 2^sh)) */
    u128 num = n, den = D;
    if (sh >= 0) den <<= sh; else num <<= -sh;
    u128 q = num / den, r = num % den;
    if (2 * r > den || (2 * r == den && (q & 1))) {
        q++;
        { int qb = 0; u128 t = q; while (t) { t >>= 1; qb++; }
          if (qb > 53) { q >>= 1; sh++; } }
    }
    double v = (double)(u64)q;
    /* scale by 2^sh exactly */
    while (sh > 0)  { v *= 2.0; sh--; }
    while (sh < 0)  { v *= 0.5; sh++; }
    return neg ? -v : v;
}

int main(void) {
    char line[256];
    long long x, y, z;
    unsigned long long bits;
    long n = 0, h64 = 0, h53 = 0, hint = 0, agree = 0;
    long h24 = 0, hmut = 0, hmis = 0, hmsp = 0;
    unsigned short cw64 = 0x133F, cw53 = 0x123F, cw24 = 0x103F;
    printf("entry control word = 0x%04X\n", getcw());
    while (fgets(line, sizeof line, stdin)) {
        if (sscanf(line, "%lld %lld %lld %llx", &x, &y, &z, &bits) != 4) continue;
        double stored; memcpy(&stored, &bits, 8);
        setcw(cw64);
        double a = chain((double)x, (double)y, (double)z);
        setcw(cw53);
        double b = chain((double)x, (double)y, (double)z);
        setcw(cw24);
        double d24 = chain((double)x, (double)y, (double)z);
        setcw(cw64);
        double c = once53(x, y, z);
        /* NEGATIVE CONTROL: the same chain with the operands permuted. The
         * value is mathematically identical; only the rounding schedule
         * differs. If this also scored 4194 the comparison would not be
         * measuring the schedule at all. */
        double mut = chain((double)z, (double)y, (double)x);
        double mis = chain_is((double)x, (double)y, (double)z);
        double msp = chain_spill((double)x, (double)y, (double)z);
        n++;
        if (a == stored) h64++;
        if (b == stored) h53++;
        if (d24 == stored) h24++;
        if (c == stored) hint++;
        if (a == c) agree++;
        if (mut == stored) hmut++;
        if (mis == stored) hmis++;
        if (msp == stored) hmsp++;
    }
    printf("rows              %ld\n", n);
    printf("x87 PC=64 chain   %ld/%ld  (CW 0x133F - the original's word)\n", h64, n);
    printf("x87 PC=53 chain   %ld/%ld  (CW 0x123F - IEEE double per op)\n", h53, n);
    printf("x87 PC=24 chain   %ld/%ld  (CW 0x103F - lino's native width)\n", h24, n);
    printf("exact-int once    %ld/%ld  (no FPU anywhere in the arithmetic)\n", hint, n);
    printf("PC=64 == exact    %ld/%ld\n", agree, n);
    printf("NEG CTL z,y,x     %ld/%ld  (same value, permuted operands)\n", hmut, n);
    printf("NEG CTL isthere   %ld/%ld  (*1e-5, right-assoc, PC=64)\n", hmis, n);
    printf("NEG CTL one spill %ld/%ld  (PC=64, one intermediate stored)\n", hmsp, n);
    return 0;
}
