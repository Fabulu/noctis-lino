/* mg_ref.c -- Wave 8 Impl A C oracle for the Noctis IV main-loop numerical
 *             kernels: flight integrators, consumes, and the exact float
 *             sites that survive into the game loop.
 *
 * PROVENANCE
 * ----------
 * Transliterated from C:\programmieren\noctis\niv-plus\source :
 *   NOCTIS.CPP:2268-4485   the 22-phase do-while (the loop body)
 *   NOCTIS.CPP:3193-3263   ap_drive_mode  (vimana coefficient integrator)
 *   NOCTIS.CPP:3318-3363   ip_drive_mode  (approach coefficient integrator)
 *   NOCTIS.CPP:31-67       fix_remote_target / fix_local_target
 *   NOCTIS-0.CPP:6443-6486 additional_consumes (lithium drain / reserve)
 *   NOCTIS-0.CPP:5636-5726 isthere (the sector chop lives at 5649-5651)
 *   NOCTIS-0.CPP:4078      nearstar_identity = x/100000*y/100000*z/100000
 *   NOCTIS-0.CPP:3999-4041 search_id_code (the +/- idscale window)
 *   NOCTIS.CPP:2842        ap_target_id == nearstar_identity
 *   NOCTIS-1.CPP:3411-3413 backup_dzat_x/y/z float roundtrip (deliberate)
 *   NOCTIS.CPP:3948-4471   the keyboard switch (state-changing subset)
 *
 * FLOAT MODEL
 *   long double is the 80-bit x87 format on x86-64 MinGW, so every
 *   intermediate is rounded to a 64-bit significand by hardware, exactly as
 *   Borland's 16-bit build did at control word 133Fh (PC=64, RC=nearest).
 *   fsin/fcos are executed, not modelled.  (long) casts chop toward zero,
 *   matching __ftol.  pwr is a 16-bit signed int in the DOS build, so every
 *   store back into it is chop-then-wrap to int16; that is reproduced.
 *
 * NOT from noctis-iv-lr, which PLANPLAN disqualifies for these functions.
 *
 * Build:  gcc -O2 -fno-fast-math -o mg_ref.exe mg_ref.c -lm
 * Usage:  mg_ref.exe corpus.txt out.bin
 *
 * CORPUS  - flat signed decimal integers ('#' comments to EOL), the only
 *           lexeme.  binary64 inputs arrive as the signed decimal values of
 *           their two int32 halves (low then high), exactly as the lino
 *           driver and the Python spec see them.
 * OUT     - a flat little-endian int32 stream, one record per case; the
 *           layout per kind is documented beside each emitter below.  The
 *           Python spec and the lino port write the same stream.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

typedef int16_t   i16;
typedef uint16_t  u16;
typedef int32_t   i32;
typedef uint32_t  u32;
typedef uint64_t  u64;
typedef long double ld;

static const double DEGD = 3.14159265358979323846 / 180.0;
#define M_PI_D 3.14159265358979323846

/* ---- x87 control, matching Wave 3's measured 133Fh ------------------- */
static void set_cw(unsigned short cw) { __asm__ __volatile__("fldcw %0" : : "m"(cw)); }

/* Borland's (long) cast: __ftol, chop toward zero, keep the low 32 bits. */
static i32 ftol32(ld x) {
    long long t;
    if (x >= 9.2233720368547758e18L || x <= -9.2233720368547758e18L)
        t = (long long)0x8000000000000000ULL;
    else
        t = (long long)x;                       /* C truncates toward zero */
    return (i32)(u32)((u64)t & 0xFFFFFFFFULL);
}

/* i16 store: __ftol then keep low 16 bits, sign-extended.  pwr is int16. */
static i32 to_i16(i32 v) {
    v &= 0xFFFF;
    if (v >= 0x8000) v -= 0x10000;
    return v;
}

