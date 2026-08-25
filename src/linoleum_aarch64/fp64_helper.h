#ifndef LINOLEUM_AARCH64_FP64_HELPER_H
#define LINOLEUM_AARCH64_FP64_HELPER_H

#include <stdbool.h>
#include <stdint.h>

/* Exact x87 PC=64 arithmetic followed by an FSTP binary64 spill.  Arguments
 * and results are raw IEEE-754 bits, so the host floating-point environment is
 * deliberately not involved. */
enum {
    FLOAT_BINARY64_SUM = 3,
    FLOAT_BINARY64_DIFFERENCE = 4,
    FLOAT_BINARY64_PRODUCT = 5,
    FLOAT_BINARY64_QUOTIENT = 6,
    FLOAT_BINARY64_NEAREST_INT32 = 7,
    FLOAT_BINARY64_FROM_INT32 = 8,
    FLOAT_BINARY64_NARROW_BINARY32 = 9
};

#define FP64_SIGN UINT64_C(0x8000000000000000)
#define FP64_EXPONENT UINT64_C(0x7FF0000000000000)
#define FP64_FRACTION UINT64_C(0x000FFFFFFFFFFFFF)
#define FP64_QUIET UINT64_C(0x0008000000000000)
#define FP64_INDEFINITE UINT64_C(0xFFF8000000000000)

struct fp64_extended {
    bool sign;
    uint64_t significand;
    int exponent;
};

static bool fp64_is_nan(uint64_t bits)
{
    return (bits & FP64_EXPONENT) == FP64_EXPONENT &&
           (bits & FP64_FRACTION) != 0;
}

static bool fp64_is_infinity(uint64_t bits)
{
    return (bits & ~FP64_SIGN) == FP64_EXPONENT;
}

static bool fp64_is_zero(uint64_t bits)
{
    return (bits & ~FP64_SIGN) == 0;
}

static uint64_t fp64_propagate_nan(uint64_t left, uint64_t right)
{
    const bool left_nan = fp64_is_nan(left);
    const bool right_nan = fp64_is_nan(right);
    uint64_t chosen;

    if (!left_nan)
        chosen = right;
    else if (!right_nan)
        chosen = left;
    else if ((right & FP64_FRACTION) > (left & FP64_FRACTION) ||
             ((right & FP64_FRACTION) == (left & FP64_FRACTION) &&
              (right & FP64_SIGN) < (left & FP64_SIGN)))
        chosen = right;
    else
        chosen = left;
    return chosen | FP64_QUIET;
}

static unsigned fp64_leading_zeros(uint64_t value)
{
    unsigned count = 0;
    uint64_t bit = UINT64_C(1) << 63;

    while ((value & bit) == 0) {
        count++;
        bit >>= 1;
    }
    return count;
}

static unsigned fp64_u128_bit_length(__uint128_t value)
{
    const uint64_t high = (uint64_t) (value >> 64);

    if (high != 0)
        return 128U - fp64_leading_zeros(high);
    return 64U - fp64_leading_zeros((uint64_t) value);
}

static struct fp64_extended fp64_decode(uint64_t bits)
{
    const uint64_t fraction = bits & FP64_FRACTION;
    const unsigned encoded_exponent = (unsigned) ((bits >> 52) & UINT64_C(0x7FF));
    struct fp64_extended result;

    result.sign = (bits & FP64_SIGN) != 0;
    if (encoded_exponent != 0) {
        result.significand = (UINT64_C(0x0010000000000000) | fraction) << 11;
        result.exponent = (int) encoded_exponent - 1023;
    } else {
        const unsigned shift = fp64_leading_zeros(fraction);

        result.significand = fraction << shift;
        result.exponent = -1074 + (int) (63U - shift);
    }
    return result;
}

static struct fp64_extended fp64_normalize_p64(bool sign,
                                                __uint128_t magnitude,
                                                int scale)
{
    const unsigned length = fp64_u128_bit_length(magnitude);
    struct fp64_extended result;

    result.sign = sign;
    result.exponent = scale + (int) length - 1;
    if (length <= 64U) {
        result.significand = (uint64_t) magnitude << (64U - length);
    } else {
        const unsigned shift = length - 64U;
        __uint128_t quotient = magnitude >> shift;
        const __uint128_t remainder = magnitude - (quotient << shift);
        const __uint128_t half = ((__uint128_t) 1) << (shift - 1U);

        if (remainder > half ||
            (remainder == half && (quotient & 1U) != 0))
            quotient++;
        if (quotient == (((__uint128_t) UINT64_MAX) + 1U)) {
            result.significand = UINT64_C(0x8000000000000000);
            result.exponent++;
        } else {
            result.significand = (uint64_t) quotient;
        }
    }
    return result;
}

