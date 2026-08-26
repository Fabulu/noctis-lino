"""Guard the complete shipping Lino dependency closure against native escapes.

Run: python tests/test_native_closure.py
"""
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_lino_native_closure as gate


X87_SIGNATURES = (
    ("FReset", "DB E3"),
    ("FEnter", "9B D9 BF <dFCWSAV mtp bytesperunit>"),
    ("FEnter", "D9 AF <dFCW mtp bytesperunit>"),
    ("FLeave", "D9 AF <dFCWSAV mtp bytesperunit>"),
    ("FLoadCW", "D9 AF <dFCW mtp bytesperunit>"),
    ("FCWRead", "9B D9 BF <dFCWTMP mtp bytesperunit>"),
    ("FSWRead", "9B DD BF <dFSW mtp bytesperunit>"),
)
CANONICAL_ROOTS = tuple(
    (ROOT / relative).resolve()
    for relative in ("work/vhgame.txt", "work/vhnivgen.txt")
)
CANONICAL_SHARED_MODULES = tuple(
    (ROOT / relative).resolve()
    for relative in (
        "work/fp/fpconv.txt",
        "work/fp/fpx87.txt",
        "work/mul64frag.txt",
        "work/pgproj.txt",
        "work/pgtex.txt",
        "work/vhgame.txt",
        "work/vhground.txt",
        "work/vhspace.txt",
    )
)
BUILD_ROUTE_FILES = (
    "build/compile_vhgame_linux.sh",
    "build/compile_noctis_macos_linux.sh",
    ".github/workflows/source-release.yml",
    ".github/workflows/windows-release.yml",
    ".github/workflows/macos-aarch64-runtime.yml",
    ".github/workflows/tagged-release.yml",
)
BUILD_SOURCE_PATTERNS = {
    "build/compile_vhgame_linux.sh": re.compile(
        r'^source="\$repo/(?P<source>[^"\r\n]+\.txt)"$', re.MULTILINE),
    "build/compile_noctis_macos_linux.sh": re.compile(
        r'^source="\$repo/(?P<source>[^"\r\n]+\.txt)"$', re.MULTILINE),
    ".github/workflows/source-release.yml": re.compile(
        r'-Src "\$PWD\\(?P<source>[^"\r\n]+\.txt)"'),
}
REQUIRED_BUILD_TEXT = {
    "build/compile_vhgame_linux.sh": (
        '--sys:win32--cpu:i386m--ext:.lxe--env:$repo/main--src:$source',
        '("source_sha256", sha256(repo / "work/vhgame.txt"))',
    ),
    "build/compile_noctis_macos_linux.sh": (
        '--sys:macos--cpu:x64--ext:.exe--env:$repo/main--src:$source',
        '("source_sha256", sha256(repo / "work/vhgame.txt"))',
    ),
    ".github/workflows/source-release.yml": (
        '-Compiler "$PWD\\main\\lib\\gen\\compiler114m.exe"',
        "-Cpu i386m",
        "-StageExtension .lxe",
        "Get-FileHash -LiteralPath work\\vhgame.txt",
        '"source_sha256=$sourceHash"',
    ),
    ".github/workflows/windows-release.yml": (
        "'commit', 'source_sha256',",
        "Get-FileHash -LiteralPath work\\vhgame.txt",
        "$values.source_sha256 -ne $sourceHash",
    ),
    ".github/workflows/macos-aarch64-runtime.yml": (
        "work/vhgame.txt \\\n            build/macos-aarch64-noctis.unsigned \\\n            tracked-work",
    ),
    ".github/workflows/tagged-release.yml": (
        "'commit', 'source_sha256',",
        "Get-FileHash -LiteralPath work\\vhgame.txt",
        "$values.source_sha256 -ne $sourceHash",
    ),
}
FORBIDDEN_BUILD_TEXT = (
    "stage_windows_i386_source",
    "windows-i386-source",
    "source_manifest_sha256",
    "src/linoleum_i386",
    "src\\linoleum_i386",
)


def target_source_errors(paths):
    errors = []
    for path in paths:
        try:
            relative = path.resolve().relative_to(ROOT)
        except ValueError:
            continue
        parts = relative.parts
        if (len(parts) >= 3 and parts[0] == "src" and
                parts[1].startswith("linoleum_") and
                path.suffix.lower() == ".txt"):
            errors.append(
                f"target-specific Lino source is forbidden: {relative.as_posix()}"
            )
    return errors


def build_route_errors(route_texts):
    errors = []
    for relative, text in route_texts.items():
        for marker in FORBIDDEN_BUILD_TEXT:
            if marker in text:
                errors.append(f"{relative} contains forbidden source routing {marker!r}")
        for required in REQUIRED_BUILD_TEXT.get(relative, ()):
            if required not in text:
                errors.append(f"{relative} lacks canonical build text {required!r}")
    for relative, pattern in BUILD_SOURCE_PATTERNS.items():
        sources = [match.replace("\\", "/")
                   for match in pattern.findall(route_texts.get(relative, ""))]
        if sources != ["work/vhgame.txt"]:
            errors.append(
                f"{relative} must select exactly work/vhgame.txt, got {sources!r}"
            )
    return errors


def read_build_routes():
    return {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in BUILD_ROUTE_FILES
    }


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS", message)