/* double <---> two int32 halves (low, high), bit-identical. */
static ld halves_to_ld(i32 lo, i32 hi) {
    u64 u = ((u64)(u32)hi << 32) | (u32)lo;
    ld d;
    memcpy(&d, &u, 8);       /* long double is 10 bytes on x86-64 but the
                                valid range of these values fits a double;
                                we work in double internally for the halves
                                round-trip and let the hardware widen. */
    double dd;
    u64 u2 = u;
    memcpy(&dd, &u2, 8);
    return (ld)dd;
}
/* emit a double as two int32 halves into the int32 stream */
static void emit_d(FILE *o, double d) {
    u64 u; memcpy(&u, &d, 8);
    i32 lo = (i32)(u32)(u & 0xFFFFFFFFULL);
    i32 hi = (i32)(u32)(u >> 32);
    fwrite(&lo, 4, 1, o); fwrite(&hi, 4, 1, o);
}
static void emit_i(FILE *o, i32 v) { fwrite(&v, 4, 1, o); }

/* =====================================================================
 * corpus tokeniser: flat signed decimals, '#' comments to EOL
 * ===================================================================== */
static i32 *gtok = NULL; static i32 gti = 0, gntok = 0;
static void tokenise(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = (char*)malloc(sz + 1);
    fread(buf, 1, sz, f); buf[sz] = 0; fclose(f);
    gtok = (i32*)malloc(sizeof(i32) * (sz / 2 + 16));
    gntok = 0; gti = 0;
    long i = 0;
    while (i < sz) {
        unsigned char c = buf[i];
        if (c == '#') { while (i < sz && buf[i] != '\n') i++; continue; }
        if (c == '-' || (c >= '0' && c <= '9')) {
            int neg = 0; long acc = 0; int any = 0;
            if (c == '-') { neg = 1; i++; }
            while (i < sz && buf[i] >= '0' && buf[i] <= '9') {
                acc = acc * 10 + (buf[i] - '0'); i++; any = 1;
            }
            if (any) { gtok[gntok++] = (i32)(neg ? -acc : acc); }
            continue;
        }
        i++;
    }
    free(buf);
}
static i32 tok(void) { return gti < gntok ? gtok[gti++] : 0; }
static i32 tokpeek_eof(void) { return gti < gntok ? 1 : 0; }
static double tok_d(void) { i32 lo = tok(), hi = tok(); return (double)halves_to_ld(lo, hi); }

/* status string id, so the cascade-window selection is byte-exact even
 * where the double trajectory is graded tolerant.  Ordered as in source. */
enum {
    ST_NONE = 0, ST_CHARGING, ST_PARKING, ST_LINKING, ST_DRIVING, ST_IGNITION,
    ST_CALIBRATED, ST_TRACKING, ST_WARMING, ST_REFINING, ST_BREAKING,
    ST_APPROACH, ST_STANDBY
};

/* =====================================================================
 * kernel 1 - ap_drive_mode (NOCTIS.CPP:3193-3263)
 * dzat, ap_target, dxx/dyy/dzz, l_dsd, coefficients all double; pwr i16.
 * ===================================================================== */
