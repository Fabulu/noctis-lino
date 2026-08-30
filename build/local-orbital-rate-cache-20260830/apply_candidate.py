from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/local-orbital-rate-cache-20260830"
SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(original):
    text = original.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"

    def block(value):
        return value.strip("\n").replace("\n", nl)

    def replace_once(old, new):
        nonlocal text
        old = block(old)
        new = block(new)
        assert text.count(old) == 1, (old, text.count(old))
        text = text.replace(old, new, 1)

    def replace_n(old, new, count):
        nonlocal text
        old = block(old)
        new = block(new)
        assert text.count(old) == count, (old, text.count(old), count)
        text = text.replace(old, new)

    replace_once(
        """
	VHGlocalbatch = 0; VHGlocalacc = 0; VHGlocalphasetick = 0;
""",
        """
	VHGlocalbatch = 0; VHGlocalacc = 0; VHGlocalphasetick = 0;
	VHGlocalorbitclear = 0;
""",
    )
    replace_once(
        """
	VHGwideframes = 192000;
	VHGwideoutput = 183200;

"programme"
""",
        """
	VHGwideframes = 192000;
	VHGwideoutput = 183200;
	( 80 local static orbital-rate records, 8 words each. )
	VHGlocalorbitcache = 640;

"programme"
""",
    )
    replace_once(
        """
	[VHGlocalresident1] = 0FFFFFFFFh; [VHGlocalresident2] = 0FFFFFFFFh;
	[VHGlocalpmapbody] = 0FFFFFFFFh; [VHGlocalmmapbody] = 0FFFFFFFFh;
	( Source planets() waits for the 25-radius surface LOD before building a
""",
        """
	[VHGlocalresident1] = 0FFFFFFFFh; [VHGlocalresident2] = 0FFFFFFFFh;
	[VHGlocalpmapbody] = 0FFFFFFFFh; [VHGlocalmmapbody] = 0FFFFFFFFh;
	=> VHG local orbit cache clear;
	( Source planets() waits for the 25-radius surface LOD before building a
""",
    )
    replace_once(
        """
"VHG restore local checkpoint"
	( Version-14 saves carry the fine-approach integrator separately from galactic
	  dzat. Rebuild only its generated-system caches and MG boundary inputs; the
	  persisted position, distance and current coefficient remain authoritative. )
	A = [VHGlocalactive]; ? A = 0 -> VHG restore local inactive;
""",
        """
"VHG restore local checkpoint"
	( Version-14 saves carry the fine-approach integrator separately from galactic
	  dzat. Rebuild only its generated-system caches and MG boundary inputs; the
	  persisted position, distance and current coefficient remain authoritative. )
	=> VHG local orbit cache clear;
	A = [VHGlocalactive]; ? A = 0 -> VHG restore local inactive;
""",
    )
    replace_n(
        """
	[VHGNDvecindex] = [VHGplanet]; => VHGND absolute body vector;
""",
        """
	[VHGNDvecindex] = [VHGplanet]; => VHG local absolute body vector;
""",
        2,
    )
    replace_once(
        """
	? A = [VHGplanet] -> VHG local body next;
	[VHGNDvecindex] = A; => VHGND absolute body vector;
	=> VHG local body relative;
""",
        """
	? A = [VHGplanet] -> VHG local body next;
	[VHGNDvecindex] = A; => VHG local absolute body vector;
	=> VHG local body relative;
""",
    )
    replace_once(
        """
	[VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;
""",
        """
	[VHGNDvecindex] = [VHGlocalbody]; => VHG local absolute body vector;
""",
    )
    replace_n(
        """
	[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;
""",
        """
	[VHGNDvecindex] = A; => VHG local absolute body vector; => VHG local body relative;
""",
        2,
    )

    helpers = (
        """
"VHG local orbit cache clear"
	[VHGlocalorbitclear] = 0;
    "VHG local orbit cache clear body"
	A = [VHGlocalorbitclear]; ? A '>= 80 -> VHG local orbit cache clear done;
	A '* 8; E = VHGlocalorbitcache; E + A; [E] = 0;
	[VHGlocalorbitclear]+; -> VHG local orbit cache clear body;
    "VHG local orbit cache clear done"
	end;

"VHG local orbit angle"
	( Cache only the static pre-time root.  The live seconds, grouping, and
	  terminal VHGND/FP state still follow the original helper. )
	A = [VHGNDvecindex]; ? A < 0 -> VHG local orbit angle original;
	? A '>= 80 -> VHG local orbit angle original;
	A '* 8; E = VHGlocalorbitcache; E + A;
	A = [E]; ? A = 0 -> VHG local orbit angle miss;
	A = [E plus 1]; [VHGNDvecowner] = A;
	[VHGNDmass0] = [E plus 2]; [VHGNDmass1] = [E plus 3];
	[VHGNDorbit0] = [E plus 4]; [VHGNDorbit1] = [E plus 5];
	[FA0] = [E plus 6]; [FA1] = [E plus 7];
	A = [VHGNDvecowner]; ? A >= 0 -> VHG local orbit angle root ready;
	[FS0] = [nsstarray];
    "VHG local orbit angle root ready"
	A = [VHGNDvecindex]; A < 1; E = nsporbray; E + A;
	-> VHG local orbit angle dynamic;
    "VHG local orbit angle miss"
	E = nspowner; E + [VHGNDvecindex]; A = [E]; [VHGNDvecowner] = A;
	? A >= 0 -> VHG local orbit body mass;
	[FS0] = [nsstarray]; => FLoadF32; -> VHG local orbit radius mass;
    "VHG local orbit body mass"
	A < 1; E = nspray; E + A; [FA0] = [E plus 0]; [FA1] = [E plus 1];
    "VHG local orbit radius mass"
	[VHGNDmass0] = [FA0]; [VHGNDmass1] = [FA1];
	[FB0] = [VHGNDmass0]; [FB1] = [VHGNDmass1]; => FMul;
	[FB0] = [VHGNDmass0]; [FB1] = [VHGNDmass1]; => FMul;
	A = [VHGNDvecowner]; ? A >= 0 -> VHG local orbit body constant;
	[FB0] = 0A01627EEh; [FB1] = 3E31FD9Fh; -> VHG local orbit mass ready;
    "VHG local orbit body constant"
	[FB0] = 1735C01Dh; [FB1] = 3F28284Fh;
    "VHG local orbit mass ready"
	=> FMul; [VHGNDmass0] = [FA0]; [VHGNDmass1] = [FA1];
	A = [VHGNDvecindex]; A < 1; E = nsporbray; E + A;
	[FA0] = [E plus 0]; [FA1] = [E plus 1];
	[VHGNDorbit0] = [FA0]; [VHGNDorbit1] = [FA1];
	[FB0] = [VHGNDorbit0]; [FB1] = [VHGNDorbit1]; => FMul;
	[FB0] = [FA0]; [FB1] = [FA1];
	[FA0] = [VHGNDmass0]; [FA1] = [VHGNDmass1]; => FQuo; => FSqrt;
	A = [VHGNDvecindex]; A '* 8; E = VHGlocalorbitcache; E + A;
	[E plus 1] = [VHGNDvecowner];
	[E plus 2] = [VHGNDmass0]; [E plus 3] = [VHGNDmass1];
	[E plus 4] = [VHGNDorbit0]; [E plus 5] = [VHGNDorbit1];
	[E plus 6] = [FA0]; [E plus 7] = [FA1]; [E] = 1;
	A = [VHGNDvecindex]; A < 1; E = nsporbray; E + A;
    "VHG local orbit angle dynamic"
	[FB0] = [SUsec0]; [FB1] = [SUsec1]; => FMul;
	[FB0] = 54442D18h; [FB1] = 400921FBh; => FMul;
	[FB0] = 0; [FB1] = 40668000h; => FQuo;
	[VHGNDangle0] = [FA0]; [VHGNDangle1] = [FA1];
	end;
    "VHG local orbit angle original"
	=> VHGND orbit angle;
	end;

"VHG local body vector"
	=> VHG local orbit angle;
	[FA0] = [VHGNDangle0]; [FA1] = [VHGNDangle1]; => FSin;
	[VHGNDsin0] = [FA0]; [VHGNDsin1] = [FA1];
	[FA0] = [VHGNDangle0]; [FA1] = [VHGNDangle1]; => FCos;
	[VHGNDcos0] = [FA0]; [VHGNDcos1] = [FA1];
	A = [VHGNDvecindex]; A < 1; E = nsporbtlt; E + A;
	[FA0] = [E plus 0]; [FA1] = [E plus 1];
	[FB0] = A2529D39h; [FB1] = 3F91DF46h; => FMul;
	[VHGNDct0] = [FA0]; [VHGNDct1] = [FA1]; => FSin;
	A = [VHGNDvecindex]; A < 1; E = nsporbray; E + A;
	[FB0] = [E plus 0]; [FB1] = [E plus 1]; => FMul;
	[VHGNDvecy0] = [FA0]; [VHGNDvecy1] = [FA1];
	[FA0] = [VHGNDct0]; [FA1] = [VHGNDct1]; => FCos;
	[VHGNDct0] = [FA0]; [VHGNDct1] = [FA1];
	A = [VHGNDvecindex]; A < 1;
	E = nsporbray; E + A; [FA0] = [E plus 0]; [FA1] = [E plus 1];
	[FB0] = [VHGNDsin0]; [FB1] = [VHGNDsin1]; => FMul;
	[FB0] = [VHGNDct0]; [FB1] = [VHGNDct1]; => FMul; => FNeg;
	[VHGNDxx0] = [FA0]; [VHGNDxx1] = [FA1];
	A = [VHGNDvecindex]; A < 1;
	E = nsporbray; E + A; [FA0] = [E plus 0]; [FA1] = [E plus 1];
	[FB0] = [VHGNDcos0]; [FB1] = [VHGNDcos1]; => FMul;
	[FB0] = [VHGNDct0]; [FB1] = [VHGNDct1]; => FMul;
	A = [VHGNDvecindex]; A < 1;
	E = nsporbecc; E + A; [FB0] = [E plus 0]; [FB1] = [E plus 1]; => FMul;
	[VHGNDzz0] = [FA0]; [VHGNDzz1] = [FA1];
	A = [VHGNDvecindex]; A < 1;
	E = nspororient; E + A; [FA0] = [E plus 0]; [FA1] = [E plus 1]; => FSin;
	[VHGNDso0] = [FA0]; [VHGNDso1] = [FA1];
	A = [VHGNDvecindex]; A < 1;
	E = nspororient; E + A; [FA0] = [E plus 0]; [FA1] = [E plus 1]; => FCos;
	[VHGNDco0] = [FA0]; [VHGNDco1] = [FA1];
	[FA0] = [VHGNDxx0]; [FA1] = [VHGNDxx1];
	[FB0] = [VHGNDco0]; [FB1] = [VHGNDco1]; => FMul;
	[VHGNDvecx0] = [FA0]; [VHGNDvecx1] = [FA1];
	[FA0] = [VHGNDzz0]; [FA1] = [VHGNDzz1];
	[FB0] = [VHGNDso0]; [FB1] = [VHGNDso1]; => FMul;
	[FB0] = [VHGNDvecx0]; [FB1] = [VHGNDvecx1]; => FAdd;
	[VHGNDvecx0] = [FA0]; [VHGNDvecx1] = [FA1];
	[FA0] = [VHGNDzz0]; [FA1] = [VHGNDzz1];
	[FB0] = [VHGNDco0]; [FB1] = [VHGNDco1]; => FMul;
	[VHGNDvecz0] = [FA0]; [VHGNDvecz1] = [FA1];
	[FA0] = [VHGNDxx0]; [FA1] = [VHGNDxx1];
	[FB0] = [VHGNDso0]; [FB1] = [VHGNDso1]; => FMul;
	[FB0] = [FA0]; [FB1] = [FA1];
	[FA0] = [VHGNDvecz0]; [FA1] = [VHGNDvecz1]; => FSub;
	[VHGNDvecz0] = [FA0]; [VHGNDvecz1] = [FA1];
	end;

"VHG local absolute body vector"
	A = [VHGNDvecindex]; ? A < 0 -> VHG local absolute body original;
	? A '>= 80 -> VHG local absolute body original;
	=> VHG local body vector;
	[VHGNDownx0] = [VHGNDvecx0]; [VHGNDownx1] = [VHGNDvecx1];
	[VHGNDowny0] = [VHGNDvecy0]; [VHGNDowny1] = [VHGNDvecy1];
	[VHGNDownz0] = [VHGNDvecz0]; [VHGNDownz1] = [VHGNDvecz1];
	E = nspowner; E + [VHGNDvecindex]; A = [E];
	? A < 0 -> VHG local absolute body done;
	[VHGNDvecindex] = A; ? A '>= 80 -> VHG local absolute owner original;
	=> VHG local body vector; -> VHG local absolute body combine;
    "VHG local absolute owner original"
	=> VHGND body vector;
    "VHG local absolute body combine"
	[FA0] = [VHGNDownx0]; [FA1] = [VHGNDownx1];
	[FB0] = [VHGNDvecx0]; [FB1] = [VHGNDvecx1]; => FAdd;
	[VHGNDownx0] = [FA0]; [VHGNDownx1] = [FA1];
	[FA0] = [VHGNDowny0]; [FA1] = [VHGNDowny1];
	[FB0] = [VHGNDvecy0]; [FB1] = [VHGNDvecy1]; => FAdd;
	[VHGNDowny0] = [FA0]; [VHGNDowny1] = [FA1];
	[FA0] = [VHGNDownz0]; [FA1] = [VHGNDownz1];
	[FB0] = [VHGNDvecz0]; [FB1] = [VHGNDvecz1]; => FAdd;
	[VHGNDownz0] = [FA0]; [VHGNDownz1] = [FA1];
    "VHG local absolute body done"
	[VHGNDvecx0] = [VHGNDownx0]; [VHGNDvecx1] = [VHGNDownx1];
	[VHGNDvecy0] = [VHGNDowny0]; [VHGNDvecy1] = [VHGNDowny1];
	[VHGNDvecz0] = [VHGNDownz0]; [VHGNDvecz1] = [VHGNDownz1];
	end;
    "VHG local absolute body original"
	=> VHGND absolute body vector;
	end;
"""
    )
    replace_once(
        """
"VHG local far pixel"
""",
        helpers + "\n\n" + '"VHG local far pixel"',
    )
    return text.encode("utf-8")


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    assert digest(SOURCE) == digest(ACCEPTED)
    candidate = transform(accepted)
    assert candidate != accepted
    CANDIDATE.write_bytes(candidate)
    SOURCE.write_bytes(candidate)
    print(f"accepted_source_sha256={digest(ACCEPTED)}")
    print(f"candidate_source_sha256={digest(CANDIDATE)}")
