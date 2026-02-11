# plugins/add_platform_tools_to_path.py
# -*- coding: utf-8 -*-

"""
add_platform_tools_to_path – plugin for xHelper

Allows:
 • searching for …\platform-tools directories on all Windows drives;
 • adding them to the PATH environment variable (via the registry);
 • manually adding any path.

Windows‑only implementation (on other OSes an info message will be shown).
"""

import os
import sys
import threading
import winreg
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QFileDialog,
    QMessageBox, QProgressBar, QApplication
)


# --------------------------------------------------------------
#   Worker thread class – searches for platform‑tools
# --------------------------------------------------------------
class SearchWorker(QObject):
    finished = pyqtSignal(list)      # list of found paths
    progress = pyqtSignal(str)      # status (e.g., “Scanning C:\…”)

    def __init__(self):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True

    def start_search(self):
        """Search for platform‑tools folders on all available drives."""
        found = []
        drives = [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(f"{c}:\\")]
        for drive in drives:
            if self._stop:
                break
            self.progress.emit(f"Scanning {drive}")
            for root, dirs, _ in os.walk(drive):
                if "platform-tools" in dirs:
                    p = os.path.join(root, "platform-tools")
                    found.append(p)
                    dirs[:] = []  # don't descend further
                if len(root.split(os.sep)) > 10:
                    dirs[:] = []  # limit depth for speed
        self.finished.emit(found)


