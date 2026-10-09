import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.model import ValidatedSong
from maderpacker.validate import (assign_numbers, field_reason,
                                  overlap_summary, parse_name, scan_folder)


class TestParseName(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_name("012345 - Song - Singer.mid"),
                         ("012345", "Song", "Singer"))

    def test_title_keeps_inner_dashes_last_segment_is_singer(self):
        self.assertEqual(parse_name("000123 - A - B - C.mid"),
                         ("000123", "A - B", "C"))

    def test_five_digits_rejected(self):
        self.assertIsNone(parse_name("12345 - Song - Singer.mid"))

    def test_seven_digits_rejected(self):
        self.assertIsNone(parse_name("0123456 - Song - Singer.mid"))

    def test_missing_number_rejected(self):
        self.assertIsNone(parse_name("Song - Singer.mid"))

    def test_wrong_extension_rejected(self):
        self.assertIsNone(parse_name("012345 - Song - Singer.txt"))

    def test_uppercase_extension_accepted(self):
        self.assertEqual(parse_name("012345 - Song - SINGER.MID")[0], "012345")

    def test_kar_extension_parsed(self):
        self.assertEqual(parse_name("012345 - Song - Singer.kar"),
                         ("012345", "Song", "Singer"))

    def test_kar_uppercase_extension_parsed(self):
        self.assertEqual(parse_name("012345 - Song - Singer.KAR")[0], "012345")


class TestScanFolder(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="mv_scan_"))

    def _file(self, name, data=b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_valid_row(self):
        self._file("000001 - Song - Singer.mid")
        rows = scan_folder(self.dir)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertTrue(r.ok, r.reason)
        self.assertEqual((r.number, r.title, r.singer), ("000001", "Song", "Singer"))

    def test_non_mid_files_ignored(self):
        self._file("000001 - Song - Singer.mid")
        (self.dir / "readme.txt").write_text("x")
        (self.dir / "packed").mkdir()
        self.assertEqual(len(scan_folder(self.dir)), 1)

    def test_bad_filename_rejected_with_reason(self):
        self._file("oops.mid")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].ok)
        self.assertIn("6 digits", rows[0].reason)

    def test_duplicate_numbers_all_rejected(self):
        self._file("000001 - A - X.mid")
        self._file("000001 - B - Y.mid")
        rows = scan_folder(self.dir)
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertFalse(r.ok)
            self.assertIn("duplicate number 000001", r.reason)

    def test_missing_mthd_rejected(self):
        self._file("000001 - Song - Singer.mid", data=b"RIFFxxxx")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].ok)
        self.assertIn("MThd", rows[0].reason)

    def test_non_cp1252_title_rejected(self):
        self._file("000001 - \u6700\u5f31 - Singer.mid")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].ok)
        self.assertIn("cp1252", rows[0].reason)

    def test_whitespace_title_rejected(self):
        self._file("000001 -  Song  - Singer.mid")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].ok)
        self.assertIn("whitespace", rows[0].reason)

    def test_overlong_title_rejected(self):
        # full filename would exceed MAX_PATH; field_reason is the pure seam
        self.assertIn("too long", field_reason("\u00e9" * 244, "Singer"))

    def test_overlong_singer_rejected(self):
        self.assertIn("singer too long", field_reason("Song", "\u00e9" * 251))

    def test_field_reason_ok(self):
        self.assertEqual(field_reason("Song", "Singer"), "")


class TestKarScanFolder(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="mv_kar_"))

    def _file(self, name, data=b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_kar_valid_row(self):
        self._file("000001 - Song - Singer.kar")
        rows = scan_folder(self.dir)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertTrue(r.ok, r.reason)
        self.assertEqual((r.number, r.title, r.singer), ("000001", "Song", "Singer"))

    def test_kar_bad_filename_rejected(self):
        self._file("oops.kar")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].ok)
        self.assertIn("6 digits", rows[0].reason)
        self.assertIn(".kar", rows[0].reason)

    def test_kar_missing_mthd_rejected(self):
        self._file("000001 - Song - Singer.kar", data=b"RIFFxxxx")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].ok)
        self.assertIn("MThd", rows[0].reason)

    def test_mid_kar_same_number_duplicates(self):
        self._file("000001 - A - X.mid")
        self._file("000001 - B - Y.kar")
        rows = scan_folder(self.dir)
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertFalse(r.ok)
            self.assertIn("duplicate number 000001", r.reason)

    def test_unrelated_files_still_ignored(self):
        self._file("000001 - Song - Singer.kar")
        (self.dir / "readme.txt").write_text("x")
        (self.dir / "000002 - Song - Singer.mp3").write_bytes(b"x")
        self.assertEqual(len(scan_folder(self.dir)), 1)


