/* ===========================================================================
   sp_ref.c -- Wave 6b, producer P2: the C oracle.

   DERIVED FROM: C:\programmieren\noctis\niv-plus\source\NOCTIS-0.CPP, the
     INLINE ASSEMBLY, instruction by instruction:
        background()          :2697   asm body :2704-2748
        gman1x1..gman4x4      :3021-3041
        globe()               :3043   asm body :3100-3170
        glowinglobe()         :3173   asm body :3230-3296
        whiteglobe()          :3298
        whitesun()            :3535
        smootharound_64()     :607
        loadpv()              :2303
        QuickSort()           :2421
        drawpv()              :2461
        copypv()              :2574
        modpv()               :2593
        the day/night band    :5109-5124
     plus NOCTIS-D.H (x_centro 158, y_centro 100, the buffer sizes, struct
     pvlist) and TDPOLYGS.H:130-137 (riga[200] = 320*c).

   NOT derived from: work/sp*.txt (implementer 1's lino) -- not opened;
     noctis-harness/sp_spec.py (implementer 2's OTHER producer, which reads
     the asset bytes, not the assembly) -- the two are written to disagree if
     either is wrong; C:\programmieren\noctis\niv-lr (the de-assembled C++),
     which is a KNOWN WRONG ANSWER on glowinglobe's Y clip (it has an AND
     where vanilla has an OR) and on background's source offset.

   Register widths are explicit.  Every effective address in the original is
   16 bits and wraps inside its segment, so the page model here is a
   65,536-byte SEGMENT with the framebuffer at offsets 4..64003 -- farmalloc
   returns offset 4 (BUFFERMAP.md 4.1) and the literal `es:[di+4]` in the
   fill managers IS that offset.  There is no second +4 to add anywhere.

   Build:   gcc -O2 -std=c11 -o sp_ref.exe sp_ref.c
   Break:   gcc -O2 -std=c11 -DBREAK_GLOWCLAMP -o sp_brk.exe sp_ref.c
   =========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <float.h>

#if LDBL_MANT_DIG != 64
#error "sp_ref.c requires an 80-bit long double (LDBL_MANT_DIG==64)"
#endif

typedef unsigned char  u8;
typedef unsigned short u16;
typedef short          i16;
typedef uint32_t       u32;
typedef int32_t        i32;
typedef long double    R;

/* ------------------------------------------------------------- schedule -- */

enum { CAST_CHOP = 0, CAST_NEAR = 1 };
enum { SRC_EXT = 0, SRC_F64 = 1 };
enum { SCALE_X87 = 0, SCALE_F32 = 1, SCALE_DBL = 2 };

static int  CASTM   = CAST_CHOP;   /* __ftol: chop, settled from NOCTIS.EXE  */
static int  CASTSRC = SRC_EXT;     /* on the LIVE 80-bit st(0), not a stored double */
static int  SCALEM  = SCALE_X87;   /* fild/fmul/fistp on real hardware x87   */
static int  NOZERO  = 0;           /* skip loadpv's slot-3 zeroing pass      */
static const char *DGFILL = "zeros";

/* --------------------------------------------------- x87 primitives ----- */
/*
   FLOATPOLICY.md 3.3, settled from NOCTIS.EXE file 14437: Borland's __ftol
   ORs 0Ch into the control word (RC <- chop), does `fistp qword`, and puts
   the caller's word back.  It takes no parameter -- every frame access in
   its body is a negative displacement from BP -- so its input can only be
   st(0), which is still live at 80 bits.  A C cast to `int` then keeps the
   low 16 bits of that 64-bit result.
*/
static i32 ftol32(R v)
{
    R r;
    if (CASTSRC == SRC_F64) v = (R)(double)v;
    if (isnan((double)v)) return (i32)0x80000000;
    if (CASTM == CAST_NEAR) {
        R f = floorl(v), d = v - floorl(v);
        r = (d > 0.5L) ? f + 1 : (d < 0.5L) ? f
            : (fmodl(f, 2.0L) == 0.0L ? f : f + 1);
    } else {
        r = truncl(v);
    }
    if (!(r >= -9.2e18L && r <= 9.2e18L)) return (i32)0x80000000;
    return (i32)(int64_t)r;
}
static i16 ftol16(R v) { return (i16)(ftol32(v) & 0xFFFF); }

/*
   The sphere pixel loop's ENTIRE float content, per component:
        fild  word ptr temp        ; sign-extended map byte, int16
        fmul  dword ptr mag_factor ; float32
        fistp word ptr temp        ; CW 133Fh -> round half to EVEN
   dy is 8 bits with sign and dx is 9 bits with sign; mag_factor has a 24-bit
   significand; the exact product needs at most 33 significand bits, which is
   representable at PC=64.  The FMUL therefore rounds NOTHING and the single
   rounding in the chain is the FISTP -- so the result is a pure INTEGER
   function of (dy:int16, mag_factor:uint32).  This routine runs the real
   instructions at the real control word; sp_spec.py computes the same number
   with pure integer arithmetic and no float multiply at all; EX1 enumerates
   the two against each other including the adversarial ties.

   --scalemul=f32 and =dbl exist so a control implementation that looks right
   and is wrong can be shown to fail.
*/
static i16 x87_scale(i16 v, u32 magbits)
{
    float m;
    i16 t = v, out = 0;
    unsigned short cw = 0x133F, old = 0;
    memcpy(&m, &magbits, 4);
    if (SCALEM == SCALE_F32) {
        float p = (float)v * m;                 /* double rounding: WRONG    */
        return (i16)lrintf(p);
    }
    if (SCALEM == SCALE_DBL) {
        double p = (double)v * (double)m;
        return (i16)llrint(p);
    }
    __asm__ __volatile__(
        "fnstcw %1\n\t"
        "fldcw  %3\n\t"
        "filds  %2\n\t"
        "fmuls  %4\n\t"
        "fistps %0\n\t"
        "fldcw  %1\n\t"
        : "=m"(out), "=m"(old)
        : "m"(t), "m"(cw), "m"(m)
        : "memory", "st");
    (void)old;
    return out;
}

/* --------------------------------------------------------------- sha256 - */

