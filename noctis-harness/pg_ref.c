/* ===========================================================================
   pg_ref.c -- Wave 6a oracle: projection, poly3d, polymap.

   DERIVED FROM: C:\programmieren\noctis\niv-plus\source\TDPOLYGS.H
                 ("The Third Flare", 3270 lines), instruction by instruction
                 from the inline assembly, plus
                 C:\programmieren\noctis\niv-plus\source\NOCTIS-D.H:122-132
                 for the clip rectangle, and NOCTIS-0.CPP:54 for the
                 declaration `unsigned char far *adapted`.

   NOT derived from: work/pg*.txt (implementer 1's lino), and not from
                 niv-lr/src/tdpolygs.h.  The de-assembled C++ was NOT opened
                 while writing this file.  Line references in comments below
                 are TDPOLYGS.H line numbers.

   Register widths are explicit: 16-bit DI/SI/AX wrap is modelled with
   (unsigned short) casts, 32-bit operand-size-prefixed ops with uint32_t.

   Build:   gcc -O2 -std=c11 -o pg_ref.exe pg_ref.c
   Break:   gcc -O2 -std=c11 -DBREAK_NOFB1 -o pg_break_NOFB1.exe pg_ref.c
   =========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <float.h>

/* The whole FP model rests on this. Checked at build time, not at the end
   of the wave (stall mode 2). */
#if LDBL_MANT_DIG != 64
#error "pg_ref.c requires an 80-bit long double (LDBL_MANT_DIG==64)"
#endif

/* ---------------------------------------------------------------- schedule */

enum { ACC_EXT = 0, ACC_F64 = 1, ACC_F32 = 2 };
enum { FST_DUAL = 0, FST_ALLWIDE = 1, FST_ALLNARROW = 2 };
enum { RND_NEAR = 0, RND_CHOP = 1 };

static int ACC   = ACC_EXT;
static int FSTM  = FST_DUAL;
static int RNDM  = RND_NEAR;

typedef long double R;

static R q(R v)
{
    if (ACC == ACC_F64) return (R)(double)v;
    if (ACC == ACC_F32) return (R)(float)v;
    return v;
}

/* Every arithmetic op rounds to the active accumulator precision, which is
   what an x87 with PC set does, and what a binary64/binary32 engine does. */
static R Radd(R a, R b) { return q(a + b); }
static R Rsub(R a, R b) { return q(a - b); }
static R Rmul(R a, R b) { return q(a * b); }
static R Rdiv(R a, R b) { return q(a / b); }

/* fst dword ptr X : narrows to memory, leaves the wide value in st(0).
   TDPOLYGS.H has four sites where the immediate consumer sees the wide value
   and a later reload sees the narrowed one (fst zz/xx/z2/yy at :446..466,
   fst rzf[si] at :468, fst zk at :566, fst video_x0/video_y0 at :720/:730).
   The port takes both sides because the original takes both.  --fst exists
   only so a sabotage can collapse it. */
typedef struct { float m; R w; } F32;

static R FST(F32 *s, R v)            /* returns what st(0) keeps */
{
    s->m = (float)v;
    s->w = v;
    return (FSTM == FST_ALLNARROW) ? (R)(float)v : v;
}
static R FLD(const F32 *s)
{
    return (FSTM == FST_ALLWIDE) ? s->w : (R)s->m;
}
static void FSTP32(float *m, R v) { *m = (float)v; }   /* fstp dword ptr */

/* fistp / fist. All 38 hand-written conversion sites in the original run
   under Borland's control word (RC=00, round to nearest even); _control87
   (MCW_EM,MCW_EM) at TDPOLYGS.H:139 masks exceptions and does not touch RC. */
#define X87_INDEFINITE ((int32_t)0x80000000)

static R rne(R v)                     /* round half to even, on 80 bits */
{
    R f = floorl(v);
    R d = v - f;
    if (d > 0.5L) return f + 1.0L;
    if (d < 0.5L) return f;
    return (fmodl(f, 2.0L) == 0.0L) ? f : f + 1.0L;
}
static R rchop(R v) { return (v < 0.0L) ? ceill(v) : floorl(v); }

static int32_t f2i(R v)
{
    R r;
    if (isnan(v)) return X87_INDEFINITE;
#ifdef BREAK_CHOP
    r = rchop(v);
#else
    r = (RNDM == RND_CHOP) ? rchop(v) : rne(v);
#endif
    if (!(r >= -2147483648.0L && r <= 2147483647.0L)) return X87_INDEFINITE;
    return (int32_t)r;
}
/* fild dword ptr : exact for every int32 at every accumulator width >= 32
   bits of mantissa, so no q() is needed here and none is applied. */
static R i2f(int32_t v) { return (R)v; }

/* ---------------------------------------------------------------- sha256   */

typedef struct { uint32_t s[8]; uint64_t n; unsigned char b[64]; size_t bl; } SHA;
static const uint32_t K256[64] = {
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
#define ROR(x,n) (((x)>>(n))|((x)<<(32-(n))))
static void sha_block(SHA *c, const unsigned char *p)
{
    uint32_t w[64], a,b,cc,d,e,f,g,h,t1,t2; int i;
    for (i=0;i<16;i++) w[i]=((uint32_t)p[i*4]<<24)|((uint32_t)p[i*4+1]<<16)|((uint32_t)p[i*4+2]<<8)|p[i*4+3];
    for (i=16;i<64;i++){uint32_t s0=ROR(w[i-15],7)^ROR(w[i-15],18)^(w[i-15]>>3);
                        uint32_t s1=ROR(w[i-2],17)^ROR(w[i-2],19)^(w[i-2]>>10);
                        w[i]=w[i-16]+s0+w[i-7]+s1;}
    a=c->s[0];b=c->s[1];cc=c->s[2];d=c->s[3];e=c->s[4];f=c->s[5];g=c->s[6];h=c->s[7];
    for (i=0;i<64;i++){
        t1=h+(ROR(e,6)^ROR(e,11)^ROR(e,25))+((e&f)^((~e)&g))+K256[i]+w[i];
        t2=(ROR(a,2)^ROR(a,13)^ROR(a,22))+((a&b)^(a&cc)^(b&cc));
        h=g;g=f;f=e;e=d+t1;d=cc;cc=b;b=a;a=t1+t2;}
    c->s[0]+=a;c->s[1]+=b;c->s[2]+=cc;c->s[3]+=d;c->s[4]+=e;c->s[5]+=f;c->s[6]+=g;c->s[7]+=h;
}
static void sha_init(SHA *c){c->s[0]=0x6a09e667;c->s[1]=0xbb67ae85;c->s[2]=0x3c6ef372;c->s[3]=0xa54ff53a;
    c->s[4]=0x510e527f;c->s[5]=0x9b05688c;c->s[6]=0x1f83d9ab;c->s[7]=0x5be0cd19;c->n=0;c->bl=0;}
static void sha_up(SHA *c,const unsigned char*p,size_t n){c->n+=n;
    while(n){size_t k=64-c->bl; if(k>n)k=n; memcpy(c->b+c->bl,p,k); c->bl+=k;p+=k;n-=k;
        if(c->bl==64){sha_block(c,c->b);c->bl=0;}}}
static void sha_fin(SHA *c,char*out){unsigned char pad[72];size_t i;uint64_t bits=c->n*8;
    size_t padlen=(c->bl<56)?(56-c->bl):(120-c->bl);
    memset(pad,0,sizeof pad);pad[0]=0x80;
    sha_up(c,pad,padlen);
    {unsigned char L[8];for(i=0;i<8;i++)L[i]=(unsigned char)(bits>>(56-8*i));sha_up(c,L,8);}
    for(i=0;i<8;i++)sprintf(out+i*8,"%08x",c->s[i]);out[64]=0;}

static void sha_hex(const unsigned char *p, size_t n, char *out)
{ SHA c; sha_init(&c); sha_up(&c,p,n); sha_fin(&c,out); }

/* ---------------------------------------------------------------- memory   */

/* Wave 5 settled model. `adapted` is `unsigned char far *` (NOCTIS-0.CPP:54)
   with a farmalloc offset of 4 (BUFFERMAP 4.1), so the byte at 16-bit segment
   offset j is P[j], and adapted[i] is P[(4+i) & 0xFFFF].  sc_bytes = 65540
   (NOCTIS-D.H:47).  P[0..3] are the four units below adapted[0]; nothing in
   Wave 6a may write them, which is exactly what SEGOFF0 breaks. */
#define PGUNITS 65540
static unsigned char P[PGUNITS];

static unsigned char rd8(unsigned o)            { return P[(unsigned short)o]; }
static void          wr8(unsigned o, unsigned char v) { P[(unsigned short)o] = v; }

#define ADAPTED(i) P[(unsigned short)(4u + (unsigned)(i))]

/* pre-states: formulas, never checked-in blobs (Recon C trap 3).
   Index j is the segment-origin index 0..65539, i.e. adapted[i] == P[4+i]. */
static const int PRE2_LIST[] = {
    /* hand-placed sentinels: row 100 cols 40..44 and 60, row 101 col 40,
       row 150 col 5, row 150 col 311, row 190 col 200 -- as adapted[] indices */
    32040,32041,32042,32043,32044,32060, 32360, 48005, 48311, 60999, -1
};
static void preset_page(const char *pre, const unsigned char *carry)
{
    unsigned j;
    if (!strcmp(pre, "PRE0")) { memset(P, 0, sizeof P); return; }
    if (!strcmp(pre, "PRE1")) { for (j=0;j<PGUNITS;j++) P[j] = (unsigned char)((j*101u) & 255u); return; }
    if (!strcmp(pre, "PRE2")) { int k; memset(P,0,sizeof P);
        for (k=0; PRE2_LIST[k]>=0; k++) ADAPTED(PRE2_LIST[k]) = 255; return; }
    if (!strcmp(pre, "PRE3")) { if (carry) memcpy(P, carry, PGUNITS); else memset(P,0,sizeof P); return; }
    fprintf(stderr, "pg_ref: unknown pre-state '%s'\n", pre); exit(2);
}

/* texture window: the 64 KiB reachable through fs:[bx].  Formulas only. */
static unsigned char TEXW[65536];
static void preset_tex(const char *t)
{
    unsigned i;
    if (!strcmp(t,"TEX0")) { for(i=0;i<65536;i++) TEXW[i]=(unsigned char)((i*37u+11u)&255u); return; }
    if (!strcmp(t,"TEX1")) { for(i=0;i<65536;i++) TEXW[i]=(unsigned char)(((i>>8)^(i&255u))&255u); return; }
    if (!strcmp(t,"TEX2")) { for(i=0;i<65536;i++) TEXW[i]=1; return; }
    if (!strcmp(t,"TEX3")) { memset(TEXW,0,sizeof TEXW); TEXW[0]=255; TEXW[65535]=255; TEXW[32768]=255; return; }
    fprintf(stderr,"pg_ref: unknown texture '%s'\n", t); exit(2);
}

/* ------------------------------------------------------- pinned constants  */

/* NOCTIS-D.H:122-132, confirmed against NOCTIS.EXE by pg_bin.py (check C1). */
#ifdef BREAK_CONST310
#  define LARGHEZZA 300
#  define X_CENTRO  160
#else
#  define LARGHEZZA 306
#  define X_CENTRO  158
#endif
#define ALTEZZA 180
#define Y_CENTRO 100

#define LBX (-LARGHEZZA/2 + X_CENTRO)
#define UBX ( LARGHEZZA/2 + X_CENTRO)
#define LBY (-ALTEZZA/2   + Y_CENTRO)
#define UBY ( ALTEZZA/2   + Y_CENTRO)

static const int32_t lbxl = LBX, ubxl = UBX, lbyl = LBY, ubyl = UBY;
static const float   lbxf = LBX, ubxf = UBX, lbyf = LBY, ubyf = UBY;
static const float   x_centro_f = X_CENTRO, y_centro_f = Y_CENTRO;

#define MPIY 199
static unsigned riga[201];
static void initscanlines(void) { int c; for (c=0;c<201;c++) riga[c] = (unsigned)(320*c); }

/* camera / lens state, defaults exactly as declared in TDPOLYGS.H */
static float uneg = 100.0f;
static float alfa = 0, beta = 0, gammaf = 0;
static float cam_x = 0, cam_y = 0, cam_z = 0;
static float dpp = 200.0f, inv_dpp = 1.0f/200.0f;
static float EMU_K = 16.0f;
static long  H_MATRIXS = 16, V_MATRIXS = 16;
static long  XSIZE = 256*16, YSIZE = 256*16;
static float XCOEFF, YCOEFF;
static float opt_pcosbeta, opt_psinbeta, opt_tcosbeta, opt_tsinbeta;
static float opt_pcosalfa, opt_psinalfa, opt_tcosalfa, opt_tsinalfa;
static float opt_tcosgamma = 1, opt_tsingamma = 0;
static const double degc = 3.14159265358979323846 / 180.0;

static void change_angle_of_view(void)          /* TDPOLYGS.H:365 */
{
    opt_pcosbeta = (float)(cos(beta*degc) * dpp);
    opt_psinbeta = (float)(sin(beta*degc) * dpp);
    opt_tcosbeta = (float)cos(beta*degc);
    opt_tsinbeta = (float)sin(beta*degc);
    opt_pcosalfa = (float)(cos(alfa*degc) * dpp);
    opt_psinalfa = (float)(sin(alfa*degc) * dpp);
    opt_tcosalfa = (float)cos(alfa*degc);
    opt_tsinalfa = (float)sin(alfa*degc);
    opt_tcosgamma = (float)cos(gammaf*degc);
    opt_tsingamma = (float)sin(gammaf*degc);
}
static void change_camera_lens(void)            /* TDPOLYGS.H:383 */
{
    inv_dpp = 1.0f/dpp;
    XCOEFF = EMU_K/dpp;
    YCOEFF = EMU_K/dpp;
    change_angle_of_view();
}

static float x_antialias = 1.125f, y_antialias = 1.125f, z_antialias = 1.125f;
static unsigned char escrescenze = 0xE0;
static unsigned char entity = 1;
static char flares = 0;
static char culling_needed = 0, halfscan_needed = 0;

/* ------------------------------------------------------------ instrumentation */

static long ct_seg_calls, ct_rows_scanned, ct_rows_fb1, ct_bytes_filled;
static long ct_edge_writes, ct_span_pixels;

/* ------------------------------------------------------------- Segmento    */
/* TDPOLYGS.H:155-259.  Zero FP instructions.  16-bit div, truncated quotient,
   32-bit 16.16 DDA, half-open in x. */

static uint32_t g_xp, g_yp, g_xa, g_ya;
static uint32_t global_x, global_y;

static void Segmento(void)
{
    uint32_t a, b, L, t, dxv, dyv;
    unsigned pi, pf, si16;
    uint32_t eax, ebx, ecx, edx, esi;
    unsigned char ch_neg;

    ct_seg_calls++;

    if (g_xp == g_xa) {                              /* :161 */
        if (g_ya >= g_yp) { pi = (unsigned)(riga[g_yp] + g_xp); pf = riga[g_ya+1]; }
        else              { pi = (unsigned)(riga[g_ya] + g_xp); pf = riga[g_yp+1]; }
        /* les si,adapted / add pi,si / add pf,si : si == offset(adapted) == 4 */
        pi = (unsigned short)(pi + 4);
        pf = (unsigned short)(pf + 4);
        si16 = pi;
        do {                                          /* :174 clu */
            wr8(si16, 255); ct_edge_writes++;
            si16 = (unsigned short)(si16 + 320);
        } while (si16 < pf);
        return;
    }

    esi = g_xa - g_xp;                                /* :181 */
    if (g_xa < g_xp) {                                /* jnc a_posit -> CF */
        t = g_xp; g_xp = g_xa; g_xa = t;
        t = g_yp; g_yp = g_ya; g_ya = t;
        esi = (uint32_t)(0u - esi);
    }
    a = esi; L = esi;                                 /* :193 */
    ch_neg = 0;
    eax = g_ya - g_yp;
    if (g_ya < g_yp) { ch_neg = 0xFF; eax = (uint32_t)(0u - eax); }
    b = eax;                                          /* :201 */
    dxv = a; dyv = eax;
    if (!(eax < L)) L = eax;
    L = L + 1;                                        /* :205 */
    ecx = g_xa << 16;                                 /* xa <<= 16 */
    eax = g_xp << 16;
    ebx = g_yp << 16;
    global_x = eax; global_y = ebx;
    a <<= 16; b <<= 16;
    /* 16-bit unsigned div: DX:AX / L.low16 -> AX. L >= 1 always. */
    {
        unsigned Ldiv = (unsigned)(L & 0xFFFFu);
        uint32_t num;
        if (Ldiv == 0) { fprintf(stderr,"pg_ref: Segmento div by zero\n"); exit(3); }
        num = a; a = (num / Ldiv) & 0xFFFFu;
        num = b; b = (num / Ldiv) & 0xFFFFu;
    }
#ifdef BREAK_BRESENHAM
    /* round the DDA step up instead of truncating the 16-bit quotient */
    { unsigned Ldiv = (unsigned)(L & 0xFFFFu);
      a = (((dxv << 16) + Ldiv - 1) / Ldiv) & 0xFFFFu;
      b = (((dyv << 16) + Ldiv - 1) / Ldiv) & 0xFFFFu; }
#endif
    if (ch_neg) b = (uint32_t)(0u - b);

    edx = b; eax = a;
    do {                                              /* :250 _do */
        unsigned bx = (unsigned short)(global_y >> 16);
        unsigned di = (unsigned short)(global_x >> 16);
        if (bx > 200) { fprintf(stderr,"pg_ref: Segmento riga[] index %u out of range\n", bx); exit(3); }
        global_x = (uint32_t)(global_x + eax);
        di = (unsigned short)(di + riga[bx]);
        global_y = (uint32_t)(global_y + edx);
#ifdef BREAK_SEGOFF0
        wr8(di, 255);
#else
        wr8((unsigned short)(di + 4), 255);            /* :256 es:[di+4] */
#endif
        ct_edge_writes++;
#ifdef BREAK_SEGCLOSED
    } while (global_x <= ecx);   /* paints the greater-x endpoint column */
#else
    } while (global_x < ecx);                          /* :257 unsigned 32-bit */
#endif
}

