# plugins/wifi_manager.py
# -*- coding: utf-8 -*-

"""
wifi_manager – простое управление Wi‑Fi на Android‑устройстве.

* Индикация текущего статуса (включён/выключен, SSID).
* Кнопка «Включить/Выключить».
* Кнопка «Открыть настройки Wi‑Fi» (переход в системные настройки).
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer


def _run_adb(main_window, cmd):
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        out = subprocess.check_output([adb] + cmd.split(), text=True, timeout=5)
        return out
    except Exception as e:
        main_window.log_message(f"[Wi‑Fi] Ошибка adb: {e}")
        return ""


def register(main_window):
    tab = QWidget()
    vbox = QVBoxLayout(tab)

    # ------------------- Статус -------------------
    status_lbl = QLabel("Статус: неизвестно")
    ssid_lbl   = QLabel("SSID: —")
    vbox.addWidget(status_lbl)
    vbox.addWidget(ssid_lbl)

    # ------------------- Кнопки -------------------
    btn_layout = QHBoxLayout()
    btn_toggle = QPushButton("Включить Wi‑Fi")
    btn_open   = QPushButton("Открыть настройки Wi‑Fi")
    btn_layout.addWidget(btn_toggle)
    btn_layout.addWidget(btn_open)
    vbox.addLayout(btn_layout)

    # --------------------------------------------------------------
    #   Обновление статуса (каждые 3 сек.)
    # --------------------------------------------------------------
    def refresh_status():
        # 1) Проверка, включён ли Wi‑Fi
        out = _run_adb(main_window, "shell svc wifi")
        enabled = "enabled" in out.lower()

        # 2) Текущий SSID
        out2 = _run_adb(main_window, "shell dumpsys wifi")
        ssid = "—"
        for line in out2.splitlines():
            if "SSID:" in line or "SSID =" in line:
                ssid = line.split(":")[-1].strip().strip('"')
                break

        status_lbl.setText(f"Статус: {'Включён' if enabled else 'Выключен'}")
        ssid_lbl.setText(f"SSID: {ssid}")
        btn_toggle.setText("Выключить Wi‑Fi" if enabled else "Включить Wi‑Fi")

    timer = QTimer(main_window)
    timer.setInterval(3000)
    timer.timeout.connect(refresh_status)
    timer.start()
    refresh_status()

    # --------------------------------------------------------------
    #   Переключатель Wi‑Fi
    # --------------------------------------------------------------
    def toggle_wifi():
        out = _run_adb(main_window, "shell svc wifi")
        if "enabled" in out.lower():
            _run_adb(main_window, "shell svc wifi disable")
        else:
            _run_adb(main_window, "shell svc wifi enable")
        refresh_status()

    btn_toggle.clicked.connect(toggle_wifi)

    # --------------------------------------------------------------
    #   Открыть системные настройки Wi‑Fi
    # --------------------------------------------------------------
    def open_wifi_settings():
        _run_adb(main_window,
                 "shell am start -a android.settings.WIFI_SETTINGS")
        QMessageBox.information(tab,
                                "Wi‑Fi",
                                "Открыты системные настройки Wi‑Fi.\n"
                                "Закройте их, когда закончите.")

    btn_open.clicked.connect(open_wifi_settings)

    main_window.tabs.addTab(tab, "Wi‑Fi‑менеджер")
