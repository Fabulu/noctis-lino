/* Wave 7b sky_ref.c -- independent fixed-width C reference.
 *
 * Source authority:
 *   NIV+ R2.3 NOCTIS-1.CPP:1674-1701,1703-1736,2736-3139,3683-3697
 *   NIV+ R2.3 NOCTIS-0.CPP:1151-1200,4380-4444
 *
 * This program consumes the frozen 29-unit decimal corpus and emits the SKY1
 * framed stream.  It contains no Python expected values.  Host storage is
 * explicitly sized; every source float assignment is narrowed through sf(),
 * and every byte write goes through the instrumented workspace wrapper.
 *
 * usage: sky_ref.exe CORPUS OUTPUT [--offsets OFFSETS.MAP]
 *                                  [--replay 64800_BYTE_SBG]
 */

#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ST_BYTES 64800u
#define TAIL_BYTES 64u
#define PAGE_BYTES 64000u
#define SEG_BYTES 65536u
#define OFFSET_MAP_BYTES 7340u
#define SKY_MAGIC UINT32_C(0x31594B53)
#define SKY_VERSION 1u
#define FNV_OFF UINT32_C(0x811C9DC5)
#define FNV_PRIME UINT32_C(0x01000193)
#define KNOWN_FLAGS 127u

#define BINARY_ANCHOR 1u
#define GRADE_PALETTE 2u
#define GRADE_SCALARS 4u
#define GRADE_PAGE 8u
#define TAIL_SENSITIVE 16u
#define LIVE_REACHABLE 32u
#define PALETTE_UNDEFINED 64u

enum { META=1, PRE_HORIZON=2, FINAL_SBG=3, PALETTE=4, SCALARS=5,
       LEDGER=6, GUARDS=7, REPLAY_PAGE=8, JOIN_PAGE=9, CASE_END=10,
       STREAM_END=255 };
enum { OCEAN=1, PLAINS=2, DESERT=3, ICY=4 };

/* sky_break.py changes exactly one of these zeroes in each generated source. */
#define SKY_MUT_OCEAN_12_DRAWS 0
#define SKY_MUT_TYPE5_9_DRAWS 0
#define SKY_MUT_REMOVE_ALBEDO 0
#define SKY_MUT_ZERO_DENOM_ZERO 0
#define SKY_MUT_CLOUD_NO_SCALE64 0
#define SKY_MUT_BYTE_SMOOTH 0
#define SKY_MUT_OUT_OF_PLACE 0
#define SKY_MUT_SS_STRIDE_320 0
#define SKY_MUT_PS_STRIDE_360 0
#define SKY_MUT_LS_DROP_RIGHT 0
#define SKY_MUT_LS_CLAMP_TAIL 0
#define SKY_MUT_HORIZON_119 0
#define SKY_MUT_HORIZON_121 0
#define SKY_MUT_HORIZON_WIDTH_359 0
#define SKY_MUT_HORIZON_WIDTH_361 0
#define SKY_MUT_HORIZON_ORDER 0
#define SKY_MUT_HORIZON_INT_DIV_FIRST 0
#define SKY_MUT_HORIZON_NO_NIGHT_HALF 0
#define SKY_MUT_ATMOSPHERE_BUFFER 0
#define SKY_MUT_PALETTE_TO_PAL6 0
#define SKY_MUT_ROUND_CHOP 0
#define SKY_MUT_REMOVE_T3_NIGHT_GOTO 0
#define SKY_MUT_WRONG_RNG_SEED 0
#define SKY_MUT_WRONG_RNG_STREAM 0
#define SKY_MUT_STALE_TYPE5_BRIGHTNESS 0
#define SKY_MUT_NO_QW_RESTORE 0
#define SKY_MUT_SBG_OOB 0
#define SKY_MUT_WIDE_SCALE_FLOATS 0

typedef struct {
    uint32_t u[29];
} SkyCase;

enum {
    F_OPCODE, F_CASE_ID, F_FLAGS, F_PTYPE, F_SCTYPE, F_ATMOSPHERE,
    F_NIGHTZONE, F_IP_TARGETTED, F_NEARSTAR_OWNER, F_NEARSTAR_CLASS,
    F_SURFACE_SEED, F_ALBEDO, F_RAINY_BITS, F_BRIGHTNESS,
    F_SKY_R, F_SKY_G, F_SKY_B, F_GND_R, F_GND_G, F_GND_B,
    F_DSD1_BITS, F_EXPOSURE_BITS, F_LAT, F_QUADWORDS, F_TAIL_MODE,
    F_TAIL_SEED, F_BG_START, F_BG_SHIFT, F_BG_BYTES
};

typedef struct {
    uint8_t data[ST_BYTES + TAIL_BYTES];
    uint8_t canary[16];
    uint32_t min_write, max_write, writes, oob_writes;
    uint32_t tail_before, canary_before;
} Workspace;

typedef struct {
    uint32_t state, draws, hash;
} LedgerRng;

typedef struct {
    uint32_t v[8];
} PhaseLedger;

typedef struct {
    float dfs, sb, saturation;
    double wide_dfs, wide_sb, wide_saturation;
} ColourFactors;

typedef struct {
    FILE *f;
    uint32_t case_id, flags, sequence;
    uint32_t records;
    int failed;
} Writer;

static float sf(double x) {
    volatile float y = (float)x;
    return y;
}

static float sf_mul(float a, float b) {
    return sf((double)a * (double)b);
}

static uint32_t float_bits(float x) {
    uint32_t u;
    memcpy(&u, &x, sizeof u);
    return u;
}

static float bits_float(uint32_t u) {
    float x;
    memcpy(&x, &u, sizeof x);
    return x;
}

static int32_t si(const SkyCase *c, unsigned field) {
    uint32_t u = c->u[field];
    if (u & UINT32_C(0x80000000))
        return (int32_t)((int64_t)u - INT64_C(0x100000000));
    return (int32_t)u;
}

