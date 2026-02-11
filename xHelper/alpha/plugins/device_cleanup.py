# plugins/device_cleanup.py
# -*- coding: utf-8 -*-

"""
device_cleanup – плагин для поиска и очистки «тяжёлых» файлов (≥ 2 ГБ)
на Android‑устройстве.

Функционал:
 • Поиск всех файлов размером более 2 GB (используется `adb shell find …`).
 • Вывод найденных файлов в таблицу с чек‑боксами.
 • Кнопка **«Удалить выбранные»** → `adb shell rm -f <path>`.
 • Кнопка **«Скопировать выбранные»** → `adb pull <remote> <local>`  
   (пользователь выбирает папку‑назначение на ПК, сохраняется относительная
   структура каталогов).
 • Кнопка **«Обновить список»** повторно сканирует устройство.
 • В процессе сканирования/операций отображается `QProgressBar`.

Плагин не меняет ядро xHelper, использует только публичный API
`main_window.run_adb_command`, `main_window.log_message` и `main_window.tabs`.
"""

import os
import subprocess
import threading

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QProgressBar, QCheckBox,
)

# ----------------------------------------------------------------------
#   Вспомогательные функции
# ----------------------------------------------------------------------
def _run_adb(main_window, cmd: str) -> str:
    """
    Выполняет adb‑команду и возвращает stdout (или пустую строку при ошибке).
    При ошибке пишет в лог `main_window.log_message`.
    """
    adb = (
        main_window.settings.get("adb_path", "adb")
        if hasattr(main_window, "settings")
        else "adb"
    )
    try:
        out = subprocess.check_output(
            [adb] + cmd.split(),
            text=True,
            timeout=15,
        )
        return out
    except Exception as e:
        main_window.log_message(f"[Cleanup] Ошибка adb: {e}")
        return ""


def _human_readable_size(bytes_cnt: int) -> str:
    """Преобразует количество байт в строку вида «X.Y GB»."""
    GB = 1024 ** 3
    return f"{bytes_cnt / GB:.2f} GB"


# ----------------------------------------------------------------------
#   Поток сканирования (чтобы UI не «замёрзал»)
# ----------------------------------------------------------------------
class ScanThread(threading.Thread):
    """
    Выполняет `adb shell find / -type f -size +2147483648c`
    (файлы > 2 GB) и сохраняет список путей в `self.result`.
    """

    def __init__(self, main_window):
        super().__init__(daemon=True)
        self.main_window = main_window
        self.result = []          # список кортежей (path, size_bytes)
        self._stop = False

    def run(self):
        # Пытаемся искать в пользовательском хранилище, а если нет – во всём FS.
        # Используем байты, потому что `c` в find – единица «byte».
        find_cmd = "shell find /storage/emulated/0 -type f -size +2147483648c"
        out = _run_adb(self.main_window, find_cmd)

        if not out:
            # Возможно, нет доступа к /storage, пробуем корневой каталог.
            self.main_window.log_message("[Cleanup] Поиск в /storage не дал результатов, пробуем /")
            find_cmd = "shell find / -type f -size +2147483648c"
            out = _run_adb(self.main_window, find_cmd)

        # Обрабатываем построчно список путей
        for line in out.splitlines():
            if self._stop:
                break
            path = line.strip()
            if not path:
                continue
            # Получаем размер файла (stat -c %s)
            size_out = _run_adb(self.main_window, f'shell stat -c %s "{path}"')
            try:
                size_bytes = int(size_out.strip())
            except Exception:
                size_bytes = 0
            self.result.append((path, size_bytes))

    def stop(self):
        self._stop = True