static void vimana(FILE *o) {
    i32 nframes = tok();
    double dzat_x = tok_d(), dzat_y = tok_d(), dzat_z = tok_d();
    double ap_target_x = tok_d(), ap_target_y = tok_d(), ap_target_z = tok_d();
    double ap_target_initial_d = tok_d();
    double cur_coef = tok_d();
    u32 ray_bits = (u32)tok();
    float ap_target_ray; memcpy(&ap_target_ray, &ray_bits, 4);
    i32 anti_rad = tok();
    i32 ap_targetted = tok();      /* 0 or 1 (1 = a fixed target) */
    i32 pwr = tok();

    i32 stspeed = 1, ap_reached = 0;
    double req_coef = cur_coef, rt = 0.01;
    double vimana_reaction_time = 0.01;

    for (i32 f = 0; f < nframes; f++) {
        i32 status_id = ST_NONE;
        double dxx = dzat_x - ap_target_x;
        double dyy = dzat_y - ap_target_y;
        double dzz = dzat_z - ap_target_z;
        double l_dsd = sqrt(dxx * dxx + dyy * dyy + dzz * dzz);

        if (!(ap_targetted || 0) || !stspeed) {   /* drive gated off */
            emit_d(o, dzat_x); emit_d(o, dzat_y); emit_d(o, dzat_z);
            emit_i(o, to_i16(pwr)); emit_d(o, cur_coef);
            emit_i(o, ap_reached); emit_i(o, status_id);
            continue;
        }

        double ras;
        if (ap_targetted == -1) ras = 25000.0;
        else {
            ras = anti_rad ? 44.0 * (double)ap_target_ray
                           : 1.5 * (double)ap_target_ray;
            /* (l_dsd < 20000 && nsnp) prepare_nearstar() -- does not feed
             * back into dzat/pwr/coef, so it is invisible to this kernel. */
        }

        if (l_dsd < ras) {
            status_id = ST_CALIBRATED;
            ap_reached = 1; stspeed = 0;
        } else {
            if (l_dsd > 0.9999 * ap_target_initial_d) {
                req_coef = 0.001 * l_dsd; rt = 0.1;
                status_id = ST_CHARGING;
            } else if (l_dsd < 7500.0 + ras) {
                req_coef = 0.005 * l_dsd; rt = 0.01;
                status_id = ST_PARKING;
            } else if (l_dsd < 15000.0 + ras) {
                req_coef = 0.005 * l_dsd; rt = 0.0025;
                status_id = ST_LINKING;
            } else if (l_dsd < 0.9990 * ap_target_initial_d) {
                req_coef = 0.00001 * l_dsd; rt = 0.05;
                status_id = ST_DRIVING;
            } else {
                req_coef = 0.0002 * l_dsd;
                status_id = ST_IGNITION;
                if (vimana_reaction_time != 0.08) vimana_reaction_time = 0.08;
                rt = vimana_reaction_time;
            }
            /* ap_drive_mode: */
            cur_coef += (req_coef - cur_coef) * rt;
            if (cur_coef < 10.0) cur_coef = 10.0;
            dzat_x -= dxx / cur_coef;
            dzat_y -= dyy / cur_coef;
            dzat_z -= dzz / cur_coef;
            pwr = to_i16(ftol32((ld)pwr - (ld)l_dsd * (ld)1e-5));
        }
        emit_d(o, dzat_x); emit_d(o, dzat_y); emit_d(o, dzat_z);
        emit_i(o, to_i16(pwr)); emit_d(o, cur_coef);
        emit_i(o, ap_reached); emit_i(o, status_id);
    }
}

/* =====================================================================
 * kernel 2 - ip_drive_mode (NOCTIS.CPP:3318-3363)
 * The target is plx/ply/plz (from planet_xyz, supplied here directly).
 * ===================================================================== */
