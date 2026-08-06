/* fb_ref.c -- Wave 5-corrective, implementer 2.  The C reference for the
 * Noctis buffer model, palette pipeline, present path and tick period.
 *
 * WRITTEN FROM THE 1996 SOURCES, NOT FROM THE LINO:
 *   NOCTIS-D.H:25-56      buffer sizes
 *   NOCTIS.CPP:2163-2171  the farmalloc order (adaptor appended, NOCTIS-0.CPP:53)
 *   NOCTIS-0.CPP:166-241  range8088, tavola_colori
 *   NOCTIS-0.CPP:1151-1200 shade  -- note the DESTINATION PARAMETER
 *   NOCTIS-0.CPP:307-345  pcopy, pclear (QUADWORDS dwords, not 64000 bytes)
 *   NOCTIS-0.CPP:4485     spot     -- class A, 16-bit DI
 *   NOCTIS-0.CPP:4715     cirrus   -- class A, 16-bit BX BEFORE the shift
 *   NOCTIS-0.CPP:6418-6420 snapshot's DAC scaling, tmppal[c]*4
 *   NOCTIS.CPP:604-628    digit_at, including its txtr[-6..-1] underflow
 *   TDPOLYGS.H:2684       polymap's es:[0xFA00] tinta stash (alias 8)
 *   NOCTIS-D.H:171-176    the quadrant bitfield
 *
 * It never reads work/fb*.txt and it never reads fb_layout.py.  fb_layout.py
 * DERIVES the layout by parsing the 1996 sources; this file TRANSCRIBES it.
 * The two disagreeing is the point of the kind-5 compare.
 *
 * WAVE 5-CORRECTIVE
 *   * FBDUMP v2: a TAG in header unit 8, kind 5 unit 2 DEFINED as base+size,
 *     kind 6 replaced, kinds 7/9/10 added.
 *   * The pads split into TAIL (guard) and SUB (allowance): 11 pads, 22 zones.
 *   * The canary is 4 units per pad, every one read back or produced by the
 *     walker.  v1's 18 units were literals on both sides and could not fail.
 *   * shade() takes its destination buffer, because 14 of its 21 call sites
 *     pass surface_palette.
 *   * class A is masked at the DOS truncation point, against the SEGMENT
 *     ORIGIN.  Allocation size cannot reproduce a wrap.
 *   * tavola_colori's filter is modular unsigned, and a `char` filter of 200
 *     is -56.
 *
 * build:
 *   gcc -std=c99 -O2 -Wall -Wextra -o fb_ref.exe fb_ref.c
 * sabotage builds add exactly one -DBREAK_* each; see BREAKS in fb_compare.py.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <ctype.h>

/* ================================================================= SHA-256
 *
 * Needed for exactly one thing: the BUILD-IDENTITY record.  Each producer
 * hashes the fixture file it compiled its stimulus from and puts that hash in
 * its KSELF record, so the grader can require that two producers ran the SAME
 * stimulus instead of hunting for a heading number in a prose document.
 * FIPS 180-4; the constants below are the cube roots of the first 64 primes
 * and are not derived from anything in this project.
 */

typedef struct { uint32_t h[8]; uint64_t len; unsigned char buf[64]; int n; } sha256;

static const uint32_t SHA_K[64] = {
    0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,
    0x923f82a4u,0xab1c5ed5u,0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,
    0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,0xe49b69c1u,0xefbe4786u,
    0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
    0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,
    0x06ca6351u,0x14292967u,0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,
    0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,0xa2bfe8a1u,0xa81a664bu,
    0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
    0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,
    0x5b9cca4fu,0x682e6ff3u,0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,
    0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u };

#define ROR32(x,n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha256_block(sha256 *s, const unsigned char *p)
{
    uint32_t w[64], a, b, c, d, e, f, g, h, t1, t2;
    int i;
    for (i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[4*i] << 24) | ((uint32_t)p[4*i+1] << 16) |
               ((uint32_t)p[4*i+2] << 8) | (uint32_t)p[4*i+3];
    for (i = 16; i < 64; i++) {
        uint32_t s0 = ROR32(w[i-15],7) ^ ROR32(w[i-15],18) ^ (w[i-15] >> 3);
        uint32_t s1 = ROR32(w[i-2],17) ^ ROR32(w[i-2],19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    a=s->h[0]; b=s->h[1]; c=s->h[2]; d=s->h[3];
    e=s->h[4]; f=s->h[5]; g=s->h[6]; h=s->h[7];
    for (i = 0; i < 64; i++) {
        uint32_t S1 = ROR32(e,6) ^ ROR32(e,11) ^ ROR32(e,25);
        uint32_t ch = (e & f) ^ ((~e) & g);
        uint32_t S0 = ROR32(a,2) ^ ROR32(a,13) ^ ROR32(a,22);
        uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
        t1 = h + S1 + ch + SHA_K[i] + w[i];
        t2 = S0 + mj;
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    s->h[0]+=a; s->h[1]+=b; s->h[2]+=c; s->h[3]+=d;
    s->h[4]+=e; s->h[5]+=f; s->h[6]+=g; s->h[7]+=h;
}

static void sha256_init(sha256 *s)
{
    s->h[0]=0x6a09e667u; s->h[1]=0xbb67ae85u; s->h[2]=0x3c6ef372u; s->h[3]=0xa54ff53au;
    s->h[4]=0x510e527fu; s->h[5]=0x9b05688cu; s->h[6]=0x1f83d9abu; s->h[7]=0x5be0cd19u;
    s->len = 0; s->n = 0;
}

static void sha256_push(sha256 *s, const unsigned char *p, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        s->buf[s->n++] = p[i];
        s->len++;
        if (s->n == 64) { sha256_block(s, s->buf); s->n = 0; }
    }
}

static void sha256_done(sha256 *s, char *hex)
{
    uint64_t bits = s->len * 8;
    unsigned char pad = 0x80;
    int i;
    sha256_push(s, &pad, 1);
    pad = 0;
    while (s->n != 56) sha256_push(s, &pad, 1);
    for (i = 7; i >= 0; i--) { unsigned char b = (unsigned char)((bits >> (8*i)) & 255); s->buf[s->n++] = b; }
    sha256_block(s, s->buf);
    for (i = 0; i < 8; i++) sprintf(hex + 8*i, "%08x", s->h[i]);
    hex[64] = 0;
}

/* ============================================================ source reader
 *
 * The K-solver and the fixture loader both need a whole file in memory.
 */

static char *slurp(const char *path, long *outlen)
{
    FILE *f = fopen(path, "rb");
    long n;
    char *b;
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); n = ftell(f); fseek(f, 0, SEEK_SET);
    b = (char *)malloc((size_t)n + 1);
    if (!b) { fclose(f); return NULL; }
    if (fread(b, 1, (size_t)n, f) != (size_t)n) { free(b); fclose(f); return NULL; }
    fclose(f);
    b[n] = 0;
    if (outlen) *outlen = n;
    return b;
}

static void sha256_file(const char *path, char *hex, long *len)
{
    long n = 0;
    char *b = slurp(path, &n);
    sha256 s;
    if (!b) { strcpy(hex, "MISSING"); if (len) *len = -1; return; }
    sha256_init(&s);
    sha256_push(&s, (const unsigned char *)b, (size_t)n);
    sha256_done(&s, hex);
    if (len) *len = n;
    free(b);
}

/* ====================================================== the alias-8 K-SOLVER
 *
 * WHAT THIS REPLACES.  `#define SEG_OFFSET 4` was an unparsed literal in this
 * file and an unparsed literal in the Python producer.  Two files agreeing on
 * a constant that neither of them derived is not two producers; it is one
 * transcription copied twice, and every "independent" check downstream of it
 * inherits the same premise.  BUFFERMAP 4.1 calls the placement SETTLED and
 * gives the argument in prose; prose is not a grader.
 *
 * WHAT IT DOES.  It treats the offset as an UNKNOWN K and re-derives it by
 * parsing the 1996 sources.  Every site that addresses `adapted` (or, for the
 * `wave` family, `p_background`) uses one of two conventions:
 *
 *     segment offset written  =  pixel_index  +  o*K  +  D
 *
 *     o = 1   the far pointer's own offset was loaded  (`les si, dword ptr
 *             adapted`, then `es:[si+D]`)
 *     o = 0   only the segment was loaded (`mov es, seg_adapted`), the index
 *             was built from `riga[]` alone, and the write is `es:[di+D]`
 *
 * Both conventions are used to draw the SAME picture -- Stick's vertical
 * special case and its general case are the same function, and Segmento's are
 * the same function -- so for one pixel they must produce one address:
 *
 *     o_i*K + D_i  =  o_j*K + D_j     =>   K = (D_j - D_i)/(o_i - o_j)
 *
 * Three further, structurally different constraints:
 *
 *   * `wave()` loads `p_background`'s offset into DI with `les`, then THROWS
 *     IT AWAY (`mov di, ax`) and adds a literal to the index instead
 *     (`add ax, D`).  The literal must equal the offset it replaced.
 *   * `sc_bytes` = 65536 + K.  NOCTIS-D.H:47-54 says the page was extended to
 *     "64Kb+4bytes" so a 16-bit DI starting at the pointer's own offset cannot
 *     leave the block.
 *   * the hand-assembled forms.  `db 0x66, 0x26, 0xC7, 0x04` is ModRM 0x04 =
 *     mod 00 / rm 100 = [SI], no displacement; `db 0x66, 0x26, 0xC7, 0x45,
 *     0x04` is ModRM 0x45 = mod 01 / rm 101 = [DI]+disp8 with disp8 = 4.
 *     These are MACHINE CODE, not mnemonics, and they were assembled by hand
 *     for speed -- a different author, a different encoding, the same K.
 *
 * The solver requires the constraint set to be non-trivial (>= MINCON) and to
 * admit EXACTLY ONE K.  Two K's is a REFUSAL, not an average.
 *
 * FALSIFIABLE, and demonstrated: copy the sources to a sandbox, change one
 * displacement, and the solver must refuse (inconsistent) or report a
 * different K.  `fbx_ksolve.py` re-derives the same K by a different parse in
 * a different language, so the constant now has two producers.
 */

#define KSOL_MINCON 6

typedef struct {
    int ok;             /* 1 = a unique K was found */
    int k;              /* the K, if ok */
    int ncon;           /* constraints gathered */
    int ndistinct;      /* distinct K values implied */
    int kvals[16];
    char why[256];
} KSolve;

/* strip C++ // comments and Borland's asm-block noise so a search never
 * matches a mnemonic that only appears inside a comment. */
static char *strip_comments(char *s)
{
    char *r = s, *w = s;
    while (*r) {
        if (r[0] == '/' && r[1] == '/') { while (*r && *r != '\n') r++; }
        else *w++ = *r++;
    }
    *w = 0;
    return s;
}

/* find `needle` at or after p; NULL if not found */
static char *find_from(char *p, const char *needle) { return p ? strstr(p, needle) : NULL; }

/* At `p`, which points just past "es:[si" or "es:[di", read the displacement.
 * "]" -> 0, "+N]" -> N.  Returns -1 if the form is not recognised. */
static int read_disp(const char *p)
{
    while (*p == ' ' || *p == '\t') p++;
    if (*p == ']') return 0;
    if (*p == '+') {
        int v = 0, any = 0;
        p++;
        while (*p == ' ') p++;
        if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X')) {
            p += 2;
            while (isxdigit((unsigned char)*p)) {
                int d = isdigit((unsigned char)*p) ? *p - '0' : (tolower((unsigned char)*p) - 'a' + 10);
                v = v * 16 + d; p++; any = 1;
            }
        } else {
            while (isdigit((unsigned char)*p)) { v = v * 10 + (*p - '0'); p++; any = 1; }
        }
        while (*p == ' ') p++;
        if (any && *p == ']') return v;
    }
    return -1;
}

static void ksol_add(KSolve *ks, int k, const char *tag)
{
    int i;
    (void)tag;
    ks->ncon++;
    for (i = 0; i < ks->ndistinct; i++) if (ks->kvals[i] == k) return;
    if (ks->ndistinct < 16) ks->kvals[ks->ndistinct++] = k;
}

/* Collect (o, D) sites of one convention out of one file.
 *   anchor    the token that establishes the convention
 *   reg       "es:[si" or "es:[di"
 *   window    how far past the anchor the write may be
 * Returns the number of sites appended to d[] (capacity cap). */
static int collect_sites(char *text, const char *anchor, const char *reg,
                         long window, int *d, int cap)
{
    int n = 0;
    char *p = text;
    while (n < cap) {
        char *a = find_from(p, anchor);
        char *w;
        if (!a) break;
        p = a + 1;
        w = find_from(a, reg);
        if (!w) continue;
        if (w - a > window) continue;
        {
            int disp = read_disp(w + strlen(reg));
            if (disp >= 0) d[n++] = disp;
        }
    }
    return n;
}

