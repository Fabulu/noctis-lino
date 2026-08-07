#!/usr/bin/env python3
"""svsm-run.py -- harness for svstarmap.exe (STARMAP.BIN search/append/tombstone)."""
import os, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_STARMAP = os.path.join(HERE, "STARMAP.BIN")


def build_test_files():
    raw = open(REAL_STARMAP, "rb").read()
    nrec = (len(raw) - 4) // 32
    picks = []
    for i in [0, 1, 10, 100, 500, 1000]:
        if i >= nrec: continue
        rec = raw[4 + i * 32: 4 + (i + 1) * 32]
        if rec[:8] == b"Removed:": continue
        picks.append((i, rec))
    n = len(picks)
    file_size = 4 + n * 32
    tst = struct.pack("<I", file_size)
    for _i, rec in picks: tst += rec
    open(os.path.join(HERE, "STARMAP.TST"), "wb").write(tst)
    cfg = struct.pack("<II", 0x56534D53, n + 1)
    for _i, rec in picks:
        cfg += struct.pack("<III", struct.unpack_from("<I", rec, 0)[0],
                           struct.unpack_from("<I", rec, 4)[0], rec[29])
    cfg += struct.pack("<III", 0, 0x40450000, 0x53)
    open(os.path.join(HERE, "SVSM.CFG"), "wb").write(cfg)
    return picks


def verify_output(picks):
    raw = open(os.path.join(HERE, "SVSM.OUT"), "rb").read()
    u = struct.unpack("<%dI" % (len(raw) // 4), raw)
    idx = 0
    magic = u[idx]; idx += 1
    nsrch = u[idx]; idx += 1
    assert magic == 0x56534D53, "bad magic"
    all_ok = True
    print("=== search results (%d searches) ===" % nsrch)

    for i, (rec_idx, rec) in enumerate(picks):
        found = u[idx]; idx += 1
        pos = u[idx]; idx += 1
        expected_pos = 4 + i * 32
        ok = found == 1 and pos == expected_pos
        if not ok: all_ok = False
        id_val = struct.unpack_from("<d", rec, 0)[0]
        name = rec[8:28].decode("ascii", errors="replace").rstrip()
        print("  search %d (rec#%d id=%.6f '%s' %c): found=%d pos=%d (expect %d) %s" % (
            i, rec_idx, id_val, name, chr(rec[29]), found, pos, expected_pos,
            "OK" if ok else "FAIL"))

    found = u[idx]; idx += 1
    pos = u[idx]; idx += 1
    ok = found == 0
    if not ok: all_ok = False
    print("  search %d (id=42.0 non-existent): found=%d %s" % (len(picks), found,
          "OK" if ok else "FAIL"))

    app_status = u[idx]; idx += 1
    ok = app_status == 1
    if not ok: all_ok = False
    print("\n=== append test ===")
    print("  status=%d %s" % (app_status, "OK" if ok else "FAIL"))

    tb_status = u[idx]; idx += 1
    ok = tb_status == 1
    if not ok: all_ok = False
    print("\n=== tombstone test ===")
    print("  status=%d %s" % (tb_status, "OK" if ok else "FAIL"))

    # Verify STARMAP.TST content directly
    tst = open(os.path.join(HERE, "STARMAP.TST"), "rb").read()
    expected_size = 4 + (len(picks) + 1) * 32
    ok = len(tst) == expected_size
    if not ok: all_ok = False
    print("  STARMAP.TST size: %d (expect %d) %s" % (len(tst), expected_size,
          "OK" if ok else "FAIL"))

    app_pos = 4 + len(picks) * 32
    app_rec = tst[app_pos:app_pos+32]
    got_id = struct.unpack_from("<d", app_rec, 0)[0]
    ok = got_id == 42.0
    if not ok: all_ok = False
    print("  appended record id: %.1f (expect 42.0) %s" % (got_id, "OK" if ok else "FAIL"))
    ok = app_rec[29] == 0x53
    if not ok: all_ok = False
    print("  appended record type: %c (expect S) %s" % (chr(app_rec[29]),
          "OK" if ok else "FAIL"))

    tb_bytes = tst[4:12]
    ok = tb_bytes == b"Removed:"
    if not ok: all_ok = False
    print("  tombstone bytes at rec 0: %s %s" % (repr(tb_bytes), "OK" if ok else "FAIL"))

    # Verify original records are unchanged (except rec 0 which was tombstoned)
    recs_ok = True
    for i, (rec_idx, rec) in enumerate(picks):
        orig_pos = 4 + i * 32
        got_rec = tst[orig_pos:orig_pos+32]
        if i == 0:
            # rec 0 was tombstoned: name bytes 8+ should be intact
            ok = got_rec[8:] == rec[8:]
        else:
            ok = got_rec == rec
        if not ok:
            recs_ok = False
            all_ok = False
            print("  original rec %d CORRUPTED!" % i)
    print("  original records intact (rec 0 tombstoned): %s" % ("OK" if recs_ok else "FAIL"))

    print("\nOVERALL: %s" % ("ALL PASS" if all_ok else "FAILURES"))
    return all_ok


def main():
    if not os.path.exists(REAL_STARMAP):
        print("ERROR: STARMAP.BIN not found"); return 1
    print("Building test files...")
    picks = build_test_files()
    print("  picked %d records" % len(picks))
    for fn in ["SVSM.OUT"]:
        p = os.path.join(HERE, fn)
        if os.path.exists(p): os.remove(p)
    print("Running svstarmap.exe...")
    r = subprocess.run([os.path.join(HERE, "svstarmap.exe")], cwd=HERE,
                       capture_output=True, timeout=30)
    print("  exit code: %d" % r.returncode)
    if not os.path.exists(os.path.join(HERE, "SVSM.OUT")):
        print("ERROR: SVSM.OUT not produced"); return 1
    ok = verify_output(picks)
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
