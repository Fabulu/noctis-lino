from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/limb-pointer-restoring-fsqrt-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
SOURCE = ROOT / "work/fp/fpsoft.txt"

EXPECTED_ACCEPTED_SHA256 = (
    "6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3")

OLD = b'''\t[srm0] = 0; [srm1] = 0; [srm2] = 0;\n\t[sqstep] = 0;\n    "XRoot restoring loop"\n\t( Consume the radicand's high pair and shift it left by two. )\n\tA = [srd3]; A > 30; E = A;\n\tA = [srd3]; A < 2; B = [srd2]; B > 30; A | B; [srd3] = A;\n\tA = [srd2]; A < 2; B = [srd1]; B > 30; A | B; [srd2] = A;\n\tA = [srd1]; A < 2; B = [srd0]; B > 30; A | B; [srd1] = A;\n\tA = [srd0]; A < 2; [srd0] = A;\n'''

NEW = b'''\t[srm0] = 0; [srm1] = 0; [srm2] = 0;\n\t( Process four contiguous 32-bit radicand limbs from high to low,\n\t  consuming sixteen high pairs from each limb. )\n\t[sqmh] = srd3; [sqml] = 16; [sqstep] = 4;\n    "XRoot restoring loop"\n\t( Consume the active limb's high pair and shift only that limb. )\n\tB = [sqmh]; A = [B]; E = A;\n\tA < 2; [B] = A;\n\tA = E; A > 30; E = A;\n'''

OLD_TAIL = b'''    "XRoot restoring next"\n\t[sqstep]+;\n\t? [sqstep] < 64 -> XRoot restoring loop;\n\n\t( Reproduce the accepted residual subtraction's low-limb equality\n'''

NEW_TAIL = b'''    "XRoot restoring next"\n\t[sqml]-;\n\t? [sqml] != 0 -> XRoot restoring loop;\n\t[sqstep]-;\n\t? [sqstep] = 0 -> XRoot restoring complete;\n\t[sqmh]-; [sqml] = 16;\n\t-> XRoot restoring loop;\n    "XRoot restoring complete"\n\n\t( Reproduce the accepted residual subtraction's low-limb equality\n'''

OLD_PAD = b'''\t( Unreachable footprint calibration: preserve downstream addresses. )\n\tA = 0; A = 0; A = 0; A = 0;\n'''

NEW_PAD = b'''\t( Unreachable footprint calibration: preserve downstream addresses. )\n\tA = 0; A = 0; A = 0; A = 0;\n\tA+; A+; A+; A+; A+; A+; A+; A+; A+;\n'''


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def transform(data):
    assert sha256(data) == EXPECTED_ACCEPTED_SHA256
    assert data.count(OLD) == 1
    assert data.count(OLD_TAIL) == 1
    assert data.count(OLD_PAD) == 1
    data = data.replace(OLD, NEW, 1)
    data = data.replace(OLD_TAIL, NEW_TAIL, 1)
    data = data.replace(OLD_PAD, NEW_PAD, 1)
    return data


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    candidate = transform(accepted)
    SOURCE.write_bytes(candidate)
    (EVIDENCE / "candidate/fpsoft.txt").write_bytes(candidate)
    print("accepted", sha256(accepted), len(accepted))
    print("candidate", sha256(candidate), len(candidate))
