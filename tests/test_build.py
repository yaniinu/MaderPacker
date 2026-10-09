import csv
import pathlib
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.build import BuildError, build_library
from maderpacker.idx_extract import load_tables, resolve_number, resolve_singer
from maderpacker.mid_export import extract_midi
from maderpacker.model import ValidatedSong
from maderpacker.validate import scan_folder
from tests.paths import IDX, BLOB, GROUND


def _dummy_row(n: int, ok: bool = True) -> ValidatedSong:
    return ValidatedSong(f"{n:06d}", "t", "s", pathlib.Path("x.mid"), ok, "" if ok else "bad")


class TestBuildErrors(unittest.TestCase):
    def test_no_valid_songs(self):
        out = pathlib.Path(tempfile.mkdtemp(prefix="mv_out_"))
        with self.assertRaisesRegex(BuildError, "no valid songs"):
            build_library([_dummy_row(1, ok=False)], out)

    def test_too_many_songs(self):
        out = pathlib.Path(tempfile.mkdtemp(prefix="mv_out_"))
        rows = [_dummy_row(i % 1000000) for i in range(65536)]
        with self.assertRaisesRegex(BuildError, "too many songs"):
            build_library(rows, out)


@unittest.skipUnless(IDX.exists() and BLOB.exists(), "large fixtures not present")
class TestSixSongRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="mv_rt_"))
        cls.src = cls.tmp / "src"
        cls.src.mkdir()
        idx_data = IDX.read_bytes()
        blob = BLOB.read_bytes()
        tables = load_tables(idx_data)
        by_code = {resolve_number(r, tables): r for r in tables.songs}
        cls.ground = list(csv.DictReader(GROUND.read_text(encoding="utf-8").splitlines()))
        cls.expected_files = {}
        for g in cls.ground:
            rec = by_code[g["number"]]
            assert rec.title == g["title"], (rec.title, g["title"])
            midi = extract_midi(blob, rec.midi_pos, rec.midi_size)
            name = f'{g["number"]} - {g["title"]} - {g["singer"]}.mid'
            (cls.src / name).write_bytes(midi)
            cls.expected_files[name] = midi
        (cls.src / "badname.mid").write_bytes(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60")
        (cls.src / "000002 - NoHeader - X.mid").write_bytes(b"RIFFnope")
        cls.rows = scan_folder(cls.src)
        cls.out = cls.tmp / "out"
        cls.progress = []
        cls.result = build_library(cls.rows, cls.out,
                                   progress=lambda d, t: cls.progress.append((d, t)))
        cls.out_idx = (cls.out / "shubidx").read_bytes()
        cls.out_blob = (cls.out / "shubblob").read_bytes()
        cls.out_tables = load_tables(cls.out_idx)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_scan_sees_eight_files(self):
        self.assertEqual(len(self.rows), 8)
        ok = [r for r in self.rows if r.ok]
        self.assertEqual(len(ok), 6)

    def test_counts_and_progress(self):
        self.assertEqual((self.result.packed, self.result.rejected), (6, 2))
        self.assertEqual(self.progress, [(i, 6) for i in range(1, 7)])

    def test_rows_match_ground_truth(self):
        got = {(resolve_number(r, self.out_tables), r.title,
                resolve_singer(r, self.out_tables)) for r in self.out_tables.songs}
        want = {(g["number"], g["title"], g["singer"]) for g in self.ground}
        self.assertEqual(got, want)

    def test_songs_sorted_by_upper(self):
        keys = [r.title.upper() for r in self.out_tables.songs]
        self.assertEqual(keys, sorted(keys))

    def test_singers_sorted_unique(self):
        names = self.out_tables.singers
        self.assertEqual(names, sorted(set(names), key=lambda s: (s.upper(), s)))

    def test_header_counts(self):
        self.assertEqual(struct.unpack_from("<HH", self.out_idx, 28),
                         (len(self.out_tables.singers), 6))

    def test_midi_bytes_identical(self):
        by_code = {resolve_number(r, self.out_tables): r for r in self.out_tables.songs}
        for name, want in self.expected_files.items():
            number = name.split(" - ")[0]
            rec = by_code[number]
            got = extract_midi(self.out_blob, rec.midi_pos, rec.midi_size)
            self.assertEqual(got, want, number)

    def test_blob_geometry(self):
        for rec in self.out_tables.songs:
            off = rec.midi_pos * 2048
            end = off + rec.midi_size * 2048
            self.assertEqual(self.out_blob[off:off + 4], b"MKMD")
            self.assertLessEqual(end, len(self.out_blob))
        self.assertEqual(len(self.out_blob) % 2048, 0)


def _kar_bytes() -> bytes:
    """Minimal format-0 SMF with karaoke-style text/lyric meta events."""
    import struct as _s
    text = b"@TKar Song"
    ev1 = b"\x00\xff\x01" + bytes([len(text)]) + text
    lyric = b"LaLa"
    ev2 = b"\x00\xff\x05" + bytes([len(lyric)]) + lyric
    end = b"\x00\xff\x2f\x00"
    track_body = ev1 + ev2 + end
    track = b"MTrk" + _s.pack(">I", len(track_body)) + track_body
    header = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"
    return header + track


class TestKarBuild(unittest.TestCase):
    def test_kar_row_packed_byte_exact(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="mv_karbuild_"))
        try:
            src = tmp / "src"
            src.mkdir()
            midi = _kar_bytes()
            (src / "000042 - Kar Song - Kar Singer.kar").write_bytes(midi)
            rows = scan_folder(src)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0].ok, rows[0].reason)
            out = tmp / "out"
            result = build_library(rows, out)
            self.assertEqual((result.packed, result.rejected), (1, 0))
            tables = load_tables((out / "shubidx").read_bytes())
            self.assertEqual(len(tables.songs), 1)
            rec = tables.songs[0]
            got = extract_midi((out / "shubblob").read_bytes(),
                               rec.midi_pos, rec.midi_size)
            self.assertEqual(got, midi)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
