import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.idx_extract import detect_p_index_start, load_tables, resolve_number, resolve_singer
from maderpacker.idxwrite import (encode_code, encode_singer, encode_song,
                                  load_template, template_slice, write_index)
from maderpacker.model import PackedSong
from tests.paths import IDX


class TestTemplate(unittest.TestCase):
    def test_load_template_matches_fixture(self):
        self.assertEqual(load_template(), IDX.read_bytes())

    def test_slice_ends_at_first_singer_record(self):
        data = load_template()
        sliced = template_slice(data)
        self.assertEqual(detect_p_index_start(sliced), 8608)
        self.assertEqual(sliced[8608], 0x06)
        self.assertEqual(data[len(sliced)], 0x05)
        self.assertLess(len(sliced), len(data))


class TestEncoders(unittest.TestCase):
    def test_code_shuffle_inverse(self):
        for number in ("000001", "017142", "999999"):
            b = encode_code(number)
            self.assertEqual(len(b), 4)
            self.assertEqual(b[0], 0x09)
            decoded = ((b[1] << 16) | (b[3] << 8)) | b[2]
            self.assertEqual(f"{decoded:06d}", number)

    def test_singer_record_layout(self):
        b = encode_singer("AB", 7)
        self.assertEqual(b[0], 0x05)
        self.assertEqual(b[1], len(b))
        self.assertEqual(b[1], 5 + 2)
        packed, style = struct.unpack_from("<HB", b, 2)
        self.assertEqual(packed, 7)
        self.assertEqual(style, 1)
        self.assertEqual(b[5:], b"AB")

    def test_song_record_layout(self):
        b = encode_song(3, 9, 107518, "'Nyebe'")
        self.assertEqual(b[0], 0x01)
        self.assertEqual(b[1], len(b))
        self.assertEqual(b[1], 12 + 7)
        style, lang, singer_idx, size, pos = struct.unpack_from("<BBHHI", b, 2)
        self.assertEqual((style, lang), (1, 0))
        self.assertEqual((singer_idx, size, pos), (3, 9, 107518))
        self.assertEqual(b[12:], b"'Nyebe'")

    def test_song_sentinel_guards(self):
        with self.assertRaises(ValueError):
            encode_song(0x3FFF + 1, 1, 0, "X")
        with self.assertRaises(ValueError):
            encode_song(0, 0xFFFE, 1, "X")


class TestWriteIndex(unittest.TestCase):
    def _songs(self):
        return [PackedSong("000100", "Zong", 0, 5, 3),
                PackedSong("000050", "apple", 1, 9, 7),
                PackedSong("000075", "Zebra", 1, 20, 2)]

    def test_reparse_written_index(self):
        out = write_index(load_template(), ["Zeta", "alpha"], self._songs())
        self.assertEqual(detect_p_index_start(out), 8608)
        self.assertEqual(out[8608], 0x06)
        self.assertEqual(struct.unpack_from("<HH", out, 28), (2, 3))
        tables = load_tables(out)
        self.assertEqual(tables.singers, ["Zeta", "alpha"])
        got = [(resolve_number(r, tables), r.title, resolve_singer(r, tables),
                r.midi_pos, r.midi_size) for r in tables.songs]
        self.assertEqual(got, [("000100", "Zong", "Zeta", 5, 3),
                               ("000050", "apple", "alpha", 9, 7),
                               ("000075", "Zebra", "alpha", 20, 2)])

    def test_singer_counts_in_records(self):
        out = write_index(load_template(), ["Zeta", "alpha"], self._songs())
        start = len(template_slice(load_template()))
        rec = out[start:]  # first 0x05 record (don't scan for byte 0x05: style ids contain it)
        self.assertEqual(rec[0], 0x05)
        self.assertEqual(rec[1], 5 + len(b"Zeta"))
        packed = struct.unpack_from("<H", rec, 2)[0]
        self.assertEqual(packed & 4095, 1)  # Zeta sings 1 of the 3 songs


if __name__ == "__main__":
    unittest.main()
