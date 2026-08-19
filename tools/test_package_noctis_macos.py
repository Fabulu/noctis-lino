#!/usr/bin/env python3
"""Focused tests for appended-Lino Mach-O normalization."""

from pathlib import Path
import struct
import tempfile
import unittest

from tools.package_noctis_macos import (
    LC_CODE_SIGNATURE,
    LC_SEGMENT_64,
    _linkedit,
    normalize_appended_macho,
    parse_macho,
    validate_signed_appended_macho,
)


class MachONormalizationTests(unittest.TestCase):
    @staticmethod
    def fixture() -> bytes:
        text_command_size = 72 + 80
        linkedit_command_size = 72
        commands_size = text_command_size + linkedit_command_size
        physwsentry = 5120
        app_units = 4
        physappsize = physwsentry + app_units * 4
        data = bytearray(physappsize + 5000)
        struct.pack_into(
            "<8I",
            data,
            0,
            0xFEEDFACF,
            0x01000007,
            3,
            2,
            2,
            commands_size,
            0,
            0,
        )
        struct.pack_into(
            "<II16sQQQQiiII",
            data,
            32,
            LC_SEGMENT_64,
            text_command_size,
            b"__TEXT",
            0x04000000,
            4096,
            0,
            4096,
            5,
            5,
            1,
            0,
        )
        struct.pack_into(
            "<16s16sQQIIIIIIII",
            data,
            32 + 72,
            b"__text",
            b"__TEXT",
            0x04000200,
            256,
            512,
            4,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        linkedit_command = 32 + text_command_size
        struct.pack_into(
            "<II16sQQQQiiII",
            data,
            linkedit_command,
            LC_SEGMENT_64,
            linkedit_command_size,
            b"__LINKEDIT",
            0x04001000,
            4096,
            4096,
            physwsentry - 4096,
            1,
            1,
            0,
            0,
        )
        marker = 1024
        data[marker : marker + 8] = b"LNLMInit"
        data[marker + 8 : marker + 13] = b"test\0"
        struct.pack_into(
            "<14i",
            data,
            marker + 8 + 40,
            2,
            2,
            0,
            physwsentry,
            physappsize,
            2,
            0,
            0,
            0,
            640,
            480,
            0,
            0,
            0,
        )
        data[physwsentry:] = bytes(
            (index * 37 + 11) & 0xFF for index in range(len(data) - physwsentry)
        )
        return bytes(data)

    def test_normalization_changes_only_linkedit_geometry(self) -> None:
        original = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game"
            path.write_bytes(original)
            result = normalize_appended_macho(path)
            normalized = path.read_bytes()

        self.assertEqual(len(normalized), len(original))
        self.assertEqual(result.original_size, len(original))
        self.assertEqual(
            normalized[result.lino.physwsentry :],
            original[result.lino.physwsentry :],
        )
        layout = parse_macho(normalized)
        linkedit = _linkedit(layout)
        self.assertEqual(linkedit.fileoff + linkedit.filesize, len(normalized))
        self.assertGreater(linkedit.vmsize, 4096)

    def test_wrong_runtime_boundary_is_rejected(self) -> None:
        data = bytearray(self.fixture())
        linkedit_command = 32 + 72 + 80
        struct.pack_into("<Q", data, linkedit_command + 48, 1023)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game"
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "runtime boundary"):
                normalize_appended_macho(path)

    def test_signed_validator_preserves_complete_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game"
            path.write_bytes(self.fixture())
            normalization = normalize_appended_macho(path)
            signed = bytearray(path.read_bytes())

            _, _, _, _, ncmds, sizeofcmds, _, _ = struct.unpack_from(
                "<8I", signed, 0
            )
            command_offset = 32 + sizeofcmds
            signature_offset = (len(signed) + 15) & ~15
            signature_size = 64
            signed.extend(b"\0" * (signature_offset - len(signed)))
            signed.extend(bytes(range(signature_size)))
            struct.pack_into("<I", signed, 16, ncmds + 1)
            struct.pack_into("<I", signed, 20, sizeofcmds + 16)
            struct.pack_into(
                "<IIII",
                signed,
                command_offset,
                LC_CODE_SIGNATURE,
                16,
                signature_offset,
                signature_size,
            )
            linkedit = _linkedit(parse_macho(path.read_bytes()))
            new_filesize = len(signed) - linkedit.fileoff
            new_vmsize = (new_filesize + 4095) & ~4095
            struct.pack_into("<Q", signed, linkedit.command_offset + 32, new_vmsize)
            struct.pack_into("<Q", signed, linkedit.command_offset + 48, new_filesize)
            path.write_bytes(signed)

            validate_signed_appended_macho(path, normalization)
            signed[normalization.lino.physwsentry] ^= 1
            path.write_bytes(signed)
            with self.assertRaisesRegex(ValueError, "changed the appended"):
                validate_signed_appended_macho(path, normalization)


if __name__ == "__main__":
    unittest.main()
