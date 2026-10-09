"""MaderPacker GUI: pick a MIDI folder, review rows, pack a fresh library."""
import os
import pathlib
import re
import sys
from dataclasses import replace

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from maderpacker.about import AboutDialog
from maderpacker.build import BuildResult, build_library
from maderpacker.icons import logo_icon
from maderpacker.model import ValidatedSong
from maderpacker.validate import assign_numbers, overlap_summary, scan_folder

REJECT_COLOR = QColor("#ef4444")
NEEDS_COLOR = QColor("#f59e0b")

BUNDLED_FONTS = ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")


def _fonts_dir() -> pathlib.Path:
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen is not None:
        # bundled via: --add-data "maderpacker/fonts;maderpacker/fonts"
        return pathlib.Path(frozen) / "maderpacker" / "fonts"
    return pathlib.Path(__file__).resolve().parent / "fonts"


def _point_qt_at_bundled_fonts() -> None:
    """Point Qt's font directory at the bundled fonts BEFORE QApplication."""
    fonts_dir = _fonts_dir()
    if fonts_dir.is_dir():
        os.environ.setdefault("QT_QPA_FONTDIR", str(fonts_dir))


_point_qt_at_bundled_fonts()


def register_fonts() -> list[str]:
    """Register bundled DejaVu fonts (Qt ships none in frozen builds)."""
    from PySide6.QtGui import QFontDatabase
    loaded: list[str] = []
    for name in BUNDLED_FONTS:
        path = _fonts_dir() / name
        if path.is_file() and QFontDatabase.addApplicationFont(str(path)) >= 0:
            loaded.append(name)
    return loaded


def scan_now(folders, progress=None) -> list[ValidatedSong]:
    return scan_folder(folders, progress=progress)