def main():
    check(tuple(path.resolve() for path in gate.DEFAULT_ROOTS) == CANONICAL_ROOTS,
          "production roots are exactly work/vhgame.txt and work/vhnivgen.txt")
    closure, edges, blocks = gate.scan(gate.DEFAULT_ROOTS)
    check(set(CANONICAL_SHARED_MODULES).issubset(closure),
          "production uses the canonical shared renderer, gameplay, multiply, and FP modules")
    check(not target_source_errors(gate.tracked_sources()),
          "tracked platform runtime trees contain no target-specific Lino source")
    routes = read_build_routes()
    check(not build_route_errors(routes),
          "shipping build and provenance routes consume canonical work/vhgame.txt")

    synthetic_overlay = ROOT / "src" / "linoleum_synthetic" / "vhground.txt"
    check(target_source_errors((synthetic_overlay,)),
          "a synthetic platform-specific Lino source fork is rejected")
    alternate_routes = dict(routes)
    alternate_routes["build/compile_vhgame_linux.sh"] = alternate_routes[
        "build/compile_vhgame_linux.sh"
    ].replace("work/vhgame.txt", "build/alternate/vhgame.txt")
    check(build_route_errors(alternate_routes),
          "a synthetic alternate production source root is rejected")

    check(len(closure) > 2 and edges >= len(closure) - 2,
          "shipping roots are checked through their transitive libraries")
    check(not blocks and not gate.block_errors(blocks),
          "the complete production closure contains zero native blocks")
    inventory = gate.float_inventory(closure)
    check(not gate.float_errors(closure) and
          sum(len(lines) for lines in inventory.values()) == 263 and
          len(inventory) == 8,
          "the 263 reviewed Lino float operations remain in eight files")
    check(all("??" not in line
              for lines in inventory.values() for line in lines),
          "production has no target-dependent floating comparison")

    x87_path = ROOT / "work" / "fp" / "fpctlx87.txt"
    x87_blocks = gate.raw_blocks(x87_path)
    check(tuple((block.label, block.body) for block in x87_blocks) ==
          X87_SIGNATURES,
          "the test-only x87 witness contains its seven exact pinned blocks")
    check(x87_path.resolve() not in closure,
          "the test-only x87 witness is outside the production closure")
    check(gate.block_errors(x87_blocks) and
          all("forbidden raw target block" in error
              for error in gate.block_errors(x87_blocks)),
          "the production policy rejects every test-only x87 block")

    index = gate.build_index()
    owner = ROOT / "work" / "vhgame.txt"
    check(gate.resolve_library(owner, "work/fp/fpabi", index) ==
          (ROOT / "work" / "fp" / "fpabi.txt").resolve(),
          "an explicit work/ library resolves from the repository root")
    check(gate.resolve_library(owner, "main/lib/gen/rect", index) ==
          (ROOT / "main" / "lib" / "gen" / "rect.txt").resolve(),
          "an explicit main/ library resolves from the repository root")
    check(gate.resolve_library(owner, "/gen/rect", index) ==
          (ROOT / "main" / "lib" / "gen" / "rect.txt").resolve(),
          "a stock /gen/ library resolves beneath main/lib")

    with tempfile.TemporaryDirectory(prefix="lino-native-gate-") as directory:
        root = Path(directory)
        (root / "root.txt").write_text(
            '"libraries"\n\n child;\n\n"programme"\n end;\n',
            encoding="latin-1",
        )
        child = root / "child.txt"
        child.write_text(
            '( a documented C fragment {\n  is not executable\n} )\n'
            'data = { a parenthesis ( is literal };\n'
            '{ force }; 1;\n'
            '"programme"\n'
            '"multi"\n'
            '{\n  D9 FE\n}\n'
            '"one"\n'
            '{ D9 FF }\n'
            '"semicolon"\n'
            '{ D9 FC };\n',
            encoding="latin-1",
        )
        fixture_closure, fixture_edges, fixture_blocks = gate.scan(
            [root / "root.txt"]
        )
        check(len(fixture_closure) == 2 and fixture_edges == 1,
              "a native block imported one level down is reached")
        check([(block.path, block.start, block.end, block.label, block.body)
               for block in fixture_blocks] == [
                   (child.resolve(), 8, 10, "multi", "D9 FE"),
                   (child.resolve(), 12, 12, "one", "D9 FF"),
                   (child.resolve(), 14, 14, "semicolon", "D9 FC"),
               ],
              "comments and data strings are ignored while multiline, one-line, "
              "and semicolon-suffixed programme blocks fail")

    with tempfile.TemporaryDirectory(
            prefix="lino-native-gate-in-repo-", dir=ROOT / "tests") as directory:
        root = Path(directory)
        (root / "root.txt").write_text(
            '"libraries"\n\n child;\n\n"programme"\n end;\n',
            encoding="latin-1",
        )
        (root / "child.txt").write_text(
            '"programme"\n end;\n', encoding="latin-1")
        try:
            gate.scan([root / "root.txt"])
        except ValueError as exc:
            rejected = "resolves to untracked source" in str(exc)
        else:
            rejected = False
        check(rejected,
              "an in-repository owner cannot import an untracked sibling")

    print("native closure gate: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
