/* Hosted x87 control-word probe for Intel macOS and Rosetta 2. */

#include <stdint.h>
#include <stdio.h>

#define LINO_FCW_MASK UINT16_C(0x0f3f)
#define LINO_FCW_DOUBLE UINT16_C(0x123f)
#define LINO_FCW_EXT UINT16_C(0x133f)

static uint16_t
read_fcw(void)
{
    uint16_t value;
    __asm__ volatile ("fnstcw %0" : "=m" (value));
    return value;
}

static void
write_fcw(const uint16_t value)
{
    __asm__ volatile ("fldcw %0" : : "m" (value));
}

int
main(void)
{
    const uint16_t original = read_fcw();
    uint16_t observed_double;
    uint16_t observed_ext;

    write_fcw(LINO_FCW_DOUBLE);
    observed_double = read_fcw();
    if ((observed_double & LINO_FCW_MASK) !=
        (LINO_FCW_DOUBLE & LINO_FCW_MASK)) {
        write_fcw(original);
        fprintf(stderr, "double FCW readback mismatch: %04x\n",
                (unsigned int) observed_double);
        return 1;
    }

    write_fcw(LINO_FCW_EXT);
    observed_ext = read_fcw();
    if ((observed_ext & LINO_FCW_MASK) !=
        (LINO_FCW_EXT & LINO_FCW_MASK)) {
        write_fcw(original);
        fprintf(stderr, "extended FCW readback mismatch: %04x\n",
                (unsigned int) observed_ext);
        return 1;
    }

    write_fcw(original);
    if (read_fcw() != original) {
        fprintf(stderr, "original FCW was not restored\n");
        return 1;
    }

    printf("FCW_HOST_PROBE_OK original=%04x double=%04x extended=%04x\n",
           (unsigned int) original, (unsigned int) observed_double,
           (unsigned int) observed_ext);
    return 0;
}