static void approach(FILE *o) {
    i32 nframes = tok();
    double dzat_x = tok_d(), dzat_y = tok_d(), dzat_z = tok_d();
    double plx = tok_d(), ply = tok_d(), plz = tok_d();
    double ip_target_initial_d = tok_d();
    double cur_coef = tok_d();
    u32 ray_bits = (u32)tok();
    float nearstar_p_ray; memcpy(&nearstar_p_ray, &ray_bits, 4);
    i32 pwr = tok();
    i32 ip_reaching = tok();       /* expect 1 */

    i32 ip_reached = (ip_reaching == 0) ? 1 : 0;
    double req_coef = cur_coef, rt = 0.01;

    for (i32 f = 0; f < nframes; f++) {
        i32 status_id = ST_NONE;
        double dxx = dzat_x - plx;
        double dyy = dzat_y - ply;
        double dzz = dzat_z - plz;
        double l_dsd = sqrt(dxx * dxx + dyy * dyy + dzz * dzz);

        if (!ip_reaching) {
            emit_d(o, dzat_x); emit_d(o, dzat_y); emit_d(o, dzat_z);
            emit_i(o, to_i16(pwr)); emit_d(o, cur_coef);
            emit_i(o, ip_reached); emit_i(o, status_id);
            continue;
        }

        if (l_dsd > 0.99999 * ip_target_initial_d) {
            req_coef = 25.0 * l_dsd; rt = 0.001;    status_id = ST_WARMING;
        } else if (l_dsd < 25.0 && ip_target_initial_d > 500.0) {
            req_coef = 50.0 * l_dsd; rt = 0.0002;   status_id = ST_REFINING;
        } else if (l_dsd < 100.0 && ip_target_initial_d > 500.0) {
            req_coef = 15.0 * l_dsd; rt = 0.0003;   status_id = ST_BREAKING;
        } else if (l_dsd < 0.99500 * ip_target_initial_d) {
            req_coef = 0.05 * l_dsd; rt = 0.025;    status_id = ST_APPROACH;
        } else {
            req_coef = 1.5 * l_dsd; rt = 0.05;      status_id = ST_IGNITION;
        }
        /* ip_drive_mode: */
        cur_coef += (req_coef - cur_coef) * rt;
        if (cur_coef < 10.0) cur_coef = 10.0;
        dzat_x -= dxx / cur_coef;
        dzat_z -= dzz / cur_coef;
        dzat_y -= dyy / (0.5 * cur_coef);
        pwr = to_i16(ftol32((ld)pwr - (ld)l_dsd * (ld)0.5e-5));
        if (l_dsd < 2.0 * (double)nearstar_p_ray) {
            status_id = ST_STANDBY;
            ip_reaching = 0; ip_reached = 1;
        }
        emit_d(o, dzat_x); emit_d(o, dzat_y); emit_d(o, dzat_z);
        emit_i(o, to_i16(pwr)); emit_d(o, cur_coef);
        emit_i(o, ip_reached); emit_i(o, status_id);
    }
}

/* =====================================================================
 * kernel 3 - additional_consumes (NOCTIS-0.CPP:6443-6486), pure integer.
 * Per call: iqsecs advances to ceil(secs), then the modulus drains fire,
 * then the reserve logic at the bottom.  We run nticks calls, feeding a
 * monotonically rising secs so iqsecs chases it one step at a time.
 * ===================================================================== */
static void consumes(FILE *o) {
    i32 nticks = tok();
    i32 iqsecs = tok();
    double secs = tok_d();
    i32 ip_targetted = tok(), sync = tok(), ip_reached = tok();
    i32 pl_search = tok(), ilightv = tok(), field_amplificator = tok();
    i32 pwr = tok(), charge = tok();

    for (i32 t = 0; t < nticks; t++) {
        secs += 1.0;                       /* one simulation second elapses */
        if (iqsecs < (i32)secs) iqsecs = (i32)secs;

        if (ip_targetted > -1 && pwr > 15000) {
            if (ip_reached && sync) {
                if (sync == 1 && !(iqsecs % 29)) { pwr--; iqsecs++; }
                if (sync == 2 && !(iqsecs % 18)) { pwr--; iqsecs++; }
                if (sync == 3 && !(iqsecs % 58)) { pwr--; iqsecs++; }
                if (sync == 4 && !(iqsecs % 7))  { pwr--; iqsecs++; }
                if (sync == 5 && !(iqsecs % 33)) { pwr--; iqsecs++; }
            }
        }
        if (pl_search         && !(iqsecs % 155)) { pwr--; iqsecs++; }
        if (ilightv == 1      && !(iqsecs % 84))  { pwr--; iqsecs++; }
        if (field_amplificator&& !(iqsecs % 41))  { pwr--; iqsecs++; }

        if (pwr <= 15000) {
            if (charge > 0) {
                charge--; pwr = 20000;
            } else if (charge < 0) {
                pwr = 20000;             /* OMEGA cheat (charge < 0) */
            } else {
                pwr = 15000;             /* POWER LOSS: also zeroes stspeed,
                                          * ip_reaching and ip_targetted in
                                          * the original; those side-effects
                                          * are not emitted here -- see
                                          * mg_grade.py NOT-GRADED. */
            }
        }
        emit_i(o, to_i16(pwr)); emit_i(o, charge); emit_i(o, iqsecs);
    }
}

