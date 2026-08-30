from pathlib import Path
import hashlib
import json
import shutil

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fmul-lowering-20260830"
ACCEPTED = EVIDENCE / "accepted"
CANDIDATE = EVIDENCE / "candidate"
ACCEPTED_COMPILER_SOURCE_SHA256 = (
    "be83e4e9160497af7b3272a5f0245ce813a76927ff3807249dce5c0dd5d00e19")
ACCEPTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
I386M_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")
I386_PACK_SHA256 = (
    "26714bde27cc6c3d91b6be3a19e59f3ef8c856b942b08252d88034cce367786e")
X64_PACK_SHA256 = (
    "786b2cca48708735b1afc360e0b2c147d103d39d94ad8d439a2eec1d694761ab")
ACCEPTED_FPABI_SHA256 = (
    "0c2f2602a82b9619d0bb909098857f804482456c504c2667874046be0598c7fd")
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
GAME_SOURCE_SHA256 = (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
ACCEPTED_GAME_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
XSCALAR_MUL_START = 0x255F0
XSCALAR_MUL_END = 0x2566A
XFROM_REJECT_START = 0x23907
PREREQUISITE_DISTANCE = XSCALAR_MUL_END - XFROM_REJECT_START
ACCEPTED_SCALAR = bytes.fromhex(
    "8B 87 28 26 00 00 89 87 A0 26 00 00 "
    "8B 87 2C 26 00 00 89 87 A4 26 00 00 E8 C2 E1 FF FF "
    "8B 87 78 26 00 00 89 87 88 26 00 00 "
    "8B 87 7C 26 00 00 89 87 8C 26 00 00 "
    "8B 87 80 26 00 00 89 87 90 26 00 00 "
    "8B 87 84 26 00 00 89 87 94 26 00 00 "
    "8B 87 20 26 00 00 89 87 A0 26 00 00 "
    "8B 87 24 26 00 00 89 87 A4 26 00 00 E8 75 E1 FF FF "
    "E8 79 E6 FF FF E8 82 F8 FF FF BD 65 6E 6F 64 C3")
XREJ_PREREQUISITE = bytes.fromhex(
    "FF 87 A8 26 00 00 "
    "C7 87 7C 26 00 00 00 00 00 00 "
    "C7 87 80 26 00 00 00 00 00 00 "
    "C7 87 84 26 00 00 00 00 00 00 "
    "BD 65 6E 6F 64 C3")
CANDIDATE_ASSEMBLY = """
    lea esi, [edi + 0x2620]
    lea edx, [edi + 0x2678]
    mov eax, dword ptr [esi + 4]
    mov ebx, dword ptr [esi + 12]
    mov ecx, eax
    add ecx, ecx
    cmp ecx, 0xffe00000
    jae reject_a
    mov ecx, ebx
    add ecx, ecx
    cmp ecx, 0xffe00000
    jae reject_b
    fld qword ptr [esi]
    fmul qword ptr [esi + 8]
    fstp tbyte ptr [edx]
    fld tbyte ptr [edx]
    fstp qword ptr [esi]
    movzx ecx, word ptr [edx + 8]
    and ch, 0x7f
    jz done
    cmp cx, 0x3bcc
    jb count
    mov ecx, dword ptr [esi + 4]
    add ecx, ecx
    cmp ecx, 0xffe00000
    jb done
count:
    inc dword ptr [edx + 0x30]
done:
    ret
reject_a:
    inc dword ptr [edx + 0x30]
    mov ecx, ebx
    add ecx, ecx
    cmp ecx, 0xffe00000
    jb special
reject_b:
    inc dword ptr [edx + 0x30]
special:
    xor eax, ebx
    shr eax, 31
    ror eax, 1
    xor ecx, ecx
    mov dword ptr [esi], ecx
    mov dword ptr [esi + 4], eax
    ret
"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def assemble_candidate():
    assembler = Ks(KS_ARCH_X86, KS_MODE_32)
    encoded, count = assembler.asm(CANDIDATE_ASSEMBLY, addr=XSCALAR_MUL_START)
    result = bytes(encoded)
    assert count > 0 and len(result) == 119
    result += b"\x90" * (len(ACCEPTED_SCALAR) - len(result))
    assert len(result) == len(ACCEPTED_SCALAR) == 122
    decoded = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(
        result, XSCALAR_MUL_START))
    assert decoded[-1].address + decoded[-1].size == XSCALAR_MUL_END
    assert [item.mnemonic for item in decoded[-4:]] == [
        "ret", "nop", "nop", "nop"]
    return result


CANDIDATE_SCALAR = assemble_candidate()
assert len(XREJ_PREREQUISITE) == 42
assert PREREQUISITE_DISTANCE == 0x1D63


def format_vector(newline, name, blob):
    values = " ".join(f"{value:02X}h;" for value in blob)
    return f"\tvector {name} =\r\n\t  {values}".replace("\r\n", newline)


def transform_fp(source):
    assert sha256(source) == ACCEPTED_FP_SHA256
    old = (b'\t=> XMulCore;\n\t=> XToF64;\n\tend;\n\n'
           b'      ( XScalarSqrt')
    new = (b'\t=> XMulCore;\n\t=> XToF64;\n\tend;\n'
           b'\t"XSM exact i386m native fmul"\n\n'
           b'      ( XScalarSqrt')
    assert source.count(old) == 1
    result = source.replace(old, new)
    assert result.count(b'"XSM exact i386m native fmul"') == 1
    return result


def transform_compiler(source):
    assert sha256(source) == ACCEPTED_COMPILER_SOURCE_SHA256
    text = source.decode("ascii")
    newline = "\r\n"
    assert text.count(newline) == text.count("\n")

    declaration_old = (
        "\tpp vhgui fixed2x marker = { vhguiexacti386mblockoffsetfixed2x };\r\n"
        "\tvector pp vhgui compose scalar =")
    declaration_new = (
        "\tpp vhgui fixed2x marker = { vhguiexacti386mblockoffsetfixed2x };\r\n"
        "\tpp xsm fmul marker = { xsmexacti386mnativefmul };\r\n"
        + format_vector(newline, "pp xsm fmul prerequisite", XREJ_PREREQUISITE)
        + "\r\n" + format_vector(newline, "pp xsm fmul scalar", ACCEPTED_SCALAR)
        + "\r\n" + format_vector(newline, "pp xsm fmul exact", CANDIDATE_SCALAR)
        + "\r\n\tvector pp vhgui compose scalar =")
    assert text.count(declaration_old) == 1
    text = text.replace(declaration_old, declaration_new)

    workspace_old = (
        "\tpp exact island scalar = 1; (accepted byte vector for marked exact island)\r\n"
        "\tpp exact island candidate = 1; (replacement byte vector for marked exact island)\r\n"
        "\tpp exact island length = 1; (same-size marked exact island length)\r\n")
    workspace_new = (
        workspace_old
        + "\tpp exact prerequisite scalar = 1; (accepted fixed-back prerequisite vector)\r\n"
        + "\tpp exact prerequisite length = 1; (zero disables prerequisite gate)\r\n"
        + "\tpp exact prerequisite distance = 1; (marker to prerequisite start bytes)\r\n")
    assert text.count(workspace_old) == 1
    text = text.replace(workspace_old, workspace_new)

    compose_old = (
        "      ? failed -> examine vhgui fixed2x marker;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui compose scalar;\r\n")
    compose_new = (
        "      ? failed -> examine vhgui fixed2x marker;\r\n"
        "\t[pp exact prerequisite length] = 0;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui compose scalar;\r\n")
    assert text.count(compose_old) == 1
    text = text.replace(compose_old, compose_new)

    dispatch_old = (
        "      \"examine vhgui fixed2x marker\"\r\n"
        "\t[target string] = pp vhgui fixed2x marker;\r\n"
        "\t=> strcmp;\r\n"
        "      ? failed -> note prior code label;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui fixed2x scalar;\r\n"
        "\t[pp exact island candidate] = vector pp vhgui fixed2x exact;\r\n"
        "\t[pp exact island length] = 210;\r\n"
        "\t=> pp exact marked island;\r\n"
        "      \"note prior code label\"")
    dispatch_new = (
        "      \"examine vhgui fixed2x marker\"\r\n"
        "\t[target string] = pp vhgui fixed2x marker;\r\n"
        "\t=> strcmp;\r\n"
        "      ? failed -> examine xsm fmul marker;\r\n"
        "\t[pp exact prerequisite length] = 0;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui fixed2x scalar;\r\n"
        "\t[pp exact island candidate] = vector pp vhgui fixed2x exact;\r\n"
        "\t[pp exact island length] = 210;\r\n"
        "\t=> pp exact marked island;\r\n"
        "\t-> note prior code label;\r\n"
        "      \"examine xsm fmul marker\"\r\n"
        "\t[target string] = pp xsm fmul marker;\r\n"
        "\t=> strcmp;\r\n"
        "      ? failed -> note prior code label;\r\n"
        "\t[pp exact prerequisite scalar] = vector pp xsm fmul prerequisite;\r\n"
        "\t[pp exact prerequisite length] = 42;\r\n"
        "\t[pp exact prerequisite distance] = 7523;\r\n"
        "\t[pp exact island scalar] = vector pp xsm fmul scalar;\r\n"
        "\t[pp exact island candidate] = vector pp xsm fmul exact;\r\n"
        "\t[pp exact island length] = 122;\r\n"
        "\t=> pp exact marked island;\r\n"
        "      \"note prior code label\"")
    assert text.count(dispatch_old) == 1
    text = text.replace(dispatch_old, dispatch_new)

    matcher_old = (
        "\ta = [bpos];\r\n"
        "\ta - [pp prior code label position];\r\n"
        "      ? a != [pp exact island length] -> pp exact marked island restore;\r\n")
    matcher_new = (
        "\ta = [pp exact prerequisite length];\r\n"
        "      ? a = 0 -> pp exact marked island local gate;\r\n"
        "\ta = [pp exact prerequisite distance];\r\n"
        "      ? [bbss] < a -> pp exact marked island restore;\r\n"
        "\td = [bbss];\r\n"
        "\td - a;\r\n"
        "\t[target string] = [pp exact prerequisite scalar];\r\n"
        "\te = [target string];\r\n"
        "\tc = [pp exact prerequisite length];\r\n"
        "\t[pb stream] = bins;\r\n"
        "      \"pp exact marked prerequisite compare\"\r\n"
        "\t[pb offset] = d;\r\n"
        "\t=> get progressive byte;\r\n"
        "\ta = [pb bvalue];\r\n"
        "      ? a != [e] -> pp exact marked island restore;\r\n"
        "\td+;\r\n"
        "\te+;\r\n"
        "\tc ^ pp exact marked prerequisite compare;\r\n"
        "      \"pp exact marked island local gate\"\r\n"
        "\ta = [bpos];\r\n"
        "\ta - [pp prior code label position];\r\n"
        "      ? a != [pp exact island length] -> pp exact marked island restore;\r\n")
    assert text.count(matcher_old) == 1
    text = text.replace(matcher_old, matcher_new)

    result = text.encode("ascii")
    assert result.count(b"xsmexacti386mnativefmul") == 1
    assert result.count(b"vector pp xsm fmul prerequisite =") == 1
    assert result.count(b"vector pp xsm fmul scalar =") == 1
    assert result.count(b"vector pp xsm fmul exact =") == 1
    assert result.count(b'"pp exact marked prerequisite compare"') == 1
    return result


def snapshot():
    named = {
        "compiler114m.txt": ROOT / "main/lib/gen/compiler114m.txt",
        "compiler114m.exe": ROOT / "main/lib/gen/compiler114m.exe",
        "i386m.bin": ROOT / "main/cpu/i386m.bin",
        "i386.bin": ROOT / "main/cpu/i386.bin",
        "x64.bin": ROOT / "main/cpu/x64.bin",
        "fpabi.txt": ROOT / "work/fp/fpabi.txt",
        "fpsoft.txt": ROOT / "work/fp/fpsoft.txt",
        "vhgame.txt": ROOT / "work/vhgame.txt",
        "vhgame.exe": ROOT / "work/vhgame.exe",
    }
    expected = {
        "compiler114m.txt": ACCEPTED_COMPILER_SOURCE_SHA256,
        "compiler114m.exe": ACCEPTED_COMPILER_SHA256,
        "i386m.bin": I386M_PACK_SHA256,
        "i386.bin": I386_PACK_SHA256,
        "x64.bin": X64_PACK_SHA256,
        "fpabi.txt": ACCEPTED_FPABI_SHA256,
        "fpsoft.txt": ACCEPTED_FP_SHA256,
        "vhgame.txt": GAME_SOURCE_SHA256,
        "vhgame.exe": ACCEPTED_GAME_SHA256,
    }
    ACCEPTED.mkdir(parents=True, exist_ok=True)
    for name, source in named.items():
        assert sha256(source.read_bytes()) == expected[name], name
        destination = ACCEPTED / name
        if destination.exists():
            assert sha256(destination.read_bytes()) == expected[name], name
        else:
            shutil.copyfile(source, destination)


def main():
    snapshot()
    accepted_compiler = (ACCEPTED / "compiler114m.txt").read_bytes()
    accepted_fp = (ACCEPTED / "fpsoft.txt").read_bytes()
    accepted_game = (ACCEPTED / "vhgame.exe").read_bytes()
    assert accepted_game[XSCALAR_MUL_START:XSCALAR_MUL_END] == ACCEPTED_SCALAR
    assert accepted_game[
        XFROM_REJECT_START:XFROM_REJECT_START + len(XREJ_PREREQUISITE)
    ] == XREJ_PREREQUISITE
    CANDIDATE.mkdir(parents=True, exist_ok=True)
    (CANDIDATE / "compiler114m.txt").write_bytes(
        transform_compiler(accepted_compiler))
    (CANDIDATE / "fpsoft.txt").write_bytes(transform_fp(accepted_fp))
    for name in ("i386m.bin", "i386.bin", "x64.bin", "fpabi.txt", "vhgame.txt"):
        shutil.copyfile(ACCEPTED / name, CANDIDATE / name)
    report = {
        "schema": 1,
        "task": 235,
        "status": "prepared",
        "accepted_compiler_source_sha256": ACCEPTED_COMPILER_SOURCE_SHA256,
        "candidate_compiler_source_sha256": sha256(
            (CANDIDATE / "compiler114m.txt").read_bytes()),
        "accepted_fp_sha256": ACCEPTED_FP_SHA256,
        "candidate_fp_sha256": sha256((CANDIDATE / "fpsoft.txt").read_bytes()),
        "accepted_game_sha256": ACCEPTED_GAME_SHA256,
        "accepted_scalar_bytes": len(ACCEPTED_SCALAR),
        "candidate_scalar_bytes": len(CANDIDATE_SCALAR),
        "candidate_instruction_bytes_before_padding": 119,
        "candidate_nop_padding_bytes": 3,
        "xrej_prerequisite_bytes": len(XREJ_PREREQUISITE),
        "xrej_prerequisite_distance": PREREQUISITE_DISTANCE,
        "candidate_scalar_sha256": sha256(CANDIDATE_SCALAR),
        "common_lino_marker_only": True,
        "raw_target_machine_block_added_to_shipping_lino": False,
        "compiler_lowering_below_shared_source_boundary": True,
    }
    (EVIDENCE / "prepared-source.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