typedef struct { u32 s[8]; uint64_t n; u8 b[64]; size_t bl; } SHA;
static const u32 K256[64] = {
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
#define ROR(x,n) (((x)>>(n))|((x)<<(32-(n))))
static void sha_block(SHA *c, const u8 *p){
    u32 w[64],a,b,cc,d,e,f,g,h,t1,t2; int i;
    for(i=0;i<16;i++) w[i]=((u32)p[i*4]<<24)|((u32)p[i*4+1]<<16)|((u32)p[i*4+2]<<8)|p[i*4+3];
    for(i=16;i<64;i++){u32 s0=ROR(w[i-15],7)^ROR(w[i-15],18)^(w[i-15]>>3);
        u32 s1=ROR(w[i-2],17)^ROR(w[i-2],19)^(w[i-2]>>10); w[i]=w[i-16]+s0+w[i-7]+s1;}
    a=c->s[0];b=c->s[1];cc=c->s[2];d=c->s[3];e=c->s[4];f=c->s[5];g=c->s[6];h=c->s[7];
    for(i=0;i<64;i++){t1=h+(ROR(e,6)^ROR(e,11)^ROR(e,25))+((e&f)^((~e)&g))+K256[i]+w[i];
        t2=(ROR(a,2)^ROR(a,13)^ROR(a,22))+((a&b)^(a&cc)^(b&cc));
        h=g;g=f;f=e;e=d+t1;d=cc;cc=b;b=a;a=t1+t2;}
    c->s[0]+=a;c->s[1]+=b;c->s[2]+=cc;c->s[3]+=d;c->s[4]+=e;c->s[5]+=f;c->s[6]+=g;c->s[7]+=h;}
static void sha_init(SHA*c){c->s[0]=0x6a09e667;c->s[1]=0xbb67ae85;c->s[2]=0x3c6ef372;
    c->s[3]=0xa54ff53a;c->s[4]=0x510e527f;c->s[5]=0x9b05688c;c->s[6]=0x1f83d9ab;
    c->s[7]=0x5be0cd19;c->n=0;c->bl=0;}
static void sha_up(SHA*c,const u8*p,size_t n){c->n+=n;
    while(n){size_t k=64-c->bl; if(k>n)k=n; memcpy(c->b+c->bl,p,k); c->bl+=k;p+=k;n-=k;
        if(c->bl==64){sha_block(c,c->b);c->bl=0;}}}
static void sha_fin(SHA*c,char*out){u8 pad[72];size_t i;uint64_t bits=c->n*8;
    size_t padlen=(c->bl<56)?(56-c->bl):(120-c->bl);
    memset(pad,0,sizeof pad);pad[0]=0x80;sha_up(c,pad,padlen);
    {u8 L[8];for(i=0;i<8;i++)L[i]=(u8)(bits>>(56-8*i));sha_up(c,L,8);}
    for(i=0;i<8;i++)sprintf(out+i*8,"%08x",c->s[i]);out[64]=0;}
static void sha_hex(const u8*p,size_t n,char*out){SHA c;sha_init(&c);sha_up(&c,p,n);sha_fin(&c,out);}

/* --------------------------------------------------------- the machine -- */

#define OFF4      4            /* farmalloc's offset -- BUFFERMAP.md 4.1     */
#define X_CENTRO  158          /* NOCTIS-D.H:126, included BEFORE tdpolygs.h */
#define Y_CENTRO  100          /* NOCTIS-D.H:127                             */
#define RIGA_OFF  0x435C       /* NOCTIS.EXE 54124/54931 mov di,gs:[di+435Ch]*/
#define SENT      100

static u8 dgroup[65536];       /* riga[] lives here; everything else is a
                                  DECLARED filler and the values read through
                                  it are NOT GRADED -- see the OOB census.   */

static void dgroup_build(void)
{
    int c; u32 s = 0x6B;
    if (!strcmp(DGFILL, "ff")) memset(dgroup, 0xFF, sizeof dgroup);
    else if (!strncmp(DGFILL, "prng:", 5)) {
        s = (u32)strtoul(DGFILL + 5, NULL, 0);
        for (c = 0; c < 65536; c++) { s = s * 1103515245u + 12345u; dgroup[c] = (u8)(s >> 16); }
    } else memset(dgroup, 0, sizeof dgroup);
    for (c = 0; c < 200; c++) {
        u16 v = (u16)(320 * c);
        dgroup[(RIGA_OFF + 2 * c) & 0xFFFF]     = (u8)(v & 0xFF);
        dgroup[(RIGA_OFF + 2 * c + 1) & 0xFFFF] = (u8)(v >> 8);
    }
}
static u16 riga_word(u16 di)                  /* mov di, gs:[di + 435Ch]     */
{
    u16 a = (u16)(di + RIGA_OFF);
    return (u16)(dgroup[a] | (dgroup[(u16)(a + 1)] << 8));
}
static int riga_in_range(u16 di) { return di <= 398 && (di % 2) == 0; }

typedef struct { u8 b[65536]; } SEG;
static void seg_clear(SEG *s, u8 v) { memset(s->b, v, sizeof s->b); }
static void seg_w8(SEG *s, u32 a, u8 v) { s->b[a & 0xFFFF] = v; }
static u8   seg_r8(const SEG *s, u32 a) { return s->b[a & 0xFFFF]; }

/* --------------------------------------------------- the fill managers -- */
/* NOCTIS-0.CPP:3021-3041.  gman2x2 stores DX (dh=dl) so it writes TWO bytes
   per row; gman3x3 adds a third with a byte store; gman4x4 stores DX twice.  */

static void gman(SEG *sg, int which, u16 di, u8 dl)
{
    switch (which) {
    case 1: seg_w8(sg, di + 4, dl); break;
    case 2: seg_w8(sg, di + 4, dl);   seg_w8(sg, di + 5, dl);
            seg_w8(sg, di + 324, dl); seg_w8(sg, di + 325, dl); break;
    case 3: seg_w8(sg, di + 4, dl);   seg_w8(sg, di + 5, dl);   seg_w8(sg, di + 6, dl);
            seg_w8(sg, di + 324, dl); seg_w8(sg, di + 325, dl); seg_w8(sg, di + 326, dl);
            seg_w8(sg, di + 644, dl); seg_w8(sg, di + 645, dl); seg_w8(sg, di + 646, dl);
            break;
    case 4: seg_w8(sg, di + 4, dl);   seg_w8(sg, di + 5, dl);
            seg_w8(sg, di + 6, dl);   seg_w8(sg, di + 7, dl);
            seg_w8(sg, di + 324, dl); seg_w8(sg, di + 325, dl);
            seg_w8(sg, di + 326, dl); seg_w8(sg, di + 327, dl);
            seg_w8(sg, di + 644, dl); seg_w8(sg, di + 645, dl);
            seg_w8(sg, di + 646, dl); seg_w8(sg, di + 647, dl);
#ifdef BREAK_GMAN4
            seg_w8(sg, di + 960, dl); seg_w8(sg, di + 961, dl);   /* dropped +4 */
            seg_w8(sg, di + 962, dl); seg_w8(sg, di + 963, dl);
#else
            seg_w8(sg, di + 964, dl); seg_w8(sg, di + 965, dl);
            seg_w8(sg, di + 966, dl); seg_w8(sg, di + 967, dl);
#endif
            break;
    }
}

/* ----------------------------------------------------------- globe() ---- */

typedef struct {
    u16 cursor; long drawn;
    long rej_ylo, rej_yhi, rej_xlo, rej_xhi;
    long tap_min, tap_max;
} GLOBERES;

static void globe_raster(SEG *sg, const u8 *tab, u16 total_map_bytes,
                         const u8 *tap, size_t taplen, u16 start, u32 magbits,
                         i16 center_x, i16 center_y, int which,
                         u8 colormask, u8 saturation, GLOBERES *out)
{
    u16 cx = (u16)(total_map_bytes >> 1);
    u16 bx = (u16)(start + OFF4);          /* les ax,tapestry / add start,ax */
    size_t si = 0;
    memset(out, 0, sizeof *out);
    out->tap_min = -1; out->tap_max = -1;
    while (cx) {
        if (tab[si] == SENT) {                       /* cmp byte [si],100    */
            u16 ax = tab[si + 1];                    /* xor ah,ah : UNSIGNED */
            bx = (u16)(bx + ax);
            si += 2; cx--;
            continue;
        }
        {
            i16 t = (i16)(signed char)tab[si];       /* mov al,[si] / cbw    */
            u16 di = (u16)(x87_scale(t, magbits) + center_y);
#ifdef BREAK_GLOBEOFF1
            if (di < 7) { out->rej_ylo++; goto clipout; }        /* LR's 7   */
#else
            if (di < 6) { out->rej_ylo++; goto clipout; }
#endif
            if (di >= 191) { out->rej_yhi++; goto clipout; }
            {
                i16 tx = (i16)(signed char)tab[si + 1];
                u16 d2 = (u16)(di + di);              /* add di,di BEFORE cbw */
                u16 d3 = riga_word(d2);
                u16 ax = (u16)(x87_scale(tx, magbits) + center_x);
                u8 dl, tex;
                if (ax < 6)    { out->rej_xlo++; goto clipout; }
                if (ax >= 311) { out->rej_xhi++; goto clipout; }
                d3 = (u16)(d3 + ax);
                tex = (bx < taplen) ? tap[bx] : 0;    /* mov dl, fs:[bx]      */
                if (out->tap_min < 0 || bx < out->tap_min) out->tap_min = bx;
                if (bx > out->tap_max) out->tap_max = bx;
                dl = tex;
                if (dl < saturation) dl = saturation; /* UNSIGNED jnb         */
                dl = (u8)(dl | colormask);            /* OR *after* the clamp */
                gman(sg, which, d3, dl);
                out->drawn++;
            }
        }
    clipout:
#ifdef BREAK_CURSORCLIP
        /* the defect: only DRAWN records advance the tapestry cursor.  The
           original advances on clipped records too -- `clipout: add bx,1` is
           inside the clip path, not after the store.                        */
        if (out->drawn) bx = (u16)(bx + 1);
#else
        bx = (u16)(bx + 1);                           /* clipout: add bx,1    */
#endif
        si += 2; cx--;
    }
    out->cursor = bx;
}

/* ------------------------------------------------------ glowinglobe() -- */

typedef struct {
    u16 counter_end; long drawn, decimated;
    long rej_y, rej_xlo, rej_xhi;
    long oob_n; long oob_min, oob_max;
    u8 light, dark;
    long oob_writes;
} GLOWRES;

static void glow_raster(SEG *sg, const u8 *tab, u16 total_map_bytes,
                        int start_in, int tstart, int arc, u32 magbits,
                        u16 center_x, u16 center_y, u8 color,
                        GLOWRES *out, FILE *oobf, const char *cid)
{
    u16 cx = (u16)(total_map_bytes >> 1);
    u8 bl = color;
    u8 bh = (u8)(((color & 0x3F) >> 2) | (color & 0xC0));
    int start = start_in - tstart;
    u16 dx;
    size_t si = 0;
    while (start < 0) start += 360;
    dx = (u16)start;
    memset(out, 0, sizeof *out);
    out->oob_min = -1; out->oob_max = -1;
    out->light = bl; out->dark = bh;
    while (cx) {
        if (tab[si] == SENT) {
            u16 ax = tab[si + 1];                     /* xor ah,ah            */
            dx = (u16)(dx + ax);
            while (dx >= 360) dx -= 360;              /* repeated SUB, not %  */
            si += 2; cx--;
            continue;
        }
        if (dx & 3) { out->decimated++; goto clipout; }   /* test dx,3 / jz   */
        {
            i16 t = (i16)(signed char)tab[si];
            u16 di = (u16)(x87_scale(t, magbits) + center_y);
            /* NOCTIS.EXE 54912:  83 FF 0A  cmp di,10
                                  73 08     jnb -> 54925 (y_ok)
                                  81 FF BE 00 cmp di,190
                                  72 02     jb  -> 54925 (y_ok)
                                  EB 38     jmp -> 54981 (clipout)  UNREACHABLE
               (di >= 10) OR (di < 190) is true for EVERY 16-bit di.  The clip
               never fires.  Reproduced as written.                          */
#ifdef BREAK_GLOWCLAMP
            if (!(di > 10 && di < 190)) { out->rej_y++; goto clipout; } /* LR */
#else
            if (!(di >= 10 || di < 190)) { out->rej_y++; goto clipout; }
#endif
            {
                i16 tx = (i16)(signed char)tab[si + 1];
                u16 d2 = (u16)(di + di);
                u16 d3, ax;
                if (!riga_in_range(d2)) {
                    out->oob_n++;
                    if (out->oob_min < 0 || d2 < out->oob_min) out->oob_min = d2;
                    if (d2 > out->oob_max) out->oob_max = d2;
                    if (oobf) fprintf(oobf, "OOB %s %u\n", cid, (unsigned)d2);
                }
                d3 = riga_word(d2);
                ax = (u16)(x87_scale(tx, magbits) + center_x);
                if (ax < 9)    { out->rej_xlo++; goto clipout; }
                if (ax >= 310) { out->rej_xhi++; goto clipout; }
                d3 = (u16)(d3 + ax);
                seg_w8(sg, (u16)(d3 + 4), (dx < (u16)arc) ? bh : bl);
                if (!riga_in_range(d2)) out->oob_writes++;
                out->drawn++;
            }
        }
    clipout:
        dx = (u16)(dx + 1);
        if (dx >= 360) dx = 0;
        si += 2; cx--;
    }
    out->counter_end = dx;
}

/* ------------------------------------------------------- background() -- */

typedef struct { u16 src_cursor; long paints, skips, wrapped; long smin, smax;
                 long boundary; char dihash[65]; } BGRES;

static void background_raster(SEG *sg, const u8 *offs, u16 total_map_bytes,
                              const u8 *src, size_t srclen,
                              u16 start, u16 screenshift, BGRES *out,
                              FILE *bo, const char *cid)
{
    /* les ax,target / add screenshift,ax / mov dx,screenshift
       -> offset(target)==4 is folded into DX.  Every store is a bare
          es:[di+k]; there is NO second +4.
       mov bp,start / add bp,4  with FS = segment(background)
       -> the literal 4 is offset(background), which `mov bx,es` discarded.  */
    u16 dx = (u16)(screenshift + OFF4);
#ifdef BREAK_BGPLUS4
    u16 bp = (u16)(start);                    /* LR's dropped source +4      */
#else
    u16 bp = (u16)(start + 4);
#endif
    u16 cx = (u16)(total_map_bytes >> 1);
    size_t si = 0;
    SHA dish;
    memset(out, 0, sizeof *out);
    out->smin = -1; out->smax = -1;
    sha_init(&dish);
    while (cx) {
        u16 w = (u16)(offs[si] | (offs[si + 1] << 8));
        if (w >= 64000) {                             /* cmp word [si],64000 */
            u16 bxs = (u16)(w - 64000);
            bp = (u16)(bp + bxs);
            out->skips++;
        } else {
            u32 raw = (u32)w + (u32)dx;
#ifdef BREAK_BGMASKOFF
            u32 di = raw;                             /* no mask at all      */
#elif defined(BREAK_BGMASK)
            u32 di = ((raw - OFF4) & 0xFFFF) + OFF4;  /* masked at the BUFFER
                                                         base, not the segment */
#else
            u16 di = (u16)raw;                        /* class-A 16-bit mask,
                                                         at the SEGMENT origin */
#endif
            u8 al = (bp < srclen) ? src[bp] : 0;
            int row, col;
            u8 dib[2];
            /* E-BG-MASK.  The destination index for EVERY paint word, as a
               sequence, plus the boundary hits called out by name.  A port
               that masks at the BUFFER BASE instead of the SEGMENT ORIGIN
               produces di + 65536 for exactly the words where
               (w + screenshift) mod 65536 is in {65532..65535}; a port with
               no mask at all lands 65,536 units past the page on almost
               every paint at the nominal screenshift.  Neither defect is
               expressible in THIS oracle -- it is a faithful 16-bit machine
               and every effective address wraps by construction -- so the
               INDEX SEQUENCE is what the lino side is graded against, and
               this is where it comes from.                                 */
            dib[0] = (u8)((di & 0xFFFF) & 0xFF);
            dib[1] = (u8)(((di & 0xFFFF) >> 8) & 0xFF);
            sha_up(&dish, dib, 2);
            if (((u32)w + (u32)screenshift) % 65536u >= 65532u) {
                out->boundary++;
                if (bo) fprintf(bo, "BGB %s %u %u\n", cid, (unsigned)w,
                                (unsigned)(di & 0xFFFF));
            }
            if (raw >= 65536) out->wrapped++;
            if (out->smin < 0 || bp < out->smin) out->smin = bp;
            if (bp > out->smax) out->smax = bp;
            for (row = 0; row <= 1280; row += 320)
                for (col = 0; col < 5; col++)
                    seg_w8(sg, (u32)di + row + col, al);
            bp = (u16)(bp + 1);
            out->paints++;
        }
        si += 2; cx--;
    }
    sha_fin(&dish, out->dihash);
    out->src_cursor = bp;
}

/* ------------------------------------- surface()'s day/night band ------- */
/* NOCTIS-0.CPP:5109-5124.  Lighting is BAKED INTO THE TEXTURE: a 130-degree
   longitude band starting plwp+35 UNREDUCED, shifted right by 2, across 179
   of the 180 rows, stride 360.  There is no N-dot-L anywhere.               */

static void surface_band(SEG *sg, int plwp, long *first, long *last)
{
    u16 di = (u16)(OFF4 + plwp + 35);
    int r, c;
#ifdef BREAK_DARKROWS
    int rows = 180;
#else
    int rows = 179;
#endif
    *first = di; *last = di;
    for (r = 0; r < rows; r++) {
        for (c = 0; c < 130; c++) {
#ifdef BREAK_DARKSHIFT
            sg->b[di] = (u8)(sg->b[di] >> 1);
#else
            sg->b[di] = (u8)(sg->b[di] >> 2);
#endif
            if (di > *last) *last = di;
            di = (u16)(di + 1);
        }
        di = (u16)(di + 230);
    }
}

/* -------------------------------------- the shared projection preamble -- */
/*
   globe/glowinglobe/whiteglobe/whitesun all open with the SAME five lines,
   and they are character for character project3d's rotation nucleus
   (TDPOLYGS.H).  So globe's centre IS project3d's projection of the body
   centre and shares dpp -- while the GLOBES.MAP table's focal length is a
   baked asset constant that must NOT be derived from dpp.  X1 pins that
   split; X2 measures the disagreement (isotropic 210 scores 181/10,780).
   The four functions differ only in what they do at the end:
     project3d   fistp            (round half even)
     globe       (int) cast       (__ftol chop, on the LIVE extended value)
     glowinglobe (unsigned) cast  (ditto)
     whiteglobe  + 0.5, no cast   (stays a double)
   Three different roundings across four functions, each one a falsifier.
*/
typedef struct {
    int   rejected;
    double rx, ry, rz;
    u32   mag_out;
    int   gman;
    i16   cx_i, cy_i;
    double cx_d, cy_d;
    double xsun;
    int   xsun_written;
} PRERES;

typedef struct {
    double dzx, dzy, dzz;
    float pcosbeta, psinbeta, tcosbeta, tsinbeta;
    float tcosalfa, tsinalfa, pcosalfa, psinalfa;
} CAM2;

static void preamble2(const CAM2 *c, double x, double y, double z, u32 magbits,
                      int variant, PRERES *o)
{
    R xx = (R)x - (R)c->dzx, yy = (R)y - (R)c->dzy, zz = (R)z - (R)c->dzz;
    R rx, ry, rz, z2;
    float mf;
    memset(o, 0, sizeof *o);
    o->gman = 1;
    memcpy(&mf, &magbits, 4);
    /* the source writes `xx * (double)opt_pcosbeta`: an explicit widening of
       a float32 table entry, so each product is float32-widened * double.   */
    rx = xx * (R)(double)c->pcosbeta + zz * (R)(double)c->psinbeta;
    z2 = zz * (R)(double)c->tcosbeta - xx * (R)(double)c->tsinbeta;
    rz = z2 * (R)(double)c->tcosalfa + yy * (R)(double)c->tsinalfa;
    ry = yy * (R)(double)c->pcosalfa - z2 * (R)(double)c->psinalfa;
    rx = (R)(double)rx; ry = (R)(double)ry; rz = (R)(double)rz;
    o->rz = (double)rz;
    if (rz < 0.001L) { o->rejected = 1; return; }
    mf = (float)(mf / (float)(double)rz);          /* float /= double        */
    if (variant == 0) {                             /* globe                  */
        o->gman = 1;
        if (mf < 0.01f) mf = 0.001f;
        if (mf > 0.33f) o->gman = 2;
        if (mf > 0.66f) o->gman = 3;
        if (mf > 0.99f) o->gman = 4;
        if (mf > 1.32f) mf = 1.32f;
    } else if (variant == 1) {                      /* glowinglobe            */
        if (mf > 0.66f) mf = 0.66f;                 /* 0.66 FIRST ...         */
        if (mf < 0.01f) mf = 0.001f;                /* ... then 0.001         */
    } else {                                        /* whiteglobe / whitesun  */
        if (mf > 2.99f) mf = 2.99f;
        if (mf < 0.01f) mf = 0.01f;
    }
    memcpy(&o->mag_out, &mf, 4);
    rx = (R)(double)(rx / rz);
    ry = (R)(double)(ry / rz);
    o->rx = (double)rx; o->ry = (double)ry;
    if (variant == 3) {                             /* whitesun writes this   */
        o->xsun = (double)(rx + (R)(float)X_CENTRO);/* BEFORE the reject tests*/
        o->xsun_written = 1;
    }
    if (variant == 0) {
        if (rx < -292 || rx > 292) { o->rejected = 1; return; }
        if (ry < -232 || ry > 232) { o->rejected = 1; return; }
    } else if (variant == 1) {
        if (rx < -226 || rx > 226) { o->rejected = 1; return; }
        if (ry < -166 || ry > 166) { o->rejected = 1; return; }
    } else {
        if (rx < -460 || rx > 460) { o->rejected = 1; return; }
        if (ry < -400 || ry > 400) { o->rejected = 1; return; }
    }
    if (variant <= 1) {
        o->cx_i = ftol16(rx + (R)(float)X_CENTRO);  /* __ftol: CHOP on the
                                                       LIVE extended value   */
        o->cy_i = ftol16(ry + (R)(float)Y_CENTRO);
        o->cx_d = o->cx_i; o->cy_d = o->cy_i;
    } else {
        o->cx_d = (double)(rx + (R)(float)X_CENTRO + 0.5L);  /* NO cast      */
        o->cy_d = (double)(ry + (R)(float)Y_CENTRO + 0.5L);
        o->cx_i = (i16)o->cx_d; o->cy_i = (i16)o->cy_d;
    }
}

/* --------------------------------------------- whiteglobe / whitesun ---- */
/*
   One body, three parameterised differences:
     step   whiteglobe 2 / 2.4     whitesun 1 / 1.2
     store  whiteglobe 2x2 via FS  whitesun 1x1 via target[]
     xsun   whiteglobe none        whitesun writes xsun_onscreen BEFORE the
                                   rx/ry reject tests (handled in preamble2)
   `char pix` is SIGNED and the destination is added into it BEFORE the
   compare, so a destination above 0x3F wraps: 63 + 200 -> (char)7, stored.
*/
static long white_body(SEG *sg, double center_x, double center_y,
                       float mag_factor, float fgm_factor, int sun,
                       long *clipped_out)
{
    R mag = (R)(double)((R)mag_factor * 100 + 1.5L);
    R fgm = (R)(double)((R)fgm_factor * mag);
    R shade = (R)(double)(mag - fgm);
    R ise, magsq, fgmsq, xa, ya, xb, yb, xx, yy, zz;
    R xstep = sun ? 1.0L : 2.0L, ystep = sun ? 1.0L : 2.0L;
    R yastep = sun ? 1.2L : 2.4L;
    long writes = 0, clipped = 0;
    if (shade < 1) shade = 1;
    ise = (R)(double)((R)0x3F / shade);
    magsq = (R)(double)(mag * mag);
    fgmsq = (R)(double)(fgm * fgm);
    ya = (R)(double)(-mag * 1.2L);
    yb = (R)(double)((R)center_y + mag);
    yy = (R)(double)((R)center_y - mag);
    while (yy < yb) {
        xa = (R)(double)(-mag);
        xb = (R)(double)((R)center_x + mag);
        xx = (R)(double)((R)center_x - mag);
        while (xx < xb) {
            if (xx > 9 && xx < 313 && yy > 9 && yy < 190) {
                zz = (R)(double)(xa * xa + ya * ya);
                if (zz < magsq) {
                    R pf;
                    int pix; u16 ptr; u8 dst; int v;
                    if (zz > fgmsq) pf = (R)0x3F - (sqrtl(zz) - fgm) * ise;
                    else            pf = (R)0x3F;
                    pix = (int)(signed char)(ftol32(pf) & 0xFF);
                    ptr = (u16)(riga_word((u16)(2 * (u16)ftol16(yy)))
                                + (u16)ftol16(xx));
                    dst = seg_r8(sg, (u32)ptr + OFF4);
                    v = (int)(signed char)((pix + dst) & 0xFF);
                    if (v > 0x3F) v = 0x3F;
                    seg_w8(sg, (u32)ptr + OFF4, (u8)v);
                    if (!sun) {
                        seg_w8(sg, (u32)ptr + OFF4 + 1, (u8)v);
                        seg_w8(sg, (u32)ptr + OFF4 + 320, (u8)v);
                        seg_w8(sg, (u32)ptr + OFF4 + 321, (u8)v);
                    }
                    writes++;
                }
            } else clipped++;
            xa = (R)(double)(xa + xstep);
            xx = (R)(double)(xx + xstep);
        }
        ya = (R)(double)(ya + yastep);
        yy = (R)(double)(yy + ystep);
    }
    *clipped_out = clipped;
    return writes;
}

/* ------------------------------------------------------ QuickSort ------- */
/* NOCTIS-0.CPP:2421-2447 verbatim.  Hoare partition, MID-ELEMENT pivot, `>`
   and `<` so it sorts DESCENDING, recursion (start,jq) then (iq,end).  It is
   not stable and it is not qsort(): pv_dep_i is PERSISTENT STATE and every
   frame permutes the previous frame's array.                               */

static int  *QS_IDX;
static float *QS_D;
static FILE *QS_LOG;
static const char *QS_CID;
static void quicksort(int start, int end)
{
    int tq, jq = end, iq = start;
    float xq = QS_D[QS_IDX[(start + end) / 2]];
    while (iq <= jq) {
        while (QS_D[QS_IDX[iq]] > xq) iq++;
        while (QS_D[QS_IDX[jq]] < xq) jq--;
        if (iq <= jq) {
            tq = QS_IDX[iq]; QS_IDX[iq] = QS_IDX[jq]; QS_IDX[jq] = tq;
            if (QS_LOG) fprintf(QS_LOG, "SWAP %s %d %d\n", QS_CID, iq, jq);
            iq++; jq--;
        }
    }
    if (start < jq) quicksort(start, jq);
    if (iq < end)   quicksort(iq, end);
}

/* ------------------------------------------------------------ loadpv --- */

#define HANDLES 16
#define PVBYTES 20480
static u8   pvfile[PVBYTES + 4096];
static u32  pv_dataptr[HANDLES], pv_datalen[HANDLES], pv_npolygs[HANDLES];
static u32  pv_top;
static u32  a_nvtx[HANDLES], a_x[HANDLES], a_y[HANDLES], a_z[HANDLES], a_c[HANDLES];
static u32  a_mx[HANDLES], a_my[HANDLES], a_mz[HANDLES], a_md[HANDLES], a_di[HANDLES];
static int  has_mid[HANDLES];        /* NOT `pv_mid_x != 0`: arena offset 0
                                        is legal (mamm_base lives there) and
                                        the null-pointer trick collides.     */

static float rdf(u32 off) { float v; memcpy(&v, pvfile + off, 4); return v; }
static void  wrf(u32 off, float v) { memcpy(pvfile + off, &v, 4); }
static u32   rdu(u32 off) { u32 v; memcpy(&v, pvfile + off, 4); return v; }

static void unloadallpv(void)
{
    int h;
    pv_top = 0;
    for (h = 0; h < HANDLES; h++) { pv_datalen[h] = 0; has_mid[h] = 0; }
}

static int loadpv(int handle, const u8 *file, size_t flen,
                  float xs, float ys, float zs, float xm, float ym, float zm,
                  u8 base_color, int depth_sort)
{
    u32 n, p, c;
    if (handle >= HANDLES) return 0;
    pv_datalen[handle] = 0;
    pv_dataptr[handle] = pv_top;
    n = (u32)(file[0] | (file[1] << 8));
    pv_npolygs[handle] = n;
    a_nvtx[handle] = pv_top;              pv_top += 1 * n;
    a_x[handle]    = pv_top;              pv_top += 16 * n;
    a_y[handle]    = pv_top;              pv_top += 16 * n;
    a_z[handle]    = pv_top;              pv_top += 16 * n;
    a_c[handle]    = pv_top;              pv_top += 1 * n;
    has_mid[handle] = 0;
    if (pv_top > PVBYTES) { pv_top = pv_dataptr[handle]; return 0; }
    memcpy(pvfile + pv_dataptr[handle], file + 2, pv_top - pv_dataptr[handle]);
    if (flen < 2 + 50 * (size_t)n) return 0;
    /* The garbage-zeroing pass runs BEFORE the scale pass.  For triangles the
       fourth vertex slot holds uninitialised editor memory -- VEHICLE has 150
       nonzero cells of 156, 26 finite above 1e6 and 2 non-finite, max 2.99e38.
       Reorder these two loops and the transform produces infinities.        */
#ifndef BREAK_NCCZERO
    /* BREAK_NCCZERO moves this loop BELOW the scale pass.  Note the two
       defects are NOT the same and are graded separately:
         --nozero        never zeroes -> VEHICLE's 2.986e38 survives the
                         scale and the transform produces infinities.
         BREAK_NCCZERO   zeroes too late -> the final slot-3 value is 0
                         instead of the translation (xmove,ymove,zmove).
       The second is INVISIBLE on all three shipped models, because every
       shipped loadpv call passes zero translation; only the synthetic
       mixed-nv model has a non-zero move and can tell them apart.        */
    if (!NOZERO) {
        for (p = 0; p < n; p++)
            if (pvfile[a_nvtx[handle] + p] == 3) {
                wrf(a_x[handle] + 4 * (4 * p + 3), 0.0f);
                wrf(a_y[handle] + 4 * (4 * p + 3), 0.0f);
                wrf(a_z[handle] + 4 * (4 * p + 3), 0.0f);
            }
    }
#endif
    if (depth_sort) {
        a_mx[handle] = pv_top; pv_top += 4 * n;
        a_my[handle] = pv_top; pv_top += 4 * n;
        a_mz[handle] = pv_top; pv_top += 4 * n;
        a_md[handle] = pv_top; pv_top += 4 * n;
        a_di[handle] = pv_top; pv_top += 2 * n;
        has_mid[handle] = 1;
        if (pv_top > PVBYTES) { pv_top = pv_dataptr[handle]; return 0; }
    }
    /* `for (c=0; c<4*npolygs; c++) { ...; pvfile_c[handle][c] += base_color; }`
       -- the colour write runs 4n times into an n-byte array.  Under the DOS
       offsets the 3n-byte overrun lands inside pv_mid_x, which the midpoint
       loop below zeroes before anything reads it, so it is FAITHFULLY DEAD.
       A re-laid-out arena would put it somewhere DOS never did.  The output
       path is NOT GRADED for this; the address census is.                   */
    for (c = 0; c < 4 * n; c++) {
        wrf(a_x[handle] + 4 * c, (float)((R)rdf(a_x[handle] + 4 * c) * xs));
        wrf(a_x[handle] + 4 * c, (float)((R)rdf(a_x[handle] + 4 * c) + xm));
        wrf(a_y[handle] + 4 * c, (float)((R)rdf(a_y[handle] + 4 * c) * ys));
        wrf(a_y[handle] + 4 * c, (float)((R)rdf(a_y[handle] + 4 * c) + ym));
        wrf(a_z[handle] + 4 * c, (float)((R)rdf(a_z[handle] + 4 * c) * zs));
        wrf(a_z[handle] + 4 * c, (float)((R)rdf(a_z[handle] + 4 * c) + zm));
        if (a_c[handle] + c < sizeof pvfile)
            pvfile[a_c[handle] + c] = (u8)(pvfile[a_c[handle] + c] + base_color);
    }
#ifdef BREAK_NCCZERO
    if (!NOZERO) {
        for (p = 0; p < n; p++)
            if (pvfile[a_nvtx[handle] + p] == 3) {
                wrf(a_x[handle] + 4 * (4 * p + 3), 0.0f);
                wrf(a_y[handle] + 4 * (4 * p + 3), 0.0f);
                wrf(a_z[handle] + 4 * (4 * p + 3), 0.0f);
            }
    }
#endif
    if (depth_sort) {
        for (p = 0; p < n; p++) {
            u32 v; u16 pi = (u16)p;
            memcpy(pvfile + a_di[handle] + 2 * p, &pi, 2);
            wrf(a_md[handle] + 4 * p, 0.0f);
            wrf(a_mx[handle] + 4 * p, 0.0f);
            wrf(a_my[handle] + 4 * p, 0.0f);
            wrf(a_mz[handle] + 4 * p, 0.0f);
            if (pvfile[a_nvtx[handle] + p]) {
                for (v = 0; v < pvfile[a_nvtx[handle] + p]; v++) {
                    wrf(a_mx[handle] + 4 * p, (float)((R)rdf(a_mx[handle] + 4 * p)
                        + (R)rdf(a_x[handle] + 4 * (4 * p + v))));
                    wrf(a_my[handle] + 4 * p, (float)((R)rdf(a_my[handle] + 4 * p)
                        + (R)rdf(a_y[handle] + 4 * (4 * p + v))));
                    wrf(a_mz[handle] + 4 * p, (float)((R)rdf(a_mz[handle] + 4 * p)
                        + (R)rdf(a_z[handle] + 4 * (4 * p + v))));
                }
                wrf(a_mx[handle] + 4 * p, (float)((R)rdf(a_mx[handle] + 4 * p) / v));
                wrf(a_my[handle] + 4 * p, (float)((R)rdf(a_my[handle] + 4 * p) / v));
                wrf(a_mz[handle] + 4 * p, (float)((R)rdf(a_mz[handle] + 4 * p) / v));
            }
        }
    }
    pv_datalen[handle] = pv_top - pv_dataptr[handle];
    return 1;
}

/* =========================================================================
   The driver.  Reads a corpus in the shared keyed grammar, runs the cases IN
   FILE ORDER (pre-state matters: one case's page can be another's input) and
   writes an SPDUMP.  It carries no constant of its own.
   ========================================================================= */

static u8 *slurp(const char *p, size_t *n)
{
    FILE *f = fopen(p, "rb"); u8 *b; long L;
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); L = ftell(f); fseek(f, 0, SEEK_SET);
    b = malloc((size_t)L + 1);
    if (fread(b, 1, (size_t)L, f) != (size_t)L) { fclose(f); free(b); return NULL; }
    b[L] = 0; *n = (size_t)L; fclose(f);
    return b;
}

