"""Generate a NIV+ source copy instrumented at the ROTOR IGNE render stages.

The input is never modified.  Point --output at a disposable NIV+ source tree,
then build that tree with its normal Borland toolchain.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROTOR_CAPTURE_SIZE = 192_062

HELPER_ANCHOR = """/* Programma principale. */"""
HELPER_REPLACEMENT = r'''/* Fixture nativa: pagine intermedie della compagna ROTOR IGNE. */

#define ROTOR_CAPTURE_SIZE 192062L

char *rotor_partial_file = "..\\DATA\\ROTOR.PRT";
char *rotor_final_file   = "..\\DATA\\ROTOR.BIN";

int rotor_write_page (int fh, unsigned char huge *page)
{
	unsigned row;

	/* adapted e' gia' top-down: una write distinta per ciascuna riga. */
	for (row = 0; row < 200; row++)
		if (_write (fh, page + 320L * row, 320) != 320)
			return (0);
	return (1);
}

int rotor_write_header (int fh, unsigned char flags,
			 double body_secs, double body_x, double body_y,
			 double body_z, float body_distance,
			 double body_ray, float body_fgm)
{
	char magic[8] = { 'N', 'I', 'V', 'R', 'I', '1', '0', 0 };
	unsigned version = 1;
	unsigned body_index = 3;
	unsigned char body_type = 10;

	return (_write (fh, magic, 8) == 8
		&& _write (fh, &version, 2) == 2
		&& _write (fh, &body_index, 2) == 2
		&& _write (fh, &body_type, 1) == 1
		&& _write (fh, &flags, 1) == 1
		&& _write (fh, &body_secs, 8) == 8
		&& _write (fh, &body_x, 8) == 8
		&& _write (fh, &body_y, 8) == 8
		&& _write (fh, &body_z, 8) == 8
		&& _write (fh, &body_distance, 4) == 4
		&& _write (fh, &body_ray, 8) == 8
		&& _write (fh, &body_fgm, 4) == 4);
}

void rotor_abort_capture (int fh)
{
	_close (fh);
	remove (rotor_partial_file);
}

/* Programma principale. */'''

LOCALS_ANCHOR = """	float tmp_float;
	long p1, p2, p3, p4;"""
LOCALS_REPLACEMENT = """	float tmp_float;
	long p1, p2, p3, p4;

	Dword rotor_initial_snapshot;
	char rotor_capture_pending = 0;
	char rotor_capture_done = 0;
	unsigned char rotor_flags;
	int rotor_fh = -1;
	int rotor_close_status;"""

UNFREEZE_ANCHOR = """	unfreeze ();

	pclear (adapted, 0);"""
UNFREEZE_REPLACEMENT = """	unfreeze ();
	rotor_initial_snapshot = lastSnapshot;

	pclear (adapted, 0);"""

TRIGGER_ANCHOR = """		sync_start ();"""
TRIGGER_REPLACEMENT = """		sync_start ();

		/* Il BMP schedulato arma la prima frame successiva allo snapshot. */
		if (!rotor_capture_pending && !rotor_capture_done
		 && lastSnapshot != rotor_initial_snapshot)
			rotor_capture_pending = 1;"""

COMPANION_ANCHOR = """		for (ir = 0; ir < nearstar_nop; ir++) {
			if (nearstar_p_type[ir] == 10) {
				planet_xyz (ir);
				p_dsd = nearstar_p_qsortdist[ir];
				fast_srand (ir + nearstar_x);
				whiteglobe (adapted, plx, ply, plz,
				    3 * nearstar_p_ray[ir], 0.15 - fast_flandom() * 0.3);
				if (p_dsd>5*nearstar_p_ray[ir]&&p_dsd<1000*nearstar_p_ray[ir])
					lens_flares_for (dzat_x, dzat_y, dzat_z, plx, ply, plz,
							(10 * nearstar_p_ray[ir]) / p_dsd,
							1 + (0.001 * p_dsd), hud_closed, 0, 3, 0);
			}
		}"""
COMPANION_REPLACEMENT = """		for (ir = 0; ir < nearstar_nop; ir++) {
			if (nearstar_p_type[ir] == 10) {
				planet_xyz (ir);
				p_dsd = nearstar_p_qsortdist[ir];
				fast_srand (ir + nearstar_x);
				tmp_float = 0.15 - fast_flandom() * 0.3;
				if (rotor_capture_pending && ir == 3) {
					rotor_capture_pending = 0;
					rotor_capture_done = 1;
					rotor_flags = 0;
					if (p_dsd>5*nearstar_p_ray[ir]&&p_dsd<1000*nearstar_p_ray[ir])
						rotor_flags |= 1;
					if (l_dsd > 6 * nearstar_ray)
						rotor_flags |= 2;
					remove (rotor_final_file);
					rotor_fh = _creat (rotor_partial_file, 0);
					if (rotor_fh > -1) {
						if (!rotor_write_header (rotor_fh, rotor_flags,
							secs, plx, ply, plz,
							nearstar_p_qsortdist[ir], nearstar_p_ray[ir],
							tmp_float)) {
							rotor_abort_capture (rotor_fh);
							rotor_fh = -1;
						}
					}
				}
				whiteglobe (adapted, plx, ply, plz,
				    3 * nearstar_p_ray[ir], tmp_float);
				/* Offset 62: subito dopo la corona della compagna. */
				if (ir == 3 && rotor_fh > -1
				 && !rotor_write_page (rotor_fh, adapted)) {
					rotor_abort_capture (rotor_fh);
					rotor_fh = -1;
				}
				if (p_dsd>5*nearstar_p_ray[ir]&&p_dsd<1000*nearstar_p_ray[ir])
					lens_flares_for (dzat_x, dzat_y, dzat_z, plx, ply, plz,
							(10 * nearstar_p_ray[ir]) / p_dsd,
							1 + (0.001 * p_dsd), hud_closed, 0, 3, 0);
				/* Offset 64062: subito dopo l'eventuale flare della compagna. */
				if (ir == 3 && rotor_fh > -1
				 && !rotor_write_page (rotor_fh, adapted)) {
					rotor_abort_capture (rotor_fh);
					rotor_fh = -1;
				}
			}
		}"""

SMOOTH_ANCHOR = """		if (l_dsd > 6 * nearstar_ray) {
			if (nearstar_class!=5&&nearstar_class!=6&&nearstar_class!=10) {
				if (nearstar_class!=11||gl_start<90) {
					if (l_dsd>5*nearstar_ray&&l_dsd<1000*nearstar_ray) {
						lens_flares_for (dzat_x, dzat_y, dzat_z,
								 nearstar_x, nearstar_y, nearstar_z,
								 (10 * nearstar_ray) / l_dsd, 1 + (0.001 * l_dsd), hud_closed, 0, 3, 0);
					}
				}
			}
			psmooth_grays (adapted+2880);
		}
		//
		mask_pixels (adapted+2880, 64);"""
SMOOTH_REPLACEMENT = """		if (l_dsd > 6 * nearstar_ray) {
			if (nearstar_class!=5&&nearstar_class!=6&&nearstar_class!=10) {
				if (nearstar_class!=11||gl_start<90) {
					if (l_dsd>5*nearstar_ray&&l_dsd<1000*nearstar_ray) {
						lens_flares_for (dzat_x, dzat_y, dzat_z,
								 nearstar_x, nearstar_y, nearstar_z,
								 (10 * nearstar_ray) / l_dsd, 1 + (0.001 * l_dsd), hud_closed, 0, 3, 0);
					}
				}
			}
			psmooth_grays (adapted+2880);
		}
		/* Offset 128062: dopo smoothing e prima della maschera. */
		if (rotor_fh > -1) {
			if (!rotor_write_page (rotor_fh, adapted)
			 || filelength (rotor_fh) != ROTOR_CAPTURE_SIZE) {
				rotor_abort_capture (rotor_fh);
				rotor_fh = -1;
			}
			else {
				rotor_close_status = _close (rotor_fh);
				rotor_fh = -1;
				if (rotor_close_status
				 || rename (rotor_partial_file, rotor_final_file))
					remove (rotor_partial_file);
			}
		}
		//
		mask_pixels (adapted+2880, 64);"""

PATCHES = (
    ("helper insertion", HELPER_ANCHOR, HELPER_REPLACEMENT),
    ("main capture locals", LOCALS_ANCHOR, LOCALS_REPLACEMENT),
    ("post-unfreeze snapshot baseline", UNFREEZE_ANCHOR, UNFREEZE_REPLACEMENT),
    ("following-frame trigger", TRIGGER_ANCHOR, TRIGGER_REPLACEMENT),
    ("type-10 companion stages", COMPANION_ANCHOR, COMPANION_REPLACEMENT),
    ("smoothing stage publication", SMOOTH_ANCHOR, SMOOTH_REPLACEMENT),
)


def instrument_source(source: str) -> str:
    """Return one exactly anchored instrumented source copy."""
    newline = "\r\n" if "\r\n" in source else "\n"
    result = source
    for label, anchor, replacement in PATCHES:
        source_anchor = anchor.replace("\n", newline)
        count = result.count(source_anchor)
        if count != 1:
            raise ValueError(f"{label}: expected one source anchor, found {count}")
        result = result.replace(
            source_anchor, replacement.replace("\n", newline), 1
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True,
                        help="unmodified NIV+ NOCTIS.CPP")
    parser.add_argument("--output", type=Path,
                        help="destination in a disposable source tree")
    parser.add_argument("--check", action="store_true",
                        help="validate source anchors without writing")
    parser.add_argument("--force", action="store_true",
                        help="replace an existing output file")
    args = parser.parse_args()

    if args.check == (args.output is not None):
        parser.error("select exactly one of --check or --output")
    source_path = args.source.resolve()
    if not source_path.is_file():
        parser.error("--source does not name a file")
    if args.output is not None:
        output_path = args.output.resolve()
        if output_path == source_path:
            parser.error("refusing to modify the input source in place")
        if not output_path.parent.is_dir():
            parser.error("--output parent directory does not exist")
        if output_path.exists() and not args.force:
            parser.error("refusing to overwrite --output without --force")
    else:
        output_path = None

    source_bytes = source_path.read_bytes()
    patched = instrument_source(source_bytes.decode("latin-1"))
    if output_path is None:
        print(f"validated ROTOR IGNE anchors in {source_path}")
    else:
        output_path.write_bytes(patched.encode("latin-1"))
        print(f"wrote instrumented source {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
