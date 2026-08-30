"""Build and compare production transcendental consumers in isolation.

The portable build is compared byte-for-byte with a reference build in which
only FSin, FCos, and FAtan2 use hardware x87. All source and outputs live under
tests/gen; the test never rebuilds or overwrites artifacts in work/.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
GEN = TESTS / "gen" / "transcendental-consumers"
sys.path.insert(0, str(TESTS))
import linoharness as lh  # noqa: E402


PROTECTED = {
    Path("work/fp/fpout.bin"),
    Path("work/fp/fprefout.bin"),
    Path("work/fp/fptest.exe"),
    Path("work/fp/fpvec.bin"),
}
EXTRA_SOURCES = (Path("work/vhtransprobe.txt"),)


@dataclass(frozen=True)
class Probe:
    source: str
    outputs: tuple[str, ...]
    sentinel: str
    timeout: int = 180


PROBES = (
    Probe("vhcapsuleprobe.txt", ("vhcapsule-out.bin",), "vhcapsule-out.bin"),
    Probe(
        "vhsunprobe.txt",
        ("vhsun-white.bin", "vhsun-flare.bin", "vhsun-smooth.bin",
         "vhsun-out.bin"),
        "vhsun-out.bin",
    ),
    Probe(
        "vhtreeprobe.txt",
        ("vhtree-out.bin", "vhtree-page.bin"),
        "vhtree-page.bin",
    ),
    Probe(
        "vhtransmain.txt",
        ("vhtrans-state.bin", "vhtrans-page.bin"),
        "vhtrans-page.bin",
        timeout=300,
    ),
)

EXPECTED_SHA256 = {
    "vhcapsule-out.bin":
        "0c5adacbaaa7e1531e9d7026d5d82fb64609c597233fe33b0f5f8dabe64f544a",
    "vhsun-white.bin":
        "b1240d9b35d63010704dd330134f593f76bc332608ea7d81e2f6723a6989b16c",
    "vhsun-flare.bin":
        "0cd7adb782543e384473dc3aefebe63fe5aea9481e47fa87062a8cac85c912a9",
    "vhsun-smooth.bin":
        "a84416026fee23af42e2fffaa99abf3fa737b47ae953b5ca9b9956288c9d8ea0",
    "vhsun-out.bin":
        "2882fb4e7f690dae58393a8d0ab027907df3e25900f06fb84be42347e67866d6",
    "vhtree-out.bin":
        "bde1691ac7a286998dcd5558ae4fae778f25f7b1b8fe15cc1e571cf0c94bee14",
    "vhtree-page.bin":
        "fb3e4969cb3bd56c132f1519e5ed137df21c0e77de4a072ee37da74470c1a6be",
    "vhtrans-state.bin":
        "4903b877abf104a9126be8471687da4cd1ef08cc6ebbe95b80528d81389290dc",
    "vhtrans-page.bin":
        "5a9fbebabc9e64b07f6a66ab9ba9419255b6b7f47e9523aed78df370d1535263",
}
EXPECTED_SIZE = {
    "vhcapsule-out.bin": 96,
    "vhsun-white.bin": 64000,
    "vhsun-flare.bin": 64000,
    "vhsun-smooth.bin": 64000,
    "vhsun-out.bin": 64000,
    "vhtree-out.bin": 40,
    "vhtree-page.bin": 256000,
    "vhtrans-state.bin": 256,
    "vhtrans-page.bin": 64000,
}
EXPECTED_CAPSULE = (
    1447576400, 46, 1, 1,
    1646592, 1646592, 1646592, 1646592,
    0, 0, 11, 2342, 5607, 277, 1024, 9, 9, 9,
    0, 30, 62, 2, 0, 324508639,
)
EXPECTED_TREE = (4856, 1, 1, 5, 0, 214, 0, 333, 0, 0)
EXPECTED_TRANS_STATE = (
    1448366129, 64,
    11506, -67919, 1060018034, -1086637569, -1087465614, 1060846079,
    1123418112, -1008467968, 1145389056,
    5, 242, 100, 0, -1933178670, 1075392583,
    0, 1, 116, 412,
    1130110728, -1028898805, -1012071969,
    1128808336, -1026271190, -1011854167,
    1128690196, -1025795314, -1011960695,
    1130262048, -1028966573, -1012223560,
    0, 997, 832, -550, 997, 21, 0, 997,
    -45, -27, 0, 27, 45,
    288, 3, 5, 0, 1088270893,
    -733177470, -1069257601, 1242094488, 1079995861,
)

NATIVE_WRAPPERS = {
    "FSin": (
        "XScalarSin",
        "\t{\n"
        "\t    DD 87 <dFA0 mtp bytesperunit>\t(fld  qword [edi+FA0*4])\n"
        "\t    D9 FE\t\t\t\t(fsin)\n"
        "\t    DD 9F <dFA0 mtp bytesperunit>\t(fstp qword [edi+FA0*4])\n"
        "\t}\n",
    ),
    "FCos": (
        "XScalarCos",
        "\t{\n"
        "\t    DD 87 <dFA0 mtp bytesperunit>\t(fld  qword [edi+FA0*4])\n"
        "\t    D9 FF\t\t\t\t(fcos)\n"
        "\t    DD 9F <dFA0 mtp bytesperunit>\t(fstp qword [edi+FA0*4])\n"
        "\t}\n",
    ),
    "FAtan2": (
        "XScalarAtan2",
        "\t{\n"
        "\t    DD 87 <dFA0 mtp bytesperunit>\t(fld  qword [edi+FA0*4])\n"
        "\t    DD 87 <dFB0 mtp bytesperunit>\t(fld  qword [edi+FB0*4])\n"
        "\t    D9 F3\t\t\t\t(fpatan)\n"
        "\t    DD 9F <dFA0 mtp bytesperunit>\t(fstp qword [edi+FA0*4])\n"
        "\t}\n",
    ),
}


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def tracked_work_files() -> list[Path]:
    process = subprocess.run(
        ["git", "ls-files", "-z", "--", "work"],
        cwd=ROOT, capture_output=True, check=True,
    )
    files = {
        Path(part.decode("utf-8"))
        for part in process.stdout.split(b"\0") if part
    }
    for extra in EXTRA_SOURCES:
        if (ROOT / extra).is_file():
            files.add(extra)
    return sorted(path for path in files if path not in PROTECTED)


def copy_sources(target: Path) -> Path:
    work = target / "work"
    for relative in tracked_work_files():
        source = ROOT / relative
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return work


def derive_full_game_probe(work: Path) -> None:
    source = work / "vhgame.txt"
    generated = work / "vhtransmain.txt"
    text = source.read_text(encoding="utf-8")
    libraries = "vhspace; vhstar; vhground; vhcapsule;"
    derived_libraries = "vhspace; vhstar; vhground; vhcapsule; vhtransprobe;"
    entry = "\t=> VHG run;\n\tend;"
    derived_entry = "\t=> VHTP run;\n\tend;"
    if text.count(libraries) != 1 or text.count(entry) != 1:
        raise RuntimeError("vhgame consumer-probe splice point changed")
    text = text.replace(libraries, derived_libraries, 1)
    text = text.replace(
        "program name = { vhgame };", "program name = { vhtransmain };", 1)
    text = text.replace(entry, derived_entry, 1)
    generated.write_text(text, encoding="utf-8", newline="\n")


def install_native_transcendentals(path: Path) -> None:
    text = path.read_text(encoding="latin-1")
    for label, (portable, native) in NATIVE_WRAPPERS.items():
        old = (
            f'"{label}"\n'
            "\t---->;\n"
            f"\t=> {portable};\n"
            "\t<----;\n"
            "\tend;\n"
        )
        new = f'"{label}"\n{native}\tend;\n'
        if text.count(old) != 1:
            raise RuntimeError(
                f"portable {label} wrapper changed; native-reference splice is stale")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="latin-1", newline="\n")


def fresh_variants() -> dict[str, Path]:
    if GEN.exists():
        shutil.rmtree(GEN)
    GEN.mkdir(parents=True)
    base = GEN / "base"
    copy_sources(base)
    variants = {}
    for name in ("portable", "native"):
        target = GEN / name
        shutil.copytree(base, target)
        variants[name] = target / "work"
        derive_full_game_probe(variants[name])
    shutil.rmtree(base)
    install_native_transcendentals(variants["native"] / "fp" / "fpx87.txt")
    return variants


def production_replay_tail(work: Path) -> bytes:
    """Return the culling replay body supplied by the copied game root."""
    source = (work / "vhgame.txt").read_bytes()
    start_marker = b'"PG terrain replay culling"'
    end_marker = b"\t-> PG terrain replay finish;"
    if source.count(start_marker) != 1:
        raise RuntimeError("expected one production culling replay entry")
    start = source.index(start_marker)
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError("production culling replay has no common finish")
    return source[start:end + len(end_marker)]


def production_profile_declaration(work: Path) -> str:
    """Return vhground's profiling storage declaration from the game root."""
    names = (
        "VHGprofpart", "VHGprofspace", "VHGprofcupola",
        "VHGprofhull", "VHGprofdetail",
    )
    lines = [
        line for line in (work / "vhgame.txt").read_text(encoding="utf-8").splitlines()
        if all(name in line for name in names)
    ]
    if len(lines) != 1:
        raise RuntimeError("expected one production surface-profile declaration")
    return lines[0]