static void ksolve(const char *srcdir, KSolve *ks)
{
    char p0[1024], ptd[1024], pdh[1024];
    char *n0 = NULL, *td = NULL, *dh = NULL;
    int off_sites[8], nooff_sites[16];
    int noff = 0, nnooff = 0, i, j;

    memset(ks, 0, sizeof *ks);
    ks->ok = 0;

    snprintf(p0,  sizeof p0,  "%s/NOCTIS-0.CPP", srcdir);
    snprintf(ptd, sizeof ptd, "%s/TDPOLYGS.H",   srcdir);
    snprintf(pdh, sizeof pdh, "%s/NOCTIS-D.H",   srcdir);

    n0 = slurp(p0, NULL);
    td = slurp(ptd, NULL);
    dh = slurp(pdh, NULL);
    if (!n0 || !td || !dh) {
        snprintf(ks->why, sizeof ks->why, "cannot read the 1996 sources under %s", srcdir);
        goto done;
    }
    strip_comments(n0); strip_comments(td); strip_comments(dh);

    /* ---- convention o = 1: the far pointer's own offset is in SI ---- */
    noff  = collect_sites(n0, "les si, dword ptr adapted", "es:[si", 900,
                          off_sites, 4);
    noff += collect_sites(td, "les si, dword ptr adapted", "es:[si", 900,
                          off_sites + noff, 4 - noff);

    /* ---- convention o = 0: segment only, index from riga[] ---- */
    nnooff  = collect_sites(n0, "add di, word ptr riga[bx]", "es:[di", 400,
                            nooff_sites, 8);
    nnooff += collect_sites(td, "add di, word ptr riga[bx]", "es:[di", 400,
                            nooff_sites + nnooff, 16 - nnooff);

    if (noff == 0 || nnooff == 0) {
        snprintf(ks->why, sizeof ks->why,
                 "only one addressing convention found (o=1: %d sites, o=0: %d sites)",
                 noff, nnooff);
        goto done;
    }

    /* every cross-convention pair is one equation in K */
    for (i = 0; i < noff; i++)
        for (j = 0; j < nnooff; j++)
            ksol_add(ks, nooff_sites[j] - off_sites[i], "stick/segmento");

    /* ---- wave(): the offset is loaded, discarded, and replaced by a literal
     * Anchored on the FUNCTION, because `les di, dword ptr p_background`
     * appears at 20-odd sites and all but this one keep the offset. */
    {
        char *fn = find_from(n0, "void wave ()");
        if (fn) {
            char *a  = find_from(fn, "les di, dword ptr p_background");
            char *q  = a ? find_from(a, "add ax, ") : NULL;
            char *mv = a ? find_from(a, "mov di, ax") : NULL;
            char *wr = a ? find_from(a, "es:[di") : NULL;
            if (a && a < fn + 200 && q && mv && wr &&
                q < a + 900 && mv < a + 900 && wr < a + 900 && q < mv) {
                const char *r = q + 8;
                int v = 0, any = 0;
                while (isdigit((unsigned char)*r)) { v = v*10 + (*r - '0'); r++; any = 1; }
                /* the write itself must carry NO displacement: the literal was
                 * folded into the index, replacing the discarded offset */
                if (any && read_disp(wr + strlen("es:[di")) == 0)
                    ksol_add(ks, v, "wave");
            }
        }
    }

    /* ---- sc_bytes = 65536 + K ---- */
    {
        char *a = find_from(dh, "#define sc_bytes");
        if (a) {
            const char *r = a + strlen("#define sc_bytes");
            int v = 0, any = 0;
            while (*r == ' ' || *r == '\t') r++;
            while (isdigit((unsigned char)*r)) { v = v*10 + (*r - '0'); r++; any = 1; }
            if (any) ksol_add(ks, v - 65536, "sc_bytes");
        }
    }

    /* ---- the hand-assembled forms.  ModRM, not mnemonics. ---- */
    {
        /* 0xC7 /0 with ModRM 0x04 -> mod 00, rm 100 = [SI], no displacement.
         * 0xC7 /0 with ModRM 0x45 -> mod 01, rm 101 = [DI]+disp8, and the
         * NEXT byte IS that displacement -- parsed, not assumed, so a source
         * whose hand-assembled form disagrees with its mnemonics is caught
         * rather than silently dropped. */
        char *a = find_from(n0, "0xC7, 0x04");
        char *b = find_from(n0, "0xC7, 0x45, 0x");
        if (a && b) {
            const char *r = b + strlen("0xC7, 0x45, 0x");
            int v = 0, any = 0;
            while (isxdigit((unsigned char)*r)) {
                int d = isdigit((unsigned char)*r) ? *r - '0'
                                                   : (tolower((unsigned char)*r) - 'a' + 10);
                v = v * 16 + d; r++; any = 1;
            }
            if (any) ksol_add(ks, v - 0, "modrm 0x04 [SI]+0 vs 0x45 [DI]+disp8");
        }
    }

    if (ks->ncon < KSOL_MINCON) {
        snprintf(ks->why, sizeof ks->why, "only %d constraints (need >= %d)",
                 ks->ncon, KSOL_MINCON);
        goto done;
    }
    if (ks->ndistinct != 1) {
        int n = snprintf(ks->why, sizeof ks->why, "REFUSED: %d constraints imply %d "
                         "different offsets {", ks->ncon, ks->ndistinct);
        for (i = 0; i < ks->ndistinct && n < 200; i++)
            n += snprintf(ks->why + n, sizeof ks->why - (size_t)n, "%s%d",
                          i ? "," : "", ks->kvals[i]);
        snprintf(ks->why + n, sizeof ks->why - (size_t)n, "}");
        goto done;
    }
    ks->ok = 1;
    ks->k = ks->kvals[0];
    snprintf(ks->why, sizeof ks->why, "%d constraints, one solution", ks->ncon);

done:
    free(n0); free(td); free(dh);
}

/* ------------------------------------------------------------ NOCTIS-D.H */

#define OM_BYTES   7340
#define GL_BYTES   22586
#define GL_BREST   10182
#define ST_BYTES   64800
#define PL_BYTES   65552
#define PS_BYTES   40000
#define OC_BYTES   40000
#define SC_BYTES   65540
#define PV_BYTES   20480
#define DM2_BYTES   9360
#define OFF_DIGIMAP2 (-60776L)

#define PAD    16
#define ZONE    8
#define LOWPAD 16

/* Borland's far-heap block header sits below the block and the pointer it
 * hands back has offset 4 inside its own segment.  adaptor is A000:0000. */
#ifdef BREAK_SEGADDRBASE
#define SEG_OFFSET 0
#else
#define SEG_OFFSET 4
#endif
#define ADAPTOR_SEG_OFFSET 0

#define WRAP16 65536

/* one Noctis byte per 32-bit unit, so a byte offset IS a unit offset */
#define NREG 9
enum {
    R_N_OFFSETS_MAP = 0, R_N_GLOBES_MAP, R_S_BACKGROUND, R_P_BACKGROUND,
    R_P_SURFACEMAP, R_OBJECTSCHART, R_PVFILE, R_ADAPTED, R_ADAPTOR
};

static const char *rname[NREG] = {
    "n_offsets_map", "n_globes_map", "s_background", "p_background",
    "p_surfacemap", "objectschart", "pvfile", "adapted", "adaptor"
};
static const int rsize[NREG] = {
    OM_BYTES, GL_BYTES + GL_BREST, ST_BYTES, PL_BYTES,
    PS_BYTES, OC_BYTES, PV_BYTES, SC_BYTES,
#ifdef BREAK_SHRINKADAPTOR
    64000
#else
    SC_BYTES
#endif
};

static int rbase[NREG], rpad[NREG], rsegoff[NREG];
static int nw_top;

/* the workspace.  Under BREAK_PACK4 it is physically packed 4 bytes per unit,
 * which is the whole point of that sabotage. */
#ifdef BREAK_PACK4
static uint32_t *NWSTORE;
#else
static uint32_t *NW;
#endif

static uint32_t *FB;    /* [Display Origin]: 64000 units of 00RRGGBB */
static uint32_t PAL[256];

/* Two magics, because the pads have TWO JOBS and a single magic makes a
 * legitimate write indistinguishable from a violation. */
#define PGUARD 0xA5A5A5A5u   /* TAIL: a write here is a VIOLATION */
#define PALLOW 0x5A5A5A5Au   /* SUB:  a write here may be EXPECTED */

/* ------------------------------------------------------------ byte access */

static void nw_put(int off, int v)
{
#ifdef BREAK_PACK4
    int u = off >> 2, ph = (off & 3) * 8;
    NWSTORE[u] = (NWSTORE[u] & ~(0xFFu << ph)) | ((uint32_t)(v & 255) << ph);
#else
    NW[off] = (uint32_t)(v & 255);
#endif
}

static int nw_get(int off)
{
#ifdef BREAK_PACK4
    return (int)((NWSTORE[off >> 2] >> ((off & 3) * 8)) & 255);
#else
    return (int)(NW[off] & 255);
#endif
}

static uint32_t nw_unit(int off)
{
#ifdef BREAK_PACK4
    return NWSTORE[off >> 2];
#else
    return NW[off];
#endif
}

static void nw_unit_put(int off, uint32_t v)
{
#ifdef BREAK_PACK4
    NWSTORE[off >> 2] = v;
#else
    NW[off] = v;
#endif
}

static int nw_get_signed(int off)
{
    int v = nw_get(off);
    return (v & 0x80) ? v - 256 : v;
}

/* NOCTIS-D.H:171-176.  Four 2-bit fields in one byte. */
static int quad_get(int off, int field) { return (nw_get(off) >> (2 * field)) & 3; }
static void quad_set(int off, int field, int v)
{
    int b = nw_get(off);
    b = (b & ~(3 << (2 * field))) | ((v & 3) << (2 * field));
    nw_put(off, b);
}

/* ------------------------------------------------------------------- FNV */

static uint32_t fnv_init(void) { return 0x811C9DC5u; }
static uint32_t fnv_unit(uint32_t h, uint32_t v)
{
    int i;
    for (i = 0; i < 4; i++) {
        h = (h ^ (v & 0xFFu)) * 0x01000193u;
        v >>= 8;
    }
    return h;
}
static uint32_t fnv_range(int base, int n)
{
    uint32_t h = fnv_init();
    int i;
    for (i = 0; i < n; i++) h = fnv_unit(h, (uint32_t)nw_get(base + i));
    return h;
}

/* ---------------------------------------------------------------- layout */

static void layout_init(void)
{
    int i, cur = LOWPAD;
    for (i = 0; i < NREG; i++) {
        rpad[i] = cur;
        cur += PAD;
        rbase[i] = cur;
        rsegoff[i] = (i == R_ADAPTOR) ? ADAPTOR_SEG_OFFSET : SEG_OFFSET;
        cur += rsize[i];
    }
    nw_top = cur + PAD;
}

static int segbase(int r) { return rbase[r] - rsegoff[r]; }

/* THE address primitive class A needs.  The wrap is taken against the SEGMENT
 * ORIGIN, not the buffer base.  Allocation size cannot do this. */
static int seg_index(int r, int off) { return segbase(r) + (off & 0xFFFF); }

static int region_at(int nw);
static int region_at(int nw)
{
    int i;
    for (i = 0; i < NREG; i++)
        if (nw >= rbase[i] && nw < rbase[i] + rsize[i]) return i;
    return -1;
}

/* ------------------------------------------------------ pads: 11, 22 zones
 *
 * The 16 units between two blocks ARE the upper block's far-heap header in
 * DOS, and offset == 4 means the upper block's header occupies the four bytes
 * immediately below its base -- exactly the bytes a wrap or a negative index
 * reaches.  So the gap splits by OWNERSHIP:
 *
 *   TAIL(k)  = gap + 0..+7    owned by region k      guard    PGUARD
 *   SUB(k+1) = gap + 8..+15   owned by region k+1    allowance PALLOW
 *              SUB(k+1)+4..+7 is region k+1's segment offsets 0..3
 */

#define NPAD 11
#define NZONE 22

static int padbase[NPAD];

typedef struct { int base, len, owner, role; } Zone;   /* role 0 TAIL, 1 SUB */
static Zone zones[NZONE];
static int nzones;

static void zones_init(void)
{
    int i, j, n = 0;
    padbase[0] = 0;
    for (i = 0; i < NREG; i++) padbase[i + 1] = rpad[i];
    padbase[NREG + 1] = nw_top - PAD;

    for (i = 0; i < NPAD; i++) {
        int tail_owner = -1, sub_owner = -1;
        for (j = 0; j < NREG; j++) {
            if (rbase[j] + rsize[j] == padbase[i]) tail_owner = j;
            if (rbase[j] == padbase[i] + PAD) sub_owner = j;
        }
#ifdef BREAK_PADONEMAGIC
        zones[n].base = padbase[i]; zones[n].len = PAD;
        zones[n].owner = tail_owner; zones[n].role = 0; n++;
#else
        zones[n].base = padbase[i]; zones[n].len = ZONE;
        zones[n].owner = tail_owner; zones[n].role = 0; n++;
        zones[n].base = padbase[i] + ZONE; zones[n].len = ZONE;
        zones[n].owner = sub_owner; zones[n].role = 1; n++;
#endif
    }
    nzones = n;
}

static uint32_t zone_magic(const Zone *z) { return z->role ? PALLOW : PGUARD; }

static int zone_of(int off)
{
    int i;
    for (i = 0; i < nzones; i++)
        if (off >= zones[i].base && off < zones[i].base + zones[i].len) return i;
    return -1;
}

/* The allowance table.  Three entries, each with its citation.  A SUB unit
 * named here is COUNTED when it changes, not forbidden. */
static const char *allowed(const Zone *z, int off)
{
    int rel = off - z->base;
    if (z->owner < 0) return NULL;
    if (z->role == 1 && z->owner == R_P_SURFACEMAP && rel >= 2 && rel <= 7)
        return "digit_at txtr[-6..-1], NOCTIS.CPP:614-628";
    if (z->role == 0 && z->owner == R_PVFILE && rel == 0)
        return "loadpv writes 1 past pvfile_c, NOCTIS-0.CPP:2383-2391";
    if (z->role == 1 && rel >= 4 && rel <= 7)
        return "the region's own segment offsets 0..3";
    return NULL;
}

static void poison_pads(void)
{
    int i, j;
    for (i = 0; i < nzones; i++)
        for (j = 0; j < zones[i].len; j++)
#ifdef BREAK_POISONMAGIC
            /* one magic for both roles: the guard job and the allowance job
             * become indistinguishable again, which is the defect 4.1 exists
             * to prevent */
            nw_unit_put(zones[i].base + j, PGUARD);
#else
            nw_unit_put(zones[i].base + j, zone_magic(&zones[i]));
#endif
}

static void zero_pads(void)
{
    int i, j;
    for (i = 0; i < nzones; i++)
        for (j = 0; j < zones[i].len; j++)
            nw_unit_put(zones[i].base + j, 0);
}

/* The two-sided check.
 *   (i)  VIOLATION  -- a unit not on the allowance list that no longer carries
 *        its zone's magic.  Named by region and offset.
 *   (ii) EXPECTATION -- an allowance-listed unit that changed.  COUNTED, not
 *        forbidden, so a build that never performs the legitimate write FAILS.
 */
static int walk_pads(int *n_expect, int *first_off, int *first_pad)
{
    int i, j, viol = 0;
    if (n_expect) *n_expect = 0;
    if (first_off) *first_off = -1;
    if (first_pad) *first_pad = 0;
    for (i = 0; i < nzones; i++) {
#ifdef BREAK_PAD9WALK
        /* walk only the nine REGION pads: the low pad and the top pad go
         * unwatched, which is what an rtab-driven walker does */
        {
            int p, seen = 0;
            for (p = 1; p <= NREG; p++)
                if (zones[i].base == padbase[p] || zones[i].base == padbase[p] + ZONE)
                    seen = 1;
            if (!seen) continue;
        }
#endif
        for (j = 0; j < zones[i].len; j++) {
            int off = zones[i].base + j;
#ifdef BREAK_WALKHIGHBITS
            /* a walker that only looks at the top half of the word.  It still
             * catches a zeroed pad and every write of a small value, so the
             * one-sided "poison then expect 0 violations" test never sees it.
             * The two-sided form -- corrupt ONE unit by ONE and require
             * exactly one violation AT THAT ADDRESS -- does. */
            if ((nw_unit(off) >> 16) == (zone_magic(&zones[i]) >> 16)) continue;
#else
            if (nw_unit(off) == zone_magic(&zones[i])) continue;
#endif
            if (allowed(&zones[i], off)) { if (n_expect) (*n_expect)++; continue; }
            viol++;
            if (first_off && *first_off < 0) {
                *first_off = off;
                /* which pad, 1-based */
                { int p; for (p = 0; p < NPAD; p++)
                        if (off >= padbase[p] && off < padbase[p] + PAD)
                            if (first_pad) *first_pad = p + 1; }
            }
        }
    }
    return viol;
}

