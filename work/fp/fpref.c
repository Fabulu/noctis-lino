/* fpref.c - the HARDWARE reference for the fp* scalar and conversion
 *           interface.
 *
 *   gcc -O1 -o fpref.exe fpref.c
 *
 * Independence is the only reason this file exists, so it is worth being
 * precise about what it shares with the thing it grades and what it does
 * not.
 *
 *   SHARED : the vector file, and the definition of each operation as a
 *            sequence of x87 instructions.
 *   NOT SHARED : the compiler, the language, the register allocator, the
 *            instruction encodings (gcc's assembler emits them; the
 *            L.in.oleum side has them typed out as hex by hand), and the
 *            address of every operand.
 *
 * So a byte-for-byte agreement across 4096 vectors is evidence about the
 * arithmetic and about the hand-typed opcodes, which is exactly the pair
 * of things that could be wrong on the L.in.oleum side.
 *
 * WHY x86-64 IS FINE.  There is no 32-bit toolchain on this machine, but
 * none is needed: `long double` on mingw-w64 IS the 80-bit x87 type and
 * gcc compiles arithmetic on it to x87 instructions.  Every operation here
 * is either such an operation or is written as inline assembly, so what
 * runs is a real FPU executing the real instruction, under a control word
 * this file sets explicitly.  Nothing is emulated and nothing is modelled.
 *
 * THE PATTERN EVERY OPERATION FOLLOWS is the one the L.in.oleum scalar
 * routines use:
 *      fld qword <a>        widen to the internal format, exact
 *      <op> qword <b>       round once, to whatever PC says
 *      fstp qword <r>       round again, to 53 bits
 * which for a binary64 result is a DOUBLE ROUNDING and is not the same as
 * a plain binary64 operation.  That is not a defect being reproduced; it
 * is what the original's compiler emitted, and it is why the reference
 * cannot just be C `double` arithmetic.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define CASEU_IN  16
#define CASEU_OUT  8
#define MAGIC_IN  0x46505643u   /* FPVC */
#define MAGIC_OUT 0x46504F54u   /* FPOT */

static void setcw(unsigned short cw)
{
    __asm__ __volatile__("fldcw %0" : : "m"(cw));
}

static unsigned short getcw(void)
{
    unsigned short cw = 0;
    __asm__ __volatile__("fnstcw %0" : "=m"(cw));
    return cw;
}

static unsigned short getsw(void)
{
    unsigned short sw = 0;
    __asm__ __volatile__("fnstsw %0" : "=m"(sw));
    return sw;
}

/* --- the conversions ------------------------------------------------- */

/* fistp under the AMBIENT control word: the 37 hand-written sites */
static int32_t f_to_int_near(double x)
{
    int32_t r;
    long double v = (long double)x;
    __asm__ __volatile__("fistpl %0" : "=m"(r) : "t"(v) : "st");
    return r;
}

/* Borland's __ftol: flip the rounding control to chop and back.
 * This is a C cast, and every generation seed goes through it. */
static int32_t f_to_int_chop(double x)
{
    unsigned short save = getcw();
    unsigned short chop = (unsigned short)((save & 0xF3FF) | 0x0C00);
    int32_t r;
    long double v;
    setcw(chop);
    v = (long double)x;
    __asm__ __volatile__("fistpl %0" : "=m"(r) : "t"(v) : "st");
    setcw(save);
    return r;
}

/* Borland large model: int is 16 bits.  The 32-bit fistp runs and the low
 * half is taken.  NOT fistp m16int, which traps on overflow and, masked,
 * stores 0x8000 for every one - and overflow here is the normal path. */
static int32_t narrow16(int32_t v)
{
    int32_t w = v & 0xFFFF;
    if (w >= 0x8000) w -= 0x10000;
    return w;
}

/* --- the operations -------------------------------------------------- */

static double op_add(double a, double b)
{ long double r = (long double)a + (long double)b; return (double)r; }
static double op_sub(double a, double b)
{ long double r = (long double)a - (long double)b; return (double)r; }
static double op_mul(double a, double b)
{ long double r = (long double)a * (long double)b; return (double)r; }
static double op_quo(double a, double b)
{ long double r = (long double)a / (long double)b; return (double)r; }

