"""Guard the complete shipping Lino dependency closure against native escapes.

Run: python tests/test_native_closure.py
"""
from pathlib import Path
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


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS", message)


def main():
    closure, edges, blocks = gate.scan(gate.DEFAULT_ROOTS)
    check(len(closure) > 2 and edges >= len(closure) - 2,
          "shipping roots are checked through their transitive libraries")
    check(not blocks and not gate.block_errors(blocks),
          "the complete production closure contains zero native blocks")
    inventory = gate.float_inventory(closure)
    check(inventory == gate.FLOAT_SIGNATURES and not gate.float_errors(closure),
          "the 36 reviewed ordinary Lino float operations remain in three files")
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