static long kv(const char *line, const char *key, long dflt)
{
    char pat[64]; const char *p;
    snprintf(pat, sizeof pat, " %s=", key);
    p = strstr(line, pat);
    if (!p) { snprintf(pat, sizeof pat, "\t%s=", key); p = strstr(line, pat); }
    if (!p) return dflt;
    p += strlen(pat);
    return strtol(p, NULL, 0);
}
static unsigned long kvu(const char *line, const char *key, unsigned long d)
{
    char pat[64]; const char *p;
    snprintf(pat, sizeof pat, " %s=", key);
    p = strstr(line, pat);
    if (!p) return d;
    return strtoul(p + strlen(pat), NULL, 0);
}
/* The float32/float64 fields in the keyed grammar are BARE hex with no 0x
   prefix, so they must be read base 16.  Reading them base 0 makes
   `mag=3fa8f5c3` parse as the decimal 3 -- a subnormal 4.2e-45 that scales
   every map byte to zero, so nothing is ever clipped and every case draws.
   That is exactly the failure the two-producer join caught on its first run. */
static unsigned long kvx(const char *line, const char *key, unsigned long d)
{
    char pat[64]; const char *p;
    snprintf(pat, sizeof pat, " %s=", key);
    p = strstr(line, pat);
    if (!p) return d;
    return strtoul(p + strlen(pat), NULL, 16);
}
static int kvs(const char *line, const char *key, char *out, size_t n)
{
    char pat[64]; const char *p; size_t i = 0;
    snprintf(pat, sizeof pat, " %s=", key);
    p = strstr(line, pat);
    if (!p) return 0;
    p += strlen(pat);
    while (*p && *p != ' ' && *p != '\n' && *p != '\r' && i + 1 < n) out[i++] = *p++;
    out[i] = 0;
    return 1;
}
static double kvf64(const char *line, const char *key, double d)
{
    char buf[64]; uint64_t bits;
    if (!kvs(line, key, buf, sizeof buf)) return d;
    bits = strtoull(buf, NULL, 16);
    { double v; memcpy(&v, &bits, 8); return v; }
}
static float kvf32(const char *line, const char *key, float d)
{
    char buf[64]; u32 bits;
    if (!kvs(line, key, buf, sizeof buf)) return d;
    bits = (u32)strtoul(buf, NULL, 16);
    { float v; memcpy(&v, &bits, 4); return v; }
}

