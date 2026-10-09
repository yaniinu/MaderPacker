import unittest
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.idx_extract import IdxFormatError, read_header, parse_record_at
from tests.paths import IDX, GROUND

DATA = IDX.read_bytes()


class TestHeader(unittest.TestCase):
    def test_header_fixture_u32s(self):
        h = read_header(DATA)
        self.assertEqual([h[i] for i in range(8)],
                         [0, 55, 207, 389, 317841, 8348, 8478, 0xBB7E3DB3])

    def test_short_file_raises(self):
        with self.assertRaises(IdxFormatError):
            read_header(b"\x00" * 8)


class TestRecord(unittest.TestCase):
    def test_nyebe_record(self):
        rec, nxt = parse_record_at(DATA, 326897)
        self.assertEqual(rec.title, "'Nyebe'")
        self.assertEqual(rec.length, 19)
        self.assertEqual((rec.style, rec.lang_id, rec.lang_type), (1, 0, 1))
        self.assertEqual(rec.singer_idx, 12862)
        self.assertEqual((rec.midi_size, rec.midi_pos), (9, 107518))
        self.assertEqual(nxt, 326916)

    def test_pag_pwede_record(self):
        rec, nxt = parse_record_at(DATA, 326916)
        self.assertEqual(rec.title, "'Pag Pwede Na Ang Puso Mo")
        self.assertEqual(rec.singer_idx, 14589)
        self.assertEqual(rec.midi_pos, 66120)
        self.assertEqual(nxt, 326953)

    def test_summoning_eru_record(self):
        rec, nxt = parse_record_at(DATA, 1371264)
        self.assertEqual(rec.title, "Summoning Eru")
        self.assertEqual(rec.singer_idx, 7513)
        self.assertEqual(nxt, 1371289)

    def test_wrong_type_raises(self):
        with self.assertRaises(IdxFormatError):
            parse_record_at(DATA, 326909)  # mid-record (title bytes), not a type byte

    def test_truncated_raises(self):
        with self.assertRaises(IdxFormatError):
            parse_record_at(DATA, len(DATA) - 4)


class TestFullSection(unittest.TestCase):
    def test_all_titles_parse(self):
        from maderpacker.idx_extract import parse_titles
        recs = parse_titles(DATA)
        self.assertEqual(len(recs), 47998)
        self.assertEqual(recs[0].title, "#9 Dream")
        self.assertEqual(recs[-1].title, "`Yun Ka")
        self.assertTrue(all(r.title for r in recs))

    def test_unknown_layout_fails_loudly(self):
        from maderpacker.idx_extract import parse_titles
        with self.assertRaises(IdxFormatError):
            parse_titles(b"\x00" * 4096)


class TestResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from maderpacker.idx_extract import load_tables
        cls.tables = load_tables(DATA)
        cls.by_title = {}
        with open(GROUND, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cls.by_title[row["title"]] = row

    def test_all_ground_truth_numbers(self):
        from maderpacker.idx_extract import parse_titles, resolve_number
        recs = [r for r in parse_titles(DATA) if r.title in self.by_title]
        self.assertEqual(len(recs), len(self.by_title))
        for rec in recs:
            self.assertEqual(resolve_number(rec, self.tables),
                             self.by_title[rec.title]["number"])

    def test_all_ground_truth_singers(self):
        from maderpacker.idx_extract import parse_titles, resolve_singer
        recs = [r for r in parse_titles(DATA) if r.title in self.by_title]
        self.assertEqual(len(recs), len(self.by_title))
        for rec in recs:
            self.assertEqual(resolve_singer(rec, self.tables),
                             self.by_title[rec.title]["singer"])

    def test_gummy_singer(self):
        from maderpacker.idx_extract import parse_titles, resolve_singer
        rec = next(r for r in parse_titles(DATA)
                   if r.title == "You're My Everything(English Version)")
        self.assertEqual(resolve_singer(rec, self.tables), "Gummy")


if __name__ == "__main__":
    unittest.main()
