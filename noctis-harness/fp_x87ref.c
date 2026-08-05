/* WAVE 3 / IMPLEMENTER 2 - the hardware reference.
 *
 * A tiny interpreter whose "instructions" are real x87 instructions executed
 * on the machine this runs on.  It reads the SAME frozen schedule text that
 * fp_model.py reads and that Implementer 1's genfp.py reads, so all three
 * sides consume one description and no side re-derives what a chain computes.
 *
 * The intermediate never leaves the x87 register stack between mnemonics:
 * there is one C `switch` per schedule line and nothing in between touches
 * the FPU.  That is the property under test - a backend that spills scores
 * 3139/4194 instead of 4194/4194 - so it must not be an accident of how the
 * host compiler felt about register pressure.  Two things guarantee it here:
 *   - nothing in this file is `long double`, which is the only type gcc will
 *     put on the x87 stack on x86-64; all C arithmetic is SSE and cannot
 *     disturb st(0..7);
 *   - every fragment is __volatile__ with a memory clobber, so none of them
 *     may be reordered against each other or hoisted out of the loop.
 *
 * The two-operand pop forms are emitted as raw opcode bytes, NOT mnemonics.
 * `fsubp`/`fdivp` have a famous history of meaning opposite things in
 * different assembler dialects and binutils versions; a wave whose entire
 * result is "which schedule was it" cannot afford to find that out later.
 *
 *   DE C1 FADDP  ST(1),ST(0)      DE C9 FMULP  ST(1),ST(0)
 *   DE E9 FSUBP  ST(1),ST(0)   st1 <- st1 - st0
 *   DE E1 FSUBRP ST(1),ST(0)   st1 <- st0 - st1
 *   DE F9 FDIVP  ST(1),ST(0)   st1 <- st1 / st0
 *   DE F1 FDIVRP ST(1),ST(0)   st1 <- st0 / st1
 *
 * Build (x86-64 gcc is fine and is what is installed here; long double / the
 * x87 stack exist in 64-bit mode exactly as in 32-bit mode, and the control
 * word is the same register.  -m32 would also work where 32-bit libs exist):
 *
 *   gcc -O1 -o fp_x87ref.exe fp_x87ref.c
 *
 * Run:
 *   fp_x87ref.exe <sched.txt> <ChainName> <fpvec.bin> <fpout.bin> [cwhex]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define MAXOPS   256
#define MAXNAMES 64
#define MAXNAME  32

enum {
    K_I32 = 0, K_F64 = 1, K_F32 = 2
};

enum {
    O_FILD, O_FLD, O_FLDS, O_FLD1, O_FLDZ, O_FLDST0,
    O_FADD, O_FSUB, O_FSUBR, O_FMUL, O_FDIV, O_FDIVR,
    O_FIADD, O_FISUB, O_FISUBR, O_FIMUL, O_FIDIV, O_FIDIVR,
    O_FADDP, O_FSUBP, O_FSUBRP, O_FMULP, O_FDIVP, O_FDIVRP,
    O_FSQRT, O_FABS, O_FCHS, O_FRNDINT,
    O_FSTP, O_FSTPS, O_FISTP, O_FXCH,
    O_NONE
};

static const struct { const char *m; int op; int kind; int noarg; } TBL[] = {
    {"fild", O_FILD, K_I32, 0}, {"fld", O_FLD, K_F64, 0},
    {"flds", O_FLDS, K_F32, 0},
    {"fld1", O_FLD1, 0, 1}, {"fldz", O_FLDZ, 0, 1}, {"fldst0", O_FLDST0, 0, 1},
    {"fadd", O_FADD, K_F64, 0}, {"fsub", O_FSUB, K_F64, 0},
    {"fsubr", O_FSUBR, K_F64, 0}, {"fmul", O_FMUL, K_F64, 0},
    {"fdiv", O_FDIV, K_F64, 0}, {"fdivr", O_FDIVR, K_F64, 0},
    {"fiadd", O_FIADD, K_I32, 0}, {"fisub", O_FISUB, K_I32, 0},
    {"fisubr", O_FISUBR, K_I32, 0}, {"fimul", O_FIMUL, K_I32, 0},
    {"fidiv", O_FIDIV, K_I32, 0}, {"fidivr", O_FIDIVR, K_I32, 0},
    {"faddp", O_FADDP, 0, 1}, {"fsubp", O_FSUBP, 0, 1},
    {"fsubrp", O_FSUBRP, 0, 1}, {"fmulp", O_FMULP, 0, 1},
    {"fdivp", O_FDIVP, 0, 1}, {"fdivrp", O_FDIVRP, 0, 1},
    {"fsqrt", O_FSQRT, 0, 1}, {"fabs", O_FABS, 0, 1},
    {"fchs", O_FCHS, 0, 1}, {"frndint", O_FRNDINT, 0, 1},
    {"fstp", O_FSTP, K_F64, 0}, {"fstps", O_FSTPS, K_F32, 0},
    {"fistp", O_FISTP, K_I32, 0}, {"fxch", O_FXCH, 0, 1},
    {NULL, 0, 0, 0}
};

typedef struct { char name[MAXNAME]; int kind; int slot; } Name;
typedef struct { int op; int slot; int kind; } Op;

static Name names[MAXNAMES];
static int nnames;
static Op ops[MAXOPS];
static int nops;

static int    imem[MAXNAMES];
static double dmem[MAXNAMES];
static float  fmem[MAXNAMES];

static int in_names[8], n_in;          /* declaration order */
static int out_name = -1;
static int chain_sid = -1;
static unsigned chain_cw = 0x133F;
static int chain_exact = 0;

