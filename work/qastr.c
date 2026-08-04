#include <stdio.h>
#include <stdint.h>
static uint32_t fold_mul(int32_t a, int32_t b) {
    int64_t  r = (int64_t) a * (int64_t) b;
    return (uint32_t)(r >> 32) + (uint32_t)(r & 0xFFFFFFFFu);
}
static const uint32_t T[][3] = {
    {0xF784ACA0u, 0x00000000u, 0xF7386160u},
    {0xF79B9000u, 0x00000000u, 0x00B28720u},
    {0xF7B27360u, 0x00000000u, 0xF9009E40u},
    {0xF821D700u, 0x00000000u, 0x0686D660u},
    {0xF8342680u, 0x00000000u, 0x01206420u},
    {0xF793EEE0u, 0x06008F60u, 0x00000000u},
    {0xF79E9D40u, 0xF95C2BC0u, 0x00000000u},
    {0xF7D40520u, 0x08120A40u, 0x00000000u},
    {0xF821D700u, 0x02BC60E0u, 0x00000000u},
    {0xF8B76040u, 0x0178E460u, 0x00000000u},
    {0x00000000u, 0x00000000u, 0x00000000u},
    {0x00000001u, 0x00000001u, 0x00000001u},
    {0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu},
    {0x7FFFFFFFu, 0x7FFFFFFFu, 0x7FFFFFFFu},
    {0x80000000u, 0x80000000u, 0x80000000u},
    {0x80000000u, 0x00000000u, 0x80000000u},
    {0x80000000u, 0xFFFFFFFFu, 0x7FFFFFFFu},
    {0x7FFFFFFFu, 0x80000000u, 0xFFFFFFFFu},
    {0xFFFFFFFFu, 0x00000001u, 0x80000000u},
    {0x0001FFFFu, 0x00000000u, 0x00000000u},
    {0x00020000u, 0x00000000u, 0x00000000u},
    {0x0000C350u, 0x0000C350u, 0x0000C350u},
    {0xFFFF0000u, 0x0000FFFFu, 0x80000001u},
    {0x7FFFFFFEu, 0x00000002u, 0xFFFFFFFEu},
    {0xAAAAAAAAu, 0x55555555u, 0xCCCCCCCCu},
    {0x00000020u, 0xFFFFFFE0u, 0x00008000u},
    {0x7FFFFFFFu, 0x00000001u, 0x00000001u},
    {0x00000001u, 0x7FFFFFFFu, 0x00000001u},
    {0x00000001u, 0x00000001u, 0x7FFFFFFFu},
    {0x0000C350u, 0x00000000u, 0xFFFF3CB0u},
    {0x0000C350u, 0x00000007u, 0xFFFF3CB0u},
    {0x0000C350u, 0xFFFF3CB0u, 0xFFFF3CB0u},
};
int main(void) {
    FILE *o = fopen("qastrc.bin", "wb");
    int n = sizeof(T)/sizeof(T[0]);
    for (int i = 0; i < n; i++) {
        uint32_t sect_x = T[i][0], sect_y = T[i][1], sect_z = T[i][2];
        uint32_t sum_xz = sect_x + sect_z, flags = 0;
        uint32_t temp_x = (sum_xz & 0x1FFFFu) + sect_x;
        if (temp_x == 50000) flags |= 1u;
        temp_x -= 50000;
        uint32_t accum = fold_mul((int32_t)temp_x, (int32_t)sum_xz);
        uint32_t idk = sum_xz + accum;
        uint32_t temp_y = (accum & 0x1FFFFu) + sect_y;
        if (temp_y == 50000) flags |= 2u;
        temp_y -= 50000;
        accum = fold_mul((int32_t)temp_y, (int32_t)idk);
        uint32_t temp_z = (accum & 0x1FFFFu) + sect_z;
        if (temp_z == 50000) flags |= 4u;
        temp_z -= 50000;
        uint32_t netpos = temp_x + temp_y + temp_z;
        uint32_t rec[5] = { temp_x, temp_y, temp_z, netpos, flags };
        fwrite(rec, 4, 5, o);
    }
    fclose(o);
    printf("qastrc.bin: %d cases\n", n);
    return 0;
}
