from pathlib import Path
import hashlib
import json
import shutil

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fquo-lowering-20260830"
ACCEPTED = EVIDENCE / "accepted"
CANDIDATE = EVIDENCE / "candidate"
ACCEPTED_COMPILER_SOURCE_SHA256 = (
    "c3a185ed4539eff86ea639943e3ea103b9b3065a895ae97bd93de9ff7efb93a0")
ACCEPTED_COMPILER_SHA256 = (
    "facfb8b9373c548c569771978606fcd5d5273760ec7b1e2f0b4ee6bcc30d2e78")
I386M_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")
I386_PACK_SHA256 = (
    "26714bde27cc6c3d91b6be3a19e59f3ef8c856b942b08252d88034cce367786e")
X64_PACK_SHA256 = (
    "786b2cca48708735b1afc360e0b2c147d103d39d94ad8d439a2eec1d694761ab")
ACCEPTED_FPABI_SHA256 = (
    "0c2f2602a82b9619d0bb909098857f804482456c504c2667874046be0598c7fd")
ACCEPTED_FP_SHA256 = (
    "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc")
GAME_SOURCE_SHA256 = (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
ACCEPTED_GAME_SHA256 = (
    "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4")
XSCALAR_QUO_START = 0x2540F
XSCALAR_QUO_END = 0x254FC
PRIOR_LABEL_POSITION = 0x254D0
XFROM_REJECT_START = 0x23907
PREREQUISITE_DISTANCE = XSCALAR_QUO_END - XFROM_REJECT_START
PRIOR_LABEL_DISTANCE = XSCALAR_QUO_END - PRIOR_LABEL_POSITION
ACCEPTED_SCALAR = bytes.fromhex(
    "8B 87 28 26 00 00 89 87 A0 26 00 00 8B 87 2C 26 00 00 "
    "89 87 A4 26 00 00 E8 A3 E3 FF FF 8B 87 78 26 00 00 89 87 "
    "88 26 00 00 8B 87 7C 26 00 00 89 87 8C 26 00 00 8B 87 "
    "80 26 00 00 89 87 90 26 00 00 8B 87 84 26 00 00 89 87 "
    "94 26 00 00 8B 87 20 26 00 00 89 87 A0 26 00 00 8B 87 "
    "24 26 00 00 89 87 A4 26 00 00 E8 56 E3 FF FF 81 BF 8C "
    "26 00 00 00 00 00 00 0F 84 47 00 00 00 81 BF 7C 26 00 "
    "00 00 00 00 00 0F 85 27 00 00 00 8B 87 78 26 00 00 8B "
    "9F 88 26 00 00 33 C3 C1 E0 1F 89 87 24 26 00 00 C7 87 "
    "20 26 00 00 00 00 00 00 BD 65 6E 6F 64 C3 E8 61 F6 FF "
    "FF E8 1C FA FF FF BD 65 6E 6F 64 C3 8B 87 78 26 00 00 "
    "8B 9F 88 26 00 00 33 C3 C1 E0 1F 0D 00 00 F0 7F 89 87 "
    "24 26 00 00 C7 87 20 26 00 00 00 00 00 00 BD 65 6E 6F "
    "64 C3")
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
    shr ecx, 31
    mov dword ptr [edx], ecx
    mov ebp, eax
    xor ebp, ebx
    and ebp, 0x80000000

    mov ecx, ebx
    add ecx, ecx
    cmp ecx, 0xffe00000
    jb denom_finite
    inc dword ptr [edx + 0x30]
    xor ebx, ebx
    jmp denom_ready
  denom_finite:
    shl ebx, 1
    shr ebx, 1
    or ebx, dword ptr [esi + 8]
  denom_ready:

    mov ecx, eax
    add ecx, ecx
    cmp ecx, 0xffe00000
    jb numer_finite
    inc dword ptr [edx + 0x30]
    xor eax, eax
    jmp numer_ready
  numer_finite:
    shl eax, 1
    shr eax, 1
    or eax, dword ptr [esi]
  numer_ready:

    test ebx, ebx
    jz denominator_zero
    test eax, eax
    jz clear_scratch

    fld qword ptr [esi]
    fdiv qword ptr [esi + 8]
    fstp tbyte ptr [edx]
    call unpack
    call 0x24ee6
    ret

  denominator_zero:
    test eax, eax
    jz clear_scratch
    fld qword ptr [esi]
    fstp tbyte ptr [edx]
    call unpack
    xor ebx, ebx
    jmp special_result
  clear_scratch:
    xor ecx, ecx
    mov dword ptr [edx + 4], ecx
    mov dword ptr [edx + 8], ecx
    mov dword ptr [edx + 12], ecx
  special_result:
    xor ecx, ecx
    test ebx, ebx
    jnz write_special
    or ebp, 0x7ff00000
  write_special:
    mov dword ptr [esi], ecx
    mov dword ptr [esi + 4], ebp
    ret

  unpack:
    movzx ecx, word ptr [edx + 8]
    mov ebx, dword ptr [edx]
    mov eax, dword ptr [edx + 4]
    mov dword ptr [edx + 12], ebx
    mov dword ptr [edx + 8], eax
    mov ebx, ecx
    shr ecx, 15
    mov dword ptr [edx], ecx
    and ebx, 0x7fff
    mov dword ptr [edx + 4], ebx
    ret
"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def assemble_candidate():
    assembler = Ks(KS_ARCH_X86, KS_MODE_32)
    encoded, count = assembler.asm(CANDIDATE_ASSEMBLY, addr=XSCALAR_QUO_START)
    result = bytes(encoded)
    assert count > 0 and len(result) == 190
    result += b"\x90" * (len(ACCEPTED_SCALAR) - len(result))
    assert len(result) == len(ACCEPTED_SCALAR) == 237
    decoded = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(
        result, XSCALAR_QUO_START))
    assert decoded[-1].address + decoded[-1].size == XSCALAR_QUO_END
    assert decoded[-48].mnemonic == "ret"
    assert all(item.mnemonic == "nop" for item in decoded[-47:])
    return result


