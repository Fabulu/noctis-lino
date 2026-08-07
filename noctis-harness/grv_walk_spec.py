r"""grv_walk_spec.py - Wave 7b iperificie grid-walk reference.

PROVENANCE
----------
Transliterated VERBATIM from NOCTIS-1.CPP:1393-1471 (iperificie).  iperificie
walks the 200x200 ground grid in back-to-front PAINT ORDER (the quadrant chosen
by beta, the viewing yaw) and calls fragment(x, z) per tile.  This file grades
the CALL SEQUENCE -- the ordered list of (x, z) pairs -- which isolates the
traversal from fragment's rendering (graded separately in grv_grade.py).

VERBATIM FAITHFULNESS NOTES (latent source quirks reproduced, not fixed):
  * beta is normalised by a SINGLE `if (b<0) b += 360;` -- no mod-360, so
    beta >= 360 stays >= 360 and still selects a quadrant via the >= checks.
  * quadrant 4 (b in 225..315) line 1452 uses `ipfz - additional_quadrants`
    as the x-loop bound, not `ipfx - ...`.  In-game ipfx == ipfz almost always
    so the bug is invisible, but it is reproduced here exactly.
  * each z-row (quadrants 1/2) and each x-column (quadrants 3/4) makes TWO
    passes: 0..n-1 then 199..n, so the split point ipfx/ipfz is included once.

The sequence is packed one call per int32: x in bits 0..15, z in bits 16..31.
"""

ILEFT = 0
IRIGHT = 199
ITOP = 0
IBOT = 199


def iperificie_calls(ipfx, ipfz, beta, additional_quadrants):
    """Return the ordered list of (x,z) fragment calls, packed as int32
    (x | (z << 16)).  Mirrors NOCTIS-1.CPP:1393-1471 line for line."""
    b = beta
    if b < 0:
        b += 360
    out = []

    def emit(x, z):
        out.append((x & 0xFFFF) | ((z & 0xFFFF) << 16))

    if b < 45 or b >= 315:                          # quadrant 1 (-dz, facing -z)
        z = IBOT
        while z >= ipfz - additional_quadrants:
            x = ILEFT
            while x < ipfx:
                emit(x, z); x += 1
            x = IRIGHT
            while x >= ipfx:
                emit(x, z); x -= 1
            z -= 1
        return out
    if b >= 135 and b < 225:                        # quadrant 2 (+dz, facing +z)
        z = ITOP
        while z <= ipfz + additional_quadrants:
            x = ILEFT
            while x < ipfx:
                emit(x, z); x += 1
            x = IRIGHT
            while x >= ipfx:
                emit(x, z); x -= 1
            z += 1
        return out
    if b >= 45 and b < 135:                         # quadrant 3 (+dx, facing +x)
        x = ILEFT
        while x <= ipfx + additional_quadrants:
            z = IBOT
            while z > ipfz:
                emit(x, z); z -= 1
            z = ITOP
            while z <= ipfz:
                emit(x, z); z += 1
            x += 1
        return out
    # b >= 225 and b < 315                          # quadrant 4 (-dx, facing -x)
    x = IRIGHT
    while x >= ipfz - additional_quadrants:         # SOURCE BUG: ipfz, not ipfx
        z = IBOT
        while z > ipfz:
            emit(x, z); z -= 1
        z = ITOP
        while z <= ipfz:
            emit(x, z); z += 1
        x -= 1
    return out


def pack_sequence(ipfx, ipfz, beta, add):
    """Full dump record for one case: [count, call0, call1, ...] as int32."""
    seq = iperificie_calls(ipfx, ipfz, beta, add)
    return [len(seq)] + seq


if __name__ == "__main__":
    # smoke: one case per quadrant + the boundaries
    for beta in (0, 44, 45, 134, 135, 224, 225, 314, 315, 359, -1, 400):
        seq = iperificie_calls(100, 100, beta, 0)
        print("beta=%-4d count=%-6d first6=%s last4=%s" %
              (beta, len(seq), seq[:6], seq[-4:]))
