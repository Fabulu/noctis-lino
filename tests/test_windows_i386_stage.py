"""Check reproducible win32/i386m source selection and provenance hooks."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re
import struct
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import stage_windows_i386_source as staging  # noqa: E402


TERRAIN_NATIVE_CONTRACT = {
    "VHGND surface smooth64 native": (
        1, 1, "854a9c88b3691d5b8d05b52779b3d1dd460e264fd084fb6275fbf75b7e6782a3"),
    "VHGND dense sample native": (
        1, 1, "b60c5f18990e8a7d0fcc8a5acca6de1a3bff5d4fc62f98b037edb9b745e44e12"),
    "VHGND tile samples native": (
        0, 1, "47c91b73dd6db2af1b8dc142d92ce48ae94e7860292e09c3e46639980af03104"),
    "VHGND tile shade live": (
        0, 1, "65ee57e49b7e53937f2cb36447dc2c89bbd7cf2c4f87442b949966f19d89d0c4"),
    "VHGND tile admission live": (
        0, 1, "6de3aec703107d8b1698a5d0376e7082bbba6eef7c3afe4a11682e956274fd31"),
    "VHGND tile first flat alignment": (
        0, 1, "acedfbf19c2340ed4ab44a283dc83d9d3831fa9ae1f4d6491b0082c1ec55e666"),
    "VHGND tile second flat alignment": (
        0, 1, "acedfbf19c2340ed4ab44a283dc83d9d3831fa9ae1f4d6491b0082c1ec55e666"),
    "VHGND faithful tile admission native": (
        1, 1, "1615a01772a0a1816e3562b9b15db82eb1ba9b013d3832de0704d70a2eeeaa9b"),
    "VHGND greenmush float point native": (
        1, 1, "9e778823873f2df6572a4741a69259b708583ec661313cf274acae7d4f8f2b0c"),
    "VHGND greenmush float setup native": (
        1, 1, "f1f6073e318b921a2b5f46ca06d5a11937d167f7b837201bf71c34f077181bf1"),
    "VHGND greenmush inner": (
        0, 1, "5cf4a7498af217e76473d5a9ed8ff22417cc1de56219fd2b00c8d8fac186b326"),
    "VHGND terrain triangle load native": (
        2, 1, "5d1f89328ba375dbf57cbf0e790afbec083dcdf3ae260d9f3ed9823e00e87f8f"),
    "VHGND tile depth": (
        1, 1, "461de6bb0c4102d354386a47a6d2174d3ff2e993ebc3a08440453c8356f16fef"),
    "VHGND tile shade": (
        1, 1, "547e9a5715e477fc3aa915f1b8200fb76ba896000442ee5089e3689641c66d93"),
    "VHGND tree direction": (
        2, 1, "32a4371138d591c601fc1b21b0d53f09e590ab619b05c8e878dbf849ca8fd5ca"),
    "VHGND tree leaf tip vertex": (
        1, 1, "e11034b728b0c155e234183b4e08c0bc9805f4810bf218e4f6354651f372af0c"),
    "VHGND tree node load native": (
        2, 1, "8bc72ba017cb6c89e252ea75ed3af58ada804e4507b9586ca120838eb04cea69"),
    "VHGND tree terminal native": (
        1, 1, "b03a692cdec1f00c2b0a9a13a48d975cce7e17dd31467389c05a5e5924ebdb33"),
    "VHGND vload": (
        72, 1, "b33962c511fbe3133f27b977b9b8c9f1c429d188970f86aa5a5355c0140126eb"),
    "VHGND render random": (
        50, 1, "f215e17679ecf8e5432fd2842496a83a05abf149a47c147139830d423051abe5"),
    "VHGND terrain cached bounds": (
        1, 1, "fe110f8a58818e3caa95c2a6325aabd7b20ddca7bf3f8d0ef8131e948f7ecf0b"),
    "VHGND terrain facing": (
        2, 1, "2bd5ea81ce7e6e2d1e87130e50078d0acdec5dc18d23b920679531d71a5c01f7"),
    "VHGND height finish": (
        0, 1, "bcf4b7ab18b6e1e5b6eac995a7b9289648a269259c9654603967215f364c6a4a"),
    "VHGND height upper": (
        0, 1, "76317c0d662617d7b4eb3a07f3ed397a72e55bed582e574eb2eaccaed121416f"),
    "VHGND height z ready": (
        0, 1, "11c1d196fc7322ea2cb72412ae0bf4edc0210f356332f7b005487e4e0a5dffce"),
    "VHGND rotation seed calculate": (
        0, 1, "3a05a4b7046160c2ef64bbc30579425221b47ffa936f4bd74fd044dd30dbc95b"),
    "VHGND tree forced broadleaf": (
        0, 1, "afdd3bfe9bc5c9cdeb7658c74c6c95797b1c0be9b24d81d3813586a392bb73cd"),
    "VHGND tree forced conifer": (
        0, 1, "4d60835f5c462ac81a2ebe196f5b5d67335fa2320718bce3f24e6f104fbdda7b"),
    "VHGND tree giant": (
        0, 3, "729ca67dc0e2f1e418d00b151e604e5c2e5e7a042c103be55146fac857336a12"),
    "VHGND tree child height ready": (
        0, 1, "55afb3bb05ae0bc1dbe7d5dfe82c3efa8cb0eacffe8c5f13ef4117d155244a04"),
    "VHGND tree child nonroot height": (
        0, 1, "01c6ef7a718a6bd6e67789a8ea4763e65ec82db92300cef1b39c8db49eeb7aa2"),
    "VHGND tree endpoint pi": (
        0, 1, "8fc7821bed6c9eb0a8cd7fa2a1493e402f4ee746624424a0cfa37dd6245de2eb"),
    "VHGND tree endpoint ready": (
        0, 1, "c6e42801382fe7835a7bdb0f5fd7ad57d3283f9e132cbb1673f56f5e3c3bec98"),
    "VHGND tree node branch": (
        0, 1, "8cc88e3112dd652f62d64e1c7001a0ffa4171e3063102daeba1635cc3b5462cd"),
    "VHGND tree node count ready": (
        0, 2, "1c523c434e3a7d96881e5f02407cc360860d4392c0548f826f0f2f251544e8ec"),
    "VHGND tree node nonroot range": (
        0, 1, "17a43ff635ea149279b8fb0bbc7a274e790dbf65d0c09eb9e57f3cf195a22826"),
    "VHGND tree polar float vertex": (
        0, 1, "1a02f472cdb9a48c09fa7ed6559b80d7590c116e97fa9e68c321849cb413efc4"),
}
TERRAIN_NATIVE_VARIABLES = {
    "VHGNDdensebase", "VHGNDmanhattan", "VHGNDnativecomplete",
}
TERRAIN_CURRENT_SOURCE_ANCHORS = (
    "-> VHGND convert seconds;",
    "? [nivgenf64] != 0 -> VHGND rotation seed calculate f64;",
    '"VHGND rotation seed calculate f64"',
    '"VHGND animal inclination"',
)
SMOOTH64_NATIVE_CONTRACT = (
    1,
    2,
    1,
    "40e95b20871393aee2d1985fe76740dbb1bfaef10b954d793fec874aa53f657e",
    "1ced5a72ebc03467a2cb43a64ff01c9439ba80ff5cbc42c805ebc87e5073e290",
)
SMOOTH64_NATIVE_VARIABLES = {"VHGsmoothbase", "VHGsmoothcount"}
TERRAIN_FACING_DOT_BODY_HASH = (
    "5a6d466d5de8bc81beb5c960d4918ba5d1f58fcaf6f408b0f9078383ec4033d8"
)
PGTEX_TERRAIN_NATIVE_CONTRACT = {
    "PG terrain pixel native": (
        171,
        "f990b24204f72b5fe4acbc0643ebbbdbf577b93dd8cd837227a6d9af66a90e3a",
        10,
    ),
    "PG terrain cull pixel native": (
        191,
        "407e8d9c74b1cbccad6ae65392ab186a45d4c353ec5b618d81c40c31563788fc",
        25,
    ),
}
PGTEX_TERRAIN_UNPACK_NATIVE_CONTRACT = (
    213,
    "733ff6cca1e51f39a5255e513b2d6ef99e23b05b93bff269a5ccbec483db451b",
)
PGTEX_UV_TERRAIN_NATIVE_CONTRACT = (
    273,
    "c4b3d1b3fc79fc914859898716e239f4ff755040d7132e6a427936c99305cdbe",
    4,
)
PGTEX_HALFSCAN_NATIVE_CONTRACT = (
    112,
    "1efb33844df313c58be7c340a28e69340187aa25c7007f9523d53f5ab602430e",
    19,
)
PGTEX_EDGES_NATIVE_CONTRACT = (
    706,
    "d074905d7696f33b1d22c91ee5b348e3b0b2ab388b42ac4a17144fd3f29a188c",
    24,
)
SMOOTH64_CURRENT_SOURCE_ANCHORS = (
    '"VHG fpu clean"\n\t=> FReset;',
    "\t=> FEnter;",
    "VHGfast = 1; VHGfastheld = 0; VHGsimacc = 0; VHGdosim = 1;",
    '"VHG profile option"',
    "\t=> VHG write profile;",
    "A = [VHGz]; A + 200; [VHVcamzi] = A;",
)
SMOOTH64_CALL_PATTERN = re.compile(
    r"A = nw;\s*A \+ RADPT;\s*A \+ 2556;\s*\[VHGsmoothbase\] = A;\s*"
    r"A = \[VHGhudcount\];\s*A '\* 320;\s*A \+ 320;\s*"
    r"\[VHGsmoothcount\] = A;\s*=> VHG interior smooth64;\s*"
    r"=> VHG interior smooth64;"
)


def terrain_variables(source: str) -> set[str]:
    variables = source.split('"variables"', 1)[1].split('"workspace"', 1)[0]
    return set(re.findall(r"\b(VHGND[A-Za-z0-9]+)\s*=", variables))


def game_variables(source: str) -> list[str]:
    variables = source.split('"variables"', 1)[1].split('"workspace"', 1)[0]
    return re.findall(r"\b(VHG[A-Za-z0-9]+)\s*=", variables)


def labelled_service(source: str, label: str) -> str:
    definition = re.search(
        r'^\s*"' + re.escape(label) + r'"\s*$', source, flags=re.MULTILINE)
    if definition is None:
        return ""
    terminator = re.search(
        r"^\s*end;\s*$", source[definition.end():], flags=re.MULTILINE)
    if terminator is None:
        return ""
    return source[definition.start():definition.end() + terminator.end()]


def labelled_section(source: str, label: str) -> str:
    definition = re.search(
        r'^\s*"' + re.escape(label) + r'"\s*$', source, flags=re.MULTILINE)
    if definition is None:
        return ""
    next_definition = re.search(
        r'^\s*"[^"]+"\s*$', source[definition.end():], flags=re.MULTILINE)
    end = (len(source) if next_definition is None else
           definition.end() + next_definition.start())
    return source[definition.start():end]


def normalized_hash(value: str) -> str:
    return hashlib.sha256(" ".join(value.split()).encode("ascii")).hexdigest()


def triangle_loader_branches_land_on_instruction_boundaries(source: str) -> bool:
    """Check the two relative branches in the native triangle loader."""
    service = labelled_service(source, "VHGND terrain triangle load native")
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    if len(bodies) != 1:
        return False

    instructions: list[tuple[str, int, bytes]] = []
    offset = 0
    for raw_line in bodies[0].splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = re.findall(r"<[^>]+>|[0-9A-Fa-f]{2}", line)
        if not tokens:
            return False
        encoded = b"".join(
            b"\0" * 4 if token.startswith("<") else bytes.fromhex(token)
            for token in tokens
        )
        instructions.append((line, offset, encoded))
        offset += len(encoded)

    by_line = {line: (position, encoded)
               for line, position, encoded in instructions}
    near_branches = [(position, encoded) for _, position, encoded in instructions
                     if len(encoded) == 6 and encoded[:2] == b"\x0f\x85"]
    short_branches = [(position, encoded) for _, position, encoded in instructions
                      if len(encoded) == 2 and encoded[0] == 0xEB]
    second_arm = "DD 86 E8 07 00 00"
    final_tail = "89 87 <dVHGNDvv mtp bytesperunit>"
    if (len(near_branches) != 1 or len(short_branches) != 1 or
            second_arm not in by_line or final_tail not in by_line):
        return False

    near_position, near = near_branches[0]
    short_position, short = short_branches[0]
    near_target = near_position + len(near) + int.from_bytes(
        near[2:], "little", signed=True)
    short_target = short_position + len(short) + int.from_bytes(
        short[1:], "little", signed=True)
    return (near_target == by_line[second_arm][0] and
            short_target == by_line[final_tail][0])


def smooth64_native_contract(source: str) -> tuple[int, int, int, str, str]:
    label = "VHG interior smooth64"
    definitions = len(re.findall(
        r'^\s*"' + re.escape(label) + r'"\s*$', source, flags=re.MULTILINE))
    calls = len(re.findall(r"=>\s*" + re.escape(label) + r"\s*;", source))
    service = labelled_service(source, label)
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    call_matches = list(SMOOTH64_CALL_PATTERN.finditer(source))
    call_hash = normalized_hash(call_matches[0].group(0)) if len(call_matches) == 1 else ""
    body_hash = normalized_hash(bodies[0]) if len(bodies) == 1 else ""
    return definitions, calls, len(bodies), call_hash, body_hash


def terrain_native_contract(source: str) -> dict[str, tuple[int, int, int, str]]:
    matches = list(re.finditer(r'^\s*"([^"]+)"\s*$', source, flags=re.MULTILINE))
    sections: dict[str, list[str]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        sections.setdefault(match.group(1), []).append(source[match.end():end])

    actual: dict[str, tuple[int, int, int, str]] = {}
    for label in TERRAIN_NATIVE_CONTRACT:
        label_sections = sections.get(label, [])
        bodies = [
            body
            for section in label_sections
            for body in re.findall(r"\{([^}]*)\}", section, flags=re.DOTALL)
        ]
        normalized = "\n".join(" ".join(body.split()) for body in bodies)
        calls = len(re.findall(r"=>\s*" + re.escape(label) + r"\s*;", source))
        actual[label] = (
            len(label_sections), calls, len(bodies),
            hashlib.sha256(normalized.encode("ascii")).hexdigest(),
        )
    return actual


def native_block_labels(source: str) -> list[str]:
    labels: list[str] = []
    definitions = list(re.finditer(r'^\s*"([^"]+)"\s*$', source, flags=re.MULTILINE))
    for block in re.finditer(r"\{([^}]*)\}", source, flags=re.DOTALL):
        normalized = " ".join(block.group(1).split())
        if re.match(r"^[0-9A-F]{2}(?:\s|$)", normalized):
            owner = next(
                definition.group(1)
                for definition in reversed(definitions)
                if definition.start() < block.start()
            )
            labels.append(owner)
    return labels


def expected_terrain_native_contract() -> dict[str, tuple[int, int, int, str]]:
    return {
        label: (1, calls, bodies, body_hash)
        for label, (calls, bodies, body_hash) in TERRAIN_NATIVE_CONTRACT.items()
    }


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_required_keys(workflow: str) -> tuple[str, ...]:
    match = re.search(
        r"\$requiredKeys = @\((.*?)^\s*\)", workflow,
        flags=re.DOTALL | re.MULTILINE,
    )
    if match is None:
        return ()
    return tuple(re.findall(r"'([a-z0-9_]+)'", match.group(1)))


def package_provenance_append(workflow: str) -> str:
    match = re.search(
        r"Copy-Item -LiteralPath \$buildProvenance -Destination "
        r"dist\\Noctis-IV-windows-x86\.provenance\.txt(.*?)"
        r"^\s*- name: Upload",
        workflow,
        flags=re.DOTALL | re.MULTILINE,
    )
    return "" if match is None else match.group(1)


def native_tile_admission_needs_no_completion_protocol(source: str) -> bool:
    """Check the native gate's return is consumed without dead flags or reloads."""
    normalized = " ".join(source.split())
    direct_flow = (
        "} ? A > 90 -> VHGND tile done; "
        "-> VHGND tile depth computed;"
    )
    return (
        source.count("VHGNDnativecomplete = 0;") == 1
        and "[VHGNDnativecomplete]" not in source
        and source.count("VHGNDmanhattan = 0;") == 1
        and "[VHGNDmanhattan]" not in source
        and "dVHGNDmanhattan" not in source
        and normalized.count(direct_flow) == 1
        and source.count("=> VHGND faithful tile admission native;") == 1
    )