CANDIDATE_SCALAR = assemble_candidate()
assert sha256(ACCEPTED_SCALAR) == (
    "c3e63a988112e10cd0e1ea9d7af0bacec41cce7d438fcf5dfc34678ea29246e9")
assert sha256(CANDIDATE_SCALAR) == (
    "91df2edbd9d166d7dd4be3081f9700af117b306f88007652a34f12f452dd5e52")
assert len(XREJ_PREREQUISITE) == 42
assert sha256(XREJ_PREREQUISITE) == (
    "be3b290cdba513684af52fbca2b7109e618b2ec45cb180a65c5fb3ba87cc8f94")
assert PREREQUISITE_DISTANCE == 0x1BF5
assert PRIOR_LABEL_DISTANCE == 44


def format_vector(newline, name, blob):
    values = " ".join(f"{value:02X}h;" for value in blob)
    return f"\tvector {name} =\r\n\t  {values}".replace("\r\n", newline)


def transform_fp(source):
    assert sha256(source) == ACCEPTED_FP_SHA256
    old = b'\t[FA0] = 0;\n\tend;\n\n"XScalarAdd"'
    new = (b'\t[FA0] = 0;\n\tend;\n'
           b'\t"XSQ exact i386m native quo"\n\n"XScalarAdd"')
    assert source.count(old) == 1
    result = source.replace(old, new)
    assert result.count(b'"XSQ exact i386m native quo"') == 1
    return result