/* --------------------------------------------------------------- canary v2
 *
 * v1 was 2 units per region in which BOTH fields were the literal 0xA5A5A5A5,
 * written by construction on both sides.  A clean run and a completely
 * stubbed-out mechanism produced a bit-identical dump -- including, measured,
 * the sabotage whose stated defect was "a canary check that can never fire".
 *
 * v2 is 4 units per pad and every one is read back out of NW or produced by
 * the walker:
 *   0 clean_read  NW[padbase + PROBESLOT] after poisoning
 *   1 dirty_read  the same address after storing WITNESS
 *   2 fired       pad index + 1 the walker reported
 *   3 at          NW offset of the first difference the walker reported
 *
 * WITNESS(i) is region-specific, so copy-pasting one answer fails.
 * PROBESLOT(i) sweeps the pad, so a walker that only checks the last unit
 * fails.  The +1 is not cosmetic: with slot 0 on pad 0 the `at` field is 0 in
 * both the clean and the stubbed case.
 */
/* The slot sweeps the pad, so a walker that only checks the last unit fails;
 * and it SKIPS allowance-listed units, because a probe that lands on one is
 * counted rather than flagged and the record would then say "not fired" for a
 * perfectly good walker.  Deriving the slot from the allowance table also
 * means an implementation with the WRONG allowance table probes a different
 * address and the `at` field moves -- one more thing this record can catch. */
/* CORRECTED.  The sweep is mod 12, not mod PAD.  BUFFERMODEL 4.2 publishes
 * `(7i+1) mod 12` and gives the reason: units +12..+15 are SUB+4..+7, an
 * allowance that cannot fire by design, so a probe expecting them to fire
 * would be asserting that the guard model is wrong.  This file shipped
 * `mod PAD` -- 16 -- which yields slot 0 three times over the eleven pads and
 * probes a DIFFERENT ADDRESS from the two lino walkers from i = 2 onward.
 * A canary record cannot be a cross-implementation check while the two sides
 * probe different addresses, so this is not a cosmetic divergence.
 * Falsifier: BREAK_PROBEMOD16 restores the defect. */
#ifdef BREAK_PROBEMOD16
#define PROBEMOD PAD
#else
#define PROBEMOD 12
#endif
static int probeslot(int i)
{
    int k;
    for (k = 0; k < PROBEMOD; k++) {
        int s = ((i * 7) + 1 + k) % PROBEMOD;
        int off = padbase[i] + s;
        int zi = zone_of(off);
        if (zi < 0) continue;
        if (!allowed(&zones[zi], off)) return s;
    }
    return 0;
}

/* CORRECTED.  `0xC0DE0000 | i` is a BARE LITERAL: any grader that knows the
 * rule reproduces the expected value without reading anything the mechanism
 * produced, which is Wave 5's deleted kind-6 canary reincarnated one file
 * over.  BUFFERMODEL 4.2 already publishes the rule this should have had:
 *
 *     WITNESS(i) = 0xB0B32000 + 17*i + (clean & 255)
 *
 * `clean` is the POISON THE WALKER ITSELF WROTE and read back out of NW, so
 * unit 1 is now a function of unit 0 and of the pad's role, and a producer
 * that poisons the wrong magic, probes the wrong address, or fabricates the
 * read-back stores a different word.  The published limit stands: a saboteur
 * who RECOMPUTES the rule rather than loading it produces an identical unit,
 * so units 0, 2 and 3 remain the load-bearing ones.
 * Falsifiers: BREAK_CANWITLIT (the old literal), BREAK_CANCONSTACTUAL. */
static uint32_t witness_rule(uint32_t clean, int i)
{
    return 0xB0B32000u + (uint32_t)(17 * i) + (clean & 255u);
}
static uint32_t witness(uint32_t clean, int i)
{
#ifdef BREAK_CANWITLIT
    (void)clean;
    return 0xC0DE0000u | (uint32_t)i;
#else
    return witness_rule(clean, i);
#endif
}

static int canary_v2(uint32_t *out)
{
    int i, bad = 0;
    for (i = 0; i < NPAD; i++) {
        int off = padbase[i] + probeslot(i);
        int nexp, first, firstpad, viol;
        uint32_t clean, dirty;
        poison_pads();
#ifdef BREAK_CANSTUBPOISON
        zero_pads();
#endif
        clean = nw_unit(off);
        nw_unit_put(off, witness(clean, i));
#ifdef BREAK_CANSTUBCHECK
        viol = 0; nexp = 0; first = -1; firstpad = 0;
        (void)viol;
#else
        viol = walk_pads(&nexp, &first, &firstpad);
        (void)viol; (void)nexp;
#endif
        dirty = nw_unit(off);
#ifdef BREAK_CANCONSTACTUAL
        /* v1's actual defect, transplanted: the "actual" field is written by
         * CONSTRUCTION rather than read back out of NW */
        { int zi = zone_of(off); dirty = (zi >= 0) ? zone_magic(&zones[zi]) : PGUARD; }
#endif
        out[4 * i + 0] = clean;
        out[4 * i + 1] = dirty;
        out[4 * i + 2] = (uint32_t)((first == off) ? firstpad : 0);
        out[4 * i + 3] = (uint32_t)(first < 0 ? 0 : first);
        if (out[4 * i + 2] == 0) bad++;
    }
    zero_pads();
    return bad;
}

/* ------------------------------------------------------------- Borland LCG */

static uint32_t lcg_state;
static void lcg_srand(unsigned s) { lcg_state = s & 0xFFFFu; }
static int lcg_rand(void)
{
    lcg_state = lcg_state * 0x015A4E35u + 1u;
    return (int)((lcg_state >> 16) & 0x7FFF);
}

/* ---------------------------------------------------------------- palette */

static unsigned char range8088[64 * 3];
static unsigned char pal6[768];      /* tmppal          (unsigned char) */
static unsigned char curpal6[768];   /* what the DAC holds */
static unsigned char srfpal6[768];   /* surface_palette (char, read unsigned) */
static unsigned char retpal6[768];   /* return_palette  */
/* retpal6 and region_at are part of the model's surface, referenced by the
 * self-test below and by the KSELF fields; keep them addressable. */
static int upload_lo = -1, upload_hi = -1;

#define MAXUP 32
static int up_a[MAXUP], up_b[MAXUP], n_up;

#define MAXMARK 16
static uint32_t mk_pal[MAXMARK], mk_cur[MAXMARK];
static int n_mark;

static uint32_t fnv_buf(const unsigned char *b, int n)
{
    uint32_t h = fnv_init();
    int i;
    for (i = 0; i < n; i++) h = fnv_unit(h, (uint32_t)b[i]);
    return h;
}

static void pal_mark(void)
{
    if (n_mark >= MAXMARK) return;
    mk_pal[n_mark] = fnv_buf(pal6, 768);
    mk_cur[n_mark] = fnv_buf(curpal6, 768);
    n_mark++;
}

static void range8088_init(void)
{
    int i;
    for (i = 0; i < 64; i++) {
        range8088[3 * i + 0] = (unsigned char)i;
        range8088[3 * i + 1] = (unsigned char)i;
        range8088[3 * i + 2] = (unsigned char)i;
    }
}

/* `char filtro_rosso` is SIGNED under Borland's default.  A caller that passes
 * 200 does not get 200; it gets -56.  Pinned scenario step 7 constructs
 * exactly that. */
static int schar(int f) { return (int)(signed char)(f & 0xFF); }

/* The DOS-16 filter.  `unsigned temp` is 16 bits under Borland; `temp *= f`
 * converts a signed char to unsigned and multiplies mod 65536; `temp /= 63` is
 * an UNSIGNED divide.  Since |v*f| <= 255*128 = 32640 < 65536, every negative
 * product lands in [32896,65535], divides to at least 522, and CLAMPS to 63 --
 * so a 32-bit `unsigned` gives the same answer, which is what makes this file
 * and fb_pal.py comparable at all.  BREAK_PYFILT is the floor-division form
 * fb_pal.py used to carry; it is wrong for every negative filter. */
static int filter_one(int v, int f)
{
#ifdef BREAK_DIV64
    int div = 64;
#else
    int div = 63;
#endif
    long temp;
#ifdef BREAK_PYFILT
    {
        long p = (long)v * (long)f;
        temp = (p >= 0) ? p / div : -(((-p) + div - 1) / div);   /* floor */
    }
#else
    temp = (long)(((unsigned)((int)v * (int)f)) & 0xFFFFu) / (unsigned)div;
#endif
#ifndef BREAK_NOCLAMP
    if (temp > 63) temp = 63;
#endif
    return (int)(temp & 0xFF);
}

/* THE CONTROL.  filter_one carries three `#ifdef BREAK_*` arms, so every
 * expectation this file computed with filter_one moved in lockstep with the
 * sabotage and the C self-test was BLIND to BREAK_DIV64: measured, a
 * -DBREAK_DIV64 build printed "RESULT: PASS (0 failures)" while producing a
 * different palette in every record it dumped.
 *
 * filter_one_clean carries no preprocessor arm at all and is never reachable
 * from any -DBREAK_*.  Expectations are built from it; the subject is
 * filter_one.  Two implementations, one claim.
 *
 * Deliberately written from NOCTIS-0.CPP:200-214 again rather than copied:
 *   `unsigned temp; temp = tavola[c]; temp *= filtro; temp /= 63;
 *    if (temp > 63) temp = 63; tavola[c] = temp;`
 * with Borland's 16-bit `unsigned`. */
static int filter_one_clean(int v, int f)
{
    unsigned temp = (unsigned)((v * f)) & 0xFFFFu;
    temp /= 63u;
    if (temp > 63u) temp = 63u;
    return (int)(temp & 0xFFu);
}

/* NOCTIS-0.CPP:179-241.  src == NULL means the self-copy case
 * `tavola_colori(tmppal + 3*first, first, n, ...)`: source aliases
 * destination, the copy is a no-op, the filter runs in place.
 *
 * The DESTINATION is always tmppal, whatever the first argument says -- that
 * argument is the SOURCE (NOCTIS-0.CPP:186).  Do NOT "fix" this symmetrically
 * with shade's destination parameter. */
static void tavola_colori(const unsigned char *src, unsigned first, unsigned n,
                          int fr_in, int fg_in, int fb_in)
{
    unsigned c, cc = 0, n3 = n * 3, c0 = first * 3;
    int f[3];
    f[0] = schar(fr_in); f[1] = schar(fg_in); f[2] = schar(fb_in);

    if (src) {
        c = c0;
        while (cc < n3) pal6[c++] = src[cc++];
    }
#ifdef BREAK_NOSELF
    else {
        for (c = c0; c < c0 + n3; c++) pal6[c] = 0;
    }
#endif

    c = c0;
    while (c < c0 + n3) {
        int k;
        for (k = 0; k < 3; k++) { pal6[c] = (unsigned char)filter_one(pal6[c], f[k]); c++; }
    }

    /* the asm tail: mov cx, first*3; add cx, n*3; mov al,0; out 0x3c8,al
     * -- the upload ALWAYS starts at colour zero. */
#ifdef BREAK_UPLOADFIRST
    upload_lo = (int)c0;
#else
    upload_lo = 0;
#endif
    upload_hi = (int)(c0 + n3);
    for (c = (unsigned)upload_lo; c < (unsigned)upload_hi; c++) curpal6[c] = pal6[c];
    if (n_up < MAXUP) { up_a[n_up] = upload_lo; up_b[n_up] = upload_hi; n_up++; }
}

/* `tavola_colori(surface_palette, first, n, w, w, w)` -- the shape 14 of
 * shade's callers set up.  The whole point of surface_palette is that the
 * SOURCE is the unfiltered original, so two successive fades do not compound.
 * BREAK_SELFSOURCE reproduces the compounding. */
static void fade_from(const unsigned char *srcbuf, unsigned first, unsigned n,
                      int fr, int fg, int fb)
{
#ifdef BREAK_SELFSOURCE
    (void)srcbuf;
    tavola_colori(NULL, first, n, fr, fg, fb);
#else
    tavola_colori(srcbuf + 3 * first, first, n, fr, fg, fb);
#endif
}

/* NOCTIS-0.CPP:1151-1200.  All accumulators are `float`.  The store to
 * palette_buffer[] is a C float->unsigned char conversion, i.e. TRUNCATION
 * toward zero -- lino's `=,` rounds to nearest, which is why this is a trap. */
static unsigned char shade_place(float v)
{
    if (v >= 0 && v < 64) {
#ifdef BREAK_ROUNDSHADE
        return (unsigned char)(int)(v + 0.5f);
#else
        return (unsigned char)(int)v;
#endif
    }
    /* the original's inverted clamp; provably equivalent to a plain clamp */
    return (unsigned char)(v > 0 ? 63 : 0);
}

/* `void shade (unsigned char far *palette_buffer, ...)`.  14 of its 21 call
 * sites pass surface_palette, 7 pass tmppal.  BREAK_IGNOREDST is the Wave 5
 * defect: the destination hard-coded to tmppal, which cannot express two
 * thirds of the game's shade calls.
 *
 * Detail that must not be lost: surface_palette and return_palette are
 * declared `char` (signed) but shade takes `unsigned char far *`, so the
 * STORES are unsigned and every read is through tavola_colori's
 * `unsigned char *`.  No sign extension ever occurs. */
static void shade(unsigned char *buf, int first_color, int number_of_colors,
                  float sr, float sg, float sb, float fr, float fg, float fb)
{
    int count = number_of_colors;
    float k = (float)(1.00 / (double)number_of_colors);
    float dr = (fr - sr) * k, dg = (fg - sg) * k, db = (fb - sb) * k;
    int i = first_color * 3;
#ifdef BREAK_IGNOREDST
    buf = pal6;
#endif
    while (count) {
        buf[i + 0] = shade_place(sr);
        buf[i + 1] = shade_place(sg);
        buf[i + 2] = shade_place(sb);
        sr += dr; sg += dg; sb += db;
        i += 3; count--;
    }
}

/* The 6->8 choice, made once, here.  x4 because the game's own snapshot()
 * writes tmppal[c]*4 (NOCTIS-0.CPP:6418). */
static void lut_rebuild(void)
{
    int i;
    for (i = 0; i < 256; i++) {
        unsigned r = curpal6[3 * i + 0], g = curpal6[3 * i + 1], b = curpal6[3 * i + 2];
#ifdef BREAK_SHIFTOR
        r = (r << 2) | (r >> 4); g = (g << 2) | (g >> 4); b = (b << 2) | (b >> 4);
#else
        r *= 4; g *= 4; b *= 4;
#endif
        PAL[i] = (r << 16) | (g << 8) | b;
    }
}

/* ------------------------------------------------------------- page ops
 * NOCTIS-0.CPP:307-345.  Both walk QUADWORDS DWORDS, not 64000 bytes.
 * QUADWORDS is a VARIABLE: it steady-states at 14560 after NOCTIS.CPP:2206
 * (16000 - 1440).  At 14560 mask_pixels' DI runs 2884..61123, under 65536, so
 * class-A site A3's wrap is UNREACHABLE. */
#define QW_DECLARED 16000
#define QW_STEADY   14560
static int QUADWORDS = QW_DECLARED;