/* --------------------------------------------------------- the bbox gate   */
/* TDPOLYGS.H:705-764.  Rectangle-seeded 32-bit signed accumulators plus four
   range tests with a deliberate >= / < asymmetry. */

typedef struct {
    unsigned min_x, max_x, min_y, max_y;   /* the `unsigned` globals, 16-bit */
    int      si;                           /* how many of the four fired     */
    int      fired[4];                     /* ubx, uby, lbx, lby             */
    int      clip_needed;
} BBOX;

static void bbox_gate(const int32_t *mp, int n, BBOX *o)
{
    int32_t ax = lbxl, bx = lbyl, cx = ubxl, dx = ubyl;
    int i;
    for (i = n-1; i >= 0; i--) {                       /* si counts down */
        int32_t X = mp[2*i], Y = mp[2*i+1];
        if (!(X >= cx)) cx = X;                        /* jnl outr_1 */
        if (!(X <= ax)) ax = X;                        /* jle outr_2 */
        if (!(Y >= dx)) dx = Y;                        /* jnl outr_3 */
        if (!(Y <= bx)) bx = Y;                        /* jle outr_4 */
    }
    o->max_x = (unsigned short)ax; o->max_y = (unsigned short)bx;
    o->min_x = (unsigned short)cx; o->min_y = (unsigned short)dx;
    o->si = 0; o->fired[0]=o->fired[1]=o->fired[2]=o->fired[3]=0;
#ifdef BREAK_BBOXGT
    if (!(ax <= ubxl)) { o->si++; o->fired[0]=1; o->max_x = UBX; }
#else
    if (!(ax <  ubxl)) { o->si++; o->fired[0]=1; o->max_x = UBX; }   /* :746 jl  */
#endif
    if (!(bx <  ubyl)) { o->si++; o->fired[1]=1; o->max_y = UBY; }   /* :750 jl  */
#ifdef BREAK_BBOXLE
    if (!(cx >  lbxl)) { o->si++; o->fired[2]=1; o->min_x = LBX; }
#else
    if (!(cx >= lbxl)) { o->si++; o->fired[2]=1; o->min_x = LBX; }   /* :754 jnl */
#endif
    if (!(dx >= lbyl)) { o->si++; o->fired[3]=1; o->min_y = LBY; }   /* :758 jnl */
    o->clip_needed = (o->si != 0);
}

/* ------------------------------------------------------- poly3d: drawb     */
/* TDPOLYGS.H:1449-1763.  Zero FP instructions in this whole region. */

/* rep-prefixed scasb.  With CX==0 `rep` executes zero times and leaves the
   flags untouched, which is why zf is threaded rather than recomputed. */
static int repne_scasb(unsigned *di, unsigned *cx, unsigned char al, int zf)
{
    while (*cx) {
        unsigned char m = rd8(*di);
        (*cx)--;
        *di = (unsigned short)(*di + 1);
        zf = (m == al);
        if (zf) break;
    }
    return zf;
}
static int repe_scasb(unsigned *di, unsigned *cx, unsigned char al, int zf)
{
    while (*cx) {
        unsigned char m = rd8(*di);
        (*cx)--;
        *di = (unsigned short)(*di + 1);
        zf = (m == al);
        if (!zf) break;
    }
    return zf;
}
static void rep_stosb(unsigned *di, unsigned cnt, unsigned char al)
{
    while (cnt--) { wr8(*di, al); *di = (unsigned short)(*di + 1); ct_bytes_filled++; }
}

