#!/usr/bin/env python
"""
bx_ndis.py -- Implementer 2's toolbox.  ndisasm driver + Borland symbol-table
parser + masked-signature builder/matcher.

ROUTE (bottom-up, from linker symbol NAMES).  Shares nothing with the
capstone route:
  * no  35 4E  LCG anchor
  * no  MZ relocation table used for LOCATION (only for a self-check)
  * no  call-graph walk used for LOCATION
Locations come from the Borland debug symbol tables that trail DL.EXE and
ST.EXE, transferred into NOCTIS.EXE as masked byte signatures.
"""

import os
import re
import struct
import subprocess

LINE = re.compile(r'^([0-9A-F]{8})\s+([0-9A-F]+)\s+(.*)$')
CF = re.compile(r'^(call|jmp|j[a-z]+|loop\w*)\b')

STATS = {"insns": 0, "sweeps": 0}


# ---------------------------------------------------------------- ndisasm

def engine_version():
    try:
        r = subprocess.run(['ndisasm', '-v'], capture_output=True, text=True)
        return ((r.stdout or '') + (r.stderr or '')).strip().splitlines()[0]
    except Exception:
        return 'ndisasm (version unknown)'


def sweep(path, start, stop, size):
    """Linear ndisasm sweep of path[start:stop]; addresses are FILE offsets.

    FWAIT (0x9B) prefixes that ndisasm glues onto the following instruction
    are split back out -- 9B is a standalone instruction and gluing it hides
    the opcode byte of every FPU-adjacent call.
    """
    STATS["sweeps"] += 1
    cmd = ['ndisasm', '-b16', '-o', hex(start), '-e', str(start)]
    if stop < size:
        cmd += ['-k', '%d,%d' % (stop, size - stop)]
    cmd.append(path)
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    rows = []
    for ln in out.splitlines():
        m = LINE.match(ln)
        if not m:
            continue
        f = int(m.group(1), 16)
        b = bytes.fromhex(m.group(2))
        t = m.group(3).strip()
        if len(b) > 1 and b[0] == 0x9B and t.startswith('wait '):
            rows.append((f, b[:1], 'fwait'))
            rows.append((f + 1, b[1:], t[5:]))
        else:
            rows.append((f, b, t))
    STATS["insns"] += len(rows)
    return rows


def sweep_body(path, start, size, maxlen=160):
    """Sweep from a function entry up to and including its terminating ret/retf."""
    rows = sweep(path, start, min(size, start + maxlen), size)
    body = []
    for f, b, t in rows:
        body.append((f, b, t))
        if t.startswith('ret'):
            break
    return body


def text_of(body):
    return '\n'.join('%d  %-14s %s' % (f, b.hex().upper(), t) for f, b, t in body)


# --------------------------------------------------- Borland symbol table

def mz_layout(data):
    lastpage, pages = struct.unpack_from('<HH', data, 2)
    nreloc, hdrpara = struct.unpack_from('<HH', data, 6)
    reloff = struct.unpack_from('<H', data, 24)[0]
    hdrlen = hdrpara * 16
    imglen = (pages - 1) * 512 + (lastpage if lastpage else 512)
    return dict(hdrlen=hdrlen, imglen=imglen, nreloc=nreloc, reloff=reloff)


def borland_symbols(path):
    """{name: (segment, offset)} from the debug symbol table trailing an EXE.

    Layout recovered empirically and cross-validated on DL.EXE and ST.EXE:
      magic 0xFB52 at imglen; word[2] = size of the trailing NUL-terminated
      name pool (pool sits at EOF); a 9-byte record array starts 80 bytes past
      the magic; record k (1-based, address-ordered) carries the address of
      name k as  <ord:u16> <aux:u16> <offset:u16> <segment:u16> <class:u8>.
    """
    data = open(path, 'rb').read()
    lay = mz_layout(data)
    tab = lay['imglen']
    if data[tab:tab + 2] != b'\xfb\x52':
        return None, lay, data
    pool_size = struct.unpack_from('<H', data, tab + 4)[0]
    pool = len(data) - pool_size
    if pool <= tab:
        return None, lay, data
    names = ['']
    p = pool
    while p < len(data):
        e = data.find(b'\x00', p)
        if e < 0:
            break
        names.append(data[p:e].decode('latin1'))
        p = e + 1
    syms = {}
    o = tab + 80
    k = 1
    while o + 9 <= pool and k < len(names):
        ordn, aux, off, seg, cls = struct.unpack_from('<HHHHB', data, o)
        if ordn != k:
            break
        syms.setdefault(names[k], (seg, off))
        k += 1
        o += 9
    return syms, lay, data


def sym_file_offset(lay, seg, off):
    return lay['hdrlen'] + seg * 16 + off


