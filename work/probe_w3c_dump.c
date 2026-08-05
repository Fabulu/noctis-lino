/* Dump the PC=64 x87 chain result for each (x,y,z) so the pure-integer
 * emulation can be graded against REAL HARDWARE rather than against another
 * model of the same hardware. */
#include <stdio.h>
#include <string.h>
static void setcw(unsigned short cw){ __asm__ __volatile__("fldcw %0"::"m"(cw)); }
static double chain(double x,double y,double z){
    static const int E5C=100000; long double t;
    __asm__ __volatile__("fldl %1\n\t fidivl %4\n\t fmull %2\n\t fidivl %4\n\t"
                         "fmull %3\n\t fidivl %4\n\t fstpt %0\n\t"
                         :"=m"(t):"m"(x),"m"(y),"m"(z),"m"(E5C):"st");
    return (double)t;
}
int main(void){
    char line[256]; long long x,y,z; unsigned long long b;
    setcw(0x133F);
    while(fgets(line,sizeof line,stdin)){
        if(sscanf(line,"%lld %lld %lld",&x,&y,&z)!=3) continue;
        double v=chain((double)x,(double)y,(double)z);
        memcpy(&b,&v,8);
        printf("%016llx\n",b);
    }
    return 0;
}