static void poly3d_drawb(const int32_t *mp, int n, BBOX bb,
                         unsigned char colore, char fl, unsigned char ent)
{
    unsigned _8n = (unsigned)(8*(n-1));
    unsigned segmptr, lim_y, lim_x, bytes;
    unsigned min_x = bb.min_x, max_x = bb.max_x, min_y = bb.min_y, max_y = bb.max_y;
    unsigned si;

    /* :1449 fast path -- only when flares == 0 */
#ifndef BREAK_NOFASTROW
    if (!fl) {
        if (min_y == max_y) {
            if (min_x == max_x) { ADAPTED(min_x + riga[min_y]) = colore; ct_bytes_filled++; }
            else {
                unsigned ptr = (unsigned short)(max_x + riga[min_y]);
                while (max_x >= min_x) {
                    ADAPTED(ptr) = colore; ct_bytes_filled++;
                    max_x = (unsigned short)(max_x - 1);
                    ptr   = (unsigned short)(ptr - 1);
                }
            }
            return;
        }
    }
#endif

    /* :1469 edge stroking */
    for (si = 0; ; si += 8) {
        g_xp = (uint32_t)mp[si/4];      g_yp = (uint32_t)mp[si/4+1];
        g_xa = (uint32_t)mp[si/4+2];    g_ya = (uint32_t)mp[si/4+3];
        Segmento();
        if (!((si + 8) < _8n)) { si += 8; break; }
    }
    g_xp = (uint32_t)mp[si/4]; g_yp = (uint32_t)mp[si/4+1];
    g_xa = (uint32_t)mp[0];    g_ya = (uint32_t)mp[1];
    Segmento();

    /* :1504 */
    segmptr = (unsigned short)(min_x + riga[min_y]);
    lim_y   = (unsigned short)(min_x + riga[max_y]);
    lim_x   = (unsigned short)(segmptr + max_x - min_x);
#ifdef BREAK_BYTESM1
    bytes   = (unsigned short)(lim_x - segmptr + 1);
#else
    bytes   = (unsigned short)(lim_x - segmptr + 2);   /* :1518 */
#endif

    if (fl == 0) {
        unsigned di = (unsigned short)(4 + segmptr);
        unsigned ly = (unsigned short)(lim_y + 4);
        int zf = 0;
        for (;;) {
            unsigned di0 = di, cx = bytes, sipos, bxpos;
            ct_rows_scanned++;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) goto pross0;
            sipos = di;
            zf = repe_scasb(&di, &cx, 255, zf);
            bxpos = di;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) {
#ifdef BREAK_NOFB1
                goto pross0;
#else
                unsigned s = (unsigned short)(sipos - 1);
                unsigned b = (unsigned short)(bxpos - 1);
                unsigned cnt = (unsigned short)(b - s);
                unsigned d = s;
                ct_rows_fb1++;
                rep_stosb(&d, cnt, colore);
                goto pross0;
#endif
            }
            zf = repe_scasb(&di, &cx, 255, zf);
            {
                unsigned dend = (unsigned short)(di - 1);
                unsigned s    = (unsigned short)(sipos - 1);
                unsigned dxc  = (unsigned short)(dend - s);
                unsigned d    = s;
                unsigned c4   = (unsigned short)(dxc >> 2);
#ifndef BREAK_FILLONE
                while (c4) {                       /* :1557 mov es:[di],eax */
                    wr8(d,colore); wr8((unsigned short)(d+1),colore);
                    wr8((unsigned short)(d+2),colore); wr8((unsigned short)(d+3),colore);
                    ct_bytes_filled += 4;
                    d = (unsigned short)(d + 4); c4--;
                }
#endif
#ifndef BREAK_DWORDONLY
                rep_stosb(&d, (unsigned)(dxc & 3u), colore);   /* :1561 and cl,3 */
#endif
            }
          pross0:
            di = (unsigned short)(di0 + 320);
            if (!(di <= ly)) break;
        }
        return;
    }

    if (fl == 1) {
        unsigned di = (unsigned short)(4 + segmptr);
        unsigned ly = (unsigned short)(lim_y + 4);
        unsigned char col = (unsigned char)(colore & 0x3F);
        int zf = 0;
        for (;;) {
            unsigned di0 = di, cx = bytes, sipos, bxpos;
            ct_rows_scanned++;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) goto pross1;
            sipos = di;
            zf = repe_scasb(&di, &cx, 255, zf);
            bxpos = di;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) {
#ifdef BREAK_NOFB1
                goto pross1;
#else
                unsigned s = (unsigned short)(sipos - 1);
                unsigned b = (unsigned short)(bxpos - 1);
                unsigned c = (unsigned short)(b - s);
                unsigned d = s;
                unsigned char dl = (unsigned char)(col >> 1);
                ct_rows_fb1++;
                if (c == 0) c = 65536;   /* `dec cx; jnz` with cx==0 runs 65536 times */
                while (c) {
                    unsigned char al = (unsigned char)(rd8((unsigned short)(d-1)) & 0x3F);
                    al = (unsigned char)(al + dl);
                    if (!(al < 62)) al = 62;
                    wr8(d, al); ct_bytes_filled++;
                    d = (unsigned short)(d + 1); c--;
                }
                goto pross1;
#endif
            }
            zf = repe_scasb(&di, &cx, 255, zf);
            {
                unsigned dend = (unsigned short)(di - 1);
                unsigned s    = (unsigned short)(sipos - 1);
                unsigned c    = (unsigned short)(dend - s);
                unsigned d    = s;
                if (c == 0) c = 65536;
                while (c) {
                    unsigned char al = (unsigned char)(rd8((unsigned short)(d-1)) & 0x3F);
                    al = (unsigned char)(al + col);
                    if (!(al < 62)) al = 62;
                    wr8(d, al); ct_bytes_filled++;
                    d = (unsigned short)(d + 1); c--;
                }
            }
          pross1:
            di = (unsigned short)(di0 + 320);
            if (!(di <= ly)) break;
        }
        return;
    }

    if (fl == 2) {
        unsigned di = (unsigned short)(4 + segmptr);
        unsigned ly = (unsigned short)(lim_y + 4);
        int zf = 0;
        for (;;) {
            unsigned di0 = di, cx = bytes, sipos, bxpos;
            ct_rows_scanned++;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) goto pross2;
            sipos = di;
            zf = repe_scasb(&di, &cx, 255, zf);
            bxpos = di;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) {
#ifdef BREAK_NOFB1
                goto pross2;
#else
                unsigned s = (unsigned short)(sipos - 1);
                unsigned b = (unsigned short)(bxpos - 1);
                unsigned c = (unsigned short)(b - s);
                unsigned d = s;
                ct_rows_fb1++;
                if (c == 0) c = 65536;
                while (c) {
#ifdef BREAK_NEIGH320
                    unsigned char ah = rd8((unsigned short)(d-320));
                    if (ah == 0xFF) ah = rd8((unsigned short)(d-640));
#else
                    unsigned char ah = rd8((unsigned short)(d-321));   /* :1680 */
                    if (ah == 0xFF) ah = rd8((unsigned short)(d-642)); /* :1683 */
#endif
                    ah = (unsigned char)((ah & 0x3F) | 0x40);
                    wr8(d, ah); ct_bytes_filled++;
                    d = (unsigned short)(d + 1); c--;
                }
                goto pross2;
#endif
            }
            zf = repe_scasb(&di, &cx, 255, zf);
            {
                unsigned dend = (unsigned short)(di - 1);
                unsigned s    = (unsigned short)(sipos - 1);
                unsigned c    = (unsigned short)(dend - s);
                unsigned d    = s;
                if (c == 0) c = 65536;
                while (c) {
                    if (rd8(d) == 0xFF) {                              /* :1656 */
#ifdef BREAK_NEIGH320
                        unsigned char ah = rd8((unsigned short)(d-320));
#else
                        unsigned char ah = rd8((unsigned short)(d-321));
#endif
                        ah = (unsigned char)((ah & 0x3F) | 0x40);
                        wr8(d, ah);
                    } else {                                           /* :1663 */
                        unsigned ax = (unsigned)(rd8(d) & 0x3F);
                        unsigned char al = (unsigned char)(ax | 0x40);
                        ax = (unsigned short)((unsigned)al + c);
                        if (!(ax < 128)) al = 127;
                        else al = (unsigned char)ax;
                        wr8(d, al);
                    }
                    ct_bytes_filled++;
                    d = (unsigned short)(d + 1); c--;
                }
            }
          pross2:
            di = (unsigned short)(di0 + 320);
            if (!(di <= ly)) break;
        }
        return;
    }

    if (fl == 4) {
        unsigned di = (unsigned short)(4 + segmptr);
        unsigned ly = (unsigned short)(lim_y + 4);
        unsigned char col = colore;
        int zf = 0;
        for (;;) {
            unsigned di0 = di, cx = bytes, sipos, bxpos;
            unsigned char al, ah;
            ct_rows_scanned++;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) goto fil4d;
            sipos = di;
            zf = repe_scasb(&di, &cx, 255, zf);
            bxpos = di;
            zf = repne_scasb(&di, &cx, 255, zf);
            if (!zf) {
#ifdef BREAK_NOFB1
                goto fil4d;
#else
                unsigned s = (unsigned short)(sipos - 1);
                unsigned b = (unsigned short)(bxpos - 1);
                unsigned c = (unsigned short)(b - s);
                unsigned d = s;
                ct_rows_fb1++;
                rep_stosb(&d, c, col);
                goto fil4d;
#endif
            }
            zf = repe_scasb(&di, &cx, 255, zf);
            {
                unsigned dend = (unsigned short)(di - 1);
                unsigned s    = (unsigned short)(sipos - 1);
                unsigned dxc  = (unsigned short)(dend - s);
                unsigned d    = s;
                unsigned c4   = (unsigned short)(dxc >> 2);
#ifndef BREAK_FILLONE
                while (c4) { wr8(d,col); wr8((unsigned short)(d+1),col);
                             wr8((unsigned short)(d+2),col); wr8((unsigned short)(d+3),col);
                             ct_bytes_filled += 4; d=(unsigned short)(d+4); c4--; }
#endif
#ifndef BREAK_DWORDONLY
                rep_stosb(&d, (unsigned)(dxc & 3u), col);
#endif
            }
          fil4d:                                                       /* :1745 */
            al = (unsigned char)(col & 0x3F);
            ah = (unsigned char)(col & 0xC0);
            al = (unsigned char)(al + ent);
            if (!(al <= 0x3F)) {
                al = 0x3F;
                if (ent & 0x80) al = 0;
            }
            col = (unsigned char)(al | ah);
            di = (unsigned short)(di0 + 320);
            if (!(di <= ly)) break;
        }
        return;
    }

    /* no case matches: the switch has no default, so the polygon is left as a
       bare 255 wireframe from Segmento.  Reachability is an OPEN ITEM. */
}

/* ------------------------------------------------- polymap: edge walk (S4) */
/* TDPOLYGS.H:2529-2673.  ipart[] is the LEFT boundary (seeded at ubxl),
   fpart[] is the RIGHT boundary (seeded at lbxl) -- the names are inverted
   with respect to the obvious reading and getting them the wrong way round
   silently mirrors every span. */

static int ipart[MPIY], fpart[MPIY];

static int32_t sar32(int32_t v, int n)      /* db 0x66; sar reg, n */
{
    if (v < 0) return (int32_t)~((~(uint32_t)v) >> n);
    return (int32_t)(((uint32_t)v) >> n);
}

static void polymap_edges(int32_t *mp, int vr2, int32_t min_y, int32_t max_y)
{
    int vr22 = 2*vr2;
    int i, cnt;

    /* :2531 ol_init -- only [min_y..max_y] is initialised */
    for (i = 0; i < MPIY; i++) { fpart[i] = (int)lbxl; ipart[i] = (int)ubxl; }
    for (i = (int)min_y; i <= (int)max_y; i++) { fpart[i] = (int)lbxl; ipart[i] = (int)ubxl; }

    mp[vr22]   = mp[0];                                   /* :2549 */
    mp[vr22+1] = mp[1];

    cnt = vr22 >> 1;
    for (i = 0; i < cnt; i++) {
        int32_t ax = mp[2*i], bxv = mp[2*i+1], cx = mp[2*i+2], dx = mp[2*i+3];
        int32_t x1, y1, x2, y2, ity, jty;
        R kx_w; float kx;
        int equal = (dx == bxv);                           /* flags from cmp dx,bx */

        if (dx < bxv) { x1 = cx; y1 = dx; x2 = ax; y2 = bxv; }   /* :2569 jnl noex */
        else          { x1 = ax; y1 = bxv; x2 = cx; y2 = dx; }
        if (equal) continue;                               /* :2583 jne ol / nool */

        /* :2585  kx = (float)(x2-x1)/(float)(y2-y1) -- fild/fisub pairs, so the
           subtraction happens in integers and is converted once. */
        kx_w = Rdiv(Rsub(i2f(x2), i2f(x1)), Rsub(i2f(y2), i2f(y1)));
        kx = (float)kx_w;                                  /* fstp kx */

        if (!(y1 >= lbyl)) {                               /* :2594 jnl nocr */
            ity = lbyl;
#ifdef BREAK_IPARTPROD
            x1 = x1 + f2i(Rmul(Rsub(i2f(lbyl), i2f(y1)), (R)kx));
#else
            /* :2600  fild x1 / fild lbyl / fisub y1 / fmul kx / faddp / fistp x1
               -- the SUM is rounded, not the product. */
            x1 = f2i(Radd(i2f(x1), Rmul(Rsub(i2f(lbyl), i2f(y1)), (R)kx)));
#endif
        } else ity = y1;

        if (!(y2 <= ubyl)) jty = ubyl; else jty = y2;      /* :2612 jng _nocr */

        {
            R bndx = i2f(x1);                              /* :2622 fild x1 */
            int h = (int)ity;
            int32_t iters;
#ifdef BREAK_IPARTINCL
            if (ity > jty) continue;
#else
            if (ity >= jty) continue;                      /* :2626 jnl noifor */
#endif
            iters = jty - ity + 1;
            while (iters--) {
                int32_t ax2;
#ifdef BREAK_IPARTTRUNC
                ax2 = (int32_t)rchop(bndx);                /* truncate instead */
#else
                ax2 = f2i(bndx);                           /* :2632 fist bndx */
#endif
                if (!(ax2 >= -10000)) ax2 = -10000;
                if (!(ax2 <=  10000)) ax2 =  10000;
                if (h < 0 || h >= MPIY) { fprintf(stderr,"pg_ref: edge h=%d out of range\n",h); exit(3); }
                if (ax2 > fpart[h]) {                      /* :2640 */
                    if (ax2 < ubxl) fpart[h] = (int)ax2; else fpart[h] = (int)ubxl;
                }
                if (ax2 < ipart[h]) {                      /* :2652 */
                    if (ax2 > lbxl) ipart[h] = (int)ax2; else ipart[h] = (int)lbxl;
                }
#ifdef BREAK_IPARTF32
                bndx = (R)(float)((float)bndx + kx);
#else
                bndx = Radd(bndx, (R)kx);                  /* :2665 fadd kx */
#endif
                h++;
            }
        }
    }
}

/* -------------------------------------------------- polymap: span engine   */
/* TDPOLYGS.H:2691-3071.  16-bit modular u/v accumulators, sar 4 steps,
   8-bit combines, fixed write offsets. */

#ifdef BREAK_SCRATCH64000
#  define SCR_TINTA 0xFA04u      /* LR's relocation to adapted[64000] */
#  define SCR_ESCR  0xFA05u
#else
#  define SCR_TINTA 0xFA00u      /* es:[0xFA00] == adapted[63996] */
#  define SCR_ESCR  0xFA01u      /* es:[0xFA01] == adapted[63997] */
#endif

static unsigned char texel(unsigned bx) { return TEXW[bx & 0xFFFFu]; }
static const char *tk_id_ref(void);

/* the per-pixel accumulator add.  `add ax,bp` carries no 0x66 prefix, so it
   is a 16-bit modular add and the texel index wraps the 64 KiB window. */
static unsigned uvadd(unsigned acc, unsigned step)
{
#ifdef BREAK_TEXCLAMP
    long t = (long)acc + (long)(short)step;
    if (t < 0) t = 0; if (t > 0xFFFF) t = 0xFFFF;
    return (unsigned)t;
#else
    return (acc + step) & 0xFFFFu;
#endif
}