static uint64_t fp64_round_shift(uint64_t value, unsigned shift)
{
    uint64_t quotient;
    uint64_t remainder;
    uint64_t half;

    if (shift == 0)
        return value;
    quotient = value >> shift;
    remainder = value - (quotient << shift);
    half = UINT64_C(1) << (shift - 1U);
    if (remainder > half || (remainder == half && (quotient & 1U) != 0))
        quotient++;
    return quotient;
}

static uint64_t fp64_pack(struct fp64_extended value)
{
    const uint64_t sign = value.sign ? FP64_SIGN : 0;

    if (value.exponent >= -1022) {
        uint64_t significand = fp64_round_shift(value.significand, 11U);

        if (significand == UINT64_C(0x0020000000000000)) {
            significand = UINT64_C(0x0010000000000000);
            value.exponent++;
        }
        if (value.exponent > 1023)
            return sign | FP64_EXPONENT;
        return sign |
               ((uint64_t) (value.exponent + 1023) << 52) |
               (significand & FP64_FRACTION);
    } else {
        const int signed_shift = -value.exponent - 1011;
        uint64_t significand;

        if (signed_shift < 64) {
            significand = fp64_round_shift(value.significand,
                                           (unsigned) signed_shift);
        } else if (signed_shift == 64) {
            significand = value.significand > UINT64_C(0x8000000000000000) ?
                          1U : 0U;
        } else {
            significand = 0;
        }
        return sign | significand;
    }
}

static int fp64_compare_magnitude(struct fp64_extended left,
                                  struct fp64_extended right)
{
    if (left.exponent != right.exponent)
        return left.exponent < right.exponent ? -1 : 1;
    if (left.significand != right.significand)
        return left.significand < right.significand ? -1 : 1;
    return 0;
}

static uint64_t fp64_add_subtract(uint64_t left_bits, uint64_t right_bits,
                                  bool subtract)
{
    const bool left_nan = fp64_is_nan(left_bits);
    const bool right_nan = fp64_is_nan(right_bits);
    const bool right_sign = ((right_bits & FP64_SIGN) != 0) ^ subtract;
    const uint64_t effective_right =
        (right_bits & ~FP64_SIGN) | (right_sign ? FP64_SIGN : 0);
    const bool left_infinity = fp64_is_infinity(left_bits);
    const bool right_infinity = fp64_is_infinity(right_bits);
    const bool left_zero = fp64_is_zero(left_bits);
    const bool right_zero = fp64_is_zero(right_bits);
    struct fp64_extended left;
    struct fp64_extended right;
    struct fp64_extended big;
    struct fp64_extended small;
    unsigned difference;

    if (left_nan || right_nan)
        return fp64_propagate_nan(left_bits, right_bits);
    if (left_infinity && right_infinity) {
        if (((left_bits & FP64_SIGN) != 0) != right_sign)
            return FP64_INDEFINITE;
        return left_bits;
    }
    if (left_infinity)
        return left_bits;
    if (right_infinity)
        return effective_right;
    if (left_zero && right_zero) {
        if (((left_bits & FP64_SIGN) != 0) == right_sign)
            return right_sign ? FP64_SIGN : 0;
        return 0;
    }
    if (left_zero)
        return effective_right;
    if (right_zero)
        return left_bits;

    left = fp64_decode(left_bits);
    right = fp64_decode(right_bits);
    right.sign = right_sign;
    if (fp64_compare_magnitude(left, right) >= 0) {
        big = left;
        small = right;
    } else {
        big = right;
        small = left;
    }
    if (big.exponent == small.exponent &&
        big.significand == small.significand && big.sign != small.sign)
        return 0;

    difference = (unsigned) (big.exponent - small.exponent);
    if (difference <= 64U) {
        const __uint128_t aligned_big =
            (__uint128_t) big.significand << difference;
        const __uint128_t magnitude = big.sign == small.sign ?
            aligned_big + small.significand :
            aligned_big - small.significand;

        return fp64_pack(fp64_normalize_p64(
            big.sign, magnitude, big.exponent - 63 - (int) difference));
    }
    if (difference == 65U && big.sign != small.sign &&
        big.significand == UINT64_C(0x8000000000000000) &&
        small.significand > UINT64_C(0x8000000000000000)) {
        big.significand = UINT64_MAX;
        big.exponent--;
    }
    return fp64_pack(big);
}

