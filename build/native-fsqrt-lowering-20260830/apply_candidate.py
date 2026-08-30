from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fsqrt-lowering-20260830"
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
ACCEPTED_FP_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")
GAME_SOURCE_SHA256 = (
    "f1af20ebd55b80e3a1439b0e30f1bb4e0bdcc8e00b7aced1a7b34d7395d3dc25")
ACCEPTED_GAME_SHA256 = (
    "e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0")
SCALAR_ISLAND = bytes.fromhex(
    "E825000000 E815F8FFFF BD656E6F64 C3")
CANDIDATE_ISLAND = bytes.fromhex(
    "DD8720260000 D9FA DD9F20260000 C3 90")
XSCALAR_CONTEXT = bytes.fromhex(
    "8B 87 20 26 00 00 89 87 A0 26 00 00 "
    "8B 87 24 26 00 00 89 87 A4 26 00 00 "
    "E8 48 E1 FF FF "
    "81 BF 7C 26 00 00 00 00 00 00 0F 84 40 00 00 00 "
    "81 BF 78 26 00 00 00 00 00 00 0F 84 20 00 00 00 "
    "FF 87 A8 26 00 00 "
    "C7 87 20 26 00 00 00 00 00 00 "
    "C7 87 24 26 00 00 00 00 00 00 "
    "BD 65 6E 6F 64 C3 "
    "E8 25 00 00 00 E8 15 F8 FF FF BD 65 6E 6F 64 C3")
assert len(SCALAR_ISLAND) == len(CANDIDATE_ISLAND) == 16
assert len(XSCALAR_CONTEXT) == 109
assert XSCALAR_CONTEXT.endswith(SCALAR_ISLAND)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def format_vector(newline, name, blob):
    values = " ".join(f"{value:02X}h;" for value in blob)
    return f"\tvector {name} =\r\n\t  {values}".replace("\r\n", newline)


def transform_fp(source):
    assert sha256(source) == ACCEPTED_FP_SHA256
    old = b'\t=> XRootCore;\n\t=> XToF64;\n\tend;\n    "XSS zero"'
    new = (b'\t=> XRootCore;\n\t=> XToF64;\n\tend;\n'
           b'\t"XSS exact i386m native fsqrt"\n'
           b'    "XSS zero"')
    assert source.count(old) == 1
    result = source.replace(old, new)
    assert result.count(b'"XSS exact i386m native fsqrt"') == 1
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
        "\tpp xss fsqrt marker = { xssexacti386mnativefsqrt };\r\n"
        + format_vector(newline, "pp xss fsqrt context", XSCALAR_CONTEXT)
        + "\r\n" + format_vector(newline, "pp xss fsqrt scalar", SCALAR_ISLAND)
        + "\r\n" + format_vector(newline, "pp xss fsqrt exact", CANDIDATE_ISLAND)
        + "\r\n\tvector pp vhgui compose scalar =")
    assert text.count(declaration_old) == 1
    text = text.replace(declaration_old, declaration_new)

    workspace_old = (
        "\tpp exact island scalar = 1; (accepted byte vector for marked exact island)\r\n"
        "\tpp exact island candidate = 1; (replacement byte vector for marked exact island)\r\n"
        "\tpp exact island length = 1; (same-size marked exact island length)\r\n")
    workspace_new = (
        workspace_old
        + "\tpp exact context scalar = 1; (accepted surrounding byte vector)\r\n"
        + "\tpp exact context length = 1; (zero disables surrounding context gate)\r\n")
    assert text.count(workspace_old) == 1
    text = text.replace(workspace_old, workspace_new)

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
        "      ? failed -> examine xss fsqrt marker;\r\n"
        "\t[pp exact context length] = 0;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui fixed2x scalar;\r\n"
        "\t[pp exact island candidate] = vector pp vhgui fixed2x exact;\r\n"
        "\t[pp exact island length] = 210;\r\n"
        "\t=> pp exact marked island;\r\n"
        "\t-> note prior code label;\r\n"
        "      \"examine xss fsqrt marker\"\r\n"
        "\t[target string] = pp xss fsqrt marker;\r\n"
        "\t=> strcmp;\r\n"
        "      ? failed -> note prior code label;\r\n"
        "\t[pp exact context scalar] = vector pp xss fsqrt context;\r\n"
        "\t[pp exact context length] = 109;\r\n"
        "\t[pp exact island scalar] = vector pp xss fsqrt scalar;\r\n"
        "\t[pp exact island candidate] = vector pp xss fsqrt exact;\r\n"
        "\t[pp exact island length] = 16;\r\n"
        "\t=> pp exact marked island;\r\n"
        "      \"note prior code label\"")
    assert text.count(dispatch_old) == 1
    text = text.replace(dispatch_old, dispatch_new)

    compose_old = (
        "      ? failed -> examine vhgui fixed2x marker;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui compose scalar;\r\n")
    compose_new = (
        "      ? failed -> examine vhgui fixed2x marker;\r\n"
        "\t[pp exact context length] = 0;\r\n"
        "\t[pp exact island scalar] = vector pp vhgui compose scalar;\r\n")
    assert text.count(compose_old) == 1
    text = text.replace(compose_old, compose_new)

    matcher_old = (
        "\ta = [bpos];\r\n"
        "\ta - [pp prior code label position];\r\n"
        "      ? a != [pp exact island length] -> pp exact marked island restore;\r\n")
    matcher_new = (
        "\ta = [pp exact context length];\r\n"
        "      ? a = 0 -> pp exact marked island local gate;\r\n"
        "      ? [bbss] < a -> pp exact marked island restore;\r\n"
        "\td = [bbss];\r\n"
        "\td - a;\r\n"
        "\t[target string] = [pp exact context scalar];\r\n"
        "\te = [target string];\r\n"
        "\tc = [pp exact context length];\r\n"
        "\t[pb stream] = bins;\r\n"
        "      \"pp exact marked context compare\"\r\n"
        "\t[pb offset] = d;\r\n"
        "\t=> get progressive byte;\r\n"
        "\ta = [pb bvalue];\r\n"
        "      ? a != [e] -> pp exact marked island restore;\r\n"
        "\td+;\r\n"
        "\te+;\r\n"
        "\tc ^ pp exact marked context compare;\r\n"
        "      \"pp exact marked island local gate\"\r\n"
        "\ta = [bpos];\r\n"
        "\ta - [pp prior code label position];\r\n"
        "      ? a != [pp exact island length] -> pp exact marked island restore;\r\n")
    assert text.count(matcher_old) == 1
    text = text.replace(matcher_old, matcher_new)

    result = text.encode("ascii")
    assert result.count(b"xssexacti386mnativefsqrt") == 1
    assert result.count(b"vector pp xss fsqrt context =") == 1
    assert result.count(b"vector pp xss fsqrt scalar =") == 1
    assert result.count(b"vector pp xss fsqrt exact =") == 1
    assert result.count(b'"pp exact marked context compare"') == 1
    return result


