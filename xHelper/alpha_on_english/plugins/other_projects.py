# -*- coding: utf-8 -*-
"""
Other Projects plugin for xHelper.

Creates a new tab that displays links to public Telegram channels
and the project website.
"""

def register(main_window):
    """
    Plugin entry point.
    `main_window` – the already‑running XHelperMainWindow.
    """
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
    from PyQt6.QtGui import QFont
    from PyQt6.QtCore import Qt

    tab = QWidget()
    layout = QVBoxLayout(tab)

    header = QLabel("Our other projects")
    header_font = QFont()
    header_font.setPointSize(18)
    header_font.setBold(True)
    header.setFont(header_font)
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    def link_label(text: str, url: str) -> QLabel:
        """
        Returns a QLabel with a clickable link.
        """
        lbl = QLabel(f"<a href='{url}'>{text}</a>")
        lbl.setOpenExternalLinks(True)
        font = QFont()
        font.setPointSize(14)
        lbl.setFont(font)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return lbl

    layout.addWidget(link_label(
        "Runget telegram channel",
        "https://t.me/runget_rt"
    ))
    layout.addWidget(link_label(
        "Dual gaming centre telegram channel",
        "https://t.me/DGC_off"
    ))
    layout.addWidget(link_label(
        "Dual gaming centre",
        "https://kolyadual.github.io/dualgamingcentre/"
    ))

    layout.addStretch()
    main_window.tabs.addTab(tab, "Other projects")
