# Checks, by exhaustive / large-sample simulation, the two claims that decide
# whether the split-multiply instruction is load-bearing:
#
#   CLAIM A  The "imul ax / add ax,dx" PRNG idiom (surface, load_starface,
#            nebular_sky) is 16x16 -> 32 and is reproducible with nothing but a
#            plain 32-bit signed multiply.  Checked exhaustively over all 65536
#            16-bit seeds x all relevant cx, sampled.
#
#   CLAIM B  fast_random genuinely consumes bits 32..39 of a 32x32 product, so a
#            low-32-only multiply cannot reproduce it.  Checked by running both
#            and counting divergences.

M16 = 0xFFFF
M32 = 0xFFFFFFFF


def s16(v):
    v &= M16
    return v - 0x10000 if v & 0x8000 else v


# ---------------- CLAIM A ----------------
# DOS: ax = seed; loop { add ax,cx ; imul ax ; add ax,dx ; bl = al & 0x3E }
# "imul ax" is one-operand: dx:ax = ax * ax, signed, 16x16 -> 32.

def ref_step(ax, cx):
    ax = (ax + cx) & M16
    p = s16(ax) * s16(ax)          # exact 32-bit product, dx:ax
    lo = p & M16
    hi = (p >> 16) & M16
    return (lo + hi) & M16


def lino_step(ax, cx):
    # What a Lino port would do with the native 32-bit signed '*' only:
    # sign-extend to 32, multiply, split with a shift. No 64-bit product.
    ax = (ax + cx) & M16
    a = s16(ax)
    p = (a * a) & M32              # native 32-bit result is already exact
    lo = p & M16
    hi = (p >> 16) & M16
    return (lo + hi) & M16


bad = 0
for cx in (64800, 64000, 32768, 1, 65535, 12345):
    for ax in range(0x10000):
        if ref_step(ax, cx) != lino_step(ax, cx):
            bad += 1
print("CLAIM A  16x16 PRNG: mismatches over %d cases = %d" % (6 * 0x10000, bad))
# also prove the product never exceeds 32 bits
worst = max(abs(s16(a) * s16(a)) for a in (0x8000, 0x7FFF))
print("         worst |product| = %d, fits in 32 bits: %s" % (worst, worst < 2 ** 31))


# ---------------- CLAIM B ----------------
# DOS fast_random: eax = edx = seed ; mul edx ; add al, dl ; seed += eax

def fast_random_ref(seed, mask):
    eax = seed & M32
    edx = seed & M32
    r = (eax * edx) & 0xFFFFFFFFFFFFFFFF   # unsigned 64
    eax = r & M32
    edx = (r >> 32) & M32
    al = (eax & 0xFF)
    dl = (edx & 0xFF)
    al = (al + dl) & 0xFF                  # 8-bit add, no carry out
    eax = (eax & 0xFFFFFF00) | al
    seed = (seed + eax) & M32
    return seed, eax & mask


def fast_random_low32only(seed, mask):
    # The best a port can do with only the low 32 bits: pretend the high half
    # is zero. Everything else identical.
    eax = seed & M32
    r = (eax * eax) & M32
    al = r & 0xFF                          # dl would be 0
    eax = (r & 0xFFFFFF00) | al
    seed = (seed + eax) & M32
    return seed, eax & mask


s1 = s2 = 12345 | 3
div = 0
first = None
for i in range(200000):
    s1, v1 = fast_random_ref(s1, 0xFFFF)
    s2, v2 = fast_random_low32only(s2, 0xFFFF)
    if v1 != v2:
        div += 1
        if first is None:
            first = (i, v1, v2)
print("CLAIM B  fast_random: divergences in 200000 draws = %d" % div)
print("         first divergence at draw %s (ref=%s, low32only=%s)" % (first or ("none",) * 3))

# How many bits of the high half does it actually need?
print("         high-half bits consumed: 32..39 only (add al, dl is 8-bit)")


# ---------------- CLAIM C ----------------
# If *% is rejected, the high half is still reachable in pure L.in.oleum with
# four 16-bit-limb products, all of which fit in 32 bits, and NO carry flag --
# carries are propagated by explicit >>16, which Lino has. This is the fallback
# an implementer would write if the language extension is dropped.

def mul64_emulated_unsigned(x, y):
    x &= M32
    y &= M32
    xl, xh = x & M16, x >> 16
    yl, yh = y & M16, y >> 16
    p0 = (xl * yl) & M32          # each partial fits in 32 bits unsigned
    p1 = (xl * yh) & M32
    p2 = (xh * yl) & M32
    p3 = (xh * yh) & M32
    mid = (p0 >> 16) + (p1 & M16) + (p2 & M16)
    lo = (p0 & M16) | ((mid & M16) << 16)
    hi = (p3 + (p1 >> 16) + (p2 >> 16) + (mid >> 16)) & M32
    return lo & M32, hi


def mul64_emulated_signed(x, y):
    lo, hi = mul64_emulated_unsigned(x, y)
    if x & 0x80000000:
        hi = (hi - (y & M32)) & M32
    if y & 0x80000000:
        hi = (hi - (x & M32)) & M32
    return lo, hi


import random
random.seed(7)
cases = [(0, 0), (1, 1), (M32, M32), (0x80000000, 0x80000000),
         (0x7FFFFFFF, 0x7FFFFFFF), (0x80000000, 1), (M32, 1),
         (0xFFFF0000, 0x0000FFFF), (0x12345678, 0x9ABCDEF0)]
cases += [(random.getrandbits(32), random.getrandbits(32)) for _ in range(300000)]

bad_u = bad_s = 0
for x, y in cases:
    ref = (x * y) & 0xFFFFFFFFFFFFFFFF
    lo, hi = mul64_emulated_unsigned(x, y)
    if lo != (ref & M32) or hi != (ref >> 32):
        bad_u += 1
    sx = x - 0x100000000 if x & 0x80000000 else x
    sy = y - 0x100000000 if y & 0x80000000 else y
    refs = (sx * sy) & 0xFFFFFFFFFFFFFFFF
    lo, hi = mul64_emulated_signed(x, y)
    if lo != (refs & M32) or hi != (refs >> 32):
        bad_s += 1
print("CLAIM C  pure-32-bit emulation over %d pairs: unsigned bad=%d signed bad=%d"
      % (len(cases), bad_u, bad_s))
print("         cost: 4 multiplies + ~10 shift/and/add, no carry flag needed")