def native_tile_admission_returns_branch_value(source: str) -> bool:
    """Check rejected Manhattan and accepted depth values share one live branch."""
    definition = re.search(
        r'^\s*"VHGND tile admission live"\s*$', source, flags=re.MULTILINE)
    if definition is None:
        return False
    next_definition = re.search(
        r'^\s*"[^"]+"\s*$', source[definition.end():], flags=re.MULTILINE)
    section_end = (len(source) if next_definition is None else
                   definition.end() + next_definition.start())
    section = source[definition.start():section_end]
    bodies = re.findall(r"\{([^}]*)\}", section, flags=re.DOTALL)
    native_service = labelled_service(
        source, "VHGND faithful tile admission native")
    native_bodies = re.findall(r"\{([^}]*)\}", native_service, flags=re.DOTALL)
    native_code = " ".join(re.sub(
        r"\([^)]*\)", "", native_bodies[0] if native_bodies else "").split())
    result_skip = "01 D8 EB 04 90 90 90 90 83 F8 5A"
    encoded_tokens = re.findall(
        r"[0-9A-Fa-f]{2}",
        re.sub(r"\([^)]*\)", "", bodies[0]) if bodies else "",
    )
    encoded = bytes.fromhex(" ".join(encoded_tokens))
    normalized = " ".join(source.split())
    if (
        len(bodies) != 1
        or len(native_bodies) != 1
        or native_code.count(result_skip) != 1
        or "dVHGNDmanhattan" in native_code
        or encoded != b"\xeb\x04" + b"\x90" * 4
        or 2 + int.from_bytes(encoded[1:2], "little", signed=True)
            != len(encoded)
        or normalized.count(
            "=> VHGND faithful tile admission native; "
            '"VHGND tile admission live"'
        ) != 1
        or "[VHGNDmanhattan]" in source
    ):
        return False

    tile = 1 << 14
    fractions = (0, 1, tile // 2, tile - 2, tile - 1)
    for dx in range(-92, 93):
        for dz in range(-92, 93):
            manhattan = abs(dx) + abs(dz)
            for fx in fractions:
                for fz in fractions:
                    if manhattan > 90:
                        returned = manhattan
                    else:
                        world_x = dx * tile + fx - tile // 2
                        world_z = dz * tile + fz - tile // 2
                        raw_depth = math.isqrt(
                            world_x * world_x + world_z * world_z) >> 14
                        returned = max(raw_depth - 1, 0)
                        if returned > 89:
                            return False
                    if (returned > 90) != (manhattan > 90):
                        return False
    return True


def native_tile_samples_preserve_lino_state(source: str) -> bool:
    """Check packed low-byte loads preserve samples and all live state."""
    service = labelled_section(source, "VHGND tile samples native")
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    normalized = " ".join(source.split())
    body = " ".join(bodies[0].split()) if len(bodies) == 1 else ""
    encoded_tokens = re.findall(
        r"<[^>]+>|[0-9A-Fa-f]{2}",
        re.sub(r"\([^)]*\)", "", bodies[0]) if bodies else "",
    )
    encoded = b"".join(
        b"\0" * 4 if token.startswith("<") else bytes.fromhex(token)
        for token in encoded_tokens
    )
    jump = encoded.find(b"\xeb")
    flags_are_dead = (
        "} A = [GRiptype]; ? A != 3 -> VHGND tile ground present; "
        "A = [VHGNDsctype]; ? A != 1 -> VHGND tile ground present; "
        "A = [VHGNDs1]; A + [VHGNDs2]; A + [VHGNDs3]; "
        "A + [VHGNDs4]; ? A = 0 -> VHGND tile done;"
    )
    if (
        len(bodies) != 1
        or body.split()[:4] != ["0F", "B6", "04", "B7"]
        or body.count("0F B6 04 87") != 3
        or body.count("89 F0") != 2
        or body.count("01 F0") != 1
        or "0F B6 04 9F" in body
        or "89 D8" in body
        or "01 D8" in body
        or "25 FF 00 00 00" in body
        or "85 C0" in body
        or "84 C0" in body
        or body.count("EB 2B") != 1
        or body.split().count("90") != 43
        or jump < 0
        or encoded.count(b"\xeb") != 1
        or jump + 2 + struct.unpack("b", encoded[jump + 1:jump + 2])[0]
            != len(encoded)
        or (
            "E = nw; E + RPSM; E + [VHGNDh1]; "
            '"VHGND tile samples native"'
        ) not in normalized
        or flags_are_dead not in normalized
    ):
        return False

    base = 1000
    low_byte_vectors = [
        *((0, 0, 0, s4) for s4 in range(256)),
        (1, 127, 128, 255),
        (255, 128, 127, 1),
    ]
    for step in (1, 8, 16):
        indices = (base, base + step, base + 201 * step,
                   base + 200 * step)
        for low_bytes in low_byte_vectors:
            words = {
                index: ((0xA50000 + position * 0x1100) << 8) | low
                for position, (index, low) in enumerate(zip(indices, low_bytes))
            }
            packed = bytearray((max(indices) + 1) * 4)
            for index, word in words.items():
                struct.pack_into("<I", packed, index * 4, word & 0xFFFFFFFF)
            source_samples = tuple(words[index] & 255 for index in indices)
            native_samples = tuple(packed[index * 4] for index in indices)
            source_state = (
                source_samples[3], step * 200, base,
                sum(source_samples) == 0,
            )
            native_state = (
                native_samples[3], step * 200, base,
                sum(native_samples) == 0,
            )
            if source_samples != native_samples or source_state != native_state:
                return False
    return True


def native_tile_shade_preserves_live_ecx(source: str) -> bool:
    """Check the base shade remains live across depth scaling and padding."""
    service = labelled_service(source, "VHGND tile shade")
    live_service = labelled_service(source, "VHGND tile shade live")
    bodies = re.findall(r"\{([^}]*)\}", live_service, flags=re.DOTALL)
    encoded_tokens = re.findall(
        r"[0-9A-Fa-f]{2}",
        re.sub(r"\([^)]*\)", "", bodies[0]) if bodies else "",
    )
    encoded = bytes.fromhex(" ".join(encoded_tokens))
    normalized = " ".join(service.split())
    live_label = '"VHGND tile shade live"'
    if (
        len(bodies) != 1
        or encoded != b"\xeb\x12" + b"\x90" * 18
        or 2 + int.from_bytes(encoded[1:2], "little", signed=True)
            != len(encoded)
        or normalized.count(live_label) != 1
        or not normalized.split(live_label, 1)[0].rstrip().endswith(
            "C + 8; A = [VHGNDdepth]; A > 1;")
        or not re.search(
            r'"VHGND tile shade live" .*? C \+ A; '
            r"\? C '<= 32 -> VHGND tile shade ready; C = 32;",
            normalized,
        )
        or service.count("[VHGNDshade] = C;") != 1
        or "C = [VHGNDshade]" in service
    ):
        return False

    for initial_seed in (
        3, 7, 0x103, 0x7FFFFFFF, 0x80000003, 0xFFFFFFFB, 0xFFFFFFFF,
    ):
        product = initial_seed * initial_seed
        eax = product & 0xFFFFFFFF
        edx = (product >> 32) & 0xFFFFFFFF
        folded = (eax & 0xFFFFFF00) | (((eax & 0xFF) + (edx & 0xFF)) & 0xFF)
        source_sufseed = initial_seed
        source_sufeax = folded
        source_sufseed = (source_sufseed + source_sufeax) & 0xFFFFFFFF
        source_draw = source_sufeax & 7
        source_parity_even = (source_draw.bit_count() & 1) == 0

        native_ebx = initial_seed
        native_sufeax = folded
        native_ebx = (native_ebx + native_sufeax) & 0xFFFFFFFF
        native_sufseed = native_ebx
        native_draw = native_sufeax & 7
        native_parity_even = (native_draw.bit_count() & 1) == 0
        source_state = (
            source_draw, source_draw, edx, source_sufseed,
            source_sufeax, source_sufseed, source_draw,
            source_draw == 0, source_parity_even,
        )
        native_state = (
            native_draw, native_draw, edx, native_ebx,
            native_sufeax, native_sufseed, native_draw,
            native_draw == 0, native_parity_even,
        )
        if native_state != source_state:
            return False

    for draw in range(8):
        boundary = 2 * (24 - draw)
        for depth in range(max(0, boundary - 3), boundary + 4):
            base = draw + 8
            scaled_depth = (depth & 0xFFFFFFFF) >> 1
            spilled_base = base
            source_sum = (spilled_base + scaled_depth) & 0xFFFFFFFF
            live_sum = (base + scaled_depth) & 0xFFFFFFFF
            source_state = (source_sum <= 32, min(source_sum, 32))
            live_state = (live_sum <= 32, min(live_sum, 32))
            if live_state != source_state:
                return False
    return True


def terrain_texture_gates_prefer_unit_path(source: str) -> bool:
    """Check both unit-LOD triangles branch directly to textured rendering."""
    normalized = " ".join(source.split())
    for triangle in ("first", "second"):
        alignment = f"VHGND tile {triangle} flat alignment"
        textured = f"VHGND tile {triangle} textured"
        flat = f"VHGND tile {triangle} flat"
        bodies = re.findall(
            r"\{([^}]*)\}", labelled_section(source, alignment),
            flags=re.DOTALL)
        encoded_tokens = re.findall(
            r"[0-9A-Fa-f]{2}",
            re.sub(r"\([^)]*\)", "", bodies[0]) if bodies else "",
        )
        encoded = bytes.fromhex(" ".join(encoded_tokens))
        direct_gate = (
            f"A = [VHGNDlodstep]; ? A = 1 -> {textured}; "
            f'"{alignment}"'
        )
        old_gate = (
            f"A = [VHGNDlodstep]; ? A != 1 -> {flat}; "
            f"-> {textured};"
        )
        positions = tuple(normalized.find(f'"{label}"') for label in (
            alignment, flat, textured))
        if (
            len(bodies) != 1
            or encoded != b"\xeb\x03" + b"\x90" * 3
            or 2 + int.from_bytes(encoded[1:2], "little", signed=True)
                != len(encoded)
            or normalized.count(direct_gate) != 1
            or old_gate in normalized
            or min(positions) < 0
            or positions != tuple(sorted(positions))
        ):
            return False

        for lod_step in (1, 8, 16):
            source_renderer = "textured" if lod_step == 1 else "flat"
            native_renderer = "textured" if lod_step == 1 else "flat"
            source_branches = 1 if lod_step == 1 else 2
            native_branches = 1 if lod_step == 1 else 2
            if ((native_renderer, native_branches) !=
                    (source_renderer, source_branches)):
                return False
    return True


def terrain_facing_gates_prefer_visible_path(source: str) -> bool:
    """Check ordinary terrain facing branches directly to visible triangles."""
    normalized = " ".join(source.split())
    for triangle in ("first", "second"):
        visible = f"VHGND tile {triangle} visible"
        done = f"VHGND tile {triangle} done"
        mirror = f"VHGND tile {triangle} mirror facing"
        direct_gate = (
            f"A = [FCret]; ? A != 0 -> {visible}; -> {done};")
        old_gate = (
            f"A = [FCret]; ? A = 0 -> {done}; -> {visible};")
        mirror_gate = f"A = [FCret]; ? A != 0 -> {done};"
        if (
            normalized.count(direct_gate) != 1
            or old_gate in normalized
            or normalized.count(f'"{visible}"') != 1
            or normalized.count(f'"{done}"') != 1
            or normalized.count(f'"{mirror}"') != 1
            or normalized.count(mirror_gate) != 1
        ):
            return False

        for fc_ret in (0, 1, -1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
            source_target = done if fc_ret == 0 else visible
            direct_target = visible if fc_ret != 0 else done
            if direct_target != source_target:
                return False
    return True


def terrain_uv_native_separates_exact_spills(source: str) -> bool:
    """Check independent UV sums separate exact qword spills and reloads."""
    expected_length, expected_hash, tail_nops = PGTEX_UV_TERRAIN_NATIVE_CONTRACT
    service = labelled_service(source, "PG uv terrain float")
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    if len(bodies) != 1 or source.count("-> PG uv terrain float;") != 1:
        return False

    body = bodies[0]
    tokens = re.findall(
        r"<[^>]+>|[0-9A-Fa-f]{2}",
        re.sub(r"\([^)]*\)", "", body),
    )
    encoded = b"".join(
        b"\0" * 4 if token.startswith("<") else bytes.fromhex(token)
        for token in tokens
    )
    wide_sums = (
        b"\xdd\x86\x78\0\0\0\xdc\x86\x58\0\0\0"
        b"\xdd\x9e\xc0\x07\0\0"
        b"\xdd\x86\x68\0\0\0\xdc\x86\x48\0\0\0"
        b"\xdd\x9e\xc8\x07\0\0"
        b"\xdd\x86\x70\0\0\0\xdc\x86\x50\0\0\0"
        b"\xdd\x9e\xd0\x07\0\0"
    )
    narrow_reloads = (
        b"\xdd\x86\xc0\x07\0\0\xd9\x9f\0\0\0\0"
        b"\xdd\x86\xc8\x07\0\0\xd9\x9f\0\0\0\0"
        b"\xdd\x86\xd0\x07\0\0\xd9\x9f\0\0\0\0"
        b"\xd9\x87\0\0\0\0\xdd\x9e\x78\0\0\0"
        b"\xd9\x87\0\0\0\0\xdd\x9e\x68\0\0\0"
        b"\xd9\x87\0\0\0\0\xdd\x9e\x70\0\0\0"
    )
    stacked_products = bytes.fromhex(
        "8d6424f0 dd8690000000 dcb6c0070000 dd9ed8070000 "
        "dd86c8070000 dc8e80000000 dd1c24 dd86d0070000 "
        "dc8e88000000 dd5c2408 dd86d8070000 d99f00000000 "
        "d98700000000 dd9e60000000 dd0424 dc8e60000000 dd1c24 "
        "dd442408 dc8e60000000 dd96d8070000 dd5c2408 dd0424 "
        "db9f00000000 dd442408 db9f00000000 8d642410 eb04 90909090"
    )
    return (
        len(encoded) == expected_length
        and normalized_hash(body) == expected_hash
        and encoded[9:63] == wide_sums
        and encoded[63:135] == narrow_reloads
        and encoded[135:] == stacked_products
        and encoded[-tail_nops - 2:-tail_nops] == bytes((0xEB, tail_nops))
        and encoded[-tail_nops:] == b"\x90" * tail_nops
        and encoded.count(b"\x8d\x64\x24\xf0") == 1
        and encoded.count(b"\x8d\x64\x24\x10") == 1
        and encoded.count(b"\xdd\x96\xd8\x07\0\0") == 1
        and encoded.count(b"\xdd\x9e\xc0\x07\0\0") == 1
        and encoded.count(b"\xdd\x9e\xc8\x07\0\0") == 1
        and encoded.count(b"\xdd\x9e\xd0\x07\0\0") == 1
    )


def edges_native_retains_binary64_accumulator(source: str) -> bool:
    """Check the fixed edge walker keeps its accumulator and row state live."""
    expected_length, expected_hash, tail_nops = PGTEX_EDGES_NATIVE_CONTRACT
    service = labelled_service(source, "PG edges native")
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    if len(bodies) != 1 or source.count("=> PG edges native;") != 1:
        return False

    body = bodies[0]
    code = "\n".join(line.split("(", 1)[0] for line in body.splitlines())
    tokens = re.findall(r"<[^>]+>|[0-9A-Fa-f]{2}", code)
    encoded = b"".join(
        b"\0" * 4 if token.startswith("<") else bytes.fromhex(token)
        for token in tokens
    )
    near_branches = (
        (179, 657),
        (499, 657),
        (673, 60),
    )
    if (
        len(encoded) != expected_length
        or normalized_hash(body) != expected_hash
        or encoded[505:523] != (
            b"\x81\xc6\xb0\x00\x00\x00"
            b"\x8b\x87\0\0\0\0\x29\xd0\x40\x51\x89\xc1")
        or encoded[523:531] != b"\xdd\x06\xdb\x97\0\0\0\0"
        or encoded[531:537] != b"\x8b\x87\0\0\0\0"
        or encoded[591:596] != b"\xdc\x46\xf8\xdd\x1e"
        or encoded[596:600] != b"\x42\x49\x75\xb3"
        or encoded[600:657] != (
            b"\xdd\x06\xdd\x9f\0\0\0\0"
            b"\x3d\xf0\xd8\xff\xff\x7d\x05\xb8\xf0\xd8\xff\xff"
            b"\x3d\x10\x27\x00\x00\x7e\x05\xb8\x10\x27\x00\x00"
            b"\x89\x87\0\0\0\0\x89\x97\0\0\0\0"
            b"\x89\x8f\0\0\0\0\x59\x81\xee\xb0\x00\x00\x00")
        or any(
            encoded[position] != 0x0F
            or position + 6 + int.from_bytes(
                encoded[position + 2:position + 6], "little", signed=True)
                != target
            for position, target in near_branches
        )
        or 598 + 2 + int.from_bytes(encoded[599:600], "little", signed=True)
            != 523
        or encoded[-tail_nops - 2:-tail_nops] != bytes((0xEB, tail_nops))
        or encoded[-tail_nops:] != b"\x90" * tail_nops
        or encoded[-tail_nops - 3:-tail_nops - 2] != b"\x5d"
        or b"\xdd\x86\xb0\x00\x00\x00\xdb\x9f\0\0\0\0"
            in encoded[523:638]
        or b"\x8b\x97\0\0\0\0" in encoded[523:638]
        or b"\xff\x8f\0\0\0\0" in encoded[523:638]
        or encoded.count(b"\x81\xc6\xb0\x00\x00\x00") != 1
        or encoded.count(b"\x81\xee\xb0\x00\x00\x00") != 1
    ):
        return False

    # FIST and FISTP round the same ST(0).  The retained form leaves that exact
    # loaded binary64 value for the following add, then the same qword store
    # rounds the next row's accumulator and empties the x87 stack.  EDX and ECX
    # likewise retain the source row and exhausted inclusive count.  The broad
    # clamp is needed only for the final EWax publication: live row bounds are
    # already constrained to [5, 311], so moving it past the loop leaves both
    # bounded arrays exact even for the masked-invalid FIST result.
    for initial, slope, first_row, last_row in (
        (-9999.5, 0.125, 5, 21),
        (-0.5, 1.0 / 3.0, 17, 190),
        (0.5, -1.0 / 7.0, 188, 311),
        (9999.5, -0.25, 0xFFF0, 0x10010),
    ):
        spilled = float(initial)
        retained = float(initial)
        source_row = native_row = first_row
        native_count = last_row - first_row + 1
        spilled_samples: list[tuple[int, int]] = []
        retained_samples: list[tuple[int, int]] = []
        while source_row <= last_row:
            spilled_samples.append((source_row, round(spilled)))
            spilled = float(spilled + slope)
            source_row += 1
        while native_count:
            retained_samples.append((native_row, round(retained)))
            retained = float(retained + slope)
            native_row += 1
            native_count -= 1
        if (
            retained_samples != spilled_samples
            or retained != spilled
            or native_row != source_row
            or native_count != 0
        ):
            return False

    def wide_clamp(value: int) -> int:
        return max(-10000, min(value, 10000))

    for sample in (
        -0x80000000, -10001, -10000, 4, 5, 311, 312, 10000, 10001,
    ):
        for bound in (5, 42, 311):
            old_fpart = max(bound, min(wide_clamp(sample), 311))
            new_fpart = max(bound, min(sample, 311))
            old_ipart = min(bound, max(wide_clamp(sample), 5))
            new_ipart = min(bound, max(sample, 5))
            if old_fpart != new_fpart or old_ipart != new_ipart:
                return False
    return True


def terrain_unpack_native_preserves_block_state(source: str) -> bool:
    """Check native terrain UV unpacking preserves slots, registers, and flags."""
    expected_length, expected_hash = PGTEX_TERRAIN_UNPACK_NATIVE_CONTRACT
    service = labelled_service(source, "PG terrain unpack native")
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    if len(bodies) != 1 or source.count("=> PG terrain unpack native;") != 2:
        return False

    body = bodies[0]
    tokens = re.findall(
        r"<[^>]+>|[0-9A-Fa-f]{2}",
        re.sub(r"\([^)]*\)", "", body),
    )
    encoded = b"".join(
        b"\0" * 4 if token.startswith("<") else bytes.fromhex(token)
        for token in tokens
    )
    core = bytes.fromhex(
        "52 8b8700000000 8b8f00000000 29c8 c1f804 25ffff0000 "
        "898700000000 8b8700000000 8b8f00000000 29c8 c1f804 "
        "25ffff0000 898700000000 89ca 81e2ffff0000 899700000000 "
        "8b8700000000 25ffff0000 898700000000 8b9700000000 "
        "899700000000 8b9700000000 899700000000"
    )
    expected = core + b"\xeb\x62" + b"\x90" * 98 + b"\x5a"
    if (
        len(encoded) != expected_length
        or normalized_hash(body) != expected_hash
        or encoded != expected
        or source.count("A = [SPu]; A & 65535; [SPax] = A;") != 2
        or source.count("A = [SPv]; A & 65535; [SPdx] = A;") != 2
    ):
        return False

    def signed32(value: int) -> int:
        value &= 0xFFFFFFFF
        return value - 0x100000000 if value & 0x80000000 else value

    for old_u, old_v, new_u, new_v, old_d in (
        (0, 0, 0, 0, 0),
        (0xABCD, 0x1234, 0xBCDE, 0x3456, 0x89ABCDEF),
        (0x7FFFFFFF, 0x80000000, 0x80000000, 0x7FFFFFFF, 1),
        (0xFFFFFFFF, 0x00010000, 0, 0xFFFF0000, 0xFFFFFFFF),
    ):
        source_si = (signed32(new_v - old_v) >> 4) & 0xFFFF
        source_bp = (signed32(new_u - old_u) >> 4) & 0xFFFF
        source_state = (
            source_si, source_bp, old_u & 0xFFFF, old_v & 0xFFFF,
            new_u, new_v,
        )
        native_state = (
            (signed32(new_v - old_v) >> 4) & 0xFFFF,
            (signed32(new_u - old_u) >> 4) & 0xFFFF,
            old_u & 0xFFFF, old_v & 0xFFFF, new_u, new_v,
        )
        source_registers = (old_v & 0xFFFF, old_u, old_d)
        native_registers = (old_v & 0xFFFF, old_u, old_d)
        source_flags = (old_v & 0xFFFF) == 0
        native_flags = (old_v & 0xFFFF) == 0
        if ((native_state, native_registers, native_flags) !=
                (source_state, source_registers, source_flags)):
            return False
    return True


def terrain_pixel_loops_preserve_samples(source: str) -> bool:
    """Check the opaque terrain loops retain exact UV and pixel semantics."""
    if (
        source.count("A = [SPu]; A & 65535; [SPax] = A;") != 2
        or source.count("A = [SPv]; A & 65535; [SPdx] = A;") != 2
    ):
        return False
    for label, (expected_length, expected_hash, tail_nops) in (
            PGTEX_TERRAIN_NATIVE_CONTRACT.items()):
        service = labelled_service(source, label)
        bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
        if len(bodies) != 1:
            return False
        body = bodies[0]
        tokens = re.findall(
            r"<[^>]+>|[0-9A-Fa-f]{2}",
            re.sub(r"\([^)]*\)", "", body),
        )
        encoded = b"".join(
            b"\0" * 4 if token.startswith("<") else bytes.fromhex(token)
            for token in tokens
        )
        branches = [
            position for position in range(len(encoded) - 1)
            if encoded[position] == 0x75
        ]
        outer = len(encoded) - tail_nops - 2
        normalized = " ".join(body.split())
        if (
            len(encoded) != expected_length
            or normalized_hash(body) != expected_hash
            or normalized.count("88 FA") != 1
            or normalized.count("66 89 CA") != 1
            or "31 D2" in normalized
            or "88 EE" in normalized
            or normalized.split().count("4F") != 1
            or normalized.count("89 D7") != 1
            or normalized.count("89 F9") != 1
            or normalized.count("8D 64 24 0C") != 1
            or "FF 4C 24 10" in normalized
            or "FF 4C 24 04" in normalized
            or "FF 0C 24" in normalized
            or "C1 C9 10" in normalized
            or "66 49" in normalized
            or "B2 00" in normalized
            or normalized.count("8B 87 <dPGtexoff mtp bytesperunit>") != 1
            or normalized.count("8D 84 86 70 68 06 00") != 1
            or normalized.count("81 C6 A0 8B 10 00") != 1
            or normalized.count("0F B6 14 90") != 1
            or "03 97 <dPGtexoff mtp bytesperunit>" in normalized
            or "0F B6 94 96 70 68 06 00" in normalized
            or normalized.count("FF B7 <dSPtinta mtp bytesperunit>") != 1
            or normalized.count("02 54 24 0C") != 1
            or "02 96 <dSPtinta mtp bytesperunit>" in normalized
            or "03 97 <dSPtinta mtp bytesperunit>" in normalized
            or "0F B6 D2" in normalized
            or "0F B6 AC 96 70 68 06 00" in normalized
            or "8B AC 96 70 68 06 00" in normalized
            or "81 E2 00 FF 00 00" in normalized
            or "81 E5 FF 00 00 00" in normalized
            or "C1 EB 08" in normalized
            or "09 DA" in normalized
            or normalized.count("8B 9F <dSPax mtp bytesperunit>") != 1
            or normalized.count("89 9F <dSPax mtp bytesperunit>") != 1
            or normalized.count("FF B7 <dSPbp mtp bytesperunit>") != 1
            or normalized.count("66 03 5C 24 08") != 1
            or "66 03 9F <dSPbp mtp bytesperunit>" in normalized
            or normalized.count("FF B7 <dSPsi mtp bytesperunit>") != 1
            or normalized.count("66 03 4C 24 04") != 1
            or "66 03 8F <dSPsi mtp bytesperunit>" in normalized
            or "66 03 97 <dSPsi mtp bytesperunit>" in normalized
            or normalized.count("8B 8F <dSPdx mtp bytesperunit>") != 1
            or normalized.count("89 97 <dSPdx mtp bytesperunit>") != 1
            or normalized.count("8B 87 <dSPdi mtp bytesperunit>") != 1
            or normalized.count("89 87 <dSPdi mtp bytesperunit>") != 1
            or normalized.count("8B 97 <dSPcl mtp bytesperunit>") != 1
            or normalized.count("89 8F <dSPcl mtp bytesperunit>") != 1
            or normalized.split().count("52") != 0
            or normalized.split().count("56") != 1
            or normalized.split().count("57") != 1
            or normalized.split().count("58") != 0
            or normalized.split().count("59") != 0
            or normalized.split().count("5E") != 1
            or normalized.split().count("5F") != 1
            or "31 ED" in normalized
            or normalized.count("8D 68 04") != 1
            or normalized.count("0F B7 ED") != 1
            or "66 8D 68" in normalized
            or (label == "PG terrain pixel native" and
                ("66 40" in normalized or
                 "01 D0" in normalized or
                 normalized.count("66 45") != 1 or
                 normalized.count("89 14 AE") != 1))
            or (label == "PG terrain cull pixel native" and
                ("66 83 C0 02" in normalized or
                 "8D 04 50" in normalized or
                 normalized.count("66 45") != 2 or
                 normalized.count("89 14 AE") != 2))
            or "89 94 AE A0 8B 10 00" in normalized
            or normalized.count("0F B7 C0") != 2
            or len(branches) != 1
            or outer < 0
            or encoded[outer] != 0xEB
            or encoded[outer + 1] != tail_nops
            or encoded[outer + 2:] != b"\x90" * tail_nops
        ):
            return False
        loop = branches[0]
        if (
            encoded[10:11] != b"\x56"
            or encoded[11:17] != b"\x8b\x97\0\0\0\0"
            or encoded[17:23] != b"\xff\xb7\0\0\0\0"
            or encoded[23:29] != b"\xff\xb7\0\0\0\0"
            or encoded[29:35] != b"\xff\xb7\0\0\0\0"
            or encoded[35:41] != b"\x8b\x8f\0\0\0\0"
            or encoded[41:47] != b"\x8b\x87\0\0\0\0"
            or encoded[47:53] != b"\x8b\x9f\0\0\0\0"
            or encoded[53:81] != (
                b"\x8d\x68\x04\x0f\xb7\xed"
                b"\x8b\x87\0\0\0\0\x8d\x84\x86\x70\x68\x06\x00"
                b"\x81\xc6\xa0\x8b\x10\x00\x57\x89\xd7")
            or loop + 2 + struct.unpack("b", encoded[loop + 1:loop + 2])[0]
                != 81
            or encoded[loop + 2:loop + 17] != (
                b"\x89\xca\x89\xf9\x5f\x8d\x45\xfc\x0f\xb7\xc0"
                b"\x8d\x64\x24\x0c")
            or encoded[loop + 17:loop + 23] != b"\x89\x87\0\0\0\0"
            or encoded[loop + 23:loop + 29] != b"\x89\x9f\0\0\0\0"
            or encoded[loop + 29:loop + 35] != b"\x8d\x40\x03\x0f\xb7\xc0"
            or encoded[loop + 35:loop + 41] != b"\x89\x97\0\0\0\0"
            or encoded[loop + 41:loop + 47] != b"\x89\x8f\0\0\0\0"
            or encoded[loop + 47:loop + 48] != b"\x5e"
            or encoded[loop + 48:loop + 49] != b"\x5d"
            or outer != loop + 49
            or outer + 2 + struct.unpack("b", encoded[outer + 1:outer + 2])[0]
                != len(encoded)
        ):
            return False

    vectors = (
        (0xABCD, 0x1234, 0x0100, 0x0200, 0, 0),
        (0x0000, 0x0000, 0xFFFF, 0x8000, 0x10000, 255),
        (0xFFFF, 0xFFFF, 1, 1, 0x20000, 17),
    )
    for initial_u, initial_v, du, dv, texture_offset, tinta in vectors:
        old_u, old_v = initial_u, initial_v
        live_u, live_v = initial_u, initial_v
        live_count = 2
        texture_scratch = live_count
        for _ in range(2):
            source_index = (
                (old_v & 0xFF00) | ((old_u >> 8) & 0xFF)) + texture_offset
            if texture_scratch >> 16:
                return False
            texture_scratch = (
                (texture_scratch & 0xFFFF0000) | (live_v & 0xFFFF))
            texture_scratch = (
                (texture_scratch & 0xFFFFFF00) | ((live_u >> 8) & 0xFF))
            live_index = texture_scratch + texture_offset
            source_pixel = ((source_index * 37 + 11) & 0xFF) + tinta
            live_pixel = ((live_index * 37 + 11) & 0xFF) + tinta
            texture_scratch = live_pixel & 0xFF
            if (live_index != source_index or
                    (live_pixel & 0xFF) != (source_pixel & 0xFF)):
                return False
            old_u = (old_u + du) & 0xFFFF
            old_v = (old_v + dv) & 0xFFFF
            live_u = (live_u + du) & 0xFFFF
            live_v = (live_v + dv) & 0xFFFF
            live_count = (live_count - 1) & 0xFFFFFFFF
        if (live_count != 0 or
                (live_u, live_v) != (old_u, old_v)):
            return False

    # The native loops derive final DI from the next wrapped store index in EBP
    # because no in-loop code observes the workspace slot.  Their pointer walk
    # must preserve every source store and final A = DI+3.
    for culling in (False, True):
        step = 2 if culling else 1
        counts = (1, 2, 16, 32) if culling else (1, 2, 8, 16)
        for initial_di in (0, 1, 0xFFF9, 0xFFFC, 0xFFFE, 0xFFFF):
            for count in counts:
                source_di = initial_di
                live_di = (initial_di + step * count) & 0xFFFF
                live_store_index = (initial_di + 4) & 0xFFFF
                source_stores: list[tuple[int, ...]] = []
                live_stores: list[tuple[int, ...]] = []
                for _ in range(count):
                    source_di = (source_di + step) & 0xFFFF
                    if culling:
                        source_stores.append((
                            (source_di + 2) & 0xFFFF,
                            (source_di + 3) & 0xFFFF,
                        ))
                        live_stores.append((
                            live_store_index,
                            (live_store_index + 1) & 0xFFFF,
                        ))
                        live_store_index = (live_store_index + 2) & 0xFFFF
                    else:
                        source_stores.append(((source_di + 3) & 0xFFFF,))
                        live_stores.append((live_store_index,))
                        live_store_index = (live_store_index + 1) & 0xFFFF
                source_a = (source_di + 3) & 0xFFFF
                live_a = (live_di + 3) & 0xFFFF
                if (live_stores != source_stores or live_di != source_di or
                        live_a != source_a):
                    return False
    return True


def halfscan_native_preserves_duplication(source: str) -> bool:
    """Check the fixed-size native halfscan retains exact wrapped duplicates."""
    expected_length, expected_hash, tail_nops = PGTEX_HALFSCAN_NATIVE_CONTRACT
    service = labelled_service(source, "PG halfscan native")
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    if len(bodies) != 1 or source.count("=> PG halfscan native;") != 1:
        return False

    body = bodies[0]
    normalized = " ".join(body.split())
    code = "\n".join(line.split("(", 1)[0] for line in body.splitlines())
    tokens = re.findall(r"<[^>]+>|[0-9A-Fa-f]{2}", code)
    encoded = b"".join(
        b"\0" * 4 if token.startswith("<") else bytes.fromhex(token)
        for token in tokens
    )
    setup = (
        b"\x55\x8b\xb7\0\0\0\0\x8d\x34\xb7\x56"
        b"\x81\xc6\xa0\x8b\x10\x00\x8b\x8f\0\0\0\0"
        b"\x8b\x87\0\0\0\0\x8d\x68\x04\x0f\xb7\xed"
        b"\x8d\x90\x43\x01\x00\x00\x0f\xb7\xd2"
        b"\x2d\x3c\x01\x00\x00\x0f\xb7\xc0"
    )
    loop = (
        b"\x66\x42\x0f\xb6\x1c\x86\x89\x1c\xae\x89\x1c\x96"
        b"\x66\x40\x66\x45\x49\x75\xed"
    )
    epilogue = (
        b"\x8d\x45\xfc\x0f\xb7\xc0\x89\x87\0\0\0\0"
        b"\x89\x8f\0\0\0\0\x5e\x5d"
    )
    outer = len(encoded) - tail_nops - 2
    if (
        len(encoded) != expected_length
        or normalized_hash(body) != expected_hash
        or encoded[:52] != setup
        or encoded[52:71] != loop
        or encoded[71:91] != epilogue
        or outer != 91
        or encoded[outer:outer + 2] != bytes((0xEB, tail_nops))
        or encoded[outer + 2:] != b"\x90" * tail_nops
        or 69 + 2 + struct.unpack("b", encoded[70:71])[0] != 52
        or outer + 2 + struct.unpack("b", encoded[outer + 1:outer + 2])[0]
            != len(encoded)
        or normalized.split().count("55") != 1
        or normalized.split().count("56") != 1
        or normalized.split().count("5E") != 1
        or normalized.split().count("5D") != 1
        or normalized.count("81 C6 A0 8B 10 00") != 1
        or normalized.count("0F B6 1C 86") != 1
        or normalized.count("89 1C AE") != 1
        or normalized.count("89 1C 96") != 1
        or "8B 9C 96 A0 8B 10 00" in normalized
        or "89 9C 96 A0 8B 10 00" in normalized
        or "81 E2 FF FF 00 00" in normalized
        or "81 E3 FF 00 00 00" in normalized
        or "25 FF FF 00 00" in normalized
        or "0F 85 B1 FF FF FF" in normalized
    ):
        return False

    for initial_di in (0, 1, 315, 316, 0xFEBB, 0xFEBC, 0xFFFC, 0xFFFF):
        for count in (1, 2, 17, 320, 641):
            source_di = initial_di
            native_source = (initial_di - 316) & 0xFFFF
            native_first = (initial_di + 4) & 0xFFFF
            native_second = (initial_di + 323) & 0xFFFF
            source_events: list[tuple[int, int, int, int]] = []
            native_events: list[tuple[int, int, int, int]] = []
            source_pixel = native_pixel = 0
            for _ in range(count):
                source_index = (source_di - 316) & 0xFFFF
                source_pixel = ((source_index * 0x10203 + 0xA5F077) &
                                0xFFFFFFFF) & 0xFF
                source_events.append((
                    source_index,
                    (source_di + 4) & 0xFFFF,
                    (source_di + 324) & 0xFFFF,
                    source_pixel,
                ))
                source_di = (source_di + 1) & 0xFFFF

                native_second = (native_second + 1) & 0xFFFF
                native_pixel = ((native_source * 0x10203 + 0xA5F077) &
                                0xFFFFFFFF) & 0xFF
                native_events.append((
                    native_source, native_first, native_second, native_pixel))
                native_source = (native_source + 1) & 0xFFFF
                native_first = (native_first + 1) & 0xFFFF

            native_di = (native_first - 4) & 0xFFFF
            source_edx = (source_di + 323) & 0xFFFF
            if (
                native_events != source_events
                or native_di != source_di
                or native_second != source_edx
                or native_pixel != source_pixel
            ):
                return False
    return True


def direct_depth_matches_spilled_binary64() -> bool:
    """Check the in-register x87 depth against the source qword-spill result."""
    tile = 16384
    limit = 66 * tile
    vectors = [
        (offset * tile + fraction - 8192,
         other * tile + other_fraction - 8192)
        for offset in range(-66, 67, 3)
        for other in range(-66, 67, 5)
        for fraction in (0, 1, 8191, 8192, 16383)
        for other_fraction in (0, 8191, 8192, 16383)
    ]
    state = 0x31415926
    for _ in range(50_000):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        dx = state % (2 * limit + 1) - limit
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        dz = state % (2 * limit + 1) - limit
        vectors.append((dx, dz))
    for dx, dz in vectors:
        squared = dx * dx + dz * dz
        source = int(math.sqrt(float(dx) * float(dx) +
                               float(dz) * float(dz))) >> 14
        direct = math.isqrt(squared) >> 14
        if source != direct:
            return False
    return True


def cached_normal_widen_roundtrips_binary32() -> bool:
    """Check the direct x87 m32-to-m64 widening used by the normal cache."""
    patterns = [
        0x00000000, 0x80000000, 0x00000001, 0x007FFFFF,
        0x00800000, 0x3F000000, 0x3F800000, 0xBF800000,
        0x7F7FFFFF, 0xFF7FFFFF,
    ]
    state = 0x27182818
    for _ in range(50_000):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        if state & 0x7F800000 != 0x7F800000:
            patterns.append(state)
    for bits in patterns:
        widened = float(struct.unpack("<f", struct.pack("<I", bits))[0])
        roundtrip = struct.unpack("<I", struct.pack("<f", widened))[0]
        if roundtrip != bits:
            return False
    return True


def second_triangle_reuse_preserves_coordinate_bits() -> bool:
    """Check P2/P4 reuse against rebuilding the second terrain triangle."""
    def binary64(value: int) -> bytes:
        return struct.pack("<d", float(value))

    vectors = [
        (-66, -66, 1, -255, -254, -1, 0),
        (-1, 0, 2, 0, 1, 254, 255),
        (0, 1, 4, 255, 128, 64, 32),
        (65, 65, 8, -32, -64, -128, -255),
    ]
    state = 0x16180339
    for _ in range(50_000):
        values = []
        for _ in range(7):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            values.append(state)
        vectors.append((
            values[0] % 133 - 66,
            values[1] % 133 - 66,
            1 << (values[2] % 4),
            *(value % 511 - 255 for value in values[3:]),
        ))

    for x, z, step, s1, s2, s3, s4 in vectors:
        x0 = x << 14
        x1 = (x + step) << 14
        z0 = z << 14
        z1 = (z + step) << 14
        first = (
            (binary64(x0), binary64(-(s1 << 11)), binary64(z0)),
            (binary64(x1), binary64(-(s2 << 11)), binary64(z0)),
            (binary64(x0), binary64(-(s4 << 11)), binary64(z1)),
        )
        rebuilt = (
            (binary64(x1), binary64(-(s2 << 11)), binary64(z0)),
            (binary64(x1), binary64(-(s3 << 11)), binary64(z1)),
            (binary64(x0), binary64(-(s4 << 11)), binary64(z1)),
        )
        reused = (
            first[1],
            (first[1][0], binary64(-(s3 << 11)), first[2][2]),
            first[2],
        )
        if reused != rebuilt:
            return False
    return True


def first_triangle_height_multistore_preserves_bits(source: str) -> bool:
    """Check one x87 value supplies the first triangle's P4 and final FA."""
    service = labelled_service(source, "VHGND terrain triangle load native")
    bodies = re.findall(r"\{([^}]*)\}", service, flags=re.DOTALL)
    body = " ".join(bodies[0].split()) if len(bodies) == 1 else ""
    multistore = (
        "DB 87 <dFI mtp bytesperunit> "
        "DD 96 10 08 00 00 "
        "DD 9F <dFA0 mtp bytesperunit> "
        "EB 70 "
        "90 90 90 90 90 90 "
        "DD 86 E8 07 00 00"
    )
    if (
        len(bodies) != 1
        or body.count(multistore) != 1
        or "DD 9E 10 08 00 00 DD 86 10 08 00 00" in body
        or body.split().count("90") != 6
    ):
        return False

    for sample in range(-255, 256):
        height = -(sample << 11)
        source_vertex = struct.pack("<d", float(height))
        source_fa = struct.pack(
            "<d", struct.unpack("<d", source_vertex)[0])
        native_value = struct.pack("<d", float(height))
        native_vertex = native_value
        native_fa = native_value
        source_stack = (0, "empty")
        native_stack = (0, "empty")
        if ((native_vertex, native_fa, native_stack) !=
                (source_vertex, source_fa, source_stack)):
            return False
    return True


def terrain_mapping_reuses_triangle_selector(source: str) -> bool:
    """Check each mapping call consumes its loader's existing selector."""
    tile = labelled_service(source, "VHGND tile")
    loads = [match.start() for match in re.finditer(
        r"=> VHGND terrain triangle load native; => VHGND terrain facing;",
        tile,
    )]
    mappings = [match.start() for match in re.finditer(
        r"\[PGtexf\] = 5; => VHGND terrain mapped;", tile)]
    zero = tile.find("[VHGNDvctri] = 0;")
    one = tile.find("[VHGNDvctri] = 1;")
    return (tile.count("[VHGNDvctri] =") == 2 and
            len(loads) == 2 and len(mappings) == 2 and
            0 <= zero < loads[0] < mappings[0] < one < loads[1] < mappings[1])


def cached_bounds_skip_duplicate_preserves_state() -> bool:
    """Check three unique projected vertices against the closed four walk."""
    def scan(points: list[tuple[int, int]]) -> tuple[int, int, int, int, int]:
        min_x, max_x, min_y, max_y = 311, 5, 190, 10
        final_eax = 0
        for x, y in points:
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            final_eax = y
        return min_x, max_x, min_y, max_y, final_eax

    vectors = [
        [(311, 190), (5, 10), (158, 100)],
        [(-0x80000000, 0x7FFFFFFF), (0x7FFFFFFF, -0x80000000), (0, 0)],
    ]
    state = 0x14142135
    for _ in range(50_000):
        points = []
        for _ in range(3):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            x = state - 0x100000000 if state & 0x80000000 else state
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            y = state - 0x100000000 if state & 0x80000000 else state
            points.append((x, y))
        vectors.append(points)

    return all(scan(points) == scan(points + [points[2]])
               for points in vectors)


def main() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        print("PASS" if condition else "FAIL", message)
        if not condition:
            failures.append(message)

    portable = {
        relative: digest(ROOT / relative)
        for relative in (
            Path("work/fp/fpx87.txt"),
            Path("work/fp/fpconv.txt"),
            Path("work/mul64frag.txt"),
            Path("work/pgproj.txt"),
            Path("work/pgtex.txt"),
            staging.SOURCE_RELATIVE,
            Path("work/vhground.txt"),
            Path("work/vhspace.txt"),
        )
    }
    with tempfile.TemporaryDirectory(prefix="lino-i386-stage-") as temporary:
        output = Path(temporary)
        source = staging.stage_source(ROOT, output)
        check(source == output / staging.SOURCE_RELATIVE and
              source.read_bytes() ==
                  (ROOT / "src/linoleum_i386/vhgame.txt").read_bytes() and
              source.read_bytes() != (ROOT / staging.SOURCE_RELATIVE).read_bytes(),
              "stage returns the overlaid game source")
        for name, relative in staging.OVERRIDES.items():
            check((output / relative).read_bytes() ==
                  (ROOT / "src/linoleum_i386" / name).read_bytes(),
                  f"stage selects target i386 {name}")
        manifest_path = output / staging.MANIFEST_NAME
        manifest_bytes = manifest_path.read_bytes()
        manifest_lines = manifest_path.read_text(
            encoding="ascii").splitlines()
        manifest = dict(line.split("=", 1) for line in manifest_lines)
        expected_manifest_order = [
            "source_sha256",
            *(staging.override_provenance_key(name)
              for name, relative in sorted(staging.OVERRIDES.items())
              if relative != staging.SOURCE_RELATIVE),
            "source_staging_script_sha256",
        ]
        check(len(manifest) == len(manifest_lines) and
              list(manifest) == expected_manifest_order and
              all(manifest[staging.override_provenance_key(name)] ==
                  digest(output / relative)
                  for name, relative in staging.OVERRIDES.items()) and
              manifest["source_sha256"] == digest(source) and
              manifest["source_staging_script_sha256"] ==
                  digest(ROOT / "tools/stage_windows_i386_source.py"),
              "stage manifest bijectively hashes every consumed source override")
        check(b"\r" not in manifest_bytes and manifest_bytes.endswith(b"\n"),
              "stage manifest uses host-independent LF records")
        portable_game = (ROOT / staging.SOURCE_RELATIVE).read_text(encoding="utf-8")
        staged_game = source.read_text(encoding="utf-8")
        portable_smooth64 = labelled_service(portable_game, "VHG interior smooth64")
        staged_smooth64 = labelled_service(staged_game, "VHG interior smooth64")
        check(bool(portable_smooth64) and bool(staged_smooth64) and
              staged_game.replace(staged_smooth64, portable_smooth64, 1) ==
                  portable_game,
              "game overlay changes only the smooth64 service implementation")
        check(smooth64_native_contract(staged_game) == SMOOTH64_NATIVE_CONTRACT,
              "game overlay has the exact historical smooth64 call and body hashes")
        check(game_variables(staged_game) == game_variables(portable_game) and
              SMOOTH64_NATIVE_VARIABLES.issubset(game_variables(staged_game)),
              "game overlay retains exactly the current variables including smooth64")
        check(all(anchor in staged_game
                  for anchor in SMOOTH64_CURRENT_SOURCE_ANCHORS),
              "game overlay retains fixed-FCW and current gameplay/profile fixes")
        check(native_block_labels(portable_game) == [] and
              native_block_labels(staged_game) == ["VHG interior smooth64"],
              "game overlay contains no unreviewed native blocks")

        portable_terrain = (ROOT / "work/vhground.txt").read_text(encoding="utf-8")
        staged_terrain_path = output / "work/vhground.txt"
        staged_terrain = staged_terrain_path.read_text(encoding="utf-8")
        staged_projection = (output / "work/pgproj.txt").read_text(encoding="utf-8")
        staged_texture = (output / "work/pgtex.txt").read_text(encoding="utf-8")
        facing_dot = labelled_service(
            staged_projection, "PG terrain facing dot native")
        facing_dot_bodies = re.findall(r"\{([^}]*)\}", facing_dot, flags=re.DOTALL)
        check(len(facing_dot_bodies) == 1 and
              normalized_hash(facing_dot_bodies[0]) ==
                  TERRAIN_FACING_DOT_BODY_HASH and
              "8D B7 <dfw mtp bytesperunit>" in facing_dot and
              "PJfwbase" not in facing_dot and
              staged_terrain.count("=> PG terrain facing dot native;") == 1 and
              "[VHGNDvctri] = 0; A = fw; [PJfwbase] = A;" in staged_terrain,
              "terrain dot loads invariant fw directly with preserved caller state")
        check(terrain_uv_native_separates_exact_spills(staged_texture) and
              not terrain_uv_native_separates_exact_spills(
                  staged_texture.replace(
                      "DD 9E C0 07 00 00", "DD 9E C8 07 00 00", 1)),
              "terrain UV separates exact binary64/binary32 spills from reloads")
        check(terrain_unpack_native_preserves_block_state(staged_texture) and
              not terrain_unpack_native_preserves_block_state(
                  staged_texture.replace(
                      "89 CA\n\t    81 E2 FF FF 00 00",
                      "89 C2\n\t    81 E2 FF FF 00 00", 1)),
              "native terrain UV unpack preserves exact block state")
        check(edges_native_retains_binary64_accumulator(staged_texture) and
              not edges_native_retains_binary64_accumulator(
                  staged_texture.replace(
                      "DB 97 <dFI mtp bytesperunit>",
                      "DB 9F <dFI mtp bytesperunit>", 1)) and
              not edges_native_retains_binary64_accumulator(
                  staged_texture.replace(
                      "42 49 75 B3", "42 49 75 B2", 1)),
              "native edge rows retain exact binary64 accumulation without reloads")
        check(terrain_pixel_loops_preserve_samples(staged_texture) and
              not terrain_pixel_loops_preserve_samples(
                  staged_texture.replace("88 FA", "88 DA", 1)) and
              not terrain_pixel_loops_preserve_samples(
                  staged_texture.replace(
                      "75 E1", "75 E2", 1)),
              "opaque terrain pixel loops preserve exact UV samples and loop targets")
        check(halfscan_native_preserves_duplication(staged_texture) and
              not halfscan_native_preserves_duplication(
                  staged_texture.replace("75 ED", "75 EC", 1)) and
              not halfscan_native_preserves_duplication(
                  staged_texture.replace("8D 90 43 01 00 00",
                                         "8D 90 44 01 00 00", 1)),
              "halfscan native loop preserves exact wrapped row duplication")
        check(staged_terrain_path.read_bytes() !=
              (ROOT / "work/vhground.txt").read_bytes(),
              "stage overlays the portable terrain source")
        check(len(TERRAIN_NATIVE_CONTRACT) == 37 and
              terrain_native_contract(staged_terrain) ==
                  expected_terrain_native_contract(),
              "terrain overlay has exact 37-label native call and body coverage")
        check(native_tile_admission_needs_no_completion_protocol(staged_terrain),
              "native tile admission consumes its return without dead completion state or reloads")
        check(native_tile_admission_returns_branch_value(staged_terrain) and
              not native_tile_admission_returns_branch_value(
                  staged_terrain.replace(
                      "EB 04\n\t    90 90 90 90\n\t    83 F8 5A",
                      "EB 05\n\t    90 90 90 90\n\t    83 F8 5A", 1)) and
              not native_tile_admission_returns_branch_value(
                  staged_terrain.replace(
                      "EB 04\n\t    90 90 90 90",
                      "EB 05\n\t    90 90 90 90", 1)),
              "native tile admission keeps its result live through both exact alignment skips")
        check(native_tile_samples_preserve_lino_state(staged_terrain) and
              not native_tile_samples_preserve_lino_state(
                  staged_terrain.replace("0F B6 04 B7", "0F B6 04 9F", 1)) and
              not native_tile_samples_preserve_lino_state(
                  staged_terrain.replace("EB 2B", "EB 2C", 1)),
              "native packed terrain samples preserve low bytes, live state, dead flags, and alignment target")
        check(native_tile_shade_preserves_live_ecx(staged_terrain) and
              not native_tile_shade_preserves_live_ecx(
                  staged_terrain.replace("EB 12", "EB 13", 1)),
              "native tile shade keeps ECX live and skips exact alignment padding")
        check(terrain_texture_gates_prefer_unit_path(staged_terrain) and
              not terrain_texture_gates_prefer_unit_path(
                  staged_terrain.replace(
                      "EB 03\n\t    90 90 90",
                      "EB 04\n\t    90 90 90", 1)),
              "both unit-LOD terrain triangles branch directly to textured rendering")
        check(terrain_facing_gates_prefer_visible_path(staged_terrain) and
              not terrain_facing_gates_prefer_visible_path(
                  staged_terrain.replace(
                      "A = [FCret]; ? A != 0 -> VHGND tile first visible; "
                      "-> VHGND tile first done;",
                      "A = [FCret]; ? A = 0 -> VHGND tile first visible; "
                      "-> VHGND tile first done;", 1)),
              "ordinary terrain facing branches directly to visible triangles")
        check(direct_depth_matches_spilled_binary64(),
              "streamlined x87 admission preserves every sampled source depth bin")
        check(cached_normal_widen_roundtrips_binary32(),
              "direct cached-normal loads preserve sampled binary32 bit patterns")
        check(second_triangle_reuse_preserves_coordinate_bits(),
              "second terrain triangle reuses exact sampled P2/P4 coordinates")
        check(first_triangle_height_multistore_preserves_bits(staged_terrain) and
              not first_triangle_height_multistore_preserves_bits(
                  staged_terrain.replace(
                      "DD 96 10 08 00 00", "DD 9E 10 08 00 00", 1)),
              "first terrain triangle multistores one exact P4 height without an x87 reload")
        check(terrain_mapping_reuses_triangle_selector(staged_terrain),
              "terrain mapping reuses each loader selector without restamping")
        check(triangle_loader_branches_land_on_instruction_boundaries(
                  staged_terrain) and
              not triangle_loader_branches_land_on_instruction_boundaries(
                  staged_terrain.replace(
                      "0F 85 B9 00 00 00", "0F 85 B6 00 00 00", 1)) and
              not triangle_loader_branches_land_on_instruction_boundaries(
                  staged_terrain.replace("EB 70", "EB 6F", 1)),
              "triangle branch verifier rejects off-boundary arm and tail targets")
        check(cached_bounds_skip_duplicate_preserves_state(),
              "three-entry terrain bounds preserve closed-walk bounds and EAX")
        check("A = mp; C = [A plus 4]; [A plus 6] = C; "
              "C = [A plus 5]; [A plus 7] = C; A = rwf; "
              "[A plus 3] = 1; [PJdoflag] = 4; "
              "=> VHGND terrain cached bounds;" in
              " ".join(staged_terrain.split()),
              "terrain closes projected slot three before cached bounds")
        expected_native_labels = sorted(
            label
            for label, (_, bodies, _) in TERRAIN_NATIVE_CONTRACT.items()
            for _ in range(bodies)
        )
        check(sorted(native_block_labels(staged_terrain)) ==
              expected_native_labels,
              "terrain overlay contains no unreviewed native blocks")
        check(TERRAIN_NATIVE_VARIABLES.isdisjoint(
                  terrain_variables(portable_terrain)) and
              terrain_variables(staged_terrain) ==
                  terrain_variables(portable_terrain) | TERRAIN_NATIVE_VARIABLES,
              "terrain overlay adds exactly the historical native variables")
        check(all(anchor in staged_terrain
                  for anchor in TERRAIN_CURRENT_SOURCE_ANCHORS),
              "terrain overlay retains post-kernel current-source fixes")
        try:
            staging.stage_source(ROOT, output)
        except ValueError:
            rejected = True
        else:
            rejected = False
        check(rejected, "stage refuses to overwrite retained files")

    check(all(digest(ROOT / relative) == expected
              for relative, expected in portable.items()),
          "staging never modifies portable source")

    linux_build = (ROOT / "build/compile_vhgame_linux.sh").read_text(encoding="utf-8")
    source_release = (ROOT / ".github/workflows/source-release.yml").read_text(
        encoding="utf-8")
    package_workflows = {
        "snapshot": (ROOT / ".github/workflows/windows-release.yml").read_text(
            encoding="utf-8"),
        "tagged": (ROOT / ".github/workflows/tagged-release.yml").read_text(
            encoding="utf-8"),
    }
    check("stage_windows_i386_source.py" in linux_build and
          'mktemp -d "/tmp/linoleum-windows-i386-source.' in linux_build and
          'cp -R "$repo/main/." "$stage/main"' in linux_build and
          "--cpu:i386m" in linux_build and "--env:$stage/main" in linux_build,
          "Linux Windows build stages source and target packs on native storage")
    check("stage_windows_i386_source.py" in source_release and
          '-Compiler "$PWD\\main\\lib\\gen\\compiler114m.exe"' in source_release and
          "-Cpu i386m" in source_release,
          "interactive source release uses the extended compiler on staged i386m source")
    check(staging.MANIFEST_NAME in linux_build and
          staging.MANIFEST_NAME in source_release and
          "source_manifest_sha256" in linux_build and
          "source_manifest_sha256" in source_release,
          "both build paths consume and bind the generated source manifest")
    runtime_provenance_keys = (
        "runtime_patcher_sha256", "executable_sha256", "compiler_sha256",
        "cpu_pack_sha256", "system_pack_sha256",
    )
    check(all(key in linux_build and key in source_release
              for key in runtime_provenance_keys) and
          "build_wrapper_sha256" in source_release and
          "compile_script_sha256" in linux_build,
          "both build paths bind their consumed runtime and build inputs")

    expected_package_keys = (
        "commit", "source_manifest_sha256", "source_sha256",
        "runtime_patcher_sha256", "executable_sha256", "compile_script_sha256",
        "compiler_runtime_installer_sha256", "bootstrap_compiler_sha256",
        "compiler_source_sha256", "compiler_bits_library_sha256",
        "compiler_bytes_library_sha256", "compiler_build_script_sha256",
        "bootstrap_cpu_pack_sha256", "bootstrap_system_pack_sha256",
        "compiler_sha256", "cpu_pack_sha256", "system_pack_sha256", "target",
        "build_provenance",
    )
    check(all(package_required_keys(workflow) == expected_package_keys
              for workflow in package_workflows.values()),
          "snapshot and tagged packages require the complete build provenance")
    validation_record = (
        "validation_reference_commit="
        "94200172ee2ca859de15f0c7b03dfa1939874681"
    )
    provenance_path = "dist\\Noctis-IV-windows-x86.provenance.txt"
    check(all(
        append.count('"archive_sha256=$zipHash"') == 1 and
        append.count(validation_record) == 1 and
        f"Add-Content -LiteralPath {provenance_path} -Encoding ascii" in append
        for append in map(package_provenance_append, package_workflows.values())
    ), "snapshot and tagged provenance cross-link the archive and validation source")
    check(all("python tests\\test_windows_i386_stage.py" in workflow
              for workflow in (*package_workflows.values(), source_release)),
          "every Windows release validation runs the staging regression")

    if failures:
        print(f"windows i386 stage: {len(failures)} failure(s)")
        return 1
    print("windows i386 stage: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
