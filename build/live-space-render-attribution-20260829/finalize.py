from pathlib import Path
import hashlib
import json

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/live-space-render-attribution-20260829"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(relative):
    return json.loads((EVIDENCE / relative).read_text(encoding="utf-8"))


health = report("production-health/capsule/report.json")
vht = report("vht-screen/orbital/report.json")
local = report("local-screen/orbital/report.json")
coarse = report("subphase-screen/orbital/report.json")
star = report("star-screen/orbital/report.json")
assert health["provenance"]["executable_sha256"] == digest(
    EVIDENCE / "accepted/vhgame.exe"
)
assert health["startup_seconds"] > 8.0
assert health["metrics"]["presentation_hz"] < 59.7
assert vht["profile"]["mode"] == 0
assert vht["profile"]["space_counts"] == 0
assert local["profile"]["space_counts"] > 0
assert coarse["profile"]["space_counts"] > 0
assert star["profile"]["space_counts"] > 0
assert digest(ROOT / "work/vhgame.txt") == digest(EVIDENCE / "accepted/vhgame.txt")
assert digest(ROOT / "work/vhgame.exe") == digest(EVIDENCE / "accepted/vhgame.exe")

coarse_parts = (
    coarse["metrics"]["average_cupola_ms"],
    coarse["metrics"]["average_hull_ms"],
    coarse["metrics"]["average_detail_ms"],
)
star_parts = (
    star["metrics"]["average_cupola_ms"],
    star["metrics"]["average_hull_ms"],
    star["metrics"]["average_detail_ms"],
)
coarse_sum = sum(coarse_parts)
star_sum = sum(star_parts)
result = {
    "schema": 1,
    "task": 206,
    "kind": "instrumentation_only",
    "host_health": {
        "status": "depressed",
        "startup_seconds": health["startup_seconds"],
        "presentation_hz": health["metrics"]["presentation_hz"],
        "simulation_hz": health["metrics"]["simulation_hz"],
    },
    "vht_discriminator": {
        "presentation_hz": vht["metrics"]["presentation_hz"],
        "simulation_hz": vht["metrics"]["simulation_hz"],
        "measured_vht_ms": vht["metrics"]["average_space_ms"],
        "conclusion": "VHT render is skipped at the fixed orbital checkpoint",
    },
    "local_renderer": {
        "presentation_hz": local["metrics"]["presentation_hz"],
        "simulation_hz": local["metrics"]["simulation_hz"],
        "render_ms": local["metrics"]["average_render_ms"],
        "local_render_ms": local["metrics"]["average_space_ms"],
        "local_share_of_render": (
            local["metrics"]["average_space_ms"]
            / local["metrics"]["average_render_ms"]
        ),
    },
    "local_coarse_phases": {
        "local_total_ms": coarse["metrics"]["average_space_ms"],
        "star_setup_ms": coarse_parts[0],
        "other_bodies_ms": coarse_parts[1],
        "selected_body_ms": coarse_parts[2],
        "star_setup_share_of_partition": coarse_parts[0] / coarse_sum,
        "other_bodies_share_of_partition": coarse_parts[1] / coarse_sum,
        "selected_body_share_of_partition": coarse_parts[2] / coarse_sum,
        "simulation_hz": coarse["metrics"]["simulation_hz"],
        "simulation_gate_note": "instrumentation overhead drove this run below 18.206 Hz; no candidate-performance conclusion is admitted",
    },
    "star_setup_phases": {
        "local_total_ms": star["metrics"]["average_space_ms"],
        "selected_origin_and_resident_scan_ms": star_parts[0],
        "primary_setup_and_companion_coronas_ms": star_parts[1],
        "mask_and_primary_star_raster_ms": star_parts[2],
        "selected_origin_and_resident_scan_share": star_parts[0] / star_sum,
        "primary_setup_and_companion_coronas_share": star_parts[1] / star_sum,
        "mask_and_primary_star_raster_share": star_parts[2] / star_sum,
    },
    "next_candidate": {
        "name": "squared-distance resident selection",
        "edit": (
            "inside VHG local resident scan only, retain the exact three squared "
            "coordinate terms and additions but compare their nonnegative binary64 "
            "sum directly instead of applying FSqrt before each nearest-body comparison"
        ),
        "reason": (
            "the fixed orbital checkpoint skips VHT render; active local rendering "
            "is dominant, and selected-origin/resident selection is the largest "
            "measured star/setup subphase"
        ),
    },
    "disposition": "instrumented_depressed_host_attribution_only",
    "candidate_fps_conclusion": None,
    "final_arm": "accepted",
    "accepted_restored_byte_exact": True,
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
files = (
    "apply_vht_candidate.py",
    "verify_vht_model.py",
    "vht-model.json",
    "apply_local_candidate.py",
    "verify_local_model.py",
    "local-model.json",
    "apply_local_subphase_candidate.py",
    "verify_subphase_model.py",
    "subphase-model.json",
    "apply_star_subphase_candidate.py",
    "verify_star_model.py",
    "star-model.json",
    "finalize.py",
    "accepted/vhgame.txt",
    "accepted/vhgame.exe",
    "accepted/compiler114m.exe",
    "accepted/i386m.bin",
    "vht-instrumented/vhgame.txt",
    "vht-instrumented/vhgame.exe",
    "local-instrumented/vhgame.txt",
    "local-instrumented/vhgame.exe",
    "subphase-instrumented/vhgame.txt",
    "subphase-instrumented/vhgame.exe",
    "star-instrumented/vhgame.txt",
    "star-instrumented/vhgame.exe",
    "production-health/capsule/report.json",
    "vht-screen/orbital/report.json",
    "local-screen/orbital/report.json",
    "subphase-screen/orbital/report.json",
    "star-screen/orbital/report.json",
    "result.json",
)
manifest = {
    "schema": 1,
    "files": {
        relative: {
            "bytes": (EVIDENCE / relative).stat().st_size,
            "sha256": digest(EVIDENCE / relative),
        }
        for relative in files
    },
}
(EVIDENCE / "manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({
    "disposition": result["disposition"],
    "vht_ms": result["vht_discriminator"]["measured_vht_ms"],
    "local_ms": result["local_renderer"]["local_render_ms"],
    "star_setup_ms": result["local_coarse_phases"]["star_setup_ms"],
    "resident_scan_phase_ms": result["star_setup_phases"]["selected_origin_and_resident_scan_ms"],
    "next_candidate": result["next_candidate"]["name"],
    "final_arm": result["final_arm"],
}, indent=2))