class Worker(QThread):
    progressed = Signal(int, int)
    noted = Signal(str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as e:  # noqa: BLE001 - surfaced to the user
            self.failed.emit(str(e))
        else:
            self.done.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MaderPacker")
        self.setWindowIcon(logo_icon())
        self.resize(1024, 660)
        self._folders: list[pathlib.Path] = []
        self.settings = QSettings("MaderPacker", "MaderPacker")
        self._rows: list[ValidatedSong] = []
        self._result: BuildResult | None = None
        self._worker: Worker | None = None
        self._auto_assigned = 0
        self._filling = False

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.folder_label = QLabel("No folders selected")
        self.folder_label.setObjectName("folderLabel")
        self.add_button = QPushButton("Add folder…")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self.add_folder)
        self.folder_list = QListWidget()
        self.folder_list.setFixedHeight(64)
        top.addWidget(self.add_button)
        top.addWidget(self.folder_label, 1)
        self.about_button = QPushButton("About")
        self.about_button.clicked.connect(self.show_about)
        top.addWidget(self.about_button)
        root.addLayout(top)
        root.addWidget(self.folder_list)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Number", "Title", "Singer", "File", "Status"])
        self.table.setEditTriggers(QTableWidget.DoubleClicked
                                   | QTableWidget.EditKeyPressed)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        self.scan_overlay = QFrame(central)
        self.scan_overlay.setObjectName("scanOverlay")
        self.scan_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,
                                       True)
        ov = QVBoxLayout(self.scan_overlay)
        ov.setContentsMargins(24, 24, 24, 24)
        ov.setSpacing(8)
        ov.addStretch(1)
        self.scan_title = QLabel("Scanning…")
        self.scan_title.setObjectName("scanTitle")
        self.scan_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ov.addWidget(self.scan_title)
        self.scan_detail = QLabel("")
        self.scan_detail.setObjectName("scanDetail")
        self.scan_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ov.addWidget(self.scan_detail)
        self.scan_count = QLabel("")
        self.scan_count.setObjectName("scanCount")
        self.scan_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ov.addWidget(self.scan_count)
        self.scan_bar = QProgressBar()
        self.scan_bar.setRange(0, 0)
        ov.addWidget(self.scan_bar)
        ov.addStretch(1)
        self.scan_overlay.hide()

        bottom = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_label = QLabel("Pick a folder of MIDI files to begin.")
        self.warning_label = QLabel("")
        self.warning_label.setObjectName("warningLabel")
        self.warning_label.setVisible(False)
        self.pack_button = QPushButton("Pack")
        self.pack_button.setObjectName("primaryButton")
        self.pack_button.setEnabled(False)
        self.pack_button.clicked.connect(self.start_pack)
        self.reveal_button = QPushButton("Open output folder")
        self.reveal_button.setEnabled(False)
        self.reveal_button.clicked.connect(self.reveal_output)
        bottom.addWidget(self.progress_bar)
        bottom.addWidget(self.status_label)
        bottom.addWidget(self.warning_label, 1)
        bottom.addWidget(self.pack_button)
        bottom.addWidget(self.reveal_button)
        root.addLayout(bottom)

        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0f172a; color: #f8fafc;
                                  font-family: 'DejaVu Sans'; font-size: 13px; }
            QLabel#folderLabel { color: #94a3b8; padding: 6px 0; }
            QTableWidget { background: #1b2336; alternate-background-color: #171e2f;
                           border: 1px solid #475569; gridline-color: #334155;
                           selection-background-color: #334155;
                           selection-color: #f8fafc; }
            QHeaderView::section { background: #1e293b; color: #94a3b8;
                                   border: none; border-bottom: 1px solid #475569;
                                   padding: 6px; font-weight: bold; }
            QTableWidget::item { padding: 4px; }
            QPushButton { background: #334155; color: #f8fafc;
                          border: 1px solid #475569;
                          border-radius: 6px; padding: 8px 16px; }
            QPushButton:hover { background: #3b4a63; }
            QPushButton:focus { border: 1px solid #ffffff; }
            QPushButton#primaryButton { background: #22c55e; border: none;
                                        color: #0f172a; font-weight: bold; }
            QPushButton#primaryButton:hover { background: #16a34a; }
            QPushButton#primaryButton:focus { border: 1px solid #ffffff; }
            QPushButton:disabled { background: #1e293b; color: #64748b;
                                   border: 1px solid #334155; }
            QProgressBar { background: #1e293b; border: 1px solid #475569;
                           border-radius: 4px; text-align: center; color: #f8fafc; }
            QProgressBar::chunk { background: #22c55e; border-radius: 3px; }
            QLabel#warningLabel { color: #f59e0b; font-weight: bold;
                                  padding: 2px 6px; }
            QFrame#scanOverlay { background: rgba(15, 23, 42, 225);
                                 border: 1px solid #475569;
                                 border-radius: 8px; }
            QLabel#scanTitle { color: #f8fafc; font-size: 16px;
                               font-weight: bold; }
            QLabel#scanDetail { color: #38bdf8; }
            QLabel#scanCount { color: #94a3b8; }
            QPushButton#removeFolderButton { background: transparent;
                                             border: none; color: #94a3b8;
                                             font-size: 14px; padding: 0px 8px;
                                             border-radius: 4px; }
            QPushButton#removeFolderButton:hover { color: #ef4444;
                                                   background: #1e293b; }
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_overlay()

    def _position_overlay(self):
        self.scan_overlay.setGeometry(self.table.geometry())

    def _overlay_begin(self, note: str = ""):
        self.scan_detail.setText(note)
        self.scan_count.setText("")
        self.scan_bar.setRange(0, 0)
        self._position_overlay()
        self.scan_overlay.show()
        self.scan_overlay.raise_()

    def _overlay_end(self):
        self.scan_overlay.hide()

    def _on_scan_progress(self, done: int, total: int):
        if self.scan_bar.maximum() != total:
            self.scan_bar.setRange(0, total)
        if total:
            self.scan_bar.setValue(done)
            self.scan_count.setText(f"{done:,} / {total:,} files")
        else:
            self.scan_count.setText("")

    def _on_scan_note(self, note: str):
        self.scan_detail.setText(note)

    def show_about(self) -> AboutDialog:
        dialog = AboutDialog(self)
        dialog.open()
        return dialog

    def maybe_show_intro(self) -> AboutDialog | None:
        """Show the intro once on first launch; returns the dialog or None."""
        if self.settings.value("introSeen"):
            return None
        self.settings.setValue("introSeen", True)
        return self.show_about()

    def add_folder(self):
        start = str(self._folders[0]) if self._folders else str(pathlib.Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Add MIDI folder", start)
        if not chosen:
            return
        folder = pathlib.Path(chosen)
        if folder in self._folders:
            return
        self._folders.append(folder)
        self._add_folder_row(folder)
        self.rescan()

    def _add_folder_row(self, folder: pathlib.Path):
        item = QListWidgetItem(str(folder))
        item.setToolTip(str(folder))
        self.folder_list.addItem(item)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 2, 8, 2)
        h.setSpacing(4)
        label = QLabel(str(folder))
        label.setToolTip(str(folder))
        x = QPushButton("\u2715")
        x.setObjectName("removeFolderButton")
        x.setFixedWidth(26)
        x.clicked.connect(lambda _=False, f=folder: self._remove_folder_at(f))
        h.addWidget(label, 1)
        h.addWidget(x)
        self.folder_list.setItemWidget(item, row)

    def _remove_folder_at(self, folder: pathlib.Path):
        try:
            row = self._folders.index(folder)
        except ValueError:
            return
        del self._folders[row]
        self.folder_list.takeItem(row)
        self.rescan()

    def remove_folder(self):
        row = self.folder_list.currentRow()
        if row < 0:
            row = self.folder_list.count() - 1
        if row < 0:
            return
        self.folder_list.takeItem(row)
        del self._folders[row]
        self.rescan()

    def rescan(self):
        n = len(self._folders)
        self.folder_label.setText(
            "No folders selected" if n == 0
            else f"{n} folder{'s' if n != 1 else ''} selected")
        self.pack_button.setEnabled(False)
        self.reveal_button.setEnabled(False)
        if not self._folders:
            self._apply_scan([])
            self._overlay_end()
            return
        self.status_label.setText("Scanning…")
        self._overlay_begin()
        holder: dict[str, Worker] = {}

        def report(done: int, total: int, note: str):
            holder["w"].progressed.emit(done, total)
            holder["w"].noted.emit(note)

        w = Worker(scan_now, list(self._folders), progress=report)
        holder["w"] = w
        w.progressed.connect(self._on_scan_progress)
        w.noted.connect(self._on_scan_note)
        w.done.connect(self._on_scan_done)
        w.failed.connect(self._on_failed)
        self._worker = w
        w.start()

    def _on_scan_done(self, rows):
        self._overlay_end()
        self._auto_assigned = 0
        self._apply_scan(rows)
        self._prompt_auto_assign()

    def _apply_scan(self, rows: list[ValidatedSong]):
        self._rows = rows
        self._filling = True
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                if r.needs_number:
                    status, color = "needs number", NEEDS_COLOR
                elif r.ok:
                    status, color = "ok", None
                else:
                    status, color = r.reason, REJECT_COLOR
                values = [r.number, r.title, r.singer, r.path.name, status]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 0:
                        if r.ok or r.needs_number:
                            item.setFlags(item.flags() | Qt.ItemIsEditable)
                        else:
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if color is not None and col in (3, 4):
                        item.setForeground(QBrush(color))
                    self.table.setItem(i, col, item)
        finally:
            self.table.blockSignals(False)
            self._filling = False
        self._refresh_status()
        self._refresh_warning()

    def _refresh_status(self):
        ok = sum(r.ok for r in self._rows)
        needs = sum(r.needs_number for r in self._rows)
        bad = len(self._rows) - ok - needs
        text = f"{ok} valid"
        if needs:
            text += f", {needs} need numbers"
        text += f", {bad} rejected"
        self.status_label.setText(text)
        self.pack_button.setEnabled(ok > 0)

    def _refresh_warning(self, transient: str = ""):
        text = transient or overlap_summary(self._rows, self._auto_assigned)
        self.warning_label.setText(text)
        self.warning_label.setVisible(bool(text))

    def _prompt_auto_assign(self) -> bool:
        n = sum(r.needs_number for r in self._rows)
        if n == 0:
            return True
        answer = QMessageBox.question(
            self, "Auto-assign numbers",
            f"{n} files have no valid numbers.\n\n"
            "Numbers will be auto-assigned (next free, no overlaps). Assign now?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return False
        self._auto_assigned += n
        self._rows = assign_numbers(self._rows)
        self._apply_scan(self._rows)
        return True

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._filling or item.column() != 0:
            return
        row = item.row()
        current = self._rows[row]
        value = item.text()
        transient = ""
        if not re.fullmatch(r"\d{6}", value):
            transient = "number must be exactly 6 digits"
        elif any(i != row and r.number == value
                 for i, r in enumerate(self._rows)):
            transient = f"overlapping number: {value} already used"
        if transient:
            self.table.blockSignals(True)
            item.setText(current.number)
            self.table.blockSignals(False)
            self._refresh_warning(transient)
            return
        if value == current.number:
            return
        updated = replace(current, number=value)
        if current.needs_number:
            updated = replace(updated, ok=True, reason="", needs_number=False)
        self._rows = [updated if i == row else r
                      for i, r in enumerate(self._rows)]
        self._refresh_status()
        self._refresh_warning()

    def start_pack(self):
        if not self._folders:
            return
        if not self._prompt_auto_assign():
            return
        start = str(self.settings.value("lastOutputDir",
                                        str(pathlib.Path.home())))
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose output folder", start)
        if not chosen:
            return
        chosen_path = pathlib.Path(chosen)
        out_dir = chosen_path / "idx"
        if (out_dir / "shubidx").exists() or (out_dir / "shubblob").exists():
            answer = QMessageBox.question(
                self, "Overwrite library?",
                f"{out_dir} already contains a library.\n"
                "Overwrite? Back it up first?",
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if answer != QMessageBox.Yes:
                return
        self.settings.setValue("lastOutputDir", chosen)
        self.pack_button.setEnabled(False)
        self.reveal_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Packing…")
        w = Worker(build_library, self._rows, out_dir)
        w.progressed.connect(self._on_progress)
        w.done.connect(self._on_pack_done)
        w.failed.connect(self._on_failed)
        self._worker = w
        w.start()

    def _on_progress(self, done: int, total: int):
        if self.progress_bar.maximum() != total:
            self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.status_label.setText(f"Packing {done} / {total}…")

    def _on_pack_done(self, result: BuildResult):
        self._result = result
        self.progress_bar.setVisible(False)
        self.status_label.setText(
            f"{result.packed} packed, {result.rejected} rejected → {result.idx_path.parent}")
        self.pack_button.setEnabled(True)
        self.reveal_button.setEnabled(True)

    def _on_failed(self, message: str):
        self._overlay_end()
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Failed: {message}")
        self.pack_button.setEnabled(any(r.ok for r in self._rows))
        QMessageBox.warning(self, "MaderPacker", message)

    def reveal_output(self):
        if self._result is not None:
            os.startfile(str(self._result.idx_path.parent))


def main() -> int:
    qt_app = QApplication(sys.argv)
    register_fonts()
    font = QFont("DejaVu Sans", 10)
    qt_app.setFont(font)
    win = MainWindow()
    win.show()
    win.maybe_show_intro()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
