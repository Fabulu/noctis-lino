#!/usr/bin/env python
"""
bx_w2.py -- Wave 2 decoder, Implementer 2 (ndisasm / symbol-name route).

    python bx_w2.py --binary NOCTIS.EXE --dl DL.EXE --st ST.EXE

Emits one JSON object on stdout, nothing else, exit 0.
Every number is recomputed from the bytes on every run.  Nothing is cached,
nothing is compared against a stored answer, and no path is read that was
not passed on the command line.

Route, in order (see bx_ndis.py for why each step is what it is):
  1. Parse the Borland debug symbol table trailing DL.EXE and ST.EXE and look
     up @zrandom$qi / @random$qi / N_FTOL@ / _rand / _srand BY NAME.
  2. Sweep each named body with ndisasm in its own (near-model) program.
  3. Turn each body into a masked byte signature -- call slots, frame
     displacements, absolute data displacements and the ret opcode wildcarded,
     because DL/ST are near model and the target is far model.
  4. Transfer the signatures into the target.  DL and ST must agree.
  5. Derive rand as the callee of the single call inside the located random,
     then VERIFY that body multiplies by 0x015A4E35 and adds 1.
  6. Census by linear ndisasm sweep of the code region, reading call targets
     out of the decoded stream.
  7. Classify float arguments forward from the decoded stream.
"""

import argparse
import datetime
import hashlib
import json
import struct
import sys

import bx_ndis as N

WANT = ['@zrandom$qi', '@random$qi', 'N_FTOL@', '_rand', '_srand']
KEY = {'@zrandom$qi': 'zrandom', '@random$qi': 'random', 'N_FTOL@': 'ftol',
       '_rand': 'rand', '_srand': 'srand'}
PUSHREG = {0x50: 'ax', 0x51: 'cx', 0x52: 'dx', 0x53: 'bx',
           0x54: 'sp', 0x55: 'bp', 0x56: 'si', 0x57: 'di'}
POPREG = {0x58: 'ax', 0x59: 'cx', 0x5A: 'dx', 0x5B: 'bx',
          0x5C: 'sp', 0x5D: 'bp', 0x5E: 'si', 0x5F: 'di'}
R16 = ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di']
RC = {0: 'NEAREST', 1: 'DOWN', 2: 'UP', 3: 'CHOP'}