static double op_sqrt(double a)
{
    long double v = (long double)a, r;
    __asm__ __volatile__("fsqrt" : "=t"(r) : "0"(v));
    return (double)r;
}
static double op_sin(double a)
{
    long double v = (long double)a, r;
    __asm__ __volatile__("fsin" : "=t"(r) : "0"(v));
    return (double)r;
}
static double op_cos(double a)
{
    long double v = (long double)a, r;
    __asm__ __volatile__("fcos" : "=t"(r) : "0"(v));
    return (double)r;
}
/* fpatan: st1 is the numerator, st0 the denominator, result replaces both */
static double op_atan2(double y, double x)
{
    long double vy = (long double)y, vx = (long double)x, r;
    __asm__ __volatile__("fpatan" : "=t"(r) : "0"(vx), "u"(vy) : "st(1)");
    return (double)r;
}
static double op_neg(double a)
{
    long double v = (long double)a, r;
    __asm__ __volatile__("fchs" : "=t"(r) : "0"(v));
    return (double)r;
}
static double op_abs(double a)
{
    long double v = (long double)a, r;
    __asm__ __volatile__("fabs" : "=t"(r) : "0"(v));
    return (double)r;
}
static double op_inttof(int32_t i)
{
    long double r;
    __asm__ __volatile__("fildl %1" : "=t"(r) : "m"(i));
    return (double)r;
}
/* (double)(float)x - the deliberate mid-expression narrowing */
static double op_f32narrow(double a)
{
    long double v = (long double)a;
    float f;
    __asm__ __volatile__("fstps %0" : "=m"(f) : "t"(v) : "st");
    return (double)f;
}

static int32_t op_cmp(double a, double b)
{
    long double x = (long double)a, y = (long double)b;
    if (x < y) return -1;
    if (x > y) return 1;
    if (x == y) return 0;
    return 2;                       /* unordered */
}

/* --- the chains ------------------------------------------------------ */

/* the ONE store version: the intermediate never leaves the x87 stack */
static double chain_nsidentity(int32_t x, int32_t y, int32_t z)
{
    static const int32_t k = 100000;
    long double r;
    __asm__ __volatile__(
        "fildl %1\n\t"
        "fidivl %4\n\t"
        "fildl %2\n\t"
        "fmulp %%st, %%st(1)\n\t"
        "fidivl %4\n\t"
        "fildl %3\n\t"
        "fmulp %%st, %%st(1)\n\t"
        "fidivl %4"
        : "=t"(r) : "m"(x), "m"(y), "m"(z), "m"(k));
    return (double)r;
}

static double chain_prod4(double a, double b, double c, double d)
{
    long double r = (long double)a;
    r = r * (long double)b;
    r = r * (long double)c;
    r = r * (long double)d;
    return (double)r;
}

static double chain_prod4spilled(double a, double b, double c, double d)
{
    double r = (double)((long double)a * (long double)b);
    r = (double)((long double)r * (long double)c);
    r = (double)((long double)r * (long double)d);
    return r;
}

/* --------------------------------------------------------------------- */

static uint32_t *rd;
static size_t nrd;

static double getf(size_t base, int slot)
{
    uint64_t b = (uint64_t)rd[base + slot * 2] |
                 ((uint64_t)rd[base + slot * 2 + 1] << 32);
    double d;
    memcpy(&d, &b, 8);
    return d;
}

