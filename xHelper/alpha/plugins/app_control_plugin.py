# plugins/app_control_plugin.py
# -*- coding: utf-8 -*-

"""
Плагин «App Control» – отключение и удаление произвольного приложения.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLineEdit,
    QPushButton, QLabel, QHBoxLayout, QMessageBox
)

def register(main_window):
    """
    Функция, вызываемая при загрузке плагина.
    Получает объект главного окна (XHelperMainWindow) и добавляет новую вкладку.
    """
    # ------------------------------------------------------------------
    #   UI‑часть плагина
    # ------------------------------------------------------------------
    tab = QWidget()
    tab_layout = QVBoxLayout(tab)

    # ----------------- ввод пакета -----------------
    pkg_input = QLineEdit()
    pkg_input.setPlaceholderText("Например: com.example.myapp")
    pkg_label = QLabel("Имя пакета:")

    # ----------------- кнопки -----------------
    btn_disable = QPushButton("Отключить приложение")
    btn_uninstall = QPushButton("Удалить приложение")

    # ----------------- обработчики -----------------
    def on_disable():
        pkg = pkg_input.text().strip()
        if not pkg:
            QMessageBox.warning(main_window, "Ошибка", "Введите имя пакета")
            return
        # pm disable‑user работает без root‑прав для пользовательских приложений
        main_window.run_adb_command(f"shell pm disable-user {pkg}", device_specific=True)

    def on_uninstall():
        pkg = pkg_input.text().strip()
        if not pkg:
            QMessageBox.warning(main_window, "Ошибка", "Введите имя пакета")
            return
        reply = QMessageBox.question(
            main_window,
            "Подтверждение",
            f"Вы действительно хотите удалить приложение\n{pkg} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            main_window.run_adb_command(f"uninstall {pkg}", device_specific=True)

    btn_disable.clicked.connect(on_disable)
    btn_uninstall.clicked.connect(on_uninstall)

    # ----------------- компоновка -----------------
    input_layout = QHBoxLayout()
    input_layout.addWidget(pkg_label)
    input_layout.addWidget(pkg_input)

    btn_layout = QHBoxLayout()
    btn_layout.addWidget(btn_disable)
    btn_layout.addWidget(btn_uninstall)

    group = QGroupBox("Управление отдельным приложением")
    group_layout = QVBoxLayout(group)
    group_layout.addLayout(input_layout)
    group_layout.addLayout(btn_layout)

    tab_layout.addWidget(group)

    # ------------------------------------------------------------------
    #   Добавляем вкладку в главный UI
    # ------------------------------------------------------------------
    main_window.tabs.addTab(tab, "Управление приложением")