static void pclear(int base, int pattern)
{
    int i, n = QUADWORDS * 4;
#ifdef BREAK_QUADWORDS
    n = 64000;
#endif
    for (i = 0; i < n; i++) nw_put(base + i, pattern);
}

static void pcopy(int dest, int sorg)
{
    int i, n = QUADWORDS * 4;
#ifdef BREAK_QUADWORDS
    n = 64000;
#endif
    for (i = 0; i < n; i++) nw_put(dest + i, nw_get(sorg + i));
}

static void areaclear(int base, int x, int y, int l, int a, int color)
{
    int j, i;
    for (j = 0; j < a; j++)
        for (i = 0; i < l; i++)
            nw_put(base + 320 * (y + j) + x + i, color);
}

/* ------------------------------------------------------------ present path */
static void present_expand(void)
{
    int i;
    int src = rbase[R_ADAPTOR];
    for (i = 0; i < 64000; i += 4) {
        FB[i + 0] = PAL[nw_get(src + i + 0)];
        FB[i + 1] = PAL[nw_get(src + i + 1)];
        FB[i + 2] = PAL[nw_get(src + i + 2)];
        FB[i + 3] = PAL[nw_get(src + i + 3)];
    }
}

/* ================================================================= class A
 *
 * The mask goes WHERE THE DOS CODE TRUNCATES, not at the final address:
 *     ((py+px) mod 65536) >> 1   !=   ((py+px) >> 1) mod 65536
 * so spot's error on a wrap is 65536 and cirrus' is 32768.  A single "mask the
 * final index" helper would silently halve cirrus' error and still be wrong.
 */

enum { SITE_SPOT = 1, SITE_CIRRUS = 2, SITE_CRATER = 3, SITE_ALIAS8 = 4, NSITE = 5 };
static long site_calls[NSITE], site_wraps[NSITE];
static uint32_t site_mfnv[NSITE], site_nfnv[NSITE];
static int site_contain_fail;

static void site_init(void)
{
    int i;
    for (i = 0; i < NSITE; i++) {
        site_calls[i] = site_wraps[i] = 0;
        site_mfnv[i] = site_nfnv[i] = fnv_init();
    }
    site_contain_fail = 0;
}

/* The containment assertion the debug build carries: a masked address must lie
 * in [base(B), base(B)+size(B)) or in B's own SUB zone. */
static int contained(int r, int nw)
{
    int zi;
    if (nw >= rbase[r] && nw < rbase[r] + rsize[r]) return 1;
    zi = zone_of(nw);
    return (zi >= 0 && zones[zi].owner == r && zones[zi].role == 1);
}

static int site_note(int site, int r, int masked, int naive)
{
    site_calls[site]++;
    if (masked != naive) site_wraps[site]++;
    site_mfnv[site] = fnv_unit(site_mfnv[site], (uint32_t)masked);
    site_nfnv[site] = fnv_unit(site_nfnv[site], (uint32_t)naive);
    if (!contained(r, masked)) site_contain_fail++;
    return masked;
}

/* NOCTIS-0.CPP:4485.  les di,p_background / add di,py / add di,px -- DI is
 * 16 bits and already holds the pointer's own offset 4. */
static int spot_index(int px, int py)
{
    int naive = segbase(R_P_BACKGROUND) + SEG_OFFSET + py + px;
#ifdef BREAK_MASKSPOT
    int masked = naive;
#else
    int masked = seg_index(R_P_BACKGROUND, SEG_OFFSET + py + px);
#endif
    return site_note(SITE_SPOT, R_P_BACKGROUND, masked, naive);
}

/* NOCTIS-0.CPP:4715.  mov bx,py / add bx,px / shr bx,1 / es:[bx+di] -- the
 * truncation is on (py+px) BEFORE the shift; the offset is added after. */
static int cirrus_index(int px, int py)
{
    int base = segbase(R_OBJECTSCHART);
    int naive = base + SEG_OFFSET + ((py + px) >> 1);
#if defined(BREAK_MASKCIRRUSADDR)
    int masked = base + (((SEG_OFFSET + ((py + px) >> 1))) & 0xFFFF);
#elif defined(BREAK_MASKCIRRUS)
    int masked = naive;
#else
    int masked = base + SEG_OFFSET + (((py + px) & 0xFFFF) >> 1);
#endif
    return site_note(SITE_CIRRUS, R_OBJECTSCHART, masked, naive);
}

/* alias 8.  TDPOLYGS.H:2684 -- `les ax, adapted` then `mov es:[0xFA00], al`.
 * ES is the SEGMENT of adapted and the pointer's own offset is discarded, so
 * this is the SAME primitive with a constant index, not a special case. */
#define ALIAS8_SEGOFF 0xFA00
static int alias8_at(int segoff)
{
    int naive = rbase[R_ADAPTED] + segoff;
    int masked = seg_index(R_ADAPTED, segoff);
    return site_note(SITE_ALIAS8, R_ADAPTED, masked, naive);
}
static int alias8_index(void) { return alias8_at(ALIAS8_SEGOFF); }

/* ------------------------------------------------------------ digit_at
 * NOCTIS.CPP:604-628.  txtr is based at p_surfacemap and the loop's first
 * iteration writes txtr[-6] and txtr[-5], i.e. BELOW the buffer -- which lands
 * in p_surfacemap's own SUB zone, on the allowance list.  niv-lr "fixed" this
 * by starting the loop at n = 1, silently dropping the top scanline of every
 * glyph AND the whole six-unit underflow signature. */
static uint32_t digimap2[DM2_BYTES / 4];
static const uint32_t pp32[32] = {
    0x00000001u, 0x00000002u, 0x00000004u, 0x00000008u,
    0x00000010u, 0x00000020u, 0x00000040u, 0x00000080u,
    0x00000100u, 0x00000200u, 0x00000400u, 0x00000800u,
    0x00001000u, 0x00002000u, 0x00004000u, 0x00008000u,
    0x00010000u, 0x00020000u, 0x00040000u, 0x00080000u,
    0x00100000u, 0x00200000u, 0x00400000u, 0x00800000u,
    0x01000000u, 0x02000000u, 0x04000000u, 0x08000000u,
    0x10000000u, 0x20000000u, 0x40000000u, 0x80000000u
};

static int load_digimap2(const char *supports_nct)
{
    FILE *f = fopen(supports_nct, "rb");
    long size;
    if (!f) return 0;
    fseek(f, 0, SEEK_END);
    size = ftell(f);
    fseek(f, size + OFF_DIGIMAP2, SEEK_SET);
    if (fread(digimap2, 1, DM2_BYTES, f) != DM2_BYTES) { fclose(f); return 0; }
    fclose(f);
    return 1;
}

static void digit_at(int digit, int color, int shader)
{
    int txtr = rbase[R_P_SURFACEMAP];
    int pixel_color = color % 64;
    int n, m, d, i;
    if (!(digit > 32 && digit <= 96)) return;
    d = (digit - 32) * 36;
#ifdef BREAK_DIGITN1
    for (n = 1; n < 36; n++) {
#else
    for (n = 0; n < 36; n++) {
#endif
        i = 256 * n - 5;
        nw_put(txtr + i - 1, 0);              /* txtr[-6] when n == 0 */
        for (m = 0; m < 32; m++) {
            if (digimap2[n + d] & pp32[m]) nw_put(txtr + i, pixel_color);
            else                           nw_put(txtr + i, 0);
            i++;
        }
        if (shader) pixel_color--;
    }
    nw_put(txtr + 256 * 36 - 6, 0);
}

/* ------------------------------------------------------------ texel address
 * TDPOLYGS.H:2817-2821.  texel = ((V>>8)&0xFF)*256 + ((U>>8)&0xFF), assembled
 * in the 16-bit BX, so it is confined to 0..65535 by construction. */
static int texel_addr(int u, int v) { return (((v >> 8) & 0xFF) * 256) + ((u >> 8) & 0xFF); }

/* ---------------------------------------------------------------- FBDUMP v2 */

#define FBD_MAGIC 0x46424431u
#define FBD_VERSION 2
enum { K_INDEXPAGE = 1, K_PALETTE6 = 2, K_LUT = 3, K_TICKLOG = 4, K_LAYOUT = 5,
       K_CANARY = 6, K_KSELF = 7, K_KFRM = 8, K_ZONES = 9, K_WRAPCOUNT = 10,
       K_SERVOLOG = 11 };
enum { T_ADAPTED = 1, T_ADAPTOR = 2, T_GLYPH = 3, T_PAL6 = 4, T_CURPAL6 = 5,
       T_LUT = 6, T_LAYOUT = 7, T_CANARY = 8, T_ZONES = 9, T_TICKLOG = 10,
       T_SERVOLOG = 11, T_WRAPCOUNT = 12, T_SELFCHECK = 13, T_FRAMECOST = 14 };

static void put_u32le(FILE *f, uint32_t v)
{
    fputc((int)(v & 255), f); fputc((int)((v >> 8) & 255), f);
    fputc((int)((v >> 16) & 255), f); fputc((int)((v >> 24) & 255), f);
}

static int fbdump(const char *path, int kind, const uint32_t *payload, int count,
                  int width, int height, int cpms, int ticks, int tag)
{
    FILE *f = fopen(path, "wb");
    int i;
    if (!f) { fprintf(stderr, "cannot write %s\n", path); return 0; }
    put_u32le(f, FBD_MAGIC); put_u32le(f, FBD_VERSION); put_u32le(f, (uint32_t)kind);
    put_u32le(f, (uint32_t)width); put_u32le(f, (uint32_t)height);
    put_u32le(f, (uint32_t)count); put_u32le(f, (uint32_t)cpms); put_u32le(f, (uint32_t)ticks);
    put_u32le(f, (uint32_t)tag);
    for (i = 0; i < 7; i++) put_u32le(f, 0);
    for (i = 0; i < count; i++) put_u32le(f, payload[i]);
    fclose(f);
    return 1;
}

/* ------------------------------------------------------------------ tick */
static int32_t tick_carry;
static int32_t tick_period(int32_t cpms)
{
    int32_t num = cpms * 44505 + tick_carry;
    int32_t q = num / 596591;
    tick_carry = num - q * 596591;
    return cpms * 55 - q;
}

static int tick_expired(uint32_t now, uint32_t deadline)
{
#ifdef BREAK_TICKCMP
    return now >= deadline;
#else
    return (int32_t)(now - deadline) >= 0;
#endif
}

/* ================================================== THE FIXTURE INTERPRETER
 *
 * WHAT CHANGED, AND WHY IT IS THE POINT OF THE WAVE.
 *
 * The scenarios used to be three hard-coded C functions.  fb_layout.py had
 * three hard-coded Python functions.  tests/w5probe.txt had a THIRD, analytic
 * ramp.  Nothing reconciled them, so the ADAPTED comparison differed in 63,988
 * of 64,000 units and the red row it printed was a category error, not a
 * finding: two producers that ran different stimuli have no oracle between
 * them and the honest verdict is NOT GRADED.
 *
 * Now there is ONE stimulus -- docs-notes/FIXTURE1.txt -- and this file is one
 * of its interpreters.  The distinction that has to survive review:
 *
 *     the SCRIPT is shared;  the IMPLEMENTATION of every step is not.
 *
 * A step whose answer is written in the script is a transcription check.  So
 * the script says `poke_alias8 segoff=0xFA00` and never the index 63996;
 * `quadwords phase=steady` and never 14560; `copy_glyph count=9216` and never
 * digit_at's -5 row origin.  Every one of those is computed here, from the
 * 1996 sources, and a producer that computes it differently diverges.
 *
 * That rule is ENFORCED, not remembered: fx_load() runs the fixture's own
 * FORBIDDEN-NUMERAL lint over the script before executing a single step and
 * refuses to run if the script hands over an address, an extent, a stride or a
 * magic.  Add `63996` to the fixture and this program stops with an error.
 *
 * BUILD IDENTITY.  The SHA-256 of the script goes into the KSELF record, so
 * "the two producers ran the same stimulus" is a hash comparison rather than a
 * substring hunt in a prose document.
 */

/* p_background is the 360x180 orbital map: NOCTIS-0.CPP:4583 `mov dx, 360`
 * inside wave(), and the same 360 in spot()'s callers.  DERIVED HERE, not
 * supplied by the script -- the script says which rows to sweep, not how wide
 * a row is. */
#define ORBIT_COLS 360

/* digit_at's row origin, NOCTIS.CPP:614 `i = 256*n - 5` at n == 0.  The glyph
 * window starts SIX units below p_surfacemap's base and the first two units it
 * writes are the underflow.  DERIVED HERE; the script says `copy_glyph`. */
static int glyph_window(void) { return rbase[R_P_SURFACEMAP] + 256 * 0 - 5; }

#define FX_MAXTOK 24
typedef struct { const char *op; char *k[FX_MAXTOK]; char *v[FX_MAXTOK]; int n; } FxL;

static char  *fx_text = NULL;
static long   fx_len = 0;
static char   fx_sha[80];
static char   fx_path_used[1024];
static char   fx_forbid[2048];
static int    fx_lint_hits = 0;
static char   fx_lint_msg[256];
static int    fx_ops_run = 0;

/* the two values the compound section's grader needs, RECORDED BY THE RUN
 * rather than hard-coded next to the expectation */
static unsigned char fx_snapshot[768];
static int  fx_have_snapshot = 0;
static int  fx_srf_nonzero = 0;
static int  fx_last_fade[3] = { 0, 0, 0 };
static int  fx_have_fade = 0;

static int fx_isnumtok(const char *s)
{
    if (*s == '-' || *s == '+') s++;
    if (!*s) return 0;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) {
        s += 2;
        if (!*s) return 0;
        while (*s) { if (!isxdigit((unsigned char)*s)) return 0; s++; }
        return 1;
    }
    while (*s) { if (!isdigit((unsigned char)*s)) return 0; s++; }
    return 1;
}

/* case-insensitive whole-token equality, so 0xFFFF and 0xffff are the same */
static int fx_toke(const char *a, const char *b)
{
    while (*a && *b) { if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) return 0; a++; b++; }
    return *a == 0 && *b == 0;
}

static void fx_lint_token(const char *tok, int lineno)
{
    char list[2048], *p, *save = NULL;
    if (!fx_isnumtok(tok)) return;
    strncpy(list, fx_forbid, sizeof list - 1);
    list[sizeof list - 1] = 0;
    (void)save;
    for (p = strtok(list, ","); p; p = strtok(NULL, ",")) {
        while (*p == ' ') p++;
        if (fx_toke(p, tok)) {
            fx_lint_hits++;
            if (fx_lint_hits == 1)
                snprintf(fx_lint_msg, sizeof fx_lint_msg,
                         "line %d hands over the derived quantity `%s`", lineno, tok);
        }
    }
}