def build_and_run(work: Path, probe: Probe) -> tuple[dict[str, bytes], str]:
    source = work / probe.source
    executable = source.with_suffix(".exe")
    outputs = {name: work / name for name in probe.outputs}
    for stale in (executable, *outputs.values()):
        if stale.exists():
            stale.unlink()
    pgtex = work / "pgtex.txt"
    pgtex_original: bytes | None = None
    if probe.source != "vhtransmain.txt":
        # pgtex owns the common replay entry while the production game root
        # owns its culling tail. Link the exact copied shared-Lino body only
        # while compiling modular probes; the full-game probe already has it.
        pgtex_original = pgtex.read_bytes()
        pgtex.write_bytes(
            pgtex_original + b"\n\n" + production_replay_tail(work) + b"\n"
        )
    source_original: str | None = None
    if probe.source == "vhtreeprobe.txt":
        source_original = source.read_text(encoding="utf-8")
        anchor = '"variables"\n\n'
        if source_original.count(anchor) != 1:
            raise RuntimeError("tree probe variables anchor changed")
        source.write_text(
            source_original.replace(
                anchor,
                anchor + production_profile_declaration(work) + "\n",
                1,
            ),
            encoding="utf-8",
            newline="\n",
        )
    try:
        rc, build_note = lh.build(str(source), timeout_sec=300)
    finally:
        if pgtex_original is not None:
            pgtex.write_bytes(pgtex_original)
        if source_original is not None:
            source.write_text(source_original, encoding="utf-8", newline="\n")
    if rc or not executable.is_file():
        errorlog = lh.errorlog_for(str(source))
        raise RuntimeError(
            f"build failed for {source}:\n{build_note[-3000:]}\n{errorlog[-3000:]}")
    rc, run_note, _ = lh.run(
        str(executable), str(work / probe.sentinel), timeout_sec=probe.timeout)
    missing = [name for name, path in outputs.items() if not path.is_file()]
    if rc or missing:
        raise RuntimeError(
            f"run failed for {executable}: {run_note}; missing {missing}")
    return ({name: path.read_bytes() for name, path in outputs.items()},
            build_note.strip())


