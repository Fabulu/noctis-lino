#!/usr/bin/env python3
"""w8b-all.py -- Wave 8 Impl B: run all three deliverables and summarise.

svsave    : CURRENT.BIN + SURFACE.BIN freeze/unfreeze + hidden evolution
svstarmap : STARMAP.BIN search_id_code + append + tombstone
clconsole : GOES console CLR + COMM.BIN protocol
"""
import os, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RECON = os.path.join(ROOT, "tests", "gen", "recon_w7b", "dos", "data")


def run(name, args=None):
    exe = os.path.join(HERE, "%s.exe" % name)
    if not os.path.exists(exe):
        return False, "exe not found"
    r = subprocess.run([exe], cwd=HERE, capture_output=True, timeout=30)
    return r.returncode == 0, "exit %d" % r.returncode


def test_svsave():
    """CURRENT.BIN + SURFACE.BIN round-trip + layout + evolution."""
    print("\n" + "="*60)
    print("SVSAVE: CURRENT.BIN + SURFACE.BIN")
    print("="*60)
    # Copy recon data
    for fn in ["CURRENT.BIN", "SURFACE.BIN"]:
        src = os.path.join(RECON, fn)
        dst = os.path.join(HERE, fn)
        if os.path.exists(src):
            import shutil; shutil.copy2(src, dst)

    ok, msg = run("svsave")
    if not ok:
        print("  RUN FAIL:", msg); return False

    # Verify round-trip
    cur = open(os.path.join(HERE, "CURRENT.BIN"), "rb").read()
    rt = open(os.path.join(HERE, "SVSAVE.RT"), "rb").read()
    surf = open(os.path.join(HERE, "SURFACE.BIN"), "rb").read()
    srt = open(os.path.join(HERE, "SVSAVE.SRT"), "rb").read()

    results = []
    results.append(("CURRENT.BIN round-trip", cur == rt))
    results.append(("SURFACE.BIN round-trip", surf == srt))

    # Verify field extraction
    out = open(os.path.join(HERE, "SVSAVE.OUT"), "rb").read()
    u = struct.unpack("<%dI" % (len(out)//4), out)
    results.append(("magic", u[0] == 0x56535653))
    # pwr@27 = u[10]
    pwr = struct.unpack_from("<h", cur, 27)[0]
    results.append(("pwr=%d" % pwr, u[10] == pwr))
    # charge@6 = u[5]
    charge = cur[6]
    results.append(("charge=%d" % charge, u[5] == charge))
    # dzat_x double = u[24..25]
    dx_lo = struct.unpack_from("<I", cur, 71)[0]
    dx_hi = struct.unpack_from("<I", cur, 75)[0]
    results.append(("dzat_x double", u[24] == dx_lo and u[25] == dx_hi))
    # secs double = u[30..31]
    s_lo = struct.unpack_from("<I", cur, 235)[0]
    s_hi = struct.unpack_from("<I", cur, 239)[0]
    results.append(("secs double", u[30] == s_lo and u[31] == s_hi))
    # hidden evolution: pwr_out=u[37], chg_out=u[38]
    results.append(("evo pwr 12000->17000", u[37] == 17000))
    results.append(("evo chg 2->1", u[38] == 1))

    allok = True
    for name, ok in results:
        print("  %-35s %s" % (name, "OK" if ok else "FAIL"))
        if not ok: allok = False
    return allok


def test_svstarmap():
    """STARMAP.BIN search/append/tombstone."""
    print("\n" + "="*60)
    print("SVSTARMAP: STARMAP.BIN search/append/tombstone")
    print("="*60)
    # Run the starmap harness
    r = subprocess.run([sys.executable, os.path.join(HERE, "svsm-run.py")],
                       cwd=HERE, capture_output=True, text=True, timeout=30)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr[-200:] if r.stderr else "")
        return False
    return "ALL PASS" in r.stdout


def test_clconsole():
    """GOES CLR + COMM.BIN protocol."""
    print("\n" + "="*60)
    print("CLCONSOLE: GOES CLR + COMM.BIN protocol")
    print("="*60)
    for fn in ["GOESFILE.TXT", "COMM.BIN", "CLCON.OUT"]:
        p = os.path.join(HERE, fn)
        if os.path.exists(p): os.remove(p)

    ok, msg = run("clconsole")
    if not ok:
        print("  RUN FAIL:", msg); return False

    out = open(os.path.join(HERE, "CLCON.OUT"), "rb").read()
    u = struct.unpack("<%dI" % (len(out)//4), out)
    results = []
    results.append(("magic", u[0] == 0x434C4F53))
    flags = u[1]
    results.append(("CLR (delete GOESFILE.TXT)", bool(flags & 1)))
    results.append(("COMM.BIN 2-byte protocol", bool(flags & 2)))
    results.append(("COMM.BIN 24-byte protocol", bool(flags & 4)))
    results.append(("CLR command parse", bool(flags & 8)))
    results.append(("COMM2 readback=5", u[3] == 5))
    x = struct.unpack("<d", struct.pack("<II", u[4], u[5]))[0]
    results.append(("COMM24 x=100.0", x == 100.0))

    allok = True
    for name, ok in results:
        print("  %-35s %s" % (name, "OK" if ok else "FAIL"))
        if not ok: allok = False
    return allok


def main():
    print("Wave 8 Impl B: SAVES + STARMAP + CONSOLE")
    print("Repository: C:\\programmieren\\linoleum")

    all_ok = True
    if not test_svsave(): all_ok = False
    if not test_svstarmap(): all_ok = False
    if not test_clconsole(): all_ok = False

    print("\n" + "="*60)
    print("OVERALL: %s" % ("ALL PASS" if all_ok else "FAILURES"))
    print("="*60)
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