# ----------------------------------------------------------------------
#   Основная функция регистрации
# ----------------------------------------------------------------------
def register(main_window):
    """Создаёт вкладку «Очистка устройства» и встраивает всю логику."""
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # --------------------------------------------------------------
    #   Заголовок и кнопка «Обновить список»
    # --------------------------------------------------------------
    header_layout = QHBoxLayout()
    lbl = QLabel("Поиск файлов > 2 GB (умные: стартует в отдельном потоке).")
    btn_refresh = QPushButton("Обновить список")
    header_layout.addWidget(lbl)
    header_layout.addStretch()
    header_layout.addWidget(btn_refresh)
    layout.addLayout(header_layout)

    # --------------------------------------------------------------
    #   Таблица результатов
    # --------------------------------------------------------------
    table = QTableWidget()
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["", "Путь", "Размер"])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    layout.addWidget(table)

    # --------------------------------------------------------------
    #   Кнопки действий (удалить / скопировать)
    # --------------------------------------------------------------
    actions_layout = QHBoxLayout()
    btn_delete = QPushButton("Удалить выбранные")
    btn_pull   = QPushButton("Скопировать выбранные")
    actions_layout.addWidget(btn_delete)
    actions_layout.addWidget(btn_pull)
    actions_layout.addStretch()
    layout.addLayout(actions_layout)

    # --------------------------------------------------------------
    #   Прогресс‑бар (сканирование)
    # --------------------------------------------------------------
    progress = QProgressBar()
    progress.setVisible(False)
    layout.addWidget(progress)

    # --------------------------------------------------------------
    #   Внутренние функции
    # --------------------------------------------------------------
    scan_thread = None   # будет хранить текущий ScanThread

    def populate_table(file_list):
        """Заполняем QTableWidget элементами из file_list [(path, size_bytes), …]."""
        table.setRowCount(0)
        for path, size in file_list:
            row = table.rowCount()
            table.insertRow(row)

            # Чек‑бокс
            chk = QCheckBox()
            chk.setChecked(False)
            table.setCellWidget(row, 0, chk)

            # Путь
            item_path = QTableWidgetItem(path)
            item_path.setFlags(item_path.flags() ^ Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 1, item_path)

            # Размер человеко‑читаемый
            size_str = _human_readable_size(size) if size else "—"
            item_size = QTableWidgetItem(size_str)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_size.setFlags(item_size.flags() ^ Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 2, item_size)

    def start_scan():
        """Запускает отдельный поток поиска больших файлов."""
        nonlocal scan_thread

        if scan_thread and scan_thread.is_alive():
            QMessageBox.warning(tab, "Сканирование", "Сканирование уже запущено.")
            return

        table.setRowCount(0)
        progress.setValue(0)
        progress.setMaximum(0)   # «мувинговый» индикатор
        progress.setVisible(True)
        main_window.log_message("[Cleanup] Старт сканирования > 2 GB…")

        # Создаём и запускаем поток
        scan_thread = ScanThread(main_window)
        scan_thread.start()

        # Периодически проверяем, закончил ли поток
        def check_finished():
            if scan_thread.is_alive():
                QTimer.singleShot(500, check_finished)
            else:
                progress.setVisible(False)
                populate_table(scan_thread.result)
                main_window.log_message(f"[Cleanup] Сканирование завершено, найдено {len(scan_thread.result)} файлов.")

        QTimer.singleShot(500, check_finished)

    btn_refresh.clicked.connect(start_scan)

    # --------------------------------------------------------------
    #   Удаление выбранных файлов
    # --------------------------------------------------------------
    def get_selected_rows():
        """Возвращает список индексов строк, где чек‑бокс отмечен."""
        rows = []
        for row in range(table.rowCount()):
            widget = table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                rows.append(row)
        return rows

    def delete_selected():
        rows = get_selected_rows()
        if not rows:
            QMessageBox.information(tab, "Удалить", "Не выбрано ни одного файла.")
            return

        confirm = QMessageBox.question(
            tab,
            "Подтверждение",
            f"Вы действительно хотите удалить {len(rows)} файл(ов) с устройства?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        for row in sorted(rows, reverse=True):
            path_item = table.item(row, 1)
            if not path_item:
                continue
            remote_path = path_item.text()
            # Выполняем удаление
            out = _run_adb(main_window, f'shell rm -f "{remote_path}"')
            main_window.log_message(f"[Cleanup] Удалён: {remote_path}")
            # Убираем строку из таблицы
            table.removeRow(row)

        QMessageBox.information(tab, "Готово", "Выбранные файлы удалены.")

    btn_delete.clicked.connect(delete_selected)

    # --------------------------------------------------------------
    #   Копирование выбранных файлов на ПК
    # --------------------------------------------------------------
    def pull_selected():
        rows = get_selected_rows()
        if not rows:
            QMessageBox.information(tab, "Скопировать", "Не выбрано ни одного файла.")
            return

        # Выбор папки назначения
        dest_dir = QFileDialog.getExistingDirectory(
            tab, "Выберите папку‑назначение", os.path.expanduser("~")
        )
        if not dest_dir:
            return

        for row in rows:
            path_item = table.item(row, 1)
            if not path_item:
                continue
            remote_path = path_item.text()

            # Формируем локальный путь, сохраняя иерархию после корня
            # Убираем начальный «/», затем создаём подпапки в dest_dir.
            rel_path = remote_path.lstrip("/")          # например, storage/emulated/0/Movies/Big.mkv
            local_path = os.path.join(dest_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Выполняем `adb pull`
            main_window.log_message(f"[Cleanup] Копируем {remote_path} → {local_path}")
            out = _run_adb(main_window, f'pull "{remote_path}" "{local_path}"')
            main_window.log_message(f"[Cleanup] Скопировано: {remote_path}")

        QMessageBox.information(
            tab,
            "Готово",
            f"Выбранные файлы скопированы в {dest_dir}.",
        )

    btn_pull.clicked.connect(pull_selected)

    # --------------------------------------------------------------
    #   Добавляем вкладку в главное окно
    # --------------------------------------------------------------
    main_window.tabs.addTab(tab, "Очистка устройства")
    main_window.log_message("[Cleanup] Плагин загружен – вкладка «Очистка устройства» добавлена.")