static int lookup(const char *s) {
    int i;
    for (i = 0; i < nnames; i++) if (!strcmp(names[i].name, s)) return i;
    return -1;
}

static int declare(const char *s, int kind) {
    int i = lookup(s);
    if (i >= 0) return i;
    if (nnames >= MAXNAMES) { fprintf(stderr, "too many names\n"); exit(2); }
    snprintf(names[nnames].name, MAXNAME, "%s", s);
    names[nnames].kind = kind;
    names[nnames].slot = nnames;
    return nnames++;
}

static int kind_of_word(const char *w) {
    if (!strcmp(w, "int32")) return K_I32;
    if (!strcmp(w, "f64"))   return K_F64;
    if (!strcmp(w, "f32"))   return K_F32;
    return -1;
}

/* ------------------------------------------------------------------ */
/* schedule reader.  Written from the frozen format in section 2, not  */
/* shared with the Python one - an ambiguity should surface as a       */
/* disagreement, not be papered over by a common parser.               */
/* ------------------------------------------------------------------ */
static void parse_sched(const char *path, const char *want) {
    FILE *fh = fopen(path, "r");
    char line[512];
    int in_chain = 0, seen = 0;
    if (!fh) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    while (fgets(line, sizeof line, fh)) {
        char *h, *p, w1[64], w2[128];
        p = strchr(line, '#'); if (p) *p = 0;
        h = line; while (*h && isspace((unsigned char)*h)) h++;
        p = h + strlen(h); while (p > h && isspace((unsigned char)p[-1])) *--p = 0;
        if (!*h) continue;

        if (sscanf(h, "%63s", w1) != 1) continue;
        if (!strcmp(w1, "chain")) {
            char nm[128];
            if (sscanf(h, "chain %127s", nm) != 1) continue;
            in_chain = !strcmp(nm, want);
            if (in_chain) seen = 1;
            continue;
        }
        if (!in_chain) continue;

        if (!strcmp(w1, "sid")) { sscanf(h, "sid %d", &chain_sid); continue; }
        if (!strcmp(w1, "cw"))  { sscanf(h, "cw %x", &chain_cw); continue; }
        if (!strcmp(w1, "exact")) { chain_exact = 1; continue; }
        if (!strcmp(w1, "in") || !strcmp(w1, "var")) {
            char ty[16]; const char *rest;
            if (sscanf(h, "%*s %15s", ty) != 1) continue;
            int k = kind_of_word(ty);
            if (k < 0) { fprintf(stderr, "bad type %s\n", ty); exit(2); }
            rest = strstr(h, ty) + strlen(ty);
            /* split the remainder on commas */
            while (*rest) {
                char nm[MAXNAME]; int n = 0;
                while (*rest && (isspace((unsigned char)*rest) || *rest == ',')) rest++;
                while (*rest && !isspace((unsigned char)*rest) && *rest != ',' && n < MAXNAME - 1)
                    nm[n++] = *rest++;
                nm[n] = 0;
                if (!n) break;
                int id = declare(nm, k);
                if (!strcmp(w1, "in")) {
                    if (n_in >= 8) { fprintf(stderr, "too many inputs\n"); exit(2); }
                    in_names[n_in++] = id;
                }
            }
            continue;
        }
        if (!strcmp(w1, "out")) {
            char ty[16], nm[MAXNAME];
            if (sscanf(h, "out %15s %31s", ty, nm) != 2) continue;
            out_name = declare(nm, kind_of_word(ty));
            continue;
        }
        if (!strcmp(w1, "const")) {
            char nm[MAXNAME], ty[16], val[64];
            if (sscanf(h, "const %31s = %15s %63s", nm, ty, val) != 3) {
                fprintf(stderr, "bad const line: %s\n", h); exit(2);
            }
            int k = kind_of_word(ty), id = declare(nm, k);
            if (k == K_I32) imem[names[id].slot] = (int)strtol(val, NULL, 0);
            else            dmem[names[id].slot] = strtod(val, NULL);
            continue;
        }
        /* otherwise: a mnemonic */
        {
            int i, found = 0;
            for (i = 0; TBL[i].m; i++) if (!strcmp(w1, TBL[i].m)) {
                found = 1;
                if (nops >= MAXOPS) { fprintf(stderr, "too many ops\n"); exit(2); }
                ops[nops].op = TBL[i].op;
                ops[nops].kind = TBL[i].kind;
                ops[nops].slot = -1;
                if (!TBL[i].noarg) {
                    if (sscanf(h, "%*s %127s", w2) != 1) {
                        fprintf(stderr, "%s needs an operand\n", w1); exit(2);
                    }
                    int id = lookup(w2);
                    if (id < 0) { fprintf(stderr, "undeclared %s\n", w2); exit(2); }
                    if (names[id].kind != TBL[i].kind) {
                        fprintf(stderr, "%s %s: type mismatch\n", w1, w2); exit(2);
                    }
                    ops[nops].slot = names[id].slot;
                }
                nops++;
                break;
            }
            if (!found) { fprintf(stderr, "unknown directive '%s'\n", w1); exit(2); }
        }
    }
    fclose(fh);
    if (!seen) { fprintf(stderr, "chain '%s' not found in %s\n", want, path); exit(2); }
    if (out_name < 0) { fprintf(stderr, "chain has no out\n"); exit(2); }
}