static void polymap_span_row(int i, unsigned char fl, int cull,
                             const int32_t *uv, int nuv, int *blkused)
{
    unsigned di = (unsigned short)(riga[i] + (unsigned)(int)ipart[i]);
#ifdef BREAK_SPANINCL
    int sections = fpart[i] - ipart[i] + 1;
#else
    int sections = fpart[i] - ipart[i];
#endif
    int blk = 0;
    unsigned char cl;

    if (!cull) {
        for (;;) {
            if (!(sections > 0)) break;                    /* :2755 row */
#ifdef BREAK_BLOCK17
            if (sections > 17) cl = 17; else cl = (unsigned char)(sections & 0xFF);
            sections -= 17;
#else
            if (sections > 16) cl = 16;                    /* :2758 */
            else cl = (unsigned char)(sections & 0xFF);
            sections -= 16;
#endif
            if (cl == 0) continue;
            if (2*blk+3 >= 2*nuv) { fprintf(stderr,"pg_ref: uv list too short (blk %d)\n",blk); exit(3); }
            {
                int32_t up = uv[2*blk], vp = uv[2*blk+1];
                int32_t un = uv[2*blk+2], vn = uv[2*blk+3];
                int32_t stu = sar32((int32_t)((uint32_t)un-(uint32_t)up),4);
                int32_t stv = sar32((int32_t)((uint32_t)vn-(uint32_t)vp),4);
#ifdef BREAK_UV32
                uint32_t ax = (uint32_t)up, dx = (uint32_t)vp;
                uint32_t bp = (uint32_t)stu, sv = (uint32_t)stv;
#define UVMASK 0xFFFFFFFFu
#else
                unsigned ax = (unsigned)((uint32_t)up & 0xFFFFu);
                unsigned dx = (unsigned)((uint32_t)vp & 0xFFFFu);
                unsigned bp = (unsigned)((uint32_t)stu & 0xFFFFu);
                unsigned sv = (unsigned)((uint32_t)stv & 0xFFFFu);
#define UVMASK 0xFFFFu
#endif
                blk++;
                do {
                    unsigned bxr, bh, bl;
                    unsigned char ch;
                    if (fl == 0) {                                  /* internal */
                        bh = (dx>>8)&0xFF; di = (unsigned short)(di+1); bl = (ax>>8)&0xFF;
                        bxr = (bh<<8)|bl;
                        ch = rd8(SCR_TINTA);
                        ch = (unsigned char)(ch + texel(bxr));
                        ax = uvadd(ax, bp);
                        wr8((unsigned short)(di+3), ch);
                        dx = uvadd(dx, sv);
                    } else if (fl & 1) {                            /* transp */
                        bh = (dx>>8)&0xFF; di = (unsigned short)(di+1); bl = (ax>>8)&0xFF;
                        bxr = (bh<<8)|bl;
                        ch = rd8((unsigned short)(di+3));
                        ch = (unsigned char)(ch + texel(bxr));
                        ax = uvadd(ax, bp);
                        wr8((unsigned short)(di+3), ch);
                        dx = uvadd(dx, sv);
                    } else if (fl & 2) {                            /* bright */
                        ch = rd8((unsigned short)(di+4));
                        bh = (dx>>8)&0xFF; di = (unsigned short)(di+1); bl = (ax>>8)&0xFF;
                        bxr = (bh<<8)|bl;
                        ch = (unsigned char)(ch & 0x3F);
                        ax = uvadd(ax, bp);
                        ch = (unsigned char)(ch + texel(bxr));
                        dx = uvadd(dx, sv);
#ifdef BREAK_BRIGHT3F
                        if (!(ch <= 0x3F)) ch = 0x3F;
#else
                        if (!(ch <= 0x3E)) ch = 0x3E;               /* :2847 */
#endif
                        wr8((unsigned short)(di+3), (unsigned char)(rd8((unsigned short)(di+3)) & 0xC0));
                        wr8((unsigned short)(di+3), (unsigned char)(rd8((unsigned short)(di+3)) | ch));
                    } else if (fl & 4) {                            /* merger */
                        ch = rd8((unsigned short)(di+4));
                        bh = (dx>>8)&0xFF; di = (unsigned short)(di+1); bl = (ax>>8)&0xFF;
                        bxr = (bh<<8)|bl;
                        ch = (unsigned char)(ch & 0x3F);
                        ax = uvadd(ax, bp);
                        ch = (unsigned char)(ch + texel(bxr));
                        ch = (unsigned char)(ch + rd8(SCR_TINTA));
                        dx = uvadd(dx, sv);
                        ch = (unsigned char)(ch >> 1);
                        wr8((unsigned short)(di+3), (unsigned char)(rd8((unsigned short)(di+3)) & 0xC0));
                        wr8((unsigned short)(di+3), (unsigned char)(rd8((unsigned short)(di+3)) | ch));
                    } else {                                        /* bumper */
                        unsigned savedi, d2; unsigned char savech; int n, cc;
                        bh = (dx>>8)&0xFF; di = (unsigned short)(di+1); bl = (ax>>8)&0xFF;
                        bxr = (bh<<8)|bl;
                        ch = rd8(SCR_TINTA);
                        ch = (unsigned char)(ch + texel(bxr));
                        ax = uvadd(ax, bp);
                        wr8((unsigned short)(di+3), ch);
                        savedi = di; savech = ch;
                        n = ch & 7; d2 = di; cc = n;
                        do { d2 = (unsigned short)(d2 - 320); cc--; } while (cc >= 0);
                        ch = savech;
                        ch = (unsigned char)(ch - rd8(SCR_TINTA));
                        ch = (unsigned char)(ch + rd8(SCR_ESCR));
                        ch = (unsigned char)(ch + texel(bxr));
#ifdef BREAK_BUMPROW
                        wr8((unsigned short)(d2 + 320 + 3), ch);
#else
                        wr8((unsigned short)(d2 + 640 + 3), ch);    /* :2887 */
#endif
                        di = savedi;
                        dx = uvadd(dx, sv);
                    }
                    ct_span_pixels++;
                } while (--cl);
#undef UVMASK
            }
        }
    } else {
        for (;;) {
            if (!(sections > 0)) break;                    /* :2895 c_row */
            if (sections > 32) cl = 32;
            else cl = (unsigned char)((sections + 2) & 0xFF);
            sections -= 32;
            if ((signed char)cl < 2) continue;
            if (2*blk+3 >= 2*nuv) { fprintf(stderr,"pg_ref: uv list too short (cblk %d)\n",blk); exit(3); }
            {
                int32_t up = uv[2*blk], vp = uv[2*blk+1];
                int32_t un = uv[2*blk+2], vn = uv[2*blk+3];
                int32_t stu = sar32((int32_t)((uint32_t)un-(uint32_t)up),4);
                int32_t stv = sar32((int32_t)((uint32_t)vn-(uint32_t)vp),4);
                unsigned ax = (unsigned)((uint32_t)up & 0xFFFFu);
                unsigned dx = (unsigned)((uint32_t)vp & 0xFFFFu);
                unsigned bp = (unsigned)((uint32_t)stu & 0xFFFFu);
                unsigned sv = (unsigned)((uint32_t)stv & 0xFFFFu);
                unsigned di_save;
                blk++;
                cl = (unsigned char)(cl >> 1);
                di_save = di;
                do {
                    unsigned bxr, bh, bl; unsigned char ch;
                    if (fl == 0) {
                        bh=(dx>>8)&0xFF; di=(unsigned short)(di+2); bl=(ax>>8)&0xFF;
                        bxr=(bh<<8)|bl;
                        ch = rd8(SCR_TINTA); ch = (unsigned char)(ch + texel(bxr));
                        ax = uvadd(ax, bp);
                        wr8((unsigned short)(di+2),ch); wr8((unsigned short)(di+3),ch);
                        dx = uvadd(dx, sv);
                    } else if (fl & 1) {
                        bh=(dx>>8)&0xFF; di=(unsigned short)(di+2); bl=(ax>>8)&0xFF;
                        bxr=(bh<<8)|bl;
                        ch = rd8((unsigned short)(di+3)); ch = (unsigned char)(ch + texel(bxr));
                        ax = uvadd(ax, bp);
                        wr8((unsigned short)(di+2),ch); wr8((unsigned short)(di+3),ch);
                        dx = uvadd(dx, sv);
                    } else if (fl & 2) {
                        ch = rd8((unsigned short)(di+4));
                        bh=(dx>>8)&0xFF; di=(unsigned short)(di+2); bl=(ax>>8)&0xFF;
                        bxr=(bh<<8)|bl;
                        ch = (unsigned char)(ch & 0x3F);
                        ax = uvadd(ax, bp);
                        ch = (unsigned char)(ch + texel(bxr));
                        dx = uvadd(dx, sv);
#ifdef BREAK_BRIGHT3F
                        if (!(ch <= 0x3F)) ch = 0x3F;
#else
                        if (!(ch <= 0x3E)) ch = 0x3E;
#endif
                        /* c_antibloom ORs the destination INTO ch and writes both
                           pixels with the LEFT pixel's top 2 bits.  antibloom and
                           c_antibloom are inconsistent in the original; the
                           inconsistency is reproduced, not repaired. */
                        wr8((unsigned short)(di+2), (unsigned char)(rd8((unsigned short)(di+2)) & 0xC0));
                        ch = (unsigned char)(ch | rd8((unsigned short)(di+2)));
                        wr8((unsigned short)(di+2),ch); wr8((unsigned short)(di+3),ch);
                    } else if (fl & 4) {
                        ch = rd8((unsigned short)(di+4));
                        bh=(dx>>8)&0xFF; di=(unsigned short)(di+2); bl=(ax>>8)&0xFF;
                        bxr=(bh<<8)|bl;
                        ch = (unsigned char)(ch & 0x3F);
                        ax = uvadd(ax, bp);
                        ch = (unsigned char)(ch + texel(bxr));
                        ch = (unsigned char)(ch + rd8(SCR_TINTA));
                        dx = uvadd(dx, sv);
                        ch = (unsigned char)(ch >> 1);
                        wr8((unsigned short)(di+2), (unsigned char)(rd8((unsigned short)(di+2)) & 0xC0));
                        ch = (unsigned char)(ch | rd8((unsigned short)(di+2)));
                        wr8((unsigned short)(di+2),ch); wr8((unsigned short)(di+3),ch);
                    } else {
                        unsigned savedi,d2; unsigned char savech; int n,cc;
                        bh=(dx>>8)&0xFF; di=(unsigned short)(di+2); bl=(ax>>8)&0xFF;
                        bxr=(bh<<8)|bl;
                        ch = rd8(SCR_TINTA); ch = (unsigned char)(ch + texel(bxr));
                        ax = uvadd(ax, bp);
                        wr8((unsigned short)(di+2),ch); wr8((unsigned short)(di+3),ch);
                        savedi=di; savech=ch; n=ch&7; d2=di; cc=n;
                        do { d2=(unsigned short)(d2-320); cc--; } while (cc>=0);
                        ch = savech;
                        ch = (unsigned char)(ch - rd8(SCR_TINTA));
                        ch = (unsigned char)(ch + rd8(SCR_ESCR));
                        ch = (unsigned char)(ch + texel(bxr));
#ifdef BREAK_BUMPROW
                        wr8((unsigned short)(d2+320+2),ch); wr8((unsigned short)(d2+320+3),ch);
#else
                        wr8((unsigned short)(d2+640+2),ch); wr8((unsigned short)(d2+640+3),ch);
#endif
                        di = savedi;
                        dx = uvadd(dx, sv);
                    }
                    ct_span_pixels++;
                } while (--cl);
                di = (unsigned short)(di_save + 32);       /* :3036 c_common */
            }
        }
    }
    *blkused = blk;
}

/* :3041 row_end -- the halfscan inter-scanline block. */
static int polymap_halfscan(int i, int max_y)
{
    int ip = i + 1;
    unsigned di, ax, dx;
    if (max_y < ip) return -1;
#ifdef BREAK_HALFI2
    if (ip-2 < 0) return ip;
    dx = (unsigned)(unsigned short)ipart[ip-2];
    ax = (unsigned)(unsigned short)fpart[ip-2];
#else
    dx = (unsigned)(unsigned short)ipart[ip-1];            /* :3050 ipart[si-2] */
    ax = (unsigned)(unsigned short)fpart[ip-1];
#endif
    di = riga[ip];
    if (ax < dx) return ip;                                /* jc do_singlescan */
    ax = (unsigned short)(ax - dx);
    if (ax == 0) return ip;                                /* jz do_singlescan */
    di = (unsigned short)(di + dx);
    do {                                                   /* :3060 duplicate */
#ifdef BREAK_HALFSKEW
        unsigned char dl = rd8((unsigned short)(di-320));
#else
        unsigned char dl = rd8((unsigned short)(di-316));  /* -320 + 4 */
#endif
        wr8((unsigned short)(di+4),   dl);
        wr8((unsigned short)(di+324), dl);
        di = (unsigned short)(di+1);
        ax = (unsigned short)(ax-1);
    } while (ax);
    return ip;
}

/* ============================================================ projection    */
/* poly3d's projector and polymap's projector are DIFFERENT nuclei and are
   kept separate: poly3d fuses dpp into the rotation matrix (opt_p*) and
   divides 1/Zc (TDPOLYGS.H:715 `fld uno / fdiv ultima_z`); polymap keeps a
   unit matrix (opt_t*) and divides dpp/Zc (:2451 `fld dpp / fdiv ultima_z`).
   Do not factor them together. */

#define NV 4

typedef struct {
    int ret;                 /* 0 = reached drawb, else the early-return site */
    int doflag, nrv;
    int rwf[NV];
    int vr2, vr3, vr4, vr5, vr6;
    int gate[4], gate_si, clip_needed;
    unsigned min_x, max_x, min_y, max_y;
    int32_t mp[64];
    int nmp;                 /* number of vertices in mp (pairs) */
    int mp_overflow;
    int illcond;             /* near-plane denominators under the threshold */
    int zk_degenerate;       /* exact-equality guard fired */
    float basis[9];          /* hx,vx,ox,hy,vy,oy,hz,vz,oz  (polymap only)   */
    int basis_valid;
    int gamma_nonzero;
} TOPO;

