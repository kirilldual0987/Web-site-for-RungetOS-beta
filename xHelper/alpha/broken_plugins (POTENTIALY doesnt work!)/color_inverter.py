# plugins/color_inverter.py
# -*- coding: utf-8 -*-

"""
color_inverter – плагин, который добавляет пункт «Инвертировать цвета» в меню
«Вид» и отдельную кнопку‑переключатель в строке меню (рядом с пунктом «Вид»).

Работает без изменения основного кода xHelper. При включении все цвета
интерфейса инвертируются (255‑R, 255‑G, 255‑B), при выключении – восстанавливается
исходная палитра, запомненная при первом переключении.
"""

import sys
from typing import Optional

from PyQt6.QtGui import (
    QAction,          # QAction находится в QtGui в PyQt6
    QPalette,
    QColor,
    QIcon,
    QStyle,
)
from PyQt6.QtWidgets import (
    QMenu,
    QApplication,
    QPushButton,
    QWidgetAction,
    QStyleOption,
)

# ----------------------------------------------------------------------
#   Вспомогательные функции
# ----------------------------------------------------------------------
def _invert_color(col: QColor) -> QColor:
    """Вернуть инвертированный цвет (255‑R, 255‑G, 255‑B)."""
    return QColor(255 - col.red(), 255 - col.green(), 255 - col.blue(), col.alpha())


def _create_inverted_palette(src: QPalette) -> QPalette:
    """Создать палитру, где каждый используемый цвет инвертирован."""
    inv = QPalette()
    # Перебираем набор ролей, обычно используемых в приложениях.
    roles = [
        QPalette.ColorRole.Window,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.ToolTipBase,
        QPalette.ColorRole.ToolTipText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.BrightText,
        QPalette.ColorRole.Link,
        QPalette.ColorRole.Highlight,
        QPalette.ColorRole.HighlightedText,
    ]
    for role in roles:
        inv.setColor(role, _invert_color(src.color(role)))
    return inv


def _toggle_inversion(main_window, checked: bool):
    """
    Включить/выключить инверсию.
        checked = True  → включить;
        checked = False → вернуть обычную палитру.
    """
    # Сохраняем оригинальную палитру только один раз.
    if not hasattr(main_window, "_orig_palette"):
        main_window._orig_palette = QApplication.instance().palette()
        main_window._inv_palette = _create_inverted_palette(main_window._orig_palette)

    app = QApplication.instance()
    if checked:
        app.setPalette(main_window._inv_palette)
        main_window.log_message("[UI‑Inverter] Инверсия включена")
    else:
        app.setPalette(main_window._orig_palette)
        main_window.log_message("[UI‑Inverter] Инверсия отключена")


def _find_view_menu(main_window) -> Optional[QMenu]:
    """
    Ищет в меню‑баре пункт с заголовком «Вид» (RU) или «View» (EN).
    Возвращает объект QMenu или None.
    """
    menubar = main_window.menuBar()
    for menu in menubar.findChildren(QMenu):
        title = menu.title().replace("&", "").strip().lower()
        if title in ("вид", "view"):
            return menu
    return None


# ----------------------------------------------------------------------
#   Регистрация плагина
# ----------------------------------------------------------------------
def register(main_window):
    """
    Добавляет в меню «Вид» пункт «Инвертировать цвета» и кнопку‑переключатель
    в строке меню (рядом с пунктом «Вид»).
    """
    view_menu = _find_view_menu(main_window)
    if view_menu is None:
        main_window.log_message("[UI‑Inverter] Не найдено меню «Вид». Плагин не будет загружен.")
        return

    # --------------------------------------------------------------
    #   1️⃣ Пункт меню «Инвертировать цвета»
    # --------------------------------------------------------------
    invert_action = QAction("Инвертировать цвета", main_window)
    invert_action.setCheckable(True)
    invert_action.triggered.connect(lambda ch: _toggle_inversion(main_window, ch))

    # Добавляем в конец меню «Вид» (с разделителем)
    view_menu.addSeparator()
    view_menu.addAction(invert_action)

    # --------------------------------------------------------------
    #   2️⃣ Кнопка‑переключатель в строке меню
    # --------------------------------------------------------------
    # QPushButton, действующий как чек‑кнопка
    btn = QPushButton("Invert Colors")
    btn.setCheckable(True)

    # Иконка‑обновление (на любой вкус, берём стандартную из QStyle)
    style = main_window.style()
    btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))

    # Синхронизация: при переключении кнопки обновляем меню и палитру,
    # при переключении пункта меню – обновляем кнопку.
    btn.toggled.connect(
        lambda ch: (
            invert_action.setChecked(ch),                # пункт меню
            _toggle_inversion(main_window, ch)           # палитра
        )
    )
    invert_action.toggled.connect(btn.setChecked)  # обратная связь

    # Оборачиваем кнопку в QWidgetAction, чтобы её можно было добавить в QMenuBar
    btn_action = QWidgetAction(main_window)
    btn_action.setDefaultWidget(btn)

    # Добавляем кнопку в конец строки меню – она окажется рядом с пунктом «Вид».
    menubar = main_window.menuBar()
    menubar.addAction(btn_action)

    # --------------------------------------------------------------
    #   Информируем пользователя о загрузке
    # --------------------------------------------------------------
    main_window.log_message("[UI‑Inverter] Плагин загружен – пункт в меню «Вид» "
                            "и кнопка‑переключатель добавлены.")
