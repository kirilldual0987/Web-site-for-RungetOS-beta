#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xHelper pre‑alpha unstable dev test no support v0.0.5.8
Многофункциональная GUI‑утилита управления Android‑устройствами через ADB.
"""

# ----------------------------------------------------------------------
#   Стандартные библиотеки
# ----------------------------------------------------------------------
import sys
import os
import subprocess
import threading
import time
import json
import re
import importlib.util
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------
#   PyQt6
# ----------------------------------------------------------------------
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QTextEdit, QLabel, QFileDialog,
    QMessageBox, QTabWidget, QGroupBox, QLineEdit, QGridLayout,
    QProgressBar, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QCheckBox, QSpinBox, QComboBox, QInputDialog, QMenu,
    QSystemTrayIcon, QStyle, QDialog, QDialogButtonBox,
    QFormLayout, QPlainTextEdit, QDockWidget, QTextBrowser,
    QShortcut, QTableWidget, QTableWidgetItem, QAction
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPoint,
    QEvent, QThreadPool, QRunnable
)
from PyQt6.QtGui import (
    QIcon, QFont, QColor, QKeySequence, QPalette, QCloseEvent
)

# ----------------------------------------------------------------------
#   Константы и вспомогательные функции
# ----------------------------------------------------------------------
CONFIG_PATH = Path.home() / ".xhelper_prealpha_config.json"

def resource_path(relative_path: str) -> str:
    """Получает абсолютный путь к файлу‑ресурсу (для frozen‑билда)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

# ----------------------------------------------------------------------
#   Универсальный поток для длительных задач
# ----------------------------------------------------------------------
class WorkerThread(QThread):
    log_signal      = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
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
            self.log_signal.emit(f"[THREAD ERROR] {e}")
        finally:
            self.finished_signal.emit()

# ----------------------------------------------------------------------
#   QRunnable‑задача (короткая, исполняемая через ThreadPool)
# ----------------------------------------------------------------------
class SimpleTask(QRunnable):
    def __init__(self, fn, *a, **kw):
        super().__init__()
        self.fn = fn
        self.args = a
        self.kwargs = kw

    def run(self):
        self.fn(*self.args, **self.kwargs)

# ----------------------------------------------------------------------
#   Диалог с информацией о приложении (APK)
# ----------------------------------------------------------------------
class AppInfoDialog(QDialog):
    def __init__(self, app_info: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Информация о приложении")
        self.resize(500, 400)

        lay = QVBoxLayout(self)
        te  = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(app_info)
        lay.addWidget(te)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)
        lay.addWidget(btns)