/* the declared conditioning threshold: |Zv - Zo| >= 2^-10 * max(|Zv|,|Zo|) */
static int illconditioned(float zv, float zo)
{
    double a = fabs((double)zv - (double)zo);
    double m = fabs((double)zv); if (fabs((double)zo) > m) m = fabs((double)zo);
    if (m == 0.0) return 1;
    return !(a >= m * 9.5367431640625e-07);
}

static float uno_f = 1.0f;

/* One 2-D clip stage.  Stages 2/3/4 are structurally identical (TDPOLYGS.H
   :778-935, :945-1102, :1112-1269): clip coordinate A against `bound`, carry
   coordinate B by interpolation, and set A to the bound exactly.  Stage 5 is
   NOT this function -- it writes mp[] with fistp and stores ubx as an integer.
   dir 0 = "out" means A < bound (jb);  dir 1 = "out" means A > bound (ja).
   No fst appears anywhere in these stages, so the whole interpolation chain
   runs at accumulator width and is narrowed once by the closing fstp. */
static int clip_ovf;
static int clip_stage(const float *A, const float *B, int n, float bound, int dir,
                      float *A2, float *B2, int authorcap)
{
    int vr, dx = n-1, di = 0;
#define ISOUT(t) (dir ? ((t) > bound) : ((t) < bound))
    for (vr = 0; vr < n; vr++) {
        int pvert, nvert;
        if (!ISOUT(A[vr])) { A2[di]=A[vr]; B2[di]=B[vr]; di++; continue; }  /* else_1 */
        pvert = (vr-1>=0)?vr-1:dx;
        nvert = (vr+1<=dx)?vr+1:0;
        if (ISOUT(A[pvert]) && ISOUT(A[nvert])) continue;                   /* STOP  */
        if (!ISOUT(A[pvert]) && !ISOUT(A[nvert])) {                         /* if_2  */
            int o;
            for (o=0;o<2;o++) {
                int ov = o?nvert:pvert;
                if (A[vr] != A[ov]) {                                       /* if_3  */
                    R t = Rdiv(Rsub((R)bound,(R)A[ov]), Rsub((R)A[vr],(R)A[ov]));
                    B2[di] = (float)Radd(Rmul(t, Rsub((R)B[vr],(R)B[ov])), (R)B[ov]);
                } else B2[di] = B[vr];                                      /* else_3 */
                A2[di] = bound;
                di++;
            }
        } else {                                                            /* else_2 */
            int ov = ISOUT(A[pvert]) ? nvert : pvert;
            if (A[vr] != A[ov]) {
                R t = Rdiv(Rsub((R)bound,(R)A[ov]), Rsub((R)A[vr],(R)A[ov]));
                B2[di] = (float)Radd(Rmul(t, Rsub((R)B[vr],(R)B[ov])), (R)B[ov]);
            } else B2[di] = B[vr];
            A2[di] = bound;
            di++;
        }
    }
#undef ISOUT
    /* the author's array is exactly this long; exceeding it smashes the stack
       in the original.  Sizing generously and flagging is the honest port. */
    if (di > authorcap) clip_ovf = 1;
    return di;
}

/* ---- poly3d ------------------------------------------------------------- */

static void poly3d(const float *x, const float *y, const float *z,
                   unsigned nrv, unsigned char colore, TOPO *T, int draw)
{
    float ultima_x[16], ultima_y[16], ultima_z[16];
    F32   video_x0[16], video_y0[16];
    float video_x1[24], video_y1[24];
    float video_x2[32], video_y2[32];
    float video_x3[48], video_y3[48];
    F32   zz, xx, yy, z2, rzf[NV], zkv;
    float rxf[NV], ryf[NV];
    unsigned char ent = entity;
    int i, di, _8n, vr2;
    unsigned char rwf[NV];

    memset(T, 0, sizeof *T);
    T->nrv = (int)nrv;
    T->ret = 1;

    /* ---- rototranslation, TDPOLYGS.H:441-487 ---- */
    T->doflag = 0;
    for (i = 0; i < (int)nrv; i++) {
        R zw, xw, yw, z2w, rzw, a, b;
        zw = FST(&zz, Rsub((R)z[i], (R)cam_z));
        a  = Rmul(zw, (R)opt_psinbeta);
        xw = FST(&xx, Rsub((R)x[i], (R)cam_x));
        b  = Rmul(xw, (R)opt_pcosbeta);
        rxf[i] = (float)Radd(a, b);
        a  = Rmul(FLD(&zz), (R)opt_tcosbeta);
        b  = Rmul(FLD(&xx), (R)opt_tsinbeta);
        z2w = FST(&z2, Rsub(a, b));
        a  = Rmul(z2w, (R)opt_tcosalfa);
        yw = FST(&yy, Rsub((R)y[i], (R)cam_y));
        b  = Rmul(yw, (R)opt_tsinalfa);
        rzw = FST(&rzf[i], Radd(a, b));
        /* fcomp uneg / sahf / jb : unordered sets C3:C2:C0 = 111, so CF = 1
           and a NaN is treated as "behind". */
#ifdef BREAK_NEARSTRICT
        if (rzw > (R)uneg) { T->doflag++; rwf[i] = 1; }
#else
        if (!(rzw < (R)uneg)) { T->doflag++; rwf[i] = 1; }   /* :478 jb */
#endif
        else rwf[i] = 0;
        a = Rmul(FLD(&yy), (R)opt_pcosalfa);
        b = Rmul(FLD(&z2), (R)opt_psinalfa);
        ryf[i] = (float)Rsub(a, b);
        T->rwf[i] = rwf[i];
    }
    if (!T->doflag) { T->ret = 1; return; }

    if (T->doflag == (int)nrv) {                              /* :493 fast load */
        for (i = 0; i < (int)nrv; i++) {
            ultima_x[i] = rxf[i]; ultima_y[i] = ryf[i]; ultima_z[i] = rzf[i].m;
        }
        vr2 = (int)nrv;
    } else {
        int vr, dx = (int)nrv - 1;
        di = 0;
        for (vr = 0; vr < (int)nrv; vr++) {
            int pvert, nvert;
            if (rwf[vr] != 0) {                                /* :676 bypass */
                ultima_x[di>>2] = rxf[vr]; ultima_y[di>>2] = ryf[vr];
                ultima_z[di>>2] = rzf[vr].m;
                di += 4; continue;
            }
            pvert = (vr - 1 >= 0) ? vr - 1 : dx;
            nvert = (vr + 1 <= dx) ? vr + 1 : 0;
            if (rwf[pvert] == 0 && rwf[nvert] == 0) continue;  /* :537 STOP1 */
            if (rwf[pvert] + rwf[nvert] == 2) {                /* :550 if11 */
                int o;
                for (o = 0; o < 2; o++) {
                    int ov = o ? nvert : pvert;
                    int slot = (di >> 2) + o;
                    if (illconditioned(rzf[vr].m, rzf[ov].m)) T->illcond++;
                    if (rzf[vr].m != rzf[ov].m) {              /* :558 jne */
                        R num = Rsub((R)uneg, (R)rzf[ov].m);
                        R den = Rsub((R)rzf[vr].m, (R)rzf[ov].m);
                        R zkw;
#ifdef BREAK_ZKEPS
                        if (fabsl(den) < 0.01L) { ultima_x[slot]=rxf[vr]; ultima_y[slot]=ryf[vr];
                                                  ultima_z[slot]=uneg; continue; }
#endif
                        zkw = FST(&zkv, Rdiv(num, den));
                        ultima_x[slot] = (float)Radd(Rmul(zkw, Rsub((R)rxf[vr], (R)rxf[ov])), (R)rxf[ov]);
                        /* the second half reloads zk from memory (narrow) */
                        ultima_y[slot] = (float)Radd(Rmul(FLD(&zkv), Rsub((R)ryf[vr], (R)ryf[ov])), (R)ryf[ov]);
                    } else {
                        T->zk_degenerate++;
                        ultima_x[slot] = rxf[vr]; ultima_y[slot] = ryf[vr];
                    }
                    ultima_z[slot] = uneg;                     /* dword copy of uneg */
                }
                di += 8;
            } else {                                           /* :628 else11 */
                int vvert = (rwf[pvert] != 0) ? pvert : nvert;
                int slot = di >> 2;
                if (illconditioned(rzf[vr].m, rzf[vvert].m)) T->illcond++;
                if (rzf[vr].m != rzf[vvert].m) {
                    R num = Rsub((R)uneg, (R)rzf[vvert].m);
                    R den = Rsub((R)rzf[vr].m, (R)rzf[vvert].m);
                    R zkw;
#ifdef BREAK_ZKEPS
                    if (fabsl(den) < 0.01L) { ultima_x[slot]=rxf[vr]; ultima_y[slot]=ryf[vr];
                                              ultima_z[slot]=uneg; di+=4; continue; }
#endif
                    zkw = FST(&zkv, Rdiv(num, den));
                    ultima_x[slot] = (float)Radd(Rmul(zkw, Rsub((R)rxf[vr], (R)rxf[vvert])), (R)rxf[vvert]);
                    ultima_y[slot] = (float)Radd(Rmul(FLD(&zkv), Rsub((R)ryf[vr], (R)ryf[vvert])), (R)ryf[vvert]);
                } else {
                    T->zk_degenerate++;
                    ultima_x[slot] = rxf[vr]; ultima_y[slot] = ryf[vr];
                }
                ultima_z[slot] = uneg;
                di += 4;
            }
        }
        vr2 = di >> 2;
        if (vr2 < 3) { T->vr2 = vr2; T->ret = 2; return; }
    }
    T->vr2 = vr2;

    /* ---- projector + bbox gate, :705-764 ---- */
    {
        int32_t ax = lbxl, bxa = lbyl, cx = ubxl, dxa = ubyl;
        int si;
        _8n = 8*(vr2-1);
        for (si = vr2-1; si >= 0; si--) {
            R inv = Rdiv((R)uno_f, (R)ultima_z[si]);
            R t   = Radd(Rmul(inv, (R)ultima_x[si]), (R)x_centro_f);
            R w   = FST(&video_x0[si], t);
            T->mp[2*si]   = f2i(w);
            if (!(T->mp[2*si] >= cx)) cx = T->mp[2*si];
            if (!(T->mp[2*si] <= ax)) ax = T->mp[2*si];
            t = Radd(Rmul(inv, (R)ultima_y[si]), (R)y_centro_f);
            w = FST(&video_y0[si], t);
            T->mp[2*si+1] = f2i(w);
            if (!(T->mp[2*si+1] >= dxa)) dxa = T->mp[2*si+1];
            if (!(T->mp[2*si+1] <= bxa)) bxa = T->mp[2*si+1];
        }
        T->nmp = vr2;
        T->max_x = (unsigned short)ax; T->max_y = (unsigned short)bxa;
        T->min_x = (unsigned short)cx; T->min_y = (unsigned short)dxa;
        T->gate_si = 0;
#ifdef BREAK_BBOXGT
        if (!(ax <= ubxl)) { T->gate_si++; T->gate[0]=1; T->max_x = UBX; }
#else
        if (!(ax <  ubxl)) { T->gate_si++; T->gate[0]=1; T->max_x = UBX; }
#endif
        if (!(bxa <  ubyl)) { T->gate_si++; T->gate[1]=1; T->max_y = UBY; }
#ifdef BREAK_BBOXLE
        if (!(cx >  lbxl)) { T->gate_si++; T->gate[2]=1; T->min_x = LBX; }
#else
        if (!(cx >= lbxl)) { T->gate_si++; T->gate[2]=1; T->min_x = LBX; }
#endif
        if (!(dxa >= lbyl)) { T->gate_si++; T->gate[3]=1; T->min_y = LBY; }
        T->clip_needed = (T->gate_si != 0);
    }

    if (!T->clip_needed) {
        T->vr3 = T->vr4 = T->vr5 = T->vr6 = vr2;
        T->ret = 0;
        if (draw) {
            BBOX bb; bb.min_x=T->min_x; bb.max_x=T->max_x; bb.min_y=T->min_y; bb.max_y=T->max_y;
            poly3d_drawb(T->mp, vr2, bb, colore, flares, ent);
        }
        return;
    }

    /* ---- the four 2-D clip stages, :778-1441 ---- */
    {
        int n, m, k;
        /* stage 2: y < lbyf ; stage 3: y > ubyf ; stage 4: x < lbxf */
        float A[48], B[48], A2[48], B2[48];
        n = vr2;
        for (k = 0; k < n; k++) { A[k] = FLD(&video_y0[k]); B[k] = FLD(&video_x0[k]); }
        m = clip_stage(A, B, n, lbyf, 0, A2, B2, 12);
        T->vr3 = m; if (m < 3) { T->ret = 3; return; }
        for (k = 0; k < m; k++) { video_y1[k]=A2[k]; video_x1[k]=B2[k]; }

        n = m;
        for (k = 0; k < n; k++) { A[k]=video_y1[k]; B[k]=video_x1[k]; }
        m = clip_stage(A, B, n, ubyf, 1, A2, B2, 16);
        T->vr4 = m; if (m < 3) { T->ret = 4; return; }
        for (k = 0; k < m; k++) { video_y2[k]=A2[k]; video_x2[k]=B2[k]; }

        n = m;
        for (k = 0; k < n; k++) { A[k]=video_x2[k]; B[k]=video_y2[k]; }
        m = clip_stage(A, B, n, lbxf, 0, A2, B2, 24);
        T->vr5 = m; if (m < 3) { T->ret = 5; return; }
        for (k = 0; k < m; k++) { video_x3[k]=A2[k]; video_y3[k]=B2[k]; }

        /* stage 5 writes mp directly with fistp, :1283-1441 */
        {
            int vr, dx = m - 1, dii = 0;
            for (vr = 0; vr < m; vr++) {
                int pvert, nvert;
                if (!(video_x3[vr] > ubxf)) {                    /* else51 */
                    if (dii+8 > 256) { T->mp_overflow = 1; break; }
                    T->mp[dii/4]   = f2i((R)video_x3[vr]);
                    T->mp[dii/4+1] = f2i((R)video_y3[vr]);
                    dii += 8; continue;
                }
                pvert = (vr - 1 >= 0) ? vr - 1 : dx;
                nvert = (vr + 1 <= dx) ? vr + 1 : 0;
                if (video_x3[pvert] > ubxf && video_x3[nvert] > ubxf) continue;
                if (!(video_x3[pvert] > ubxf) && !(video_x3[nvert] > ubxf)) {
                    int o;
                    for (o = 0; o < 2; o++) {
                        int ov = o ? nvert : pvert;
                        int base = dii/4 + 2*o;
                        if (base+1 >= 64) { T->mp_overflow = 1; break; }
                        if (video_x3[vr] != video_x3[ov]) {
                            R t = Rdiv(Rsub((R)ubxf, (R)video_x3[ov]),
                                       Rsub((R)video_x3[vr], (R)video_x3[ov]));
                            T->mp[base+1] = f2i(Radd(Rmul(t, Rsub((R)video_y3[vr], (R)video_y3[ov])),
                                                     (R)video_y3[ov]));
                        } else {
                            T->mp[base+1] = f2i((R)video_y3[vr]);
                        }
                        T->mp[base] = UBX;                        /* mov word mp[di],ubx */
                    }
                    dii += 16;
                } else {
                    int ov = (video_x3[pvert] > ubxf) ? nvert : pvert;
                    int base = dii/4;
                    if (base+1 >= 64) { T->mp_overflow = 1; break; }
                    if (video_x3[vr] != video_x3[ov]) {
                        R t = Rdiv(Rsub((R)ubxf, (R)video_x3[ov]),
                                   Rsub((R)video_x3[vr], (R)video_x3[ov]));
                        T->mp[base+1] = f2i(Radd(Rmul(t, Rsub((R)video_y3[vr], (R)video_y3[ov])),
                                                 (R)video_y3[ov]));
                    } else {
                        T->mp[base+1] = f2i((R)video_y3[vr]);
                    }
                    T->mp[base] = UBX;
                    dii += 8;
                }
            }
            _8n = dii - 8;
            T->vr6 = dii >> 3;
            T->nmp = T->vr6;
            if (T->vr6 < 3) { T->ret = 6; return; }
        }
    }

    T->ret = 0;
    if (draw) {
        BBOX bb; bb.min_x=T->min_x; bb.max_x=T->max_x; bb.min_y=T->min_y; bb.max_y=T->max_y;
        poly3d_drawb(T->mp, T->vr6, bb, colore, flares, ent);
    }
}

