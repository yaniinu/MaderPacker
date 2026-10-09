import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.mid_export import extract_midi
from maderpacker.pack import SECTOR, align16, build_block


def midi_like(n: int) -> bytes:
    head = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"
    if n <= len(head):
        return head[:n] if n >= 4 else head + b"\x00" * (n - 4)
    body = bytes((i * 7 + 13) % 256 for i in range(n - len(head)))
    return head + body


class TestAlign(unittest.TestCase):
    def test_align16(self):
        self.assertEqual(align16(0), 0)
        self.assertEqual(align16(1), 16)
        self.assertEqual(align16(16), 16)
        self.assertEqual(align16(17), 32)


class TestBuildBlock(unittest.TestCase):
    def test_roundtrip_sizes(self):
        for n in (4, 5, 16, 17, 100, 2048, 2035, 4096, 4123, 50000):
            midi = midi_like(n)
            block = build_block(midi)
            self.assertEqual(len(block) % SECTOR, 0, f"n={n}")
            self.assertEqual(block[:4], b"MKMD")
            self.assertEqual(block[4], 1)
            out = extract_midi(block, 0, len(block) // SECTOR)
            self.assertEqual(out, midi, f"n={n}")

    def test_header_lengths(self):
        midi = midi_like(4123)
        block = build_block(midi)
        inflated, compressed = struct.unpack_from("<II", block, 5)
        self.assertEqual(inflated, 4123)
        self.assertLessEqual(compressed, inflated + 64)

    def test_deterministic(self):
        midi = midi_like(1234)
        self.assertEqual(build_block(midi), build_block(midi))


if __name__ == "__main__":
    unittest.main()