/* split one line into op + key=value pairs.  `scratch` is mutated. */
static int fx_split(char *scratch, FxL *L)
{
    char *p = scratch;
    L->n = 0; L->op = NULL;
    while (*p) {
        char *t, *eq;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (!*p) break;
        t = p;
        while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') p++;
        if (*p) *p++ = 0;
        if (!L->op) { L->op = t; continue; }
        eq = strchr(t, '=');
        if (!eq) continue;
        *eq = 0;
        if (L->n < FX_MAXTOK) { L->k[L->n] = t; L->v[L->n] = eq + 1; L->n++; }
    }
    return L->op != NULL;
}

static const char *fx_str(const FxL *L, const char *key, const char *def)
{
    int i;
    for (i = 0; i < L->n; i++) if (!strcmp(L->k[i], key)) return L->v[i];
    return def;
}

static long fx_int(const FxL *L, const char *key, long def)
{
    const char *s = fx_str(L, key, NULL);
    if (!s) return def;
    if (!strcmp(s, "all")) return 256;          /* the whole palette */
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) return strtol(s + 2, NULL, 16);
    if (isalpha((unsigned char)s[0]) && !s[1]) return (long)(unsigned char)s[0];  /* digit=A */
    return strtol(s, NULL, 10);
}

static double fx_flt(const FxL *L, const char *key, double def)
{
    const char *s = fx_str(L, key, NULL);
    return s ? strtod(s, NULL) : def;
}

static int fx_page(const char *s)
{
    if (!s) return -1;
    if (!strcmp(s, "hidden"))  return R_ADAPTED;   /* the DOS `adapted` */
    if (!strcmp(s, "visible")) return R_ADAPTOR;   /* DOS A000:0000 */
    return -1;
}

static int fx_region(const char *s)
{
    int i;
    if (!s) return -1;
    for (i = 0; i < NREG; i++) if (!strcmp(s, rname[i])) return i;
    return -1;
}

static unsigned char *fx_palbuf(const char *s)
{
    if (!s) return NULL;
    if (!strcmp(s, "tmppal"))  return pal6;
    if (!strcmp(s, "surface")) return srfpal6;
    if (!strcmp(s, "return"))  return retpal6;
    return NULL;
}

#ifdef __GNUC__
__attribute__((format(printf, 1, 2)))
#endif
static int fx_fatal(const char *fmt, ...)
{
    va_list ap;
    fprintf(stderr, "FIXTURE ERROR: ");
    va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
    fprintf(stderr, "\n");
    exit(2);
    return 0;
}

/* load, hash and lint.  Returns 0 if the file is missing. */
static int fx_load(const char *path)
{
    char *line, *next;
    int lineno = 0, sawver = 0;

    strncpy(fx_path_used, path, sizeof fx_path_used - 1);
    fx_text = slurp(path, &fx_len);
    if (!fx_text) return 0;
    sha256_file(path, fx_sha, NULL);

    /* pass 1: the LINT declaration and the version */
    for (line = fx_text; line && *line; line = next) {
        char scratch[1024];
        FxL L;
        next = strchr(line, '\n');
        if (next) next++;
        {
            size_t n = next ? (size_t)(next - line) : strlen(line);
            if (n >= sizeof scratch) n = sizeof scratch - 1;
            memcpy(scratch, line, n); scratch[n] = 0;
        }
        lineno++;
        { char *q = scratch; while (*q == ' ' || *q == '\t') q++;
          if (*q == '#' || *q == '\r' || *q == '\n' || !*q) continue; }
        if (!fx_split(scratch, &L)) continue;
        if (!strcmp(L.op, "FIXTURE1")) sawver = 1;
        if (!strcmp(L.op, "LINT")) {
            const char *f = fx_str(&L, "forbid", "");
            strncpy(fx_forbid, f, sizeof fx_forbid - 1);
            fx_forbid[sizeof fx_forbid - 1] = 0;
        }
    }
    if (!sawver) fx_fatal("%s carries no FIXTURE1 version line", path);
    if (!fx_forbid[0]) fx_fatal("%s carries no LINT forbid= list", path);

    /* pass 2: the lint, over EXECUTABLE lines only.  Comments and the LINT
     * line itself are exempt -- the LINT line is the list. */
    lineno = 0;
    for (line = fx_text; line && *line; line = next) {
        char scratch[1024];
        FxL L;
        int i;
        next = strchr(line, '\n');
        if (next) next++;
        {
            size_t n = next ? (size_t)(next - line) : strlen(line);
            if (n >= sizeof scratch) n = sizeof scratch - 1;
            memcpy(scratch, line, n); scratch[n] = 0;
        }
        lineno++;
        { char *q = scratch; while (*q == ' ' || *q == '\t') q++;
          if (*q == '#' || *q == '\r' || *q == '\n' || !*q) continue; }
        if (!fx_split(scratch, &L)) continue;
        if (!strcmp(L.op, "LINT")) continue;
        for (i = 0; i < L.n; i++) {
            char vv[256], *piece;
            strncpy(vv, L.v[i], sizeof vv - 1); vv[sizeof vv - 1] = 0;
            for (piece = strtok(vv, ","); piece; piece = strtok(NULL, ","))
                fx_lint_token(piece, lineno);
        }
    }
    return 1;
}

/* execute one named section */
static void fx_run(const char *section)
{
    char *line, *next;
    int in = 0;

    if (!fx_text) fx_fatal("fx_run(%s) with no fixture loaded", section);

    for (line = fx_text; line && *line; line = next) {
        char scratch[1024];
        FxL L;
        next = strchr(line, '\n');
        if (next) next++;
        {
            size_t n = next ? (size_t)(next - line) : strlen(line);
            if (n >= sizeof scratch) n = sizeof scratch - 1;
            memcpy(scratch, line, n); scratch[n] = 0;
        }
        { char *q = scratch; while (*q == ' ' || *q == '\t') q++;
          if (*q == '#' || *q == '\r' || *q == '\n' || !*q) continue; }
        if (!fx_split(scratch, &L)) continue;

        if (!strcmp(L.op, "SECTION")) {
            /* `SECTION name` -- the name arrives as the op's first bare token,
             * which fx_split drops, so re-read it here */
            char again[1024], *p = again, *t;
            {
                size_t n = next ? (size_t)(next - line) : strlen(line);
                if (n >= sizeof again) n = sizeof again - 1;
                memcpy(again, line, n); again[n] = 0;
            }
            while (*p == ' ' || *p == '\t') p++;
            p += strlen("SECTION");
            while (*p == ' ' || *p == '\t') p++;
            t = p;
            while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') p++;
            *p = 0;
            in = !strcmp(t, section);
            continue;
        }
        if (!strcmp(L.op, "END")) { if (in) return; continue; }
        if (!in) continue;
        if (!strcmp(L.op, "FIXTURE1") || !strcmp(L.op, "LINT")) continue;

        fx_ops_run++;

        /* ------------------------------------------------ palette ops */
        if (!strcmp(L.op, "reset_palettes")) {
            memset(pal6, 0, sizeof pal6);
            memset(curpal6, 0, sizeof curpal6);
            memset(srfpal6, 0, sizeof srfpal6);
            n_up = 0; n_mark = 0;
            fx_have_snapshot = 0; fx_have_fade = 0;
        } else if (!strcmp(L.op, "load_range8088")) {
            range8088_init();
        } else if (!strcmp(L.op, "mark")) {
            pal_mark();
        } else if (!strcmp(L.op, "tavola_colori")) {
            const char *src = fx_str(&L, "src", "self");
            unsigned first = (unsigned)fx_int(&L, "first", 0);
            unsigned n = (unsigned)fx_int(&L, "n", 0);
            int fr = (int)fx_int(&L, "fr", 63), fg = (int)fx_int(&L, "fg", 63),
                fb = (int)fx_int(&L, "fb", 63);
            if (!strcmp(src, "range8088")) tavola_colori(range8088, first, n, fr, fg, fb);
            else if (!strcmp(src, "self"))  tavola_colori(NULL, first, n, fr, fg, fb);
            else fx_fatal("tavola_colori src=%s", src);
        } else if (!strcmp(L.op, "shade")) {
            unsigned char *dst = fx_palbuf(fx_str(&L, "dst", "tmppal"));
            if (!dst) fx_fatal("shade dst=%s", fx_str(&L, "dst", "?"));
            shade(dst, (int)fx_int(&L, "first", 0), (int)fx_int(&L, "n", 1),
                  (float)fx_flt(&L, "sr", 0), (float)fx_flt(&L, "sg", 0),
                  (float)fx_flt(&L, "sb", 0), (float)fx_flt(&L, "fr", 0),
                  (float)fx_flt(&L, "fg", 0), (float)fx_flt(&L, "fb", 0));
        } else if (!strcmp(L.op, "lut_rebuild")) {
            lut_rebuild();
        } else if (!strcmp(L.op, "snapshot_surface")) {
            int i;
            memcpy(fx_snapshot, srfpal6, 768);
            fx_have_snapshot = 1;
            fx_srf_nonzero = 0;
            for (i = 0; i < 768; i++) if (fx_snapshot[i]) fx_srf_nonzero++;
        } else if (!strcmp(L.op, "fade_from")) {
            unsigned char *src = fx_palbuf(fx_str(&L, "src", "surface"));
            int fr = (int)fx_int(&L, "fr", 63), fg = (int)fx_int(&L, "fg", 63),
                fb = (int)fx_int(&L, "fb", 63);
            if (!src) fx_fatal("fade_from src=%s", fx_str(&L, "src", "?"));
            fade_from(src, (unsigned)fx_int(&L, "first", 0),
                      (unsigned)fx_int(&L, "n", 0), fr, fg, fb);
            fx_last_fade[0] = fr; fx_last_fade[1] = fg; fx_last_fade[2] = fb;
            fx_have_fade = 1;

        /* --------------------------------------------------- page ops */
        } else if (!strcmp(L.op, "pads_release")) {
            zero_pads();
        } else if (!strcmp(L.op, "quadwords")) {
            const char *ph = fx_str(&L, "phase", "");
            if (!strcmp(ph, "declared")) QUADWORDS = QW_DECLARED;
            else if (!strcmp(ph, "steady")) QUADWORDS = QW_STEADY;
            else fx_fatal("quadwords phase=%s", ph);
        } else if (!strcmp(L.op, "pclear")) {
            int r = fx_page(fx_str(&L, "page", NULL));
            if (r < 0) fx_fatal("pclear page=%s", fx_str(&L, "page", "?"));
            pclear(rbase[r], (int)fx_int(&L, "pattern", 0));
        } else if (!strcmp(L.op, "pcopy")) {
            int d = fx_page(fx_str(&L, "dst", NULL)), s = fx_page(fx_str(&L, "src", NULL));
            if (d < 0 || s < 0) fx_fatal("pcopy dst/src");
            pcopy(rbase[d], rbase[s]);
        } else if (!strcmp(L.op, "srand")) {
            lcg_srand((unsigned)fx_int(&L, "seed", 0));
        } else if (!strcmp(L.op, "fill_rand")) {
            int r = fx_region(fx_str(&L, "region", NULL));
            long count = fx_int(&L, "count", 0);
            int mask = (int)fx_int(&L, "mask", 255), bias = (int)fx_int(&L, "bias", 0);
            long i;
            if (r < 0) fx_fatal("fill_rand region=%s", fx_str(&L, "region", "?"));
            for (i = 0; i < count; i++) nw_put(rbase[r] + (int)i, bias + (lcg_rand() & mask));
        } else if (!strcmp(L.op, "sea_texture")) {
            int d = fx_page(fx_str(&L, "dst", NULL));
            int s = fx_region(fx_str(&L, "src", NULL));
            long count = fx_int(&L, "count", 0);
            long us = fx_int(&L, "ustride", 1), vs = fx_int(&L, "vstride", 1);
            long i;
            if (d < 0 || s < 0) fx_fatal("sea_texture dst/src");
            for (i = 0; i < count; i++) {
                /* the 16-bit U/V accumulators and texel_addr's own assembly of
                 * BX are MECHANISM: they live here, not in the script.  Texels
                 * 32768..65535 read past the end of n_globes_map, which is the
                 * class-C behaviour the farmalloc order exists to reproduce. */
                int u = (int)((i * us) & 0xFFFF);
                int v = (int)((i * vs) & 0xFFFF);
                nw_put(rbase[d] + (int)i, nw_get(rbase[s] + texel_addr(u, v)));
            }
        } else if (!strcmp(L.op, "digit_at")) {
            digit_at((int)fx_int(&L, "digit", 'A'), (int)fx_int(&L, "color", 0),
                     (int)fx_int(&L, "shader", 0));
        } else if (!strcmp(L.op, "copy_glyph")) {
            int d = fx_page(fx_str(&L, "dst", NULL));
            long off = fx_int(&L, "dst_off", 0), count = fx_int(&L, "count", 0), i;
            if (d < 0) fx_fatal("copy_glyph dst");
            for (i = 0; i < count; i++)
                nw_put(rbase[d] + (int)off + (int)i, nw_get(glyph_window() + (int)i));
        } else if (!strcmp(L.op, "poke_alias8")) {
            long segoff = fx_int(&L, "segoff", 0);
            int b0 = (int)fx_int(&L, "b0", 0), b1 = (int)fx_int(&L, "b1", 0);
            /* the script gives the 1996 SEGMENT literal.  Where it lands is
             * this file's answer, computed through the same seg_index
             * primitive every class-A site uses. */
            int a8 = alias8_at((int)segoff);
#ifdef BREAK_TINTA64000
            a8 = rbase[R_ADAPTED] + 64000;      /* niv-lr's relocation */
#endif
            nw_put(a8, b0); nw_put(a8 + 1, b1);
        } else if (!strcmp(L.op, "wrap_battery")) {
            long rows = fx_int(&L, "rows", 0), step = fx_int(&L, "rowstep", 1);
            long sk = fx_int(&L, "spot_negk", 0), ck = fx_int(&L, "cirrus_negk", 0);
            const char *ctrl = fx_str(&L, "ctrl", "");
            long row, k;
            for (row = 0; row < rows; row += step) {
                /* the row stride and the store-to-unsigned wrap are mechanism */
                int py = (int)((ORBIT_COLS * row) & 0xFFFF);
                for (k = 1; k <= sk; k++) nw_put(spot_index((int)((-k) & 0xFFFF), py), 0x3E);
                for (k = 1; k <= ck; k++) nw_put(cirrus_index((int)((-k) & 0xFFFF), py), 0x1F);
            }
            for (row = 0; row < rows; row += step) {
                char cc[128], *p;
                int py = (int)((ORBIT_COLS * row) & 0xFFFF);
                strncpy(cc, ctrl, sizeof cc - 1); cc[sizeof cc - 1] = 0;
                for (p = strtok(cc, ","); p; p = strtok(NULL, ",")) {
                    int c = (int)strtol(p, NULL, 10);
                    nw_put(spot_index(c, py), 0x3E);
                    nw_put(cirrus_index(c, py), 0x1F);
                }
            }
        } else if (!strcmp(L.op, "areaclear")) {
            int r = fx_page(fx_str(&L, "page", NULL));
            if (r < 0) fx_fatal("areaclear page=%s", fx_str(&L, "page", "?"));
            areaclear(rbase[r], (int)fx_int(&L, "x", 0), (int)fx_int(&L, "y", 0),
                      (int)fx_int(&L, "l", 0), (int)fx_int(&L, "a", 0),
                      (int)fx_int(&L, "color", 0));
        } else {
            /* An unknown op is FATAL.  A producer that silently skipped a step
             * it had not implemented would agree, record for record, with a
             * producer that implemented it wrongly. */
            fx_fatal("unknown op `%s` in section %s", L.op, section);
        }
    }
}