static uint32_t fnv_bytes(const uint8_t *p, size_t n) {
    uint32_t h = FNV_OFF;
    size_t i;
    for (i = 0; i < n; ++i) h = (h ^ p[i]) * FNV_PRIME;
    return h;
}

static uint32_t fnv_u32(uint32_t h, uint32_t v) {
    unsigned i;
    for (i = 0; i < 4; ++i) {
        h = (h ^ (v & 255u)) * FNV_PRIME;
        v >>= 8;
    }
    return h;
}

static void brtl_seed(LedgerRng *r, uint32_t seed) {
    r->state = seed & 0xFFFFu;
}

static int32_t brtl_random(LedgerRng *r, int32_t n) {
    uint32_t rv;
    int64_t product;
    int32_t value;
    r->state = r->state * UINT32_C(0x015A4E35) + 1u;
    rv = (r->state >> 16) & 0x7FFFu;
    product = (int64_t)(int32_t)rv * (int64_t)n;
    value = (int32_t)(product / INT64_C(32768));
    r->draws++;
    r->hash = fnv_u32(r->hash, (uint32_t)value);
    return value;
}

static float brtl_flandom(LedgerRng *r) {
    return sf((double)brtl_random(r, 32767) * 0.000030518);
}

static void fast_seed(LedgerRng *r, uint32_t seed) {
    r->state = (seed & UINT32_C(0xFFFF0000)) | ((seed & 0xFFFFu) | 3u);
}

static uint32_t fast_random(LedgerRng *r, uint32_t mask) {
    uint64_t p = (uint64_t)r->state * (uint64_t)r->state;
    uint32_t eax = (uint32_t)p;
    uint32_t edx = (uint32_t)(p >> 32);
    uint32_t value;
    eax = (eax & UINT32_C(0xFFFFFF00)) | ((eax + edx) & 255u);
    r->state += eax;
    value = eax & mask;
    r->draws++;
    r->hash = fnv_u32(r->hash, value);
    return value;
}

static float fast_flandom(LedgerRng *r) {
    return sf((double)fast_random(r, 32767u) * 0.000030518);
}

static const uint8_t CANARY[16] = {
    0xd3,0x71,0x4a,0xc9,0x26,0x8e,0x5b,0xf0,
    0x19,0xa7,0x63,0xbc,0x40,0x2d,0xe1,0x95
};

static void ws_init(Workspace *w, uint8_t fill, uint32_t tail_mode,
                    uint32_t tail_seed) {
    uint32_t i;
    memset(w->data, fill, ST_BYTES);
    for (i = 0; i < TAIL_BYTES; ++i) {
        w->data[ST_BYTES+i] = tail_mode ?
            (uint8_t)(tail_seed + 73u*i + ((i*i) >> 1)) : 0;
    }
    memcpy(w->canary, CANARY, sizeof CANARY);
    /* The caller's _fmemset is inside the tested create+post-horizon unit. */
    w->min_write = 0;
    w->max_write = ST_BYTES - 1u;
    w->writes = ST_BYTES;
    w->oob_writes = 0;
    w->tail_before = fnv_bytes(w->data + ST_BYTES, TAIL_BYTES);
    w->canary_before = fnv_bytes(w->canary, sizeof w->canary);
}

static void ws_write(Workspace *w, uint32_t p, uint32_t value) {
    if (p < ST_BYTES) {
        w->data[p] = (uint8_t)value;
        if (w->min_write == UINT32_MAX || p < w->min_write) w->min_write = p;
        if (w->max_write == UINT32_MAX || p > w->max_write) w->max_write = p;
        w->writes++;
    } else {
        w->oob_writes++;
    }
}

static uint32_t ld32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void ssmooth(Workspace *w, uint32_t requested_stride) {
    uint32_t stride = requested_stride;
    uint32_t n, p, i;
    uint8_t *snapshot = NULL;
    if (SKY_MUT_SS_STRIDE_320 && stride == 360u) stride = 320u;
    if (SKY_MUT_PS_STRIDE_360 && stride == 320u) stride = 360u;
    n = ST_BYTES - 4u * stride;
    p = stride;
    if (SKY_MUT_OUT_OF_PLACE) {
        snapshot = (uint8_t *)malloc(ST_BYTES + TAIL_BYTES);
        if (!snapshot) { fprintf(stderr, "out of memory\n"); exit(2); }
        memcpy(snapshot, w->data, ST_BYTES + TAIL_BYTES);
    }
    for (i = 0; i < n; ++i, ++p) {
        const uint8_t *a = snapshot ? snapshot : w->data;
        uint32_t out;
        if (SKY_MUT_BYTE_SMOOTH) {
            out = ((uint32_t)a[p-stride] + a[p] + a[p+stride] +
                   a[p+2u*stride]) >> 2;
        } else {
            uint32_t e = ld32(a+p-stride) + ld32(a+p) +
                         ld32(a+p+stride) + ld32(a+p+2u*stride);
            e = (e & UINT32_C(0xFCFCFCFC)) >> 2;
            out = ((e & 255u) + ((e >> 8) & 255u) +
                   ((e >> 16) & 255u) + ((e >> 24) & 255u)) & 255u;
            out >>= 2;
        }
        ws_write(w, p, out);
    }
    free(snapshot);
}

static void lssmooth(Workspace *w) {
    uint32_t p;
    const uint32_t n = (ST_BYTES / 4u - 80u) * 4u;
    uint8_t *snapshot = NULL;
    if (SKY_MUT_OUT_OF_PLACE) {
        snapshot = (uint8_t *)malloc(ST_BYTES + TAIL_BYTES);
        if (!snapshot) { fprintf(stderr, "out of memory\n"); exit(2); }
        memcpy(snapshot, w->data, ST_BYTES + TAIL_BYTES);
    }
    for (p = 0; p < n; ++p) {
        const uint8_t *a = snapshot ? snapshot : w->data;
        uint32_t p360 = p + 360u;
        uint32_t p361 = p + 361u;
        uint32_t d0 = a[p], d1, b0, b1;
        if (SKY_MUT_LS_CLAMP_TAIL) {
            if (p360 >= ST_BYTES) p360 = ST_BYTES - 1u;
            if (p361 >= ST_BYTES) p361 = ST_BYTES - 1u;
        }
        d1 = SKY_MUT_LS_DROP_RIGHT ? d0 : a[p+1u];
        b0 = a[p360];
        b1 = SKY_MUT_LS_DROP_RIGHT ? b0 : a[p361];
        ws_write(w, p, (d0 & 0xC0u) +
                       (((d0 & 0x3Fu) + (d1 & 0x3Fu) +
                         (b0 & 0x3Fu) + (b1 & 0x3Fu)) >> 2));
    }
    free(snapshot);
}

