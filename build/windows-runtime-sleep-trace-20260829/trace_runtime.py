from pathlib import Path
import hashlib
import json
import struct

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/windows-runtime-sleep-trace-20260829"
SYS_PACK = ROOT / "main/sys/win32.bin"
EXECUTABLE = ROOT / "work/vhgame.exe"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


sys_pack = SYS_PACK.read_bytes()
executable = EXECUTABLE.read_bytes()
variant_count = u32(sys_pack, 0)
assert variant_count == 8
header_size = 4 * (1 + variant_count + variant_count)
offsets = [u32(sys_pack, 4 + 4 * index) for index in range(variant_count)]
sizes = [
    u32(sys_pack, 4 + 4 * variant_count + 4 * index)
    for index in range(variant_count)
]

# vhgame selects modular-extension variant 2 (audio playback). The compiler
# copies this RTM verbatim and then updates only the LNLM initialization
# paragraph with application dimensions, sizes, and workspace defaults.
variant_index = 2
variant = sys_pack[
    header_size + offsets[variant_index]:
    header_size + offsets[variant_index] + sizes[variant_index]
]
assert len(variant) == 0x5000
assert executable[:2] == variant[:2] == b"MZ"
differences = [
    offset for offset, (left, right) in enumerate(zip(variant, executable))
    if left != right
]
assert len(differences) == 33
assert b"LNLMInit" in variant
init_offset = variant.index(b"LNLMInit")
assert all(
    0x266F <= offset <= 0x2675
    or init_offset <= offset < init_offset + 256
    for offset in differences
)

# PE32 mapping for this fixed Win32 RTM: .text RVA 0x1000 is at file 0x400.
def text_file_offset(virtual_address):
    return virtual_address - 0x400000 - 0x1000 + 0x400


sleep_handler_va = 0x402B7B
sleep_thunk_va = 0x403C50
sleep_handler = executable[
    text_file_offset(sleep_handler_va):text_file_offset(sleep_handler_va) + 12
]
sleep_thunk = executable[
    text_file_offset(sleep_thunk_va):text_file_offset(sleep_thunk_va) + 6
]
assert sleep_handler == bytes.fromhex(
    "ff b7 84 02 02 00 e8 ca 10 00 00 c3"
)
assert sleep_thunk == bytes.fromhex("ff 25 30 40 40 00")
assert b"Sleep\x00" in executable[:0x5000]

result = {
    "schema": 1,
    "task": 201,
    "sys_pack": {
        "path": "main/sys/win32.bin",
        "sha256": digest(sys_pack),
        "variant_count": variant_count,
        "selected_variant": variant_index,
        "selected_variant_offset": offsets[variant_index],
        "selected_variant_size": sizes[variant_index],
        "selected_variant_sha256": digest(variant),
    },
    "executable": {
        "path": "work/vhgame.exe",
        "sha256": digest(executable),
        "runtime_initialization_difference_bytes": len(differences),
        "runtime_initialization_difference_min_offset": min(differences),
        "runtime_initialization_difference_max_offset": max(differences),
    },
    "sleep_implementation": {
        "handler_virtual_address": hex(sleep_handler_va),
        "handler_bytes": sleep_handler.hex(),
        "timeout_workspace_byte_offset": hex(0x20284),
        "sleep_thunk_virtual_address": hex(sleep_thunk_va),
        "sleep_thunk_bytes": sleep_thunk.hex(),
        "import_iat_virtual_address": hex(0x404030),
        "behavior": "push Sleep Timeout; call kernel32!Sleep; return",
        "sleep_zero_semantics": "direct Windows Sleep(0) scheduler yield",
    },
    "conclusion": (
        "The tracked Win32 SYS pack implements Lino SLEEP as a direct call to "
        "kernel32!Sleep with the shared workspace timeout. A more precise timed "
        "wait would require changing the native SYS-pack runtime/import surface; "
        "the next least-invasive candidate should remain in shared Lino."
    ),
    "status": "pass",
}
(EVIDENCE / "result.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
manifest_files = ("trace_runtime.py", "result.json")
manifest = {
    "schema": 1,
    "files": {
        relative: {
            "bytes": (EVIDENCE / relative).stat().st_size,
            "sha256": digest((EVIDENCE / relative).read_bytes()),
        }
        for relative in manifest_files
    },
}
(EVIDENCE / "manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, indent=2))
