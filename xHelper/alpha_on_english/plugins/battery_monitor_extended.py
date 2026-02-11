# -*- coding: utf-8 -*-
"""
Battery Monitor plugin for xHelper α‑1.0.1.

Adds a dock widget that shows:
  • Battery level (progress bar)
  • Voltage (V)
  • Temperature (°C)
  • Current status (Charging/Discharging/…)

The widget refreshes automatically (default: every 30 s) and can be
updated manually with a button. All errors are logged via
main_window.log_message().
"""

import subprocess
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QLabel,
    QProgressBar, QPushButton
)
from PyQt6.QtCore import Qt, QTimer


# ----------------------------------------------------------------------
#   Вспомогательные функции
# ----------------------------------------------------------------------
def _parse_battery_output(output: str) -> dict:
    """
    Преобразует вывод ``adb shell dumpsys battery`` в словарь.
    Пример строки: ``level: 85`` → {'level': 85, ...}
    """
    data = {}
    for line in output.splitlines():
        if ':' not in line:
            continue
        key, val = line.split(':', 1)
        data[key.strip().lower()] = val.strip()

    # Приводим к нужным типам (если что‑то не найдено – ставим -1)
    level = int(data.get('level', -1))
    voltage = int(data.get('voltage', -1)) // 1000 if data.get('voltage') else -1
    # temperature в 0.1 °C → делим на 10
    temperature = int(data.get('temperature', -1)) / 10 if data.get('temperature') else -1
    status = data.get('status', 'UNKNOWN')

    return {
        'level': level,
        'voltage': voltage,
        'temperature': temperature,
        'status': status,
    }


def _fetch_battery(main_window) -> dict:
    """
    Выполняет ``adb shell dumpsys battery`` и возвращает словарь.
    Если возникла ошибка – пишет в лог и возвращает пустой dict.
    """
    # Путь к adb может быть переопределён в настройках xHelper
    adb = (
        main_window.settings.get('adb_path', 'adb')
        if hasattr(main_window, 'settings') else 'adb'
    )
    try:
        out = subprocess.check_output(
            [adb, 'shell', 'dumpsys', 'battery'],
            text=True,
            timeout=5,
        )
        return _parse_battery_output(out)
    except Exception as e:
        main_window.log_message(f"[BatteryMonitor] Ошибка чтения батареи: {e}")
        return {}


def _update_ui(main_window, widgets: dict):
    """
    Считывает текущие данные о батарее и заполняет UI‑элементы.
    `widgets` – словарь, в котором хранятся ссылки на нужные виджеты.
    """
    data = _fetch_battery(main_window)
    if not data:
        return

    level = data['level']
    voltage = data['voltage']
    temp = data['temperature']
    status = data['status']

    # ‑‑‑ progress bar
    widgets['progress'].setValue(level)
    # ‑‑‑ цветовая индикация
    if level >= 80:
        color = "#4caf50"      # зелёный
    elif level >= 30:
        color = "#ffeb3b"      # жёлтый
    else:
        color = "#f44336"      # красный
    widgets['progress'].setStyleSheet(
        f"QProgressBar::chunk {{background-color: {color};}}"
    )

    # ‑‑‑ текстовые метки
    widgets['lbl_level'].setText(f"Уровень: {level}%")
    widgets['lbl_voltage'].setText(
        f"Напряжение: {voltage} V" if voltage != -1 else "Напряжение: —"
    )
    widgets['lbl_temp'].setText(
        f"Температура: {temp:.1f} °C" if temp != -1 else "Температура: —"
    )
    widgets['lbl_status'].setText(f"Состояние: {status}")


# ----------------------------------------------------------------------
#   Точка входа плагина
# ----------------------------------------------------------------------
def register(main_window):
    """
    Регистрация плагина – вызывается автоматически при старте xHelper.
    Добавляем dock‑виджет, таймер обновления и кнопку ручного refresh.
    """
    # === UI ------------------------------------------------------------
    battdock = QDockWidget("Battery Monitor", main_window)
    battdock.setAllowedAreas(
        Qt.DockWidgetArea.AllDockWidgetAreas
    )

    # контейнер‑виджет внутри dock
    container = QWidget()
    vbox = QVBoxLayout(container)
    vbox.setContentsMargins(8, 8, 8, 8)
    vbox.setSpacing(6)

    # – индикатор уровня
    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setFormat("%p%")
    progress.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # – метки
    lbl_level   = QLabel("Уровень: —")
    lbl_voltage = QLabel("Напряжение: —")
    lbl_temp    = QLabel("Температура: —")
    lbl_status  = QLabel("Состояние: —")

    # – кнопка ручного обновления
    btn_refresh = QPushButton("Обновить сейчас")
    # клик → мгновенное обновление
    btn_refresh.clicked.connect(
        lambda: _update_ui(main_window, widgets)
    )

    # собрать все элементы
    vbox.addWidget(progress)
    vbox.addWidget(lbl_level)
    vbox.addWidget(lbl_voltage)
    vbox.addWidget(lbl_temp)
    vbox.addWidget(lbl_status)
    vbox.addStretch()
    vbox.addWidget(btn_refresh)

    battdock.setWidget(container)
    # разместить справа (можно изменить на любой угол)
    main_window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, battdock)

    # сохраняем ссылки, чтобы таймер мог их использовать
    widgets = {
        'progress':   progress,
        'lbl_level':  lbl_level,
        'lbl_voltage': lbl_voltage,
        'lbl_temp':    lbl_temp,
        'lbl_status':  lbl_status,
    }

    # === Таймер обновления (30 сек.) ================================
    timer = QTimer(main_window)
    timer.setInterval(30_000)           # 30 000 мс = 30 сек.
    timer.timeout.connect(lambda: _update_ui(main_window, widgets))
    timer.start()

    # Первый запрос сразу после загрузки плагина
    _update_ui(main_window, widgets)

    # Информируем пользователя в основной лог
    main_window.log_message("[BatteryMonitor] Плагин загружен, авто‑обновление каждые 30 сек.")