static void cloudy_sky(Workspace *w, LedgerRng *b, int32_t density,
                       int smooths, int32_t albedo) {
    int32_t n;
    if (SKY_MUT_REMOVE_ALBEDO) albedo = 0;
    n = brtl_random(b, density + albedo);
    while (n-- > 0) {
        int32_t cx = brtl_random(b, 360);
        int32_t r = brtl_random(b, 25) + 5;
        int32_t cy = brtl_random(b, 50) + 25 + r;
        int32_t y, x;
        for (y = -r; y < r; ++y) {
            for (x = -2*r; x < 2*r; ++x) {
                if (sqrt((double)x*x*0.2 + (double)y*y) < r) {
                    uint32_t p = (uint16_t)(x + cx + 360*(y+cy));
                    if (p < ST_BYTES) {
                        double den = sqrt((double)(x+r)*(x+r) +
                                          (double)(y+r)*(y+r));
                        float v;
                        if (den == 0.0)
                            v = SKY_MUT_ZERO_DENOM_ZERO ? 0.0f : INFINITY;
                        else
                            v = sf(1.4142 / den);
                        if (!SKY_MUT_CLOUD_NO_SCALE64) v = sf((double)v * 64.0);
                        v = sf((double)v + w->data[p]);
                        if (v > 63.0f) v = 63.0f;
                        ws_write(w, p, SKY_MUT_ROUND_CHOP ?
                                 (uint32_t)(v + 0.5f) : (uint32_t)v);
                    }
                }
            }
        }
    }
    while (smooths-- > 0) ssmooth(w, 360u);
}

static void nebular_sky(Workspace *w, LedgerRng *b) {
    uint16_t ax = (uint16_t)brtl_random(b, 10000);
    uint32_t cx = ST_BYTES, p = 0;
    while (cx) {
        int32_t sx;
        int32_t product;
        uint16_t dx;
        ax = (uint16_t)(ax + (uint16_t)cx);
        sx = (ax & 0x8000u) ? (int32_t)ax - 65536 : (int32_t)ax;
        product = sx * sx;
        dx = (uint16_t)((uint32_t)product >> 16);
        ax = (uint16_t)((uint16_t)product + dx);
        ws_write(w, p++, ax & 0x3Fu);
        --cx;
    }
    lssmooth(w);
    if (brtl_random(b, 2)) ssmooth(w, 360u);
    if (brtl_random(b, 3)) ssmooth(w, 320u);
}

static void apply_horizon(Workspace *w, int night) {
    uint32_t rows = SKY_MUT_HORIZON_119 ? 119u :
                    (SKY_MUT_HORIZON_121 ? 121u : 120u);
    uint32_t width = SKY_MUT_HORIZON_WIDTH_359 ? 359u :
                     (SKY_MUT_HORIZON_WIDTH_361 ? 361u : 360u);
    uint32_t p = 0, row, col;
    for (row = 0; row < rows; ++row) {
        for (col = 0; col < width; ++col) {
            float v;
            if (p >= ST_BYTES) { ws_write(w, p, 0); ++p; continue; }
            if (SKY_MUT_HORIZON_INT_DIV_FIRST) {
                v = sf((double)(w->data[p] / 120u) * row);
            } else if (SKY_MUT_HORIZON_ORDER) {
                float divided_first = sf((double)w->data[p] / 120.0);
                v = sf((double)divided_first * row);
            } else
                v = sf(((double)w->data[p] * row) / 120.0);
            if (night && !SKY_MUT_HORIZON_NO_NIGHT_HALF) v = sf(v / 2.0);
            ws_write(w, p, SKY_MUT_ROUND_CHOP ?
                     (uint32_t)(v + 0.5f) : (uint32_t)v);
            ++p;
        }
    }
}

static uint8_t palette_place(float v) {
    if (v >= 0.0f && v < 64.0f)
        return (uint8_t)(SKY_MUT_ROUND_CHOP ? (int)(v + 0.5f) : (int)v);
    return v > 0.0f ? 63u : 0u;
}

static void shade(uint8_t *dst, int first, int n,
                  float sr, float sg, float sb,
                  float er, float eg, float eb) {
    float k = sf(1.0 / n);
    float dr = sf((double)sf((double)er - sr) * k);
    float dg = sf((double)sf((double)eg - sg) * k);
    float db = sf((double)sf((double)eb - sb) * k);
    float cr = sf(sr), cg = sf(sg), cb = sf(sb);
    int i = first * 3;
    while (n-- > 0) {
        dst[i++] = palette_place(cr);
        dst[i++] = palette_place(cg);
        dst[i++] = palette_place(cb);
        cr = sf((double)cr + dr);
        cg = sf((double)cg + dg);
        cb = sf((double)cb + db);
    }
}

