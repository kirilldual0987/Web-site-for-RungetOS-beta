# plugins/temperature_monitor.py
# -*- coding: utf-8 -*-

"""
temperature_monitor – отображает температуру Android‑устройства.

Поддерживает любые датчики, выводимые `adb shell dumpsys thermalservice`.
Если температура превышает заданный порог (по умолчанию 45 °C) – бар подсвечивается красным.
"""

import subprocess
import re
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QProgressBar, QLabel,
    QMessageBox, QHBoxLayout
)


def _run_adb(main_window, cmd):
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        out = subprocess.check_output([adb] + cmd.split(), text=True, timeout=5)
        return out
    except Exception:
        return ""


def register(main_window):
    tab = QWidget()
    vbox = QVBoxLayout(tab)

    # --------------------------------------------------------------
    #   Создаём один (или несколько) прогресс‑баров
    # --------------------------------------------------------------
    temp_bars = []      # список (label, bar, threshold)

    def add_bar(name: str, threshold: int = 45):
        hb = QHBoxLayout()
        lbl = QLabel(name)
        lbl.setMinimumWidth(150)
        bar = QProgressBar()
        bar.setRange(0, 150)                # температура в градусах Цельсия
        bar.setFormat("%v°C")
        hb.addWidget(lbl)
        hb.addWidget(bar, 1)
        vbox.addLayout(hb)
        temp_bars.append((name, bar, threshold))

    # По умолчанию создаём один бар «CPU», но при наличии нескольких датчиков
    # будет добавлен ещё один (по‑многим датчикам сразу).
    add_bar("CPU")

    # --------------------------------------------------------------
    #   Обновление температуры
    # --------------------------------------------------------------
    timer = QTimer(main_window)
    timer.setInterval(3000)          # каждые 3 сек

    def refresh():
        out = _run_adb(main_window, "shell dumpsys thermalservice")
        # Пример строки: "Thermal status: 0x0 (0) | 41.0C (CPU-0)"
        matches = re.findall(r"(\d+(?:\.\d+)?)C\s*\(([^)]+)\)", out)
        if not matches:
            main_window.log_message("[Temp] Не удалось получить температуру")
            return

        # Сопоставляем найденные датчики с уже построенными бар‑ами
        for i, (value, sensor) in enumerate(matches):
            temp = float(value)
            if i >= len(temp_bars):
                add_bar(sensor)          # добавляем новый бар, если датчик новый
            name, bar, thresh = temp_bars[i]
            bar.setMaximum(150)
            bar.setValue(int(temp))
            # цветовая индикация
            if temp >= thresh:
                bar.setStyleSheet("QProgressBar::chunk {background: red;}")
            else:
                bar.setStyleSheet("QProgressBar::chunk {background: #00aaff;}")

    timer.timeout.connect(refresh)
    timer.start()
    refresh()

    main_window.tabs.addTab(tab, "Температура")