static SEG PAGE;
static u8 *GLOBES, *OFFSETS;
static size_t GLOBES_N, OFFSETS_N;
static u8 TAP[65536], SRC[65536];
static char PAGEDIR[512] = "";

static void emit_page(FILE *o, const char *cid)
{
    char h[65];
    sha_hex(PAGE.b + OFF4, 64000, h);
    fprintf(o, "PAGE %s %s\n", cid, h);
    if (PAGEDIR[0]) {
        char p[700]; FILE *f;
        snprintf(p, sizeof p, "%s/%s.page", PAGEDIR, cid);
        f = fopen(p, "wb");
        if (f) { fwrite(PAGE.b + OFF4, 1, 64000, f); fclose(f); }
    }
}

static void fill_pattern(u8 *buf, size_t n, int which, unsigned seed)
{
    size_t i; u32 s = seed ? seed : 1;
    if (which == 0) { memset(buf, 0, n); return; }
    if (which == 1) { for (i = 0; i < n; i++) buf[i] = (u8)(i & 0x3F); return; }
    if (which == 2) { memset(buf, 0x3F, n); return; }
    if (which == 3) { memset(buf, 0xC8, n); return; }   /* 200: the signed-char trap */
    for (i = 0; i < n; i++) { s = s * 1103515245u + 12345u; buf[i] = (u8)(s >> 16); }
}

