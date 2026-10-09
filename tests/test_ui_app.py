import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from maderpacker import about as about_mod
from maderpacker import app as app_mod
from maderpacker.model import ValidatedSong

APP = QApplication.instance() or QApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope,
                  tempfile.mkdtemp(prefix="mv_qsettings_"))


def _row(number, title, singer, ok=True, reason=""):
    return ValidatedSong(number, title, singer, pathlib.Path(f"{number}.mid"),
                         ok, reason)


class TestApplyScan(unittest.TestCase):
    def setUp(self):
        self.win = app_mod.MainWindow()

    def tearDown(self):
        self.win.close()

    def test_table_and_status(self):
        rows = [_row("000001", "Song", "Singer"),
                _row("000002", "Bad", "", ok=False, reason="duplicate number")]
        self.win._apply_scan(rows)
        self.assertEqual(self.win.table.rowCount(), 2)
        self.assertIn("1 valid, 1 rejected", self.win.status_label.text())
        self.assertTrue(self.win.pack_button.isEnabled())
        self.assertIn("duplicate", self.win.table.item(1, 4).text())

    def test_pack_disabled_when_no_valid_rows(self):
        self.win._apply_scan([_row("", "", "", ok=False, reason="bad")])
        self.assertFalse(self.win.pack_button.isEnabled())

    def test_empty_scan(self):
        self.win._apply_scan([])
        self.assertEqual(self.win.table.rowCount(), 0)
        self.assertFalse(self.win.pack_button.isEnabled())

    def test_progress_updates(self):
        self.win._on_progress(3, 10)
        self.assertIn("3 / 10", self.win.status_label.text())

    def test_scan_folder_wiring(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="mv_ui_"))
        (d / "000001 - A - B.mid").write_bytes(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60")
        (d / "oops.mid").write_bytes(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60")
        rows = app_mod.scan_now(d)
        self.win._apply_scan(rows)
        self.assertEqual(self.win.table.rowCount(), 2)
        self.assertIn("1 valid, 1 rejected", self.win.status_label.text())


class TestFolderList(unittest.TestCase):
    def setUp(self):
        self.win = app_mod.MainWindow()
        self.dir_a = pathlib.Path(tempfile.mkdtemp(prefix="mv_fa_"))
        self.dir_b = pathlib.Path(tempfile.mkdtemp(prefix="mv_fb_"))
        (self.dir_a / "000001 - A - X.mid").write_bytes(
            b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60")

    def tearDown(self):
        self.win.close()

    def test_initial_state(self):
        self.assertEqual(self.win._folders, [])
        self.assertEqual(self.win.folder_list.count(), 0)
        self.assertIn("No folders selected", self.win.folder_label.text())
        self.assertFalse(self.win.pack_button.isEnabled())

    def test_add_folder_appends_and_scans(self):
        with patch.object(app_mod.QFileDialog, "getExistingDirectory",
                          return_value=str(self.dir_a)):
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(self.win._folders, [self.dir_a])
        self.assertEqual(self.win.folder_list.count(), 1)
        self.assertEqual(self.win.table.rowCount(), 1)
        self.assertIn("1 folder selected", self.win.folder_label.text())

    def test_add_same_folder_twice_is_noop(self):
        with patch.object(app_mod.QFileDialog, "getExistingDirectory",
                          return_value=str(self.dir_a)):
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(len(self.win._folders), 1)

    def test_remove_folder_rescans(self):
        with patch.object(app_mod.QFileDialog, "getExistingDirectory",
                          return_value=str(self.dir_a)):
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.win.folder_list.setCurrentRow(0)
        self.win.remove_folder()
        self.win._worker.wait(5000)
        APP.processEvents()
        self.assertEqual(self.win._folders, [])
        self.assertEqual(self.win.table.rowCount(), 0)
        self.assertIn("No folders selected", self.win.folder_label.text())

    def test_remove_when_nothing_selected_removes_last(self):
        with patch.object(app_mod.QFileDialog, "getExistingDirectory",
                          return_value=str(self.dir_a)):
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.win.folder_list.setCurrentRow(-1)
        self.win.remove_folder()
        self.win._worker.wait(5000)
        APP.processEvents()
        self.assertEqual(self.win._folders, [])

    def _x_button(self, row):
        item = self.win.folder_list.item(row)
        widget = self.win.folder_list.itemWidget(item)
        self.assertIsNotNone(widget)
        buttons = [b for b in widget.findChildren(QPushButton)
                   if b.objectName() == "removeFolderButton"]
        self.assertEqual(len(buttons), 1)
        return buttons[0]

    def test_row_has_x_button(self):
        with patch.object(app_mod.QFileDialog, "getExistingDirectory",
                          return_value=str(self.dir_a)):
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
        self._x_button(0)

    def test_x_click_removes_that_folder(self):
        with patch.object(app_mod.QFileDialog, "getExistingDirectory",
                          side_effect=[str(self.dir_a), str(self.dir_b)]):
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
            self.win.add_folder()
            self.win._worker.wait(5000)
            APP.processEvents()
        self.assertEqual(self.win._folders, [self.dir_a, self.dir_b])
        self._x_button(0).click()
        self.win._worker.wait(5000)
        APP.processEvents()
        self.assertEqual(self.win._folders, [self.dir_b])
        self.assertEqual(self.win.folder_list.count(), 1)
        self.assertIn("1 folder selected", self.win.folder_label.text())


class TestScanOverlay(unittest.TestCase):
    MTHD = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"

    def setUp(self):
        self.win = app_mod.MainWindow()
        self.dir_a = pathlib.Path(tempfile.mkdtemp(prefix="mv_ov_"))
        (self.dir_a / "000001 - A - X.mid").write_bytes(self.MTHD)

    def tearDown(self):
        self.win.close()

    def test_overlay_begin_end(self):
        self.win._overlay_begin()
        self.assertFalse(self.win.scan_overlay.isHidden())
        self.win._overlay_end()
        self.assertTrue(self.win.scan_overlay.isHidden())

    def test_on_scan_done_hides_overlay(self):
        self.win._overlay_begin()
        self.win._on_scan_done([])
        self.assertTrue(self.win.scan_overlay.isHidden())

    def test_progress_slot_updates_bar_and_count(self):
        self.win._on_scan_progress(5, 10)
        self.assertEqual(self.win.scan_bar.maximum(), 10)
        self.assertEqual(self.win.scan_bar.value(), 5)
        self.assertIn("5", self.win.scan_count.text())
        self.win._on_scan_progress(0, 0)
        self.assertEqual(self.win.scan_bar.maximum(), 0)

    def test_note_slot_updates_detail(self):
        self.win._on_scan_note("Listing songs…")
        self.assertIn("songs", self.win.scan_detail.text())

    def test_rescan_begins_overlay_and_settles_hidden(self):
        with patch.object(self.win, "_overlay_begin") as begin:
            with patch.object(app_mod.QFileDialog, "getExistingDirectory",
                              return_value=str(self.dir_a)):
                self.win.add_folder()
                self.win._worker.wait(5000)
                APP.processEvents()
        self.assertEqual(begin.call_count, 1)
        self.assertTrue(self.win.scan_overlay.isHidden())


class TestNeedsNumberUI(unittest.TestCase):
    @staticmethod
    def _need(path_name="Song - Singer.mid"):
        return ValidatedSong("", "Song", "Singer", pathlib.Path(path_name),
                             False, "needs number", True)

    def setUp(self):
        self.win = app_mod.MainWindow()

    def tearDown(self):
        self.win.close()

    def test_status_separates_needs_from_rejected(self):
        self.win._apply_scan([
            _row("000001", "A", "B"),
            self._need(),
            _row("", "", "", ok=False, reason="duplicate number")])
        self.assertIn("1 valid, 1 need numbers, 1 rejected",
                      self.win.status_label.text())

    def test_status_unchanged_without_needs(self):
        self.win._apply_scan([_row("000001", "A", "B"),
                              _row("", "", "", ok=False, reason="bad")])
        self.assertIn("1 valid, 1 rejected", self.win.status_label.text())

    def test_needs_row_shows_reason_and_orange(self):
        self.win._apply_scan([self._need()])
        item = self.win.table.item(0, 4)
        self.assertEqual(item.text(), "needs number")
        self.assertEqual(item.foreground().color().name(), "#f59e0b")

    def test_scan_done_prompts_and_yes_assigns(self):
        rows = [self._need(), _row("000007", "A", "B")]
        with patch.object(app_mod.QMessageBox, "question",
                          return_value=app_mod.QMessageBox.Yes) as q:
            self.win._on_scan_done(rows)
        self.assertEqual(q.call_count, 1)
        text = q.call_args[0][2]
        self.assertIn("1 files have no valid numbers", text)
        numbers = [r.number for r in self.win._rows]
        self.assertIn("000008", numbers)
        self.assertEqual(self.win._auto_assigned, 1)
        self.assertIn("1 auto-assigned", self.win.warning_label.text())
        self.assertTrue(self.win.pack_button.isEnabled())

    def test_scan_done_prompt_no_leaves_unassigned(self):
        rows = [self._need(), _row("000007", "A", "B")]
        with patch.object(app_mod.QMessageBox, "question",
                          return_value=app_mod.QMessageBox.Cancel):
            self.win._on_scan_done(rows)
        self.assertTrue(self.win._rows[0].needs_number)
        self.assertEqual(self.win._rows[0].number, "")
        self.assertEqual(self.win._auto_assigned, 0)

    def test_prompt_not_shown_without_needs(self):
        with patch.object(app_mod.QMessageBox, "question") as q:
            self.win._on_scan_done([_row("000001", "A", "B")])
        self.assertEqual(q.call_count, 0)

    def test_warning_label_shows_source_duplicates(self):
        self.win._apply_scan([
            _row("000001", "A", "X"),
            _row("000001", "B", "Y", ok=False, reason="duplicate number 000001")])
        self.assertIn("overlapping numbers: 000001 (2 files)",
                      self.win.warning_label.text())

    def test_warning_hidden_when_clean(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        self.assertFalse(self.win.warning_label.isVisible()
                         and self.win.warning_label.text())

    def test_valid_number_edit_commits(self):
        self.win._apply_scan([_row("000001", "A", "B"), self._need()])
        self.win._rows = app_mod.assign_numbers(self.win._rows)
        self.win._apply_scan(self.win._rows)
        self.win.table.item(1, 0).setText("000999")
        self.win._on_item_changed(self.win.table.item(1, 0))
        self.assertEqual(self.win._rows[1].number, "000999")
        self.assertTrue(self.win._rows[1].ok)

    def test_duplicate_number_edit_reverts(self):
        self.win._apply_scan([_row("000001", "A", "B"), self._need()])
        self.win._rows = app_mod.assign_numbers(self.win._rows)
        self.win._apply_scan(self.win._rows)
        self.win.table.item(1, 0).setText("000001")
        self.win._on_item_changed(self.win.table.item(1, 0))
        self.assertNotEqual(self.win._rows[1].number, "000001")
        self.assertIn("overlapping number",
                      self.win.warning_label.text())
        self.assertEqual(self.win.table.item(1, 0).text(),
                         self.win._rows[1].number)

    def test_six_digit_enforced(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        self.win.table.item(0, 0).setText("1234")
        self.win._on_item_changed(self.win.table.item(0, 0))
        self.assertEqual(self.win._rows[0].number, "000001")
        self.assertIn("6 digits", self.win.warning_label.text())

    def test_rejected_row_not_editable(self):
        self.win._apply_scan([_row("", "", "", ok=False, reason="duplicate")])
        flags = self.win.table.item(0, 0).flags()
        self.assertFalse(flags & __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ItemIsEditable)

    def test_ok_row_editable(self):
        self.win._apply_scan([_row("000001", "A", "B")])
        flags = self.win.table.item(0, 0).flags()
        self.assertTrue(flags & __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ItemIsEditable)


class TestAbout(unittest.TestCase):
    def setUp(self):
        self.win = app_mod.MainWindow()
        self.win.settings.remove("introSeen")
        self.addCleanup(self.win.settings.remove, "introSeen")

    def tearDown(self):
        self.win.close()

    def test_first_run_shows_intro_and_marks_seen(self):
        dialog = self.win.maybe_show_intro()
        self.assertIsNotNone(dialog)
        self.assertTrue(self.win.settings.value("introSeen"))
        dialog.close()

    def test_second_run_skips_intro(self):
        first = self.win.maybe_show_intro()
        self.assertIsNotNone(first)
        first.close()
        with patch.object(app_mod.AboutDialog, "open") as o:
            self.assertIsNone(self.win.maybe_show_intro())
        self.assertEqual(o.call_count, 0)

    def test_about_button_opens_dialog(self):
        with patch.object(app_mod.AboutDialog, "open") as o:
            self.win.about_button.click()
        self.assertEqual(o.call_count, 1)

    def test_dialog_text_creator_and_link(self):
        dialog = about_mod.AboutDialog()
        texts = " ".join(w.text() for w in dialog.findChildren(app_mod.QLabel))
        self.assertIn("Created by yaniinuuu", texts)
        self.assertIn("phcorner.org/members/2803058", texts)
        self.assertNotIn("github", texts.lower())
        dialog.close()

    def test_link_opens_profile_in_browser(self):
        dialog = about_mod.AboutDialog()
        with patch.object(about_mod.QDesktopServices, "openUrl") as m:
            dialog._open_profile()
        self.assertEqual(m.call_count, 1)
        self.assertEqual(m.call_args[0][0].toString(), about_mod.PROFILE_URL)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
