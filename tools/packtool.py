"""packtool.py - read and decode a L.in.oleum CPU pack.

A CPU pack maps every (instruction, operand-class, register) combination onto
raw target machine code. The compiler computes an index and reads the record at
`index * alignment + 8`; there is no index table in the file.

Record format: raw opcode bytes interleaved with 4-byte ASCII placeholders
("ISMOs") naming an operand, terminated by a 2-byte terminator, then padding.

    Ix.y   immediate value of operand x, emitted as y bytes (y in {1,4})
    Dx.4   workspace displacement of operand x, in BYTES (unit index * 4)
    LxZ4   relative code address of operand x, adjusted by Z
           ('A'..'Z' = -13..+12; 'N' = 0, 'R' = +4)

Nothing here modifies anything. Decoding is the trust step: we re-encode every
record from its decoded form and require the result to be byte-identical to the
original file. Until that passes, any pattern we generate would be built on a
guess.

Usage:
    python packtool.py verify [pack]
    python packtool.py show <index> [count] [pack]
    python packtool.py find <hex-bytes> [pack]
"""

import sys

DEFAULT_PACK = r"C:\programmieren\linoleum\main\cpu\i386.bin"

I, D, L = ord("I"), ord("D"), ord("L")
DOT = ord(".")
DIGITS_XY = set(b"14")
DIGITS_OPERAND = set(b"123")


class Pack:
    def __init__(self, blob):
        self.blob = blob
        self.align = blob[0] or 256          # a stored 0 means 256
        self.ter = bytes(blob[4:6])
        self.bea = blob[6]
        self.acc = blob[7]
        body = len(blob) - 8
        if body % self.align:
            raise SystemExit(f"body {body} not a multiple of alignment {self.align}")
        self.count = body // self.align

    def raw(self, index):
        off = index * self.align + 8
        return self.blob[off : off + self.align]

    def offset(self, index):
        return index * self.align + 8


def is_ismo(w):
    """Does this 4-byte window name an operand rather than being opcode bytes?"""
    if len(w) < 4:
        return False
    a, b, c, d = w[0], w[1], w[2], w[3]
    if d not in DIGITS_XY or b not in DIGITS_OPERAND:
        return False
    if a in (I, D) and c == DOT:
        return True
    if a == L and ord("A") <= c <= ord("Z") and d == ord("4"):
        return True
    return False


def decode(record, ter):
    """-> (items, padding). items are ('op', int) or ('ismo', str)."""
    items = []
    i = 0
    n = len(record)
    while i < n:
        if record[i] == ter[0] and i + 1 < n and record[i + 1] == ter[1]:
            return items, record[i + 2 :]
        if is_ismo(record[i : i + 4]):
            items.append(("ismo", record[i : i + 4].decode("ascii")))
            i += 4
        else:
            items.append(("op", record[i]))
            i += 1
    raise ValueError("no terminator found in record")


def encode(items, padding, ter):
    out = bytearray()
    for kind, val in items:
        if kind == "op":
            out.append(val)
        else:
            out += val.encode("ascii")
    out += ter
    out += padding
    return bytes(out)


def render(items):
    parts = []
    for kind, val in items:
        parts.append(f"{val:02X}" if kind == "op" else f"<{val}>")
    return " ".join(parts)


def cmd_verify(pack):
    print(f"alignment {pack.align}   terminator {pack.ter!r}   "
          f"BEA 0x{pack.bea:02X}   ACC 0x{pack.acc:02X}")
    print(f"{pack.count} patterns, {len(pack.blob)} bytes "
          f"({pack.align} * {pack.count} + 8 = {pack.align * pack.count + 8})")

    bad = []
    undecodable = []
    ismos = {}
    for n in range(pack.count):
        raw = pack.raw(n)
        try:
            items, padding = decode(raw, pack.ter)
        except ValueError:
            undecodable.append(n)
            continue
        for kind, val in items:
            if kind == "ismo":
                ismos[val] = ismos.get(val, 0) + 1
        if encode(items, padding, pack.ter) != raw:
            bad.append(n)

    print()
    if undecodable:
        print(f"  {len(undecodable)} records had no terminator, first: {undecodable[:5]}")
    if bad:
        print(f"  ROUND-TRIP FAILED on {len(bad)} records, first: {bad[:5]}")
        for n in bad[:3]:
            print(f"    {n}: {pack.raw(n).hex()}")
        return 1
    if undecodable:
        return 1

    print(f"  all {pack.count} records decode and re-encode byte-identically")
    print(f"  distinct ISMOs: {len(ismos)}")
    for k in sorted(ismos, key=lambda k: -ismos[k])[:8]:
        print(f"    {k}  x{ismos[k]}")

    # Landmarks proven independently during reconnaissance. If the decoder is
    # right, these must read exactly as expected.
    print()
    print("  landmarks:")
    expect = {
        0:    ("=  A,imm",        "B8 <I2.4>"),
        1406: ("*  signed A,imm", "69 C0 <I2.4>"),
        2338: ("*' unsigned A,A", "52 F7 E0 5A"),
        5997: ("/% signed A,A",   "52 99 F7 F8 5A"),
    }
    ok = True
    for n, (label, want) in sorted(expect.items()):
        items, _ = decode(pack.raw(n), pack.ter)
        got = render(items)
        mark = "ok " if got == want else "BAD"
        if got != want:
            ok = False
        print(f"    [{mark}] idx {n:>5} @ {pack.offset(n):>7}  {label:<16} {got}")
        if got != want:
            print(f"           expected: {want}")
    return 0 if ok else 1


def cmd_show(pack, index, count):
    for n in range(index, min(index + count, pack.count)):
        raw = pack.raw(n)
        try:
            items, padding = decode(raw, pack.ter)
            body = render(items)
            pad = f"  [pad {len(padding)}]" if padding else ""
        except ValueError:
            body, pad = raw.hex(), "  [UNDECODABLE]"
        print(f"idx {n:>5} @ {pack.offset(n):>7}   {body}{pad}")


def cmd_find(pack, needle):
    want = bytes.fromhex(needle.replace(" ", ""))
    for n in range(pack.count):
        if pack.raw(n).startswith(want):
            items, _ = decode(pack.raw(n), pack.ter)
            print(f"idx {n:>5} @ {pack.offset(n):>7}   {render(items)}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    path = DEFAULT_PACK

    if cmd == "verify":
        if len(argv) > 2:
            path = argv[2]
        return cmd_verify(Pack(open(path, "rb").read()))
    if cmd == "show":
        index = int(argv[2])
        count = int(argv[3]) if len(argv) > 3 else 1
        if len(argv) > 4:
            path = argv[4]
        cmd_show(Pack(open(path, "rb").read()), index, count)
        return 0
    if cmd == "find":
        needle = argv[2]
        if len(argv) > 3:
            path = argv[3]
        cmd_find(Pack(open(path, "rb").read()), needle)
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