int main(int argc, char **argv)
{
    const char *corpus = NULL, *outp = NULL, *scaleset = NULL;
    char *txt; size_t tn; FILE *o; char *line, *save;
    char selftest = 0;
    int i;
    char srcdir[400] = "C:\\programmieren\\noctis\\niv-plus\\source";

    for (i = 1; i < argc; i++) {
        if (!strncmp(argv[i], "--corpus=", 9)) corpus = argv[i] + 9;
        else if (!strncmp(argv[i], "--out=", 6)) outp = argv[i] + 6;
        else if (!strncmp(argv[i], "--pages=", 8)) snprintf(PAGEDIR, sizeof PAGEDIR, "%s", argv[i] + 8);
        else if (!strncmp(argv[i], "--src=", 6)) snprintf(srcdir, sizeof srcdir, "%s", argv[i] + 6);
        else if (!strncmp(argv[i], "--cast=", 7)) CASTM = strcmp(argv[i] + 7, "near") ? CAST_CHOP : CAST_NEAR;
        else if (!strncmp(argv[i], "--castsrc=", 10)) CASTSRC = strcmp(argv[i] + 10, "f64") ? SRC_EXT : SRC_F64;
        else if (!strncmp(argv[i], "--scalemul=", 11)) {
            const char *v = argv[i] + 11;
            SCALEM = !strcmp(v, "f32") ? SCALE_F32 : !strcmp(v, "dbl") ? SCALE_DBL : SCALE_X87;
        }
        else if (!strcmp(argv[i], "--nozero")) NOZERO = 1;
        else if (!strncmp(argv[i], "--dgroup=", 9)) DGFILL = argv[i] + 9;
        else if (!strcmp(argv[i], "--selftest")) selftest = 1;
        else if (!strncmp(argv[i], "--scaleset=", 11)) scaleset = argv[i] + 11;
        else { fprintf(stderr, "sp_ref: unknown argument %s\n", argv[i]); return 2; }
    }
    dgroup_build();

    {   char p[600]; size_t n;
        snprintf(p, sizeof p, "%s\\GLOBES.MAP", srcdir);
        GLOBES = slurp(p, &n); GLOBES_N = n;
        snprintf(p, sizeof p, "%s\\OFFSETS.MAP", srcdir);
        OFFSETS = slurp(p, &n); OFFSETS_N = n;
        if (!GLOBES || !OFFSETS) { fprintf(stderr, "sp_ref: cannot read the maps under %s\n", srcdir); return 2; }
    }

    o = outp ? fopen(outp, "wb") : stdout;
    if (!o) { fprintf(stderr, "sp_ref: cannot write %s\n", outp); return 2; }

    fprintf(o, "SPDUMP 1 producer=sp_ref.c cast=%s castsrc=%s scalemul=%s nozero=%d dgroup=%s\n",
            CASTM == CAST_CHOP ? "chop" : "near",
            CASTSRC == SRC_EXT ? "ext" : "f64",
            SCALEM == SCALE_X87 ? "x87" : SCALEM == SCALE_F32 ? "f32" : "dbl",
            NOZERO, DGFILL);
    fprintf(o, "ASSET globes bytes=%zu\n", GLOBES_N);
    fprintf(o, "ASSET offsets bytes=%zu\n", OFFSETS_N);

    if (selftest) {
        /* EX1's hardware leg: every live dy against a sweep of mag_factor.
           The exact-integer model in sp_spec.py must reproduce every one.
           The values are PRINTED, not judged -- tests/test_sphere.py judges. */
        u32 mb; int dy;
        static const double sweep[] = {0.001,0.0100001,0.33,0.330001,0.66,0.99,1.32,
                                       0.5,0.125,1.0,0.6666667,0.0009999};
        for (i = 0; i < (int)(sizeof sweep / sizeof sweep[0]); i++) {
            float f = (float)sweep[i]; memcpy(&mb, &f, 4);
            for (dy = -106; dy <= 105; dy++)
                fprintf(o, "SCALE %08x %d %d\n", mb, dy, (int)x87_scale((i16)dy, mb));
        }
        for (i = 0; i < 256; i++) {
            fprintf(o, "MANGLE %d %d\n", i, (i & 0xC0) | ((i & 0x3F) >> 1));
            fprintf(o, "GLOWCOL %d %d %d\n", i, i, ((i & 0x3F) >> 2) | (i & 0xC0));
        }
        {   int t, s, cm;
            for (t = 0; t < 256; t += 1)
                for (s = 0; s < 64; s += 21)
                    for (cm = 0; cm < 256; cm += 64) {
                        int dl = t < s ? s : t;
                        fprintf(o, "GCOL %d %d %d %d\n", t, s, cm, (dl | cm) & 0xFF);
                    }
            for (t = 0; t < 64; t++)
                for (s = 0; s < 256; s++) {
                    int v = (int)(signed char)((t + s) & 0xFF);
                    fprintf(o, "WSTORE %d %d %d\n", t, s, v > 0x3F ? 0x3F : (v & 0xFF));
                }
        }
        for (i = 1; i <= 4; i++) {
            int k;
            static const int offs[5][16] = {{0},{4},{4,5,324,325},
                {4,5,6,324,325,326,644,645,646},
                {4,5,6,7,324,325,326,327,644,645,646,647,964,965,966,967}};
            static const int cnt[5] = {0,1,4,9,16};
            fprintf(o, "GMAN %d", i);
            for (k = 0; k < cnt[i]; k++) fprintf(o, " %d", offs[i][k]);
            fprintf(o, "\n");
        }
    }

    if (scaleset) {
        /* EX1's hardware leg on a caller-chosen set of mag_factor patterns:
           the adversarial ties, where a float32 multiply and the exact chain
           disagree.  Run the whole live dy range against every one.         */
        FILE *sf = fopen(scaleset, "rb");
        char lb[64];
        if (!sf) { fprintf(stderr, "sp_ref: cannot read %s\n", scaleset); return 2; }
        while (fgets(lb, sizeof lb, sf)) {
            u32 mb; int dy;
            if (lb[0] == '#' || lb[0] == '\n' || lb[0] == '\r') continue;
            mb = (u32)strtoul(lb, NULL, 16);
            for (dy = -106; dy <= 105; dy++)
                fprintf(o, "SCALE %08x %d %d\n", mb, dy, (int)x87_scale((i16)dy, mb));
        }
        fclose(sf);
    }

    if (!corpus) { if (outp) fclose(o); return 0; }
    txt = (char *)slurp(corpus, &tn);
    if (!txt) { fprintf(stderr, "sp_ref: cannot read %s\n", corpus); return 2; }

    for (line = strtok_r(txt, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char kind[32], cid[64];
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || !*p || *p == '\r') continue;
        if (sscanf(p, "CASE %63s %31s", cid, kind) != 2) continue;

        if (!strcmp(kind, "GLOBE")) {
            GLOBERES r;
            u32 mag = (u32)kvx(p, "mag", 0);
            int cxi = (int)kv(p, "cx", 0), cyi = (int)kv(p, "cy", 0);
            int gm = (int)kv(p, "gman", 1);
            int st = (int)kv(p, "start", 0);
            int cmk = (int)kv(p, "colormask", 0), sat = (int)kv(p, "sat", 0);
            int tapf = (int)kv(p, "tapfill", 1), pre = (int)kv(p, "pre", 0);
            unsigned tseed = (unsigned)kvu(p, "tapseed", 7);
            long mark = kv(p, "tapmark", -1);
            seg_clear(&PAGE, (u8)pre);
            fill_pattern(TAP, sizeof TAP, tapf, tseed);
            if (mark >= 0 && mark < 65536) TAP[mark] = 0x2A;
            globe_raster(&PAGE, GLOBES, (u16)GLOBES_N, TAP, sizeof TAP,
                         (u16)st, mag, (i16)cxi, (i16)cyi, gm,
                         (u8)cmk, (u8)sat, &r);
            fprintf(o, "GLOBE %s cursor=%u drawn=%ld ylo=%ld yhi=%ld xlo=%ld xhi=%ld tapmin=%ld tapmax=%ld\n",
                    cid, (unsigned)r.cursor, r.drawn, r.rej_ylo, r.rej_yhi,
                    r.rej_xlo, r.rej_xhi, r.tap_min, r.tap_max);
            emit_page(o, cid);
        } else if (!strcmp(kind, "GLOW")) {
            GLOWRES r;
            u32 mag = (u32)kvx(p, "mag", 0);
            int cxi = (int)kv(p, "cx", 0), cyi = (int)kv(p, "cy", 0);
            int st = (int)kv(p, "start", 0), ts = (int)kv(p, "tstart", 0);
            int arc = (int)kv(p, "arc", 130), col = (int)kv(p, "color", 127);
            int pre = (int)kv(p, "pre", 0);
            seg_clear(&PAGE, (u8)pre);
            glow_raster(&PAGE, GLOBES, (u16)GLOBES_N, st, ts, arc, mag,
                        (u16)cxi, (u16)cyi, (u8)col, &r, o, cid);
            fprintf(o, "GLOW %s counter=%u drawn=%ld decim=%ld rejy=%ld xlo=%ld xhi=%ld oobn=%ld oobmin=%ld oobmax=%ld oobw=%ld light=%d dark=%d\n",
                    cid, (unsigned)r.counter_end, r.drawn, r.decimated, r.rej_y,
                    r.rej_xlo, r.rej_xhi, r.oob_n, r.oob_min, r.oob_max,
                    r.oob_writes, r.light, r.dark);
            emit_page(o, cid);
        } else if (!strcmp(kind, "BG")) {
            BGRES r;
            int st = (int)kv(p, "start", 0);
            int sh = (int)kv(p, "shift", 0);
            int sf = (int)kv(p, "srcfill", 1), pre = (int)kv(p, "pre", 0);
            unsigned sseed = (unsigned)kvu(p, "srcseed", 11);
            seg_clear(&PAGE, (u8)pre);
            fill_pattern(SRC, sizeof SRC, sf, sseed);
            background_raster(&PAGE, OFFSETS, (u16)OFFSETS_N, SRC, sizeof SRC,
                              (u16)st, (u16)sh, &r, o, cid);
            fprintf(o, "BG %s src=%u paints=%ld skips=%ld wrapped=%ld smin=%ld smax=%ld boundary=%ld\n",
                    cid, (unsigned)r.src_cursor, r.paints, r.skips, r.wrapped,
                    r.smin, r.smax, r.boundary);
            fprintf(o, "BGIDX %s %ld %s\n", cid, r.paints, r.dihash);
            emit_page(o, cid);
        } else if (!strcmp(kind, "DARK")) {
            long first, last;
            int plwp = (int)kv(p, "plwp", 0);
            int f = (int)kv(p, "fill", 1);
            unsigned sd = (unsigned)kvu(p, "seed", 13);
            seg_clear(&PAGE, 0);
            fill_pattern(PAGE.b + OFF4, 64800, f, sd);
            surface_band(&PAGE, plwp, &first, &last);
            fprintf(o, "DARK %s first=%ld last=%ld\n", cid, first, last);
            emit_page(o, cid);
        } else if (!strcmp(kind, "WHITE")) {
            long writes, clipped;
            double cxd = kvf64(p, "cx", 160.0), cyd = kvf64(p, "cy", 100.0);
            float mf = kvf32(p, "mag", 0.5f), fg = kvf32(p, "fgm", 0.3f);
            int sun = (int)kv(p, "sun", 0);
            int pre = (int)kv(p, "pre", 0);
            unsigned sd = (unsigned)kvu(p, "seed", 17);
            seg_clear(&PAGE, 0);
            fill_pattern(PAGE.b + OFF4, 64000, pre, sd);
            writes = white_body(&PAGE, cxd, cyd, mf, fg, sun, &clipped);
            fprintf(o, "WHITE %s writes=%ld clipped=%ld\n", cid, writes, clipped);
            emit_page(o, cid);
        } else if (!strcmp(kind, "PRE")) {
            CAM2 c; PRERES r;
            int variant = (int)kv(p, "variant", 0);
            c.dzx = kvf64(p, "dzx", 0); c.dzy = kvf64(p, "dzy", 0); c.dzz = kvf64(p, "dzz", 0);
            c.pcosbeta = kvf32(p, "pcb", 210.0f); c.psinbeta = kvf32(p, "psb", 0.0f);
            c.tcosbeta = kvf32(p, "tcb", 1.0f);   c.tsinbeta = kvf32(p, "tsb", 0.0f);
            c.tcosalfa = kvf32(p, "tca", 1.0f);   c.tsinalfa = kvf32(p, "tsa", 0.0f);
            c.pcosalfa = kvf32(p, "pca", 210.0f); c.psinalfa = kvf32(p, "psa", 0.0f);
            preamble2(&c, kvf64(p, "x", 0), kvf64(p, "y", 0), kvf64(p, "z", 0),
                      (u32)kvx(p, "mag", 0x3F000000u), variant, &r);
            {   uint64_t bx, by, brz; double t;
                t = r.rx; memcpy(&bx, &t, 8);
                t = r.ry; memcpy(&by, &t, 8);
                t = r.rz; memcpy(&brz, &t, 8);
                fprintf(o, "PRE %s rej=%d rz=%016llx rx=%016llx ry=%016llx mag=%08x gman=%d cx=%d cy=%d xsunw=%d\n",
                        cid, r.rejected, (unsigned long long)brz,
                        (unsigned long long)bx, (unsigned long long)by,
                        r.mag_out, r.gman, (int)r.cx_i, (int)r.cy_i, r.xsun_written);
                if (r.xsun_written) {
                    uint64_t bs; t = r.xsun; memcpy(&bs, &t, 8);
                    fprintf(o, "XSUN %s %016llx\n", cid, (unsigned long long)bs);
                }
                if (variant >= 2) {
                    uint64_t a, b2; t = r.cx_d; memcpy(&a, &t, 8);
                    t = r.cy_d; memcpy(&b2, &t, 8);
                    fprintf(o, "WCENTRE %s %016llx %016llx\n", cid,
                            (unsigned long long)a, (unsigned long long)b2);
                }
            }
        } else if (!strcmp(kind, "NCC")) {
            char fn[200], full[700]; size_t fl; u8 *fb; u32 h, n, k;
            int reset = (int)kv(p, "reset", 0);
            if (!kvs(p, "model", fn, sizeof fn)) continue;
            h = (u32)kv(p, "handle", 0);
            if (reset) unloadallpv();
            snprintf(full, sizeof full, "%s\\NCC\\%s.NCC", srcdir, fn);
            fb = slurp(full, &fl);
            if (!fb) {          /* the synthetic model sits beside the corpus */
                const char *s = strrchr(corpus, '/'), *s2 = strrchr(corpus, '\\');
                if (s2 > s) s = s2;
                if (s) { size_t k = (size_t)(s - corpus) + 1;
                         snprintf(full, sizeof full, "%.*s%s", (int)k, corpus, fn); }
                else snprintf(full, sizeof full, "%s", fn);
                fb = slurp(full, &fl);
            }
            if (!fb) { fprintf(o, "NCCERR %s %s\n", cid, fn); continue; }
            loadpv((int)h, fb, fl,
                   kvf32(p, "xs", 1.0f), kvf32(p, "ys", 1.0f), kvf32(p, "zs", 1.0f),
                   kvf32(p, "xm", 0.0f), kvf32(p, "ym", 0.0f), kvf32(p, "zm", 0.0f),
                   (u8)kv(p, "base", 0), (int)kv(p, "ds", 1));
            n = pv_npolygs[h];
            fprintf(o, "ARENA %s h=%u n=%u ptr=%u nvtx=%u x=%u y=%u z=%u c=%u mx=%u my=%u mz=%u md=%u di=%u len=%u top=%u mid=%d\n",
                    cid, h, n, pv_dataptr[h], a_nvtx[h], a_x[h], a_y[h], a_z[h],
                    a_c[h], a_mx[h], a_my[h], a_mz[h], a_md[h], a_di[h],
                    pv_datalen[h], pv_top, has_mid[h]);
            {   long nonfin = 0;
                for (k = 0; k < n; k++) {
                    if (pvfile[a_nvtx[h] + k] != 3) continue;
                    fprintf(o, "SLOT3 %s %u %08x %08x %08x\n", cid, k,
                            rdu(a_x[h] + 4 * (4 * k + 3)),
                            rdu(a_y[h] + 4 * (4 * k + 3)),
                            rdu(a_z[h] + 4 * (4 * k + 3)));
                }
                for (k = 0; k < 4 * n; k++) {
                    float vx = rdf(a_x[h] + 4 * k), vy = rdf(a_y[h] + 4 * k),
                          vz = rdf(a_z[h] + 4 * k);
                    if (!isfinite(vx) || !isfinite(vy) || !isfinite(vz)) nonfin++;
                }
                fprintf(o, "NONFIN %s %ld\n", cid, nonfin);
                for (k = 0; k < n; k++)
                    fprintf(o, "MID %s %u %08x %08x %08x\n", cid, k,
                            rdu(a_mx[h] + 4 * k), rdu(a_my[h] + 4 * k),
                            rdu(a_mz[h] + 4 * k));
            }
            free(fb);
        } else if (!strcmp(kind, "SORT")) {
            /* pv_dep_i is PERSISTENT: the array carried in is the PREVIOUS
               frame's permutation.  d0..dN are the pinned distances.        */
            static int idx[512]; static float dist[512];
            int n = (int)kv(p, "n", 0), k, frames = (int)kv(p, "frames", 1), fr;
            int reset = (int)kv(p, "reset", 1);
            char key[32];
            if (n <= 0 || n > 512) continue;
            if (reset) for (k = 0; k < n; k++) idx[k] = k;
            for (k = 0; k < n; k++) {
                snprintf(key, sizeof key, "d%d", k);
                dist[k] = kvf32(p, key, (float)k);
            }
            QS_IDX = idx; QS_D = dist; QS_LOG = o; QS_CID = cid;
            for (fr = 0; fr < frames; fr++) {
                quicksort(0, n - 1);
                fprintf(o, "SORT %s %d", cid, fr);
                for (k = 0; k < n; k++) fprintf(o, " %d", idx[k]);
                fprintf(o, "\n");
            }
            QS_LOG = NULL;
        } else if (!strcmp(kind, "PVL")) {
            /* modpv's do{}while(v < pv_n_vtx[c]) -- executes ONCE even at 0. */
            char buf[512]; int k, nvv[64], nent = 0, ent[64];
            if (kvs(p, "list", buf, sizeof buf)) {
                char *q = buf, *e;
                while (*q && nent < 64) { ent[nent++] = (int)strtol(q, &e, 0);
                                          if (e == q) break; q = (*e == ',') ? e + 1 : e; }
            }
            if (kvs(p, "nv", buf, sizeof buf)) {
                char *q = buf, *e; int c2 = 0;
                while (*q && c2 < 64) { nvv[c2++] = (int)strtol(q, &e, 0);
                                        if (e == q) break; q = (*e == ',') ? e + 1 : e; }
                for (; c2 < 64; c2++) nvv[c2] = 0;
            } else for (k = 0; k < 64; k++) nvv[k] = 4;
            fprintf(o, "PVL %s", cid);
            for (k = 0; k < nent; k++) {
                int w = ent[k], pid = w & 0xFFF, v = 0;
                int fl[4] = {(w >> 12) & 1, (w >> 13) & 1, (w >> 14) & 1, (w >> 15) & 1};
                if (pid == 0xFFF) break;
                do {
                    if (v < 4 && fl[v]) fprintf(o, " %d", 4 * pid + v);
                    v++;
                } while (v < (pid < 64 ? nvv[pid] : 0));
            }
            fprintf(o, "\n");
        }
    }
    free(txt);
    if (outp) fclose(o);
    return 0;
}