static void make_palette(uint8_t srf[768], uint8_t pal6[768],
                         float fr[4], float fg[4], float fb[4],
                         int atmosphere, int night, int ptype, int defined) {
    uint8_t *dst = SKY_MUT_PALETTE_TO_PAL6 ? pal6 : srf;
    if (!defined) return;
    if (!atmosphere) {
        shade(dst,64,64,0,0,0,100,110,120);
    } else if (night) {
        shade(dst,64,64,0,0,0,60,62,64);
        if (ptype == 3 && !SKY_MUT_REMOVE_T3_NIGHT_GOTO) {
            shade(dst,0,64,0,0,0,64,62,60);
            shade(dst,128,64,0,0,0,64,64,64);
            shade(dst,192,64,8,12,16,56,60,64);
            return;
        }
        fr[0]=sf(fr[0]*.33); fg[0]=sf(fg[0]*.44); fb[0]=sf(fb[0]*.55);
        fr[2]=sf(fr[2]*.33); fg[2]=sf(fg[2]*.44); fb[2]=sf(fb[2]*.55);
        fr[3]=sf(fr[3]*.33); fg[3]=sf(fg[3]*.44); fb[3]=sf(fb[3]*.55);
    } else {
        shade(dst,64,64,0,0,0,fr[1],fg[1],fb[1]);
    }
    shade(dst,0,44,0,0,0,fr[0],fg[0],fb[0]);
    shade(dst,44,20,fr[0],fg[0],fb[0],fr[1],fg[1],fb[1]);
    shade(dst,128,10,0,0,0,fr[0],fg[0],fb[0]);
    shade(dst,138,44,fr[0],fg[0],fb[0],fr[2],fg[2],fb[2]);
    shade(dst,182,10,fr[2],fg[2],fb[2],fr[1],fg[1],fb[1]);
    shade(dst,192,10,0,0,0,fr[0],fg[0],fb[0]);
    shade(dst,202,44,fr[0],fg[0],fb[0],fr[3],fg[3],fb[3]);
    shade(dst,246,10,fr[3],fg[3],fb[3],fr[1],fg[1],fb[1]);
}

static void mark_phase(PhaseLedger ledgers[8], unsigned phase,
                       const Workspace *w, const LedgerRng *b,
                       const LedgerRng *f) {
    PhaseLedger *l = &ledgers[phase];
    l->v[0]=phase; l->v[1]=b->draws; l->v[2]=f->draws;
    l->v[3]=b->hash; l->v[4]=f->hash; l->v[5]=b->state; l->v[6]=f->state;
    l->v[7]=fnv_bytes(w->data, ST_BYTES);
}

static ColourFactors colour_factors(const SkyCase *c, int atmosphere) {
    int owner=si(c,F_NEARSTAR_OWNER), cls=si(c,F_NEARSTAR_CLASS);
    ColourFactors result={0};

    /* These locals are evaluated before the planet-type switch.  Type 5 may
     * later mutate global sky_brightness, but it cannot retroactively change
     * this already-stored local sb. */
    if (SKY_MUT_WIDE_SCALE_FLOATS) {
        double factors[12]={1.0,1.5,.5,.8,1.2,.1,.1,.4,.9,1.3,.5,.2};
        result.wide_dfs=1.0-(double)(owner == -1 ?
                            si(c,F_IP_TARGETTED) : owner)*.05;
        result.wide_sb=atmosphere ?
                       (double)c->u[F_BRIGHTNESS]/24.0 : 1.0;
        if (atmosphere && si(c,F_NIGHTZONE)) result.wide_dfs*=.5;
        if (owner > 2)
            result.wide_sb*=result.wide_dfs*result.wide_dfs;
        else
            result.wide_dfs=1.0;
        if (cls >= 0 && cls < 12) result.wide_dfs*=factors[cls];
        result.wide_saturation=
            1.0-.15*(double)bits_float(c->u[F_RAINY_BITS]);
        return result;
    }

    /* NOCTIS-1.CPP:2754-2792 declares these as float locals.  Preserve every
     * initializer, assignment, and compound-assignment store explicitly: a
     * host binary64 accumulator makes later palette values observably wrong. */
    result.dfs=sf(1.0-(double)(owner == -1 ?
                  si(c,F_IP_TARGETTED) : owner)*.05);
    result.sb=atmosphere ? sf((double)c->u[F_BRIGHTNESS]/24.0) : sf(1.0);
    if (atmosphere && si(c,F_NIGHTZONE))
        result.dfs=sf((double)result.dfs*.5);
    if (owner > 2)
        result.sb=sf_mul(result.sb,sf_mul(result.dfs,result.dfs));
    else
        result.dfs=sf(1.0);
    switch(cls) {
        case 0:  result.dfs=sf((double)result.dfs*1.0); break;
        case 1:  result.dfs=sf((double)result.dfs*1.5); break;
        case 2:  result.dfs=sf((double)result.dfs*.5); break;
        case 3:  result.dfs=sf((double)result.dfs*.8); break;
        case 4:  result.dfs=sf((double)result.dfs*1.2); break;
        case 5:  result.dfs=sf((double)result.dfs*.1); break;
        case 6:  result.dfs=sf((double)result.dfs*.1); break;
        case 7:  result.dfs=sf((double)result.dfs*.4); break;
        case 8:  result.dfs=sf((double)result.dfs*.9); break;
        case 9:  result.dfs=sf((double)result.dfs*1.3); break;
        case 10: result.dfs=sf((double)result.dfs*.5); break;
        case 11: result.dfs=sf((double)result.dfs*.2); break;
        default: break;
    }
    result.saturation=
        sf(1.0-.15*(double)bits_float(c->u[F_RAINY_BITS]));
    return result;
}

static void scale_colours(float fr[4], float fg[4], float fb[4],
                          int ptype, const ColourFactors *factors) {
    int k, j;
    float *bands[3]={fr,fg,fb};

    for (k=0;k<4;++k) for(j=0;j<3;++j)
        if (bands[j][k] < 0.0f) bands[j][k]=0.0f;
    if (SKY_MUT_WIDE_SCALE_FLOATS) {
        if (ptype == 3 || ptype == 5)
            for(k=0;k<4;++k) for(j=0;j<3;++j)
                bands[j][k]=sf(((double)bands[j][k]-.5)*
                               factors->wide_saturation+.5);
        for(j=0;j<3;++j) {
            bands[j][0]=sf((double)bands[j][0]*64.0*factors->wide_dfs);
            bands[j][1]=sf((double)bands[j][1]*64.0*
                           factors->wide_dfs*factors->wide_sb);
            bands[j][2]=sf((double)bands[j][2]*64.0*factors->wide_dfs);
            bands[j][3]=sf((double)bands[j][3]*64.0*factors->wide_dfs);
        }
        return;
    }
    if (ptype == 3 || ptype == 5)
        for(k=0;k<4;++k) for(j=0;j<3;++j)
            bands[j][k]=sf(((double)bands[j][k]-.5)*
                           (double)factors->saturation+.5);
    for(j=0;j<3;++j) {
        bands[j][0]=sf_mul(sf_mul(bands[j][0],64.0f),factors->dfs);
        bands[j][1]=sf_mul(sf_mul(sf_mul(bands[j][1],64.0f),
                                  factors->dfs),factors->sb);
        bands[j][2]=sf_mul(sf_mul(bands[j][2],64.0f),factors->dfs);
        bands[j][3]=sf_mul(sf_mul(bands[j][3],64.0f),factors->dfs);
    }
}