class TestMultiFolderScan(unittest.TestCase):
    def setUp(self):
        self.a = pathlib.Path(tempfile.mkdtemp(prefix="mv_mf_a_"))
        self.b = pathlib.Path(tempfile.mkdtemp(prefix="mv_mf_b_"))

    def _file(self, folder, name,
              data=b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"):
        p = folder / name
        p.write_bytes(data)
        return p

    def test_rows_from_both_folders_in_order(self):
        self._file(self.a, "000002 - B - X.mid")
        self._file(self.a, "000001 - A - X.mid")
        self._file(self.b, "000003 - C - X.mid")
        rows = scan_folder([self.a, self.b])
        self.assertEqual([r.number for r in rows],
                         ["000001", "000002", "000003"])
        self.assertTrue(all(r.ok for r in rows))

    def test_duplicate_across_folders_both_rejected(self):
        self._file(self.a, "000001 - A - X.mid")
        self._file(self.b, "000001 - B - Y.mid")
        rows = scan_folder([self.a, self.b])
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertFalse(r.ok)
            self.assertIn("duplicate number 000001", r.reason)

    def test_folder_order_follows_argument_order(self):
        self._file(self.b, "000005 - E - X.mid")
        self._file(self.a, "000009 - N - X.mid")
        rows = scan_folder([self.b, self.a])
        self.assertEqual([r.number for r in rows], ["000005", "000009"])

    def test_single_path_accepted(self):
        self._file(self.a, "000007 - G - X.mid")
        rows = scan_folder(self.a)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].ok)

    def test_empty_list(self):
        self.assertEqual(scan_folder([]), [])


class TestNeedsNumber(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="mv_need_"))

    def _file(self, name,
              data=b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_missing_number_needs(self):
        self._file("Song - Singer.mid")
        rows = scan_folder(self.dir)
        r = rows[0]
        self.assertTrue(r.needs_number)
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "needs number")
        self.assertEqual((r.title, r.singer), ("Song", "Singer"))
        self.assertEqual(r.number, "")

    def test_five_digit_number_needs(self):
        self._file("12345 - Song - Singer.kar")
        rows = scan_folder(self.dir)
        self.assertTrue(rows[0].needs_number)
        self.assertEqual((rows[0].title, rows[0].singer), ("Song", "Singer"))

    def test_seven_digit_number_needs(self):
        self._file("1234567 - Song - Singer.mid")
        rows = scan_folder(self.dir)
        self.assertTrue(rows[0].needs_number)

    def test_singer_taken_from_last_segment(self):
        self._file("Some - Long - Title - Singer.mid")
        rows = scan_folder(self.dir)
        self.assertTrue(rows[0].needs_number)
        self.assertEqual((rows[0].title, rows[0].singer),
                         ("Some - Long - Title", "Singer"))

    def test_no_singer_stays_rejected(self):
        self._file("justtitle.mid")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].ok)
        self.assertFalse(rows[0].needs_number)
        self.assertIn("6 digits", rows[0].reason)

    def test_bad_encoding_never_needs(self):
        self._file("Song - \u6700\u5f31.mid")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].needs_number)
        self.assertIn("cp1252", rows[0].reason)

    def test_missing_mthd_never_needs(self):
        self._file("Song - Singer.mid", data=b"RIFFnope")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].needs_number)
        self.assertIn("MThd", rows[0].reason)

    def test_six_digit_duplicate_stays_rejected_not_needs(self):
        self._file("000001 - A - X.mid")
        self._file("000001 - B - Y.mid")
        rows = scan_folder(self.dir)
        for r in rows:
            self.assertFalse(r.needs_number)
            self.assertIn("duplicate number", r.reason)

    def test_whitespace_title_never_needs(self):
        self._file("  Song  - Singer.mid")
        rows = scan_folder(self.dir)
        self.assertFalse(rows[0].needs_number)
        self.assertIn("whitespace", rows[0].reason)