/* --------------------------------------------------------------- selftest */

static int failures;

/* ------------------------------------------------------------- the ledger
 *
 * Every row now carries a STABLE CHECK ID, a KIND and a DECLARED FALSIFIER
 * LIST, and the whole table is written out as fbout/fb-ref-checks.tsv so the
 * grader's mutation-coverage tool can require, mechanically, that
 *
 *   * every GRADED row is falsified by at least the sabotages it names;
 *   * every PIN row is falsified by NONE of them (a pin that becomes
 *     falsifiable was never a pin);
 *   * every NOTGRADED row is excluded from the pass count rather than
 *     inflating it.
 *
 * The ids are stable strings, not normalised message text: messages
 * interpolate measured values, so text-keyed identity silently merges checks
 * whose numbers happen to render alike.
 *
 * KIND meanings:
 *   GRADED     a claim about the port.  Must name >= 1 falsifier.
 *   PIN        an external literal or a form with no reachable mutation in
 *              the set.  Must name why, and must NOT be falsifiable.
 *   NOTGRADED  printed, counted separately, never a pass and never a fail.
 *              Used where this file grades ITSELF and therefore carries no
 *              evidence about any port.
 *   INVARIANT  a constructor assertion.  It is an assert, not evidence; it
 *              fails the build but is not counted as a graded pass.
 */
enum { CK_GRADED = 0, CK_PIN = 1, CK_NOTGRADED = 2, CK_INVARIANT = 3,
       CK_UNLEDGERED = 4 };
static const char *kindname[5] = { "GRADED", "PIN", "NOTGRADED", "INVARIANT",
                                   "UNLEDGERED" };

#define MAXCHK 128
typedef struct { const char *cid; int kind; const char *fals; int cond; } Chk;
static Chk chks[MAXCHK];
static int nchk;
static int n_notgraded;

/* the format attribute is not decoration: an argument-count mismatch inside a
 * 60-word explanatory message is invisible to review and crashed this file
 * once already during this wave.  -Wall does not check a varargs function it
 * has not been told is printf-shaped. */
#ifdef __GNUC__
__attribute__((format(printf, 5, 6)))
#endif
static void rec(const char *cid, int kind, const char *fals, int cond,
                const char *fmt, ...)
{
    va_list ap;
    int i;
    for (i = 0; i < nchk; i++)
        if (!strcmp(chks[i].cid, cid)) {
            fprintf(stderr, "LEDGER ERROR: duplicate check id %s\n", cid);
            exit(3);
        }
    if (kind == CK_GRADED && (!fals || !*fals)) {
        fprintf(stderr, "LEDGER ERROR: GRADED check %s names no falsifier\n", cid);
        exit(3);
    }
    if (nchk < MAXCHK) {
        chks[nchk].cid = cid; chks[nchk].kind = kind;
        chks[nchk].fals = fals ? fals : ""; chks[nchk].cond = cond;
        nchk++;
    }
    if (kind == CK_NOTGRADED) { printf("  ----  "); n_notgraded++; }
    else printf(cond ? "  PASS  " : "  FAIL  ");
    printf("[%s] ", cid);
    va_start(ap, fmt); vprintf(fmt, ap); va_end(ap);
    printf("\n");
    if (!cond && kind != CK_NOTGRADED) failures++;
}

/* THE ROWS THIS WAVE DID NOT REACH.
 *
 * Twenty-one checks in this file predate the ledger -- the byte-semantics
 * rows, A2/A3/A5, the tick rows, the S1 palette rows.  They are not bad
 * checks and the brief did not name them, but a ledger that quietly omitted
 * them would claim a coverage it does not have, which is the same defect in a
 * different costume.  So they are RECORDED, as kind UNLEDGERED with no
 * declared falsifier, and fbx_mutmatrix prints how many of them no sabotage
 * in the set reaches.  The hole is a number in the output instead of an
 * absence a reader has to notice.
 *
 * The generated ids are positional, so they are stable only while every
 * -DBREAK_* build runs the same sequence of req() calls.  That is true today
 * and the matrix checks it by comparing the row COUNT across builds. */
#ifdef __GNUC__
__attribute__((format(printf, 2, 3)))
#endif
static void req(int cond, const char *fmt, ...)
{
    va_list ap;
    static int seq;
    static char ids[64][32];
    if (seq < 64) {
        snprintf(ids[seq], sizeof ids[0], "REF.UNLEDGERED.%02d", seq);
        if (nchk < MAXCHK) {
            chks[nchk].cid = ids[seq]; chks[nchk].kind = CK_UNLEDGERED;
            chks[nchk].fals = ""; chks[nchk].cond = cond;
            nchk++;
        }
        printf(cond ? "  PASS  " : "  FAIL  ");
        printf("[%s] ", ids[seq]);
        seq++;
    } else {
        printf(cond ? "  PASS  " : "  FAIL  ");
    }
    va_start(ap, fmt); vprintf(fmt, ap); va_end(ap);
    printf("\n");
    if (!cond) failures++;
}

