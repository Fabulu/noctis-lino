from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-flag-chain-20260830"
ACCEPTED = EVIDENCE / "accepted"
CANDIDATE = EVIDENCE / "candidate"

ACCEPTED_COMPILER_SOURCE_SHA256 = (
    "be83e4e9160497af7b3272a5f0245ce813a76927ff3807249dce5c0dd5d00e19")
ACCEPTED_COMPILER_SHA256 = (
    "cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87")
CPU_PACK_SHA256 = (
    "1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7")
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
GAME_SOURCE_SHA256 = (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
ACCEPTED_GAME_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")

SCALAR_ISLAND = bytes.fromhex(
    "8b87d42700008b9fc42700003bc30f87300000003bc30f82d8000000"
    "8b87d02700008bd93bc30f87180000003bc30f82c0000000"
    "8b87cc2700008bda3bc30f82b0000000"
    "8b87cc2700008bda3bc30f820a000000be00000000e905000000be01000000"
    "8b87cc2700002bc28987cc270000"
    "8b87d02700008bd93bc30f872e0000003bc30f820c000000"
    "81fe000000000f841a000000"
    "8b87d02700002bc12bc68987d0270000be01000000e915000000"
    "8b87d02700002bc12bc68987d0270000be00000000"
    "8b87d42700002b87c42700002bc68987d4270000")

REACHABLE_CANDIDATE = bytes.fromhex(
    "8b87d4270000"          # mov eax,[srm2]
    "8b9fc4270000"          # mov ebx,[sqcarry]
    "3bc3"                  # cmp eax,ebx
    "7728"                  # ja accepted subtraction
    "0f82de000000"          # jb XRoot restoring next
    "8b87d0270000"          # mov eax,[srm1]
    "8bd9"                  # mov ebx,ecx
    "3bc3"                  # cmp eax,ebx
    "7716"                  # ja accepted subtraction
    "0f82cc000000"          # jb XRoot restoring next
    "8b87cc270000"          # mov eax,[srm0]
    "8bda"                  # mov ebx,edx
    "3bc3"                  # cmp eax,ebx
    "0f82bc000000"          # jb XRoot restoring next
    "8b87cc270000"          # mov eax,[srm0]
    "2bc2"                  # sub eax,edx
    "8987cc270000"          # mov [srm0],eax
    "8b87d0270000"          # mov eax,[srm1]
    "1bc1"                  # sbb eax,ecx
    "8987d0270000"          # mov [srm1],eax
    "be00000000"            # mov esi,0 (preserves middle-borrow CF)
    "83d600"                # adc esi,0
    "8b87d4270000"          # mov eax,[srm2]
    "2b87c4270000"          # sub eax,[sqcarry]
    "2bc6"                  # sub eax,esi
    "8987d4270000"          # mov [srm2],eax
    "8bd9"                  # mov ebx,ecx
    "e961000000")           # jump over equal-footprint padding
CANDIDATE_ISLAND = REACHABLE_CANDIDATE + bytes([0x90]) * (
    len(SCALAR_ISLAND) - len(REACHABLE_CANDIDATE))
assert len(SCALAR_ISLAND) == len(CANDIDATE_ISLAND) == 216


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def format_vector(newline, name, blob):
    lines = [f"\tvector {name} ="]
    for offset in range(0, len(blob), 12):
        values = " ".join(f"{value:02X}h;" for value in blob[offset:offset + 12])
        lines.append("\t  " + values)
    return newline.join(lines)


def transform_fp(source):
    assert sha256(source) == ACCEPTED_FP_SHA256
    old = b"\tA = [srm2]; A - [sqcarry]; A - E; [srm2] = A;\n\n\t( Set the admitted low root bit. )"
    new = b"\tA = [srm2]; A - [sqcarry]; A - E; [srm2] = A;\n\t\"XRoot exact i386m restoring flag chain\"\n\n\t( Set the admitted low root bit. )"
    assert source.count(old) == 1
    result = source.replace(old, new)
    assert result.count(b'"XRoot exact i386m restoring flag chain"') == 1
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
        "\tpp xroot flag marker = { xrootexacti386mrestoringflagchain };\r\n"
        + format_vector(newline, "pp xroot flag scalar", SCALAR_ISLAND)
        + "\r\n" + format_vector(newline, "pp xroot flag exact", CANDIDATE_ISLAND)
        + "\r\n\tvector pp vhgui compose scalar =")
    assert text.count(declaration_old) == 1
    text = text.replace(declaration_old, declaration_new)

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
        "      ? failed -> examine xroot flag marker;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui fixed2x scalar;\r\n"
        "\t[pp exact island candidate] = vector pp vhgui fixed2x exact;\r\n"
        "\t[pp exact island length] = 210;\r\n"
        "\t=> pp exact marked island;\r\n"
        "\t-> note prior code label;\r\n"
        "      \"examine xroot flag marker\"\r\n"
        "\t[target string] = pp xroot flag marker;\r\n"
        "\t=> strcmp;\r\n"
        "      ? failed -> note prior code label;\r\n"
        "\t[pp exact island scalar] = vector pp xroot flag scalar;\r\n"
        "\t[pp exact island candidate] = vector pp xroot flag exact;\r\n"
        "\t[pp exact island length] = 216;\r\n"
        "      (The exact suffix spans internal source labels. Point the existing\r\n"
        "       fail-closed matcher at its fixed start; the full byte comparison\r\n"
        "       remains authoritative and note-prior immediately restores state.)\r\n"
        "\ta = [bpos]; a - 216; [pp prior code label position] = a;\r\n"
        "\t=> pp exact marked island;\r\n"
        "      \"note prior code label\"")
    assert text.count(dispatch_old) == 1
    text = text.replace(dispatch_old, dispatch_new)
    result = text.encode("ascii")
    assert result.count(b"xrootexacti386mrestoringflagchain") == 1
    assert result.count(b"vector pp xroot flag scalar =") == 1
    assert result.count(b"vector pp xroot flag exact =") == 1
    return result