int main(int argc, char **argv)
{
    const char *inp = argc > 1 ? argv[1] : "fpvec.bin";
    const char *outp = argc > 2 ? argv[2] : "fprefout.bin";
    FILE *f = fopen(inp, "rb");
    long sz;
    uint32_t ncase, caseu, sched, cw;
    uint32_t *w;
    size_t i;
    unsigned short cw_end;
    unsigned sw_end;

    if (!f) { fprintf(stderr, "cannot open %s\n", inp); return 2; }
    fseek(f, 0, SEEK_END); sz = ftell(f); fseek(f, 0, SEEK_SET);
    nrd = (size_t)sz / 4;
    rd = malloc(nrd * 4);
    if (fread(rd, 4, nrd, f) != nrd) { fprintf(stderr, "short read\n"); return 2; }
    fclose(f);

    if (rd[0] != MAGIC_IN) { fprintf(stderr, "bad magic %08X\n", rd[0]); return 2; }
    if (rd[1] != 1) { fprintf(stderr, "bad version %u\n", rd[1]); return 2; }
    ncase = rd[2]; caseu = rd[3]; sched = rd[4]; cw = rd[5];
    if (caseu != CASEU_IN) { fprintf(stderr, "bad caseu %u\n", caseu); return 2; }
    if (nrd != 8 + (size_t)ncase * CASEU_IN) {
        fprintf(stderr, "size %zu != header says %zu\n",
                nrd, 8 + (size_t)ncase * CASEU_IN);
        return 2;
    }

    w = calloc(8 + (size_t)ncase * CASEU_OUT, 4);
    setcw((unsigned short)cw);

    for (i = 0; i < ncase; i++) {
        size_t b = 8 + i * CASEU_IN;
        size_t o = 8 + i * CASEU_OUT;
        double fa = getf(b, 0), fb = getf(b, 1);
        double fc = getf(b, 2), fd = getf(b, 3);
        int32_t j0 = (int32_t)rd[b + 8], j1 = (int32_t)rd[b + 9];
        int32_t j2 = (int32_t)rd[b + 10];
        double r = 0.0;
        uint64_t bits;
        uint32_t expo, flags = 0;
        unsigned short sw0;

        switch (sched) {
        case 1:  r = op_add(fa, fb); break;
        case 2:  r = op_sub(fa, fb); break;
        case 3:  r = op_mul(fa, fb); break;
        case 4:  r = op_quo(fa, fb); break;
        case 5:  r = op_sqrt(fa < 0 ? -fa : fa); break;
        case 6:  r = op_neg(fa); break;
        case 7:  r = op_abs(fa); break;
        case 8:  r = op_sin(fa); break;
        case 9:  r = op_cos(fa); break;
        case 10: r = op_atan2(fa, fb); break;
        case 11: r = fa; break;                    /* FCmp only */
        case 12: r = op_inttof(j0); break;
        case 13: r = op_f32narrow(fa); break;
        case 20: r = chain_nsidentity(j0, j1, j2); break;
        case 21: r = chain_prod4(fa, fb, fc, fd); break;
        case 22: r = chain_prod4spilled(fa, fb, fc, fd); break;
        default: fprintf(stderr, "unknown schedule %u\n", sched); return 2;
        }

        memcpy(&bits, &r, 8);
        w[o + 0] = (uint32_t)(bits & 0xFFFFFFFFu);
        w[o + 1] = (uint32_t)(bits >> 32);
        w[o + 2] = (uint32_t)f_to_int_chop(r);
        w[o + 3] = (uint32_t)f_to_int_near(r);
        w[o + 4] = (uint32_t)narrow16(f_to_int_chop(r));
        w[o + 5] = (uint32_t)op_cmp(r, fb);

        expo = (uint32_t)((bits >> 52) & 0x7FF);
        if (expo == 0 || expo == 0x7FF) flags |= 1;
        sw0 = getsw();
        if (((sw0 >> 11) & 7) != 0) flags |= 2;
        w[o + 6] = flags;
        w[o + 7] = 0x5A5A5A5Au;
    }

    cw_end = getcw();
    sw_end = getsw();

    w[0] = MAGIC_OUT;
    w[1] = 1;
    w[2] = ncase;
    w[3] = CASEU_OUT;
    w[4] = 4;                       /* backend id 4 = C hardware reference */
    w[5] = (uint32_t)(cw_end & 0x0F3F);
    w[6] = sw_end;
    w[7] = 0x0DEFACEDu;

    f = fopen(outp, "wb");
    fwrite(w, 4, 8 + (size_t)ncase * CASEU_OUT, f);
    fclose(f);
    printf("fpref: schedule %u, %u cases, cw in %04X out %04X, TOP %u -> %s\n",
           sched, ncase, cw, cw_end & 0x0F3F, (sw_end >> 11) & 7, outp);
    return 0;
}