static uint64_t fp64_multiply(uint64_t left_bits, uint64_t right_bits)
{
    const bool sign = ((left_bits ^ right_bits) & FP64_SIGN) != 0;
    const bool left_infinity = fp64_is_infinity(left_bits);
    const bool right_infinity = fp64_is_infinity(right_bits);
    const bool left_zero = fp64_is_zero(left_bits);
    const bool right_zero = fp64_is_zero(right_bits);
    struct fp64_extended left;
    struct fp64_extended right;
    __uint128_t product;

    if (fp64_is_nan(left_bits) || fp64_is_nan(right_bits))
        return fp64_propagate_nan(left_bits, right_bits);
    if ((left_infinity && right_zero) || (right_infinity && left_zero))
        return FP64_INDEFINITE;
    if (left_infinity || right_infinity)
        return (sign ? FP64_SIGN : 0) | FP64_EXPONENT;
    if (left_zero || right_zero)
        return sign ? FP64_SIGN : 0;

    left = fp64_decode(left_bits);
    right = fp64_decode(right_bits);
    product = (__uint128_t) left.significand * right.significand;
    return fp64_pack(fp64_normalize_p64(
        sign, product, left.exponent + right.exponent - 126));
}

static uint64_t fp64_divide(uint64_t left_bits, uint64_t right_bits)
{
    const bool sign = ((left_bits ^ right_bits) & FP64_SIGN) != 0;
    const bool left_infinity = fp64_is_infinity(left_bits);
    const bool right_infinity = fp64_is_infinity(right_bits);
    const bool left_zero = fp64_is_zero(left_bits);
    const bool right_zero = fp64_is_zero(right_bits);
    struct fp64_extended left;
    struct fp64_extended right;
    struct fp64_extended result;
    __uint128_t numerator;
    __uint128_t quotient;
    __uint128_t remainder;

    if (fp64_is_nan(left_bits) || fp64_is_nan(right_bits))
        return fp64_propagate_nan(left_bits, right_bits);
    if ((left_zero && right_zero) || (left_infinity && right_infinity))
        return FP64_INDEFINITE;
    if (left_infinity)
        return (sign ? FP64_SIGN : 0) | FP64_EXPONENT;
    if (right_infinity)
        return sign ? FP64_SIGN : 0;
    if (right_zero)
        return (sign ? FP64_SIGN : 0) | FP64_EXPONENT;
    if (left_zero)
        return sign ? FP64_SIGN : 0;

    left = fp64_decode(left_bits);
    right = fp64_decode(right_bits);
    result.sign = sign;
    if (left.significand >= right.significand) {
        numerator = (__uint128_t) left.significand << 63;
        result.exponent = left.exponent - right.exponent;
    } else {
        numerator = (__uint128_t) left.significand << 64;
        result.exponent = left.exponent - right.exponent - 1;
    }
    quotient = numerator / right.significand;
    remainder = numerator % right.significand;
    if ((remainder << 1) > right.significand ||
        ((remainder << 1) == right.significand && (quotient & 1U) != 0))
        quotient++;
    if (quotient == (((__uint128_t) UINT64_MAX) + 1U)) {
        result.significand = UINT64_C(0x8000000000000000);
        result.exponent++;
    } else {
        result.significand = (uint64_t) quotient;
    }
    return fp64_pack(result);
}

static uint32_t fp64_nearest_int32(uint64_t bits)
{
    const bool sign = (bits & FP64_SIGN) != 0;
    const unsigned encoded_exponent =
        (unsigned) ((bits >> 52) & UINT64_C(0x7FF));
    const uint64_t fraction = bits & FP64_FRACTION;
    uint64_t magnitude;
    int exponent;

    if (encoded_exponent == 0x7FFU)
        return UINT32_C(0x80000000);
    if (encoded_exponent == 0)
        return 0;
    exponent = (int) encoded_exponent - 1023;
    if (exponent < -1)
        return 0;
    if (exponent > 31)
        return UINT32_C(0x80000000);

    magnitude = fp64_round_shift(
        UINT64_C(0x0010000000000000) | fraction,
        (unsigned) (52 - exponent));
    if ((!sign && magnitude > UINT32_C(0x7FFFFFFF)) ||
        (sign && magnitude > UINT32_C(0x80000000)))
        return UINT32_C(0x80000000);
    return sign ? 0U - (uint32_t) magnitude : (uint32_t) magnitude;
}

