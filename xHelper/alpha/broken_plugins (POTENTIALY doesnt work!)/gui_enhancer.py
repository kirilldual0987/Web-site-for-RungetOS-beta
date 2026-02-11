# plugins/gui_enhancer.py
# -*- coding: utf-8 -*-

"""
gui_enhancer – плагин‑модуль для улучшения внешнего вида xHelper.

Он:
 • задаёт тёмную палитру (если пользователь её ещё не включил);
 • накладывает современный QSS‑стиль (округлые кнопки, градиенты);
 • добавляет верхнюю QToolBar с быстрыми действиями;
 • перестраивает центральный layout в QSplitter (вкладки ↕ консоль);
 • показывает небольшое сообщение‑информер о трансформации UI.

Плагин полностью автономен – работает даже если у `XHelperMainWindow`
отсутствуют такие атрибуты, как `settings`, `backup_tab` и т.п.;
все необходимые элементы ищутся динамически.
"""

import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QAction
from PyQt6.QtWidgets import (
    QToolBar, QSplitter, QStyle, QMessageBox,
    QFontDialog, QProgressBar
)


# ----------------------------------------------------------------------
#   Утилита: поиск вкладки по её заголовку
# ----------------------------------------------------------------------
def _find_tab_by_title(main_window, title):
    """Возвращает виджет‑вкладку, у которой `tabText == title`."""
    for i in range(main_window.tabs.count()):
        if main_window.tabs.tabText(i) == title:
            return main_window.tabs.widget(i)
    return None