# --------------------------------------------------------------
#   Function called when the plugin is loaded
# --------------------------------------------------------------
def register(main_window):
    """Creates the “PATH manager” tab and registers it in xHelper."""
    tab = QWidget()
    main_layout = QVBoxLayout(tab)

    # ----- Upper button panel ---------------------------------
    btn_layout = QHBoxLayout()
    btn_search   = QPushButton("Search platform-tools")
    btn_manual   = QPushButton("Add manually")
    btn_add_path = QPushButton("Add selected to PATH")
    btn_add_path.setEnabled(False)
    btn_layout.addWidget(btn_search)
    btn_layout.addWidget(btn_manual)
    btn_layout.addStretch()
    btn_layout.addWidget(btn_add_path)

    # ----- List of found paths -------------------------------
    list_widget = QListWidget()
    list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

    # ----- Status line ----------------------------------------
    status_lbl = QLabel("Ready to search ...")
    status_lbl.setStyleSheet("color: gray;")
    status_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

    # ----- Small progress bar (bottom) -----------------------
    prog_bar = QProgressBar()
    prog_bar.setMaximumHeight(12)
    prog_bar.setTextVisible(False)
    prog_bar.setVisible(False)

    # ----- Assemble layout -------------------------------------
    main_layout.addLayout(btn_layout)
    main_layout.addWidget(list_widget)
    main_layout.addWidget(prog_bar)
    main_layout.addWidget(status_lbl)

    # --------------------------------------------------------------
    #   Helper functions
    # --------------------------------------------------------------
    def _enable_add_btn():
        btn_add_path.setEnabled(bool(list_widget.selectedItems()))

    def _refresh_status(msg: str, error: bool = False):
        status_lbl.setText(msg)
        status_lbl.setStyleSheet("color: red;" if error else "color: gray;")

    # --------------------------------------------------------------
    #   Search platform-tools
    # --------------------------------------------------------------
    search_thread = None
    search_worker = None

    def start_search():
        nonlocal search_thread, search_worker
        if not sys.platform.startswith("win"):
            QMessageBox.information(
                tab,
                "Not supported",
                "Searching for platform-tools is implemented only on Windows."
            )
            return

        btn_search.setEnabled(False)
        list_widget.clear()
        _refresh_status("Scanning drives…")
        prog_bar.setVisible(True)
        prog_bar.setRange(0, 0)          # moving indicator

        search_worker = SearchWorker()
        search_worker.progress.connect(_refresh_status)
        search_worker.finished.connect(on_search_finished)

        search_thread = threading.Thread(target=search_worker.start_search, daemon=True)
        search_thread.start()

    def on_search_finished(paths: list):
        btn_search.setEnabled(True)
        prog_bar.setVisible(False)

        if paths:
            for p in paths:
                item = QListWidgetItem(p)
                list_widget.addItem(item)
            status = f"Found directories: {len(paths)}. Select and click “Add”."
            _refresh_status(status)
            btn_add_path.setEnabled(True)
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)
        else:
            _refresh_status("No platform-tools folders found.", error=False)

    # --------------------------------------------------------------
    #   Manual path addition
    # --------------------------------------------------------------
    def add_manual():
        folder = QFileDialog.getExistingDirectory(
            tab, "Select platform-tools directory"
        )
        if folder:
            if not os.path.isdir(os.path.join(folder, "platform-tools")) and \
               not folder.lower().endswith("platform-tools"):
                reply = QMessageBox.question(
                    tab,
                    "Confirmation",
                    "The selected folder does not look like platform-tools.\nAdd anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            for i in range(list_widget.count()):
                if list_widget.item(i).text() == folder:
                    QMessageBox.information(tab, "Info", "This folder is already in the list")
                    return

            list_widget.addItem(folder)
            _refresh_status(f"Manually added path: {folder}")
            btn_add_path.setEnabled(True)

    # --------------------------------------------------------------
    #   Add selected paths to Windows PATH
    # --------------------------------------------------------------
    def add_to_path():
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(tab, "Error", "No path selected")
            return

        paths_to_add = [it.text() for it in selected_items]

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as hk:
                try:
                    cur_path, reg_type = winreg.QueryValueEx(hk, "Path")
                except FileNotFoundError:
                    cur_path = ""
                    reg_type = winreg.REG_EXPAND_SZ

                cur_items = [p for p in cur_path.split(os.pathsep) if p]
                cur_items_lower = [p.lower() for p in cur_items]

                added = []
                for p in paths_to_add:
                    if p.lower() not in cur_items_lower:
                        cur_items.append(p)
                        added.append(p)

                if added:
                    new_path = os.pathsep.join(cur_items)
                    winreg.SetValueEx(hk, "Path", 0, reg_type, new_path)

                    os.environ["PATH"] = new_path

                    import ctypes
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x001A
                    SMTO_ABORTIFHUNG = 0x0002
                    ctypes.windll.user32.SendMessageTimeoutW(
                        HWND_BROADCAST,
                        WM_SETTINGCHANGE,
                        0,
                        "Environment",
                        SMTO_ABORTIFHUNG,
                        5000,
                        None
                    )

                    QMessageBox.information(
                        tab,
                        "Done",
                        f"Paths added to PATH:\n" + "\n".join(added) +
                        "\n\nRestart terminals/IDE to apply changes."
                    )
                    _refresh_status(f"PATH updated, added {len(added)} path(s)")
                else:
                    QMessageBox.information(
                        tab,
                        "Info",
                        "All selected paths are already present in PATH."
                    )
                    _refresh_status("No new paths added.")
        except PermissionError:
            QMessageBox.critical(
                tab,
                "Access error",
                "Insufficient rights to modify the registry.\nRun the program as administrator."
            )
        except Exception as exc:
            QMessageBox.critical(
                tab,
                "Error",
                f"Failed to modify PATH:\n{exc}"
            )
            _refresh_status(f"Error: {exc}", error=True)

    # --------------------------------------------------------------
    #   Connect signals/slots
    # --------------------------------------------------------------
    btn_search.clicked.connect(start_search)
    btn_manual.clicked.connect(add_manual)
    btn_add_path.clicked.connect(add_to_path)
    list_widget.itemSelectionChanged.connect(_enable_add_btn)

    # --------------------------------------------------------------
    #   Add tab to main window
    # --------------------------------------------------------------
    main_window.tabs.addTab(tab, "PATH manager")