static float thermo(const SkyCase *c, LedgerRng *f) {
    double exposure=bits_float(c->u[F_EXPOSURE_BITS]);
    float temp=sf(90.0-(double)bits_float(c->u[F_DSD1_BITS])*.33);
    int atmosphere=si(c,F_ATMOSPHERE), night=si(c,F_NIGHTZONE);
    int guard=0, ptype=si(c,F_PTYPE), sctype=si(c,F_SCTYPE);
    int64_t delta=(int64_t)si(c,F_LAT)-60;
    if (delta < 0) delta=-delta;
    if (!atmosphere) {
        temp=sf((double)temp-44.0);
        temp=sf((double)temp*fabs((double)temp*.44));
        temp=sf((double)temp*(night ? .3 : .3+exposure*.0077));
    } else temp=sf((double)temp*(night ? .6 : .6+exposure*.0044));
    temp=sf((double)temp-(.5+.5*fast_flandom(f))*(double)delta);
    if (temp < -269.0f) temp=sf(-269.0+4.0*fast_flandom(f));
    if (ptype == 2) temp=sf((double)temp+fast_flandom(f)*150.0);
    if (ptype == 3) {
        double lo=-1e30, hi=1e30;
        if(sctype==OCEAN){lo=10;hi=60;} else if(sctype==PLAINS){lo=-10;hi=45;}
        else if(sctype==DESERT){lo=20;hi=80;} else if(sctype==ICY){lo=-120;hi=4;}
        while(temp<lo && guard++<100000) temp=sf((double)temp+fast_flandom(f)*5.0);
        while(temp>hi && guard++<100000) temp=sf((double)temp-fast_flandom(f)*5.0);
        if(guard>=100000){fprintf(stderr,"temperature convergence guard\n");exit(3);}
    }
    return temp;
}

static void put_u32(FILE *f, uint32_t v, int *failed) {
    uint8_t b[4]={(uint8_t)v,(uint8_t)(v>>8),(uint8_t)(v>>16),(uint8_t)(v>>24)};
    if (fwrite(b,1,4,f)!=4) *failed=1;
}

static void record_header(Writer *w, uint32_t kind, uint32_t width,
                          uint32_t height, uint32_t body_units,
                          uint32_t phase, uint32_t body_bytes) {
    uint32_t h[16]={SKY_MAGIC,SKY_VERSION,kind,width,height,body_units,
                    w->case_id,phase,body_bytes,w->sequence++,w->flags,0,0,0,0,0};
    unsigned i;
    for(i=0;i<16;++i) put_u32(w->f,h[i],&w->failed);
    w->records++;
}

static void record_units(Writer *w, uint32_t kind, uint32_t width,
                         uint32_t height, const uint32_t *body,
                         uint32_t units, uint32_t phase) {
    uint32_t i;
    record_header(w,kind,width,height,units,phase,units*4u);
    for(i=0;i<units;++i) put_u32(w->f,body[i],&w->failed);
}

static void record_bytes(Writer *w, uint32_t kind, uint32_t width,
                         uint32_t height, const uint8_t *body,
                         uint32_t bytes) {
    uint32_t units=(bytes+3u)/4u, i;
    record_header(w,kind,width,height,units,0,bytes);
    for(i=0;i<units;++i) {
        uint32_t p=i*4u, v=0, j;
        for(j=0;j<4u && p+j<bytes;++j) v|=(uint32_t)body[p+j]<<(8u*j);
        put_u32(w->f,v,&w->failed);
    }
}

static int load_file(const char *path, uint8_t **data, size_t *size) {
    FILE *f=fopen(path,"rb"); long n;
    if(!f){perror(path);return 0;} if(fseek(f,0,SEEK_END)||((n=ftell(f))<0)||fseek(f,0,SEEK_SET)){
        perror(path);fclose(f);return 0;}
    *data=(uint8_t*)malloc((size_t)n ? (size_t)n : 1); *size=(size_t)n;
    if(!*data || fread(*data,1,*size,f)!=*size){perror(path);fclose(f);free(*data);return 0;}
    fclose(f);return 1;
}

static int compose_page(const uint8_t *source, uint32_t map_bytes,
                        int32_t start, uint32_t shift,
                        const uint8_t *offsets, size_t offsets_n,
                        uint8_t page[PAGE_BYTES]) {
    uint8_t seg[SEG_BYTES]; uint16_t dx=(uint16_t)(shift+4u);
    uint16_t bp=(uint16_t)((uint32_t)start+4u); size_t i; memset(seg,0,sizeof seg);
    if(offsets_n != OFFSET_MAP_BYTES || map_bytes != OFFSET_MAP_BYTES ||
       (map_bytes&1u)){fprintf(stderr,"bad offsets.map length %lu/%u\n",
       (unsigned long)offsets_n,map_bytes);return 0;}
    for(i=0;i<map_bytes;i+=2) {
        uint16_t word=(uint16_t)(offsets[i]|((uint16_t)offsets[i+1]<<8));
        if(word>=64000u) bp=(uint16_t)(bp+(word-64000u));
        else {
            uint16_t di=(uint16_t)(word+dx);
            /* Delivered SP addresses the panorama through SSBG=RSBG-4,
             * while DOS BP starts at start+4.  The two fours cancel: BP 4
             * is logical source byte 0, not source byte 4. */
            uint8_t al=(bp>=4u && (uint32_t)(bp-4u)<ST_BYTES) ?
                       source[bp-4u] : 0;
            unsigned row,col;
            for(row=0;row<5;++row) for(col=0;col<5;++col)
                seg[(uint16_t)(di+320u*row+col)]=al;
            bp=(uint16_t)(bp+1u);
        }
    }
    memcpy(page,seg+4,PAGE_BYTES); return 1;
}

