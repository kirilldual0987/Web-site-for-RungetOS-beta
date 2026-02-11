#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xHelper alpha 1.0.1 LTS/ATS
GUI‑утилита для управления Android‑устройствами через ADB.
"""

import sys
import os
import subprocess
import threading
import time
import queue
import json
import re
import importlib.util
from datetime import datetime

# ---------- PyQt6 ----------
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QListWidget, QTextEdit,
    QLabel, QFileDialog, QMessageBox, QTabWidget,
    QGroupBox, QLineEdit, QGridLayout, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QSplitter,
    QCheckBox, QSpinBox, QComboBox, QTableWidget,
    QTableWidgetItem, QInputDialog, QMenu, QSystemTrayIcon,
    QStyle, QDialog, QDialogButtonBox, QFormLayout,
    QPlainTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint
from PyQt6.QtGui import QIcon, QFont, QColor, QAction, QPixmap, QImage, QPalette


# ----------------------------------------------------------------------
#   Worker thread – универсальный исполнитель произвольных функций
# ----------------------------------------------------------------------
class WorkerThread(QThread):
    log_signal      = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal   = pyqtSignal(str)
    finished_signal = pyqtSignal()
    data_signal     = pyqtSignal(object)

    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args     = args
        self.kwargs  = kwargs

    def run(self):
        try:
            self.function(*self.args, **self.kwargs)
        except Exception as e:
            self.log_signal.emit(f"Ошибка в потоке: {str(e)}")
        finally:
            self.finished_signal.emit()


# ----------------------------------------------------------------------
#   Информационный диалог о приложении
# ----------------------------------------------------------------------
class AppInfoDialog(QDialog):
    def __init__(self, app_info: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Информация о приложении")
        self.setGeometry(200, 200, 500, 400)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(app_info)
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


# ----------------------------------------------------------------------
#   Главное окно – переименовано в XHelperMainWindow
# ----------------------------------------------------------------------
class XHelperMainWindow(QMainWindow):
    log_signal      = pyqtSignal(str)   # для вывода текста в лог
    progress_signal = pyqtSignal(int)   # единый сигнал прогресса

    # ------------------------------------------------------------------
    #   Инициализация
    # ------------------------------------------------------------------
    def __init__(self):
        super().__init__()
        self.setWindowTitle("xHelper alpha 1.0.1 LTS/ATS")
        self.setGeometry(100, 100, 1400, 900)

        # ------------------ меню ------------------
        self.create_menu()

        # ------------------ UI --------------------
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        main_layout.addWidget(self.console)

        # ------------------ сигналы -------------
        self.log_signal.connect(self.log_message)
        self.progress_signal.connect(self.update_test_progress)   # тест‑прогресс

        # ------------------ вкладки ---------------
        self.create_device_tab()
        self.create_apk_tab()
        self.create_mass_apk_tab()
        self.create_file_operations_tab()
        self.create_command_tab()
        self.create_logcat_tab()
        self.create_reboot_tab()
        self.create_app_tester_tab()
        self.create_screen_mirror_tab()
        self.create_monitor_tab()
        self.create_wifi_tab()
        self.create_backup_tab()
        self.create_screen_record_tab()
        self.create_script_editor_tab()
        self.create_fastboot_tab()

        # ------------------ плагины ----------------
        self.load_plugins()

        # ------------------ ADB --------------------
        self.check_adb()

        # ------------------ переменные -------------
        self.apk_files           = []
        self.install_in_progress = False
        self.stop_installation   = False

        self.packages    = []
        self.crashed_apps = {}
        self.testing     = False

    # ------------------------------------------------------------------
    #   Меню и темы
    # ------------------------------------------------------------------
    def create_menu(self):
        menubar = self.menuBar()
        view_menu = menubar.addMenu("Вид")
        self.toggle_dark_action = QAction("Тёмная тема", self, checkable=True)
        self.toggle_dark_action.triggered.connect(self.toggle_dark_theme)
        view_menu.addAction(self.toggle_dark_action)

    def toggle_dark_theme(self, checked: bool):
        if checked:
            self.apply_dark_palette()
        else:
            self.apply_default_palette()

    def apply_dark_palette(self):
        dark = QPalette()
        dark.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        QApplication.instance().setPalette(dark)

    def apply_default_palette(self):
        QApplication.instance().setPalette(
            QApplication.instance().style().standardPalette()
        )

    # ------------------------------------------------------------------
    #   Плагин‑система
    # ------------------------------------------------------------------
    def load_plugins(self):
        plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
        if not os.path.isdir(plugins_dir):
            self.log_message("Папка plugins не найдена – плагины не загружены.")
            return

        for fn in os.listdir(plugins_dir):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(plugins_dir, fn)
            spec = importlib.util.spec_from_file_location(f"plugin_{fn[:-3]}", path)
            if spec and spec.loader:
                try:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "register"):
                        mod.register(self)
                        self.log_message(f"Плагин загружен: {fn}")
                except Exception as e:
                    self.log_message(f"Ошибка загрузки плагина {fn}: {e}")

    # ------------------------------------------------------------------
    #   Проверка ADB
    # ------------------------------------------------------------------
    def check_adb(self):
        """Проверка доступа к ADB."""
        try:
            result = subprocess.run(['adb', '--version'],
                                    capture_output=True,
                                    text=True)
            if result.returncode == 0:
                self.log_message("ADB доступен в системе")
                self.get_devices()
            else:
                self.log_message("ADB не найден. Установите его и добавьте в PATH.")
        except FileNotFoundError:
            self.log_message("ADB не найден. Установите его и добавьте в PATH.")

    def get_devices(self):
        """Получаем список подключённых устройств."""
        result = subprocess.run(['adb', 'devices'],
                                capture_output=True,
                                text=True)
        lines = result.stdout.split('\n')[1:]                     # первая строка – заголовок
        devices = [line.split('\t')[0] for line in lines
                   if line.strip() and '\tdevice' in line]

        self.device_list.clear()
        if devices:
            self.device_list.addItems(devices)
            self.log_message(f"Найдено устройств: {len(devices)}")
        else:
            self.log_message("Устройства не найдены")

    # ------------------------------------------------------------------
    #   Выполнение ADB‑команд
    # ------------------------------------------------------------------
    def run_adb_command(self, command: str, device_specific: bool = True):
        """
        Выполняет ADB‑команду.

        Если device_specific=True – команда будет выполнена на выбранном(ых)
        устройстве(ах). При включённом чекбоксе «Выполнять на всех выбранных»
        команда будет выполнена на всех отмеченных, иначе – только на первом.
        """
        if device_specific:
            selected = self.device_list.selectedItems()
            if not selected:
                self.log_message("Не выбрано устройство")
                return
            devices = [it.text() for it in selected]
            if not self.run_all_checkbox.isChecked():
                devices = [devices[0]]
        else:
            devices = [None]  # глобальная команда

        for dev in devices:
            if dev:
                full_cmd = ['adb', '-s', dev] + command.split()
            else:
                full_cmd = ['adb'] + command.split()
            try:
                self.log_message(f"Выполняем: {' '.join(full_cmd)}")
                result = subprocess.run(full_cmd,
                                        capture_output=True,
                                        text=True,
                                        timeout=30)
                if result.stdout:
                    self.log_message("Результат:")
                    self.log_message(result.stdout)
                if result.stderr:
                    self.log_message("Ошибки:")
                    self.log_message(result.stderr)
                if result.returncode != 0:
                    self.log_message(f"Команда завершилась с кодом: {result.returncode}")
            except subprocess.TimeoutExpired:
                self.log_message("Команда превысила таймаут (30 сек.)")
            except Exception as e:
                self.log_message(f"Ошибка выполнения команды: {str(e)}")

    def run_adb_package_command(self, base_cmd: str):
        """Запрашивает у пользователя имя пакета и исполняет команду."""
        if not self.device_list.currentItem():
            QMessageBox.warning(self, "Ошибка", "Сначала выберите устройство.")
            return
        pkg, ok = QInputDialog.getText(
            self,
            "Имя пакета",
            "Введите полное имя пакета (например, com.example.app):"
        )
        if ok and pkg:
            self.run_adb_command(f"{base_cmd} {pkg}")

    # ------------------------------------------------------------------
    #   Универсальное логирование
    # ------------------------------------------------------------------
    def log_message(self, message: str):
        """Записывает сообщение в консоль с отметкой времени."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"[{ts}] {message}")

    # ------------------------------------------------------------------
    #   Вкладка «Устройства»
    # ------------------------------------------------------------------
    def create_device_tab(self):
        device_tab = QWidget()
        layout = QVBoxLayout(device_tab)

        # Список устройств
        device_group = QGroupBox("Подключённые устройства")
        device_layout = QVBoxLayout(device_group)

        self.device_list = QListWidget()
        self.device_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        refresh_btn = QPushButton("Обновить список устройств")
        refresh_btn.clicked.connect(self.get_devices)

        device_layout.addWidget(self.device_list)
        device_layout.addWidget(refresh_btn)

        # Чекбокс «выполнять на всех выбранных»
        self.run_all_checkbox = QCheckBox("Выполнять на всех выбранных")
        device_layout.addWidget(self.run_all_checkbox)

        # Управление питанием
        reboot_group = QGroupBox("Управление питанием")
        reboot_layout = QGridLayout(reboot_group)

        reboot_buttons = [
            ("Перезагрузка",               "reboot"),
            ("Recovery",                   "reboot recovery"),
            ("Bootloader",                 "reboot bootloader"),
            ("Fastboot",                   "reboot fastboot")
        ]

        for i, (txt, cmd) in enumerate(reboot_buttons):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            reboot_layout.addWidget(btn, i // 2, i % 2)

        layout.addWidget(device_group)
        layout.addWidget(reboot_group)
        self.tabs.addTab(device_tab, "Устройства")

    # ------------------------------------------------------------------
    #   Вкладка «APK»
    # ------------------------------------------------------------------
    def create_apk_tab(self):
        apk_tab = QWidget()
        layout = QVBoxLayout(apk_tab)

        # Установка отдельного APK
        install_group = QGroupBox("Установка APK")
        install_layout = QVBoxLayout(install_group)

        self.apk_path = QLineEdit()
        browse_btn = QPushButton("Выбрать APK")
        browse_btn.clicked.connect(self.select_apk)

        install_btn = QPushButton("Установить APK")
        install_btn.clicked.connect(self.install_apk)

        install_layout.addWidget(QLabel("Путь к APK:"))
        install_layout.addWidget(self.apk_path)
        install_layout.addWidget(browse_btn)
        install_layout.addWidget(install_btn)

        # Управление пакетами
        package_group = QGroupBox("Управление приложениями")
        package_layout = QGridLayout(package_group)

        simple_cmds = [
            ("Список приложений",                 "shell pm list packages"),
            ("Список системных приложений",      "shell pm list packages -s"),
            ("Список сторонних приложений",      "shell pm list packages -3")
        ]

        for i, (txt, cmd) in enumerate(simple_cmds):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            package_layout.addWidget(btn, i // 3, i % 3)

        pkg_cmds = [
            ("Очистить данные",                   "shell pm clear"),
            ("Удалить приложение",                "uninstall"),
            ("Запуск приложения",                "shell monkey -p")
        ]

        offset = len(simple_cmds)
        for i, (txt, cmd) in enumerate(pkg_cmds):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_package_command(c))
            package_layout.addWidget(btn, (offset + i) // 3, (offset + i) % 3)

        layout.addWidget(install_group)
        layout.addWidget(package_group)
        self.tabs.addTab(apk_tab, "APK")

    def select_apk(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите APK файл", "", "APK Files (*.apk)"
        )
        if file_path:
            self.apk_path.setText(file_path)

    def install_apk(self):
        apk = self.apk_path.text()
        if not apk:
            QMessageBox.warning(self, "Ошибка", "Выберите APK‑файл")
            return
        if not os.path.exists(apk):
            QMessageBox.warning(self, "Ошибка", "Файл не существует")
            return
        self.run_adb_command(f"install -r {apk}")

    # ------------------------------------------------------------------
    #   Вкладка «Массовая установка APK»
    # ------------------------------------------------------------------
    def create_mass_apk_tab(self):
        mass_tab = QWidget()
        layout = QVBoxLayout(mass_tab)

        # Папка с APK
        folder_group = QGroupBox("Выбор папки с APK")
        folder_layout = QVBoxLayout(folder_group)

        self.folder_path = QLineEdit()
        browse_folder_btn = QPushButton("Выбрать папку с APK")
        browse_folder_btn.clicked.connect(self.select_apk_folder)

        folder_layout.addWidget(QLabel("Путь к папке:"))
        folder_layout.addWidget(self.folder_path)
        folder_layout.addWidget(browse_folder_btn)

        # Управление установкой
        install_group = QGroupBox("Массовая установка")
        install_layout = QVBoxLayout(install_group)

        self.apk_count_label = QLabel("APK‑файлы не выбраны")
        self.progress_bar    = QProgressBar()
        self.progress_bar.setVisible(False)

        self.start_install_btn = QPushButton("Начать установку")
        self.start_install_btn.clicked.connect(self.start_mass_installation)

        self.stop_install_btn = QPushButton("Остановить установку")
        self.stop_install_btn.clicked.connect(self.stop_mass_installation)
        self.stop_install_btn.setEnabled(False)

        install_layout.addWidget(self.apk_count_label)
        install_layout.addWidget(self.progress_bar)
        install_layout.addWidget(self.start_install_btn)
        install_layout.addWidget(self.stop_install_btn)

        layout.addWidget(folder_group)
        layout.addWidget(install_group)
        self.tabs.addTab(mass_tab, "Массовая установка APK")

    def select_apk_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с APK")
        if folder:
            self.folder_path.setText(folder)
            self.apk_files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith('.apk')
            ]
            self.apk_count_label.setText(f"Найдено APK‑файлов: {len(self.apk_files)}")

    def start_mass_installation(self):
        if not self.apk_files:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите папку с APK‑файлами")
            return
        if self.install_in_progress:
            QMessageBox.information(self, "Информация", "Установка уже запущена")
            return

        self.install_in_progress = True
        self.stop_installation = False
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.apk_files))
        self.progress_bar.setValue(0)

        # подключаем сигнал прогресса к индикатору
        self.progress_signal.connect(self.progress_bar.setValue)

        self.start_install_btn.setEnabled(False)
        self.stop_install_btn.setEnabled(True)

        self.worker_thread = WorkerThread(self.install_apks_thread)
        self.worker_thread.log_signal.connect(self.log_message)
        self.worker_thread.finished_signal.connect(self.mass_installation_finished)
        self.worker_thread.start()

    def stop_mass_installation(self):
        if self.install_in_progress:
            self.stop_installation = True
            self.log_message("Установка прервана пользователем")
            self.stop_install_btn.setEnabled(False)

    def mass_installation_finished(self):
        self.install_in_progress = False
        self.progress_bar.setVisible(False)
        try:
            self.progress_signal.disconnect(self.progress_bar.setValue)
        except TypeError:
            pass
        self.start_install_btn.setEnabled(True)
        self.stop_install_btn.setEnabled(False)

    def install_apks_thread(self):
        total = len(self.apk_files)
        success = 0
        failed = 0
        entries = []

        self.log_signal.emit(f"Начало массовой установки {total} APK‑файлов")
        log_file = f"install_log_{datetime.now():%Y%m%d_%H%M%S}.txt"

        with open(log_file, 'w', encoding='utf-8') as log_f:
            log_f.write(f"Лог массовой установки – {datetime.now()}\n")
            log_f.write("=" * 50 + "\n")

            for i, apk_path in enumerate(self.apk_files):
                if self.stop_installation:
                    self.log_signal.emit("Установка остановлена пользователем")
                    break

                self.log_signal.emit(f"[{i+1}/{total}] Устанавливаем {apk_path}")

                try:
                    result = subprocess.run(
                        ['adb', 'install', '-r', apk_path],
                        capture_output=True,
                        text=True,
                        timeout=360          # 6 минут максимум
                    )
                    if result.returncode == 0:
                        success += 1
                        status = "success"
                        details = "Installed"
                        msg = f"УСПЕХ: {apk_path}"
                        self.log_signal.emit(msg)
                        log_f.write(msg + "\n")
                    else:
                        failed += 1
                        status = "failed"
                        details = result.stderr.strip()
                        msg = f"ОШИБКА: {apk_path}\n{details}"
                        self.log_signal.emit(msg)
                        log_f.write(msg + "\n")
                except subprocess.TimeoutExpired:
                    failed += 1
                    status = "timeout"
                    details = "Превышен таймаут (6 мин.)"
                    msg = f"ТАЙМАУТ: {apk_path}"
                    self.log_signal.emit(msg)
                    log_f.write(msg + "\n")
                except Exception as e:
                    failed += 1
                    status = "exception"
                    details = str(e)
                    msg = f"ИСКЛЮЧЕНИЕ: {apk_path} – {details}"
                    self.log_signal.emit(msg)
                    log_f.write(msg + "\n")

                entries.append({
                    "package": os.path.basename(apk_path),
                    "status":  status,
                    "details": details
                })

                self.progress_signal.emit(i + 1)

            log_f.write("=" * 50 + "\n")
            log_f.write(f"Успешно: {success}\n")
            log_f.write(f"Не удалось: {failed}\n")
            log_f.write(f"Всего обработано: {success + failed}\n")

        # сохраняем отчёт JSON/HTML
        report = {
            "type":      "mass_install",
            "timestamp": datetime.now().isoformat(),
            "total":     total,
            "success":   success,
            "failed":    failed,
            "entries":   entries
        }
        self.save_report(report, "mass_install_report")

        self.log_signal.emit(f"Установка завершена! Успешно: {success}, Ошибки: {failed}")

        if failed == 0:
            QMessageBox.information(self, "Готово", "Все APK‑файлы установлены успешно!")
        else:
            QMessageBox.warning(
                self, "Готово",
                f"Установка завершена с ошибками.\nУспешно: {success}\nОшибки: {failed}"
            )

    # ------------------------------------------------------------------
    #   Вкладка «Файлы» (push / pull)
    # ------------------------------------------------------------------
    def create_file_operations_tab(self):
        file_tab = QWidget()
        layout = QVBoxLayout(file_tab)

        # Push
        push_group = QGroupBox("Отправка файлов на устройство")
        push_layout = QVBoxLayout(push_group)

        self.push_local  = QLineEdit()
        self.push_remote = QLineEdit("/sdcard/")

        browse_push_btn = QPushButton("Выбрать файл")
        browse_push_btn.clicked.connect(self.select_push_file)

        push_btn = QPushButton("Отправить")
        push_btn.clicked.connect(self.push_file)

        push_layout.addWidget(QLabel("Локальный файл:"))
        push_layout.addWidget(self.push_local)
        push_layout.addWidget(browse_push_btn)
        push_layout.addWidget(QLabel("Удалённый путь:"))
        push_layout.addWidget(self.push_remote)
        push_layout.addWidget(push_btn)

        # Pull
        pull_group = QGroupBox("Получение файлов с устройства")
        pull_layout = QVBoxLayout(pull_group)

        self.pull_remote = QLineEdit("/sdcard/")
        self.pull_local  = QLineEdit("./")

        browse_pull_btn = QPushButton("Выбрать папку")
        browse_pull_btn.clicked.connect(self.select_pull_folder)

        pull_btn = QPushButton("Получить")
        pull_btn.clicked.connect(self.pull_file)

        pull_layout.addWidget(QLabel("Удалённый файл:"))
        pull_layout.addWidget(self.pull_remote)
        pull_layout.addWidget(QLabel("Локальная папка:"))
        pull_layout.addWidget(self.pull_local)
        pull_layout.addWidget(browse_pull_btn)
        pull_layout.addWidget(pull_btn)

        layout.addWidget(push_group)
        layout.addWidget(pull_group)
        self.tabs.addTab(file_tab, "Файлы")

    def select_push_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл для отправки", "")
        if path:
            self.push_local.setText(path)

    def select_pull_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения")
        if folder:
            self.pull_local.setText(folder)

    def push_file(self):
        local = self.push_local.text()
        remote = self.push_remote.text()
        if not local or not remote:
            QMessageBox.warning(self, "Ошибка", "Заполните оба поля")
            return
        if not os.path.exists(local):
            QMessageBox.warning(self, "Ошибка", "Локальный файл не найден")
            return
        self.run_adb_command(f"push {local} {remote}")

    def pull_file(self):
        remote = self.pull_remote.text()
        local = self.pull_local.text()
        if not remote or not local:
            QMessageBox.warning(self, "Ошибка", "Заполните оба поля")
            return
        self.run_adb_command(f"pull {remote} {local}")

    # ------------------------------------------------------------------
    #   Вкладка «Команды» (системные)
    # ------------------------------------------------------------------
    def create_command_tab(self):
        cmd_tab = QWidget()
        layout = QVBoxLayout(cmd_tab)

        sys_group = QGroupBox("Системные команды")
        sys_layout = QGridLayout(sys_group)

        sys_commands = [
            ("Получить свойства",                "shell getprop"),
            ("Информация о батарее",            "shell dumpsys battery"),
            ("Информация о процессоре",         "shell cat /proc/cpuinfo"),
            ("Информация о памяти",             "shell cat /proc/meminfo"),
            ("Сетевые соединения",              "shell netstat"),
            ("Текущая активность",              "shell dumpsys activity activities | grep mResumedActivity"),
            ("Запущенные процессы",             "shell ps"),
            ("Информация о Wi‑Fi",               "shell dumpsys wifi"),
            ("Информация о дисплее",            "shell dumpsys display"),
            ("Свободная память",                "shell df -h")
        ]

        for i, (txt, cmd) in enumerate(sys_commands):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            sys_layout.addWidget(btn, i // 2, i % 2)

        layout.addWidget(sys_group)
        self.tabs.addTab(cmd_tab, "Команды")

    # ------------------------------------------------------------------
    #   Вкладка «Logcat»
    # ------------------------------------------------------------------
    def create_logcat_tab(self):
        logcat_tab = QWidget()
        layout = QVBoxLayout(logcat_tab)

        log_group = QGroupBox("Logcat")
        log_layout = QVBoxLayout(log_group)

        log_btns = [
            ("Запустить logcat",                     "logcat"),
            ("Очистить логи",                        "logcat -c"),
            ("Сохранить лог в файл",                 "logcat -d -f /sdcard/logcat.txt"),
            ("Только ошибки",                        "logcat *:E"),
            ("Полный дамп системы",                  "bugreport")
        ]

        for txt, cmd in log_btns:
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            log_layout.addWidget(btn)

        layout.addWidget(log_group)
        self.tabs.addTab(logcat_tab, "Логи")

    # ------------------------------------------------------------------
    #   Вкладка «Перезагрузка»
    # ------------------------------------------------------------------
    def create_reboot_tab(self):
        reboot_tab = QWidget()
        layout = QVBoxLayout(reboot_tab)

        reboot_group = QGroupBox("Режимы перезагрузки")
        reboot_layout = QGridLayout(reboot_group)

        reboot_buttons = [
            ("🔄 Обычная перезагрузка",                         "reboot"),
            ("🛠 Перезагрузка в Recovery",                      "reboot recovery"),
            ("⚡ Fastboot / Bootloader",                        "reboot bootloader"),
            ("🛡 Безопасный режим",                             "shell am broadcast -a android.intent.action.REBOOT --ez android.intent.extra.IS_SAFE_MODE true"),
            ("📡 Режим EDL (Qualcomm)",                        "reboot edl"),
            ("⏻ Выключить устройство",                         "shell reboot -p")
        ]

        for i, (txt, cmd) in enumerate(reboot_buttons):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            reboot_layout.addWidget(btn, i // 2, i % 2)

        layout.addWidget(reboot_group)
        self.tabs.addTab(reboot_tab, "Перезагрузка")

    # ------------------------------------------------------------------
    #   Вкладка «Тестирование приложений»
    # ------------------------------------------------------------------
    def create_app_tester_tab(self):
        tester_tab = QWidget()
        layout = QVBoxLayout(tester_tab)

        # Управление
        ctrl_group = QGroupBox("Управление тестированием")
        ctrl_layout = QVBoxLayout(ctrl_group)

        # задержка
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Задержка между тестами (сек):"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(5, 60)
        self.delay_spinbox.setValue(10)
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()

        # кнопки
        btn_layout = QHBoxLayout()
        self.get_packages_btn = QPushButton("Получить приложения")
        self.get_packages_btn.clicked.connect(self.get_user_packages)

        self.start_test_btn = QPushButton("Начать тестирование")
        self.start_test_btn.clicked.connect(self.start_app_testing)
        self.start_test_btn.setEnabled(False)

        self.stop_test_btn = QPushButton("Остановить тестирование")
        self.stop_test_btn.clicked.connect(self.stop_app_testing)
        self.stop_test_btn.setEnabled(False)

        btn_layout.addWidget(self.get_packages_btn)
        btn_layout.addWidget(self.start_test_btn)
        btn_layout.addWidget(self.stop_test_btn)

        ctrl_layout.addLayout(delay_layout)
        ctrl_layout.addLayout(btn_layout)

        # прогресс‑бар
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        ctrl_layout.addWidget(self.test_progress)

        # таблица результатов
        result_group = QGroupBox("Результаты тестирования")
        result_layout = QVBoxLayout(result_group)

        self.app_tree = QTreeWidget()
        self.app_tree.setHeaderLabels(["Имя", "Пакет", "Статус"])
        self.app_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        result_layout.addWidget(self.app_tree)

        # действия над проблемными приложениями
        action_layout = QHBoxLayout()
        self.delete_selected_btn = QPushButton("Удалить выбранные")
        self.delete_selected_btn.clicked.connect(self.delete_selected_apps)
        self.delete_selected_btn.setEnabled(False)

        self.delete_all_btn = QPushButton("Удалить все проблемные")
        self.delete_all_btn.clicked.connect(self.delete_all_problematic_apps)
        self.delete_all_btn.setEnabled(False)

        action_layout.addWidget(self.delete_selected_btn)
        action_layout.addWidget(self.delete_all_btn)

        result_layout.addLayout(action_layout)

        # собрать вкладку
        layout.addWidget(ctrl_group)
        layout.addWidget(result_group)
        self.tabs.addTab(tester_tab, "Тестирование приложений")

    def get_user_packages(self):
        """Получаем список пользовательских приложений."""
        self.log_message("Запрашиваем список пользовательских приложений...")
        try:
            result = subprocess.run(
                ["adb", "shell", "pm", "list", "packages", "-3"],
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
                errors='ignore'
            )
            if result.stdout:
                self.packages = [
                    line.replace("package:", "").strip()
                    for line in result.stdout.splitlines()
                    if line.strip()
                ]
                self.log_message(f"Найдено {len(self.packages)} пользовательских приложений")
                self.start_test_btn.setEnabled(True)

                self.app_tree.clear()
                for pkg in self.packages:
                    it = QTreeWidgetItem(self.app_tree)
                    it.setText(0, "—")
                    it.setText(1, pkg)
                    it.setText(2, "Ожидание")
                    it.setForeground(2, QColor("gray"))
            else:
                self.log_message("Пакеты не получены")
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка получения пакетов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить список приложений:\n{e}")

    def start_app_testing(self):
        if not self.packages:
            QMessageBox.warning(self, "Внимание", "Сначала получите список приложений")
            return

        self.testing = True
        self.crashed_apps = {}
        self.start_test_btn.setEnabled(False)
        self.stop_test_btn.setEnabled(True)
        self.test_progress.setVisible(True)
        self.test_progress.setMaximum(len(self.packages))
        self.test_progress.setValue(0)
        self.log_message("Запуск тестирования приложений…")

        self.test_worker_thread = WorkerThread(self.test_applications_thread)
        self.test_worker_thread.finished_signal.connect(self.app_testing_finished)
        self.test_worker_thread.start()

    def stop_app_testing(self):
        self.testing = False
        self.log_message("Тестирование остановлено пользователем")

    def app_testing_finished(self):
        self.testing = False
        self.start_test_btn.setEnabled(True)
        self.stop_test_btn.setEnabled(False)
        self.test_progress.setVisible(False)

        if self.crashed_apps:
            self.delete_selected_btn.setEnabled(True)
            self.delete_all_btn.setEnabled(True)
            self.generate_test_report()
        else:
            self.delete_selected_btn.setEnabled(False)
            self.delete_all_btn.setEnabled(False)

    def test_applications_thread(self):
        try:
            delay = self.delay_spinbox.value()
            for i, pkg in enumerate(self.packages):
                if not self.testing:
                    break

                result = self.test_application(pkg)

                if result["crashed"]:
                    self.update_app_test_status(i,
                                                f"Ошибок: {result['error_count']}",
                                                "red")
                    self.crashed_apps[pkg] = result
                else:
                    self.update_app_test_status(i, "OK", "green")

                self.progress_signal.emit(i + 1)

                # задержка перед следующим тестом
                for sec in range(delay, 0, -1):
                    if not self.testing:
                        break
                    self.log_signal.emit(f"Ожидание {sec} сек. перед следующим тестом...")
                    time.sleep(1)

            if self.crashed_apps:
                self.log_signal.emit(f"Тестирование завершено. Проблемных приложений: {len(self.crashed_apps)}")
            else:
                self.log_signal.emit("Тестирование завершено. Проблемных приложений не обнаружено")
        except Exception as e:
            self.log_signal.emit(f"Ошибка в тестировщике: {e}")

    def update_app_test_status(self, index: int, status: str, color_name: str):
        item = self.app_tree.topLevelItem(index)
        if item:
            item.setText(2, status)
            item.setForeground(2, QColor(color_name))

    def update_test_progress(self, value: int):
        self.test_progress.setValue(value)

    def test_application(self, package_name: str) -> dict:
        """Запуск, сбор логов и проверка падений."""
        result = {"crashed": False, "error_count": 0, "name": package_name}
        try:
            subprocess.run(["adb", "logcat", "-c"], capture_output=True)

            subprocess.run(
                ["adb", "shell", "monkey", "-p", package_name,
                 "-c", "android.intent.category.LAUNCHER", "1"],
                capture_output=True,
                timeout=5
            )
            time.sleep(3)

            log = subprocess.run(
                ["adb", "logcat", "-d", "-v", "brief", "*:E"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if log.stdout:
                err_cnt = log.stdout.count("FATAL") + log.stdout.count("CRASH")
                if err_cnt > 0 and package_name in log.stdout:
                    result["crashed"]     = True
                    result["error_count"] = err_cnt

            subprocess.run(["adb", "shell", "am", "force-stop", package_name],
                           capture_output=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            result["crashed"]     = True
            result["error_count"] = 1
        except Exception as e:
            result["crashed"]     = True
            result["error_count"] = 1
            self.log_signal.emit(f"Исключение в test_application: {e}")
        return result

    def delete_selected_apps(self):
        selected = self.app_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Внимание", "Не выбрано приложение для удаления")
            return
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить выбранные {len(selected)} приложение(й)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        success = 0
        for it in selected:
            pkg = it.text(1)
            if self.uninstall_package(pkg):
                success += 1
                self.app_tree.takeTopLevelItem(self.app_tree.indexOfTopLevelItem(it))

        QMessageBox.information(self, "Готово",
                                f"Удалено {success} из {len(selected)} приложений")

    def delete_all_problematic_apps(self):
        if not self.crashed_apps:
            QMessageBox.warning(self, "Внимание", "Нет проблемных приложений")
            return
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить все {len(self.crashed_apps)} проблемных приложений?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        success = 0
        for pkg in list(self.crashed_apps.keys()):
            if self.uninstall_package(pkg):
                success += 1
                for i in range(self.app_tree.topLevelItemCount()):
                    it = self.app_tree.topLevelItem(i)
                    if it.text(1) == pkg:
                        self.app_tree.takeTopLevelItem(i)
                        break

        self.crashed_apps.clear()
        QMessageBox.information(self, "Готово",
                                f"Удалено {success} проблемных приложений")
        self.delete_selected_btn.setEnabled(False)
        self.delete_all_btn.setEnabled(False)

    def uninstall_package(self, package_name: str) -> bool:
        try:
            result = subprocess.run(
                ["adb", "uninstall", package_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.stdout and "Success" in result.stdout:
                self.log_message(f"Успешно удалено: {package_name}")
                return True
            else:
                self.log_message(f"Не удалось удалить {package_name}: {result.stdout or result.stderr}")
                return False
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка удаления {package_name}: {e}")
            return False

    # ------------------------------------------------------------------
    #   Вкладка «Экран устройства» (scrcpy)
    # ------------------------------------------------------------------
    def create_screen_mirror_tab(self):
        screen_tab = QWidget()
        layout = QVBoxLayout(screen_tab)

        screen_group = QGroupBox("Управление экраном")
        screen_layout = QVBoxLayout(screen_group)

        self.start_stream_btn = QPushButton("Запуск скринкаста (scrcpy)")
        self.start_stream_btn.clicked.connect(self.start_screen_stream)

        self.stop_stream_btn = QPushButton("Остановить скринкаст")
        self.stop_stream_btn.clicked.connect(self.stop_screen_stream)
        self.stop_stream_btn.setEnabled(False)

        self.screenshot_btn = QPushButton("Сделать скриншот")
        self.screenshot_btn.clicked.connect(self.take_screenshot)

        screen_layout.addWidget(self.start_stream_btn)
        screen_layout.addWidget(self.stop_stream_btn)
        screen_layout.addWidget(self.screenshot_btn)

        layout.addWidget(screen_group)
        self.tabs.addTab(screen_tab, "Экран устройства")

    def start_screen_stream(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return

        # проверяем наличие scrcpy
        try:
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            QMessageBox.critical(self, "Ошибка", "scrcpy не найден в PATH")
            return

        self.log_message("Запуск scrcpy...")
        self.start_stream_btn.setEnabled(False)
        self.stop_stream_btn.setEnabled(True)

        self.scrcpy_process = subprocess.Popen(
            ["scrcpy", "--max-fps", "60", "--window-title", "xHelper – Android Screen"]
        )

    def stop_screen_stream(self):
        if hasattr(self, "scrcpy_process"):
            self.scrcpy_process.terminate()
            self.scrcpy_process = None
            self.log_message("Скринкаст остановлен")
        self.start_stream_btn.setEnabled(True)
        self.stop_stream_btn.setEnabled(False)

    def take_screenshot(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить скриншот",
            f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png",
            "PNG Files (*.png)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "wb") as f:
                subprocess.run(
                    ["adb", "exec-out", "screencap", "-p"],
                    stdout=f,
                    check=True
                )
            self.log_message(f"Скриншот сохранён: {file_path}")
            QMessageBox.information(self, "Успех", f"Скриншот сохранён:\n{file_path}")
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка скриншота: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить скриншот:\n{e}")

    def check_device_connected(self) -> bool:
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().splitlines()
            return any("device" in line for line in lines[1:] if line.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    # ------------------------------------------------------------------
    #   Вкладка «Мониторинг» (CPU, память, батарея, сеть)
    # ------------------------------------------------------------------
    def create_monitor_tab(self):
        monitor_tab = QWidget()
        layout = QVBoxLayout(monitor_tab)

        self.monitor_labels = {
            "Battery": QLabel("Battery: N/A"),
            "CPU":     QLabel("CPU: N/A"),
            "Memory":  QLabel("Memory: N/A"),
            "Network": QLabel("Network: N/A")
        }

        for lbl in self.monitor_labels.values():
            layout.addWidget(lbl)

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_monitor)
        self.monitor_timer.start(5000)   # раз в 5 сек.

        self.tabs.addTab(monitor_tab, "Мониторинг")

    def update_monitor(self):
        """Обновление данных мониторинга."""
        if not self.check_device_connected():
            for key, lbl in self.monitor_labels.items():
                lbl.setText(f"{key}: N/A")
            return

        # Battery
        bat = subprocess.run(
            ["adb", "shell", "dumpsys", "battery"],
            capture_output=True, text=True
        ).stdout
        level = "?"
        for line in bat.splitlines():
            if "level:" in line:
                level = line.split(":")[1].strip()
                break
        self.monitor_labels["Battery"].setText(f"Battery: {level}%")

        # CPU – упрощённый вывод (можно расширить)
        self.monitor_labels["CPU"].setText("CPU: N/A")

        # Memory
        mem = subprocess.run(
            ["adb", "shell", "cat", "/proc/meminfo"],
            capture_output=True, text=True
        ).stdout
        total = free = None
        for line in mem.splitlines():
            if line.startswith("MemTotal:"):
                total = line.split(":")[1].strip()
            elif line.startswith("MemFree:"):
                free = line.split(":")[1].strip()
        if total and free:
            self.monitor_labels["Memory"].setText(f"Memory: {free} free / {total}")
        else:
            self.monitor_labels["Memory"].setText("Memory: N/A")

        # Network (IP‑адрес wlan0)
        ipinfo = subprocess.run(
            ["adb", "shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
            capture_output=True, text=True
        ).stdout
        ip = "?"
        for line in ipinfo.splitlines():
            if "inet " in line:
                ip = line.strip().split()[1]
                break
        self.monitor_labels["Network"].setText(f"Network (wlan0): {ip}")

    # ------------------------------------------------------------------
    #   Вкладка «Wi‑Fi ADB» (tcpip)
    # ------------------------------------------------------------------
    def create_wifi_tab(self):
        wifi_tab = QWidget()
        layout = QVBoxLayout(wifi_tab)

        enable_btn = QPushButton("Включить ADB over Wi‑Fi (tcpip 5555)")
        enable_btn.clicked.connect(self.enable_wifi_adb)

        self.wifi_ip_input = QLineEdit()
        self.wifi_ip_input.setPlaceholderText("IP‑адрес устройства (пример: 192.168.1.42)")

        connect_btn = QPushButton("Подключить")
        connect_btn.clicked.connect(self.connect_wifi_adb)

        disconnect_btn = QPushButton("Отключить")
        disconnect_btn.clicked.connect(self.disconnect_wifi_adb)

        layout.addWidget(enable_btn)
        layout.addWidget(QLabel("IP‑адрес:"))
        layout.addWidget(self.wifi_ip_input)
        layout.addWidget(connect_btn)
        layout.addWidget(disconnect_btn)

        self.tabs.addTab(wifi_tab, "Wi‑Fi ADB")

    def enable_wifi_adb(self):
        self.run_adb_command("tcpip 5555", device_specific=True)

    def connect_wifi_adb(self):
        ip = self.wifi_ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "Ошибка", "Введите IP‑адрес")
            return
        self.run_adb_command(f"connect {ip}:5555", device_specific=False)

    def disconnect_wifi_adb(self):
        self.run_adb_command("disconnect", device_specific=False)

    # ------------------------------------------------------------------
    #   Вкладка «Бэкап / Восстановление»
    # ------------------------------------------------------------------
    def create_backup_tab(self):
        backup_tab = QWidget()
        layout = QVBoxLayout(backup_tab)

        backup_btn = QPushButton("Создать бэкап (full)")
        backup_btn.clicked.connect(self.create_backup)

        restore_btn = QPushButton("Восстановить бэкап")
        restore_btn.clicked.connect(self.restore_backup)

        layout.addWidget(backup_btn)
        layout.addWidget(restore_btn)

        self.tabs.addTab(backup_tab, "Бэкап / Восстановление")

    def create_backup(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить бэкап", "backup.ab", "AB Files (*.ab)"
        )
        if not file_path:
            return
        self.run_adb_command(f"backup -apk -shared -all -f {file_path}", device_specific=False)

    def restore_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите бэкап", "", "AB Files (*.ab)"
        )
        if not file_path:
            return
        self.run_adb_command(f"restore {file_path}", device_specific=False)

    # ------------------------------------------------------------------
    #   Вкладка «Запись экрана» (screenrecord)
    # ------------------------------------------------------------------
    def create_screen_record_tab(self):
        record_tab = QWidget()
        layout = QVBoxLayout(record_tab)

        self.start_record_btn = QPushButton("Начать запись")
        self.start_record_btn.clicked.connect(self.start_screen_record)

        self.stop_record_btn = QPushButton("Остановить запись")
        self.stop_record_btn.clicked.connect(self.stop_screen_record)
        self.stop_record_btn.setEnabled(False)

        self.save_record_btn = QPushButton("Сохранить запись")
        self.save_record_btn.clicked.connect(self.save_screen_record)
        self.save_record_btn.setEnabled(False)

        layout.addWidget(self.start_record_btn)
        layout.addWidget(self.stop_record_btn)
        layout.addWidget(self.save_record_btn)

        self.tabs.addTab(record_tab, "Запись экрана")

    def start_screen_record(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return
        self.log_message("Запуск screenrecord на устройстве...")
        self.screenrecord_process = subprocess.Popen(
            ["adb", "shell", "screenrecord", "/sdcard/xHelper_record.mp4"]
        )
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)

    def stop_screen_record(self):
        if hasattr(self, "screenrecord_process"):
            self.screenrecord_process.terminate()
            self.screenrecord_process.wait()
            self.log_message("Запись остановлена")
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self.save_record_btn.setEnabled(True)

    def save_screen_record(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить запись",
            f"record_{datetime.now():%Y%m%d_%H%M%S}.mp4",
            "MP4 Files (*.mp4)"
        )
        if not save_path:
            return
        self.log_message(f"Копирование записи в {save_path} …")
        self.run_adb_command(f"pull /sdcard/xHelper_record.mp4 {save_path}", device_specific=False)
        self.run_adb_command("shell rm /sdcard/xHelper_record.mp4", device_specific=False)
        QMessageBox.information(self, "Готово", f"Запись сохранена:\n{save_path}")
        self.save_record_btn.setEnabled(False)

    # ------------------------------------------------------------------
    #   Вкладка «Скриптовый редактор»
    # ------------------------------------------------------------------
    def create_script_editor_tab(self):
        script_tab = QWidget()
        layout = QVBoxLayout(script_tab)

        self.script_edit = QPlainTextEdit()
        self.script_edit.setPlaceholderText(
            "# Пишите ADB‑команды, одну на строку.\n"
            "# Строки, начинающиеся с #, игнорируются.\n"
        )
        run_btn = QPushButton("Выполнить скрипт")
        run_btn.clicked.connect(self.run_script)

        layout.addWidget(self.script_edit)
        layout.addWidget(run_btn)

        self.tabs.addTab(script_tab, "Скриптовый редактор")

    def run_script(self):
        script = self.script_edit.toPlainText()
        lines = [ln.strip() for ln in script.splitlines()
                 if ln.strip() and not ln.strip().startswith('#')]
        if not lines:
            QMessageBox.information(self, "Инфо", "Скрипт пуст")
            return

        def exec_lines():
            for cmd in lines:
                self.log_message(f"Выполняю: {cmd}")
                self.run_adb_command(cmd, device_specific=True)
                time.sleep(0.2)

        self.script_thread = WorkerThread(exec_lines)
        self.script_thread.log_signal.connect(self.log_message)
        self.script_thread.start()

    # ------------------------------------------------------------------
    #   Вкладка «Fastboot»
    # ------------------------------------------------------------------
    def create_fastboot_tab(self):
        fastboot_tab = QWidget()
        layout = QVBoxLayout(fastboot_tab)

        list_btn = QPushButton("Список Fastboot‑устройств")
        list_btn.clicked.connect(self.fastboot_devices)

        # Flash
        flash_layout = QHBoxLayout()
        self.flash_file_path = QLineEdit()
        browse_flash_btn = QPushButton("Файл")
        browse_flash_btn.clicked.connect(self.select_flash_file)
        flash_btn = QPushButton("Flash")
        flash_btn.clicked.connect(self.flash_fastboot)

        flash_layout.addWidget(self.flash_file_path)
        flash_layout.addWidget(browse_flash_btn)
        flash_layout.addWidget(flash_btn)

        # Erase
        erase_layout = QHBoxLayout()
        self.erase_partition_input = QLineEdit()
        self.erase_partition_input.setPlaceholderText("Имя раздела (например, system)")
        erase_btn = QPushButton("Erase")
        erase_btn.clicked.connect(self.erase_fastboot_partition)

        erase_layout.addWidget(self.erase_partition_input)
        erase_layout.addWidget(erase_btn)

        unlock_btn = QPushButton("Unlock bootloader")
        unlock_btn.clicked.connect(self.fastboot_unlock)

        layout.addWidget(list_btn)
        layout.addLayout(flash_layout)
        layout.addLayout(erase_layout)
        layout.addWidget(unlock_btn)

        self.tabs.addTab(fastboot_tab, "Fastboot")

    def fastboot_devices(self):
        try:
            result = subprocess.run(
                ["fastboot", "devices"],
                capture_output=True,
                text=True,
                timeout=15
            )
            self.log_message("Fastboot‑устройства:")
            self.log_message(result.stdout.strip() or "Не обнаружено")
        except FileNotFoundError:
            self.log_message("fastboot не найден в PATH")
        except Exception as e:
            self.log_message(f"Ошибка fastboot devices: {e}")

    def select_flash_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл для flash", "", "All Files (*)")
        if path:
            self.flash_file_path.setText(path)

    def flash_fastboot(self):
        path = self.flash_file_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Укажите файл для flash")
            return
        # Предполагаем flash в системный раздел; пользователь может изменить команду
        self.run_fastboot_command(f"flash system {path}")

    def erase_fastboot_partition(self):
        part = self.erase_partition_input.text().strip()
        if not part:
            QMessageBox.warning(self, "Ошибка", "Укажите имя раздела")
            return
        self.run_fastboot_command(f"erase {part}")

    def fastboot_unlock(self):
        self.run_fastboot_command("oem unlock")

    def run_fastboot_command(self, command: str):
        """Выполняет fastboot‑команду и выводит результат в лог."""
        try:
            full_cmd = ["fastboot"] + command.split()
            self.log_message(f"Fastboot: {' '.join(full_cmd)}")
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.stdout:
                self.log_message(result.stdout)
            if result.stderr:
                self.log_message(result.stderr)
        except subprocess.TimeoutExpired:
            self.log_message("Fastboot‑команда превысила таймаут")
        except FileNotFoundError:
            self.log_message("fastboot не найден в PATH")
        except Exception as e:
            self.log_message(f"Ошибка fastboot: {e}")

    # ------------------------------------------------------------------
    #   Универсальная генерация отчётов (JSON + HTML)
    # ------------------------------------------------------------------
    def save_report(self, data: dict, base_name: str):
        """Сохраняет отчёт в файлы JSON и HTML."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = f"{base_name}_{timestamp}.json"
        html_path = f"{base_name}_{timestamp}.html"

        # JSON
        try:
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(data, jf, ensure_ascii=False, indent=4)
            self.log_message(f"JSON‑отчёт сохранён: {json_path}")
        except Exception as e:
            self.log_message(f"Не удалось сохранить JSON‑отчёт: {e}")

        # HTML (простейшая таблица)
        try:
            rows = ""
            for entry in data.get("entries", []):
                rows += f"<tr><td>{entry.get('package','')}</td><td>{entry.get('status','')}</td><td>{entry.get('details','')}</td></tr>\n"
            html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{base_name} report</title>
<style>
body {{font-family:Arial,sans-serif;}}
table {{border-collapse:collapse;width:100%;}}
th,td {{border:1px solid #ddd;padding:8px;}}
th {{background:#f2f2f2;}}
</style>
</head>
<body>
<h2>{base_name} report – {datetime.now():%Y-%m-%d %H:%M:%S}</h2>
<table>
<tr><th>Пакет</th><th>Статус</th><th>Подробности</th></tr>
{rows}
</table>
</body>
</html>"""
            with open(html_path, "w", encoding="utf-8") as hf:
                hf.write(html)
            self.log_message(f"HTML‑отчёт сохранён: {html_path}")
        except Exception as e:
            self.log_message(f"Не удалось сохранить HTML‑отчёт: {e}")

    def generate_test_report(self):
        """Создаёт отчёт о результатах тестирования приложений."""
        total = len(self.packages)
        failed = len(self.crashed_apps)
        success = total - failed

        entries = []
        for pkg in self.packages:
            if pkg in self.crashed_apps:
                entry = {
                    "package": pkg,
                    "status":  "crashed",
                    "details": f"Ошибок: {self.crashed_apps[pkg]['error_count']}"
                }
            else:
                entry = {
                    "package": pkg,
                    "status":  "ok",
                    "details": "No errors"
                }
            entries.append(entry)

        report = {
            "type":      "app_testing",
            "timestamp": datetime.now().isoformat(),
            "total":     total,
            "success":   success,
            "failed":    failed,
            "entries":   entries
        }
        self.save_report(report, "app_testing_report")
        QMessageBox.information(self, "Отчёт", "Отчёт о тестировании сохранён в текущей папке.")

    # ------------------------------------------------------------------
    #   Точка входа
    # ------------------------------------------------------------------
    def main(self):
        self.show()

def main():
    app = QApplication(sys.argv)
    window = XHelperMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
