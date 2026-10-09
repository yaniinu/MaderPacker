import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.idx_extract import _walk_index, detect_p_index_start, load_tables
from tests.paths import IDX, BLOB

DATA = IDX.read_bytes()
BLOB_DATA = BLOB.read_bytes() if BLOB.exists() else b""


class TestIdxGrammar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.langs, cls.styles, cls.singers_raw, cls.songs, cls.codes,
         _, cls.encodings) = _walk_index(DATA)

    def test_census(self):
        self.assertEqual(len(self.langs), 15)
        self.assertEqual(len(self.styles), 17)
        self.assertEqual(len(self.singers_raw), 15795)
        self.assertEqual(len(self.songs), 47998)
        self.assertEqual(len(self.codes), 47998)

    def test_index_start_and_first_record_byte(self):
        self.assertEqual(detect_p_index_start(DATA), 8608)
        self.assertEqual(DATA[8608], 0x06)

    def test_language_zero_is_opm_cp1252(self):
        self.assertEqual(self.langs[0], "OPM")
        self.assertEqual(self.encodings[0], "cp1252")

    def test_style_table(self):
        self.assertEqual(self.styles, {
            1: "Pop", 2: "Rock", 3: "Ballad", 4: "Jazz", 5: "Disco",
            6: "Country", 7: "Folk", 8: "R&B", 9: "OPM", 10: "Remix",
            11: "Gospel", 12: "Electronic", 13: "Latin", 14: "Bollywood",
            15: "TV movie theme", 16: "Game", 17: "Other"})

    def test_all_songs_style1_lang0(self):
        self.assertTrue(all(s.style == 1 and s.lang_id == 0 and s.lang_type == 1
                            for s in self.songs))

    def test_header_counts_and_marker(self):
        self.assertEqual(struct.unpack_from("<HH", DATA, 28), (15795, 47998))
        self.assertEqual(struct.unpack_from("<I", DATA, 52)[0], 8608)
        self.assertEqual(struct.unpack_from("<I", DATA, 56)[0], 0x0DA10159)

    def test_titles_sorted_by_upper(self):
        keys = [s.title.upper() for s in self.songs]
        bad = [j for j in range(len(keys) - 1) if keys[j] > keys[j + 1]]
        self.assertEqual(bad, [])

    def test_singers_sorted_by_upper(self):
        names = [n.decode("latin-1") for (_, _, _, n) in self.singers_raw]
        keys = [n.upper() for n in names]
        bad = [j for j in range(len(keys) - 1) if keys[j] > keys[j + 1]]
        self.assertEqual(bad, [])


@unittest.skipUnless(BLOB.exists(), "large blob fixture not present")
class TestBlobChain(unittest.TestCase):
    def test_blocks_chain_exactly(self):
        tables = load_tables(DATA)
        recs = sorted(tables.songs, key=lambda r: r.midi_pos)[:2000]
        for rec in recs:
            off = rec.midi_pos * 2048
            end = off + rec.midi_size * 2048
            self.assertEqual(BLOB_DATA[off:off + 4], b"MKMD")
            if end + 4 <= len(BLOB_DATA):
                self.assertEqual(BLOB_DATA[end:end + 4], b"MKMD")


if __name__ == "__main__":
    unittest.main()