# ----------------------------------------------------------------------
#   Тёмная палитра (если пользователь её ещё не включил)
# ----------------------------------------------------------------------
def _ensure_dark_palette(main_window):
    # Если в окне уже есть атрибут settings → проверяем флаг
    dark_requested = getattr(main_window, "settings", {}).get("theme_dark", False)
    if dark_requested:
        return

    # Простейшая тёмная палитра, не сохраняем в конфиг
    dark = main_window.palette()
    dark.setColor(dark.ColorRole.Window, Qt.GlobalColor.black)
    dark.setColor(dark.ColorRole.WindowText, Qt.GlobalColor.white)
    dark.setColor(dark.ColorRole.Base, Qt.GlobalColor.black)
    dark.setColor(dark.ColorRole.AlternateBase, Qt.GlobalColor.darkGray)
    dark.setColor(dark.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark.setColor(dark.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark.setColor(dark.ColorRole.Text, Qt.GlobalColor.white)
    dark.setColor(dark.ColorRole.Button, Qt.GlobalColor.darkGray)
    dark.setColor(dark.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark.setColor(dark.ColorRole.BrightText, Qt.GlobalColor.red)
    dark.setColor(dark.ColorRole.Link, Qt.GlobalColor.cyan)
    dark.setColor(dark.ColorRole.Highlight, Qt.GlobalColor.cyan)
    dark.setColor(dark.ColorRole.HighlightedText, Qt.GlobalColor.black)
    main_window.setPalette(dark)


# ----------------------------------------------------------------------
#   QSS‑стиль (полностью встроен)
# ----------------------------------------------------------------------
_QSS = r"""
/* Универсальный шрифт */
* {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 10pt;
}

/* Кнопки */
QPushButton {
    background-color: #3a3a3a;
    color: #e0e0e0;
    border: 1px solid #555;
    border-radius: 6px;
    padding: 4px 12px;
    min-height: 24px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:pressed { background-color: #2a2a2a; }

/* Списки и таблицы */
QListWidget, QTableWidget {
    background-color: #252525;
    border: 1px solid #444;
}

/* Вкладки */
QTabBar::tab {
    background: #2c2c2c;
    color: #c0c0c0;
    padding: 6px 12px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #3d3d3d;
    color: #ffffff;
}

/* Поля ввода */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #1e1e1e;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 2px 4px;
    color: #e0e0e0;
}

/* Прогресс‑бар */
QProgressBar {
    background-color: #1e1e1e;
    border: 1px solid #555;
    border-radius: 5px;
    text-align: center;
    color: #e0e0e0;
}
QProgressBar::chunk { background-color: #00aaff; border-radius: 5px; }

/* Toolbar */
QToolBar {
    background: #2b2b2b;
    spacing: 4px;
    padding: 2px;
}
QToolButton { background: transparent; border: none; margin: 0px; }
QToolButton:hover { background: #3a3a3a; }
"""


# ----------------------------------------------------------------------
#   Основная регистрационная функция, вызываемая XHelperMainWindow.load_plugins()
# ----------------------------------------------------------------------
def register(main_window):
    """Перестраивает GUI, добавляя стили и тулбар."""
    # --------------------------------------------------------------
    # 1️⃣  Тёмная палитра + QSS‑стиль
    # --------------------------------------------------------------
    _ensure_dark_palette(main_window)
    main_window.setStyleSheet(_QSS)

    # --------------------------------------------------------------
    # 2️⃣  Создаём QToolBar с типовыми действиями
    # --------------------------------------------------------------
    toolbar = QToolBar("Main Toolbar", main_window)
    toolbar.setMovable(False)
    toolbar.setIconSize(QSize(20, 20))
    main_window.addToolBar(toolbar)

    style = main_window.style()

    # ---------- Refresh devices ----------
    act_refresh = QAction(
        style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
        "Обновить список устройств", main_window
    )
    act_refresh.triggered.connect(main_window.get_devices)
    toolbar.addAction(act_refresh)

    # ---------- Logcat ----------
    # Ищем вкладку Logcat по заголовку, если прямой ссылки нет
    logcat_tab = getattr(main_window, "logcat_tab", None) or \
                 _find_tab_by_title(main_window, "Логи")
    act_logcat = QAction(
        style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
        "Logcat", main_window
    )
    if logcat_tab:
        act_logcat.triggered.connect(lambda: main_window.tabs.setCurrentWidget(logcat_tab))
    else:
        act_logcat.setEnabled(False)
    toolbar.addAction(act_logcat)

    # ---------- Scrcpy (toggle) ----------
    act_scrcpy = QAction(
        style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
        "Scrcpy", main_window
    )
    act_scrcpy.setCheckable(True)

    def _toggle_scrcpy(checked):
        if checked:
            if hasattr(main_window, "start_screen_stream"):
                main_window.start_screen_stream()
                act_scrcpy.setIcon(
                    style.standardIcon(QStyle.StandardPixmap.SP_MediaStop)
                )
                act_scrcpy.setText("Stop Scrcpy")
            else:
                QMessageBox.warning(main_window, "Ошибка",
                                    "Метод start_screen_stream() не найден")
                act_scrcpy.setChecked(False)
        else:
            if hasattr(main_window, "stop_screen_stream"):
                main_window.stop_screen_stream()
                act_scrcpy.setIcon(
                    style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
                )
                act_scrcpy.setText("Scrcpy")
            else:
                QMessageBox.warning(main_window, "Ошибка",
                                    "Метод stop_screen_stream() не найден")
                act_scrcpy.setChecked(True)

    act_scrcpy.toggled.connect(_toggle_scrcpy)
    toolbar.addAction(act_scrcpy)

    # ---------- Backup / Restore ----------
    backup_tab = _find_tab_by_title(main_window, "Бэкап / Восстановление") or \
                 _find_tab_by_title(main_window, "Backup / Restore")
    act_backup = QAction(
        # В Qt6 правильный элемент – SP_DriveHDIcon (не SP_DriveFD)
        style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon),
        "Бэкап / Восстановление", main_window
    )
    if backup_tab:
        act_backup.triggered.connect(lambda: main_window.tabs.setCurrentWidget(backup_tab))
    else:
        act_backup.setEnabled(False)
    toolbar.addAction(act_backup)

    # ---------- Settings ----------
    settings_tab = _find_tab_by_title(main_window, "Настройки") or \
                   _find_tab_by_title(main_window, "Settings")
    act_settings = QAction(
        style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon),
        "Настройки", main_window
    )
    if settings_tab:
        act_settings.triggered.connect(lambda: main_window.tabs.setCurrentWidget(settings_tab))
    else:
        act_settings.setEnabled(False)
    toolbar.addAction(act_settings)

    toolbar.addSeparator()

    # --------------------------------------------------------------
    # 3️⃣  Перестраиваем центральный layout (Splitter)
    # --------------------------------------------------------------
    central = main_window.centralWidget()
    old_layout = central.layout()
    while old_layout.count():
        it = old_layout.takeAt(0)
        w = it.widget()
        if w:
            w.setParent(None)

    splitter = QSplitter(Qt.Orientation.Vertical)
    splitter.setHandleWidth(4)                # более заметный «ползунок»
    splitter.addWidget(main_window.tabs)      # сверху – набор табов
    splitter.addWidget(main_window.console)   # снизу – консоль‑лог

    # 70 % / 30 % по умолчанию
    total_h = main_window.height() if main_window.height() > 0 else 800
    splitter.setSizes([int(total_h * 0.7), int(total_h * 0.3)])

    old_layout.addWidget(splitter)

    # --------------------------------------------------------------
    # 4️⃣  Немного «подгонки» уже существующих виджетов
    # --------------------------------------------------------------
    mono_font = QFont("Consolas", 10)
    mono_font.setStyleHint(QFont.StyleHint.Monospace)
    main_window.console.setFont(mono_font)

    # --------------------------------------------------------------
    # 5️⃣  Информируем пользователя о трансформации UI
    # --------------------------------------------------------------
    QMessageBox.information(
        main_window,
        "UI‑enhancer",
        "Интерфейс был обновлён:\n\n"
        "• Тёмный стиль и современный QSS;\n"
        "• Верхняя панель быстрого доступа;\n"
        "• Вкладки и консоль разделены ползунком.\n\n"
        "Если хотите вернуть оригинальный вид, удалите файл "
        "`plugins/gui_enhancer.py` и перезапустите приложение.",
        QMessageBox.StandardButton.Ok,
    )

    # --------------------------------------------------------------
    # 6️⃣  Сохраняем ссылки для возможного дальнейшего использования
    # --------------------------------------------------------------
    main_window.enhanced_splitter = splitter
    main_window.enhanced_toolbar  = toolbar