class TestAssignNumbers(unittest.TestCase):
    @staticmethod
    def _ok(number, title="t", singer="s"):
        return ValidatedSong(number, title, singer, pathlib.Path(f"{number}.mid"),
                             True, "")

    @staticmethod
    def _need(title="t", singer="s"):
        return ValidatedSong("", title, singer, pathlib.Path("x.mid"),
                             False, "needs number", True)

    @staticmethod
    def _rej(number):
        return ValidatedSong(number, "t", "s", pathlib.Path(f"{number}.mid"),
                             False, "duplicate number")

    def test_assigns_from_max_plus_one_in_row_order(self):
        rows = [self._ok("000005"), self._need(title="A"), self._need(title="B")]
        out = assign_numbers(rows)
        self.assertEqual([r.number for r in out], ["000005", "000006", "000007"])
        self.assertTrue(all(r.ok for r in out))
        self.assertTrue(all(not r.needs_number for r in out))
        self.assertTrue(all(r.reason == "" for r in out[1:]))

    def test_never_collides_with_rejected_rows(self):
        rows = [self._rej("000100"), self._need()]
        out = assign_numbers(rows)
        self.assertEqual(out[1].number, "000101")

    def test_base_is_one_when_no_numbers_exist(self):
        out = assign_numbers([self._need()])
        self.assertEqual(out[0].number, "000001")

    def test_fills_between_never(self):
        rows = [self._ok("000001"), self._ok("000009"), self._need()]
        out = assign_numbers(rows)
        self.assertEqual(out[2].number, "000010")

    def test_no_needs_is_noop(self):
        rows = [self._ok("000001")]
        out = assign_numbers(rows)
        self.assertEqual(out, rows)
        self.assertIs(out[0], rows[0])

    def test_input_not_mutated(self):
        rows = [self._ok("000001"), self._need()]
        assign_numbers(rows)
        self.assertEqual(rows[1].number, "")
        self.assertTrue(rows[1].needs_number)

    def test_overflow_rejected(self):
        rows = [self._ok("999999"), self._need()]
        out = assign_numbers(rows)
        self.assertFalse(out[1].ok)
        self.assertFalse(out[1].needs_number)
        self.assertEqual(out[1].reason, "no free 6-digit numbers")

    def test_assigned_rows_unique(self):
        rows = [self._ok("000002"), self._need(title="A"),
                self._need(title="B"), self._need(title="C")]
        out = assign_numbers(rows)
        nums = [r.number for r in out if r.ok]
        self.assertEqual(len(nums), len(set(nums)))


class TestOverlapSummary(unittest.TestCase):
    @staticmethod
    def _row(number):
        return ValidatedSong(number, "t", "s", pathlib.Path(f"{number or 'x'}.mid"),
                             number != "", "" if number else "needs number",
                             number == "")

    def test_empty_when_clean(self):
        rows = [self._row("000001"), ValidatedSong("", "t", "s",
                pathlib.Path("y.mid"), False, "needs number", True)]
        self.assertEqual(overlap_summary(rows), "")

    def test_lists_each_duplicate_sorted(self):
        rows = [self._row("000042"), self._row("000042"),
                self._row("000001"), self._row("000001")]
        self.assertEqual(overlap_summary(rows),
                         "overlapping numbers: 000001 (2 files), 000042 (2 files)")

    def test_includes_auto_assigned_count(self):
        rows = [self._row("000001")]
        self.assertEqual(overlap_summary(rows, auto_assigned=3),
                         "3 auto-assigned")

    def test_dups_plus_auto_assigned(self):
        rows = [self._row("000007"), self._row("000007")]
        self.assertEqual(overlap_summary(rows, auto_assigned=2),
                         "overlapping numbers: 000007 (2 files); 2 auto-assigned")


class TestScanProgress(unittest.TestCase):
    MTHD = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"

    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="mv_prog_"))
        for n in ("000001 - A - X", "000002 - B - Y", "000003 - C - Z"):
            (self.dir / f"{n}.mid").write_bytes(self.MTHD)

    def test_progress_sequence(self):
        calls = []

        def progress(done, total, note):
            calls.append((done, total, note))

        rows = scan_folder(self.dir, progress=progress)
        self.assertEqual(len(rows), 3)
        self.assertEqual(calls[0][0], 0)
        self.assertEqual(calls[0][1], 0)
        self.assertIn(self.dir.name, calls[0][2])
        validate = [c for c in calls if c[1] == 3]
        self.assertEqual(len(validate), 3)
        self.assertEqual(validate[-1][0], 3)
        self.assertEqual(validate[0][2], "000001 - A - X.mid")
        self.assertEqual(validate[1][2], "000002 - B - Y.mid")
        self.assertEqual(validate[2][2], "000003 - C - Z.mid")

    def test_enumerate_called_per_folder(self):
        d2 = pathlib.Path(tempfile.mkdtemp(prefix="mv_prog2_"))
        (d2 / "000004 - D - W.mid").write_bytes(self.MTHD)
        calls = []
        rows = scan_folder([self.dir, d2], progress=lambda *a: calls.append(a))
        self.assertEqual(len(rows), 4)
        listing = [c for c in calls if c[1] == 0]
        self.assertEqual(len(listing), 2)
        self.assertIn(self.dir.name, listing[0][2])
        self.assertIn(d2.name, listing[1][2])

    def test_progress_reports_rejected_files_too(self):
        (self.dir / "bad.mid").write_bytes(self.MTHD)
        calls = []
        rows = scan_folder(self.dir, progress=lambda *a: calls.append(a))
        self.assertEqual(len(rows), 4)
        validate = [c for c in calls if c[1] == 4]
        self.assertEqual(len(validate), 4)
        self.assertIn("bad.mid", validate[-1][2])

    def test_scan_without_progress_unchanged(self):
        rows = scan_folder(self.dir)
        self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
