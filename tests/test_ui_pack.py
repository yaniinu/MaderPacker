import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from maderpacker import app as app_mod
from maderpacker.build import BuildError, BuildResult
from maderpacker.model import ValidatedSong

APP = QApplication.instance() or QApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope,
                  tempfile.mkdtemp(prefix="mv_qsettings_"))


def _row(number, title, singer, ok=True, reason=""):
    return ValidatedSong(number, title, singer, pathlib.Path(f"{number}.mid"),
                         ok, reason)


class PackTestBase(unittest.TestCase):
    def setUp(self):
        self.win = app_mod.MainWindow()
        self.src = pathlib.Path(tempfile.mkdtemp(prefix="mv_pack_"))
        self.win._folders = [self.src]
        self.out = pathlib.Path(tempfile.mkdtemp(prefix="mv_out_"))
        patcher = patch.object(
            app_mod.QFileDialog, "getExistingDirectory",
            return_value=str(self.out))
        self.picker = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.win.close()


class TestPackFlow(PackTestBase):
    def test_pack_done_status_and_reveal(self):
        self.win._apply_scan([_row("000001", "Song", "Singer")])
        fake = BuildResult(1, 0, self.out / "idx" / "shubidx",
                           self.out / "idx" / "shubblob")
        with patch.object(app_mod, "build_library", return_value=fake) as m:
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(m.call_count, 1)
        self.assertEqual(m.call_args[0][1], self.out / "idx")
        self.assertIn("1 packed, 0 rejected", self.win.status_label.text())
        self.assertIn(str(self.out), self.win.status_label.text())
        self.assertTrue(self.win.reveal_button.isEnabled())

    def test_rejected_count_shown(self):
        self.win._apply_scan([_row("000001", "A", "B"),
                              _row("000002", "", "", ok=False, reason="duplicate")])
        fake = BuildResult(1, 1, self.out / "idx" / "shubidx",
                           self.out / "idx" / "shubblob")
        with patch.object(app_mod, "build_library", return_value=fake):
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertIn("1 packed, 1 rejected", self.win.status_label.text())

    def test_failure_path_shows_message(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        with patch.object(app_mod, "build_library",
                          side_effect=BuildError("disk full")), \
             patch.object(app_mod.QMessageBox, "warning") as warn:
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(warn.call_count, 1)
        self.assertIn("disk full", self.win.status_label.text())
        self.assertTrue(self.win.pack_button.isEnabled())

    def test_not_a_valid_song_failure(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        with patch.object(app_mod, "build_library",
                          side_effect=BuildError("no valid songs to pack")), \
             patch.object(app_mod.QMessageBox, "warning"):
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertIn("no valid songs", self.win.status_label.text())


class TestOutputPicker(PackTestBase):
    def _fake_result(self):
        return BuildResult(1, 0, self.out / "idx" / "shubidx",
                           self.out / "idx" / "shubblob")

    def test_picker_cancel_aborts_build(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        self.picker.return_value = ""
        with patch.object(app_mod, "build_library") as m:
            self.win.start_pack()
            APP.processEvents()
        self.assertEqual(m.call_count, 0)

    def test_overwrite_confirmed_build_proceeds(self):
        (self.out / "idx").mkdir(parents=True)
        (self.out / "idx" / "shubidx").write_bytes(b"x")
        self.win._apply_scan([_row("000001", "A", "B")])
        with patch.object(app_mod.QMessageBox, "question",
                          return_value=app_mod.QMessageBox.Yes) as q, \
             patch.object(app_mod, "build_library",
                          return_value=self._fake_result()) as m:
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(q.call_count, 1)
        self.assertIn("already contains a library", q.call_args[0][2])
        self.assertEqual(m.call_count, 1)

    def test_overwrite_declined_no_build(self):
        (self.out / "idx").mkdir(parents=True)
        (self.out / "idx" / "shubblob").write_bytes(b"x")
        self.win._apply_scan([_row("000001", "A", "B")])
        with patch.object(app_mod.QMessageBox, "question",
                          return_value=app_mod.QMessageBox.No), \
             patch.object(app_mod, "build_library") as m:
            self.win.start_pack()
            APP.processEvents()
        self.assertEqual(m.call_count, 0)

    def test_no_overwrite_prompt_when_idx_empty(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        with patch.object(app_mod.QMessageBox, "question") as q, \
             patch.object(app_mod, "build_library",
                          return_value=self._fake_result()):
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(q.call_count, 0)

    def test_needs_rows_guard_prompts_before_picker(self):
        need = ValidatedSong("", "Song", "Singer", pathlib.Path("x.mid"),
                             False, "needs number", True)
        self.win._apply_scan([_row("000001", "A", "B"), need])
        with patch.object(app_mod.QMessageBox, "question",
                          return_value=app_mod.QMessageBox.Yes) as q, \
             patch.object(app_mod, "build_library",
                          return_value=self._fake_result()) as m:
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(q.call_count, 1)
        self.assertIn("Assign now?", q.call_args[0][2])
        self.assertEqual(m.call_count, 1)

    def test_needs_rows_guard_no_aborts(self):
        need = ValidatedSong("", "Song", "Singer", pathlib.Path("x.mid"),
                             False, "needs number", True)
        self.win._apply_scan([_row("000001", "A", "B"), need])
        with patch.object(app_mod.QMessageBox, "question",
                          return_value=app_mod.QMessageBox.Cancel), \
             patch.object(app_mod, "build_library") as m:
            self.win.start_pack()
            APP.processEvents()
        self.assertEqual(m.call_count, 0)
        self.assertEqual(self.picker.call_count, 0)

    def test_last_output_dir_remembered(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        with patch.object(app_mod, "build_library",
                          return_value=self._fake_result()):
            self.win.start_pack()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(self.win.settings.value("lastOutputDir"),
                         str(self.out))


if __name__ == "__main__":
    unittest.main()
