#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
typedef int32_t i32;
typedef int64_t i64;
typedef uint64_t u64;
typedef long double ld;
static void set_cw(unsigned short cw){__asm__ __volatile__("fldcw %0" : : "m"(cw));}
static double ident_i(i32 x, i32 y, i32 z){
    ld t=(ld)x; t/=(ld)100000.0; t*=(ld)y; t/=(ld)100000.0; t*=(ld)z; t/=(ld)100000.0;
    return (double)t;
}
int main(int argc,char**argv){
    set_cw(0x133F);
    i32 x=atol(argv[1]),y=atol(argv[2]),z=atol(argv[3]);
    double d=ident_i(x,y,z);
    u64 u; memcpy(&u,&d,8);
    printf("with set_cw: ident(%d,%d,%d)=%.6f  bits=%llx\n",x,y,z,d,(unsigned long long)u);
    set_cw(0x37F); /* default double */
    double d2=ident_i(x,y,z);
    printf("default cw: ident=%.6f\n",d2);
    return 0;
}
