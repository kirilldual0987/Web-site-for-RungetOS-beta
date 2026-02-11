# plugins/usb_tethering.py
# -*- coding: utf-8 -*-


"""
USB Tethering Manager – плагин для включения/выключения режима USB‑модема.

Функции:
- Проверка текущего статуса USB‑модема
- Включение/выключение режима модема
- Отображение статуса подключения
- Логирование операций
"""


import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt



def _run_adb(main_window, cmd):
    """Выполнение ADB‑команды с обработкой ошибок."""
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        out = subprocess.check_output(
            [adb] + cmd.split(),
            text=True,
            timeout=5
        )
        return out.strip()
    except Exception as e:
        main_window.log_message(f"[USB Tethering] Ошибка ADB: {e}")
        return None


def _get_tethering_status(main_window):
    """Получение текущего статуса USB‑модема."""
    result = _run_adb(main_window, "shell settings get global tether_dns1")
    if result is None:
        return "Неизвестно"
    return "Включён" if result else "Выключен"


def _set_tethering(main_window, enable):
    """Включение/выключение USB‑модема."""
    cmd = "shell su -c 'svc usb setFunctions"
    if enable:
        cmd += " rndis,diag,adb'"
    else:
        cmd += " mtp,adb'"
    
    result = _run_adb(main_window, cmd)
    if result is not None:
        main_window.log_message(
            f"[USB Tethering] Режим {'включён' if enable else 'выключен'}"
        )

def register(main_window):
    """Регистрация плагина в главном окне."""
    # Создаём контейнер вкладки
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # Заголовок
    title = QLabel("<h2>USB‑модем</h2>")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)


    # Статус подключения
    status_label = QLabel("Статус: проверяется...")
    status_label.setStyleSheet("font-weight: bold;")
    layout.addWidget(status_label)

    # Описание функционала
    desc = QLabel(
        "Позволяет использовать телефон как USB‑модем.\n"
        "Для работы требуется подключение по USB и права root."
    )
    desc.setWordWrap(True)
    layout.addWidget(desc)


    # Кнопка управления
    toggle_btn = QPushButton("Включить USB‑модем")
    toggle_btn.setStyleSheet("padding: 10px;")
    layout.addWidget(toggle_btn)


    # Пространство для выравнивания
    layout.addStretch()


    # --- Логика работы ---
    def update_status():
        status = _get_tethering_status(main_window)
        status_label.setText(f"Статус: {status}")
        toggle_btn.setText(
            "Выключить USB‑модем" if status == "Включён" else "Включить USB‑модем"
        )

    def toggle_tethering():
        current_status = _get_tethering_status(main_window)
        if current_status == "Включён":
            _set_tethering(main_window, False)
        else:
            _set_tethering(main_window, True)
        update_status()

    # Связываем события
    toggle_btn.clicked.connect(toggle_tethering)


    # Первоначальная проверка статуса
    update_status()

    # Добавляем вкладку в интерфейс
    main_window.tabs.addTab(tab, "USB‑Модем")

    # Логируем загрузку
    main_window.log_message("[USB Tethering] Плагин загружен")
