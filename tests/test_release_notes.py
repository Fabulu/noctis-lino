"""Keep tagged GitHub release bodies limited to their own note section."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "release_notes_for_tag.py"
NOTES = ROOT / "RELEASE_NOTES.md"
WORKFLOW = ROOT / ".github" / "workflows" / "tagged-release.yml"
spec = importlib.util.spec_from_file_location("release_notes_for_tag", SCRIPT)
notes_tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(notes_tool)


def main() -> int:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if condition:
            print("PASS", message)
        else:
            print("FAIL", message)
            errors.append(message)

    text = NOTES.read_text(encoding="utf-8")
    numbers = [int(match.group(1)) for match in notes_tool.BETA_HEADING_RE.finditer(text)]
    check(numbers == list(range(23, 8, -1)),
          "release-note headings are unique and ordered Beta 23 through Beta 9")

    for number in numbers:
        tag = f"v0.1.0-beta.{number}"
        section = notes_tool.release_notes(text, tag)
        first_line = section.splitlines()[0]
        check(first_line.lower().startswith(f"## beta {number}"),
              f"{tag} selects its own heading")
        check("\n## " not in section,
              f"{tag} does not include another release")

    for bad in ("v0.1.0", "v0.1.0-beta.0", "v0.1.0-beta.24"):
        try:
            notes_tool.release_notes(text, bad)
        except ValueError:
            check(True, f"unsupported tag {bad!r} is rejected")
        else:
            check(False, f"unsupported tag {bad!r} is rejected")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    check("self-hosted" not in workflow and "lino-gui" not in workflow,
          "tagged publication has no optional self-hosted runner dependency")
    check("needs: [validate, numerical]" not in workflow,
          "hosted Windows and macOS tagged builds depend only on hosted validation")
    check("gh release edit" not in workflow,
          "rerunning an existing tag cannot overwrite its release body")
    check("gh release upload $tag @files --clobber" in workflow and
          "Existing release body preserved" in workflow,
          "rerunning an existing tag replaces only generated assets")
    check("uses: ./.github/workflows/macos-aarch64-runtime.yml" in workflow and
          "tagged_release: true" in workflow and
          "package_artifact_name: Noctis-IV-macos-arm64-${{ github.ref_name }}"
          in workflow,
          "tagged publication calls the proven native ARM64 product gate")
    check("needs: [package, mac_package, arm64_package]" in workflow and
          "name: Noctis-IV-macos-arm64-${{ github.ref_name }}" in workflow,
          "publication waits for and downloads the tested ARM64 package")
    check(all(name in workflow for name in (
              "Noctis-IV-macos-arm64.zip",
              "Noctis-IV-macos-arm64.zip.sha256",
              "Noctis-IV-macos-arm64.provenance.txt",
          )),
          "ARM64 archive, checksum, and provenance are release assets")

    with tempfile.TemporaryDirectory(prefix="noctis-release-notes-") as directory:
        output = Path(directory) / "notes.md"
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "v0.1.0-beta.23", "--output", str(output)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        check(process.returncode == 0 and output.is_file(),
              "command-line extractor writes a release body")
        if output.is_file():
            check(output.read_text(encoding="utf-8") == notes_tool.release_notes(
                text, "v0.1.0-beta.23"),
                  "command-line output matches the in-process section")

    if errors:
        print(f"release-note extraction: {len(errors)} failure(s)")
        return 1
    print("release-note extraction: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