/* =====================================================================
 * kernel 4 - the sector-crossing chop (NOCTIS-0.CPP:5649-5651, sky:2808)
 *   sect = (long)((dzat - visible_sectors*50000) / 100000); sect *= 100000;
 * (long) chops toward zero.  Three axes.
 * ===================================================================== */
static void sector_chop(FILE *o) {
    double dzat_x = tok_d(), dzat_y = tok_d(), dzat_z = tok_d();
    i32 vs = tok();
    i32 sx = ftol32(((ld)dzat_x - (ld)vs * (ld)50000) / (ld)100000); sx *= 100000;
    i32 sy = ftol32(((ld)dzat_y - (ld)vs * (ld)50000) / (ld)100000); sy *= 100000;
    i32 sz = ftol32(((ld)dzat_z - (ld)vs * (ld)50000) / (ld)100000); sz *= 100000;
    emit_i(o, sx); emit_i(o, sy); emit_i(o, sz);
}

/* =====================================================================
 * kernel 5 - nearstar_identity / ap_target_id (NOCTIS-0.CPP:4078)
 *   id = x/100000*y/100000*z/100000   left-to-right, double.
 * Evaluated at >= double; Borland's 16-bit build kept the whole expression
 * in 80-bit ext on the x87 stack (one store, to the double).  We compute in
 * long double then store to double, matching that exactly.  This is the
 * NsIdentity chain Wave 4 pinned 4113/4113 against STARMAP.BIN.
 * ===================================================================== */
static double ident_i(i32 x, i32 y, i32 z) {
    /* The NsIdentity chain (Wave 4, pinned 4113/4113): five ops, one store,
     * left-associated exactly as C parses x/100000*y/100000*z/100000:
     *   ((((x/100000)*y)/100000)*z)/100000
     * Each op rounds to ext (64-bit significand) under CW 133Fh; the single
     * fstp qword rounds to binary64.  Coordinates are integer-valued, so
     * loading as int (fild) or double (fld) gives an identical ext value. */
    ld t = (ld)x;
    t = t / (ld)100000.0;
    t = t * (ld)y;
    t = t / (ld)100000.0;
    t = t * (ld)z;
    t = t / (ld)100000.0;
    return (double)t;
}
static void identity(FILE *o) {
    i32 x = tok(), y = tok(), z = tok();
    emit_d(o, ident_i(x, y, z));
}

/* =====================================================================
 * kernel 6 - ap_target_id == nearstar_identity (NOCTIS.CPP:2842)
 *   if (ap_reached && ap_target_id == nearstar_identity) l_dsd *= 0.01;
 * Two identities, an exact-bit == compare, and the consequence.
 * ===================================================================== */
static void identity_cmp(FILE *o) {
    i32 apx = tok(), apy = tok(), apz = tok();
    i32 nsx = tok(), nsy = tok(), nsz = tok();
    double ap_id = ident_i(apx, apy, apz);
    double ns_id = ident_i(nsx, nsy, nsz);
    i32 equal = (ap_id == ns_id);
    emit_d(o, ap_id); emit_d(o, ns_id); emit_i(o, equal);
}

/* =====================================================================
 * kernel 7 - the landing roundtrip (NOCTIS-1.CPP:3411-3413)
 *   float backup_dzat_x = dzat_x;  ...  dzat_x = backup_dzat_x;
 * double -> float -> double.  At ~3.8e6 a binary32 ULP is 0.25, so this
 * loses ~9 mantissa bits observably.  Reproduced verbatim (it is a bug by
 * design; preserving it is the requirement).
 * ===================================================================== */