/* ------------------------------------------------------------------ */
static unsigned short getcw(void) {
    unsigned short v; __asm__ __volatile__("fnstcw %0" : "=m"(v)); return v;
}
static unsigned short getsw(void) {
    unsigned short v; __asm__ __volatile__("fnstsw %0" : "=m"(v)); return v;
}
static void setcw(unsigned short v) {
    __asm__ __volatile__("fldcw %0" : : "m"(v));
}

#define A0(S)      __asm__ __volatile__(S ::: "memory")
#define AM(S, P)   __asm__ __volatile__(S " %0" : : "m"(*(P)) : "memory")
#define AMW(S, P)  __asm__ __volatile__(S " %0" : "=m"(*(P)) : : "memory")

static void run_case(void) {
    int k;
    for (k = 0; k < nops; k++) {
        int s = ops[k].slot;
        switch (ops[k].op) {
        case O_FILD:    AM("fildl",  &imem[s]); break;
        case O_FLD:     AM("fldl",   &dmem[s]); break;
        case O_FLDS:    AM("flds",   &fmem[s]); break;
        case O_FLD1:    A0("fld1");             break;
        case O_FLDZ:    A0("fldz");             break;
        case O_FLDST0:  A0(".byte 0xD9,0xC0");  break;   /* fld st(0) */

        case O_FADD:    AM("faddl",  &dmem[s]); break;
        case O_FSUB:    AM("fsubl",  &dmem[s]); break;
        case O_FSUBR:   AM("fsubrl", &dmem[s]); break;
        case O_FMUL:    AM("fmull",  &dmem[s]); break;
        case O_FDIV:    AM("fdivl",  &dmem[s]); break;
        case O_FDIVR:   AM("fdivrl", &dmem[s]); break;

        case O_FIADD:   AM("fiaddl",  &imem[s]); break;
        case O_FISUB:   AM("fisubl",  &imem[s]); break;
        case O_FISUBR:  AM("fisubrl", &imem[s]); break;
        case O_FIMUL:   AM("fimull",  &imem[s]); break;
        case O_FIDIV:   AM("fidivl",  &imem[s]); break;
        case O_FIDIVR:  AM("fidivrl", &imem[s]); break;

        /* raw bytes: see the dialect note at the top of the file */
        case O_FADDP:   A0(".byte 0xDE,0xC1"); break;
        case O_FMULP:   A0(".byte 0xDE,0xC9"); break;
        case O_FSUBP:   A0(".byte 0xDE,0xE9"); break;
        case O_FSUBRP:  A0(".byte 0xDE,0xE1"); break;
        case O_FDIVP:   A0(".byte 0xDE,0xF9"); break;
        case O_FDIVRP:  A0(".byte 0xDE,0xF1"); break;

        case O_FSQRT:   A0("fsqrt");   break;
        case O_FABS:    A0("fabs");    break;
        case O_FCHS:    A0("fchs");    break;
        case O_FRNDINT: A0("frndint"); break;
        case O_FXCH:    A0(".byte 0xD9,0xC9"); break;   /* fxch st(1) */

        case O_FSTP:    AMW("fstpl",  &dmem[s]); break;
        case O_FSTPS:   AMW("fstps",  &fmem[s]); break;
        case O_FISTP:   AMW("fistpl", &imem[s]); break;
        default:        fprintf(stderr, "bad op\n"); exit(2);
        }
    }
}

