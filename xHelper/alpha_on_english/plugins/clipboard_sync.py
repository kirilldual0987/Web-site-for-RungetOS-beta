# plugins/clipboard_sync.py
# -*- coding: utf-8 -*-

"""
clipboard_sync – синхронизация буфера обмена между ПК и Android‑устройством.

* Кнопка «Получить из устройства» → выводит содержимое в поле.
* Кнопка «Отправить в устройство» → копирует содержимое из поля в Android.
"""

import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt


def _run_adb(main_window, cmd):
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        out = subprocess.check_output([adb] + cmd.split(), text=True, timeout=5)
        return out
    except Exception as e:
        main_window.log_message(f"[Clipboard] Ошибка adb: {e}")
        return ""


def register(main_window):
    tab = QWidget()
    vbox = QVBoxLayout(tab)

    # ------------------------------------------------------------------
    #   Текстовое поле – отображает содержимое буфера
    # ------------------------------------------------------------------
    txt = QTextEdit()
    txt.setPlaceholderText("Clipboard contents")
    vbox.addWidget(txt)

    # ------------------------------------------------------------------
    #   Кнопки «Получить» / «Отправить»
    # ------------------------------------------------------------------
    btn_layout = QHBoxLayout()
    btn_get = QPushButton("Get from device")
    btn_set = QPushButton("Send to device")
    btn_layout.addWidget(btn_get)
    btn_layout.addWidget(btn_set)
    vbox.addLayout(btn_layout)

    # ------------------------------------------------------------------
    #   Получение буфера с Android (через dumpsys clipboard)
    # ------------------------------------------------------------------
    def get_clipboard():
        out = _run_adb(main_window, "shell dumpsys clipboard")
        # Пример строки: “Primary clip: text=Hello world”
        for line in out.splitlines():
            if "text=" in line:
                txt.setPlainText(line.split("text=")[1].strip())
                main_window.log_message("[Clipboard] Содержимое получено")
                return
        QMessageBox.information(tab, "Clipboard", "No text found in clipboard")
        main_window.log_message("[Clipboard] Пустой буфер")

    btn_get.clicked.connect(get_clipboard)

    # ------------------------------------------------------------------
    #   Отправка текста в Android (через `am broadcast` – требует установленный
    #   сервис ‘clipper’, но в большинстве современных прошивок он уже есть)
    # ------------------------------------------------------------------
    def set_clipboard():
        data = txt.toPlainText()
        if not data:
            QMessageBox.warning(tab, "Warning", "Field is empty")
            return
        # Попытка через обычный ввод – работает в большинстве ROM‑ов
        escaped = data.replace("\\", "\\\\").replace("\"", "\\\"")
        _run_adb(main_window,
                 f'shell am broadcast -a clipper.set -e text "{escaped}"')
        main_window.log_message("[Clipboard] Текст отправлен в устройство")
        QMessageBox.information(tab, "Clipboard", "Text copied to Android")

    btn_set.clicked.connect(set_clipboard)

    main_window.tabs.addTab(tab, "Clipboard")
