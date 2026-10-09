import unittest
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from maderpacker.mid_export import sanitize_filename, song_filename, extract_midi, MidiError
from tests.paths import IDX, BLOB

IDX_DATA = IDX.read_bytes()
BLOB_DATA = BLOB.read_bytes()


class TestNaming(unittest.TestCase):
    def test_basic_name(self):
        self.assertEqual(song_filename("017142", "'Nyebe'", "SB19"),
                         "017142 - 'Nyebe' - SB19.mid")

    def test_illegal_chars_sanitized(self):
        name = song_filename("028729", "You're: My/Everything? (Ver.)", "Gummy*")
        for ch in '<>:"/\\|?*':
            self.assertNotIn(ch, name)
        self.assertTrue(name.startswith("028729 - "))
        self.assertTrue(name.endswith(".mid"))

    def test_control_chars_stripped(self):
        self.assertNotIn("\x01", sanitize_filename("a\x01b"))


class TestExtractMidi(unittest.TestCase):
    def test_nyebe(self):
        midi = extract_midi(BLOB_DATA, 107518, 9)
        self.assertTrue(midi.startswith(b"MThd"))
        self.assertEqual(len(midi), 52225)

    def test_youre_my_everything(self):
        midi = extract_midi(BLOB_DATA, 174300, 7)
        self.assertTrue(midi.startswith(b"MThd"))
        self.assertEqual(len(midi), 29394)

    def test_bad_magic_raises(self):
        with self.assertRaises(MidiError):
            extract_midi(BLOB_DATA, 0 + 1, 9)  # misaligned: no MKMD

    def test_out_of_range_raises(self):
        with self.assertRaises(MidiError):
            extract_midi(BLOB_DATA, 10_000_000, 9)


if __name__ == "__main__":
    unittest.main()
