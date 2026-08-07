#include <stdio.h>
#include <stdint.h>
typedef int32_t i32;
typedef long double ld;
static double ident_i(i32 x, i32 y, i32 z) {
    ld t = (ld)x;
    t = t / (ld)100000.0;
    t = t * (ld)y;
    t = t / (ld)100000.0;
    t = t * (ld)z;
    t = t / (ld)100000.0;
    return (double)t;
}
int main(){
    double d = ident_i(-5497488, 5077519, 2856581);
    printf("ident = %.6g  sizeof(ld)=%zu\n", d, sizeof(ld));
    printf("plain: ((((x/1e5)*y)/1e5)*z)/1e5 = %.6g\n",
           ((((-5497488.0/100000.0)*5077519.0)/100000.0)*2856581.0)/100000.0);
    return 0;
}