static int validate_case(const SkyCase *c) {
    uint32_t flags=c->u[F_FLAGS], i;
    if(c->u[F_OPCODE]!=1u || c->u[F_CASE_ID]==0u){fprintf(stderr,"bad opcode/case id\n");return 0;}
    if(flags&~KNOWN_FLAGS){fprintf(stderr,"case %u unknown flags\n",c->u[F_CASE_ID]);return 0;}
    if(c->u[F_ATMOSPHERE]>1u || c->u[F_NIGHTZONE]>1u || c->u[F_TAIL_MODE]>1u){fprintf(stderr,"case %u noncanonical boolean\n",c->u[F_CASE_ID]);return 0;}
    if((flags&PALETTE_UNDEFINED)&&(flags&GRADE_PALETTE)){fprintf(stderr,"case %u contradictory palette flags\n",c->u[F_CASE_ID]);return 0;}
    if(c->u[F_BG_BYTES]!=OFFSET_MAP_BYTES){fprintf(stderr,"case %u bad bg_bytes\n",c->u[F_CASE_ID]);return 0;}
    (void)i; return 1;
}

static int read_token(FILE *f, int64_t *out) {
    char tok[128], *end; long long v;
    if(fscanf(f,"%127s",tok)!=1)return 0;
    errno=0; v=strtoll(tok,&end,10);
    if(errno || *end || v<INT32_MIN || v>INT32_MAX){fprintf(stderr,"bad corpus token: %s\n",tok);return -1;}
    *out=(int64_t)v; return 1;
}

