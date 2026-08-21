#!/usr/bin/env python3
"""Extract the one RELEASE_NOTES.md section belonging to a release tag."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTES = ROOT / "RELEASE_NOTES.md"
TAG_RE = re.compile(r"(?:^|[-_.])beta[-_.]?(\d+)$", re.IGNORECASE)
BETA_HEADING_RE = re.compile(
    r"^##[ \t]+Beta[ \t]+(\d+)(?:[ \t]+.*)?$", re.IGNORECASE | re.MULTILINE
)
H2_RE = re.compile(r"^##(?!#)[ \t]+\S.*$", re.MULTILINE)


def beta_number(tag: str) -> int:
    match = TAG_RE.search(tag.strip())
    if not match:
        raise ValueError(f"release tag does not end in a beta number: {tag!r}")
    return int(match.group(1))


def release_notes(text: str, tag: str) -> str:
    number = beta_number(tag)
    matches = [
        match for match in BETA_HEADING_RE.finditer(text)
        if int(match.group(1)) == number
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one '## Beta {number}' section, found {len(matches)}"
        )
    start = matches[0].start()
    following = H2_RE.search(text, matches[0].end())
    end = following.start() if following else len(text)
    section = text[start:end].strip()
    if not section or "\n## " in section:
        raise ValueError(f"Beta {number} section boundary is ambiguous")
    return section + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", help="release tag, for example v0.1.0-beta.22")
    parser.add_argument("--notes", type=Path, default=DEFAULT_NOTES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        text = args.notes.read_text(encoding="utf-8")
        section = release_notes(text, args.tag)
    except (OSError, ValueError) as exc:
        print(f"FAIL release notes: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(section, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
