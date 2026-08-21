"""Pin the fixed production floating-point environment below Lino.

Run: python tests/test_fp_runtime_boundary.py
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
WIN32 = ROOT / "main" / "sys" / "win32.bin"
LINUX = ROOT / "src" / "linoleum_linux32" / "isokernel.s"
MACOS = ROOT / "src" / "linoleum_macos64" / "isokernel.s"
FPCTL = ROOT / "work" / "fp" / "fpctl.txt"
BUILD = ROOT / "lino_build.ps1"
HOST_PROBE = ROOT / "tests" / "macos_fcw_probe.c"
HOST_RUNNER = ROOT / "tests" / "run_macos_fcw_probe.sh"
MACOS_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "macos-runtime.yml",
    ROOT / ".github" / "workflows" / "macos-rosetta-nivgen.yml",
    ROOT / ".github" / "workflows" / "tagged-release.yml",
)
sys.path.insert(0, str(ROOT / "tools"))
import patch_runtime_fcw  # noqa: E402

OLD_CHOP = patch_runtime_fcw.OLD_CONTROL
LOAD_EXT = patch_runtime_fcw.FIXED_CONTROL
WIN_SITE = re.compile(
    rb"\x9b\xd9\x3d(?P<word>.{4})"
    rb"\x66\xa1(?P=word)" + re.escape(OLD_CHOP) +
    rb"\x66\xa3(?P=word)\xd9\x2d(?P=word)",
    re.DOTALL,
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS", message)


def source_checks(path, call_symbol, entry_pattern, fcw_operand, constant_pattern):
    text = path.read_text(encoding="utf-8")
    target = path.parent.name
    check(text.count("fldcw") == 2,
          f"{target} has exactly two explicit FP-boundary reloads")
    check(re.search(rf"call\s+{re.escape(call_symbol)}.*?fldcw\s+{fcw_operand}",
                    text, re.DOTALL) is not None,
          f"{target} reloads FCWEXT immediately after every C isocall")
    check(re.search(rf"fldcw\s+{fcw_operand}.*?call\s+{entry_pattern}",
                    text, re.DOTALL) is not None,
          f"{target} installs FCWEXT before application entry")
    check(len(re.findall(constant_pattern, text)) == 1,
          f"{target} defines one exact 0x133f control word")


def main():
    win = WIN32.read_bytes()
    sites = list(WIN_SITE.finditer(win))
    check(win.count(OLD_CHOP) == 8 and len(sites) == 8,
          "all eight protected Windows runtime variants retain their upstream bytes")
    check(LOAD_EXT not in win,
          "the fixed control sequence is not written into the protected runtime")
    check(len({match.group("word") for match in sites}) == 8,
          "the eight Windows sites address their eight distinct control slots")

    synthetic = b"PE-prefix" + OLD_CHOP + b"-payload"
    patched = patch_runtime_fcw.patch_image(synthetic)
    check(patched == b"PE-prefix" + LOAD_EXT + b"-payload" and
          len(patched) == len(synthetic),
          "post-link patch changes only one size-preserving control sequence")
    rejected = 0
    for invalid in (b"no runtime", synthetic + OLD_CHOP, patched):
        try:
            patch_runtime_fcw.patch_image(invalid)
        except ValueError:
            rejected += 1
    check(rejected == 3,
          "post-link patch rejects missing, duplicate, and already-patched runtimes")
    build = BUILD.read_text(encoding="utf-8")
    check("tools\\patch_runtime_fcw.py" in build and
          "& python $runtimePatcher $built" in build and
          build.index("Move-Item -LiteralPath $built") <
          build.index("& python $runtimePatcher $built") <
          build.index("elseif ($built -and $settled"),
          "build wrapper patches the settled output PE before reporting success")

    source_checks(
        LINUX, "ISOKRNLCALL", r"\*pCodeEntry", r"\.L_lino_fcw",
        r"\.short\s+0x133f",
    )
    source_checks(
        MACOS, "_ISOKRNLCALL", r"\*%rax", r"L_lino_fcw\(%rip\)",
        r"\.short\s+0x133f",
    )

    probe = HOST_PROBE.read_text(encoding="utf-8")
    check(probe.count('"fnstcw %0"') == 1 and
          probe.count('"fldcw %0"') == 1 and
          "#define LINO_FCW_EXT UINT16_C(0x133f)" in probe and
          "#define LINO_FCW_DOUBLE UINT16_C(0x123f)" in probe and
          "#define LINO_FCW_MASK UINT16_C(0x0f3f)" in probe,
          "host probe reads, perturbs, and restores the exact x87 control word")
    runner = HOST_RUNNER.read_text(encoding="utf-8")
    check("-arch x86_64 -mmacosx-version-min=10.15" in runner and
          'arch -x86_64 "$out"' in runner and
          "^FCW_HOST_PROBE_OK " in runner,
          "host probe runner builds one x86_64 Mach-O and requires exact success")
    for workflow_path in MACOS_WORKFLOWS:
        workflow = workflow_path.read_text(encoding="utf-8")
        check("bash tests/run_macos_fcw_probe.sh" in workflow and
              (workflow_path.stem == "tagged-release" or
               ("tests/macos_fcw_probe.c" in workflow and
                "tests/run_macos_fcw_probe.sh" in workflow)),
              f"{workflow_path.stem} executes the hosted x87 boundary probe")
    rosetta_workflow = MACOS_WORKFLOWS[1].read_text(encoding="utf-8")
    check(re.search(r"(?m)^  pull_request:\s*$", rosetta_workflow) and
          '      - "work/**.txt"' in rosetta_workflow,
          "Rosetta game validation runs on production-source pull requests")
    check("uniform white 0x3f palette" in rosetta_workflow,
          "Rosetta NIVGEN rejects the flat-white palette regression")

    production = FPCTL.read_text(encoding="latin-1")
    check("{" not in production and "}" not in production,
          "production fpctl contains no target-machine escape block")
    check("[FCW] = FCWEXT" in production and "[FI] = 033Fh" in production,
          "portable fpctl exposes only the fixed FCWEXT state contract")

    print("FP runtime boundary: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
