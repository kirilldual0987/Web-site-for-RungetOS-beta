# plugins/type_text_on_device.py
# -*- coding: utf-8 -*-

"""
type_text_on_device – плагин для xHelper.

Он добавляет отдельную вкладку «Клавиатура», где пользователь может
ввести произвольный текст (включая русские буквы) и отправить его
на подключённое Android‑устройство через ADB‑команду:

    adb shell input text "<текст>"

Пробелы автоматически заменяются на %s, как требует `adb shell input text`.
После ввода текста (по желанию) посылается клавиша Enter (KEYCODE_ENTER).

Плагин полностью автономен: использует только публичный API главного окна
(`main_window.run_adb_command`, `main_window.log_message`, `main_window.tabs`),
не меняет ядра программы и не требует дополнительных зависимостей.
"""

import subprocess
import re
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox, QHBoxLayout
)


# ----------------------------------------------------------------------
#   Внутренняя функция – отправка текста через adb
# ----------------------------------------------------------------------
def _send_text_via_adb(main_window, raw_text: str):
    """
    Преобразует произвольный текст в форму, пригодную для команды
    `adb shell input text`, и отправляет её.

    1) Пробелы → %s (требуется ADB).  
    2) Удаляем только кавычки – они могут спровоцировать ошибки в
       командной строке.  Русские буквы и любые другие Unicode‑символы
       оставляем без изменений (adb передаёт их в UTF‑8).  
    3) После ввода посылаем клавишу Enter (KEYCODE_ENTER) – удобно,
       когда нужно «подтвердить» ввод.

    Пишет сообщения в лог (`main_window.log_message`).
    """
    # ------------------------------------------------------------------
    #   1️⃣  Очистка и экранирование
    # ------------------------------------------------------------------
    text = raw_text.strip()

    # Удаляем одинарные и двойные кавычки – они могут «сломать» команду.
    # Важно НЕ удалять русские буквы и другие Unicode‑символы.
    text = text.replace("'", "").replace('"', '')

    # Пробелы → %s (ADB‑правило)
    text = text.replace(' ', '%s')

    if not text:
        main_window.log_message("[Keyboard] Пустой ввод – ничего не отправлено")
        return

    # ------------------------------------------------------------------
    #   2️⃣  Выполняем adb‑команду без shell (чтобы сохранить Unicode)
    # ------------------------------------------------------------------
    adb = (
        main_window.settings.get("adb_path", "adb")
        if hasattr(main_window, "settings")
        else "adb"
    )
    cmd = [adb, "shell", "input", "text", text]

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7,
            check=True      # бросит исключение, если код выхода != 0
        )
        main_window.log_message(f"[Keyboard] Текст отправлен: {raw_text}")
    except subprocess.CalledProcessError as e:
        main_window.log_message(f"[Keyboard] Ошибка adb: {e.stderr or e}")
        QMessageBox.critical(
            None,
            "ADB‑ошибка",
            f"Не удалось отправить текст.\n\n{e.stderr or e}"
        )
        return
    except Exception as exc:
        main_window.log_message(f"[Keyboard] Неожиданное исключение: {exc}")
        QMessageBox.critical(
            None,
            "Ошибка",
            f"Не удалось отправить текст.\n\n{exc}"
        )
        return
    else:
        # По желанию сразу нажимаем Enter (KEYCODE_ENTER = 66)
        subprocess.run(
            [adb, "shell", "input", "keyevent", "66"],
            capture_output=True,
            text=True
        )


# ----------------------------------------------------------------------
#   Регистрация плагина
# ----------------------------------------------------------------------
def register(main_window):
    """
    Добавляет новую вкладку «Клавиатура» в основной QTabWidget.
    Вкладка состоит из:
        • QTextEdit – многострочное поле ввода;
        • Кнопка «Отправить» – отправка текста на устройство;
        • Кнопка «Очистить» – очистка поля ввода.
    """
    # --------------------- UI‑элементы ---------------------
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # Инструкция
    hint = QLabel(
        "Введите любой текст (русские буквы поддерживаются) и нажмите «Отправить». "
        "Текст будет «напечатан» на Android‑устройстве. Пробелы автоматически "
        "заменяются на %s, а после ввода будет нажата клавиша Enter."
    )
    hint.setWordWrap(True)
    layout.addWidget(hint)

    # Текстовое поле
    txt_edit = QTextEdit()
    txt_edit.setPlaceholderText(
        "Введите здесь русский или любой другой текст..."
    )
    txt_edit.setMaximumHeight(200)
    layout.addWidget(txt_edit)

    # Кнопки управления
    btn_layout = QHBoxLayout()
    btn_send = QPushButton("Отправить")
    btn_clear = QPushButton("Очистить")
    btn_layout.addWidget(btn_send)
    btn_layout.addWidget(btn_clear)
    btn_layout.addStretch()
    layout.addLayout(btn_layout)

    # --------------------- Логика ---------------------
    def on_send():
        """Обработчик нажатия «Отправить»."""
        text = txt_edit.toPlainText()
        if not text.strip():
            QMessageBox.information(tab, "Пустой ввод", "Введите хотя бы один символ.")
            return

        # Если пользователь ввёл несколько строк – отправляем их последовательно
        for line in text.splitlines():
            _send_text_via_adb(main_window, line)

        QMessageBox.information(tab, "Готово", "Текст отправлен на устройство.")

    def on_clear():
        txt_edit.clear()

    btn_send.clicked.connect(on_send)
    btn_clear.clicked.connect(on_clear)

    # --------------------- Добавляем во вкладки ---------------------
    main_window.tabs.addTab(tab, "Клавиатура")
    main_window.log_message("[Keyboard] Плагин загружен – вкладка «Клавиатура» добавлена.")