/* ---- polymap front half -------------------------------------------------- */

static void polymap_project(float *x, float *y, float *z, int nv, TOPO *T)
{
    float ultima_x[16], ultima_y[16], ultima_z[16];
    F32 zz, xx, yy, z2, rzf[NV];
    float rxf[NV], ryf[NV];
    float trxf[NV], tryf[NV], trzf[NV];
    float midx, midy, midz;
    float rx,ry,rz,mx,my,mz,nx,ny,nz;
    unsigned char rwf[NV];
    int i, di, vr2, vr22;

    memset(T, 0, sizeof *T);
    T->nrv = nv; T->ret = 1;

    if (nv == 3) { x[3]=x[2]; y[3]=y[2]; z[3]=z[2]; }   /* :1973 caller-visible */

    T->gamma_nonzero = (gammaf != 0.0f);
    if (T->gamma_nonzero) { T->ret = 9; return; }       /* t_axis is dead code */

    T->doflag = 0;
    for (i = 0; i < 4; i++) {                            /* :2048 vertex (4 fixed) */
        R zw,xw,yw,z2w,rzw,a,b;
        zw = FST(&zz, Rsub((R)z[i], (R)cam_z));
        a  = Rmul(zw, (R)opt_tsinbeta);
        xw = FST(&xx, Rsub((R)x[i], (R)cam_x));
        b  = Rmul(xw, (R)opt_tcosbeta);
        rxf[i] = (float)Radd(a, b);
        a = Rmul(FLD(&zz), (R)opt_tcosbeta);
        b = Rmul(FLD(&xx), (R)opt_tsinbeta);
        z2w = FST(&z2, Rsub(a,b));
        a = Rmul(z2w, (R)opt_tcosalfa);
        yw = FST(&yy, Rsub((R)y[i], (R)cam_y));
        b = Rmul(yw, (R)opt_tsinalfa);
        rzw = FST(&rzf[i], Radd(a,b));
#ifdef BREAK_NEARSTRICT
        if (rzw > (R)uneg) { T->doflag++; rwf[i]=1; }
#else
        if (!(rzw < (R)uneg)) { T->doflag++; rwf[i]=1; }
#endif
        else rwf[i]=0;
        a = Rmul(FLD(&yy), (R)opt_tcosalfa);
        b = Rmul(FLD(&z2), (R)opt_tsinalfa);
        ryf[i] = (float)Rsub(a,b);
        T->rwf[i]=rwf[i];
    }
    if (!T->doflag) { T->ret = 1; return; }

    /* :2102 antialias expansion about the centroid */
    if (nv == 3) {
        midx = (float)(((double)rxf[0]+rxf[1]+rxf[2])*0.3333333);
        midy = (float)(((double)ryf[0]+ryf[1]+ryf[2])*0.3333333);
        midz = (float)(((double)rzf[0].m+rzf[1].m+rzf[2].m)*0.3333333);
        for (i=0;i<3;i++) {
            trxf[i]=(float)(((double)rxf[i]-midx)*x_antialias+midx);
            tryf[i]=(float)(((double)ryf[i]-midy)*y_antialias+midy);
            trzf[i]=(float)(((double)rzf[i].m-midz)*z_antialias+midz);
        }
        trxf[3]=trxf[2]; tryf[3]=tryf[2]; trzf[3]=trzf[2];   /* _SI = 8 -> uses [2] */
    } else {
        midx = (float)(((double)rxf[0]+rxf[1]+rxf[2]+rxf[3])*0.25);
        midy = (float)(((double)ryf[0]+ryf[1]+ryf[2]+ryf[3])*0.25);
        midz = (float)(((double)rzf[0].m+rzf[1].m+rzf[2].m+rzf[3].m)*0.25);
        for (i=0;i<4;i++) {
            trxf[i]=(float)(((double)rxf[i]-midx)*x_antialias+midx);
            tryf[i]=(float)(((double)ryf[i]-midy)*y_antialias+midy);
            trzf[i]=(float)(((double)rzf[i].m-midz)*z_antialias+midz);
        }
    }
    {
        int last = (nv==3) ? 2 : 3;                    /* _SI = 8 or 12 bytes */
        rx = trxf[0]; mx = (float)Rsub((R)trxf[1],(R)rx); nx = (float)Rsub((R)rx,(R)trxf[last]);
        ry = tryf[0]; my = (float)Rsub((R)tryf[1],(R)ry); ny = (float)Rsub((R)ry,(R)tryf[last]);
        rz = trzf[0]; mz = (float)Rsub((R)trzf[1],(R)rz); nz = (float)Rsub((R)rz,(R)trzf[last]);
    }
    T->basis[0] = (float)Rmul(Rsub(Rmul((R)rx,(R)mz),Rmul((R)rz,(R)mx)),(R)YCOEFF);   /* hx */
    T->basis[3] = (float)Rmul(Rsub(Rmul((R)rx,(R)nz),Rmul((R)rz,(R)nx)),(R)YCOEFF);   /* hy */
    T->basis[6] = (float)Rmul(Rsub(Rmul((R)nx,(R)mz),Rmul((R)nz,(R)mx)),(R)inv_dpp);  /* hz */
    T->basis[1] = (float)Rmul(Rsub(Rmul((R)rz,(R)my),Rmul((R)ry,(R)mz)),(R)XCOEFF);   /* vx */
    T->basis[4] = (float)Rmul(Rsub(Rmul((R)rz,(R)ny),Rmul((R)ry,(R)nz)),(R)XCOEFF);   /* vy */
    T->basis[7] = (float)Rmul(Rsub(Rmul((R)nz,(R)my),Rmul((R)ny,(R)mz)),(R)inv_dpp);  /* vz */
    T->basis[2] = (float)Rmul(Rsub(Rmul((R)ry,(R)mx),Rmul((R)rx,(R)my)),(R)EMU_K);    /* ox */
    T->basis[5] = (float)Rmul(Rsub(Rmul((R)ry,(R)nx),Rmul((R)rx,(R)ny)),(R)EMU_K);    /* oy */
    T->basis[8] = (float)Rsub(Rmul((R)ny,(R)mx),Rmul((R)nx,(R)my));                   /* oz */
    T->basis_valid = 1;

    if (T->doflag == 4) {                               /* :2233 */
        for (i=0;i<4;i++) { ultima_x[i]=rxf[i]; ultima_y[i]=ryf[i]; ultima_z[i]=rzf[i].m; }
        vr2 = 4; vr22 = 8;
    } else {
        int vr, dx = 3;
        di = 0;
        for (vr = 0; vr < 4; vr++) {
            int pvert, nvert;
            if (rwf[vr] != 0) {
                ultima_x[di>>2]=rxf[vr]; ultima_y[di>>2]=ryf[vr]; ultima_z[di>>2]=rzf[vr].m;
                di += 4; continue;
            }
            pvert = (vr-1>=0)?vr-1:dx;
            nvert = (vr+1<=dx)?vr+1:0;
            if (rwf[pvert]==0 && rwf[nvert]==0) continue;
            if (rwf[pvert]+rwf[nvert]==2) {
                int o;
                for (o=0;o<2;o++) {
                    int ov = o?nvert:pvert, slot=(di>>2)+o;
                    F32 zkv;
                    if (illconditioned(rzf[vr].m, rzf[ov].m)) T->illcond++;
                    if (rzf[vr].m != rzf[ov].m) {
                        R zkw = FST(&zkv, Rdiv(Rsub((R)uneg,(R)rzf[ov].m),
                                               Rsub((R)rzf[vr].m,(R)rzf[ov].m)));
                        ultima_x[slot]=(float)Radd(Rmul(zkw,Rsub((R)rxf[vr],(R)rxf[ov])),(R)rxf[ov]);
                        ultima_y[slot]=(float)Radd(Rmul(FLD(&zkv),Rsub((R)ryf[vr],(R)ryf[ov])),(R)ryf[ov]);
                    } else { T->zk_degenerate++; ultima_x[slot]=rxf[vr]; ultima_y[slot]=ryf[vr]; }
                    ultima_z[slot]=uneg;
                }
                di += 8;
            } else {
                int ov = (rwf[pvert]!=0)?pvert:nvert, slot=di>>2;
                F32 zkv;
                if (illconditioned(rzf[vr].m, rzf[ov].m)) T->illcond++;
                if (rzf[vr].m != rzf[ov].m) {
                    R zkw = FST(&zkv, Rdiv(Rsub((R)uneg,(R)rzf[ov].m),
                                           Rsub((R)rzf[vr].m,(R)rzf[ov].m)));
                    ultima_x[slot]=(float)Radd(Rmul(zkw,Rsub((R)rxf[vr],(R)rxf[ov])),(R)rxf[ov]);
                    ultima_y[slot]=(float)Radd(Rmul(FLD(&zkv),Rsub((R)ryf[vr],(R)ryf[ov])),(R)ryf[ov]);
                } else { T->zk_degenerate++; ultima_x[slot]=rxf[vr]; ultima_y[slot]=ryf[vr]; }
                ultima_z[slot]=uneg;
                di += 4;
            }
        }
        vr22 = di >> 1; vr2 = di >> 2;
        if (vr2 < 3) { T->vr2=vr2; T->ret=2; return; }
    }
    T->vr2 = vr2; T->vr3 = vr22;

    {   /* :2444 projector -- dpp/Zc, and only a y-extent is tracked */
        int32_t bxa = lbyl, dxa = ubyl;
        int si;
        for (si = vr2-1; si >= 0; si--) {
            R inv = Rdiv((R)dpp, (R)ultima_z[si]);
            T->mp[2*si]   = f2i(Radd(Rmul(inv,(R)ultima_x[si]), (R)x_centro_f));
            T->mp[2*si+1] = f2i(Radd(Rmul(inv,(R)ultima_y[si]), (R)y_centro_f));
            if (!(T->mp[2*si+1] >= dxa)) dxa = T->mp[2*si+1];
            if (!(T->mp[2*si+1] <= bxa)) bxa = T->mp[2*si+1];
        }
        T->nmp = vr2;
        {
            int32_t miny = dxa, maxy = bxa;
            if (!(miny <= ubyl)) { T->ret = 7; return; }     /* :2476 */
            if (!(maxy >= lbyl)) { T->ret = 7; return; }
            if (!(miny >= lbyl)) miny = lbyl;                /* :2487 */
            if (!(maxy <= ubyl)) maxy = ubyl;
            if (!(miny <= maxy)) { T->ret = 8; return; }
            T->min_y = (unsigned)miny; T->max_y = (unsigned)maxy;
        }
    }
    T->ret = 0;
}

