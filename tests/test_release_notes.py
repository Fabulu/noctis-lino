"""Keep tagged GitHub release bodies limited to their own note section."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
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
    check(text.startswith("# Noctis IV L.in.oleum port -- release history\n"),
          "release-note title describes stable release history")

    stable_headings = [
        ".".join(match.groups())
        for match in notes_tool.STABLE_HEADING_RE.finditer(text)
    ]
    check(stable_headings == ["1.0.0"],
          "release notes contain one exact v1.0.0 stable heading")
    stable_section = notes_tool.release_notes(text, "v1.0.0")
    check(stable_section.startswith("## v1.0.0\n"),
          "v1.0.0 selects its stable heading")
    check("\n## " not in stable_section and "Beta 26" not in stable_section,
          "v1.0.0 stops at the next release boundary")

    duplicate_stable = text.replace("## Beta 26", "## v1.0.0\n\nduplicate\n\n## Beta 26", 1)
    try:
        notes_tool.release_notes(duplicate_stable, "v1.0.0")
    except ValueError:
        check(True, "duplicate stable release sections are rejected")
    else:
        check(False, "duplicate stable release sections are rejected")

    numbers = [int(match.group(1)) for match in notes_tool.BETA_HEADING_RE.finditer(text)]
    check(numbers == list(range(26, 8, -1)),
          "release-note headings are unique and ordered Beta 26 through Beta 9")

    for number in numbers:
        tag = f"v0.1.0-beta.{number}"
        section = notes_tool.release_notes(text, tag)
        first_line = section.splitlines()[0]
        check(first_line.lower().startswith(f"## beta {number}"),
              f"{tag} selects its own heading")
        check("\n## " not in section,
              f"{tag} does not include another release")

    for bad in (
        "1.0.0", "V1.0.0", "v01.0.0", "v1.0", "v1.0.0-rc.1", "v1.0.1",
        "v0.1.0", "v0.1.0-beta.0", "v0.1.0-beta.27",
    ):
        try:
            notes_tool.release_notes(text, bad)
        except ValueError:
            check(True, f"unsupported tag {bad!r} is rejected")
        else:
            check(False, f"unsupported tag {bad!r} is rejected")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    check("name: Publish the GitHub release" in workflow and
          "name: Publish the GitHub prerelease" not in workflow,
          "publication job is not classified as prerelease-only")
    early_tag_check = (
        "python tools\\release_notes_for_tag.py $env:GITHUB_REF_NAME "
        "--output build\\tag-release-notes.md"
    )
    check(workflow.count(early_tag_check) == 1 and
          workflow.index(early_tag_check) < workflow.index("  compile:"),
          "the actual pushed tag's note section is validated before builds")
    check(
        "$isStable = $tag -cmatch '^v(?:0|[1-9][0-9]*)\\."
        "(?:0|[1-9][0-9]*)\\.(?:0|[1-9][0-9]*)$'" in workflow and
        "if (-not $isStable) { $releaseArgs += '--prerelease' }" in workflow and
        "gh release create $tag @files" not in workflow,
        "stable tags omit --prerelease while beta tags retain it",
    )
    expected_assets = (
        "Noctis-IV-windows-x86.zip",
        "Noctis-IV-windows-x86.zip.sha256",
        "Noctis-IV-windows-x86.provenance.txt",
        "Noctis-IV-macos-x86_64.zip",
        "Noctis-IV-macos-x86_64.zip.sha256",
        "Noctis-IV-macos-x86_64.provenance.txt",
        "Noctis-IV-macos-arm64.zip",
        "Noctis-IV-macos-arm64.zip.sha256",
        "Noctis-IV-macos-arm64.provenance.txt",
    )
    files_block = re.search(r"\$files = @\((.*?)\n\s*\)", workflow, re.DOTALL)
    manifest_assets = tuple(re.findall(r"'dist\\([^']+)'", files_block.group(1))) \
        if files_block else ()
    check(manifest_assets == expected_assets and len(set(manifest_assets)) == 9,
          "release manifest contains exactly nine unique canonical assets")
    check("Downloaded assets do not exactly match the nine-file release manifest"
          in workflow and
          "Published release does not contain exactly the nine canonical assets"
          in workflow,
          "publication checks the local and remote exact-nine asset invariant")
    check("refusing destructive cleanup" in workflow,
          "reruns fail rather than deleting unexpected existing assets")
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
        for tag in ("v1.0.0", "v0.1.0-beta.26"):
            output = Path(directory) / f"{tag}.md"
            process = subprocess.run(
                [sys.executable, str(SCRIPT), tag, "--output", str(output)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            check(process.returncode == 0 and output.is_file(),
                  f"command-line extractor writes the {tag} release body")
            if output.is_file():
                check(output.read_text(encoding="utf-8") == notes_tool.release_notes(
                    text, tag),
                      f"command-line {tag} output matches in-process extraction")

    if errors:
        print(f"release-note extraction: {len(errors)} failure(s)")
        return 1
    print("release-note extraction: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
