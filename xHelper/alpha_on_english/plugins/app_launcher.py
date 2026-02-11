# plugins/app_launcher.py
# -*- coding: utf-8 -*-

"""
app_launcher – быстрый запуск приложений.

* Поиск/фильтрация списка пакетов.
* Кнопка «Обновить список».
* Двойной клик → запуск.
"""

import subprocess
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QLabel
)


def _run_adb(main_window, cmd):
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        out = subprocess.check_output([adb] + cmd.split(), text=True, timeout=10)
        return out
    except Exception as e:
        main_window.log_message(f"[Launcher] Ошибка adb: {e}")
        return ""


def register(main_window):
    tab = QWidget()
    vbox = QVBoxLayout(tab)

    # ---- Поисковая строка ----
    search_edit = QLineEdit()
    search_edit.setPlaceholderText("Filter packages …")
    vbox.addWidget(search_edit)

    # ---- Список пакетов ----
    list_widget = QListWidget()
    vbox.addWidget(list_widget)

    # ---- Кнопка обновления ----
    btn_refresh = QPushButton("Refresh list")
    vbox.addWidget(btn_refresh)

    # --------------------------------------------------------------
    #   Получаем список пакетов
    # --------------------------------------------------------------
    def load_packages():
        list_widget.clear()
        # Пользовательские
        out_user = _run_adb(main_window, "shell pm list packages -3")
        # Системные
        out_sys = _run_adb(main_window, "shell pm list packages -s")
        packages = set()
        for line in (out_user + out_sys).splitlines():
            if line.startswith("package:"):
                packages.add(line.replace("package:", "").strip())
        for pkg in sorted(packages):
            item = QListWidgetItem(pkg)
            list_widget.addItem(item)

    btn_refresh.clicked.connect(load_packages)

    # --------------------------------------------------------------
    #   Фильтрация в реальном времени
    # --------------------------------------------------------------
    def filter_packages():
        txt = search_edit.text().lower()
        for i in range(list_widget.count()):
            it = list_widget.item(i)
            it.setHidden(txt not in it.text().lower())

    search_edit.textChanged.connect(filter_packages)

    # --------------------------------------------------------------
    #   Запуск выбранного приложения
    # --------------------------------------------------------------
    def launch_selected():
        cur = list_widget.currentItem()
        if not cur:
            QMessageBox.warning(tab, "Warning", "Select an application")
            return
        pkg = cur.text()
        main_window.log_message(f"[Launcher] Запуск {pkg}")
        # Monkey – простой и быстрый способ
        _run_adb(main_window,
                 f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

    # Двойной клик – запуск
    list_widget.itemDoubleClicked.connect(lambda _: launch_selected())

    btn_launch = QPushButton("Launch selected")
    btn_launch.clicked.connect(launch_selected)
    vbox.addWidget(btn_launch)

    # --------------------------------------------------------------
    #   Первичная загрузка
    # --------------------------------------------------------------
    load_packages()

    main_window.tabs.addTab(tab, "App Launcher")