def transform_compiler(source):
    assert sha256(source) == ACCEPTED_COMPILER_SOURCE_SHA256
    text = source.decode("ascii")
    newline = "\r\n"
    assert text.count(newline) == text.count("\n")

    marker_old = (
        "\tpp xsm fmul marker = { xsmexacti386mnativefmul };\r\n")
    marker_new = marker_old + (
        "\tpp xsq quo marker = { xsqexacti386mnativequo };\r\n")
    assert text.count(marker_old) == 1
    text = text.replace(marker_old, marker_new)

    vector_point = "\tvector pp vhgui compose scalar ="
    vector_new = (
        format_vector(newline, "pp xsq quo prerequisite", XREJ_PREREQUISITE)
        + "\r\n" + format_vector(newline, "pp xsq quo scalar", ACCEPTED_SCALAR)
        + "\r\n" + format_vector(newline, "pp xsq quo exact", CANDIDATE_SCALAR)
        + "\r\n" + vector_point)
    assert text.count(vector_point) == 1
    text = text.replace(vector_point, vector_new)

    workspace_old = (
        "\tpp exact island length = 1; (same-size marked exact island length)\r\n")
    workspace_new = workspace_old + (
        "\tpp exact prior label distance = 1; (marker to preceding source label bytes)\r\n")
    assert text.count(workspace_old) == 1
    text = text.replace(workspace_old, workspace_new)

    compose_old = (
        "\t[pp exact island length] = 168;\r\n"
        "\t=> pp exact marked island;")
    compose_new = (
        "\t[pp exact island length] = 168;\r\n"
        "\t[pp exact prior label distance] = 168;\r\n"
        "\t=> pp exact marked island;")
    assert text.count(compose_old) == 1
    text = text.replace(compose_old, compose_new)

    fixed_old = (
        "\t[pp exact island length] = 210;\r\n"
        "\t=> pp exact marked island;")
    fixed_new = (
        "\t[pp exact island length] = 210;\r\n"
        "\t[pp exact prior label distance] = 210;\r\n"
        "\t=> pp exact marked island;")
    assert text.count(fixed_old) == 1
    text = text.replace(fixed_old, fixed_new)

    fmul_old = (
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
    fmul_new = (
        "      \"examine xsm fmul marker\"\r\n"
        "\t[target string] = pp xsm fmul marker;\r\n"
        "\t=> strcmp;\r\n"
        "      ? failed -> examine xsq quo marker;\r\n"
        "\t[pp exact prerequisite scalar] = vector pp xsm fmul prerequisite;\r\n"
        "\t[pp exact prerequisite length] = 42;\r\n"
        "\t[pp exact prerequisite distance] = 7523;\r\n"
        "\t[pp exact island scalar] = vector pp xsm fmul scalar;\r\n"
        "\t[pp exact island candidate] = vector pp xsm fmul exact;\r\n"
        "\t[pp exact island length] = 122;\r\n"
        "\t[pp exact prior label distance] = 122;\r\n"
        "\t=> pp exact marked island;\r\n"
        "\t-> note prior code label;\r\n"
        "      \"examine xsq quo marker\"\r\n"
        "\t[target string] = pp xsq quo marker;\r\n"
        "\t=> strcmp;\r\n"
        "      ? failed -> note prior code label;\r\n"
        "\t[pp exact prerequisite scalar] = vector pp xsq quo prerequisite;\r\n"
        "\t[pp exact prerequisite length] = 42;\r\n"
        "\t[pp exact prerequisite distance] = 7157;\r\n"
        "\t[pp exact island scalar] = vector pp xsq quo scalar;\r\n"
        "\t[pp exact island candidate] = vector pp xsq quo exact;\r\n"
        "\t[pp exact island length] = 237;\r\n"
        "\t[pp exact prior label distance] = 44;\r\n"
        "\t=> pp exact marked island;\r\n"
        "      \"note prior code label\"")
    assert text.count(fmul_old) == 1
    text = text.replace(fmul_old, fmul_new)

    matcher_old = (
        "\ta = [bpos];\r\n"
        "\ta - [pp prior code label position];\r\n"
        "      ? a != [pp exact island length] -> pp exact marked island restore;\r\n")
    matcher_new = (
        "\ta = [bpos];\r\n"
        "\ta - [pp prior code label position];\r\n"
        "      ? a != [pp exact prior label distance] -> pp exact marked island restore;\r\n")
    assert text.count(matcher_old) == 1
    text = text.replace(matcher_old, matcher_new)

    result = text.encode("ascii")
    assert result.count(b"xsqexacti386mnativequo") == 1
    assert result.count(b"vector pp xsq quo prerequisite =") == 1
    assert result.count(b"vector pp xsq quo scalar =") == 1
    assert result.count(b"vector pp xsq quo exact =") == 1
    assert result.count(b"pp exact prior label distance") == 6
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
    assert accepted_game[XSCALAR_QUO_START:XSCALAR_QUO_END] == ACCEPTED_SCALAR
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
        "task": 237,
        "status": "prepared",
        "accepted_compiler_source_sha256": ACCEPTED_COMPILER_SOURCE_SHA256,
        "candidate_compiler_source_sha256": sha256(
            (CANDIDATE / "compiler114m.txt").read_bytes()),
        "accepted_fp_sha256": ACCEPTED_FP_SHA256,
        "candidate_fp_sha256": sha256((CANDIDATE / "fpsoft.txt").read_bytes()),
        "accepted_game_sha256": ACCEPTED_GAME_SHA256,
        "accepted_scalar_bytes": len(ACCEPTED_SCALAR),
        "candidate_scalar_bytes": len(CANDIDATE_SCALAR),
        "candidate_instruction_bytes_before_padding": 190,
        "candidate_nop_padding_bytes": 47,
        "xrej_prerequisite_bytes": len(XREJ_PREREQUISITE),
        "xrej_prerequisite_distance": PREREQUISITE_DISTANCE,
        "prior_internal_label_distance": PRIOR_LABEL_DISTANCE,
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