static int run_case(const SkyCase *c, Writer *wr, const uint8_t *offsets,
                    size_t offsets_n, const uint8_t *replay) {
    Workspace w; LedgerRng b={1,0,FNV_OFF}, f={0,0,FNV_OFF};
    PhaseLedger ledger[8]; uint8_t pre[ST_BYTES], srf[768]={0}, pal6[768]={0};
    uint32_t scalars[12], guards[10], qw=c->u[F_QUADWORDS], qw_before=qw;
    float fr[4]={0},fg[4]={0},fb[4]={0}, pressure=0.0f,temp;
    float br=sf(si(c,F_SKY_R)/64.0), bg=sf(si(c,F_SKY_G)/64.0), bb=sf(si(c,F_SKY_B)/64.0);
    float tr=sf(si(c,F_GND_R)/64.0), tg=sf(si(c,F_GND_G)/64.0), tb=sf(si(c,F_GND_B)/64.0);
    float al=(float)(si(c,F_ALBEDO)/64); int ptype=si(c,F_PTYPE),sctype=si(c,F_SCTYPE);
    int atmosphere=si(c,F_ATMOSPHERE),night=si(c,F_NIGHTZONE),defined=1,marked2=0;
    ColourFactors factors;
    uint8_t brightness=(uint8_t)c->u[F_BRIGHTNESS]; int j;
    ws_init(&w,brightness,c->u[F_TAIL_MODE],c->u[F_TAIL_SEED]);
    if(SKY_MUT_ATMOSPHERE_BUFFER) atmosphere=(w.data[0]!=0);
    factors=colour_factors(c,atmosphere);
    mark_phase(ledger,0,&w,&b,&f);
    brtl_seed(&b,SKY_MUT_WRONG_RNG_SEED?c->u[F_SURFACE_SEED]+1u:c->u[F_SURFACE_SEED]);
    fast_seed(&f,SKY_MUT_WRONG_RNG_SEED?c->u[F_SURFACE_SEED]+1u:c->u[F_SURFACE_SEED]);
    mark_phase(ledger,1,&w,&b,&f);

    if(ptype==1 || ptype==4) {
        if(ptype==4) pressure=sf(fast_flandom(&f)*.1);
        fr[0]=tr;fg[0]=tg;fb[0]=tb;fr[1]=fg[1]=fb[1]=1.5f;
        fr[2]=sf(2.0*fr[0]);fg[2]=sf(2.0*fg[0]);fb[2]=sf(2.0*fb[0]);
    } else if(ptype==2) {
        float *bands[3]={fr,fg,fb},base[3]={tr,tg,tb};
        fr[0]=sf(1.2-tr);fg[0]=sf(1.2-tg);fb[0]=sf(1.2-tb);
        for(j=0;j<3;++j){
            float a1=brtl_flandom(&b),z1=brtl_flandom(&b);
            float a2=brtl_flandom(&b),z2=brtl_flandom(&b);
            float a3=brtl_flandom(&b),z3=brtl_flandom(&b);
            bands[j][1]=sf(base[j]+a1*.15-z1*.15+.3);
            bands[j][2]=sf(base[j]+a2*.30-z2*.30+.2);
            bands[j][3]=sf(base[j]+a3*.45-z3*.45+.1);
        }
        mark_phase(ledger,2,&w,&b,&f);marked2=1;
        qw=ST_BYTES/4u;nebular_sky(&w,&b);if(!SKY_MUT_NO_QW_RESTORE)qw=qw_before;
        pressure=sf(fast_flandom(&f)*20.0+si(c,F_ALBEDO)+1.0);
    } else if(ptype==3) {
        fr[1]=sf(br*.5+.5*brtl_flandom(&b));fg[1]=sf(bg*.5+.5*brtl_flandom(&b));fb[1]=sf(bb*.5+.5*brtl_flandom(&b));
        if(sctype==OCEAN){
            fr[0]=sf(.65+.5*brtl_flandom(&b));fg[0]=sf(.45+.4*brtl_flandom(&b));fb[0]=sf(.25+.3*brtl_flandom(&b));
            if(fg[0]<.6)fg[0]=sf(fg[0]*2.0);
            fr[2]=sf(.8*brtl_flandom(&b));fg[2]=sf(.8*brtl_flandom(&b));fb[2]=sf(fb[0]*2.0+.4);
            fr[3]=sf(.2+brtl_flandom(&b));fg[3]=sf(.4+brtl_flandom(&b));fb[3]=sf(brtl_flandom(&b)*.6);
            mark_phase(ledger,2,&w,&b,&f);marked2=1;
            if(SKY_MUT_OCEAN_12_DRAWS)(void)brtl_flandom(&b);
            qw=ST_BYTES/4u;cloudy_sky(&w,&b,50,1,si(c,F_ALBEDO));if(!SKY_MUT_NO_QW_RESTORE)qw=qw_before;
        } else if(sctype==PLAINS){
            fr[0]=sf(.25+.5*brtl_flandom(&b));fg[0]=sf(.50+.4*brtl_flandom(&b));fb[0]=sf(.25+.3*brtl_flandom(&b));
            if(fg[0]<.75)fg[0]=sf(fg[0]*1.5);
            fr[2]=sf(brtl_flandom(&b)*.4+fr[0]*.3);fr[2]=sf(brtl_flandom(&b)*.7+fg[0]*.3);fr[2]=sf(brtl_flandom(&b)*.2+fb[0]*.3);
            fr[3]=brtl_flandom(&b);fg[3]=brtl_flandom(&b);fb[3]=brtl_flandom(&b);defined=0;
            mark_phase(ledger,2,&w,&b,&f);marked2=1;
            qw=ST_BYTES/4u;cloudy_sky(&w,&b,33,1,si(c,F_ALBEDO));if(!SKY_MUT_NO_QW_RESTORE)qw=qw_before;
        } else if(sctype==DESERT){
            fr[0]=sf(tr+brtl_flandom(&b)*.33);fg[0]=sf(tg+brtl_flandom(&b)*.25);fb[0]=sf(tb+brtl_flandom(&b)*.12);
            fr[2]=tr;fg[2]=tg;fb[2]=tb;fr[3]=sf(.5*brtl_flandom(&b));fg[3]=sf(.9*brtl_flandom(&b));fb[3]=sf(.4*brtl_flandom(&b));
            mark_phase(ledger,2,&w,&b,&f);marked2=1;
            qw=ST_BYTES/4u;cloudy_sky(&w,&b,10,1,si(c,F_ALBEDO));if(!SKY_MUT_NO_QW_RESTORE)qw=qw_before;
        } else if(sctype==ICY){
            fr[0]=sf(.25+brtl_flandom(&b));fg[0]=sf(.55+brtl_flandom(&b));fb[0]=sf(1.0+brtl_flandom(&b));
            fr[2]=sf(fr[0]*.6);fg[2]=sf(fg[0]*.8);fb[2]=fb[0];fr[3]=sf(.95*brtl_flandom(&b));fg[3]=sf(.95*brtl_flandom(&b));fb[3]=sf(.95*brtl_flandom(&b));
            mark_phase(ledger,2,&w,&b,&f);marked2=1;
            qw=ST_BYTES/4u;cloudy_sky(&w,&b,15,1,si(c,F_ALBEDO));if(!SKY_MUT_NO_QW_RESTORE)qw=qw_before;
        } else defined=0;
        pressure=sf(fast_flandom(&f)*.8+.6);
    } else if(ptype==5) {
        LedgerRng *colour_rng=SKY_MUT_WRONG_RNG_STREAM?&f:&b;
        fr[0]=sf(tr+.33*brtl_flandom(colour_rng)*al);fg[0]=sf(tg+.33*brtl_flandom(colour_rng)*al);fb[0]=sf(tb+.33*brtl_flandom(colour_rng)*al);
        fr[1]=sf(.8*tb+.2*brtl_flandom(colour_rng)*al);fg[1]=sf(.8*tg+.2*brtl_flandom(colour_rng)*al);fb[1]=sf(.8*tr+.2*brtl_flandom(colour_rng)*al);
        fr[2]=sf(.5+fr[0]*.5*al);fg[2]=sf(.5+fg[0]*.5*al);fb[2]=sf(.5+fb[0]*.5*al);
        if(!SKY_MUT_STALE_TYPE5_BRIGHTNESS)brightness=(uint8_t)(int)sf(brightness*.65);
        mark_phase(ledger,2,&w,&b,&f);marked2=1;
        if(SKY_MUT_TYPE5_9_DRAWS){(void)brtl_flandom(&b);(void)brtl_flandom(&b);(void)brtl_flandom(&b);}
        qw=ST_BYTES/4u;cloudy_sky(&w,&b,10,2,si(c,F_ALBEDO));if(!SKY_MUT_NO_QW_RESTORE)qw=qw_before;
        pressure=sf(fast_flandom(&f)*.05+.01);
    } else if(ptype==7 || ptype==8) {
        pressure=ptype==7?sf(fast_flandom(&f)*.02):sf(fast_flandom(&f)+.2);
        fr[0]=sf(tr+brtl_flandom(&b)*al);fg[0]=sf(tg+brtl_flandom(&b)*al);fb[0]=sf(tb+brtl_flandom(&b)*al);
        fr[1]=1.3f;fg[1]=1.4f;fb[1]=1.5f;fr[2]=sf(.5+fr[0]);fg[2]=sf(.5+fg[0]);fb[2]=sf(.5+fb[0]);
    } else defined=0;
    if(!marked2)mark_phase(ledger,2,&w,&b,&f);
    mark_phase(ledger,3,&w,&b,&f);
    scale_colours(fr,fg,fb,ptype,&factors);
    make_palette(srf,pal6,fr,fg,fb,atmosphere,night,ptype,defined);
    mark_phase(ledger,4,&w,&b,&f);
    temp=thermo(c,&f);mark_phase(ledger,5,&w,&b,&f);
    memcpy(pre,w.data,ST_BYTES);apply_horizon(&w,night);mark_phase(ledger,6,&w,&b,&f);
    if(SKY_MUT_SBG_OOB)ws_write(&w,ST_BYTES,0x5a);
    mark_phase(ledger,7,&w,&b,&f);

    scalars[0]=brightness;scalars[1]=float_bits(pressure);scalars[2]=float_bits(temp);
    scalars[3]=scalars[1];scalars[4]=scalars[2];scalars[5]=b.state;scalars[6]=f.state;
    scalars[7]=b.draws;scalars[8]=f.draws;scalars[9]=b.hash;scalars[10]=f.hash;scalars[11]=qw;
    guards[0]=w.min_write;guards[1]=w.max_write;guards[2]=w.writes;guards[3]=w.oob_writes;
    guards[4]=w.tail_before;guards[5]=fnv_bytes(w.data+ST_BYTES,TAIL_BYTES);
    guards[6]=w.canary_before;guards[7]=fnv_bytes(w.canary,sizeof w.canary);guards[8]=qw_before;guards[9]=qw;

    wr->case_id=c->u[F_CASE_ID];wr->flags=c->u[F_FLAGS];wr->sequence=0;
    record_units(wr,META,28,1,c->u+1,28,0);
    record_bytes(wr,PRE_HORIZON,360,180,pre,ST_BYTES);
    record_bytes(wr,FINAL_SBG,360,180,w.data,ST_BYTES);
    record_bytes(wr,PALETTE,256,1,srf,768);
    record_units(wr,SCALARS,12,1,scalars,12,0);
    for(j=0;j<8;++j)record_units(wr,LEDGER,8,1,ledger[j].v,8,(uint32_t)j);
    record_units(wr,GUARDS,10,1,guards,10,0);
    if(c->u[F_FLAGS]&GRADE_PAGE){
        uint8_t rp[PAGE_BYTES],jp[PAGE_BYTES];const uint8_t *rs=replay?replay:w.data;
        if(!compose_page(rs,c->u[F_BG_BYTES],si(c,F_BG_START),c->u[F_BG_SHIFT],offsets,offsets_n,rp))return 0;
        if(!compose_page(w.data,c->u[F_BG_BYTES],si(c,F_BG_START),c->u[F_BG_SHIFT],offsets,offsets_n,jp))return 0;
        record_bytes(wr,REPLAY_PAGE,320,200,rp,PAGE_BYTES);record_bytes(wr,JOIN_PAGE,320,200,jp,PAGE_BYTES);
    }
    record_header(wr,CASE_END,0,0,0,0,0);
    return !wr->failed;
}

