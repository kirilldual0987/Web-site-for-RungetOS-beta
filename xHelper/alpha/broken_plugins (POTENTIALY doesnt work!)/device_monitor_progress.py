# plugins/device_monitor_progress.py
# -*- coding: utf-8 -*-

"""
device_monitor_progress – панель «Монитор (прогресс)».

Показывает в реальном времени:
 • CPU‑нагрузку   (процент)
 • ОЗУ‑занятость  (процент)
 • Уровень батареи (%)
 • Сигнал Wi‑Fi   (RSSI → %)

Все данные собираются через adb‑команды, обновляются каждые 2 сек.
"""

import subprocess
import re
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QProgressBar, QLabel,
    QHBoxLayout, QMessageBox
)


def _run_adb(main_window, cmd):
    """Утилита – выполнить команду adb и вернуть stdout."""
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        out = subprocess.check_output(
            [adb] + cmd.split(),
            text=True,
            timeout=5
        )
        return out
    except Exception as e:
        return ""


def register(main_window):
    """Создаёт вкладку «Монитор (прогресс)» и запускает таймер обновления."""
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # --------------------------------------------------------------
    #   Создаём 4 progress‑бара
    # --------------------------------------------------------------
    def bar_item(name: str):
        """Вернёт (label, progress‑bar)."""
        hb = QHBoxLayout()
        lbl = QLabel(name)
        lbl.setMinimumWidth(80)
        prog = QProgressBar()
        prog.setRange(0, 100)
        prog.setTextVisible(True)
        hb.addWidget(lbl)
        hb.addWidget(prog, 1)
        layout.addLayout(hb)
        return prog

    cpu_bar      = bar_item("CPU")
    mem_bar      = bar_item("RAM")
    bat_bar      = bar_item("Battery")
    wifi_bar     = bar_item("Wi‑Fi")

    # --------------------------------------------------------------
    #   Функции получения данных
    # --------------------------------------------------------------
    def get_cpu():
        """Пытаемся получить среднюю загрузку CPU через top."""
        out = _run_adb(main_window, "shell top -b -n 1 -d 0.5")
        # строка вида «%CPU USER …» – ищем первое число с «%» после «%CPU»
        match = re.search(r"%CPU\s+(\d+\.\d+)", out)
        if match:
            return float(match.group(1))
        # fallback – используем dumpsys cpuinfo (можно, но тяжелее)
        out = _run_adb(main_window, "shell dumpsys cpuinfo")
        m = re.search(r"Total\s+(\d+)%", out)
        return float(m.group(1)) if m else 0.0

    def get_mem():
        """% занятости ОЗУ = (Total‑Free)/Total."""
        out = _run_adb(main_window, "shell cat /proc/meminfo")
        total = free = None
        for line in out.splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemFree:"):
                free = int(line.split()[1])
        if total and free:
            used = total - free
            return used / total * 100.0
        return 0.0

    def get_battery():
        out = _run_adb(main_window, "shell dumpsys battery")
        for line in out.splitlines():
            if "level:" in line:
                return float(line.split(":")[1].strip())
        return 0.0

    def get_wifi():
        """RSSI в диапазоне -100…0 → переводим в %."""
        out = _run_adb(main_window, "shell dumpsys wifi")
        m = re.search(r"RSSI:\s*(-?\d+)", out)
        if m:
            rssi = int(m.group(1))
            # -100 → 0 %, 0 → 100 %
            return max(0, min(100, (rssi + 100)))
        return 0

    # --------------------------------------------------------------
    #   Таймер обновления
    # --------------------------------------------------------------
    timer = QTimer(main_window)
    timer.setInterval(2000)  # 2 сек

    def refresh():
        """Обновляем все бары, выводим сообщения в консоль."""
        try:
            cpu = get_cpu()
            mem = get_mem()
            bat = get_battery()
            wifi = get_wifi()

            cpu_bar.setValue(int(cpu))
            mem_bar.setValue(int(mem))
            bat_bar.setValue(int(bat))
            wifi_bar.setValue(int(wifi))

            # Информируем о неудачах (например, отсутствие устройства)
            if any(v == 0 for v in (cpu, mem, bat, wifi)):
                main_window.log_message("[Монитор] Похоже, устройство не подключено")
        except Exception as exc:
            main_window.log_message(f"[Монитор] Ошибка обновления: {exc}")

    timer.timeout.connect(refresh)
    timer.start()
    refresh()                     # первый запуск сразу

    # --------------------------------------------------------------
    #   Добавляем вкладку в главное окно
    # --------------------------------------------------------------
    main_window.tabs.addTab(tab, "Монитор (прогресс)")