/* per-row u/v derivation, :2694-2738.  Graded as part of S6, bounded. */
static void polymap_rowuv(const float *basis, int i, int ipart_i,
                          int32_t *u, int32_t *v, float *zout, float *k4out)
{
    R p, t, _x, _y, _z, k4;
    R hx=basis[0], vx=basis[1], ox=basis[2];
    R hy=basis[3], vy=basis[4], oy=basis[5];
    R hz=basis[6], vz=basis[7], oz=basis[8];
    R tX = (R)(float)XSIZE, tY = (R)(float)YSIZE;
#ifdef BREAK_NOPLUS1
    p = Rsub(i2f(ipart_i), (R)x_centro_f);
#else
    p = Radd(Rsub(i2f(ipart_i), (R)x_centro_f), (R)uno_f);      /* ipart - xc + 1 */
#endif
    t = Radd(Rmul(Rsub(i2f(i), (R)y_centro_f), hz), Rmul(p, vz));
    _z = Radd(t, oz);
    *zout = (float)_z;
    k4 = Rdiv((R)uno_f, _z);
    *k4out = (float)k4;
    t = Radd(Rmul(Rsub(i2f(i), (R)y_centro_f), hx), Rmul(p, vx));
    _x = Radd(t, ox);
    t = Radd(Rmul(Rsub(i2f(i), (R)y_centro_f), hy), Rmul(p, vy));
    _y = Radd(t, oy);
    /* fld _y / fmul tempYsize / fmul k4 ; fld _x / fmul tempXsize / fmul k4 ;
       fxch / fistp v / fistp u */
    *v = f2i(Rmul(Rmul(_y, tY), k4));
    *u = f2i(Rmul(Rmul(_x, tX), k4));
}

/* ---- getcoords, :3086-3204 ---------------------------------------------- */
static int32_t gc_x, gc_y;
static int getcoords(float x, float y, float z)
{
    F32 zz, xx, yy, z2;
    R zw,xw,yw,z2w,rzw,a,b,rx,ry,inv,t;
    zw = FST(&zz, Rsub((R)z,(R)cam_z));
    a = Rmul(zw,(R)opt_tsinbeta);
    xw = FST(&xx, Rsub((R)x,(R)cam_x));
    b = Rmul(xw,(R)opt_tcosbeta);
    rx = q(a+b);
    { float rxf_ = (float)rx; rx = (R)rxf_; }        /* fstp rx : a float local */
    a = Rmul(FLD(&zz),(R)opt_tcosbeta);
    b = Rmul(FLD(&xx),(R)opt_tsinbeta);
    z2w = FST(&z2, Rsub(a,b));
    a = Rmul(z2w,(R)opt_tcosalfa);
    yw = FST(&yy, Rsub((R)y,(R)cam_y));
    b = Rmul(yw,(R)opt_tsinalfa);
    rzw = Radd(a,b);
    { F32 rzs; rzw = FST(&rzs, rzw); }               /* fst rz -- wide kept for fcomp */
    if (rzw < (R)uneg) return 0;
    a = Rmul(FLD(&yy),(R)opt_tcosalfa);
    b = Rmul(FLD(&z2),(R)opt_tsinalfa);
    ry = (R)(float)Rsub(a,b);                        /* fstp ry */
    /* `fld dpp / fdiv rz` reloads rz from memory, i.e. the NARROWED value.
       The wide value was consumed by fcomp uneg and nothing else. */
    inv = Rdiv((R)dpp, (R)(float)rzw);
    t = Radd(Rmul(inv, rx), (R)x_centro_f);
    gc_x = f2i(t);
    t = Radd(Rmul(inv, ry), (R)y_centro_f);
    gc_y = f2i(t);
#ifdef BREAK_GETCOORDINCL
    if (gc_x >= lbxl && gc_x <= ubxl && gc_y >= lbyl && gc_y <= ubyl) return 1;
#else
    if (gc_x > lbxl && gc_x < ubxl && gc_y > lbyl && gc_y < ubyl) return 1;   /* :3200 */
#endif
    return 0;
}

/* ---- facing, :3206-3270 -------------------------------------------------- */
static int facing(const float *x, const float *y, const float *z)
{
    R x1,y1,z1,x2,y2,z2v,xr,yr,zr,s;
    x1=(R)(float)Rsub((R)x[0],(R)x[2]); y1=(R)(float)Rsub((R)y[0],(R)y[2]); z1=(R)(float)Rsub((R)z[0],(R)z[2]);
    x2=(R)(float)Rsub((R)x[1],(R)x[2]); y2=(R)(float)Rsub((R)y[1],(R)y[2]);
    z2v=Rsub((R)z[1],(R)z[2]);                        /* fst z2 : wide kept */
    { F32 s2; z2v = FST(&s2, z2v);
      xr=(R)(float)Rsub(Rmul(z2v,y1), Rmul(y2,z1));
      yr=(R)(float)Rsub(Rmul(z1,x2), Rmul(FLD(&s2),x1)); }
    zr=(R)(float)Rsub(Rmul(x1,y2), Rmul(x2,y1));
    s = Radd(Radd(Rmul(Rsub((R)cam_x,(R)x[2]),xr), Rmul(Rsub((R)cam_y,(R)y[2]),yr)),
             Rmul(Rsub((R)cam_z,(R)z[2]),zr));
    return (s < 0.0L) ? 0 : 1;                        /* ftst / jb _zero */
}

/* ==================================================== corpus + record I/O   */

#ifndef PGBREAK
#define PGBREAK "none"
#endif

static FILE *pagefp = NULL;
static unsigned char SNAP[PGUNITS];      /* page as it was before the case ran */
static unsigned char CARRY[PGUNITS];     /* previous case's OUTPUT page        */
static int have_carry = 0;

static uint32_t fnv32(const unsigned char *p, size_t n)
{
    uint32_t h = 2166136261u; size_t i;
    for (i=0;i<n;i++) { h ^= p[i]; h *= 16777619u; }
    return h;
}

static void emit_page(const char *id)
{
    char hex[65]; long nz=0, n255=0; unsigned j; int r;
    for (j=0;j<PGUNITS;j++) { if (P[j]) nz++; if (P[j]==255) n255++; }
    sha_hex(P, PGUNITS, hex);
    printf("K20 PAGE %s sha=%s\n", id, hex);
    printf("K21 CENSUS %s nz=%ld n255=%ld seg=%ld rows=%ld fb1=%ld filled=%ld edgew=%ld spanpx=%ld\n",
           id, nz, n255, ct_seg_calls, ct_rows_scanned, ct_rows_fb1,
           ct_bytes_filled, ct_edge_writes, ct_span_pixels);
    for (r=0;r<200;r++) {
        const unsigned char *a = &P[4 + 320*r];
        const unsigned char *b = &SNAP[4 + 320*r];
        if (memcmp(a,b,320)) printf("K26 ROW %s r=%d h=%08x\n", id, r, fnv32(a,320));
    }
    /* the two scratch pixels are a free canary: a polymap call that did not
       touch them did not run (BUFFERMAP 2.6). */
    printf("K2B SCRATCH %s t=%u e=%u\n", id, P[0xFA00], P[0xFA01]);
    if (pagefp) {
        char nm[32]; memset(nm,0,sizeof nm);
        strncpy(nm, id, 31);
        fwrite(nm,1,32,pagefp); fwrite(P,1,PGUNITS,pagefp);
    }
    memcpy(CARRY, P, PGUNITS); have_carry = 1;
}

static void emit_mp(const char *id, const int32_t *mp, int n)
{
    int k;
    printf("K22 MP %s n=%d", id, n);
    for (k=0;k<2*n;k++) printf(" %ld", (long)mp[k]);
    printf("\n");
}
static void emit_topo(const char *id, const TOPO *T)
{
    printf("K24 TOPO %s ret=%d doflag=%d rwf=%d%d%d%d vr2=%d vr3=%d vr4=%d vr5=%d vr6=%d "
           "gate=%d%d%d%d gsi=%d clip=%d bbox=%u,%u,%u,%u ill=%d zkdeg=%d mpovf=%d clipovf=%d\n",
           id, T->ret, T->doflag, T->rwf[0],T->rwf[1],T->rwf[2],T->rwf[3],
           T->vr2,T->vr3,T->vr4,T->vr5,T->vr6,
           T->gate[0],T->gate[1],T->gate[2],T->gate[3], T->gate_si, T->clip_needed,
           T->min_x,T->max_x,T->min_y,T->max_y, T->illcond, T->zk_degenerate,
           T->mp_overflow, clip_ovf);
}
static void emit_lim(const char *id, int y0, int y1)
{
    int k;
    printf("K23 LIM %s y0=%d y1=%d", id, y0, y1);
    for (k=y0;k<=y1;k++) printf(" %d:%d", ipart[k], fpart[k]);
    printf("\n");
}

/* ------------------------------------------------------------ tokenizer    */

#define MAXTOK 48
static char *tk_key[MAXTOK], *tk_val[MAXTOK];
static int   tk_n;
static char  tk_dir[32], tk_id[64];
static const char *tk_id_ref(void) { return tk_id; }

static int split_line(char *line)
{
    char *p = line, *t;
    tk_n = 0;
    while (*p==' '||*p=='\t') p++;
    if (*p=='#' || *p=='\n' || *p=='\r' || *p==0) return 0;
    t = strtok(p, " \t\r\n"); if (!t) return 0;
    strncpy(tk_dir, t, sizeof tk_dir - 1); tk_dir[sizeof tk_dir - 1]=0;
    t = strtok(NULL, " \t\r\n"); if (!t) return 0;
    strncpy(tk_id, t, sizeof tk_id - 1); tk_id[sizeof tk_id - 1]=0;
    while ((t = strtok(NULL, " \t\r\n")) != NULL) {
        char *eq = strchr(t,'=');
        if (!eq) { fprintf(stderr,"pg_ref: bad token '%s' on %s %s\n", t, tk_dir, tk_id); exit(2); }
        *eq = 0;
        if (tk_n >= MAXTOK) { fprintf(stderr,"pg_ref: too many tokens\n"); exit(2); }
        tk_key[tk_n]=t; tk_val[tk_n]=eq+1; tk_n++;
    }
    return 1;
}
static const char *getv(const char *k, const char *def)
{
    int i; for (i=0;i<tk_n;i++) if (!strcmp(tk_key[i],k)) return tk_val[i];
    if (def) return def;
    fprintf(stderr,"pg_ref: %s %s: missing required key '%s'\n", tk_dir, tk_id, k); exit(2);
}
static long geti(const char *k, long def)
{
    int i; for (i=0;i<tk_n;i++) if (!strcmp(tk_key[i],k)) return strtol(tk_val[i],NULL,0);
    return def;
}
static long getir(const char *k)   /* required */
{
    const char *v = getv(k,NULL); return strtol(v,NULL,0);
}
static float hexf(const char *s)
{
    uint32_t b; float f;
    if (s[0]=='0' && (s[1]=='x'||s[1]=='X')) b = (uint32_t)strtoul(s,NULL,16);
    else { double d = strtod(s,NULL); f = (float)d; memcpy(&b,&f,4); }
    memcpy(&f,&b,4); return f;
}
static int parse_i32list(const char *s, int32_t *out, int max)
{
    int n=0; const char *p=s;
    while (*p) {
        char *e;
        long v = strtol(p,&e,0);
        if (e==p) break;
        if (n>=max) { fprintf(stderr,"pg_ref: list too long\n"); exit(2); }
        out[n++]=(int32_t)v;
        p=e; while (*p==','||*p==';') p++;
    }
    return n;
}
static int parse_f32list(const char *s, float *out, int max)
{
    int n=0; const char *p=s;
    char buf[64];
    while (*p) {
        int k=0;
        while (*p && *p!=',' && *p!=';') { if (k<63) buf[k++]=*p; p++; }
        buf[k]=0;
        if (!k) break;
        if (n>=max) { fprintf(stderr,"pg_ref: float list too long\n"); exit(2); }
        out[n++]=hexf(buf);
        while (*p==','||*p==';') p++;
    }
    return n;
}