/* Borland's __ftol: flip the rounding control to chop, fistp, flip back.
 * The 37 hand-written sites do NOT do this - they inherit RC, which at the
 * original's 0x133F is round-to-nearest-even.  Both are produced here. */
static int conv_chop(double v, unsigned short cw) {
    unsigned short c = (unsigned short)((cw & ~0x0C00) | 0x0C00);
    int r;
    setcw(c);
    __asm__ __volatile__("fldl %1\n\t fistpl %0" : "=m"(r) : "m"(v) : "memory");
    setcw(cw);
    return r;
}
static int conv_near(double v, unsigned short cw) {
    unsigned short c = (unsigned short)(cw & ~0x0C00);
    int r;
    setcw(c);
    __asm__ __volatile__("fldl %1\n\t fistpl %0" : "=m"(r) : "m"(v) : "memory");
    setcw(cw);
    return r;
}

/* ------------------------------------------------------------------ */
#define VMAGIC 0x46505643u
#define OMAGIC 0x46504F54u
#define SENT_HDR  0x0DEFACEDu
#define SENT_CASE 0x5A5A5A5Au
#define BACKEND_C_X87 4

typedef unsigned int u32;
typedef unsigned long long u64;

int main(int argc, char **argv) {
    const char *sched, *chain, *vecp, *outp;
    unsigned cwover = 0;
    int have_cwover = 0;
    FILE *fh;
    long vlen;
    unsigned char *vb;
    u32 hdr[8], ncase, caseu, sid, cw;
    u32 i, j, unbalanced = 0, rejects = 0;
    unsigned char *ob;
    size_t olen;

    if (argc < 5) {
        fprintf(stderr, "usage: %s <sched.txt> <Chain> <fpvec.bin> <fpout.bin> [cwhex]\n",
                argv[0]);
        return 2;
    }
    sched = argv[1]; chain = argv[2]; vecp = argv[3]; outp = argv[4];
    if (argc > 5) { cwover = (unsigned)strtoul(argv[5], NULL, 16); have_cwover = 1; }

    parse_sched(sched, chain);

    fh = fopen(vecp, "rb");
    if (!fh) { fprintf(stderr, "cannot open %s\n", vecp); return 2; }
    fseek(fh, 0, SEEK_END); vlen = ftell(fh); fseek(fh, 0, SEEK_SET);
    vb = (unsigned char *)malloc((size_t)vlen);
    if (fread(vb, 1, (size_t)vlen, fh) != (size_t)vlen) {
        fprintf(stderr, "short read on %s\n", vecp); return 2;
    }
    fclose(fh);
    if (vlen < 32) { fprintf(stderr, "fpvec too short\n"); return 2; }
    memcpy(hdr, vb, 32);
    if (hdr[0] != VMAGIC) { fprintf(stderr, "fpvec magic %08X\n", hdr[0]); return 2; }
    if (hdr[1] != 1)      { fprintf(stderr, "fpvec version %u\n", hdr[1]); return 2; }
    ncase = hdr[2]; caseu = hdr[3]; sid = hdr[4]; cw = hdr[5];
    if (caseu != 16) { fprintf(stderr, "fpvec CASEU %u != 16\n", caseu); return 2; }
    if ((u64)vlen < 32ull + (u64)ncase * 64ull) {
        fprintf(stderr, "fpvec truncated\n"); return 2;
    }
    if ((int)sid != chain_sid)
        fprintf(stderr, "WARNING: fpvec sid %u != chain sid %d\n", sid, chain_sid);
    if (have_cwover) cw = cwover;

    olen = 32 + (size_t)ncase * 32;
    ob = (unsigned char *)malloc(olen);
    memset(ob, 0, olen);

    /* One fninit for the whole run, then the chain's control word.  The stack
     * is NOT re-initialised per case on purpose: TOP must come back to 0 by
     * itself after every chain, and a leak has to accumulate visibly rather
     * than be swept up between cases. */
    __asm__ __volatile__("fninit" ::: "memory");
    setcw((unsigned short)cw);

    for (i = 0; i < ncase; i++) {
        const unsigned char *c = vb + 32 + (size_t)i * 64;
        u32 u[16];
        double res; int chop, near; short i16; int cmpv; u32 flags = 0;
        unsigned short sw;
        int fi = 0, ii = 0;
        memcpy(u, c, 64);

        for (j = 0; j < (u32)n_in; j++) {
            int id = in_names[j];
            if (names[id].kind == K_I32) {
                imem[names[id].slot] = (int)u[8 + ii]; ii++;
            } else {
                u64 b = (u64)u[2 * fi] | ((u64)u[2 * fi + 1] << 32);
                memcpy(&dmem[names[id].slot], &b, 8); fi++;
            }
        }

        run_case();
        sw = getsw();

        res = dmem[names[out_name].slot];
        if (((sw >> 11) & 7) != 0) { flags |= 2; unbalanced++; }
        /* REJECT, defined identically here and in fp_model.py: zero,
         * subnormal, infinite or NaN.  Such a result cannot discriminate one
         * engine from another and the two sides legitimately represent it
         * differently, so fp_diff.py compares the FLAG but skips the value. */
        {
            double m = res < 0.0 ? -res : res;
            if (!(res == res) || res == 0.0 || m > 1.7976931348623157e308
                || m < 2.2250738585072014e-308) { flags |= 1; rejects++; }
        }

        chop = conv_chop(res, (unsigned short)cw);
        near = conv_near(res, (unsigned short)cw);
        i16  = (short)(chop & 0xFFFF);
        cmpv = (res > 0.0) - (res < 0.0);

        {
            unsigned char *o = ob + 32 + (size_t)i * 32;
            u64 b; u32 t;
            memcpy(&b, &res, 8);
            t = (u32)(b & 0xFFFFFFFFu);        memcpy(o + 0, &t, 4);
            t = (u32)(b >> 32);                memcpy(o + 4, &t, 4);
            memcpy(o + 8, &chop, 4);
            memcpy(o + 12, &near, 4);
            { int e = (int)i16; memcpy(o + 16, &e, 4); }
            memcpy(o + 20, &cmpv, 4);
            memcpy(o + 24, &flags, 4);
            t = SENT_CASE;                     memcpy(o + 28, &t, 4);
        }
    }

    {
        unsigned short cwe = getcw(), swe = getsw();
        u32 h[8];
        h[0] = OMAGIC; h[1] = 1; h[2] = ncase; h[3] = 8;
        h[4] = BACKEND_C_X87; h[5] = (u32)(cwe & 0x0F3F); h[6] = (u32)swe;
        h[7] = SENT_HDR;
        memcpy(ob, h, 32);
        fh = fopen(outp, "wb");
        if (!fh) { fprintf(stderr, "cannot write %s\n", outp); return 2; }
        fwrite(ob, 1, olen, fh);
        fclose(fh);
        printf("fp_x87ref: chain=%s sid=%d cw_loaded=%04X cw_readback=%04X"
               " (masked %04X) sw=%04X TOP=%d\n",
               chain, chain_sid, cw, cwe, cwe & 0x0F3F, swe, (swe >> 11) & 7);
        printf("  cases=%u  unbalanced=%u  rejects=%u  -> %s (%zu bytes)\n",
               ncase, unbalanced, rejects, outp, olen);
    }
    return 0;
}
