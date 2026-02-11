# plugins/add_platform_tools_to_path.py
# -*- coding: utf-8 -*-

"""
add_platform_tools_to_path – плагин для xHelper

Позволяет:
 • искать каталоги  …\platform-tools  на всех дисках Windows;
 • добавлять их в переменную среды PATH (через реестр);
 • вручную указывать любой путь.

Только Windows‑реализация (на остальных ОС покажет инфо‑сообщение).
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
#   Класс‑рабочий поток – поиск platform‑tools
# --------------------------------------------------------------
class SearchWorker(QObject):
    finished = pyqtSignal(list)      # список найденных путей
    progress = pyqtSignal(str)      # статус (например, «Сканируем C:\…»)

    def __init__(self):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True

    def start_search(self):
        """Ищет папки platform‑tools на всех доступных дисках."""
        found = []
        drives = [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(f"{c}:\\")]
        for drive in drives:
            if self._stop:
                break
            self.progress.emit(f"Сканирую {drive}")
            for root, dirs, _ in os.walk(drive):
                if "platform-tools" in dirs:
                    p = os.path.join(root, "platform-tools")
                    found.append(p)
                    # Не спускаемся дальше в этой ветке
                    dirs[:] = []
                # Ограничение для слишком «глубоких» деревьев (для ускорения)
                if len(root.split(os.sep)) > 10:
                    dirs[:] = []
        self.finished.emit(found)


# --------------------------------------------------------------
#   Функция, вызываемая при загрузке плагина
# --------------------------------------------------------------
def register(main_window):
    """Создаёт вкладку «PATH‑manager» и регистрирует её в xHelper."""
    tab = QWidget()
    main_layout = QVBoxLayout(tab)

    # ----- Верхняя панель с кнопками ---------------------------------
    btn_layout = QHBoxLayout()
    btn_search   = QPushButton("Найти platform‑tools")
    btn_manual   = QPushButton("Добавить вручную")
    btn_add_path = QPushButton("Добавить выбранные в PATH")
    btn_add_path.setEnabled(False)          # активируем, когда в списке что‑то выбрано
    btn_layout.addWidget(btn_search)
    btn_layout.addWidget(btn_manual)
    btn_layout.addStretch()
    btn_layout.addWidget(btn_add_path)

    # ----- Список найденных путей -----------------------------------
    list_widget = QListWidget()
    list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

    # ----- Строка‑статуса -------------------------------------------
    status_lbl = QLabel("Готов к поиску …")
    status_lbl.setStyleSheet("color: gray;")
    status_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

    # ----- Прогресс‑бар (небольшой, внизу) -------------------------
    prog_bar = QProgressBar()
    prog_bar.setMaximumHeight(12)
    prog_bar.setTextVisible(False)
    prog_bar.setVisible(False)

    # ----- Добавляем всё в макет ------------------------------------
    main_layout.addLayout(btn_layout)
    main_layout.addWidget(list_widget)
    main_layout.addWidget(prog_bar)
    main_layout.addWidget(status_lbl)

    # --------------------------------------------------------------
    #   Вспомогательные функции плагина
    # --------------------------------------------------------------
    def _enable_add_btn():
        """Активирует кнопку «Добавить», если выбран хотя бы один элемент."""
        btn_add_path.setEnabled(bool(list_widget.selectedItems()))

    def _refresh_status(msg: str, error: bool = False):
        status_lbl.setText(msg)
        status_lbl.setStyleSheet("color: red;" if error else "color: gray;")

    # --------------------------------------------------------------
    #   Поиск platform‑tools
    # --------------------------------------------------------------
    search_thread = None
    search_worker = None

    def start_search():
        nonlocal search_thread, search_worker
        if not sys.platform.startswith("win"):
            QMessageBox.information(
                tab,
                "Не поддерживается",
                "Поиск platform‑tools реализован только для Windows."
            )
            return

        btn_search.setEnabled(False)
        list_widget.clear()
        _refresh_status("Идёт сканирование дисков…")
        prog_bar.setVisible(True)
        prog_bar.setRange(0, 0)          # «мувинговый» индикатор

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
            status = f"Найдено каталогов: {len(paths)}. Выберите нужные и нажмите «Добавить»"
            _refresh_status(status)
            btn_add_path.setEnabled(True)
            # По умолчанию выделяем всё
            for i in range(list_widget.count()):
                list_widget.item(i).setSelected(True)
        else:
            _refresh_status("Папки platform‑tools не найдены.", error=False)

    # --------------------------------------------------------------
    #   Ручное добавление пути
    # --------------------------------------------------------------
    def add_manual():
        folder = QFileDialog.getExistingDirectory(
            tab, "Выберите каталог platform‑tools"
        )
        if folder:
            # Проверка, действительно ли это platform‑tools
            if not os.path.isdir(os.path.join(folder, "platform-tools")) and \
               not folder.lower().endswith("platform-tools"):
                reply = QMessageBox.question(
                    tab,
                    "Подтверждение",
                    "Выбранный каталог не выглядит как platform‑tools.\n"
                    "Все‑равно добавить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            # Не допускаем дублирования в списке
            for i in range(list_widget.count()):
                if list_widget.item(i).text() == folder:
                    QMessageBox.information(tab, "Информация", "Эта папка уже в списке")
                    return

            list_widget.addItem(folder)
            _refresh_status(f"Путь добавлен вручную: {folder}")
            btn_add_path.setEnabled(True)

    # --------------------------------------------------------------
    #   Добавление выбранных путей в Windows‑PATH
    # --------------------------------------------------------------
    def add_to_path():
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(tab, "Ошибка", "Не выбрано ни одного пути")
            return

        paths_to_add = [it.text() for it in selected_items]

        try:
            # Открываем ветку реестра HKCU\Environment
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

                    # Обновляем переменную окружения текущего процесса
                    os.environ["PATH"] = new_path

                    # Сообщаем системе о изменении (чтобы новые терминалы видели PATH)
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
                        "Готово",
                        f"Пути успешно добавлены в PATH:\n" + "\n".join(added) +
                        "\n\nДля применения изменений перезапустите терминал/IDE."
                    )
                    _refresh_status(f"PATH обновлён, добавлено: {len(added)} путь(ов)")
                else:
                    QMessageBox.information(
                        tab,
                        "Информация",
                        "Все выбранные пути уже находятся в переменной PATH."
                    )
                    _refresh_status("Новых путей не добавлено.")
        except PermissionError:
            QMessageBox.critical(
                tab,
                "Ошибка доступа",
                "Недостаточно прав для изменения реестра.\n"
                "Запустите программу от имени администратора."
            )
        except Exception as exc:
            QMessageBox.critical(
                tab,
                "Ошибка",
                f"Не удалось изменить PATH:\n{exc}"
            )
            _refresh_status(f"Ошибка: {exc}", error=True)

    # --------------------------------------------------------------
    #   Подключаем сигналы/слоты
    # --------------------------------------------------------------
    btn_search.clicked.connect(start_search)
    btn_manual.clicked.connect(add_manual)
    btn_add_path.clicked.connect(add_to_path)
    list_widget.itemSelectionChanged.connect(_enable_add_btn)

    # --------------------------------------------------------------
    #   Добавляем вкладку в главное окно
    # --------------------------------------------------------------
    main_window.tabs.addTab(tab, "PATH‑manager")
