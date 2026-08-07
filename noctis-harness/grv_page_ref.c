/* grv_page_ref.c -- Wave 7b framebuffer oracle for fragment -> polymap.
 *
 * Reuses pg_ref.c's polymap_project + polymap_edges + the camera model via
 * #include (with main renamed), so the projection/edge math is the SAME
 * Wave-6a-proven code the lino's PG polymap uses.  This file adds:
 *   - fragment's vertex + c1 computation for the pinned scene;
 *   - a TEX2 flat-fill of each triangle's [ipart,fpart) footprint with c1+1
 *     (matching polymap_span_row under uniform texel = 1);
 *   - the page dump.
 *
 * The scene, camera, surf bytes and c1 match work/fragpage.txt exactly.
 * The alfa angle tables are set from the SAME binary32 bit patterns the
 * lino hardcodes, so projection is bit-identical.
 *
 * Build: gcc -O2 -fno-fast-math -o grv_page_ref.exe grv_page_ref.c -lm
 * Run:   grv_page_ref.exe  -> writes grv-page-cref.bin (64000 int32 units)
 */

#define main pg_ref_main_unused
#include "pg_ref.c"
#undef main

#include <stdio.h>

#define WLIPFX 100
#define WLIPFZ 100
#define WLCAMX 1646592.0f
#define WLCAMZ 1646592.0f
#define WLCAMY (-100000.0f)
#define WGLO 95
#define WGHI 103

static unsigned char g_surf[40000];

/* the binary32 bit patterns work/fragpage.txt hardcodes for alfa = -90 deg */
#define COS90 0x00000000u   /* cos(90) = 0 (exact) */
#define SIN90 0xBF800000u   /* -sin(90) = -1 (exact) */
#define DPPC90 0x00000000u  /* dpp*0 = 0 */
#define DPPS90 0xC3520000u  /* dpp*(-1) = -210 */

static float bits_as_float(unsigned u) { float f; memcpy(&f, &u, 4); return f; }

static void set_angle_tables(void)
{
    opt_tcosbeta = 1.0f; opt_tsinbeta = 0.0f;
    opt_pcosbeta = dpp;  opt_psinbeta = 0.0f;
    opt_tcosalfa = bits_as_float(COS90);
    opt_tsinalfa = bits_as_float(SIN90);
    opt_pcosalfa = bits_as_float(DPPC90);
    opt_psinalfa = bits_as_float(DPPS90);
    opt_tcosgamma = 1.0f; opt_tsingamma = 0.0f;
}

static void render_triangle(float vx[4], float vy[4], float vz[4], int c1)
{
    TOPO T;
    int i;
    /* ol_end writes SPtinta (=c1) to the tinta scratch before the span */
    wr8(SCR_TINTA, (unsigned char)c1);
    polymap_project(vx, vy, vz, 3, &T);
    if (T.ret != 0 || T.nmp < 3) return;
    polymap_edges(T.mp, T.nmp, (int32_t)T.min_y, (int32_t)T.max_y);
    for (i = (int)T.min_y; i <= (int)T.max_y; i++) {
        int x;
        if (i < 0 || i >= MPIY) continue;
        for (x = ipart[i]; x < fpart[i]; x++) {
            unsigned o = (unsigned)(riga[i] + x);
            wr8(o, (unsigned char)(c1 + 1));
        }
    }
}

static void fragment_tile(int x, int z)
{
    long h1 = x + (long)z * 200;
    long s1 = g_surf[h1];
    long s2 = g_surf[h1 + 1];
    long s3 = g_surf[h1 + 201];
    long s4 = g_surf[h1 + 200];
    int c1 = (int)(s1 & 31);
    float vx1[4], vy1[4], vz1[4];
    float vx2[4], vy2[4], vz2[4];
    float fx = (float)(x << 14), fx1 = (float)((x + 1) << 14);
    float fz = (float)(z << 14), fz1 = (float)((z + 1) << 14);

    vy1[0] = -(float)(s1 << 11); vy1[1] = -(float)(s2 << 11); vy1[2] = -(float)(s4 << 11);
    vx1[0] = fx;  vz1[0] = fz;
    vx1[1] = fx1; vz1[1] = fz;
    vx1[2] = fx;  vz1[2] = fz1;
    vy2[0] = -(float)(s2 << 11); vy2[1] = -(float)(s3 << 11); vy2[2] = -(float)(s4 << 11);
    vx2[0] = fx1; vz2[0] = fz;
    vx2[1] = fx1; vz2[1] = fz1;
    vx2[2] = fx;  vz2[2] = fz1;

    render_triangle(vx1, vy1, vz1, c1);
    render_triangle(vx2, vy2, vz2, c1);
}

int main(void)
{
    int x, z, i;
    FILE *fo;
    initscanlines();
    memset(P, 0, sizeof P);
    memset(g_surf, 0, sizeof g_surf);

    /* place surf bytes: surf[h1]=((x*5+z)*7)&255, +17/+43/+91 at the corners */
    for (x = WGLO; x <= WGHI; x++)
        for (z = WGLO; z <= WGHI; z++) {
            long h1 = x + (long)z * 200;
            long b = (((long)x * 5 + z) * 7) & 255;
            g_surf[h1]     = (unsigned char)b;
            g_surf[h1 + 1] = (unsigned char)((b + 17) & 255);
            g_surf[h1 + 201] = (unsigned char)((b + 43) & 255);
            g_surf[h1 + 200] = (unsigned char)((b + 91) & 255);
        }

    /* camera: walker pos, dpp=210, uneg=100, beta=0, alfa=-55 (overridden) */
    cam_x = WLCAMX; cam_y = WLCAMY; cam_z = WLCAMZ;
    alfa = -55.0f; beta = 0.0f; gammaf = 0.0f;
    dpp = 210.0f; uneg = 100.0f;
    change_camera_lens();
    set_angle_tables();

    for (x = WGLO; x <= WGHI; x++)
        for (z = WGLO; z <= WGHI; z++)
            fragment_tile(x, z);

    fo = fopen("grv-page-cref.bin", "wb");
    if (!fo) { perror("open"); return 2; }
    for (i = 0; i < 64000; i++) {
        int32_t v = P[4 + i];
        fwrite(&v, 4, 1, fo);
    }
    fclose(fo);
    return 0;
}
