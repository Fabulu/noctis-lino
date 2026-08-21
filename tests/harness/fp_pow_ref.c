/* Historical x87 witness for GR std crater's positive fractional power.
 *
 * The production implementation is ordinary Lino.  This test-only program
 * executes the exact old instruction sequence and exposes only its observable
 * binary32 result.  It deliberately does not call any C library power routine.
 */

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define IN_MAGIC  0x46505049u /* FPPI */
#define OUT_MAGIC 0x4650504fu /* FPPO */
#define VERSION   1u

struct header {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t units;
};

struct input_record {
    uint32_t type;
    uint32_t radius;
    uint32_t factor_index;
    uint32_t exponent_index;
    uint32_t d2;
};

struct output_record {
    uint32_t base_bits;
    uint32_t exponent_bits;
    uint32_t result_bits;
    uint32_t model_bits;
    uint32_t top_before;
    uint32_t top_after;
};

static void set_cw(uint16_t cw)
{
    __asm__ __volatile__("fldcw %0" : : "m"(cw));
}

static uint16_t get_cw(void)
{
    uint16_t cw;
    __asm__ __volatile__("fnstcw %0" : "=m"(cw));
    return cw;
}

static uint16_t get_sw(void)
{
    uint16_t sw;
    __asm__ __volatile__("fnstsw %0" : "=m"(sw));
    return sw;
}

static float scaled_integer(int32_t value, double scale)
{
    float result;
    __asm__ __volatile__(
        "fildl %1\n\t"
        "fmull %2\n\t"
        "fstps %0"
        : "=m"(result)
        : "m"(value), "m"(scale)
        : "st");
    return result;
}

static float crater_base(int32_t radius, int32_t d2, float factor)
{
    static const double pi = 0x1.921fb54442d18p+1;
    float distance;
    float float_radius;
    float height;
    float result;

    __asm__ __volatile__(
        "fildl %1\n\t"
        "fsqrt\n\t"
        "fstps %0"
        : "=m"(distance)
        : "m"(d2)
        : "st");
    __asm__ __volatile__(
        "fildl %1\n\t"
        "fstps %0"
        : "=m"(float_radius)
        : "m"(radius)
        : "st");
    __asm__ __volatile__(
        "fildl %1\n\t"
        "fmuls %2\n\t"
        "fstps %0"
        : "=m"(height)
        : "m"(radius), "m"(factor)
        : "st");
    __asm__ __volatile__(
        "fldl %1\n\t"
        "flds %2\n\t"
        "flds %3\n\t"
        ".byte 0xde,0xf9\n\t" /* fdivp st(1),st(0): distance/radius */
        ".byte 0xde,0xc9\n\t" /* fmulp st(1),st(0): pi*(distance/radius) */
        "fsin\n\t"
        "fmuls %4\n\t"
        "fstps %0"
        : "=m"(result)
        : "m"(pi), "m"(distance), "m"(float_radius), "m"(height)
        : "st");
    return result;
}

static float historical_power(float base, float exponent)
{
    float result;

    if (base == 0.0f)
        return 0.0f;

    __asm__ __volatile__(
        "flds %2\n\t"
        "flds %1\n\t"
        ".byte 0xd9,0xf1\n\t" /* fyl2x */
        ".byte 0xd9,0xc0\n\t" /* fld st(0) */
        ".byte 0xd9,0xfc\n\t" /* frndint */
        ".byte 0xdc,0xe9\n\t" /* fsub st(1),st(0) */
        ".byte 0xd9,0xc9\n\t" /* fxch st(1) */
        ".byte 0xd9,0xf0\n\t" /* f2xm1 */
        ".byte 0xd9,0xe8\n\t" /* fld1 */
        ".byte 0xde,0xc1\n\t" /* faddp st(1),st(0) */
        ".byte 0xd9,0xfd\n\t" /* fscale */
        ".byte 0xdd,0xd9\n\t" /* fstp st(1) */
        "fstps %0"
        : "=m"(result)
        : "m"(base), "m"(exponent)
        : "st");
    return result;
}

static inline long double ext_add(long double left, long double right)
{
    volatile long double result = left + right;
    return result;
}

static inline long double ext_sub(long double left, long double right)
{
    volatile long double result = left - right;
    return result;
}

static inline long double ext_mul(long double left, long double right)
{
    volatile long double result = left * right;
    return result;
}

static inline long double ext_div(long double left, long double right)
{
    volatile long double result = left / right;
    return result;
}

static long double ext_near(long double value)
{
    long double result;
    __asm__ __volatile__("frndint" : "=t"(result) : "0"(value));
    return result;
}

/* Operation-for-operation mathematical mirror of XPowPositive.  This is not
 * the authority: historical_power above is.  The deep test uses the mirror to
 * exhaust the large reachable domain, then checks its operation order against
 * compiled Lino on a bounded sensitive corpus. */
