"""About / first-launch intro dialog: logo, creator credit, PH Corner link."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

from maderpacker.icons import logo_pixmap

PROFILE_URL = "https://phcorner.org/members/2803058/"
CREATOR = "yaniinuuu"
APP_TITLE = "MaderPacker"
TAGLINE = "Folders of numbered karaoke MIDI files \u2192 a SongHub library."


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_TITLE}")
        self.setModal(True)
        self.setFixedWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(96))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(logo)

        title = QLabel(APP_TITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("aboutTitle")
        root.addWidget(title)

        tagline = QLabel(TAGLINE)
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setWordWrap(True)
        root.addWidget(tagline)

        creator = QLabel(f"Created by {CREATOR}")
        creator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        creator.setObjectName("aboutCreator")
        root.addWidget(creator)

        link = QLabel(f'<a href="{PROFILE_URL}">phcorner.org/members/2803058</a>')
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setObjectName("aboutLink")
        link.linkActivated.connect(self._open_profile)
        root.addWidget(link)

        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("primaryButton")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        row.addStretch(1)
        root.addLayout(row)

        self.setStyleSheet("""
            QDialog { background: #0f172a; color: #f8fafc;
                      font-family: 'DejaVu Sans'; font-size: 13px; }
            QLabel { color: #f8fafc; padding: 2px 0; }
            QLabel#aboutTitle { font-size: 20px; font-weight: bold;
                                color: #22c55e; padding-top: 6px; }
            QLabel#aboutCreator { color: #94a3b8; }
            QLabel#aboutLink a { color: #38bdf8; }
            QPushButton { background: #334155; color: #f8fafc;
                          border: 1px solid #475569;
                          border-radius: 6px; padding: 8px 24px; }
            QPushButton:hover { background: #3b4a63; }
            QPushButton#primaryButton { background: #22c55e; border: none;
                                        color: #0f172a; font-weight: bold; }
            QPushButton#primaryButton:hover { background: #16a34a; }
        """)

    def _open_profile(self):
        QDesktopServices.openUrl(QUrl(PROFILE_URL))
