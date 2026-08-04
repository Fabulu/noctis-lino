"""buildpack.py - build an extended CPU pack containing the MUL-split block.

Append-only. The pattern index the compiler computes is a running sum over
earlier records, so adding records at the END leaves every existing index
untouched and the original 299,576 bytes byte-identical. Nothing that compiles
today can compile differently against the new pack.

The output is written under a NEW NAME (i386m.bin). The pack name is a
per-invocation command-line argument, so the stock and extended toolchains
coexist and the compiler's exact size check can never strand us:

    algn * patterns + 8 == filesize

Order follows the existing precedent for split-divide, where the unsigned form
(/%') precedes the signed (/%): unsigned block first, then signed.

    6241 existing + 121 unsigned + 121 signed = 6483 patterns
    48 * 6483 + 8 = 311,192 bytes
"""

import sys

sys.path.insert(0, ".")
from genmul import enumerate_block, emit  # noqa: E402
from packtool import Pack, decode, encode  # noqa: E402

SRC = r"C:\programmieren\linoleum\main\cpu\i386.bin"
DST = r"C:\programmieren\linoleum\tools\i386m.bin"
ALIGN = 48


def block_bytes(signed):
    return b"".join(emit(code) for _, _, _, _, code, _ in enumerate_block(signed))


def main():
    original = open(SRC, "rb").read()
    pack = Pack(original)
    print(f"source pack: {pack.count} patterns, {len(original)} bytes")

    unsigned = block_bytes(False)
    signed = block_bytes(True)
    n_new = (len(unsigned) + len(signed)) // ALIGN
    print(f"appending: {len(unsigned)//ALIGN} unsigned + {len(signed)//ALIGN} signed"
          f" = {n_new} patterns")

    out = original + unsigned + signed
    total = pack.count + n_new
    expect = ALIGN * total + 8

    # The header's pattern count is implied by file size, so nothing in the
    # first eight bytes changes.
    assert out[:8] == original[:8], "header must be untouched"
    assert out[:len(original)] == original, "existing patterns must be untouched"
    assert len(out) == expect, f"size {len(out)} != {expect}"

    open(DST, "wb").write(out)
    print(f"\nwrote {DST}")
    print(f"  {total} patterns, {len(out)} bytes  (48 * {total} + 8 = {expect})")
    print(f"  first {len(original)} bytes byte-identical to the stock pack")

    # The new pack must satisfy the same decoder the compiler's interpreter
    # implements: every record decodes and re-encodes byte-identically.
    new = Pack(open(DST, "rb").read())
    bad = 0
    for n in range(new.count):
        raw = new.raw(n)
        try:
            items, padding = decode(raw, new.ter)
        except ValueError:
            bad += 1
            continue
        if encode(items, padding, new.ter) != raw:
            bad += 1
    if bad:
        print(f"  ROUND-TRIP FAILED on {bad} records")
        return 1
    print(f"  all {new.count} records decode and re-encode byte-identically")

    print("\n  main/cpu/i386.bin is unchanged; this is a separate file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