static float portable_model(float base, float exponent)
{
    static int initialized;
    static long double log_coefficients[15];
    static long double exp_coefficients[21];
    static const long double sqrt_two = 0x1.6a09e667f3bcc908p+0L;
    static const long double ln_two = 0x1.62e42fefa39ef358p-1L;
    static const long double two_over_ln_two = 0x1.71547652b82fe178p+1L;
    uint32_t image;
    uint32_t significand;
    int binary_exponent;
    int index;
    int integral;
    long double m;
    long double z;
    long double q;
    long double polynomial;
    long double value;
    long double nearest;
    long double fraction;
    volatile float rounded;

    if (base == 0.0f)
        return 0.0f;
    if (!initialized) {
        for (index = 0; index < 15; ++index)
            log_coefficients[index] = ext_div(1.0L, (long double)(2 * index + 1));
        exp_coefficients[0] = 1.0L;
        for (index = 1; index <= 20; ++index)
            exp_coefficients[index] = ext_div(
                exp_coefficients[index - 1], (long double)index);
        initialized = 1;
    }

    memcpy(&image, &base, sizeof(image));
    significand = (image & 0x007fffffu) | 0x00800000u;
    binary_exponent = (int)((image >> 23) & 0xffu) - 127;
    m = (long double)significand / 8388608.0L;
    if (m > sqrt_two) {
        m = ext_mul(m, 0.5L);
        ++binary_exponent;
    }

    z = ext_div(ext_sub(m, 1.0L), ext_add(m, 1.0L));
    q = ext_mul(z, z);
    polynomial = log_coefficients[14];
    for (index = 13; index >= 0; --index)
        polynomial = ext_add(ext_mul(polynomial, q), log_coefficients[index]);
    value = ext_add((long double)binary_exponent,
                    ext_mul(ext_mul(polynomial, z), two_over_ln_two));
    value = ext_mul(value, (long double)exponent);
    nearest = ext_near(value);
    integral = (int)nearest;
    fraction = ext_sub(value, nearest);

    value = ext_mul(fraction, ln_two);
    polynomial = exp_coefficients[20];
    for (index = 19; index >= 0; --index)
        polynomial = ext_add(ext_mul(polynomial, value), exp_coefficients[index]);
    value = ldexpl(polynomial, integral);
    rounded = (float)value;
    return rounded;
}

static uint32_t bits(float value)
{
    uint32_t result;
    memcpy(&result, &value, sizeof(result));
    return result;
}

int main(int argc, char **argv)
{
    FILE *input;
    FILE *output;
    struct header in_header;
    struct header out_header;
    struct input_record in;
    struct output_record out;
    uint16_t saved_cw;
    uint32_t index;

    if (argc != 3) {
        fprintf(stderr, "usage: fp_pow_ref INPUT OUTPUT\n");
        return 2;
    }
    input = fopen(argv[1], "rb");
    output = fopen(argv[2], "wb");
    if (!input || !output) {
        fprintf(stderr, "cannot open input or output\n");
        return 2;
    }
    if (fread(&in_header, sizeof(in_header), 1, input) != 1 ||
        in_header.magic != IN_MAGIC || in_header.version != VERSION ||
        in_header.units != 5) {
        fprintf(stderr, "bad input header\n");
        return 2;
    }

    out_header.magic = OUT_MAGIC;
    out_header.version = VERSION;
    out_header.count = in_header.count;
    out_header.units = 6;
    if (fwrite(&out_header, sizeof(out_header), 1, output) != 1)
        return 2;

    saved_cw = get_cw();
    set_cw(0x133f);
    for (index = 0; index < in_header.count; ++index) {
        float factor;
        float exponent;
        float base;
        float result;
        double factor_scale;
        double exponent_scale;

        if (fread(&in, sizeof(in), 1, input) != 1) {
            fprintf(stderr, "short input at record %u\n", index);
            return 2;
        }
        if (in.type == 1) {
            factor_scale = 0.01;
            exponent_scale = 0.075;
        } else if (in.type == 5) {
            factor_scale = 0.015;
            exponent_scale = 0.27;
        } else {
            fprintf(stderr, "unsupported type %u\n", in.type);
            return 2;
        }
        factor = scaled_integer((int32_t)in.factor_index, factor_scale);
        exponent = scaled_integer((int32_t)in.exponent_index, exponent_scale);
        base = crater_base((int32_t)in.radius, (int32_t)in.d2, factor);
        out.top_before = (get_sw() >> 11) & 7u;
        result = historical_power(base, exponent);
        out.top_after = (get_sw() >> 11) & 7u;
        out.base_bits = bits(base);
        out.exponent_bits = bits(exponent);
        out.result_bits = bits(result);
        out.model_bits = bits(portable_model(base, exponent));
        if (fwrite(&out, sizeof(out), 1, output) != 1)
            return 2;
    }
    set_cw(saved_cw);

    if (fgetc(input) != EOF) {
        fprintf(stderr, "trailing input bytes\n");
        return 2;
    }
    if (fclose(input) || fclose(output))
        return 2;
    return 0;
}
