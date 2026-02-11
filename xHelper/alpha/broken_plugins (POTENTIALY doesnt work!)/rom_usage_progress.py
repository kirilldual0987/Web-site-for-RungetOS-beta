# plugins/rom_usage_progress.py
# -*- coding: utf-8 -*-

"""
rom_usage_progress – плагин для xHelper.

Добавляет в меню «Инструменты» пункт «ROM‑Usage».  
При открытии показывается диалог с QProgressBar, в котором:
    • отображается процент занятого места (ROM);
    • цвет полоски плавно меняется от зелёного → жёлтого → красного
      в зависимости от заполненности;
    • есть кнопка «Обновить», которая перечитывает данные с устройства.

Требуется установленный adb и подключённое Android‑устройство.
"""

import re
import subprocess
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QMessageBox, QMenu, QAction
)


# ----------------------------------------------------------------------
#   Вспомогательные функции
# ----------------------------------------------------------------------
def _run_adb(main_window, cmd: str) -> str:
    """
    Выполняет adb‑команду и возвращает её stdout.
    При ошибке возвращает пустую строку и пишет сообщение в лог.
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
            timeout=7,
        )
        return out
    except Exception as e:
        main_window.log_message(f"[ROM‑Usage] Ошибка adb: {e}")
        return ""


def _parse_rom_percent(df_output: str) -> int:
    """
    Парсит вывод `adb shell df -h /data` (или `df /sdcard`), ищет строку,
    содержащую путь «/data», и извлекает процент использования.
    Возвращает значение от 0 до 100. При невозможности парса – -1.
    """
    # Пример строки:
    # /dev/block/dm-0   8.0G   5.4G   2.2G  71% /data
    for line in df_output.splitlines():
        if "/data" in line:
            m = re.search(r"(\d+)%\s*/data", line)
            if m:
                return int(m.group(1))
    # Если не нашли – попытка через dumpsys storage
    m = re.search(r"Total:\s*([\d\.]+)([KMG]?)\s*Used:\s*([\d\.]+)([KMG]?)", df_output)
    if m:
        # Приводим к мегабайтам (приблизительно)
        total_val, total_unit, used_val, used_unit = m.groups()
        units = {"": 1, "K": 1 / 1024, "M": 1, "G": 1024}
        total_mb = float(total_val) * units.get(total_unit.upper(), 1)
        used_mb = float(used_val) * units.get(used_unit.upper(), 1)
        if total_mb > 0:
            return int(used_mb / total_mb * 100)
    return -1


def _color_for_percent(percent: int) -> str:
    """
    Возвращает строку CSS‑цвета (rgb) для заданного процента.
    0 % → #00ff00 (зелёный)
    50 % → #ffff00 (жёлтый)
    100 % → #ff0000 (красный)
    """
    # Линейный переход зелёный → жёлтый → красный
    if percent < 0:
        percent = 0
    if percent > 100:
        percent = 100

    if percent <= 50:
        # от зелёного к жёлтому: R растёт от 0 до 255, G остаётся 255
        r = int(255 * percent / 50)
        g = 255
    else:
        # от жёлтого к красному: G падает от 255 до 0, R остаётся 255
        r = 255
        g = int(255 * (100 - percent) / 50)

    return f"rgb({r},{g},0)"


# ----------------------------------------------------------------------
#   Диалоговое окно
# ----------------------------------------------------------------------
class RomUsageDialog(QDialog):
    """
    Диалог с прогресс‑баром, показывающим заполненность ROM.
    Кнопка «Обновить» перечитывает данные.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self.setWindowTitle("Заполненность ROM")
        self.setMinimumSize(340, 150)

        self.main_window = main_window

        self.layout = QVBoxLayout(self)

        self.info_label = QLabel("Запрашивается информация…")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.info_label)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress.setRange(0, 100)
        self.layout.addWidget(self.progress)

        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh)
        self.layout.addWidget(self.refresh_btn)

        # Первичное обновление сразу после создания окна
        QTimer.singleShot(100, self.refresh)

    def refresh(self):
        """Запросить процент использования ROM и отобразить."""
        self.info_label.setText("Чтение данных с устройства…")
        self.refresh_btn.setEnabled(False)

        # 1️⃣  Получаем вывод df -h /data
        raw = _run_adb(self.main_window, "shell df -h /data")
        if not raw:
            # Если df не дал результата, пробуем dumpsys storage
            raw = _run_adb(self.main_window, "shell dumpsys storage")
        percent = _parse_rom_percent(raw)

        if percent < 0:
            self.info_label.setText("Не удалось определить заполненность ROM")
            self.progress.setValue(0)
            self.progress.setStyleSheet("")
        else:
            self.info_label.setText(f"Заполнено {percent}%")
            self.progress.setValue(percent)

            # Меняем цвет полоски в соответствии с процентом
            color = _color_for_percent(percent)
            self.progress.setStyleSheet(
                f"""
                QProgressBar {{
                    border: 1px solid #777;
                    border-radius: 5px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    width: 10px;
                }}
                """
            )
        self.refresh_btn.setEnabled(True)


# ----------------------------------------------------------------------
#   Поиск нужного меню в строке меню (по названию)
# ----------------------------------------------------------------------
def _find_menu_by_title(main_window, title: str):
    """
    Ищет QMenu в menubar, у которого title (без '&') совпадает
    (регистр игнорируется). Возвращает QMenu либо None.
    """
    menubar = main_window.menuBar()
    for menu in menubar.findChildren(QMenu):
        if menu.title().replace("&", "").strip().lower() == title.lower():
            return menu
    return None


# ----------------------------------------------------------------------
#   Регистрация плагина
# ----------------------------------------------------------------------
def register(main_window):
    """
    Добавляет пункт «ROM‑Usage» в меню «Инструменты» и открывает
    диалог RomUsageDialog при его выборе.
    """
    tools_menu = _find_menu_by_title(main_window, "Инструменты")
    if tools_menu is None:
        # Если по какой‑то причине меню «Инструменты» не найдено,
        # выводим сообщение в лог и завершаем регистрацию.
        main_window.log_message("[ROM‑Usage] Меню «Инструменты» не найдено, плагин не будет загружен.")
        return

    action = QAction("ROM‑Usage", main_window)
    action.triggered.connect(lambda: RomUsageDialog(main_window).exec())
    tools_menu.addSeparator()
    tools_menu.addAction(action)

    main_window.log_message("[ROM‑Usage] Плагин загружен – пункт «ROM‑Usage» добавлен в меню «Инструменты».")