int main(int argc,char **argv){
    const char *corpus,*output,*offset_path="work/offsets.map",*replay_path=NULL;
    FILE *in,*out;Writer wr;uint8_t *offsets=NULL,*replay=NULL;size_t offsets_n=0,replay_n=0;
    uint32_t cases=0;uint32_t ids[4096];int arg=3,terminated=0,rc=1;
    if(argc<3){fprintf(stderr,"usage: %s CORPUS OUTPUT [--offsets PATH] [--replay PATH]\n",argv[0]);return 2;}
    corpus=argv[1];output=argv[2];
    while(arg<argc){if(!strcmp(argv[arg],"--offsets")&&arg+1<argc){offset_path=argv[arg+1];arg+=2;}
        else if(!strcmp(argv[arg],"--replay")&&arg+1<argc){replay_path=argv[arg+1];arg+=2;}
        else{fprintf(stderr,"bad argument: %s\n",argv[arg]);return 2;}}
    if(!load_file(offset_path,&offsets,&offsets_n))goto done;
    if(replay_path){if(!load_file(replay_path,&replay,&replay_n)||replay_n!=ST_BYTES){fprintf(stderr,"replay must be exactly %u bytes\n",ST_BYTES);goto done;}}
    in=fopen(corpus,"rb");if(!in){perror(corpus);goto done;}out=fopen(output,"wb");if(!out){perror(output);fclose(in);goto done;}
    memset(&wr,0,sizeof wr);wr.f=out;
    for(;;){int64_t v;int tr=read_token(in,&v);SkyCase c;unsigned i;
        if(tr==0)break;
        if(tr<0)goto parse_fail;
        c.u[0]=(uint32_t)(int32_t)v;
        if(c.u[0]==0){int64_t extra;terminated=1;if(read_token(in,&extra)!=0){fprintf(stderr,"tokens after terminator\n");goto parse_fail;}break;}
        if(c.u[0]!=1){fprintf(stderr,"unknown opcode %u\n",c.u[0]);goto parse_fail;}
        for(i=1;i<29;++i){tr=read_token(in,&v);if(tr<=0){fprintf(stderr,"truncated 29-unit sky record\n");goto parse_fail;}c.u[i]=(uint32_t)(int32_t)v;}
        if(!validate_case(&c))goto parse_fail;
        if(cases>=4096){fprintf(stderr,"too many cases\n");goto parse_fail;}
        for(i=0;i<cases;++i)if(ids[i]==c.u[F_CASE_ID]){fprintf(stderr,"duplicate case id %u\n",c.u[F_CASE_ID]);goto parse_fail;}
        ids[cases++]=c.u[F_CASE_ID];if(!run_case(&c,&wr,offsets,offsets_n,replay))goto parse_fail;
    }
    if(!terminated){fprintf(stderr,"missing corpus terminator\n");goto parse_fail;}
    {uint32_t body[4]={cases,0,wr.records,0};wr.case_id=0;wr.flags=0;wr.sequence=0;record_units(&wr,STREAM_END,4,1,body,4,0);}
    if(wr.failed||fclose(out)){fprintf(stderr,"output write failed\n");fclose(in);goto done;}
    fclose(in);printf("sky_ref: %u cases, %u records -> %s\n",cases,wr.records,output);rc=0;goto done;
parse_fail:
    fclose(in);fclose(out);remove(output);
done:
    free(offsets);free(replay);return rc;
}