int main(int argc, char **argv)
{
    const char *outdir = (argc > 1) ? argv[1] : ".";
    const char *supports = (argc > 2) ? argv[2]
        : "C:\\programmieren\\noctis\\niv-plus\\data\\SUPPORTS.NCT";
    const char *srcdir  = (argc > 3) ? argv[3]
        : "C:\\programmieren\\noctis\\niv-plus\\source";
    const char *fixture = (argc > 4) ? argv[4]
        : "C:\\programmieren\\linoleum\\docs-notes\\FIXTURE1.txt";
    char path[1024];
    int i, j;
    int probe_viol = 0, probe_exp = 0, probe_first = -1, probe_pad = 0;
    uint32_t cmp_got = 0, cmp_want = 0;
    int srf_nonzero = 0;
    uint32_t canbad = 0;
    KSolve ks;

    /* stand-alone solver mode, so the falsification demo can point this at a
     * sandbox copy of the sources without running the rest of the programme:
     *     fb_ref.exe --ksolve <srcdir>                                    */
    if (argc > 2 && !strcmp(argv[1], "--ksolve")) {
        ksolve(argv[2], &ks);
        printf("ksolve %s: %s  K=%s", argv[2], ks.ok ? "SOLVED" : "REFUSED",
               ks.ok ? "" : "-");
        if (ks.ok) printf("%d", ks.k);
        printf("  (%s)\n", ks.why);
        return ks.ok ? 0 : 1;
    }

    printf("fb_ref.c -- C reference for the Wave 5-corrective buffer model\n");
    printf("build flags:");
#define SHOW(x) do { printf(" " #x); } while (0)
#ifdef BREAK_SHIFTOR
    SHOW(BREAK_SHIFTOR);
#endif
#ifdef BREAK_UPLOADFIRST
    SHOW(BREAK_UPLOADFIRST);
#endif
#ifdef BREAK_ROUNDSHADE
    SHOW(BREAK_ROUNDSHADE);
#endif
#ifdef BREAK_NOCLAMP
    SHOW(BREAK_NOCLAMP);
#endif
#ifdef BREAK_NOSELF
    SHOW(BREAK_NOSELF);
#endif
#ifdef BREAK_DIGITN1
    SHOW(BREAK_DIGITN1);
#endif
#ifdef BREAK_TINTA64000
    SHOW(BREAK_TINTA64000);
#endif
#ifdef BREAK_PACK4
    SHOW(BREAK_PACK4);
#endif
#ifdef BREAK_QUADWORDS
    SHOW(BREAK_QUADWORDS);
#endif
#ifdef BREAK_TICKCMP
    SHOW(BREAK_TICKCMP);
#endif
#ifdef BREAK_SHRINKADAPTOR
    SHOW(BREAK_SHRINKADAPTOR);
#endif
#ifdef BREAK_DIV64
    SHOW(BREAK_DIV64);
#endif
#ifdef BREAK_PYFILT
    SHOW(BREAK_PYFILT);
#endif
#ifdef BREAK_IGNOREDST
    SHOW(BREAK_IGNOREDST);
#endif
#ifdef BREAK_SELFSOURCE
    SHOW(BREAK_SELFSOURCE);
#endif
#ifdef BREAK_MASKSPOT
    SHOW(BREAK_MASKSPOT);
#endif
#ifdef BREAK_MASKCIRRUS
    SHOW(BREAK_MASKCIRRUS);
#endif
#ifdef BREAK_MASKCIRRUSADDR
    SHOW(BREAK_MASKCIRRUSADDR);
#endif
#ifdef BREAK_SEGADDRBASE
    SHOW(BREAK_SEGADDRBASE);
#endif
#ifdef BREAK_PADONEMAGIC
    SHOW(BREAK_PADONEMAGIC);
#endif
#ifdef BREAK_PAD9WALK
    SHOW(BREAK_PAD9WALK);
#endif
#ifdef BREAK_CANSTUBCHECK
    SHOW(BREAK_CANSTUBCHECK);
#endif
#ifdef BREAK_CANSTUBPOISON
    SHOW(BREAK_CANSTUBPOISON);
#endif
#ifdef BREAK_CANCONSTACTUAL
    SHOW(BREAK_CANCONSTACTUAL);
#endif
#ifdef BREAK_LAYOUTEND
    SHOW(BREAK_LAYOUTEND);
#endif
#ifdef BREAK_CANWITLIT
    SHOW(BREAK_CANWITLIT);
#endif
#ifdef BREAK_PROBEMOD16
    SHOW(BREAK_PROBEMOD16);
#endif
#ifdef BREAK_POISONMAGIC
    SHOW(BREAK_POISONMAGIC);
#endif
#ifdef BREAK_WALKHIGHBITS
    SHOW(BREAK_WALKHIGHBITS);
#endif
#ifdef BREAK_OVERRUN
    printf(" BREAK_OVERRUN=%d", BREAK_OVERRUN);
#endif
    printf(" (none listed = clean)\n\n");

    layout_init();
    zones_init();
    site_init();
#ifdef BREAK_PACK4
    NWSTORE = calloc((size_t)(nw_top / 4 + 2), sizeof(uint32_t));
#else
    NW = calloc((size_t)nw_top, sizeof(uint32_t));
#endif
    FB = calloc(64000, sizeof(uint32_t));
    range8088_init();

    /* ------------------------------------------------ the pinned stimulus */
    printf("fixture:\n");
    if (!fx_load(fixture)) {
        fprintf(stderr, "FIXTURE ERROR: cannot read %s\n", fixture);
        return 2;
    }
    printf("  %s\n  %ld bytes, sha256 %s\n", fx_path_used, fx_len, fx_sha);
    rec("REF.FIX.LINT", CK_GRADED, "EXT_FIXTUREFORBIDDEN",
        fx_lint_hits == 0,
        "the fixture's own forbidden-numeral lint passes: %d hits%s%s.  The script may "
        "carry the stimulus and may not carry the answer; adding `63996` to it stops "
        "this programme.", fx_lint_hits, fx_lint_hits ? " -- " : "",
        fx_lint_hits ? fx_lint_msg : "");
    if (fx_lint_hits) return 2;

    /* ------------------------------------------------- the alias-8 K-solve */
    printf("\nalias 8 -- the premise, SOLVED from the 1996 sources instead of asserted:\n");
    ksolve(srcdir, &ks);
    printf("  %s\n", ks.why);
    rec("REF.K.UNIQUE", CK_GRADED, "EXT_SANDBOXDISP",
        ks.ok, "the far-pointer offset is over-determined by %d parsed constraints and "
        "they admit exactly one solution (K = %d)", ks.ncon, ks.ok ? ks.k : -1);
    rec("REF.K.EQUALS.SEGOFFSET", CK_GRADED, "BREAK_SEGADDRBASE",
        ks.ok && ks.k == SEG_OFFSET,
        "and the constant this file COMPILED with equals the solved one: SEG_OFFSET %d, "
        "solved %d.  Before this row, `#define SEG_OFFSET 4` was an unparsed literal here "
        "AND an unparsed literal in the Python producer -- one transcription copied twice, "
        "not two producers.", SEG_OFFSET, ks.ok ? ks.k : -1);

    printf("\nlayout (transcribed from NOCTIS-D.H + NOCTIS.CPP farmalloc order):\n");
    for (i = 0; i < NREG; i++)
        printf("  %d %-14s base %6d size %6d end %6d pad %6d segbase %6d window end %6d\n",
               i, rname[i], rbase[i], rsize[i], rbase[i] + rsize[i], rpad[i],
               segbase(i), segbase(i) + WRAP16);
    printf("  NW top %d units = %d bytes;  %d pads, %d zones\n\n",
           nw_top, nw_top * 4, NPAD, nzones);

    printf("byte semantics:\n");
    nw_put(1000, 300); req(nw_get(1000) == 44, "B1 store 300 -> 44 (got %d)", nw_get(1000));
    nw_put(1000, -1);  req(nw_get(1000) == 255, "B2 store -1 -> 255 (got %d)", nw_get(1000));
    nw_put(1000, 0xC0); req(nw_get_signed(1000) == -64, "B3 sign extend 0xC0 -> -64 (got %d)", nw_get_signed(1000));
    nw_put(1000, 0x3F); req(nw_get_signed(1000) == 63, "B3 sign extend 0x3F -> +63 (got %d)", nw_get_signed(1000));
    {
        int okq = 1;
        for (i = 0; i < 256; i++) {
            nw_put(1001, i);
            for (j = 0; j < 4; j++) if (quad_get(1001, j) != ((i >> (2 * j)) & 3)) okq = 0;
        }
        req(okq, "B4 quadrant bitfield get agrees with the byte for all 256 values");
        nw_put(1001, 0);
        quad_set(1001, 0, 3); quad_set(1001, 3, 2);
        req(nw_get(1001) == 0x83, "B4 quadrant set -> 0x83 (got 0x%02X)", nw_get(1001));
    }
    {
        int okid = 1;
        for (i = 0; i < 16; i++) { nw_put(2000 + i, 0x10 + i); }
        for (i = 0; i < 16; i++) if (nw_unit(2000 + i) != (uint32_t)(0x10 + i)) okid = 0;
        req(okid, "B5 one byte per unit: raw unit at offset k equals the byte at k");
    }
    printf("\n");

    printf("class A -- the 16-bit index wrap:\n");
    {
        int py = 61200, px = (-1) & 0xFFFF;
        int m, n;
        site_init();
        /* CORRECTED.  These two rows used to read
         *     n - m == 65536 || site_wraps[SITE_SPOT] == 0
         * and the escape clause was DISARMED BY THE VERY SABOTAGE THE ROW
         * NAMES: -DBREAK_MASKSPOT removes the mask, so the site never records
         * a wrap, so site_wraps == 0, so the row passes.  Measured, before
         * this change:
         *     PASS  A1 spot py=61200 px=65535: masked NW 231723, naive NW
         *           231723, delta 0
         * A site that recorded zero wraps has not exonerated the mask; it has
         * failed to execute, and that is a FAIL, printed as its own row. */
        m = spot_index(px, py);
        n = segbase(R_P_BACKGROUND) + SEG_OFFSET + py + px;
        rec("REF.A1.SPOT.EXEC", CK_GRADED, "BREAK_MASKSPOT",
            site_wraps[SITE_SPOT] > 0,
            "A1 the spot probe ACTUALLY WRAPPED (%ld of %ld calls).  Zero is not a pass; "
            "it means the site under test did not execute.",
            site_wraps[SITE_SPOT], site_calls[SITE_SPOT]);
        rec("REF.A1.SPOT.DELTA", CK_GRADED, "BREAK_MASKSPOT",
            n - m == 65536,
            "A1 spot py=%d px=%d: masked NW %d, naive NW %d, delta %d (want 65536)",
            py, px, m, n, n - m);
        m = cirrus_index(px, py);
        n = segbase(R_OBJECTSCHART) + SEG_OFFSET + ((py + px) >> 1);
        rec("REF.A1.CIRRUS.EXEC", CK_GRADED, "BREAK_MASKCIRRUS",
            site_wraps[SITE_CIRRUS] > 0,
            "A1 the cirrus probe ACTUALLY WRAPPED (%ld of %ld calls)",
            site_wraps[SITE_CIRRUS], site_calls[SITE_CIRRUS]);
        rec("REF.A1.CIRRUS.DELTA", CK_GRADED, "BREAK_MASKCIRRUS,BREAK_MASKCIRRUSADDR",
            n - m == 32768,
            "A1 cirrus, SAME inputs: masked NW %d, naive NW %d, delta %d (want 32768) -- "
            "half of spot's, because of the `shr bx,1` between the truncation and the "
            "address.  BREAK_MASKCIRRUSADDR masks the final index instead and lands here "
            "with delta 65536, which is why the DIFFERENCE of the two deltas is the "
            "graded quantity and not the existence of a mask.", m, n, n - m);
        {
            int rn = region_at(n), rm = region_at(m);
            /* PIN.  With base = segbase + SEG_OFFSET and every class-A target
             * region at least 65536 units, an unmasked cirrus address at these
             * inputs is off its own buffer for EVERY input in the domain -- it
             * is a property of the layout, not a measurement of this call.
             * No mutation in the set falsifies it, and pretending otherwise by
             * quoting a case count would be the 340-case framing again. */
            rec("REF.A1.CIRRUS.OFFBUF", CK_PIN,
                "", rn != R_OBJECTSCHART,
                "A1 [PIN: true for every input in the domain, by the layout; declared "
                "unfalsifiable rather than dressed as a measurement] the UNMASKED cirrus "
                "address lands on %s, past the end of its own buffer; the masked one lands "
                "on %s", rn < 0 ? "a pad" : rname[rn], rm < 0 ? "a pad" : rname[rm]);
        }
        /* the four addresses that fold onto segment offsets 0..3 */
        {
            int lowok = 1, k;
            for (k = 1; k <= 4; k++) {
                int mm = spot_index((-k) & 0xFFFF, 0);
                int zi = zone_of(mm);
                if (mm != segbase(R_P_BACKGROUND) + (SEG_OFFSET - k)) lowok = 0;
                if (zi < 0 || zones[zi].owner != R_P_BACKGROUND || zones[zi].role != 1) lowok = 0;
            }
            req(lowok, "A2 py=0, px=65536-k for k=1..4 folds onto segment offsets 3,2,1,0 "
                       "-- NW %d..%d, p_background's own SUB zone, which is where DOS put "
                       "the far-heap header", segbase(R_P_BACKGROUND),
                segbase(R_P_BACKGROUND) + 3);
        }
        req(site_contain_fail == 0,
            "A3 containment: every masked address is inside its own region or its own "
            "SUB zone (%d failures)", site_contain_fail);
        /* alias 8.  CORRECTED: the expected index used to be the literal
         * 63996, carried here AND in the Python producer, so the two
         * "independent" sides shared the premise they were supposed to be
         * checking.  It is now `ALIAS8_SEGOFF - K` with K taken from the
         * SOLVER's parse of the 1996 assembly, which is a different source
         * from the `#define` this file compiled against. */
        {
            int a8 = alias8_index();
            int idx = a8 - rbase[R_ADAPTED];
            int want = ks.ok ? (ALIAS8_SEGOFF - ks.k) : -1;
            rec("REF.A4.ALIAS8", CK_GRADED, "BREAK_SEGADDRBASE",
                idx == want && want >= 0,
                "A4 alias 8: es:[0x%04X] with the SOLVED offset %d is adapted[%d]; the "
                "solver says %d.  Row %d col %d of a %d-column page.  niv-lr relocated "
                "the stash off the visible page; ours stays where 1996 put it.",
                ALIAS8_SEGOFF, ks.ok ? ks.k : -1, idx, want, idx / 320, idx % 320, 320);
        }
        /* A7: snapshot()'s row loop, NOCTIS-0.CPP:6423, with `unsigned ptr` */
        {
            unsigned long p = 63680; int n2 = 0;
            while (p < 64000 && n2 < 1000) { n2++; p = (p - 320) & 0xFFFFFFFFul; }
            req(n2 == 200, "A5 A7's `ptr` is a TYPING requirement, not a mask: unsigned, "
                           "the loop runs %d rows and exits (0-320 = %lu >= 64000)",
                n2, (unsigned long)((0ul - 320ul) & 0xFFFFFFFFul));
        }
        site_init();
    }
    printf("\n");

    printf("pads -- 11 pads, 22 zones, two magics, a two-sided check:\n");
    {
        int nexp, first, fpad, viol;
        rec("REF.P0.ZONECOUNT", CK_INVARIANT, "", nzones == NZONE,
            "P0 [INVARIANT of this file's own constructor, not evidence] %d zones (want %d)",
            nzones, NZONE);

        /* CORRECTED.  The old P1 was ONE-SIDED: poison_pads writes
         * zone_magic(z) and walk_pads skips every unit that equals
         * zone_magic(z).  Write X, check X.  A walker that compared nothing
         * but the top half of the word, or one that compared the wrong magic
         * against the wrong role, still reported 0 violations on a freshly
         * poisoned workspace.  The refounded form is TWO-SIDED: poison and
         * require silence, then corrupt exactly one unit BY EXACTLY ONE and
         * require exactly one violation AT THAT ADDRESS.  A one-bit
         * perturbation is the smallest thing the mechanism claims to see, so
         * it is the right probe. */
        poison_pads();
        viol = walk_pads(&nexp, &first, &fpad);
        rec("REF.P1.SILENT", CK_GRADED, "BREAK_POISONMAGIC",
            viol == 0 && nexp == 0,
            "P1a a freshly poisoned workspace reports 0 violations and 0 expectations "
            "(got %d, %d)", viol, nexp);
        {
            int tail = rbase[R_N_GLOBES_MAP] + rsize[R_N_GLOBES_MAP];   /* a TAIL unit */
            int subz = rpad[R_P_BACKGROUND] + ZONE;                     /* a SUB unit, rel 0 */
            int okt, oks;
            poison_pads();
            nw_unit_put(tail, nw_unit(tail) + 1u);
            viol = walk_pads(&nexp, &first, &fpad);
            okt = (viol == 1 && first == tail && nexp == 0);
            rec("REF.P1.TAILPLUS1", CK_GRADED, "BREAK_WALKHIGHBITS,BREAK_POISONMAGIC",
                okt,
                "P1b ONE unit of a TAIL changed by ONE fires exactly one violation at NW "
                "%d (got %d violations, first at %d, %d expectations).  magic+1 is the "
                "probe a walker that compares only the high half of the word cannot see.",
                tail, viol, first, nexp);
            poison_pads();
            nw_unit_put(subz, nw_unit(subz) + 1u);
            viol = walk_pads(&nexp, &first, &fpad);
            oks = (viol == 1 && first == subz && nexp == 0);
            rec("REF.P1.SUBPLUS1", CK_GRADED, "BREAK_WALKHIGHBITS,BREAK_POISONMAGIC",
                oks,
                "P1c and the same in a SUB zone BELOW its allowance window (NW %d): %d "
                "violations, first at %d, %d expectations.  A SUB is a guard everywhere "
                "the allowance table does not name, and the allowance must not swallow "
                "the guard.", subz, viol, first, nexp);
        }
        /* the EXPECTATION probe: one glyph, nothing else */
        if (!load_digimap2(supports)) {
            printf("  FAIL  P2 could not read digimap2 from %s\n", supports);
            failures++;
        } else {
            poison_pads();
            digit_at('A', 64 + 40, 1);
            probe_viol = walk_pads(&probe_exp, &probe_first, &probe_pad);
            rec("REF.P2.GLYPHEXP", CK_GRADED, "BREAK_DIGITN1",
                probe_viol == 0 && probe_exp == 6,
                "P2 one digit_at glyph: %d violations, %d expectations.  The EXACT count "
                "is asserted, so a build that never performs the legitimate write FAILS "
                "-- which BREAK_DIGITN1 does (it reports 0).", probe_viol, probe_exp);
        }
        /* P3 DELETED.  It wrote 0xDEADBEEF one unit past n_globes_map and
         * required one violation there -- the same address and the same claim
         * as P1b, with a coarser perturbation.  Any walker that sees magic+1
         * sees 0xDEADBEEF, so P3 was implied by P1b and could never fail
         * alone.  A row implied by another row is not a second piece of
         * evidence; it is a second opportunity to feel confident.  The
         * mutation matrix agreed: P3's measured falsifier set was a subset of
         * P1b's. */
        zero_pads();
    }
    printf("\n");

    printf("canary v2 -- 4 units per pad, none of them a literal:\n");
    {
        uint32_t can[4 * NPAD];
        int bad = canary_v2(can);
        canbad = (uint32_t)bad;
        int wok = 1, aok = 1, wbad = -1, abad = -1;
        for (i = 0; i < NPAD; i++) {
            /* unit 1 must satisfy BUFFERMODEL 4.2's published rule against
             * THIS PAD'S OWN unit 0 -- the poison the walker itself wrote and
             * read back.  The old row compared unit 1 against the bare literal
             * `0xC0DE0000 | i`, which is Wave 5's deleted kind-6 canary
             * reincarnated: expected and actual were the same constant and no
             * mechanism sabotage could separate them. */
            if (can[4*i + 1] != witness_rule(can[4*i + 0], i)) { wok = 0; if (wbad < 0) wbad = i; }
            /* the `at` field must land INSIDE the pad it belongs to.  This is
             * a containment property, not a recomputation of probeslot(); a
             * stubbed walker reports 0 and fails it on every pad but the low
             * one. */
            if (!(can[4*i + 3] >= (uint32_t)padbase[i] &&
                  can[4*i + 3] <  (uint32_t)(padbase[i] + PAD))) { aok = 0; if (abad < 0) abad = i; }
        }
        rec("REF.C1.FIRED", CK_GRADED, "BREAK_CANSTUBCHECK,BREAK_CANSTUBPOISON,BREAK_PAD9WALK",
            bad == 0, "C1 every one of the %d pads reports its own probe fired (%d did not)",
            NPAD, bad);
        rec("REF.C1.WITNESS", CK_GRADED, "BREAK_CANWITLIT,BREAK_CANCONSTACTUAL",
            wok,
            "C1 every pad's dirty_read satisfies WITNESS(i) = 0xB0B32000 + 17i + "
            "(clean & 255) against its OWN clean_read (pad 0: %08X -> %08X).  Stated "
            "limit, unchanged from BUFFERMODEL 4.2: a saboteur who RECOMPUTES the rule "
            "instead of loading it produces an identical unit, so units 0, 2 and 3 stay "
            "the load-bearing ones.  First bad pad: %d (-1 = none)",
            can[0], can[1], wbad);
        rec("REF.C1.AT", CK_GRADED, "BREAK_CANSTUBCHECK,BREAK_CANSTUBPOISON",
            aok,
            "C1 every pad's `at` field lands inside that pad (pad 0 at %u).  First bad "
            "pad: %d (-1 = none)", can[3], abad);
        zero_pads();
    }
    printf("\n");

    printf("tick:\n");
    {
        int32_t cpms = 9000, k;
        int64_t total = 0;
        int32_t mn = 0x7FFFFFFF, mx = 0;
        tick_carry = 0;
        for (k = 0; k < 4096; k++) {
            int32_t p = tick_period(cpms);
            total += p; if (p < mn) mn = p; if (p > mx) mx = p;
        }
        {
            int64_t want = ((int64_t)4096 * cpms * 32768000 + 596591 / 2) / 596591;
            req(total >= want - 1 && total <= want + 1,
                "T1 4096 ticks total %lld counts, exact %lld (within 1)", (long long)total, (long long)want);
        }
        req(mx - mn <= 1, "T1 period takes at most two adjacent values (%d..%d)", mn, mx);
        req(tick_expired(0x00000005u, 0xFFFFFFF0u) == 1, "T2 wrap: now=5 deadline=FFFFFFF0 is EXPIRED");
        req(tick_expired(0xFFFFFFF0u, 0x00000005u) == 0, "T2 wrap: now=FFFFFFF0 deadline=5 is NOT expired");
        req(tick_expired(0x80000000u, 0x7FFFFFFFu) == 1, "T2 sign boundary: 80000000 vs 7FFFFFFF is EXPIRED");
    }
    printf("\n");

    printf("palette -- LINOBUF 6.1 scenario \"surface\":\n");
    req(schar(200) == -56, "S1 `char` filtro 200 is -56 (got %d)", schar(200));
    req(filter_one(1, -56) == 63,
        "S1 v=1 f=-56: (1*-56) mod 65536 = 65480, /63 = 1039, clamp -> 63 (got %d)",
        filter_one(1, -56));
    {
        int wraps = 0, maxp = 0, v, f;
        for (v = 0; v < 64; v++) for (f = 0; f < 128; f++) {
            if (v * f >= 65536) wraps++;
            if (v * f > maxp) maxp = v * f;
        }
        req(wraps == 0, "S1 trap 2's 16-bit wrap is UNREACHABLE for every legal filter: "
                        "%d of 8192 (v,f) pairs wrap, max product %d < 65536", wraps, maxp);
    }
    {
        /* the destination parameter is GENERAL: 14 sites pass surface_palette,
         * 7 pass tmppal, and shade never writes return_palette in the game --
         * but the parameter must still express it. */
        memset(retpal6, 0, sizeof retpal6);
        memset(pal6, 0, sizeof pal6);
        shade(retpal6, 0, 2, 5.0f, 5.0f, 5.0f, 5.0f, 5.0f, 5.0f);
        req(retpal6[0] == 5 && retpal6[1] == 5 && pal6[0] == 0,
            "S1 shade's destination parameter is general: return_palette written "
            "(%d,%d), tmppal untouched (%d)", retpal6[0], retpal6[1], pal6[0]);
        /* and NO sign extension: srfpal6/retpal6 are `char` but shade stores
         * through `unsigned char far *` and tavola_colori reads through
         * `unsigned char *` */
        memset(srfpal6, 0, sizeof srfpal6);
        srfpal6[0] = 200;
        memset(pal6, 0, sizeof pal6);
        fade_from(srfpal6, 0, 1, 63, 63, 63);
        req(pal6[0] == 63,
            "S1 srfpal6 is read UNSIGNED: 200*63/63 = 200 -> clamp 63, not sign-extended "
            "to -56 (got %d)", pal6[0]);
    }
    fx_run("surface");
    printf("  pal6[0:12]   "); for (i = 0; i < 12; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  pal6[480:492]"); for (i = 480; i < 492; i++) printf(" %d", pal6[i]); printf("\n");
    printf("  curpal6[0:12]"); for (i = 0; i < 12; i++) printf(" %d", curpal6[i]); printf("\n");
    printf("  lut[0:4]      %08X %08X %08X %08X\n", PAL[0], PAL[1], PAL[2], PAL[3]);
    printf("  uploads      "); for (i = 0; i < n_up; i++) printf(" [%d,%d)", up_a[i], up_b[i]);
    printf("\n");

    /* SH-COMPOUND: what surface_palette is FOR.
     *
     * CORRECTED.  `cmp_want` used to be built with filter_one -- the SUBJECT,
     * carrying three `#ifdef BREAK_*` arms.  Both sides therefore moved
     * together and the C self-test was BLIND to -DBREAK_DIV64: measured, that
     * build printed "RESULT: PASS (0 failures)" while every palette record it
     * dumped was wrong.  The expectation is now built with filter_one_clean,
     * which no -DBREAK_* can reach, and the filter it uses is the one the
     * FIXTURE'S LAST FADE actually applied, recorded by the run rather than
     * written next to the expectation. */
    fx_run("compound");
    srf_nonzero = fx_srf_nonzero;
    if (!fx_have_snapshot || !fx_have_fade)
        fx_fatal("the compound section did not snapshot or did not fade");
    cmp_got = fnv_buf(pal6, 768);
    {
        uint32_t h = fnv_init();
        for (i = 0; i < 768; i++)
            h = fnv_unit(h, (uint32_t)filter_one_clean(fx_snapshot[i], fx_last_fade[i % 3]));
        cmp_want = h;
    }
    rec("REF.S2.LADDERWROTE", CK_GRADED, "BREAK_IGNOREDST",
        srf_nonzero > 0, "S2 the ladder actually wrote surface_palette (%d nonzero of 768)",
        srf_nonzero);
    rec("REF.S2.NOCOMPOUND", CK_GRADED, "BREAK_SELFSOURCE,BREAK_DIV64",
        cmp_got == cmp_want,
        "S2 two successive fades do NOT compound: pal6 == clean_filter(ladder, %d) exactly "
        "(fnv %08X vs %08X).  The expected side runs filter_one_clean, which carries no "
        "preprocessor arm, so a sabotage of the filter now separates the two sides "
        "instead of moving both.", fx_last_fade[0], cmp_got, cmp_want);
    /* restore the surface scenario for the dumps */
    fx_run("surface");
    printf("\n");

    printf("page scenario (fixture section `page`):\n");
    fx_run("page");
    present_expand();
    {
        /* DELETED as a mechanism check, and the deletion is the finding.
         *   for i: FB[i] == PAL[nw_get(adaptor+i)]
         * is present_expand's assignment re-executed by the checker.  It is
         * true for a correct expand, for an expand with the wrong LUT, for an
         * expand with the wrong source page, and for an expand that has been
         * deleted entirely and replaced by this loop.  What replaces it is a
         * property the assignment does NOT establish: the page the expander
         * read must be the VISIBLE page, and the two pages must differ, or the
         * record cannot tell which one was expanded. */
        int diff = 0, ok;
        for (i = 0; i < 64000; i++)
            if (nw_get(rbase[R_ADAPTOR] + i) != nw_get(rbase[R_ADAPTED] + i)) diff++;
        ok = (diff > 0);
        rec("REF.E1.PAGESDIFFER", CK_GRADED, "EXT_FIXTUREORDER",
            ok,
            "E1 the visible and hidden pages differ in %d of 64000 units, so \"which page "
            "did the expander read\" is a question with an answer.  The old row -- "
            "FB[i] == PAL[adaptor[i]] for all i -- was present_expand's own assignment "
            "re-executed by the checker and passed for every possible build.", diff);
        {
            /* and the expanded framebuffer must NOT match the hidden page,
             * which the deleted row could never have told us */
            int wrongpage = 0;
            for (i = 0; i < 64000; i++)
                if (FB[i] != PAL[nw_get(rbase[R_ADAPTED] + i)]) { wrongpage = 1; break; }
            rec("REF.E1.RIGHTPAGE", CK_GRADED, "EXT_FIXTUREORDER",
                wrongpage,
                "E1 and the framebuffer is NOT an expansion of the HIDDEN page -- the one "
                "check of this pair that a wrong-source expander fails");
        }
    }
    rec("REF.E2.BATTERYWRAPPED", CK_GRADED, "BREAK_MASKSPOT,BREAK_MASKCIRRUS",
        site_wraps[SITE_SPOT] > 0 && site_wraps[SITE_CIRRUS] > 0,
        "E2 the wrap battery actually wrapped: spot %ld/%ld, cirrus %ld/%ld",
        site_wraps[SITE_SPOT], site_calls[SITE_SPOT],
        site_wraps[SITE_CIRRUS], site_calls[SITE_CIRRUS]);
    rec("REF.E2.CONTAINED", CK_GRADED, "BREAK_MASKSPOT,BREAK_MASKCIRRUS",
        site_contain_fail == 0,
        "E2 and every masked address stayed contained (%d failures)", site_contain_fail);
    printf("\n");

    /* dumps */
    {
        uint32_t *pay = malloc(sizeof(uint32_t) * 64000);

        snprintf(path, sizeof path, "%s/fb-ref-layout.bin", outdir);
        for (i = 0; i < NREG; i++) {
            pay[4 * i + 0] = (uint32_t)rbase[i];
            pay[4 * i + 1] = (uint32_t)rsize[i];
#ifdef BREAK_LAYOUTEND
            pay[4 * i + 2] = (uint32_t)rpad[i];      /* the v1 ambiguity */
#else
            pay[4 * i + 2] = (uint32_t)(rbase[i] + rsize[i]);
#endif
            pay[4 * i + 3] = (uint32_t)i;
        }
        fbdump(path, K_LAYOUT, pay, 4 * NREG, 0, 0, 0, 0, T_LAYOUT);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-zones.bin", outdir);
        for (i = 0; i < nzones; i++) {
            pay[4 * i + 0] = (uint32_t)zones[i].base;
            pay[4 * i + 1] = (uint32_t)zones[i].len;
            pay[4 * i + 2] = (uint32_t)zones[i].owner;
            pay[4 * i + 3] = (uint32_t)zones[i].role;
        }
        fbdump(path, K_ZONES, pay, 4 * nzones, 0, 0, 0, 0, T_ZONES);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-pal6.bin", outdir);
        for (i = 0; i < 768; i++) pay[i] = pal6[i];
        fbdump(path, K_PALETTE6, pay, 768, 0, 0, 0, 0, T_PAL6);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-curpal6.bin", outdir);
        for (i = 0; i < 768; i++) pay[i] = curpal6[i];
        fbdump(path, K_PALETTE6, pay, 768, 0, 0, 0, 0, T_CURPAL6);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-lut.bin", outdir);
        for (i = 0; i < 256; i++) pay[i] = PAL[i];
        fbdump(path, K_LUT, pay, 256, 0, 0, 0, 0, T_LUT);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-adapted.bin", outdir);
        for (i = 0; i < 64000; i++) pay[i] = (uint32_t)nw_get(rbase[R_ADAPTED] + i);
        fbdump(path, K_INDEXPAGE, pay, 64000, 320, 200, 0, 0, T_ADAPTED);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-adaptor.bin", outdir);
        for (i = 0; i < 64000; i++) pay[i] = (uint32_t)nw_get(rbase[R_ADAPTOR] + i);
        fbdump(path, K_INDEXPAGE, pay, 64000, 320, 200, 0, 0, T_ADAPTOR);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-glyph.bin", outdir);
        for (i = 0; i < 9216; i++) pay[i] = (uint32_t)nw_get(glyph_window() + i);
        fbdump(path, K_INDEXPAGE, pay, 9216, 256, 36, 0, 0, T_GLYPH);
        printf("wrote %s\n", path);

        snprintf(path, sizeof path, "%s/fb-ref-wrapcount.bin", outdir);
        {
            int n = 0, s;
            for (s = 1; s < NSITE; s++) {
                if (!site_calls[s]) continue;
                pay[n++] = (uint32_t)s;
                pay[n++] = (uint32_t)site_calls[s];
                pay[n++] = (uint32_t)site_wraps[s];
            }
            fbdump(path, K_WRAPCOUNT, pay, n, 0, 0, 0, 0, T_WRAPCOUNT);
        }
        printf("wrote %s\n", path);

        /* KSELF.  Field ids 1..99 are NORMATIVE and independently computable,
         * so they are GRADED; 100+ are port-local and are never graded. */
        snprintf(path, sizeof path, "%s/fb-ref-kself.bin", outdir);
        {
            int n = 0, a8 = seg_index(R_ADAPTED, ALIAS8_SEGOFF);
            int idx = a8 - rbase[R_ADAPTED];
            uint32_t glyph_nz = 0, upfnv = fnv_init(), palt = fnv_init(), curt = fnv_init();
            for (i = 0; i < 9216; i++)
                if (nw_get(glyph_window() + i)) glyph_nz++;
            for (i = 0; i < n_up; i++) {
                upfnv = fnv_unit(upfnv, (uint32_t)up_a[i]);
                upfnv = fnv_unit(upfnv, (uint32_t)up_b[i]);
            }
            for (i = 0; i < n_mark; i++) {
                palt = fnv_unit(palt, mk_pal[i]);
                curt = fnv_unit(curt, mk_cur[i]);
            }
#define KF(id, val) do { pay[n++] = (uint32_t)(id); pay[n++] = (uint32_t)(val); } while (0)
            KF(1, nw_top);
            KF(2, nzones);
            KF(3, NPAD);
            KF(4, probe_viol);
            KF(5, probe_exp);
            KF(6, QW_STEADY);
            KF(7, a8);
            KF(8, idx / 320);
            KF(9, idx % 320);
            KF(10, site_mfnv[SITE_SPOT]);
            KF(11, site_nfnv[SITE_SPOT]);
            KF(12, site_mfnv[SITE_CIRRUS]);
            KF(13, site_nfnv[SITE_CIRRUS]);
            KF(14, glyph_nz);
            KF(15, curt);
            KF(16, srf_nonzero);
            KF(17, fnv_range(rbase[R_ADAPTED], 64000));
            KF(18, fnv_range(rbase[R_ADAPTOR], 64000));
            KF(19, fnv_range(glyph_window(), 9216));
            KF(20, canbad);
            KF(21, cmp_got);
            KF(22, palt);
            KF(23, upfnv);
            /* BUILD IDENTITY.  Fields 80-91 carry the first 32 bytes of the
             * SHA-256 of the fixture this producer compiled its stimulus from.
             * The grader requires every producer's hash to match before it
             * compares one content unit: two producers that ran different
             * scripts have no oracle between them and the honest verdict for
             * their difference is NOT GRADED, not FAIL.  This replaces the
             * LINOBUF 6.1 "scenario marker" check, whose verdict was decided by
             * a heading number.
             *
             * 80..91 and NOT 24..34, which is where they first landed: the
             * lino producer's KSELF stream already occupies 0..64 (measured
             * today -- and it occupies them with a malformed pair stream, ids
             * 0..64 with duplicates and stray six-digit values, which is a
             * separate defect flagged to the coordinator).  A field id
             * collision between two producers is a comparison of two
             * different quantities that reads as a disagreement about one, so
             * the block is placed above everything in use and reserved here
             * in writing. */
            for (i = 0; i < 8; i++) {
                char b[9];
                memcpy(b, fx_sha + 8 * i, 8); b[8] = 0;
                KF(80 + i, (uint32_t)strtoul(b, NULL, 16));
            }
            /* 88: the SOLVED far-pointer offset, not the compiled literal */
            KF(88, ks.ok ? (uint32_t)ks.k : 0xFFFFFFFFu);
            KF(89, (uint32_t)ks.ncon);
            KF(90, (uint32_t)fx_ops_run);
            KF(91, (uint32_t)fx_len);
            fbdump(path, K_KSELF, pay, n, 0, 0, 0, 0, T_SELFCHECK);
        }
        printf("wrote %s\n", path);

        /* CANARY v2.  A DEBUG-BUILD artifact by definition: it poisons, probes,
         * checks and restores the release state, and every graded page record
         * above was dumped BEFORE this. */
        snprintf(path, sizeof path, "%s/fb-ref-canary.bin", outdir);
        canary_v2(pay);
        fbdump(path, K_CANARY, pay, 4 * NPAD, 0, 0, 0, 0, T_CANARY);
        printf("wrote %s\n", path);
        free(pay);
    }

    /* ------------------------------------------------- the ledger artifact
     *
     * One row per check: id, kind, this run's verdict, and the sabotages the
     * row DECLARES must falsify it.  The grader's mutation-coverage tool reads
     * this, builds the same table from every -DBREAK_* build, and fails when
     *   * a GRADED row survives a sabotage it named  (it stopped catching what
     *     it claims), or
     *   * a PIN row is falsified by anything          (it was never a pin).
     * Declaring the diagonal is the part that matters: "some mutation broke
     * it" is satisfied by accident, "the mutation it named broke it" is not.
     */
    {
        FILE *tf;
        snprintf(path, sizeof path, "%s/fb-ref-checks.tsv", outdir);
        tf = fopen(path, "wb");
        if (tf) {
            fprintf(tf, "#cid\tkind\tverdict\tdeclared_falsifiers\n");
            fprintf(tf, "#producer\tfb_ref.c\tfixture_sha256\t%s\n", fx_sha);
            for (i = 0; i < nchk; i++)
                fprintf(tf, "%s\t%s\t%s\t%s\n", chks[i].cid, kindname[chks[i].kind],
                        chks[i].kind == CK_NOTGRADED ? "NOTGRADED"
                                                     : (chks[i].cond ? "PASS" : "FAIL"),
                        chks[i].fals);
            fclose(tf);
            printf("wrote %s  (%d rows)\n", path, nchk);
        }
    }

    printf("\nRESULT: %s  (%d failures, %d ledger rows, %d NOT GRADED)\n",
           failures ? "FAIL" : "PASS", failures, nchk, n_notgraded);
    return failures ? 1 : 0;
}