def main():
    accepted_compiler_source = (ACCEPTED / "compiler114m.txt").read_bytes()
    accepted_fp = (ACCEPTED / "fpsoft.txt").read_bytes()
    assert sha256((ACCEPTED / "compiler114m.exe").read_bytes()) == ACCEPTED_COMPILER_SHA256
    assert sha256((ACCEPTED / "i386m.bin").read_bytes()) == CPU_PACK_SHA256
    assert sha256((ACCEPTED / "vhgame.txt").read_bytes()) == GAME_SOURCE_SHA256
    assert sha256((ACCEPTED / "vhgame.exe").read_bytes()) == ACCEPTED_GAME_SHA256
    accepted_game = (ACCEPTED / "vhgame.exe").read_bytes()
    assert accepted_game[0x258C5:0x2599D] == SCALAR_ISLAND

    CANDIDATE.mkdir(parents=True, exist_ok=True)
    (CANDIDATE / "compiler114m.txt").write_bytes(transform_compiler(accepted_compiler_source))
    (CANDIDATE / "fpsoft.txt").write_bytes(transform_fp(accepted_fp))
    for name in ("i386m.bin", "vhgame.txt"):
        shutil.copyfile(ACCEPTED / name, CANDIDATE / name)

    report = {
        "schema": 1,
        "task": 231,
        "status": "prepared",
        "accepted_compiler_source_sha256": ACCEPTED_COMPILER_SOURCE_SHA256,
        "candidate_compiler_source_sha256": sha256(
            (CANDIDATE / "compiler114m.txt").read_bytes()),
        "accepted_fp_sha256": ACCEPTED_FP_SHA256,
        "candidate_fp_sha256": sha256((CANDIDATE / "fpsoft.txt").read_bytes()),
        "scalar_island_bytes": len(SCALAR_ISLAND),
        "candidate_island_bytes": len(CANDIDATE_ISLAND),
        "candidate_reachable_bytes": len(REACHABLE_CANDIDATE),
        "candidate_unreachable_padding_bytes": (
            len(CANDIDATE_ISLAND) - len(REACHABLE_CANDIDATE)),
        "common_lino_marker_only": True,
        "raw_target_machine_block_added_to_shipping_lino": False,
    }
    (EVIDENCE / "prepared-source.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