def snapshot():
    named = {
        "compiler114m.txt": ROOT / "main/lib/gen/compiler114m.txt",
        "compiler114m.exe": ROOT / "main/lib/gen/compiler114m.exe",
        "i386m.bin": ROOT / "main/cpu/i386m.bin",
        "i386.bin": ROOT / "main/cpu/i386.bin",
        "x64.bin": ROOT / "main/cpu/x64.bin",
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
    assert accepted_game[0x2566A:0x256D7] == XSCALAR_CONTEXT
    assert accepted_game[0x256C7:0x256D7] == SCALAR_ISLAND
    CANDIDATE.mkdir(parents=True, exist_ok=True)
    (CANDIDATE / "compiler114m.txt").write_bytes(
        transform_compiler(accepted_compiler))
    (CANDIDATE / "fpsoft.txt").write_bytes(transform_fp(accepted_fp))
    for name in ("i386m.bin", "i386.bin", "x64.bin", "vhgame.txt"):
        shutil.copyfile(ACCEPTED / name, CANDIDATE / name)
    report = {
        "schema": 1,
        "task": 233,
        "status": "prepared",
        "accepted_compiler_source_sha256": ACCEPTED_COMPILER_SOURCE_SHA256,
        "candidate_compiler_source_sha256": sha256(
            (CANDIDATE / "compiler114m.txt").read_bytes()),
        "accepted_fp_sha256": ACCEPTED_FP_SHA256,
        "candidate_fp_sha256": sha256((CANDIDATE / "fpsoft.txt").read_bytes()),
        "accepted_game_sha256": ACCEPTED_GAME_SHA256,
        "scalar_island_bytes": len(SCALAR_ISLAND),
        "candidate_island_bytes": len(CANDIDATE_ISLAND),
        "accepted_context_bytes": len(XSCALAR_CONTEXT),
        "accepted_context_binds_fa_displacement": True,
        "common_lino_marker_only": True,
        "raw_target_machine_block_added_to_shipping_lino": False,
        "compiler_lowering_below_shared_source_boundary": True,
    }
    (EVIDENCE / "prepared-source.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