static void reset_counters(void)
{
    ct_seg_calls=ct_rows_scanned=ct_rows_fb1=ct_bytes_filled=0;
    ct_edge_writes=ct_span_pixels=0;
    clip_ovf = 0;
}
static void setup_page(void)
{
    const char *pre = getv("pre","PRE0");
    preset_page(pre, have_carry ? CARRY : NULL);
    memcpy(SNAP, P, PGUNITS);
}

/* --------------------------------------------------------------- cases     */

static void case_SEG(void)
{
    reset_counters(); setup_page();
    g_xp=(uint32_t)getir("xp"); g_yp=(uint32_t)getir("yp");
    g_xa=(uint32_t)getir("xa"); g_ya=(uint32_t)getir("ya");
    Segmento();
    emit_page(tk_id);
}

static void case_BBOX(void)
{
    int32_t mp[64]; int n = (int)getir("n"); BBOX bb;
    int got = parse_i32list(getv("mp",NULL), mp, 64);
    if (got != 2*n) { fprintf(stderr,"pg_ref: %s mp has %d values, expected %d\n", tk_id, got, 2*n); exit(2); }
    reset_counters();
    bbox_gate(mp, n, &bb);
    printf("K25 BBOX %s minx=%u maxx=%u miny=%u maxy=%u gate=%d%d%d%d si=%d clip=%d\n",
           tk_id, bb.min_x, bb.max_x, bb.min_y, bb.max_y,
           bb.fired[0],bb.fired[1],bb.fired[2],bb.fired[3], bb.si, bb.clip_needed);
}

static void case_FILL(void)
{
    int32_t mp[64]; int n = (int)getir("n"); BBOX bb; int32_t bx[4];
    int got = parse_i32list(getv("mp",NULL), mp, 64);
    if (got != 2*n) { fprintf(stderr,"pg_ref: %s mp has %d values, expected %d\n", tk_id, got, 2*n); exit(2); }
    if (parse_i32list(getv("bbox",NULL), bx, 4) != 4) { fprintf(stderr,"pg_ref: %s bad bbox\n", tk_id); exit(2); }
    reset_counters(); setup_page();
    bb.min_x=(unsigned)bx[0]; bb.max_x=(unsigned)bx[1];
    bb.min_y=(unsigned)bx[2]; bb.max_y=(unsigned)bx[3];
    bb.si=0; bb.clip_needed=0;
    poly3d_drawb(mp, n, bb, (unsigned char)geti("colore",1),
                 (char)geti("flares",0), (unsigned char)geti("entity",1));
    emit_page(tk_id);
}

static void case_EDGE(void)
{
    int32_t mp[64]; int n = (int)getir("n");
    int y0 = (int)getir("miny"), y1 = (int)getir("maxy");
    int got = parse_i32list(getv("mp",NULL), mp, 60);
    if (got != 2*n) { fprintf(stderr,"pg_ref: %s mp has %d values, expected %d\n", tk_id, got, 2*n); exit(2); }
    reset_counters();
    polymap_edges(mp, n, y0, y1);
    emit_lim(tk_id, y0, y1);
}

static void case_SPAN(void)
{
    int32_t uv[512]; int nuv, blk=0;
    int i = (int)getir("i");
    int ip = (int)getir("ipart"), fp = (int)getir("fpart");
    int maxy = (int)geti("maxy", i+1);
    int k;
    reset_counters(); setup_page();
    preset_tex(getv("tex","TEX0"));
    for (k=0;k<MPIY;k++) { fpart[k]=(int)lbxl; ipart[k]=(int)ubxl; }
    ipart[i]=ip; fpart[i]=fp;
    nuv = parse_i32list(getv("uv",NULL), uv, 512) / 2;
    /* :2677 ol_end preamble: tinta and escrescenze into the two scratch pixels */
    wr8(SCR_TINTA, (unsigned char)geti("tinta",0));
    wr8(SCR_ESCR,  (unsigned char)geti("escr",0xE0));
    polymap_span_row(i, (unsigned char)geti("flares",0), (int)geti("cull",0),
                     uv, nuv, &blk);
    if ((int)geti("half",0)) polymap_halfscan(i, maxy);
    printf("K2C SPANRUN %s blocks=%d sections=%d\n", tk_id, blk, fp-ip);
    emit_page(tk_id);
}

static void apply_camera(void)
{
    float t[4];
    const char *c = getv("cam", "0x00000000,0x00000000,0x00000000");
    const char *a = getv("ang", "0x00000000,0x00000000,0x00000000");
    parse_f32list(c, t, 3); cam_x=t[0]; cam_y=t[1]; cam_z=t[2];
    parse_f32list(a, t, 3); alfa=t[0]; beta=t[1]; gammaf=t[2];
    dpp  = hexf(getv("dpp", "0x43520000"));       /* 210.0f, NOCTIS.CPP:2214 */
    uneg = hexf(getv("uneg","0x42c80000"));       /* 100.0f */
    change_camera_lens();
}

static void case_PROJ(void)
{
    float vx[16], vy[16], vz[16], tmp[64];
    int nrv = (int)getir("nrv"), k, got;
    TOPO T;
    const char *which = getv("which","poly3d");
    got = parse_f32list(getv("v",NULL), tmp, 48);
    if (got != 3*nrv) { fprintf(stderr,"pg_ref: %s v has %d values, expected %d\n", tk_id, got, 3*nrv); exit(2); }
    for (k=0;k<nrv;k++) { vx[k]=tmp[3*k]; vy[k]=tmp[3*k+1]; vz[k]=tmp[3*k+2]; }
    vx[3]=vx[nrv-1]; vy[3]=vy[nrv-1]; vz[3]=vz[nrv-1];
    apply_camera();
    flares  = (char)geti("flares",0);
    entity  = (unsigned char)geti("entity",1);
    reset_counters();
    if ((int)geti("draw",0)) setup_page();
    if (!strcmp(which,"polymap")) polymap_project(vx,vy,vz,nrv,&T);
    else poly3d(vx,vy,vz,(unsigned)nrv,(unsigned char)geti("colore",1),&T,(int)geti("draw",0));
    emit_topo(tk_id,&T);
    if (T.nmp > 0) emit_mp(tk_id, T.mp, T.nmp);
    if (T.basis_valid) {
        uint32_t b[9]; int j;
        for (j=0;j<9;j++) memcpy(&b[j], &T.basis[j], 4);
        printf("K29 BASIS %s hx=%08x vx=%08x ox=%08x hy=%08x vy=%08x oy=%08x hz=%08x vz=%08x oz=%08x\n",
               tk_id, b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[8]);
    }
    if ((int)geti("draw",0)) emit_page(tk_id);
}

static void case_ROWUV(void)
{
    float vx[16],vy[16],vz[16],tmp[64];
    int nrv=(int)getir("nrv"), k, got;
    TOPO T; int32_t u,v; float z,k4; uint32_t bz,bk;
    got = parse_f32list(getv("v",NULL), tmp, 48);
    if (got != 3*nrv) { fprintf(stderr,"pg_ref: %s v has %d values\n", tk_id, got); exit(2); }
    for (k=0;k<nrv;k++) { vx[k]=tmp[3*k]; vy[k]=tmp[3*k+1]; vz[k]=tmp[3*k+2]; }
    vx[3]=vx[nrv-1]; vy[3]=vy[nrv-1]; vz[3]=vz[nrv-1];
    apply_camera();
    reset_counters();
    polymap_project(vx,vy,vz,nrv,&T);
    if (!T.basis_valid) { printf("K2A ROWUV %s NOBASIS ret=%d\n", tk_id, T.ret); return; }
    polymap_rowuv(T.basis, (int)getir("i"), (int)getir("ipart"), &u,&v,&z,&k4);
    memcpy(&bz,&z,4); memcpy(&bk,&k4,4);
    printf("K2A ROWUV %s u=%ld v=%ld z=%08x k4=%08x\n", tk_id, (long)u,(long)v,bz,bk);
}

static void case_GETC(void)
{
    float p[4]; int r;
    if (parse_f32list(getv("p",NULL), p, 3) != 3) { fprintf(stderr,"pg_ref: %s bad p\n", tk_id); exit(2); }
    apply_camera();
    r = getcoords(p[0],p[1],p[2]);
    printf("K27 GETC %s ret=%d x=%ld y=%ld\n", tk_id, r, (long)gc_x, (long)gc_y);
}

static void case_FACING(void)
{
    float vx[8],vy[8],vz[8],tmp[32]; int k, got = parse_f32list(getv("v",NULL), tmp, 24);
    if (got != 9) { fprintf(stderr,"pg_ref: %s FACING needs 3 vertices\n", tk_id); exit(2); }
    for (k=0;k<3;k++) { vx[k]=tmp[3*k]; vy[k]=tmp[3*k+1]; vz[k]=tmp[3*k+2]; }
    apply_camera();
    printf("K2D FACING %s ret=%d\n", tk_id, facing(vx,vy,vz));
}

/* --------------------------------------------------------------- driver    */

static void run_file(const char *path)
{
    FILE *f = fopen(path, "r");
    char line[8192];
    if (!f) { fprintf(stderr,"pg_ref: cannot open %s\n", path); exit(2); }
    printf("# corpus %s\n", path);
    while (fgets(line,sizeof line,f)) {
        if (!split_line(line)) continue;
        if      (!strcmp(tk_dir,"SEG"))    case_SEG();
        else if (!strcmp(tk_dir,"BBOX"))   case_BBOX();
        else if (!strcmp(tk_dir,"FILL"))   case_FILL();
        else if (!strcmp(tk_dir,"EDGE"))   case_EDGE();
        else if (!strcmp(tk_dir,"SPAN"))   case_SPAN();
        else if (!strcmp(tk_dir,"PROJ"))   case_PROJ();
        else if (!strcmp(tk_dir,"ROWUV"))  case_ROWUV();
        else if (!strcmp(tk_dir,"GETC"))   case_GETC();
        else if (!strcmp(tk_dir,"FACING")) case_FACING();
        else { fprintf(stderr,"pg_ref: unknown directive '%s'\n", tk_dir); exit(2); }
    }
    fclose(f);
}

int main(int argc, char **argv)
{
    int i, nfiles = 0;
    const char *accs="ext", *fsts="dual", *rnds="near";

    initscanlines();
    dpp = 210.0f;                 /* NOCTIS.CPP:2214 followed by change_camera_lens */
    change_camera_lens();

    for (i=1;i<argc;i++) {
        if (!strncmp(argv[i],"--acc=",6)) {
            accs = argv[i]+6;
            if (!strcmp(accs,"ext")) ACC=ACC_EXT;
            else if (!strcmp(accs,"f64")) ACC=ACC_F64;
            else if (!strcmp(accs,"f32")) ACC=ACC_F32;
            else { fprintf(stderr,"pg_ref: bad --acc\n"); return 2; }
        } else if (!strncmp(argv[i],"--fst=",6)) {
            fsts = argv[i]+6;
            if (!strcmp(fsts,"dual")) FSTM=FST_DUAL;
            else if (!strcmp(fsts,"allwide")) FSTM=FST_ALLWIDE;
            else if (!strcmp(fsts,"allnarrow")) FSTM=FST_ALLNARROW;
            else { fprintf(stderr,"pg_ref: bad --fst\n"); return 2; }
        } else if (!strncmp(argv[i],"--round=",8)) {
            rnds = argv[i]+8;
            if (!strcmp(rnds,"near")) RNDM=RND_NEAR;
            else if (!strcmp(rnds,"chop")) RNDM=RND_CHOP;
            else { fprintf(stderr,"pg_ref: bad --round\n"); return 2; }
        } else if (!strncmp(argv[i],"--pages=",8)) {
            pagefp = fopen(argv[i]+8,"wb");
            if (!pagefp) { fprintf(stderr,"pg_ref: cannot write pages\n"); return 2; }
        } else if (argv[i][0]=='-') {
            fprintf(stderr,"pg_ref: unknown flag %s\n", argv[i]); return 2;
        } else nfiles++;
    }
    if (!nfiles) {
        fprintf(stderr,
          "usage: pg_ref [--acc=ext|f64|f32] [--fst=dual|allwide|allnarrow]\n"
          "              [--round=near|chop] [--pages=FILE] corpus...\n");
        return 2;
    }
    printf("# pg_ref build=%s acc=%s fst=%s round=%s ldbl_mant=%d\n",
           PGBREAK, accs, fsts, rnds, LDBL_MANT_DIG);
    printf("# geom larghezza=%d x_centro=%d lbx=%d ubx=%d lby=%d uby=%d dpp=%.10g uneg=%.10g\n",
           LARGHEZZA, X_CENTRO, LBX, UBX, LBY, UBY, (double)dpp, (double)uneg);
    for (i=1;i<argc;i++) if (argv[i][0] != '-') run_file(argv[i]);
    if (pagefp) fclose(pagefp);
    return 0;
}
