#!/usr/bin/env python3
"""Reject target-machine blocks in the transitive production Lino closure.

A source-only grep is too weak: a clean game root can import an opcode block
through any library. This scanner follows the actual ``"libraries"`` sections
from the shipping roots and requires the entire production closure to contain
zero raw target blocks. Deliberate negative and reconstruction fixtures are
outside the dependency closure and therefore remain valid tests.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (ROOT / "work" / "vhgame.txt", ROOT / "work" / "vhnivgen.txt")
SECTION_RE = re.compile(r'^\s*"([^"]+)"\s*$', re.MULTILINE)
PERIOD_NAMES = {
    "constants", "variables", "workspace", "libraries", "directors",
    "programme",
}
FLOAT_OPERATOR_RE = re.compile(
    r"\?\?(?:!=|>=|<=|=|>|<)\s*->|"
    r"(?<!\+)\+\+(?!\+)|(?<![<-])--(?!-)(?!>)|"
    r"(?<!\*)\*\*(?!\*)|(?<!/)//(?!/)|=,|,=|"
    r"\+:|-:|\*:|/:|=:|:=|~:"
)
FLOAT_SIGNATURES = {
    "main/lib/gen/rect.txt": (
        "[RECT Pixels] ,= [RECT Pixels];",
        "[RECT Scanlines] ,= [RECT Scanlines];",
        "[RECT V Delta Red] -- [B plus 0];",
        "[RECT V Delta Red] // [RECT Scanlines];",
        "[RECT V Delta Green] -- [B plus 1];",
        "[RECT V Delta Green] // [RECT Scanlines];",
        "[RECT V Delta Blue] -- [B plus 2];",
        "[RECT V Delta Blue] // [RECT Scanlines];",
        "[RECT H Delta Red] -- [B plus 0];",
        "[RECT H Delta Red] // [RECT Pixels];",
        "[RECT H Delta Green] -- [B plus 1];",
        "[RECT H Delta Green] // [RECT Pixels];",
        "[RECT H Delta Blue] -- [B plus 2];",
        "[RECT H Delta Blue] // [RECT Pixels];",
        "[RECT Pixels] =, [RECT Pixels];",
        "[RECT Scanlines] =, [RECT Scanlines];",
        "B = [RECT H Start Red]; B ** 255f; B =, B;",
        "C = [RECT H Start Green]; C ** 255f; C =, C;",
        "D = [RECT H Start Blue]; D ** 255f; D =, D;",
        "[RECT H Start Red] ++ [RECT H Delta Red];",
        "[RECT H Start Green] ++ [RECT H Delta Green];",
        "[RECT H Start Blue] ++ [RECT H Delta Blue];",
        "[RECT V Start Red] ++ [RECT V Delta Red];",
        "[RECT V Start Green] ++ [RECT V Delta Green];",
        "[RECT V Start Blue] ++ [RECT V Delta Blue];",
    ),
    "work/fp/fpconv.txt": (
        "[CVTMP] = [FS0]; [FS0] ,= [FI]; => CV F32 to F64;",
    ),
    "work/pgfp.txt": (
        "~: [FA0];",
        "[FA0] +: [A];",
        "[FA0] -: [A];",
        "[FA0] *: [A];",
        "[FA0] /: [A];",
        "A = FT0; [FA0] -: [A];",
        "A = FT0; [FA0] /: [A];",
        "[FI] =: [FA0];",
        "[FA0] := [FI];",
    ),
    "work/pgtex.txt": (
        "A = [EWx2]; C = [EWx1]; A - C; [FI] = A; [FA0] := [FI];",
        "A = [EWy2]; C = [EWy1]; A - C; [FI] = A; [FA0] := [FI];",
        "[FA0] /: [FB0];",
        "[FI] = [EWx1]; [FA0] := [FI];",
        "A = PGLBY; C = [EWy1]; A - C; [FI] = A; [FA0] := [FI];",
        "[FA0] +: [FB0];",
        "[FI] =: [FA0];",
        "[FI] = [EWx1]; [FA0] := [FI];",
        "[FA0] +: [fw plus 22];",
        "~: [FA0]; [fw plus 30] = [FA0]; [fw plus 31] = [FA1];",
        "[FA0] +: [fw plus 18];",
        "~: [FA0]; [fw plus 26] = [FA0]; [fw plus 27] = [FA1];",
        "[FA0] +: [fw plus 20];",
        "~: [FA0]; [fw plus 28] = [FA0]; [fw plus 29] = [FA1];",
        "[FA0] /: [FT0];",
        "~: [FA0]; [fw plus 24] = [FA0]; [fw plus 25] = [FA1];",
        "[FA0] *: [fw plus 32];",
        "[FA0] *: [fw plus 24];",
        "[FI] =: [FA0]; [SPun] = [FI];",
        "[FA0] *: [fw plus 34];",
        "[FA0] *: [fw plus 24];",
        "[FI] =: [FA0]; [SPvn] = [FI];",
    ),
    "work/supaint.txt": (
        "[SFpx] -- [KF360];",
        "[SFpx] ++ [KF360];",
        "[SFpy] -- [KF180];",
        "[SFpy] ++ [KF180];",
        "[SFa] -- [SFth];",
        "[SFa] ** [SFkq];",
        "[SFa] ** [SFkt];",
        "[SFa] ++ [SFth];",
    ),
    "work/supal.txt": (
        "[SFsr] ++ [SFdr];",
        "[SFsg] ++ [SFdg];",
        "[SFsb] ++ [SFdb];",
    ),
}

# The direct terrain basis is deliberately large.  A count plus an ordered-line
# digest pins it just as strictly as the readable tuples above without copying
# the complete exact schedule into this policy file.
FLOAT_SIGNATURE_HASHES = {
    "work/pgproj.txt": (
        148,
        "75b628b703b14ba1947c758771bf03dc5e5cdebf59d286b6b131aa98b8e130da",
    ),
}


@dataclass(frozen=True)
class RawBlock:
    path: Path
    start: int
    end: int
    label: str
    body: str


def without_comments(text):
    """Blank nested Lino comments while retaining line positions.

    Parentheses inside brace strings are data, not comments. Outside the
    ``"programme"`` period, a brace string is identified by its required
    semicolon immediately after the closing brace. Inside ``"programme"``,
    however, the compiler emits every brace body's bytes even when a stray
    semicolon follows it, so those braces must remain visible to the native-
    block parser.
    """
    depth = 0
    clean = []
    index = 0
    while index < len(text):
        char = text[index]
        if depth == 0 and char == "{":
            line_end = text.find("\n", index)
            if line_end < 0:
                line_end = len(text)
            literal_end = text.find("}", index + 1, line_end)
            if literal_end >= 0 and re.match(
                    r"[ \t]*;", text[literal_end + 1:line_end]):
                clean.append(text[index:literal_end + 1])
                index = literal_end + 1
                continue
        if char == "(":
            depth += 1
            clean.append(" ")
        elif char == ")" and depth:
            depth -= 1
            clean.append(" ")
        elif depth:
            clean.append("\n" if char == "\n" else " ")
        else:
            clean.append(char)
        index += 1
    if depth:
        raise ValueError("unclosed Lino comment")
    return "".join(clean)


def libraries(path):
    try:
        text = without_comments(path.read_text(encoding="latin-1"))
    except ValueError as exc:
        raise ValueError(f"{display_path(path)}: {exc}") from exc
    sections = list(SECTION_RE.finditer(text))
    for i, match in enumerate(sections):
        if match.group(1).strip().lower() != "libraries":
            continue
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[match.end():end]
        return [token.strip() for token in body.split(";") if token.strip()]
    return []


def raw_blocks(path):
    try:
        text = without_comments(path.read_text(encoding="latin-1"))
    except ValueError as exc:
        raise ValueError(f"{display_path(path)}: {exc}") from exc
    blocks = []
    labels = list(SECTION_RE.finditer(text))
    periods = [match for match in labels
               if match.group(1).strip().lower() in PERIOD_NAMES]
    label_index = 0
    period_index = 0
    current_label = "<no label>"
    current_period = "<no period>"
    index = 0
    while index < len(text):
        while label_index < len(labels) and labels[label_index].start() < index:
            current_label = labels[label_index].group(1)
            label_index += 1
        opened = text.find("{", index)
        closed = text.find("}", index)
        if closed >= 0 and (opened < 0 or closed < opened):
            line = text.count("\n", 0, closed) + 1
            raise ValueError(f"{display_path(path)}: unmatched raw-block close at line {line}")
        if opened < 0:
            break
        while label_index < len(labels) and labels[label_index].start() < opened:
            current_label = labels[label_index].group(1)
            label_index += 1
        while (period_index < len(periods) and
               periods[period_index].start() < opened):
            current_period = periods[period_index].group(1).strip().lower()
            period_index += 1
        closed = text.find("}", opened + 1)
        if closed < 0:
            line = text.count("\n", 0, opened) + 1
            raise ValueError(f"{display_path(path)}: raw block at line {line} is not closed")
        line_end = text.find("\n", closed)
        if line_end < 0:
            line_end = len(text)
        if (current_period != "programme" and
                re.match(r"[ \t]*;", text[closed + 1:line_end])):
            index = closed + 1
            continue
        if "{" in text[opened + 1:closed]:
            line = text.count("\n", 0, opened) + 1
            raise ValueError(f"{display_path(path)}: nested raw block at line {line}")
        start_line = text.count("\n", 0, opened) + 1
        end_line = text.count("\n", 0, closed) + 1
        body = " ".join(without_comments(text[opened + 1:closed]).split())
        blocks.append(RawBlock(path.resolve(), start_line, end_line,
                               current_label, body))
        index = closed + 1
    return blocks


def float_operators(path):
    """Return executable ordinary-Lino float-operator lines in one source."""
    try:
        text = without_comments(path.read_text(encoding="latin-1"))
    except ValueError as exc:
        raise ValueError(f"{display_path(path)}: {exc}") from exc
    periods = [match for match in SECTION_RE.finditer(text)
               if match.group(1).strip().lower() in PERIOD_NAMES]
    hits = []
    for index, period in enumerate(periods):
        if period.group(1).strip().lower() != "programme":
            continue
        end = periods[index + 1].start() if index + 1 < len(periods) else len(text)
        body = text[period.end():end]
        first_line = text.count("\n", 0, period.end())
        for offset, line in enumerate(body.splitlines(), 1):
            if FLOAT_OPERATOR_RE.search(line):
                hits.append((first_line + offset, line.strip()))
    return hits


def float_inventory(closure):
    inventory = {}
    for path in sorted(closure):
        hits = float_operators(path)
        if hits:
            key = path.resolve().relative_to(ROOT).as_posix()
            inventory[key] = tuple(line for _number, line in hits)
    return inventory


def float_errors(closure):
    actual = float_inventory(closure)
    errors = []
    paths = set(FLOAT_SIGNATURES) | set(FLOAT_SIGNATURE_HASHES) | set(actual)
    for path in sorted(paths):
        actual_lines = actual.get(path, ())
        if path in FLOAT_SIGNATURE_HASHES:
            expected_count, expected_digest = FLOAT_SIGNATURE_HASHES[path]
            actual_digest = hashlib.sha256(
                ("\n".join(actual_lines) + "\n").encode("utf-8")
            ).hexdigest()
            if (len(actual_lines), actual_digest) != (
                    expected_count, expected_digest):
                errors.append(
                    f"ordinary Lino float-operator inventory changed: {path}")
                errors.append(
                    f"expected {expected_count} lines, sha256 {expected_digest}")
                errors.append(
                    f"actual   {len(actual_lines)} lines, sha256 {actual_digest}")
            continue
        expected_lines = FLOAT_SIGNATURES.get(path, ())
        if actual_lines != expected_lines:
            errors.append(f"ordinary Lino float-operator inventory changed: {path}")
            errors.append(f"expected {expected_lines!r}")
            errors.append(f"actual   {actual_lines!r}")
    return errors


def tracked_sources():
    process = subprocess.run(
        ["git", "ls-files", "-z", "--", "work", "main", "src"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode:
        detail = process.stderr.decode("utf-8", "replace").strip()
        raise ValueError(f"cannot enumerate tracked Lino sources: {detail}")
    for raw in process.stdout.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        if relative.suffix.lower() == ".txt":
            path = (ROOT / relative).resolve()
            if path.is_file():
                yield path


def build_index():
    index = defaultdict(list)
    for path in tracked_sources():
        index[path.stem.lower()].append(path)
    return index


def source_path(base, name):
    candidate = base / name
    if candidate.suffix.lower() != ".txt":
        candidate = Path(str(candidate) + ".txt")
    return candidate


def resolve_library(owner, name, index):
    normalized = name.replace("\\", "/").strip()
    lowered = normalized.lower().lstrip("/")
    tracked = {path for paths in index.values() for path in paths}
    owner_resolved = owner.resolve()
    try:
        owner_resolved.relative_to(ROOT)
        owner_is_external = False
    except ValueError:
        owner_is_external = True
    if lowered.startswith("work/") or lowered.startswith("main/"):
        direct = [source_path(ROOT, normalized.lstrip("/"))]
    elif normalized.startswith("/"):
        direct = [source_path(ROOT / "main" / "lib", normalized.lstrip("/"))]
    else:
        direct = [
            source_path(owner.parent, normalized),
            source_path(ROOT / "work", normalized),
            source_path(ROOT / "main", normalized),
        ]
    for candidate in direct:
        if candidate.is_file():
            resolved = candidate.resolve()
            if resolved in tracked or (
                    owner_is_external and resolved.parent == owner_resolved.parent):
                return resolved
            raise ValueError(
                f"{display_path(owner)}: library {name!r} resolves to untracked "
                f"source {display_path(resolved)}"
            )
    stem = Path(normalized).name.lower()
    if stem.endswith(".txt"):
        stem = stem[:-4]
    matches = index.get(stem, [])
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"{display_path(owner)}: unresolved library {name!r}")
    choices = ", ".join(display_path(path) for path in matches)
    raise ValueError(
        f"{display_path(owner)}: ambiguous library {name!r}: {choices}"
    )


def display_path(path):
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def scan(roots):
    index = build_index()
    queue = deque(path.resolve() for path in roots)
    seen = set()
    edges = 0
    all_blocks = []
    while queue:
        path = queue.popleft()
        if path in seen:
            continue
        if not path.is_file():
            raise ValueError(f"missing production root/library: {display_path(path)}")
        seen.add(path)
        all_blocks.extend(raw_blocks(path))
        for name in libraries(path):
            dependency = resolve_library(path, name, index)
            edges += 1
            if dependency not in seen:
                queue.append(dependency)
    return seen, edges, all_blocks


def block_errors(blocks):
    return [
        f"forbidden raw target block: {display_path(block.path)}:"
        f"{block.start}-{block.end} ({block.label})"
        for block in blocks
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="*", type=Path)
    args = parser.parse_args()
    roots = [path if path.is_absolute() else ROOT / path
             for path in (args.roots or DEFAULT_ROOTS)]
    try:
        closure, edges, blocks = scan(roots)
        inventory = float_inventory(closure)
        errors = block_errors(blocks) + float_errors(closure)
    except ValueError as exc:
        print(f"FAIL native closure: {exc}")
        return 1

    print(
        f"production Lino closure: {len(closure)} files, {edges} imports, "
        f"{len(blocks)} raw blocks"
    )
    print(
        f"  reviewed ordinary Lino float operators: "
        f"{sum(len(lines) for lines in inventory.values())} in "
        f"{len(inventory)} files"
    )
    if errors:
        for error in errors:
            print("  FAIL", error)
        return 1
    print("  PASS zero target blocks and exact reviewed float-operator inventory")
    return 0


if __name__ == "__main__":
    sys.exit(main())