static void landing_roundtrip(FILE *o) {
    double dzat_x = tok_d(), dzat_y = tok_d(), dzat_z = tok_d();
    float bx = (float)dzat_x; dzat_x = bx;
    float by = (float)dzat_y; dzat_y = by;
    float bz = (float)dzat_z; dzat_z = bz;
    emit_d(o, dzat_x); emit_d(o, dzat_y); emit_d(o, dzat_z);
}

/* =====================================================================
 * kernel 8 - the keyboard switch, state-changing subset
 * (NOCTIS.CPP:3948-4471, the active_screen==-1 path).  The input FIFO is an
 * ASCII stream where a NUL byte means "extended code follows".  This models
 * the keys that change navigational / device state; the big switch's other
 * arms (movie, snapshot, naming) are documented out of scope in mg_grade.
 * ===================================================================== */
static void key_switch(FILE *o) {
    i32 nkeys = tok();
    i32 sys = tok(), dev_page = tok(), s_command = tok();
    i32 about = tok(), graphics_menu_status = tok(), option_mouseLook = tok();
    i32 surlight = tok(), revcontrols = tok();
    i32 dlt_nav_beta = 0;      /* fixed-point /10, see emit */
    i32 lifter = 0;

    for (i32 k = 0; k < nkeys; k++) {
        i32 c = tok();
        i32 ext = 0;
        i32 status_id = ST_NONE;
        if (c == 0) { c = tok(); ext = 1; }

        if (ext) {
            if (c == 0x3B) { about = about ? 0 : 1; if (about) { graphics_menu_status = 0; } }
            else if (c == 0x3C) { graphics_menu_status = graphics_menu_status ? 0 : 1;
                                  if (graphics_menu_status) about = 0; }
            else if (c == 0x49) { /* PgUp open visor: openhuddelta=-5 (cosmetic) */ }
            else if (c == 0x51) { /* PgDn close visor */ }
            else if (c == 75) { dlt_nav_beta += 15; status_id = ST_NONE; } /* PITCH - R */
            else if (c == 77) { dlt_nav_beta -= 15; }                      /* PITCH - L */
            else if (c == 72) { lifter = -100; }
            else if (c == 80) { option_mouseLook = (option_mouseLook + 1) % 3; }
        } else {
            if (c == '5') { sys = 1; dev_page = 0; }
            else if (c == 'r') { sys = 2; dev_page = 0; }
            else if (c == 'd') { sys = 3; dev_page = 0; }
            else if (c == 'x') { sys = 4; dev_page = 0; }
            else if (c == '6') { s_command = 1; }
            else if (c == '7') { s_command = 2; }
            else if (c == '8') { s_command = 3; }
            else if (c == '9') { s_command = 4; }
            else if (c == '+' && surlight < 63) { surlight++; }
            else if (c == '-' && surlight > 10) { surlight--; }
        }
        emit_i(o, sys); emit_i(o, dev_page); emit_i(o, s_command);
        emit_i(o, about); emit_i(o, graphics_menu_status); emit_i(o, option_mouseLook);
        emit_i(o, surlight); emit_i(o, dlt_nav_beta); emit_i(o, lifter);
        emit_i(o, status_id);
    }
}

/* ===================================================================== */
int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s corpus.txt out.bin\n", argv[0]); return 2; }
    set_cw(0x133F);
    tokenise(argv[1]);
    FILE *o = fopen(argv[2], "wb");
    if (!o) { fprintf(stderr, "cannot write %s\n", argv[2]); return 2; }

    while (gti < gntok) {
        i32 kind = tok();
        switch (kind) {
            case 1: vimana(o); break;
            case 2: approach(o); break;
            case 3: consumes(o); break;
            case 4: sector_chop(o); break;
            case 5: identity(o); break;
            case 6: identity_cmp(o); break;
            case 7: landing_roundtrip(o); break;
            case 8: key_switch(o); break;
            default: /* ignore unknown */ break;
        }
    }
    fclose(o);
    return 0;
}