static uint64_t fp64_from_int32(uint64_t bits)
{
    const uint32_t raw = (uint32_t) bits;
    const bool sign = (raw & UINT32_C(0x80000000)) != 0;
    const uint32_t magnitude = sign ? 0U - raw : raw;
    unsigned highest;
    uint64_t significand;

    if (magnitude == 0)
        return 0;
    highest = 63U - fp64_leading_zeros(magnitude);
    significand = (uint64_t) magnitude << (52U - highest);
    return (sign ? FP64_SIGN : 0) |
           ((uint64_t) (highest + 1023U) << 52) |
           (significand & FP64_FRACTION);
}

static uint32_t fp64_narrow_binary32_bits(uint64_t bits)
{
    const uint32_t sign = (uint32_t) (bits >> 32) & UINT32_C(0x80000000);
    const unsigned encoded_exponent =
        (unsigned) ((bits >> 52) & UINT64_C(0x7FF));
    const uint64_t fraction = bits & FP64_FRACTION;
    uint64_t significand;
    int exponent;

    if (encoded_exponent == 0x7FFU) {
        uint32_t result = sign | UINT32_C(0x7F800000);

        if (fraction != 0)
            result |= (uint32_t) (fraction >> 29) | UINT32_C(0x00400000);
        return result;
    }
    if (encoded_exponent == 0)
        return sign;

    exponent = (int) encoded_exponent - 1023;
    if (exponent > 127)
        return sign | UINT32_C(0x7F800000);
    significand = UINT64_C(0x0010000000000000) | fraction;
    if (exponent >= -126) {
        significand = fp64_round_shift(significand, 29U);
        if (significand == UINT64_C(0x01000000)) {
            significand >>= 1;
            exponent++;
        }
        if (exponent > 127)
            return sign | UINT32_C(0x7F800000);
        return sign |
               ((uint32_t) (exponent + 127) << 23) |
               ((uint32_t) significand & UINT32_C(0x007FFFFF));
    }
    if (exponent >= -150) {
        significand = fp64_round_shift(
            significand, (unsigned) (-exponent - 97));
        return sign | (uint32_t) significand;
    }
    return sign;
}

static uint64_t fp64_widen_binary32_bits(uint32_t bits)
{
    const uint64_t sign = (uint64_t) (bits & UINT32_C(0x80000000)) << 32;
    const unsigned encoded_exponent = (bits >> 23) & 0xFFU;
    const uint32_t fraction = bits & UINT32_C(0x007FFFFF);

    if (encoded_exponent == 0) {
        unsigned highest;
        int exponent;
        uint64_t significand;

        if (fraction == 0)
            return sign;
        highest = 63U - fp64_leading_zeros(fraction);
        exponent = (int) highest - 149;
        significand = (uint64_t) fraction << (52U - highest);
        return sign |
               ((uint64_t) (exponent + 1023) << 52) |
               (significand & FP64_FRACTION);
    }
    if (encoded_exponent == 0xFFU)
        return sign | FP64_EXPONENT | ((uint64_t) fraction << 29);
    return sign |
           ((uint64_t) (encoded_exponent + 896U) << 52) |
           ((uint64_t) fraction << 29);
}

static uint64_t fp64_narrow_binary32(uint64_t bits)
{
    return fp64_widen_binary32_bits(fp64_narrow_binary32_bits(bits));
}

static uint64_t apply_binary64(uint64_t left, uint64_t right,
                               uint32_t operation)
{
    switch (operation) {
    case FLOAT_BINARY64_SUM:
        return fp64_add_subtract(left, right, false);
    case FLOAT_BINARY64_DIFFERENCE:
        return fp64_add_subtract(left, right, true);
    case FLOAT_BINARY64_PRODUCT:
        return fp64_multiply(left, right);
    case FLOAT_BINARY64_QUOTIENT:
        return fp64_divide(left, right);
    case FLOAT_BINARY64_NEAREST_INT32:
        return fp64_nearest_int32(left);
    case FLOAT_BINARY64_FROM_INT32:
        return fp64_from_int32(left);
    case FLOAT_BINARY64_NARROW_BINARY32:
        return fp64_narrow_binary32(left);
    default:
        return left;
    }
}

#undef FP64_SIGN
#undef FP64_EXPONENT
#undef FP64_FRACTION
#undef FP64_QUIET
#undef FP64_INDEFINITE

#endif