# ----------------------------------------------- masked signature transfer

def build_sig(rows):
    """Turn a decoded body into (items, span) where items alternate
    fixed-byte blocks (with a wildcard mask) and variable-length gaps.

    Wildcarded, because they are memory-model or link dependent:
      * whole control-transfer instructions   (E8 rel16 <-> 9A off:seg, +0x90 pad)
      * frame displacements [bp+4] <-> [bp+6]
      * absolute data displacements (DGROUP differs per program)
      * the ret opcode itself                 (C3 near <-> CB far)
    Immediates are KEPT -- 0x8000, 0x0C, 0x4E35, 0x015A are semantics.
    """
    items = []
    for a, b, t in rows:
        L = len(b)
        if CF.match(t):
            items.append(('g', 0, L + 4))
            continue
        if t.startswith('ret'):
            items.append(('b', b, [True] * L))
            continue
        mask = [False] * L
        for m in re.finditer(r'\[(?:[a-z]{2}\+)?0x([0-9a-f]{3,4})\]', t):
            enc = struct.pack('<H', int(m.group(1), 16))
            i = b.rfind(enc)
            if i >= 0:
                mask[i] = mask[i + 1] = True
        for m in re.finditer(r'\[(?:bp|bx|si|di)([+-])0x([0-9a-f]{1,2})\]', t):
            v = int(m.group(2), 16) * (-1 if m.group(1) == '-' else 1)
            enc = v & 0xFF
            for i in range(L - 1, -1, -1):
                if b[i] == enc and not mask[i]:
                    mask[i] = True
                    break
        items.append(('b', b, mask))
    # merge adjacent blocks
    merged = []
    for it in items:
        if it[0] == 'b' and merged and merged[-1][0] == 'b':
            merged[-1] = ('b', merged[-1][1] + it[1], merged[-1][2] + it[2])
        else:
            merged.append(list(it) if it[0] == 'b' else it)
            if merged[-1][0] == 'b':
                merged[-1] = ('b', merged[-1][1], list(merged[-1][2]))
    return merged


def _anchor_runs(items, minrun):
    """(run_bytes, min_offset, max_offset) for each maximal unmasked run."""
    runs = []
    lo = hi = 0
    for it in items:
        if it[0] == 'g':
            lo += it[1]
            hi += it[2]
            continue
        blk, mask = it[1], it[2]
        i = 0
        while i < len(blk):
            if mask[i]:
                i += 1
                continue
            j = i
            while j < len(blk) and not mask[j]:
                j += 1
            if j - i >= minrun:
                runs.append((blk[i:j], lo + i, hi + i))
            i = j
        lo += len(blk)
        hi += len(blk)
    runs.sort(key=lambda r: -len(r[0]))
    return runs


def _score(data, items, start, tol, limit):
    states = {start: 0}
    for it in items:
        ns = {}
        if it[0] == 'g':
            for p, c in states.items():
                for k in range(it[1], it[2] + 1):
                    q = p + k
                    if ns.get(q, 999) > c:
                        ns[q] = c
        else:
            blk, mask = it[1], it[2]
            L = len(blk)
            for p, c in states.items():
                if p < 0 or p + L > limit:
                    continue
                seg = data[p:p + L]
                cc = c
                for i in range(L):
                    if not mask[i] and seg[i] != blk[i]:
                        cc += 1
                        if cc > tol:
                            break
                if cc <= tol:
                    q = p + L
                    if ns.get(q, 999) > cc:
                        ns[q] = cc
        states = ns
        if not states:
            return None
    end = min(states, key=lambda p: (states[p], p))
    return states[end], end


def locate(data, items, lo, hi, tol=3):
    """Unique best match of a transferred signature inside data[lo:hi].

    Tolerates up to `tol` substituted bytes so that a one-byte mutation
    INSIDE the function being located cannot make the decoder go blind --
    the answer is then read out of the decoded body, not out of the pattern.
    """
    for minrun in (6, 5, 4, 3):
        runs = _anchor_runs(items, minrun)
        if not runs:
            continue
        cands = set()
        for rb, omin, omax in runs[:6]:
            i = lo
            while True:
                i = data.find(rb, i, hi)
                if i < 0:
                    break
                for dlt in range(omin, omax + 1):
                    if lo <= i - dlt < hi:
                        cands.add(i - dlt)
                i += 1
        if not cands:
            continue
        scored = []
        for s in sorted(cands):
            r = _score(data, items, s, tol, hi)
            if r:
                scored.append((r[0], s, r[1]))
        if not scored:
            continue
        best = min(c for c, _, _ in scored)
        winners = [(s, e) for c, s, e in scored if c == best]
        if len(winners) == 1:
            return winners[0][0], winners[0][1], best
        return None
    return None
