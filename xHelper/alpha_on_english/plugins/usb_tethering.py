# plugins/usb_tethering.py
# -*- coding: utf-8 -*-

"""
USB Tethering Manager – plugin for enabling/disabling USB‑tethering mode.

Features:
- Check current USB‑tethering status
- Enable/disable tethering
- Show connection status
- Log operations
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt


def _run_adb(main_window, cmd):
    """Execute an ADB command with error handling."""
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        out = subprocess.check_output(
            [adb] + cmd.split(),
            text=True,
            timeout=5
        )
        return out.strip()
    except Exception as e:
        main_window.log_message(f"[USB Tethering] ADB error: {e}")
        return None


def _get_tethering_status(main_window):
    """Get current USB‑tethering status."""
    result = _run_adb(main_window, "shell settings get global tether_dns1")
    if result is None:
        return "Unknown"
    return "Enabled" if result else "Disabled"


def _set_tethering(main_window, enable):
    """Enable/disable USB‑tethering."""
    cmd = "shell su -c 'svc usb setFunctions"
    if enable:
        cmd += " rndis,diag,adb'"
    else:
        cmd += " mtp,adb'"
    
    result = _run_adb(main_window, cmd)
    if result is not None:
        main_window.log_message(
            f"[USB Tethering] Mode {'enabled' if enable else 'disabled'}"
        )

def register(main_window):
    """Register the plugin in the main window."""
    tab = QWidget()
    layout = QVBoxLayout(tab)

    title = QLabel("<h2>USB Tethering</h2>")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    status_label = QLabel("Status: checking...")
    status_label.setStyleSheet("font-weight: bold;")
    layout.addWidget(status_label)

    desc = QLabel(
        "Allows using the phone as a USB tethering device.\n"
        "Requires a USB connection and root privileges."
    )
    desc.setWordWrap(True)
    layout.addWidget(desc)

    toggle_btn = QPushButton("Enable USB Tethering")
    toggle_btn.setStyleSheet("padding: 10px;")
    layout.addWidget(toggle_btn)

    layout.addStretch()

    def update_status():
        status = _get_tethering_status(main_window)
        status_label.setText(f"Status: {status}")
        toggle_btn.setText(
            "Disable USB Tethering" if status == "Enabled" else "Enable USB Tethering"
        )

    def toggle_tethering():
        current_status = _get_tethering_status(main_window)
        if current_status == "Enabled":
            _set_tethering(main_window, False)
        else:
            _set_tethering(main_window, True)
        update_status()

    toggle_btn.clicked.connect(toggle_tethering)

    update_status()

    main_window.tabs.addTab(tab, "USB Tethering")
    main_window.log_message("[USB Tethering] Plugin loaded")