def fail(stage, detail, extra=None):
    out = {"status": "LOCATION_FAILED", "failed_stage": stage, "detail": detail,
           "decoder": {"id": "bx", "engine": "ndisasm",
                       "engine_version": N.engine_version(),
                       "route": "borland-symtab-name -> masked-signature transfer -> ndisasm linear sweep",
                       "insns_decoded": N.STATS["insns"],
                       "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}}
    if extra:
        out.update(extra)
    print(json.dumps(out))
    sys.exit(0)


def dgroup_paragraph(path, hdrlen, size):
    """Borland's C0 startup opens with  mov dx,DGROUP."""
    rows = N.sweep(path, hdrlen, min(size, hdrlen + 16), size)
    if rows and rows[0][1][:1] == b'\xba' and len(rows[0][1]) == 3:
        return struct.unpack_from('<H', rows[0][1], 1)[0]
    for f, b, t in rows:
        if b[:1] == b'\xba' and len(b) == 3:
            return struct.unpack_from('<H', b, 1)[0]
    return None


def modrm_regs(mb):
    return R16[(mb >> 3) & 7], R16[mb & 7]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--binary', required=True)
    ap.add_argument('--dl')
    ap.add_argument('--st')
    a = ap.parse_args()

    data = open(a.binary, 'rb').read()
    size = len(data)
    lay = N.mz_layout(data)
    hdrlen = lay['hdrlen']

    # ---- 1..4  locate by transferred signature ---------------------------
    donors = [p for p in (a.dl, a.st) if p]
    if not donors:
        fail('donors', 'no --dl/--st symbol donor supplied')
    per_donor = {}
    for dp in donors:
        syms, dlay, ddata = N.borland_symbols(dp)
        if syms is None:
            fail('symtab', 'no Borland symbol table in %s' % dp)
        missing = [w for w in WANT if w not in syms]
        if missing:
            fail('symbol-lookup', 'names absent from %s symbol table: %s' % (dp, ','.join(missing)))
        found = {}
        for w in WANT:
            seg, off = syms[w]
            f = N.sym_file_offset(dlay, seg, off)
            body = N.sweep_body(dp, f, len(ddata))
            if not body or not body[-1][2].startswith('ret'):
                fail('donor-body', '%s: %s at %d has no terminating ret' % (dp, w, f))
            items = N.build_sig(body)
            hit = N.locate(data, items, hdrlen, size)
            if hit is None:
                fail('signature-transfer', 'signature for %s from %s did not match uniquely' % (w, dp))
            found[KEY[w]] = hit          # (start, end, cost)
        per_donor[dp] = found
    ref = per_donor[donors[0]]
    for dp in donors[1:]:
        for k in ref:
            if per_donor[dp][k][0] != ref[k][0]:
                fail('donor-disagreement', '%s puts %s at %d, %s puts it at %d'
                     % (donors[0], k, ref[k][0], dp, per_donor[dp][k][0]))
    ENT = {k: v[0] for k, v in ref.items()}
    rev = {v: k for k, v in ENT.items()}

    # ---- bodies ----------------------------------------------------------
    bodies = {k: N.sweep_body(a.binary, ENT[k], size) for k in ENT}
    zr, rnd, ft, rd = bodies['zrandom'], bodies['random'], bodies['ftol'], bodies['rand']
    zr_end = zr[-1][0] + len(zr[-1][1])
    rnd_end = rnd[-1][0] + len(rnd[-1][1])

    dgp = dgroup_paragraph(a.binary, hdrlen, size)
    if dgp is None:
        fail('dgroup', 'startup does not begin with mov dx,DGROUP')
    dgroup_file = hdrlen + dgp * 16
    code_end = min(dgroup_file, size)

    def far_target(b):
        off, seg = struct.unpack_from('<HH', b, 1)
        return hdrlen + seg * 16 + off

    # ---- 5  rand, derived from random's single call, then verified -------
    inner = [(f, b, t) for f, b, t in rnd if (b[0] == 0x9A and len(b) == 5) or (b[0] == 0xE8 and len(b) == 3)]
    if len(inner) != 1:
        fail('random-callee', 'random body contains %d calls, expected 1' % len(inner))
    f, b, t = inner[0]
    if b[0] == 0x9A:
        derived_rand = far_target(b)
    else:
        rel = struct.unpack_from('<h', b, 1)[0]
        derived_rand = f + 3 + rel
        if not (hdrlen <= derived_rand < code_end):
            derived_rand += 65536
    if derived_rand != ENT['rand']:
        fail('rand-crosscheck', 'random calls %d but the _rand signature landed at %d'
             % (derived_rand, ENT['rand']))
    rdtext = ' '.join(t for _, _, t in rd)
    lcg_ok = ('mov dx,0x15a' in rdtext and 'mov ax,0x4e35' in rdtext
              and 'add ax,0x1' in rdtext and 'adc dx,byte +0x0' in rdtext)
    if not lcg_ok:
        fail('lcg-verify', 'body at %d does not compute seed*0x015A4E35+1: %s' % (ENT['rand'], rdtext))

    # ---- 6  census, from the decoded stream ------------------------------
    stream = N.sweep(a.binary, hdrlen, code_end, size)
    census = {k: {'far': [], 'pushcs': [], 'near': []} for k in ENT}
    calls = []
    for i, (f, b, t) in enumerate(stream):
        site = f
        tf = None
        kind = None
        if b[0] == 0x9A and len(b) == 5:
            tf, kind = far_target(b), 'far'
        elif b[0] == 0xE8 and len(b) == 3:
            rel = struct.unpack_from('<h', b, 1)[0]
            c = [f + 3 + rel + k * 65536 for k in (-1, 0, 1)]
            c = [x for x in c if abs(x - f) < 65536 and hdrlen <= x < code_end]
            hit = [x for x in c if x in rev]
            if len(hit) == 1:
                tf = hit[0]
                pv = stream[i - 1] if i else (0, b'', '')
                if pv[1] == b'\x0e' and pv[0] + 1 == f:
                    kind, site = 'pushcs', pv[0]
                else:
                    kind = 'near'
        if tf is None or tf not in rev:
            continue
        census[rev[tf]][kind].append(site)
        calls.append((i, site, kind, rev[tf]))

    def cen(k):
        c = census[k]
        s = sorted(c['far'] + c['pushcs'] + c['near'])
        return {'far': len(c['far']), 'pushcs': len(c['pushcs']) + len(c['near']),
                'total': len(s), 'sites': s}

    # ---- 7  float-argument classification, forward over the stream -------
    fp_sites = []
    nonftol = []
    for i, site, kind, callee in calls:
        if callee not in ('random', 'zrandom'):
            continue
        j = i - 1
        while j >= 0 and stream[j][1] in (b'\x90', b'\x0e'):
            j -= 1
        pf, pb, pt = stream[j] if j >= 0 else (0, b'', '')
        if len(pb) != 1 or pb[0] not in PUSHREG:
            continue
        k = j - 1
        while k >= 0 and stream[k][1] == b'\x90':
            k -= 1
        qf, qb, qt = stream[k] if k >= 0 else (0, b'', '')
        qt_far = qb[0] == 0x9A and len(qb) == 5 and far_target(qb) == ENT['ftol']
        qt_near = False
        if qb[0] == 0xE8 and len(qb) == 3:
            rel = struct.unpack_from('<h', qb, 1)[0]
            qt_near = any(qf + 3 + rel + m * 65536 == ENT['ftol'] for m in (-1, 0, 1))
        if qt_far or qt_near:
            reg = PUSHREG[pb[0]]
            fp_sites.append({'call': site, 'callee': callee, 'ftol': qf, 'push': pf,
                             'push_reg': reg,
                             'narrowing': 'LOW16_OF_FTOL' if reg == 'ax' else
                                          ('HIGH16_OF_FTOL' if reg == 'dx' else 'OTHER_REG_AFTER_FTOL')})
        elif 0xD8 <= qb[0] <= 0xDF:
            nonftol.append(site)
    fp_sites.sort(key=lambda s: s['call'])

    # ---- UNKNOWN 2, read out of zrandom's decoded body -------------------
    zcalls = [(n, f, b, t) for n, (f, b, t) in enumerate(zr)
              if (b[0] == 0x9A and len(b) == 5) or (b[0] == 0xE8 and len(b) == 3)]
    if len(zcalls) != 2:
        fail('zrandom-shape', 'zrandom body has %d calls, expected 2' % len(zcalls))
    i1, i2 = zcalls[0][0], zcalls[1][0]
    zcall_sites = []
    for n, f, b, t in zcalls:
        pv = zr[n - 1] if n else (0, b'', '')
        zcall_sites.append(pv[0] if pv[1] == b'\x0e' and pv[0] + 1 == f else f)
    # Symbolic stack walk.  A `push ax` issued while a draw is live in AX
    # spills that draw; the matching `pop` (by stack discipline, NOT by
    # "first pop seen" -- the first pop is the caller's argument cleanup)
    # names the register the spilled draw is subtracted from.
    sstack = []
    draw_reg = {}
    ndraw = 0
    axval = None
    for n, (f, b, t) in enumerate(zr):
        if (b[0] == 0x9A and len(b) == 5) or (b[0] == 0xE8 and len(b) == 3):
            ndraw += 1
            axval = 'draw%d' % ndraw
        elif len(b) == 1 and b[0] in PUSHREG:
            reg = PUSHREG[b[0]]
            sstack.append(axval if (reg == 'ax' and axval) else 'other')
        elif len(b) == 1 and b[0] in POPREG:
            if POPREG[b[0]] == 'ax':
                axval = None
            sym = sstack.pop() if sstack else 'other'
            if sym.startswith('draw'):
                draw_reg[sym] = POPREG[b[0]]
    if 'draw1' not in draw_reg:
        fail('zrandom-shape', 'the first draw is never spilled and restored')
    draw1_reg = draw_reg['draw1']
    draw2_reg = 'ax'
    for f, b, t in zr[i2 + 1:]:
        if len(b) == 2 and b[0] in (0x29, 0x2B) and b[1] >= 0xC0:
            break
        if (b[0] == 0x8B and (b[1] >> 3) & 7 == 0) or (len(b) == 1 and b[0] == 0x58):
            fail('zrandom-shape', 'ax is clobbered between the second draw and the subtract')
    sub = next(((f, b, t) for f, b, t in zr if len(b) == 2 and b[0] in (0x29, 0x2B) and b[1] >= 0xC0), None)
    if sub is None:
        fail('zrandom-shape', 'no register-to-register subtract in zrandom')
    sf, sb, st = sub
    if sb[0] == 0x2B:
        dst, src = modrm_regs(sb[1])
    else:
        src, dst = modrm_regs(sb[1])
    if dst == draw1_reg:
        minuend, verdict = 'draw1', 'LEFT_TO_RIGHT'
    elif dst == draw2_reg:
        minuend, verdict = 'draw2', 'RIGHT_TO_LEFT'
    else:
        fail('zrandom-shape', 'subtract destination %s is neither draw' % dst)
    store = next(((f, b, t) for f, b, t in zr if b[0] in (0x88, 0x89) and len(b) >= 2
                  and (b[1] & 0xC7) in (0x46, 0x86)), None)
    if store is None:
        fail('zrandom-shape', 'no frame store of the difference')
    stored_reg = R16[(store[1][1] >> 3) & 7]
    width = 16 if store[1][0] == 0x89 else 8
    ret_load = next((t for f, b, t in zr if t.startswith('fild')), '')

    # ---- UNKNOWN 1, read out of random's and __ftol's decoded bodies -----
    rtext = [t for _, _, t in rnd]
    movsx = next((b for f, b, t in rnd if b[:3] == b'\x66\x0f\xbf' and 'word [bp' in t), None)
    movzx = next((b for f, b, t in rnd if b[:3] == b'\x66\x0f\xb7' and 'word [bp' in t), None)
    if movsx is None and movzx is None:
        fail('random-shape', 'random does not widen a 16-bit frame parameter')
    imul = next((b for f, b, t in rnd if b[:3] == b'\x66\x0f\xaf'), None)
    divi = next(((b, t) for f, b, t in rnd if b[:2] == b'\x66\xf7' and len(b) == 3), None)
    divisor = next((struct.unpack_from('<I', b, 2)[0] for f, b, t in rnd
                    if b[:2] == b'\x66\xbb' and len(b) == 6), None)
    if imul is None or divi is None or divisor is None:
        fail('random-shape', 'random is not a 32-bit imul/idiv body: %s' % ' ; '.join(rtext))
    div_signed = (divi[0][2] & 0x38) == 0x38

    orim = next(((b, t) for f, b, t in ft if b[0] == 0x80 and len(b) == 4 and (b[1] & 0x38) == 0x08), None)
    if orim is None:
        fail('ftol-shape', 'no control-word OR in __ftol')
    cwimm = orim[0][3]
    fistp = next((t for f, b, t in ft if t.startswith('fistp')), '')
    store_w = 64 if 'qword' in fistp else (32 if 'dword' in fistp else (16 if 'word' in fistp else 0))
    retregs = set()
    for f, b, t in ft:
        m = b[0] == 0x8B and len(b) >= 2 and (b[1] & 0xC7) in (0x46, 0x86)
        if m:
            retregs.add(R16[(b[1] >> 3) & 7])
    ret_w = 16 * len([r for r in retregs if r in ('ax', 'dx')])

    v = {
        "status": "OK",
        "binary": {"sha256": hashlib.sha256(data).hexdigest(), "size": size},
        "layout": {"header_len": hdrlen, "dgroup_file": dgroup_file},
        "anchors": {
            "rand_entry": ENT['rand'], "srand_entry": ENT['srand'],
            "random_entry": ENT['random'], "zrandom_entry": ENT['zrandom'],
            "zrandom_len": zr_end - ENT['zrandom'], "ftol_entry": ENT['ftol'],
            "zrandom_body_sha256": hashlib.sha256(data[ENT['zrandom']:zr_end]).hexdigest(),
            "random_body_sha256": hashlib.sha256(data[ENT['random']:rnd_end]).hexdigest(),
        },
        "census": {"rand": cen('rand'), "random": cen('random'),
                   "zrandom": cen('zrandom'), "ftol": {"total": cen('ftol')['total']}},
        "unknown1": {
            "verdict": "NARROWED_AT_CALL_BOUNDARY",
            "random_is_macro": False,
            "random_param_width_bits": 16,
            "random_param_signextended": movsx is not None,
            "random_divisor": divisor,
            "random_div_is_signed": div_signed,
            "random_mul_width_bits": 32,
            "ftol": {"cw_or_immediate": cwimm, "rounding": RC[(cwimm >> 2) & 3],
                     "store_width_bits": store_w, "return_width_bits": ret_w},
            "fp_sites": fp_sites,
            "fp_sites_total": len(fp_sites),
            "nonftol_fp_arg_sites": sorted(nonftol),
        },
        "unknown2": {
            "verdict": verdict, "minuend": minuend,
            "spilled_draw": "draw1", "live_draw": "draw2",
            "sub_dst": dst, "sub_src": src, "sub_file": sf,
            "op": "sub", "stored_reg": stored_reg, "result_width_bits": width,
            # underscore-joined so the token survives the contract's
            # whitespace-insensitive-only canonicaliser identically for
            # both engines ("fild word [bp-0x2]" -> "fild_word")
            "return_load": '_'.join(ret_load.split()[:2]),
            "call_files": zcall_sites,
        },
        "selfcheck": {},
        "evidence": {
            "zrandom_text": N.text_of(zr),
            "random_text": N.text_of(rnd),
            "ftol_text": N.text_of(ft),
        },
        "decoder": {
            "id": "bx", "engine": "ndisasm", "engine_version": N.engine_version(),
            "route": "borland-symtab-name -> masked-signature transfer -> ndisasm linear sweep",
            "insns_decoded": N.STATS["insns"],
            "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    }
    # ---- self-checks (reported, never used to locate anything) -----------
    relset = set()
    for i in range(lay['nreloc']):
        o, s = struct.unpack_from('<HH', data, lay['reloff'] + 4 * i)
        relset.add(hdrlen + s * 16 + o)
    farr = census['random']['far']
    pcs = census['random']['pushcs']
    v["selfcheck"] = {
        "anchor_354e_count": data.count(b'\x35\x4e'),
        "far_sites_with_reloc": sum(1 for s in farr if (s + 3) in relset),
        "far_sites_total": len(farr),
        "pushcs_sites_with_nop_pad": sum(1 for s in pcs if s >= 1 and data[s - 1] == 0x90),
        "pushcs_sites_total": len(pcs),
    }
    print(json.dumps(v))


if __name__ == '__main__':
    main()