# ----------------------------------------------------------------------
#   Главное окно
# ----------------------------------------------------------------------
class XHelperMainWindow(QMainWindow):
    # глобальные сигналы
    log_signal      = pyqtSignal(str)   # запись в главный лог
    progress_signal = pyqtSignal(int)   # единый сигнал прогресса

    # ------------------------------------------------------------------
    #   Инициализация
    # ------------------------------------------------------------------
    def __init__(self):
        super().__init__()
        self.setWindowTitle("xHelper pre‑alpha unstable dev test no support v0.0.5.8")
        self.resize(1600, 950)

        # --------------------------------- настройки -------------------------
        self.settings = {
            "adb_path"        : "adb",
            "theme_dark"      : False,
            "auto_update"     : False,
            "log_to_file"     : False,
            "log_file_path"   : str(Path.home() / "xHelper_log.txt"),
            "language"        : "ru",
            "hotkeys"         : {
                "RefreshDevices"    : "F5",
                "OpenLogcat"       : "Ctrl+L",
                "StartScrcpy"      : "Ctrl+S",
                "TakeScreenshot"   : "Ctrl+Shift+S"
            }
        }
        self.load_settings()

        # --------------------------------- UI --------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # вкладки
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # консоль вывода (правый бок)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        main_layout.addWidget(self.console)

        # статус‑бар
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # --------------------------------- сигналы -------------------------
        self.log_signal.connect(self.log_message)
        self.progress_signal.connect(self.set_progress)
        self.progress_signal.connect(self.progress_bar.setValue)

        # --------------------------------- меню -----------------------------
        self.create_menu()
        self.create_tray_icon()

        # --------------------------------- dock‑виджеты --------------------
        self.create_device_info_dock()
        self.create_command_history_dock()
        self.create_live_log_dock()

        # --------------------------------- вкладки -------------------------
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
        self.create_settings_tab()
        self.create_file_manager_tab()
        self.create_network_tab()
        self.create_permission_tab()
        self.create_root_tab()
        self.create_plugin_manager_tab()
        self.create_update_checker_tab()

        # --------------------------------- плагины -------------------------
        self.load_plugins()

        # --------------------------------- ADB ----------------------------
        self.check_adb()

        # --------------------------------- прочее -------------------------
        self.command_history = []          # список всех выполненных команд
        self.package_list    = []          # список пакетов (тестер)
        self.crashed_apps    = {}          # найденные проблемные пакеты
        self.testing         = False

        # --------------------------------- горячие клавиши ---------------
        self.apply_hotkeys()

        # --------------------------------- тема ---------------------------
        self.apply_theme()

        # Показ окна (в случае вызова из __init__)
        self.show()

    # ------------------------------------------------------------------
    #   Загрузка/сохранение настроек
    # ------------------------------------------------------------------
    def load_settings(self):
        if CONFIG_PATH.is_file():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.settings.update(json.load(f))
            except Exception as e:
                self.log_message(f"[SETTINGS] Не удалось загрузить: {e}")

    def save_settings(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.log_message(f"[SETTINGS] Не удалось сохранить: {e}")

    # ------------------------------------------------------------------
    #   Меню и трей‑иконка
    # ------------------------------------------------------------------
    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        exit_act  = QAction("Выход", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        view_menu = menubar.addMenu("Вид")
        self.dark_action = QAction("Тёмная тема", self, checkable=True)
        self.dark_action.setChecked(self.settings.get("theme_dark", False))
        self.dark_action.triggered.connect(self.toggle_dark_theme)
        view_menu.addAction(self.dark_action)

        tools_menu = menubar.addMenu("Инструменты")
        self.update_check_act = QAction("Проверить обновления", self)
        self.update_check_act.triggered.connect(self.check_updates_stub)
        tools_menu.addAction(self.update_check_act)

        help_menu = menubar.addMenu("Помощь")
        about_act = QAction("О программе", self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

    def toggle_dark_theme(self, checked: bool):
        self.settings["theme_dark"] = checked
        self.apply_theme()
        self.save_settings()

    def apply_theme(self):
        if self.settings.get("theme_dark", False):
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
        else:
            QApplication.instance().setPalette(
                QApplication.instance().style().standardPalette()
            )

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray_icon.setToolTip("xHelper – Android Helper")
        tray_menu = QMenu()
        show_act = QAction("Показать", self)
        quit_act = QAction("Выход", self)
        show_act.triggered.connect(self.show)
        quit_act.triggered.connect(self.close)
        tray_menu.addAction(show_act)
        tray_menu.addAction(quit_act)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show()

    # ------------------------------------------------------------------
    #   Dock‑виджеты
    # ------------------------------------------------------------------
    def create_device_info_dock(self):
        """Инфо‑панель о выбранном устройстве."""
        dock = QDockWidget("Информация об устройстве", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea |
                             Qt.DockWidgetArea.RightDockWidgetArea)

        widget = QWidget()
        layout = QFormLayout(widget)

        self.dev_model_lbl   = QLabel("-")
        self.dev_android_lbl = QLabel("-")
        self.dev_serial_lbl  = QLabel("-")
        self.dev_ip_lbl      = QLabel("-")
        self.dev_battery_lbl = QLabel("-")

        layout.addRow("Модель:",      self.dev_model_lbl)
        layout.addRow("Android:",     self.dev_android_lbl)
        layout.addRow("Серийный №:", self.dev_serial_lbl)
        layout.addRow("IP-адрес:",   self.dev_ip_lbl)
        layout.addRow("Батарея:",    self.dev_battery_lbl)

        dock.setWidget(widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        # При выборе устройства обновляем инфо
        self.device_list.itemSelectionChanged.connect(self.update_device_info)

    def create_command_history_dock(self):
        """Панель истории команд."""
        dock = QDockWidget("История команд", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea |
                             Qt.DockWidgetArea.TopDockWidgetArea)

        widget = QWidget()
        vlay = QVBoxLayout(widget)

        self.history_browser = QTextBrowser()
        self.history_browser.setOpenExternalLinks(False)
        self.history_browser.anchorClicked.connect(self.handle_history_click)

        clear_btn = QPushButton("Очистить историю")
        clear_btn.clicked.connect(lambda: self.history_browser.clear())

        vlay.addWidget(self.history_browser)
        vlay.addWidget(clear_btn)

        dock.setWidget(widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def handle_history_click(self, url):
        """Обрабатывает клик по записи истории (повторный запуск)."""
        cmd = url.toString()
        self.run_adb_command(cmd, device_specific=True)

    def create_live_log_dock(self):
        """Панель live‑logcat."""
        dock = QDockWidget("Live Logcat", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea |
                             Qt.DockWidgetArea.TopDockWidgetArea)

        widget = QWidget()
        vlay = QVBoxLayout(widget)

        self.live_log_edit = QTextEdit()
        self.live_log_edit.setReadOnly(True)

        self.live_log_btn = QPushButton("Запустить live‑logcat")
        self.live_log_btn.setCheckable(True)
        self.live_log_btn.toggled.connect(self.toggle_live_logcat)

        vlay.addWidget(self.live_log_edit)
        vlay.addWidget(self.live_log_btn)

        dock.setWidget(widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    def toggle_live_logcat(self, enabled: bool):
        """Запуск/остановка непрерывного logcat в отдельном потоке."""
        if enabled:
            self.live_log_edit.clear()
            self.live_log_thread = WorkerThread(self._live_logcat_worker)
            self.live_log_thread.log_signal.connect(self.live_log_edit.append)
            self.live_log_thread.finished_signal.connect(
                lambda: self.live_log_btn.setChecked(False)
            )
            self.live_log_thread.start()
        else:
            if hasattr(self, "live_log_thread"):
                self.live_log_thread.terminate()
                del self.live_log_thread

    def _live_logcat_worker(self):
        """Читает logcat построчно и эмитит сигналы."""
        cmd = ["adb", "logcat"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in proc.stdout:
            self.log_signal.emit(line.rstrip())
        proc.terminate()

    # ------------------------------------------------------------------
    #   Меню‑действия
    # ------------------------------------------------------------------
    def show_about(self):
        txt = (
            "xHelper pre‑alpha unstable dev test no support v0.0.5.8\n"
            "Автор: OpenAI ChatGPT\n"
            "Все функции находятся в активной разработке. "
            "Программа предоставляется «как есть» без каких‑либо гарантий."
        )
        QMessageBox.information(self, "О программе", txt)

    def check_updates_stub(self):
        """Псевдо‑проверка обновлений (заглушка)."""
        QMessageBox.information(self, "Проверка обновлений",
                                "Текущая версия – 0.0.5.8.\n"
                                "Автоматическая проверка отключена в pre‑alpha‑версии.")

    # ------------------------------------------------------------------
    #   Горячие клавиши
    # ------------------------------------------------------------------
    def apply_hotkeys(self):
        self.hotkeys = {}
        hk = self.settings.get("hotkeys", {})
        # Refresh devices
        seq = hk.get("RefreshDevices", "F5")
        self.hotkeys["Refresh"] = QShortcut(QKeySequence(seq), self)
        self.hotkeys["Refresh"].activated.connect(self.get_devices)
        # Open Logcat
        seq = hk.get("OpenLogcat", "Ctrl+L")
        self.hotkeys["Logcat"] = QShortcut(QKeySequence(seq), self)
        self.hotkeys["Logcat"].activated.connect(self.open_logcat_tab)
        # Start Scrcpy
        seq = hk.get("StartScrcpy", "Ctrl+S")
        self.hotkeys["Scrcpy"] = QShortcut(QKeySequence(seq), self)
        self.hotkeys["Scrcpy"].activated.connect(self.start_screen_stream)
        # Screenshot
        seq = hk.get("TakeScreenshot", "Ctrl+Shift+S")
        self.hotkeys["Screenshot"] = QShortcut(QKeySequence(seq), self)
        self.hotkeys["Screenshot"].activated.connect(self.take_screenshot)

    def open_logcat_tab(self):
        idx = self.tabs.indexOf(self.logcat_tab)
        if idx != -1:
            self.tabs.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    #   Логика работы с ADB
    # ------------------------------------------------------------------
    def check_adb(self):
        """Проверка доступности ADB, поиск в PATH или пользовательский путь."""
        adb_path = self.settings.get("adb_path", "adb")
        try:
            result = subprocess.run([adb_path, '--version'],
                                    capture_output=True,
                                    text=True,
                                    timeout=5)
            if result.returncode == 0:
                self.log_message("ADB доступен")
                self.get_devices()
            else:
                self.log_message("ADB не найден. Укажите путь в Настройках.")
        except (FileNotFoundError, subprocess.SubprocessError):
            self.log_message("ADB не найден. Укажите путь в Настройках.")

    def get_devices(self):
        """Получаем список подключённых устройств."""
        adb_path = self.settings.get("adb_path", "adb")
        try:
            result = subprocess.run([adb_path, "devices"],
                                    capture_output=True,
                                    text=True,
                                    timeout=10)
            lines = result.stdout.strip().splitlines()[1:]  # без заголовка
            devices = [line.split('\t')[0] for line in lines
                       if line.strip() and '\tdevice' in line]
            self.device_list.clear()
            if devices:
                self.device_list.addItems(devices)
                self.log_message(f"Найдено устройств: {len(devices)}")
            else:
                self.log_message("Устройства не найдены")
        except Exception as e:
            self.log_message(f"Ошибка получения списка устройств: {e}")

    def run_adb_command(self, command: str, device_specific: bool = True):
        """
        Выполняет произвольную ADB‑команду.

        device_specific – True – использовать выбранное устройство (или все выбранные
        при включённом чекбоксе), False – глобальная команда без указания устройства.
        """
        adb_path = self.settings.get("adb_path", "adb")
        if device_specific:
            selected = self.device_list.selectedItems()
            if not selected:
                self.log_message("Не выбрано устройство")
                return
            devices = [it.text() for it in selected]
            if not self.run_all_checkbox.isChecked():
                devices = [devices[0]]
        else:
            devices = [None]        # глобальная команда

        for dev in devices:
            if dev:
                full_cmd = [adb_path, '-s', dev] + command.split()
            else:
                full_cmd = [adb_path] + command.split()

            try:
                self.log_message(f"Выполняю: {' '.join(full_cmd)}")
                result = subprocess.run(full_cmd,
                                        capture_output=True,
                                        text=True,
                                        timeout=30)
                # вывод в консоль
                if result.stdout:
                    self.log_message(result.stdout.strip())
                if result.stderr:
                    self.log_message(result.stderr.strip())
                if result.returncode != 0:
                    self.log_message(f"Код возврата: {result.returncode}")
                # сохраняем в историю
                self.command_history.append(' '.join(full_cmd))
                self.history_browser.append(f'<a href="{html.escape(" ".join(full_cmd))}">{html.escape(" ".join(full_cmd))}</a>')
                # запись в файл (если включено)
                if self.settings.get("log_to_file", False):
                    with open(self.settings["log_file_path"], "a", encoding="utf-8") as lf:
                        lf.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {' '.join(full_cmd)}\n")
                        if result.stdout:
                            lf.write(result.stdout)
                        if result.stderr:
                            lf.write(result.stderr)
            except subprocess.TimeoutExpired:
                self.log_message("Команда превысила таймаут (30 сек.)")
            except Exception as e:
                self.log_message(f"Ошибка выполнения команды: {e}")

    def run_adb_package_command(self, base_cmd: str):
        """Запрашивает у пользователя имя пакета и запускает ADB‑команду."""
        if not self.device_list.currentItem():
            QMessageBox.warning(self, "Ошибка", "Сначала выберите устройство.")
            return
        pkg, ok = QInputDialog.getText(
            self,
            "Имя пакета",
            "Введите полное имя пакета (пример: com.example.app):"
        )
        if ok and pkg:
            self.run_adb_command(f"{base_cmd} {pkg}", device_specific=True)

    def update_device_info(self):
        """Обновление информации о выбранном в списке устройстве."""
        if not self.device_list.currentItem():
            # очистка полей
            for lbl in [self.dev_model_lbl, self.dev_android_lbl,
                        self.dev_serial_lbl, self.dev_ip_lbl,
                        self.dev_battery_lbl]:
                lbl.setText("-")
            return

        device = self.device_list.currentItem().text()
        adb = self.settings.get("adb_path", "adb")
        def fetch(prop):
            try:
                out = subprocess.check_output(
                    [adb, "-s", device, "shell", "getprop", prop],
                    text=True, timeout=5
                ).strip()
                return out
            except Exception:
                return "N/A"

        self.dev_model_lbl.setText(fetch("ro.product.model"))
        self.dev_android_lbl.setText(fetch("ro.build.version.release"))
        self.dev_serial_lbl.setText(fetch("ro.serialno"))

        # IP‑address (wifi0)
        ip = "N/A"
        try:
            out = subprocess.check_output(
                [adb, "-s", device, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
                text=True, timeout=5
            )
            for line in out.splitlines():
                if "inet " in line:
                    ip = line.split()[1]
                    break
        except Exception:
            pass
        self.dev_ip_lbl.setText(ip)

        # Battery level
        bat = "N/A"
        try:
            out = subprocess.check_output(
                [adb, "-s", device, "shell", "dumpsys", "battery"],
                text=True, timeout=5
            )
            for line in out.splitlines():
                if "level:" in line:
                    bat = line.split(":")[1].strip()
                    break
        except Exception:
            pass
        self.dev_battery_lbl.setText(f"{bat}%")

    # ------------------------------------------------------------------
    #   Универсальная запись в консоль
    # ------------------------------------------------------------------
    def log_message(self, message: str):
        """Записывает сообщение в главную консоль с отметкой времени."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"[{ts}] {message}")

    def set_progress(self, value: int):
        """Отображает прогресс в статус‑баре."""
        self.progress_bar.setValue(value)

    # ------------------------------------------------------------------
    #   Вкладка «Устройства» (уже реализована в оригинальном коде)
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

        self.run_all_checkbox = QCheckBox("Выполнять на всех выбранных")
        device_layout.addWidget(self.device_list)
        device_layout.addWidget(refresh_btn)
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
    #   Вкладка «APK» (уже реализована)
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
            ("Системные",                         "shell pm list packages -s"),
            ("Сторонние",                         "shell pm list packages -3")
        ]

        for i, (txt, cmd) in enumerate(simple_cmds):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            package_layout.addWidget(btn, i // 3, i % 3)

        pkg_cmds = [
            ("Очистить данные",                   "shell pm clear"),
            ("Удалить",                           "uninstall"),
            ("Запуск",                            "shell monkey -p")
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
    #   Вкладка «Массовая установка APK» (уже реализована)
    # ------------------------------------------------------------------
    def create_mass_apk_tab(self):
        mass_tab = QWidget()
        layout = QVBoxLayout(mass_tab)

        folder_group = QGroupBox("Папка с APK")
        folder_layout = QVBoxLayout(folder_group)

        self.folder_path = QLineEdit()
        browse_folder_btn = QPushButton("Выбрать папку")
        browse_folder_btn.clicked.connect(self.select_apk_folder)

        folder_layout.addWidget(QLabel("Путь к папке:"))
        folder_layout.addWidget(self.folder_path)
        folder_layout.addWidget(browse_folder_btn)

        install_group = QGroupBox("Массовая установка")
        install_layout = QVBoxLayout(install_group)

        self.apk_count_label = QLabel("APK‑файлы не выбраны")
        self.progress_bar = QProgressBar()
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

        # соединяем сигнал прогресса
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

        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write(f"Лог массовой установки – {datetime.now()}\n")
            lf.write("=" * 50 + "\n")
            for i, apk_path in enumerate(self.apk_files):
                if self.stop_installation:
                    self.log_signal.emit("Установка остановлена пользователем")
                    break

                self.log_signal.emit(f"[{i+1}/{total}] Устанавливаем {apk_path}")

                try:
                    result = subprocess.run(
                        ["adb", "install", "-r", apk_path],
                        capture_output=True,
                        text=True,
                        timeout=360
                    )
                    if result.returncode == 0:
                        success += 1
                        status = "success"
                        details = "Installed"
                        msg = f"УСПЕХ: {apk_path}"
                        self.log_signal.emit(msg)
                        lf.write(msg + "\n")
                    else:
                        failed += 1
                        status = "failed"
                        details = result.stderr.strip()
                        msg = f"ОШИБКА: {apk_path}\n{details}"
                        self.log_signal.emit(msg)
                        lf.write(msg + "\n")
                except subprocess.TimeoutExpired:
                    failed += 1
                    status = "timeout"
                    details = "Таймаут (6 мин.)"
                    msg = f"ТАЙМАУТ: {apk_path}"
                    self.log_signal.emit(msg)
                    lf.write(msg + "\n")
                except Exception as e:
                    failed += 1
                    status = "exception"
                    details = str(e)
                    msg = f"ИСКЛЮЧЕНИЕ: {apk_path} – {details}"
                    self.log_signal.emit(msg)
                    lf.write(msg + "\n")

                entries.append({
                    "package": os.path.basename(apk_path),
                    "status":  status,
                    "details": details
                })
                self.progress_signal.emit(i + 1)

            lf.write("=" * 50 + "\n")
            lf.write(f"Успешно: {success}\n")
            lf.write(f"Не удалось: {failed}\n")
            lf.write(f"Всего: {success + failed}\n")

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
            QMessageBox.warning(self, "Готово",
                                f"Установка завершена с ошибками.\nУспешно: {success}\nОшибки: {failed}")

    # ------------------------------------------------------------------
    #   Вкладка «Файлы» (push / pull)
    # ------------------------------------------------------------------
    def create_file_operations_tab(self):
        file_tab = QWidget()
        layout = QVBoxLayout(file_tab)

        # Push
        push_group = QGroupBox("Отправка файлов")
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
        pull_group = QGroupBox("Получение файлов")
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
            ("Батарея",                         "shell dumpsys battery"),
            ("CPU‑info",                        "shell cat /proc/cpuinfo"),
            ("Memory‑info",                     "shell cat /proc/meminfo"),
            ("Сетевые соединения",              "shell netstat"),
            ("Текущая активность",              "shell dumpsys activity activities | grep mResumedActivity"),
            ("Запущенные процессы",             "shell ps"),
            ("Wi‑Fi",                           "shell dumpsys wifi"),
            ("Дисплей",                         "shell dumpsys display"),
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

        actions = [
            ("Запуск logcat",                                   "logcat"),
            ("Очистить логи",                                   "logcat -c"),
            ("Сохранить в файл",                                 "logcat -d -f /sdcard/logcat.txt"),
            ("Только ошибки",                                   "logcat *:E"),
            ("Bugreport",                                       "bugreport")
        ]

        for txt, cmd in actions:
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            log_layout.addWidget(btn)

        layout.addWidget(log_group)
        self.tabs.addTab(logcat_tab, "Логи")
        self.logcat_tab = logcat_tab   # для быстрого доступа

    # ------------------------------------------------------------------
    #   Вкладка «Перезагрузка»
    # ------------------------------------------------------------------
    def create_reboot_tab(self):
        reboot_tab = QWidget()
        layout = QVBoxLayout(reboot_tab)

        reboot_group = QGroupBox("Режимы перезагрузки")
        reboot_layout = QGridLayout(reboot_group)

        buttons = [
            ("🔄 Обычная",           "reboot"),
            ("🛠 Recovery",        "reboot recovery"),
            ("⚡ Bootloader",      "reboot bootloader"),
            ("🛡 Safe mode",       "shell am broadcast -a android.intent.action.REBOOT --ez android.intent.extra.IS_SAFE_MODE true"),
            ("📡 EDL (Qualcomm)",  "reboot edl"),
            ("⏻ Выключить",        "shell reboot -p")
        ]

        for i, (txt, cmd) in enumerate(buttons):
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

        ctrl_group = QGroupBox("Управление тестированием")
        ctrl_layout = QVBoxLayout(ctrl_group)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Задержка (сек):"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(5, 60)
        self.delay_spinbox.setValue(10)
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()

        btn_layout = QHBoxLayout()
        self.get_packages_btn = QPushButton("Получить приложения")
        self.get_packages_btn.clicked.connect(self.get_user_packages)

        self.start_test_btn = QPushButton("Начать тест")
        self.start_test_btn.clicked.connect(self.start_app_testing)
        self.start_test_btn.setEnabled(False)

        self.stop_test_btn = QPushButton("Остановить")
        self.stop_test_btn.clicked.connect(self.stop_app_testing)
        self.stop_test_btn.setEnabled(False)

        btn_layout.addWidget(self.get_packages_btn)
        btn_layout.addWidget(self.start_test_btn)
        btn_layout.addWidget(self.stop_test_btn)

        ctrl_layout.addLayout(delay_layout)
        ctrl_layout.addLayout(btn_layout)

        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        ctrl_layout.addWidget(self.test_progress)

        # результаты
        res_group = QGroupBox("Результаты")
        res_layout = QVBoxLayout(res_group)

        self.app_tree = QTreeWidget()
        self.app_tree.setHeaderLabels(["Имя", "Пакет", "Статус"])
        self.app_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        res_layout.addWidget(self.app_tree)

        act_layout = QHBoxLayout()
        self.delete_selected_btn = QPushButton("Удалить выбранные")
        self.delete_selected_btn.clicked.connect(self.delete_selected_apps)
        self.delete_selected_btn.setEnabled(False)

        self.delete_all_btn = QPushButton("Удалить все проблемные")
        self.delete_all_btn.clicked.connect(self.delete_all_problematic_apps)
        self.delete_all_btn.setEnabled(False)

        act_layout.addWidget(self.delete_selected_btn)
        act_layout.addWidget(self.delete_all_btn)

        res_layout.addLayout(act_layout)

        layout.addWidget(ctrl_group)
        layout.addWidget(res_group)
        self.tabs.addTab(tester_tab, "Тестирование приложений")

    def get_user_packages(self):
        self.log_message("Запрашиваем список пользовательских приложений...")
        try:
            out = subprocess.check_output(
                ["adb", "shell", "pm", "list", "packages", "-3"],
                text=True, timeout=10
            )
            self.package_list = [line.replace("package:", "").strip()
                                 for line in out.splitlines()
                                 if line.strip()]
            self.log_message(f"Найдено {len(self.package_list)} приложений")
            self.start_test_btn.setEnabled(True)

            self.app_tree.clear()
            for pkg in self.package_list:
                it = QTreeWidgetItem(self.app_tree)
                it.setText(0, "—")
                it.setText(1, pkg)
                it.setText(2, "Ожидание")
                it.setForeground(2, QColor("gray"))
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка получения пакетов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить список приложений:\n{e}")

    def start_app_testing(self):
        if not self.package_list:
            QMessageBox.warning(self, "Внимание", "Сначала получите список приложений")
            return
        self.testing = True
        self.crashed_apps = {}
        self.start_test_btn.setEnabled(False)
        self.stop_test_btn.setEnabled(True)
        self.test_progress.setVisible(True)
        self.test_progress.setMaximum(len(self.package_list))
        self.test_progress.setValue(0)
        self.log_message("Запуск тестирования")

        self.test_thread = WorkerThread(self.test_applications_thread)
        self.test_thread.finished_signal.connect(self.testing_finished)
        self.test_thread.start()

    def stop_app_testing(self):
        self.testing = False
        self.log_message("Тестирование остановлено пользователем")

    def testing_finished(self):
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
            for i, pkg in enumerate(self.package_list):
                if not self.testing:
                    break

                res = self.test_application(pkg)

                if res["crashed"]:
                    self.update_app_test_status(i,
                                                f"Ошибок: {res['error_count']}",
                                                "red")
                    self.crashed_apps[pkg] = res
                else:
                    self.update_app_test_status(i, "OK", "green")

                self.progress_signal.emit(i + 1)

                for sec in range(delay, 0, -1):
                    if not self.testing:
                        break
                    self.log_signal.emit(f"Ожидание {sec} сек. перед следующим тестом...")
                    time.sleep(1)

            if self.crashed_apps:
                self.log_signal.emit(f"Тест завершён. Проблемных: {len(self.crashed_apps)}")
            else:
                self.log_signal.emit("Тест завершён. Проблемных приложений нет")
        except Exception as e:
            self.log_signal.emit(f"Ошибка в тестировщике: {e}")

    def test_application(self, pkg: str) -> dict:
        """Запуск, сбор логов, проверка FATAL/CRASH."""
        result = {"crashed": False, "error_count": 0, "name": pkg}
        try:
            subprocess.run(["adb", "logcat", "-c"], capture_output=True)
            subprocess.run(
                ["adb", "shell", "monkey", "-p", pkg,
                 "-c", "android.intent.category.LAUNCHER", "1"],
                capture_output=True, timeout=5
            )
            time.sleep(3)
            log = subprocess.run(
                ["adb", "logcat", "-d", "-v", "brief", "*:E"],
                capture_output=True, text=True, timeout=10
            )
            if log.stdout:
                cnt = log.stdout.count("FATAL") + log.stdout.count("CRASH")
                if cnt > 0 and pkg in log.stdout:
                    result["crashed"] = True
                    result["error_count"] = cnt
            subprocess.run(["adb", "shell", "am", "force-stop", pkg],
                           capture_output=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            result["crashed"] = True
            result["error_count"] = 1
        except Exception as e:
            result["crashed"] = True
            result["error_count"] = 1
            self.log_signal.emit(f"Исключение в test_application: {e}")
        return result

    def update_app_test_status(self, index: int, status: str, color_name: str):
        it = self.app_tree.topLevelItem(index)
        if it:
            it.setText(2, status)
            it.setForeground(2, QColor(color_name))

    def delete_selected_apps(self):
        selected = self.app_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Внимание", "Не выбрано приложение")
            return
        reply = QMessageBox.question(
            self, "Подтверждение",
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
            self, "Подтверждение",
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

    def uninstall_package(self, pkg: str) -> bool:
        try:
            out = subprocess.run(
                ["adb", "uninstall", pkg],
                capture_output=True, text=True, timeout=30
            )
            if out.stdout and "Success" in out.stdout:
                self.log_message(f"Успешно удалено: {pkg}")
                return True
            else:
                self.log_message(f"Не удалось удалить {pkg}: {out.stdout or out.stderr}")
                return False
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка удаления {pkg}: {e}")
            return False

    # ------------------------------------------------------------------
    #   Вкладка «Экран устройства» (scrcpy)
    # ------------------------------------------------------------------
    def create_screen_mirror_tab(self):
        scr_tab = QWidget()
        layout = QVBoxLayout(scr_tab)

        grp = QGroupBox("Управление экраном")
        grp_layout = QVBoxLayout(grp)

        self.start_stream_btn = QPushButton("Запуск scrcpy")
        self.start_stream_btn.clicked.connect(self.start_screen_stream)

        self.stop_stream_btn = QPushButton("Остановить scrcpy")
        self.stop_stream_btn.clicked.connect(self.stop_screen_stream)
        self.stop_stream_btn.setEnabled(False)

        self.screenshot_btn = QPushButton("Скриншот")
        self.screenshot_btn.clicked.connect(self.take_screenshot)

        grp_layout.addWidget(self.start_stream_btn)
        grp_layout.addWidget(self.stop_stream_btn)
        grp_layout.addWidget(self.screenshot_btn)

        layout.addWidget(grp)
        self.tabs.addTab(scr_tab, "Экран устройства")

    def start_screen_stream(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return
        # проверяем, установлен scrcpy
        try:
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            QMessageBox.critical(self, "Ошибка", "scrcpy не найден в PATH")
            return
        self.log_message("Запуск scrcpy …")
        self.start_stream_btn.setEnabled(False)
        self.stop_stream_btn.setEnabled(True)
        self.scrcpy_process = subprocess.Popen(
            ["scrcpy", "--max-fps", "60", "--window-title", "xHelper – Android Screen"]
        )

    def stop_screen_stream(self):
        if hasattr(self, "scrcpy_process"):
            self.scrcpy_process.terminate()
            self.scrcpy_process = None
            self.log_message("scrcpy остановлен")
        self.start_stream_btn.setEnabled(True)
        self.stop_stream_btn.setEnabled(False)

    def take_screenshot(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить скриншот",
            f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png",
            "PNG Files (*.png)"
        )
        if not path:
            return
        try:
            with open(path, "wb") as f:
                subprocess.run(
                    ["adb", "exec-out", "screencap", "-p"],
                    stdout=f, check=True
                )
            self.log_message(f"Скриншот сохранён: {path}")
            QMessageBox.information(self, "Успех", f"Скриншот сохранён:\n{path}")
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка скриншота: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить скриншот:\n{e}")

    def check_device_connected(self) -> bool:
        try:
            out = subprocess.check_output(
                ["adb", "devices"], text=True, timeout=5
            )
            lines = out.strip().splitlines()[1:]
            return any("device" in line for line in lines if line.strip())
        except Exception:
            return False

    # ------------------------------------------------------------------
    #   Вкладка «Мониторинг» (CPU, память, батарея, сеть)
    # ------------------------------------------------------------------
    def create_monitor_tab(self):
        mon_tab = QWidget()
        layout = QVBoxLayout(mon_tab)

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
        self.monitor_timer.start(5000)   # каждые 5 сек.

        self.tabs.addTab(mon_tab, "Мониторинг")

    def update_monitor(self):
        if not self.check_device_connected():
            for key, lbl in self.monitor_labels.items():
                lbl.setText(f"{key}: N/A")
            return

        # Battery
        try:
            bat_out = subprocess.check_output(
                ["adb", "shell", "dumpsys", "battery"], text=True, timeout=5
            )
            level = "?"
            for line in bat_out.splitlines():
                if "level:" in line:
                    level = line.split(":")[1].strip()
                    break
            self.monitor_labels["Battery"].setText(f"Battery: {level}%")
        except Exception:
            self.monitor_labels["Battery"].setText("Battery: N/A")

        # CPU (упрощённо, выводим "N/A")
        self.monitor_labels["CPU"].setText("CPU: N/A")

        # Memory
        try:
            mem_out = subprocess.check_output(
                ["adb", "shell", "cat", "/proc/meminfo"],
                text=True, timeout=5
            )
            total = free = None
            for line in mem_out.splitlines():
                if line.startswith("MemTotal:"):
                    total = line.split(":")[1].strip()
                elif line.startswith("MemFree:"):
                    free = line.split(":")[1].strip()
            if total and free:
                self.monitor_labels["Memory"].setText(f"Memory: {free} free / {total}")
            else:
                self.monitor_labels["Memory"].setText("Memory: N/A")
        except Exception:
            self.monitor_labels["Memory"].setText("Memory: N/A")

        # Network – IP‑адрес wlan0
        try:
            ip_out = subprocess.check_output(
                ["adb", "shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
                text=True, timeout=5
            )
            ip = "?"
            for line in ip_out.splitlines():
                if "inet " in line:
                    ip = line.strip().split()[1]
                    break
            self.monitor_labels["Network"].setText(f"Network (wlan0): {ip}")
        except Exception:
            self.monitor_labels["Network"].setText("Network: N/A")

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
    #   Вкладка «Запись экрана (screenrecord)»
    # ------------------------------------------------------------------
    def create_screen_record_tab(self):
        record_tab = QWidget()
        layout = QVBoxLayout(record_tab)

        self.start_rec_btn = QPushButton("Начать запись")
        self.start_rec_btn.clicked.connect(self.start_screen_record)

        self.stop_rec_btn = QPushButton("Остановить запись")
        self.stop_rec_btn.clicked.connect(self.stop_screen_record)
        self.stop_rec_btn.setEnabled(False)

        self.save_rec_btn = QPushButton("Сохранить запись")
        self.save_rec_btn.clicked.connect(self.save_screen_record)
        self.save_rec_btn.setEnabled(False)

        layout.addWidget(self.start_rec_btn)
        layout.addWidget(self.stop_rec_btn)
        layout.addWidget(self.save_rec_btn)

        self.tabs.addTab(record_tab, "Запись экрана")

    def start_screen_record(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return
        self.log_message("Запуск screenrecord …")
        self.screenrecord_process = subprocess.Popen(
            ["adb", "shell", "screenrecord", "/sdcard/xHelper_record.mp4"]
        )
        self.start_rec_btn.setEnabled(False)
        self.stop_rec_btn.setEnabled(True)

    def stop_screen_record(self):
        if hasattr(self, "screenrecord_process"):
            self.screenrecord_process.terminate()
            self.screenrecord_process.wait()
            self.log_message("Запись остановлена")
        self.start_rec_btn.setEnabled(True)
        self.stop_rec_btn.setEnabled(False)
        self.save_rec_btn.setEnabled(True)

    def save_screen_record(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить запись",
            f"record_{datetime.now():%Y%m%d_%H%M%S}.mp4",
            "MP4 Files (*.mp4)"
        )
        if not save_path:
            return
        self.log_message(f"Копирование записи в {save_path} …")
        self.run_adb_command(f"pull /sdcard/xHelper_record.mp4 {save_path}", device_specific=False)
        self.run_adb_command("shell rm /sdcard/xHelper_record.mp4", device_specific=False)
        QMessageBox.information(self, "Готово", f"Запись сохранена:\n{save_path}")
        self.save_rec_btn.setEnabled(False)

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
        fb_tab = QWidget()
        layout = QVBoxLayout(fb_tab)

        list_btn = QPushButton("Список Fastboot‑устройств")
        list_btn.clicked.connect(self.fastboot_devices)

        # flash
        flash_layout = QHBoxLayout()
        self.flash_file_path = QLineEdit()
        browse_flash_btn = QPushButton("Файл")
        browse_flash_btn.clicked.connect(self.select_flash_file)
        flash_btn = QPushButton("Flash (system)")
        flash_btn.clicked.connect(self.flash_fastboot)

        flash_layout.addWidget(self.flash_file_path)
        flash_layout.addWidget(browse_flash_btn)
        flash_layout.addWidget(flash_btn)

        # erase
        erase_layout = QHBoxLayout()
        self.erase_partition_input = QLineEdit()
        self.erase_partition_input.setPlaceholderText("Имя раздела (пример: system)")
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

        self.tabs.addTab(fb_tab, "Fastboot")

    def fastboot_devices(self):
        try:
            out = subprocess.check_output(["fastboot", "devices"], text=True, timeout=5)
            self.log_message("Fastboot‑устройства:")
            self.log_message(out.strip() or "Не найдено")
        except FileNotFoundError:
            self.log_message("fastboot не найден в PATH")
        except Exception as e:
            self.log_message(f"Ошибка fastboot devices: {e}")

    def select_flash_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл для flash", "", "All Files (*)")
        if path:
            self.flash_file_path.setText(path)

    def flash_fastboot(self):
        path = self.flash_file_path.text().