def main() -> int:
    if sys.platform != "win32":
        print("FAIL executable consumer comparison requires the Windows compiler/runtime")
        return 2

    check = lh.Check("portable transcendental production consumers")
    copied_inputs = tracked_work_files()
    root_hashes = {
        relative: sha256((ROOT / relative).read_bytes())
        for relative in copied_inputs
    }
    variants = fresh_variants()
    results: dict[str, dict[str, bytes]] = {}
    for variant, work in variants.items():
        result: dict[str, bytes] = {}
        for probe in PROBES:
            blobs, note = build_and_run(work, probe)
            result.update(blobs)
            check.ok(bool(blobs), f"{variant} {probe.source} builds and emits output",
                     note.splitlines()[-1] if note else "compiled")
        results[variant] = result

    check.eq(sorted(results["portable"]), sorted(results["native"]),
             "portable and native-reference runs emit the same files")
    for name in sorted(results["portable"]):
        portable = results["portable"][name]
        native = results["native"][name]
        check.eq(len(portable), EXPECTED_SIZE[name], f"{name} has its exact size")
        check.ok(portable == native,
                 f"{name} is byte-identical with native x87 transcendental consumers",
                 f"sha256 {sha256(portable)}")
        check.eq(sha256(portable), EXPECTED_SHA256[name],
                 f"{name} retains its pinned output hash")

    capsule = struct.unpack("<24i", results["portable"]["vhcapsule-out.bin"])
    check.eq(capsule, EXPECTED_CAPSULE,
             "capsule state pins wind, drift, touchdown, seal, and ascent")
    tree = struct.unpack("<10i", results["portable"]["vhtree-out.bin"])
    check.eq(tree, EXPECTED_TREE,
             "flat-fixture tree state pins orientation and rendered geometry")
    check.ok(tree[-2:] == (0, 0),
             "tree smoke records that optional captured texture/height inputs were absent")

    trans = struct.unpack("<64i", results["portable"]["vhtrans-state.bin"])
    check.eq(trans[:len(EXPECTED_TRANS_STATE)], EXPECTED_TRANS_STATE,
             "full-game state pins camera/walk, globe, Euler model, animal, and viewpoint consumers")
    check.ok(not any(trans[len(EXPECTED_TRANS_STATE):]),
             "full-game state has a deterministic zero-filled tail")
    check.eq(trans[33:41], (0, 997, 832, -550, 997, 21, 0, 997),
             "animal heading pins sine/cosine movement at four hundredth-degree angles")
    check.eq(trans[41:46], (-45, -27, 0, 27, 45),
             "animal incline pins clamping, signed atan2, degree conversion, and rounding")
    check.eq(trans[46], 288,
             "retained-system viewpoint pins the production orbital atan2 result")

    after_hashes = {
        relative: sha256((ROOT / relative).read_bytes())
        for relative in copied_inputs
    }
    changed_inputs = [
        str(relative) for relative in copied_inputs
        if after_hashes[relative] != root_hashes[relative]
    ]
    check.ok(not changed_inputs,
             "the isolated comparison leaves every copied production input unchanged",
             f"changed: {changed_inputs[:10]}" if changed_inputs else "")
    return check.done()


if __name__ == "__main__":
    raise SystemExit(main())
