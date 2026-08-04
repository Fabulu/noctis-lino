"""Mechanism for driving the Tier 2 programmes from a test.

Two things this exists to guarantee:

  * TESTS NEVER TOUCH work/. Each test gets its own sandbox under tests/gen,
    into which work/starmap_find.txt and work/starmap_read.txt are copied with
    ONLY their file-name string literals rewritten. The code under test is
    still the code in work/ - a regression there fails the suite - but the
    delivered artifacts, the catalogue copy and the .err files in work/ are
    left exactly as the pipeline left them.
  * NOTHING IS EVER WAITED ON. Both programmes are GUI-subsystem binaries;
    linoharness drives them through lino_build.ps1 / linorun.ps1, which poll
    for the artifact and kill the process.

One language trap is baked in here: "\\us" inside a lino string literal emits an
UNDERSCORE, so { starmap\\usfind.bin } is the file starmap_find.bin. The sandbox
names are underscore-free so the rewriting stays a plain substring swap.

A note on the .err file: both programmes write <stem>.err and nothing else when
an isocall fails, and neither deletes a stale one. Every run here removes it
first and reports its presence afterwards, because "the output file is fresh"
and "the run succeeded" are not the same statement.
"""

import os
import struct

import linoharness as L
import starmapspec as S

MODE_DECOY, MODE_UNSIGNED, MODE_RAW = 1, 2, 4
HITCAP = 60000

# The file-name literals of each programme, as they appear in work/*.txt.
# "%s" is the sandbox stem. The counts are asserted by the tests: if a rename
# in work/ silently stops matching, the test must say so rather than quietly
# drive a programme that still writes into work/.
LITERALS = {
    "starmap_find": ({r"starmap\usfind": "%s", r"starmap\uscfg": "%scfg"}, 4),
    "starmap_read": ({r"starmap\usread": "%s", r"starmap\uskeys": "%skeys"}, 3),
}


def sandbox(name):
    d = os.path.join(L.gen_dir(), name)
    os.makedirs(d, exist_ok=True)
    return d


def localise(prog, stem, sbox):
    """work/<prog>.txt -> <sbox>/<stem>.txt, file-name literals only.

    Returns (dst_path, substitutions_made, expected_substitutions).
    """
    src = os.path.join(L.WORK, prog + ".txt")
    with open(src, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    mapping, want = LITERALS[prog]
    n = 0
    for pat, repl in mapping.items():
        n += text.count(pat)
        text = text.replace(pat, repl % stem)
    dst = os.path.join(sbox, stem + ".txt")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(text)
    return dst, n, want


class Programme(object):
    """A localised copy of one work/ programme, built and run in a sandbox."""

    def __init__(self, prog, stem, sbox_name):
        self.prog = prog
        self.stem = stem
        self.dir = sandbox(sbox_name)
        self.src, self.nsubs, self.want_subs = localise(prog, stem, self.dir)
        self.exe = os.path.join(self.dir, stem + ".exe")
        self.err = os.path.join(self.dir, stem + ".err")
        self.out = os.path.join(self.dir, stem + ".bin")

    def build(self):
        for stale in (self.exe, self.out, self.err):
            if os.path.exists(stale):
                os.remove(stale)
        rc, msg = L.build(self.src)
        return rc == 0, msg.strip()

    def catalogue(self, blob):
        """Install the STARMAP.BIN this run will read."""
        with open(os.path.join(self.dir, "STARMAP.BIN"), "wb") as fh:
            fh.write(blob)

    def real_catalogue(self):
        with open(S.CATALOGUE, "rb") as fh:
            blob = fh.read()
        self.catalogue(blob)
        return blob

    def _run(self, out, timeout):
        if os.path.exists(self.err):
            os.remove(self.err)
        rc, msg, blob = L.run(self.exe, out, timeout_sec=timeout)
        return blob, os.path.exists(self.err), msg


class Find(Programme):
    def __init__(self, stem="tsfind", sbox_name="tsfind"):
        Programme.__init__(self, "starmap_find", stem, sbox_name)

    def run(self, K, mode=0, cap=HITCAP, timeout=300):
        """Returns (header, hits, failed_flag, message).

        header/hits are None when the programme wrote its .err file or left no
        fresh output - a caller must not read a stale artifact as a result.
        """
        with open(os.path.join(self.dir, self.stem + "cfg.bin"), "wb") as fh:
            fh.write(struct.pack("<3i", K, mode, cap))
        blob, failed, msg = self._run(self.out, timeout)
        if blob is None or failed:
            return None, None, failed, msg
        if mode & MODE_RAW:
            return None, blob, False, msg
        h, hits = S.read_find(blob)
        return h, hits, False, msg


class Read(Programme):
    def __init__(self, stem="tsread", sbox_name="tsread"):
        Programme.__init__(self, "starmap_read", stem, sbox_name)
        self.out = os.path.join(self.dir, stem + "keys.bin")

    def run(self, timeout=300):
        blob, failed, msg = self._run(self.out, timeout)
        if blob is None or failed:
            return None, None, failed, msg
        hdr = struct.unpack_from("<4I", blob, 0)
        n = hdr[0]
        recs = [struct.unpack_from("<5I", blob, 16 + 20 * i) for i in range(n)]
        return hdr, recs, False, msg
