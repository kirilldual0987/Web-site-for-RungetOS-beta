# -*- coding: utf-8 -*-
"""
Плагин «Другие проекты» для xHelper.

Создаёт новую вкладку, в которой выводятся ссылки на
публичные Telegram‑каналы и сайт проекта.
"""

def register(main_window):
    """
    Точка входа плагина.
    `main_window` – уже запущенный XHelperMainWindow.
    """
    # ------------------- импорт внутри функции (без конфликтов) -------------------
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
    from PyQt6.QtGui import QFont
    from PyQt6.QtCore import Qt

    # ------------------- контейнер -------------------
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # ------------------- заголовок -------------------
    header = QLabel("наши другие проекты")
    header_font = QFont()
    header_font.setPointSize(18)   # большой шрифт
    header_font.setBold(True)
    header.setFont(header_font)
    header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(header)

    # ------------------- вспомогательная функция для ссылок -------------------
    def link_label(text: str, url: str) -> QLabel:
        """
        Возвращает QLabel с кликабельной ссылкой.
        """
        lbl = QLabel(f"<a href='{url}'>{text}</a>")
        lbl.setOpenExternalLinks(True)        # открывать в браузере
        font = QFont()
        font.setPointSize(14)                 # чуть меньше заголовка, но крупно
        lbl.setFont(font)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return lbl

    # ------------------- ссылки -------------------
    layout.addWidget(link_label(
        "Runget telegram channel",
        "https://t.me/runget_rt"
    ))
    layout.addWidget(link_label(
        "Dual gaming centre telegram channel",
        "https://t.me/DGC_off"
    ))
    layout.addWidget(link_label(
        "dual gaming centre",
        "https://kolyadual.github.io/dualgamingcentre/"
    ))

    # Заполняем оставшееся пространство, чтобы элементы выглядели аккуратно
    layout.addStretch()

    # ------------------- добавляем вкладку в главное окно -------------------
    main_window.tabs.addTab(tab, "Другие проекты")
