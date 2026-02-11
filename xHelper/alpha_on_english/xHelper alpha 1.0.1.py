#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
xHelper alpha 1.0.1 LTS/ATS
GUI utility for managing Android devices via ADB.
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
#   Worker thread – universal executor for arbitrary functions
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
            self.log_signal.emit(f"Error in thread: {str(e)}")
        finally:
            self.finished_signal.emit()


# ----------------------------------------------------------------------
#   Information dialog about the application
# ----------------------------------------------------------------------
class AppInfoDialog(QDialog):
    def __init__(self, app_info: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Information")
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
#   Main window – renamed to XHelperMainWindow
# ----------------------------------------------------------------------
class XHelperMainWindow(QMainWindow):
    log_signal      = pyqtSignal(str)   # for logging text
    progress_signal = pyqtSignal(int)   # unified progress signal

    # ------------------------------------------------------------------
    #   Initialization
    # ------------------------------------------------------------------
    def __init__(self):
        super().__init__()
        self.setWindowTitle("xHelper alpha 1.0.1 LTS/ATS")
        self.setGeometry(100, 100, 1400, 900)

        # ------------------ menu ------------------
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

        # ------------------ signals -------------
        self.log_signal.connect(self.log_message)
        self.progress_signal.connect(self.update_test_progress)   # test progress

        # ------------------ tabs -----------------
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

        # ------------------ plugins ----------------
        self.load_plugins()

        # ------------------ ADB --------------------
        self.check_adb()

        # ------------------ variables -------------
        self.apk_files           = []
        self.install_in_progress = False
        self.stop_installation   = False

        self.packages    = []
        self.crashed_apps = {}
        self.testing     = False

    # ------------------------------------------------------------------
    #   Menu and themes
    # ------------------------------------------------------------------
    def create_menu(self):
        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")
        self.toggle_dark_action = QAction("Dark Theme", self, checkable=True)
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
    #   Plugin system
    # ------------------------------------------------------------------
    def load_plugins(self):
        plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
        if not os.path.isdir(plugins_dir):
            self.log_message("Plugins folder not found – no plugins loaded.")
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
                        self.log_message(f"Plugin loaded: {fn}")
                except Exception as e:
                    self.log_message(f"Error loading plugin {fn}: {e}")

    # ------------------------------------------------------------------
    #   Check ADB availability
    # ------------------------------------------------------------------
    def check_adb(self):
        """Check access to ADB."""
        try:
            result = subprocess.run(['adb', '--version'],
                                    capture_output=True,
                                    text=True)
            if result.returncode == 0:
                self.log_message("ADB is available")
                self.get_devices()
            else:
                self.log_message("ADB not found. Install it and add to PATH.")
        except FileNotFoundError:
            self.log_message("ADB not found. Install it and add to PATH.")

    def get_devices(self):
        """Obtain list of connected devices."""
        result = subprocess.run(['adb', 'devices'],
                                capture_output=True,
                                text=True)
        lines = result.stdout.split('\n')[1:]                     # first line is header
        devices = [line.split('\t')[0] for line in lines
                   if line.strip() and '\tdevice' in line]

        self.device_list.clear()
        if devices:
            self.device_list.addItems(devices)
            self.log_message(f"Devices found: {len(devices)}")
        else:
            self.log_message("No devices found")

    # ------------------------------------------------------------------
    #   Execute ADB commands
    # ------------------------------------------------------------------
    def run_adb_command(self, command: str, device_specific: bool = True):
        """
        Executes an ADB command.

        If device_specific=True – the command will be executed on the selected
        device(s). When the “Run on all selected” checkbox is checked,
        the command will run on all selected devices; otherwise only on the first.
        """
        if device_specific:
            selected = self.device_list.selectedItems()
            if not selected:
                self.log_message("No device selected")
                return
            devices = [it.text() for it in selected]
            if not self.run_all_checkbox.isChecked():
                devices = [devices[0]]
        else:
            devices = [None]  # global command

        for dev in devices:
            if dev:
                full_cmd = ['adb', '-s', dev] + command.split()
            else:
                full_cmd = ['adb'] + command.split()
            try:
                self.log_message(f"Executing: {' '.join(full_cmd)}")
                result = subprocess.run(full_cmd,
                                        capture_output=True,
                                        text=True,
                                        timeout=30)
                if result.stdout:
                    self.log_message("Result:")
                    self.log_message(result.stdout)
                if result.stderr:
                    self.log_message("Errors:")
                    self.log_message(result.stderr)
                if result.returncode != 0:
                    self.log_message(f"Command exited with code: {result.returncode}")
            except subprocess.TimeoutExpired:
                self.log_message("Command timed out (30 sec.)")
            except Exception as e:
                self.log_message(f"Error executing command: {str(e)}")

    def run_adb_package_command(self, base_cmd: str):
        """Prompt the user for a package name and execute the command."""
        if not self.device_list.currentItem():
            QMessageBox.warning(self, "Error", "Select a device first.")
            return
        pkg, ok = QInputDialog.getText(
            self,
            "Package name",
            "Enter the full package name (e.g., com.example.app):"
        )
        if ok and pkg:
            self.run_adb_command(f"{base_cmd} {pkg}")

    # ------------------------------------------------------------------
    #   Universal logging
    # ------------------------------------------------------------------
    def log_message(self, message: str):
        """Write a timestamped message to the console."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"[{ts}] {message}")

    # ------------------------------------------------------------------
    #   Devices tab
    # ------------------------------------------------------------------
    def create_device_tab(self):
        device_tab = QWidget()
        layout = QVBoxLayout(device_tab)

        # Device list
        device_group = QGroupBox("Connected Devices")
        device_layout = QVBoxLayout(device_group)

        self.device_list = QListWidget()
        self.device_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        refresh_btn = QPushButton("Refresh device list")
        refresh_btn.clicked.connect(self.get_devices)

        device_layout.addWidget(self.device_list)
        device_layout.addWidget(refresh_btn)

        # “Run on all selected” checkbox
        self.run_all_checkbox = QCheckBox("Run on all selected")
        device_layout.addWidget(self.run_all_checkbox)

        # Power management
        reboot_group = QGroupBox("Power Management")
        reboot_layout = QGridLayout(reboot_group)

        reboot_buttons = [
            ("Reboot",               "reboot"),
            ("Recovery",             "reboot recovery"),
            ("Bootloader",           "reboot bootloader"),
            ("Fastboot",             "reboot fastboot")
        ]

        for i, (txt, cmd) in enumerate(reboot_buttons):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            reboot_layout.addWidget(btn, i // 2, i % 2)

        layout.addWidget(device_group)
        layout.addWidget(reboot_group)
        self.tabs.addTab(device_tab, "Devices")

    # ------------------------------------------------------------------
    #   APK tab
    # ------------------------------------------------------------------
    def create_apk_tab(self):
        apk_tab = QWidget()
        layout = QVBoxLayout(apk_tab)

        # Install single APK
        install_group = QGroupBox("Install APK")
        install_layout = QVBoxLayout(install_group)

        self.apk_path = QLineEdit()
        browse_btn = QPushButton("Browse APK")
        browse_btn.clicked.connect(self.select_apk)

        install_btn = QPushButton("Install APK")
        install_btn.clicked.connect(self.install_apk)

        install_layout.addWidget(QLabel("APK Path:"))
        install_layout.addWidget(self.apk_path)
        install_layout.addWidget(browse_btn)
        install_layout.addWidget(install_btn)

        # Application management
        package_group = QGroupBox("Application Management")
        package_layout = QGridLayout(package_group)

        simple_cmds = [
            ("List apps",                 "shell pm list packages"),
            ("List system apps",          "shell pm list packages -s"),
            ("List third‑party apps",     "shell pm list packages -3")
        ]

        for i, (txt, cmd) in enumerate(simple_cmds):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            package_layout.addWidget(btn, i // 3, i % 3)

        pkg_cmds = [
            ("Clear data",                "shell pm clear"),
            ("Uninstall app",            "uninstall"),
            ("Launch app",                "shell monkey -p")
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
            self, "Select APK file", "", "APK Files (*.apk)"
        )
        if file_path:
            self.apk_path.setText(file_path)

    def install_apk(self):
        apk = self.apk_path.text()
        if not apk:
            QMessageBox.warning(self, "Error", "Select an APK file")
            return
        if not os.path.exists(apk):
            QMessageBox.warning(self, "Error", "File does not exist")
            return
        self.run_adb_command(f"install -r {apk}")

    # ------------------------------------------------------------------
    #   Mass APK installation tab
    # ------------------------------------------------------------------
    def create_mass_apk_tab(self):
        mass_tab = QWidget()
        layout = QVBoxLayout(mass_tab)

        # Folder with APKs
        folder_group = QGroupBox("Select APK folder")
        folder_layout = QVBoxLayout(folder_group)

        self.folder_path = QLineEdit()
        browse_folder_btn = QPushButton("Browse APK folder")
        browse_folder_btn.clicked.connect(self.select_apk_folder)

        folder_layout.addWidget(QLabel("Folder Path:"))
        folder_layout.addWidget(self.folder_path)
        folder_layout.addWidget(browse_folder_btn)

        # Mass installation controls
        install_group = QGroupBox("Mass Installation")
        install_layout = QVBoxLayout(install_group)

        self.apk_count_label = QLabel("No APK files selected")
        self.progress_bar    = QProgressBar()
        self.progress_bar.setVisible(False)

        self.start_install_btn = QPushButton("Start installation")
        self.start_install_btn.clicked.connect(self.start_mass_installation)

        self.stop_install_btn = QPushButton("Stop installation")
        self.stop_install_btn.clicked.connect(self.stop_mass_installation)
        self.stop_install_btn.setEnabled(False)

        install_layout.addWidget(self.apk_count_label)
        install_layout.addWidget(self.progress_bar)
        install_layout.addWidget(self.start_install_btn)
        install_layout.addWidget(self.stop_install_btn)

        layout.addWidget(folder_group)
        layout.addWidget(install_group)
        self.tabs.addTab(mass_tab, "Mass APK Installation")

    def select_apk_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select APK folder")
        if folder:
            self.folder_path.setText(folder)
            self.apk_files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith('.apk')
            ]
            self.apk_count_label.setText(f"APK files found: {len(self.apk_files)}")

    def start_mass_installation(self):
        if not self.apk_files:
            QMessageBox.warning(self, "Error", "Select an APK folder first")
            return
        if self.install_in_progress:
            QMessageBox.information(self, "Info", "Installation already in progress")
            return

        self.install_in_progress = True
        self.stop_installation = False
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.apk_files))
        self.progress_bar.setValue(0)

        # connect progress signal
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
            self.log_message("Installation aborted by user")
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

        self.log_signal.emit(f"Beginning mass installation of {total} APK files")
        log_file = f"install_log_{datetime.now():%Y%m%d_%H%M%S}.txt"

        with open(log_file, 'w', encoding='utf-8') as log_f:
            log_f.write(f"Mass installation log – {datetime.now()}\n")
            log_f.write("=" * 50 + "\n")

            for i, apk_path in enumerate(self.apk_files):
                if self.stop_installation:
                    self.log_signal.emit("Installation stopped by user")
                    break

                self.log_signal.emit(f"[{i+1}/{total}] Installing {apk_path}")

                try:
                    result = subprocess.run(
                        ['adb', 'install', '-r', apk_path],
                        capture_output=True,
                        text=True,
                        timeout=360          # 6 min max
                    )
                    if result.returncode == 0:
                        success += 1
                        status = "success"
                        details = "Installed"
                        msg = f"SUCCESS: {apk_path}"
                        self.log_signal.emit(msg)
                        log_f.write(msg + "\n")
                    else:
                        failed += 1
                        status = "failed"
                        details = result.stderr.strip()
                        msg = f"ERROR: {apk_path}\n{details}"
                        self.log_signal.emit(msg)
                        log_f.write(msg + "\n")
                except subprocess.TimeoutExpired:
                    failed += 1
                    status = "timeout"
                    details = "Timed out (6 min.)"
                    msg = f"TIMEOUT: {apk_path}"
                    self.log_signal.emit(msg)
                    log_f.write(msg + "\n")
                except Exception as e:
                    failed += 1
                    status = "exception"
                    details = str(e)
                    msg = f"EXCEPTION: {apk_path} – {details}"
                    self.log_signal.emit(msg)
                    log_f.write(msg + "\n")

                entries.append({
                    "package": os.path.basename(apk_path),
                    "status":  status,
                    "details": details
                })

                self.progress_signal.emit(i + 1)

            log_f.write("=" * 50 + "\n")
            log_f.write(f"Success: {success}\n")
            log_f.write(f"Failed: {failed}\n")
            log_f.write(f"Total processed: {success + failed}\n")

        # save JSON/HTML report
        report = {
            "type":      "mass_install",
            "timestamp": datetime.now().isoformat(),
            "total":     total,
            "success":   success,
            "failed":    failed,
            "entries":   entries
        }
        self.save_report(report, "mass_install_report")

        self.log_signal.emit(f"Installation completed! Success: {success}, Errors: {failed}")

        if failed == 0:
            QMessageBox.information(self, "Done", "All APK files installed successfully!")
        else:
            QMessageBox.warning(
                self, "Done",
                f"Installation completed with errors.\nSuccess: {success}\nErrors: {failed}"
            )

    # ------------------------------------------------------------------
    #   Files tab (push / pull)
    # ------------------------------------------------------------------
    def create_file_operations_tab(self):
        file_tab = QWidget()
        layout = QVBoxLayout(file_tab)

        # Push
        push_group = QGroupBox("Push files to device")
        push_layout = QVBoxLayout(push_group)

        self.push_local  = QLineEdit()
        self.push_remote = QLineEdit("/sdcard/")

        browse_push_btn = QPushButton("Browse file")
        browse_push_btn.clicked.connect(self.select_push_file)

        push_btn = QPushButton("Push")
        push_btn.clicked.connect(self.push_file)

        push_layout.addWidget(QLabel("Local file:"))
        push_layout.addWidget(self.push_local)
        push_layout.addWidget(browse_push_btn)
        push_layout.addWidget(QLabel("Remote path:"))
        push_layout.addWidget(self.push_remote)
        push_layout.addWidget(push_btn)

        # Pull
        pull_group = QGroupBox("Pull files from device")
        pull_layout = QVBoxLayout(pull_group)

        self.pull_remote = QLineEdit("/sdcard/")
        self.pull_local  = QLineEdit("./")

        browse_pull_btn = QPushButton("Browse folder")
        browse_pull_btn.clicked.connect(self.select_pull_folder)

        pull_btn = QPushButton("Pull")
        pull_btn.clicked.connect(self.pull_file)

        pull_layout.addWidget(QLabel("Remote file:"))
        pull_layout.addWidget(self.pull_remote)
        pull_layout.addWidget(QLabel("Local folder:"))
        pull_layout.addWidget(self.pull_local)
        pull_layout.addWidget(browse_pull_btn)
        pull_layout.addWidget(pull_btn)

        layout.addWidget(push_group)
        layout.addWidget(pull_group)
        self.tabs.addTab(file_tab, "Files")

    def select_push_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file to push", "")
        if path:
            self.push_local.setText(path)

    def select_pull_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder to save")
        if folder:
            self.pull_local.setText(folder)

    def push_file(self):
        local = self.push_local.text()
        remote = self.push_remote.text()
        if not local or not remote:
            QMessageBox.warning(self, "Error", "Fill in both fields")
            return
        if not os.path.exists(local):
            QMessageBox.warning(self, "Error", "Local file not found")
            return
        self.run_adb_command(f"push {local} {remote}")

    def pull_file(self):
        remote = self.pull_remote.text()
        local = self.pull_local.text()
        if not remote or not local:
            QMessageBox.warning(self, "Error", "Fill in both fields")
            return
        self.run_adb_command(f"pull {remote} {local}")

    # ------------------------------------------------------------------
    #   Commands tab (system)
    # ------------------------------------------------------------------
    def create_command_tab(self):
        cmd_tab = QWidget()
        layout = QVBoxLayout(cmd_tab)

        sys_group = QGroupBox("System commands")
        sys_layout = QGridLayout(sys_group)

        sys_commands = [
            ("Get properties",                "shell getprop"),
            ("Battery info",                "shell dumpsys battery"),
            ("CPU info",                     "shell cat /proc/cpuinfo"),
            ("Memory info",                  "shell cat /proc/meminfo"),
            ("Network connections",          "shell netstat"),
            ("Current activity",             "shell dumpsys activity activities | grep mResumedActivity"),
            ("Running processes",            "shell ps"),
            ("Wi‑Fi info",                   "shell dumpsys wifi"),
            ("Display info",                  "shell dumpsys display"),
            ("Free memory",                  "shell df -h")
        ]

        for i, (txt, cmd) in enumerate(sys_commands):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            sys_layout.addWidget(btn, i // 2, i % 2)

        layout.addWidget(sys_group)
        self.tabs.addTab(cmd_tab, "Commands")

    # ------------------------------------------------------------------
    #   Logcat tab
    # ------------------------------------------------------------------
    def create_logcat_tab(self):
        logcat_tab = QWidget()
        layout = QVBoxLayout(logcat_tab)

        log_group = QGroupBox("Logcat")
        log_layout = QVBoxLayout(log_group)

        log_btns = [
            ("Start logcat",                     "logcat"),
            ("Clear logs",                       "logcat -c"),
            ("Save log to file",                 "logcat -d -f /sdcard/logcat.txt"),
            ("Only errors",                     "logcat *:E"),
            ("Full system dump",                 "bugreport")
        ]

        for txt, cmd in log_btns:
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            log_layout.addWidget(btn)

        layout.addWidget(log_group)
        self.tabs.addTab(logcat_tab, "Logs")

    # ------------------------------------------------------------------
    #   Reboot tab
    # ------------------------------------------------------------------
    def create_reboot_tab(self):
        reboot_tab = QWidget()
        layout = QVBoxLayout(reboot_tab)

        reboot_group = QGroupBox("Reboot modes")
        reboot_layout = QGridLayout(reboot_group)

        reboot_buttons = [
            ("🔄 Normal reboot",                         "reboot"),
            ("🛠 Reboot to Recovery",                     "reboot recovery"),
            ("⚡ Fastboot / Bootloader",                  "reboot bootloader"),
            ("🛡 Safe mode",                             "shell am broadcast -a android.intent.action.REBOOT --ez android.intent.extra.IS_SAFE_MODE true"),
            ("📡 EDL mode (Qualcomm)",                   "reboot edl"),
            ("⏻ Power off device",                      "shell reboot -p")
        ]

        for i, (txt, cmd) in enumerate(reboot_buttons):
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            reboot_layout.addWidget(btn, i // 2, i % 2)

        layout.addWidget(reboot_group)
        self.tabs.addTab(reboot_tab, "Reboot")

    # ------------------------------------------------------------------
    #   Application testing tab
    # ------------------------------------------------------------------
    def create_app_tester_tab(self):
        tester_tab = QWidget()
        layout = QVBoxLayout(tester_tab)

        # Control
        ctrl_group = QGroupBox("Testing Management")
        ctrl_layout = QVBoxLayout(ctrl_group)

        # delay
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay between tests (seconds):"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(5, 60)
        self.delay_spinbox.setValue(10)
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()

        # buttons
        btn_layout = QHBoxLayout()
        self.get_packages_btn = QPushButton("Get apps")
        self.get_packages_btn.clicked.connect(self.get_user_packages)

        self.start_test_btn = QPushButton("Start testing")
        self.start_test_btn.clicked.connect(self.start_app_testing)
        self.start_test_btn.setEnabled(False)

        self.stop_test_btn = QPushButton("Stop testing")
        self.stop_test_btn.clicked.connect(self.stop_app_testing)
        self.stop_test_btn.setEnabled(False)

        btn_layout.addWidget(self.get_packages_btn)
        btn_layout.addWidget(self.start_test_btn)
        btn_layout.addWidget(self.stop_test_btn)

        ctrl_layout.addLayout(delay_layout)
        ctrl_layout.addLayout(btn_layout)

        # progress bar
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        ctrl_layout.addWidget(self.test_progress)

        # results table
        result_group = QGroupBox("Testing Results")
        result_layout = QVBoxLayout(result_group)

        self.app_tree = QTreeWidget()
        self.app_tree.setHeaderLabels(["Name", "Package", "Status"])
        self.app_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        result_layout.addWidget(self.app_tree)

        # actions on problematic apps
        action_layout = QHBoxLayout()
        self.delete_selected_btn = QPushButton("Delete selected")
        self.delete_selected_btn.clicked.connect(self.delete_selected_apps)
        self.delete_selected_btn.setEnabled(False)

        self.delete_all_btn = QPushButton("Delete all problematic")
        self.delete_all_btn.clicked.connect(self.delete_all_problematic_apps)
        self.delete_all_btn.setEnabled(False)

        action_layout.addWidget(self.delete_selected_btn)
        action_layout.addWidget(self.delete_all_btn)

        result_layout.addLayout(action_layout)

        # assemble tab
        layout.addWidget(ctrl_group)
        layout.addWidget(result_group)
        self.tabs.addTab(tester_tab, "App Testing")

    def get_user_packages(self):
        """Fetch list of user applications."""
        self.log_message("Fetching list of user applications...")
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
                self.log_message(f"Found {len(self.packages)} user applications")
                self.start_test_btn.setEnabled(True)

                self.app_tree.clear()
                for pkg in self.packages:
                    it = QTreeWidgetItem(self.app_tree)
                    it.setText(0, "—")
                    it.setText(1, pkg)
                    it.setText(2, "Waiting")
                    it.setForeground(2, QColor("gray"))
            else:
                self.log_message("No packages received")
        except subprocess.CalledProcessError as e:
            self.log_message(f"Error fetching packages: {e}")
            QMessageBox.critical(self, "Error", f"Failed to get application list:\n{e}")

    def start_app_testing(self):
        if not self.packages:
            QMessageBox.warning(self, "Attention", "Get the application list first")
            return

        self.testing = True
        self.crashed_apps = {}
        self.start_test_btn.setEnabled(False)
        self.stop_test_btn.setEnabled(True)
        self.test_progress.setVisible(True)
        self.test_progress.setMaximum(len(self.packages))
        self.test_progress.setValue(0)
        self.log_message("Starting application testing…")

        self.test_worker_thread = WorkerThread(self.test_applications_thread)
        self.test_worker_thread.finished_signal.connect(self.app_testing_finished)
        self.test_worker_thread.start()

    def stop_app_testing(self):
        self.testing = False
        self.log_message("Testing stopped by user")

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
                                                f"Errors: {result['error_count']}",
                                                "red")
                    self.crashed_apps[pkg] = result
                else:
                    self.update_app_test_status(i, "OK", "green")

                self.progress_signal.emit(i + 1)

                # delay before next test
                for sec in range(delay, 0, -1):
                    if not self.testing:
                        break
                    self.log_signal.emit(f"Waiting {sec}s before next test...")
                    time.sleep(1)

            if self.crashed_apps:
                self.log_signal.emit(f"Testing finished. Problematic apps: {len(self.crashed_apps)}")
            else:
                self.log_signal.emit("Testing finished. No problematic apps found")
        except Exception as e:
            self.log_signal.emit(f"Error in tester: {e}")

    def update_app_test_status(self, index: int, status: str, color_name: str):
        item = self.app_tree.topLevelItem(index)
        if item:
            item.setText(2, status)
            item.setForeground(2, QColor(color_name))

    def update_test_progress(self, value: int):
        self.test_progress.setValue(value)

    def test_application(self, package_name: str) -> dict:
        """Launch, collect logs and check for crashes."""
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
            self.log_signal.emit(f"Exception in test_application: {e}")
        return result

    def delete_selected_apps(self):
        selected = self.app_tree.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Attention", "No app selected for deletion")
            return
        reply = QMessageBox.question(
            self,
            "Confirmation",
            f"Delete the selected {len(selected)} app(s)?",
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

        QMessageBox.information(self, "Done",
                                f"Deleted {success} of {len(selected)} apps")

    def delete_all_problematic_apps(self):
        if not self.crashed_apps:
            QMessageBox.warning(self, "Attention", "No problematic apps")
            return
        reply = QMessageBox.question(
            self,
            "Confirmation",
            f"Delete all {len(self.crashed_apps)} problematic apps?",
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
        QMessageBox.information(self, "Done",
                                f"Deleted {success} problematic apps")
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
                self.log_message(f"Successfully removed: {package_name}")
                return True
            else:
                self.log_message(f"Failed to remove {package_name}: {result.stdout or result.stderr}")
                return False
        except subprocess.CalledProcessError as e:
            self.log_message(f"Error removing {package_name}: {e}")
            return False

    # ------------------------------------------------------------------
    #   Screen mirror tab (scrcpy)
    # ------------------------------------------------------------------
    def create_screen_mirror_tab(self):
        screen_tab = QWidget()
        layout = QVBoxLayout(screen_tab)

        screen_group = QGroupBox("Screen Management")
        screen_layout = QVBoxLayout(screen_group)

        self.start_stream_btn = QPushButton("Start screen cast (scrcpy)")
        self.start_stream_btn.clicked.connect(self.start_screen_stream)

        self.stop_stream_btn = QPushButton("Stop screen cast")
        self.stop_stream_btn.clicked.connect(self.stop_screen_stream)
        self.stop_stream_btn.setEnabled(False)

        self.screenshot_btn = QPushButton("Take screenshot")
        self.screenshot_btn.clicked.connect(self.take_screenshot)

        screen_layout.addWidget(self.start_stream_btn)
        screen_layout.addWidget(self.stop_stream_btn)
        screen_layout.addWidget(self.screenshot_btn)

        layout.addWidget(screen_group)
        self.tabs.addTab(screen_tab, "Device Screen")

    def start_screen_stream(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Error", "No device found!")
            return

        # check scrcpy
        try:
            subprocess.run(["scrcpy", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            QMessageBox.critical(self, "Error", "scrcpy not found in PATH")
            return

        self.log_message("Starting scrcpy...")
        self.start_stream_btn.setEnabled(False)
        self.stop_stream_btn.setEnabled(True)

        self.scrcpy_process = subprocess.Popen(
            ["scrcpy", "--max-fps", "60", "--window-title", "xHelper – Android Screen"]
        )

    def stop_screen_stream(self):
        if hasattr(self, "scrcpy_process"):
            self.scrcpy_process.terminate()
            self.scrcpy_process = None
            self.log_message("Screen cast stopped")
        self.start_stream_btn.setEnabled(True)
        self.stop_stream_btn.setEnabled(False)

    def take_screenshot(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Error", "No device found!")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png",
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
            self.log_message(f"Screenshot saved: {file_path}")
            QMessageBox.information(self, "Success", f"Screenshot saved:\n{file_path}")
        except subprocess.CalledProcessError as e:
            self.log_message(f"Screenshot error: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save screenshot:\n{e}")

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
    #   Monitoring tab (CPU, memory, battery, network)
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
        self.monitor_timer.start(5000)   # every 5 sec.

        self.tabs.addTab(monitor_tab, "Monitoring")

    def update_monitor(self):
        """Refresh monitoring data."""
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

        # CPU – placeholder
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

        # Network (IP‑address of wlan0)
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
    #   Wi‑Fi ADB (tcpip)
    # ------------------------------------------------------------------
    def create_wifi_tab(self):
        wifi_tab = QWidget()
        layout = QVBoxLayout(wifi_tab)

        enable_btn = QPushButton("Enable ADB over Wi‑Fi (tcpip 5555)")
        enable_btn.clicked.connect(self.enable_wifi_adb)

        self.wifi_ip_input = QLineEdit()
        self.wifi_ip_input.setPlaceholderText("Device IP address (e.g., 192.168.1.42)")

        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.connect_wifi_adb)

        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.clicked.connect(self.disconnect_wifi_adb)

        layout.addWidget(enable_btn)
        layout.addWidget(QLabel("IP address:"))
        layout.addWidget(self.wifi_ip_input)
        layout.addWidget(connect_btn)
        layout.addWidget(disconnect_btn)

        self.tabs.addTab(wifi_tab, "Wi‑Fi ADB")

    def enable_wifi_adb(self):
        self.run_adb_command("tcpip 5555", device_specific=True)

    def connect_wifi_adb(self):
        ip = self.wifi_ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "Error", "Enter an IP address")
            return
        self.run_adb_command(f"connect {ip}:5555", device_specific=False)

    def disconnect_wifi_adb(self):
        self.run_adb_command("disconnect", device_specific=False)

    # ------------------------------------------------------------------
    #   Backup / Restore
    # ------------------------------------------------------------------
    def create_backup_tab(self):
        backup_tab = QWidget()
        layout = QVBoxLayout(backup_tab)

        backup_btn = QPushButton("Create backup (full)")
        backup_btn.clicked.connect(self.create_backup)

        restore_btn = QPushButton("Restore backup")
        restore_btn.clicked.connect(self.restore_backup)

        layout.addWidget(backup_btn)
        layout.addWidget(restore_btn)

        self.tabs.addTab(backup_tab, "Backup / Restore")

    def create_backup(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save backup", "backup.ab", "AB Files (*.ab)"
        )
        if not file_path:
            return
        self.run_adb_command(f"backup -apk -shared -all -f {file_path}", device_specific=False)

    def restore_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select backup", "", "AB Files (*.ab)"
        )
        if not file_path:
            return
        self.run_adb_command(f"restore {file_path}", device_specific=False)

    # ------------------------------------------------------------------
    #   Screen recording (screenrecord)
    # ------------------------------------------------------------------
    def create_screen_record_tab(self):
        record_tab = QWidget()
        layout = QVBoxLayout(record_tab)

        self.start_record_btn = QPushButton("Start recording")
        self.start_record_btn.clicked.connect(self.start_screen_record)

        self.stop_record_btn = QPushButton("Stop recording")
        self.stop_record_btn.clicked.connect(self.stop_screen_record)
        self.stop_record_btn.setEnabled(False)

        self.save_record_btn = QPushButton("Save recording")
        self.save_record_btn.clicked.connect(self.save_screen_record)
        self.save_record_btn.setEnabled(False)

        layout.addWidget(self.start_record_btn)
        layout.addWidget(self.stop_record_btn)
        layout.addWidget(self.save_record_btn)

        self.tabs.addTab(record_tab, "Screen Recording")

    def start_screen_record(self):
        if not self.check_device_connected():
            QMessageBox.critical(self, "Error", "No device found!")
            return
        self.log_message("Starting screenrecord on device...")
        self.screenrecord_process = subprocess.Popen(
            ["adb", "shell", "screenrecord", "/sdcard/xHelper_record.mp4"]
        )
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)

    def stop_screen_record(self):
        if hasattr(self, "screenrecord_process"):
            self.screenrecord_process.terminate()
            self.screenrecord_process.wait()
            self.log_message("Recording stopped")
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self.save_record_btn.setEnabled(True)

    def save_screen_record(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save recording",
            f"record_{datetime.now():%Y%m%d_%H%M%S}.mp4",
            "MP4 Files (*.mp4)"
        )
        if not save_path:
            return
        self.log_message(f"Copying recording to {save_path} …")
        self.run_adb_command(f"pull /sdcard/xHelper_record.mp4 {save_path}", device_specific=False)
        self.run_adb_command("shell rm /sdcard/xHelper_record.mp4", device_specific=False)
        QMessageBox.information(self, "Done", f"Recording saved:\n{save_path}")
        self.save_record_btn.setEnabled(False)

    # ------------------------------------------------------------------
    #   Script editor
    # ------------------------------------------------------------------
    def create_script_editor_tab(self):
        script_tab = QWidget()
        layout = QVBoxLayout(script_tab)

        self.script_edit = QPlainTextEdit()
        self.script_edit.setPlaceholderText(
            "# Write ADB commands, one per line.\n"
            "# Lines starting with # are ignored.\n"
        )
        run_btn = QPushButton("Run script")
        run_btn.clicked.connect(self.run_script)

        layout.addWidget(self.script_edit)
        layout.addWidget(run_btn)

        self.tabs.addTab(script_tab, "Script editor")

    def run_script(self):
        script = self.script_edit.toPlainText()
        lines = [ln.strip() for ln in script.splitlines()
                 if ln.strip() and not ln.strip().startswith('#')]
        if not lines:
            QMessageBox.information(self, "Info", "Script is empty")
            return

        def exec_lines():
            for cmd in lines:
                self.log_message(f"Executing: {cmd}")
                self.run_adb_command(cmd, device_specific=True)
                time.sleep(0.2)

        self.script_thread = WorkerThread(exec_lines)
        self.script_thread.log_signal.connect(self.log_message)
        self.script_thread.start()

    # ------------------------------------------------------------------
    #   Fastboot
    # ------------------------------------------------------------------
    def create_fastboot_tab(self):
        fastboot_tab = QWidget()
        layout = QVBoxLayout(fastboot_tab)

        list_btn = QPushButton("List Fastboot devices")
        list_btn.clicked.connect(self.fastboot_devices)

        # Flash
        flash_layout = QHBoxLayout()
        self.flash_file_path = QLineEdit()
        browse_flash_btn = QPushButton("File")
        browse_flash_btn.clicked.connect(self.select_flash_file)
        flash_btn = QPushButton("Flash")
        flash_btn.clicked.connect(self.flash_fastboot)

        flash_layout.addWidget(self.flash_file_path)
        flash_layout.addWidget(browse_flash_btn)
        flash_layout.addWidget(flash_btn)

        # Erase
        erase_layout = QHBoxLayout()
        self.erase_partition_input = QLineEdit()
        self.erase_partition_input.setPlaceholderText("Partition name (e.g., system)")
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
            self.log_message("Fastboot devices:")
            self.log_message(result.stdout.strip() or "None found")
        except FileNotFoundError:
            self.log_message("fastboot not found in PATH")
        except Exception as e:
            self.log_message(f"Fastboot devices error: {e}")

    def select_flash_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file to flash", "", "All Files (*)")
        if path:
            self.flash_file_path.setText(path)

    def flash_fastboot(self):
        path = self.flash_file_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Error", "Specify a file to flash")
            return
        # Assume flashing to system partition; user can modify command
        self.run_fastboot_command(f"flash system {path}")

    def erase_fastboot_partition(self):
        part = self.erase_partition_input.text().strip()
        if not part:
            QMessageBox.warning(self, "Error", "Specify a partition name")
            return
        self.run_fastboot_command(f"erase {part}")

    def fastboot_unlock(self):
        self.run_fastboot_command("oem unlock")

    def run_fastboot_command(self, command: str):
        """Run a fastboot command and log its output."""
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
            self.log_message("Fastboot command timed out")
        except FileNotFoundError:
            self.log_message("fastboot not found in PATH")
        except Exception as e:
            self.log_message(f"Fastboot error: {e}")

    # ------------------------------------------------------------------
    #   Universal report generation (JSON + HTML)
    # ------------------------------------------------------------------
    def save_report(self, data: dict, base_name: str):
        """Save a report in JSON and HTML files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = f"{base_name}_{timestamp}.json"
        html_path = f"{base_name}_{timestamp}.html"

        # JSON
        try:
            with open(json_path, "w", encoding="utf-8") as jf:
                json.dump(data, jf, ensure_ascii=False, indent=4)
            self.log_message(f"JSON report saved: {json_path}")
        except Exception as e:
            self.log_message(f"Failed to save JSON report: {e}")

        # HTML (simple table)
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
<tr><th>Package</th><th>Status</th><th>Details</th></tr>
{rows}
</table>
</body>
</html>"""
            with open(html_path, "w", encoding="utf-8") as hf:
                hf.write(html)
            self.log_message(f"HTML report saved: {html_path}")
        except Exception as e:
            self.log_message(f"Failed to save HTML report: {e}")

    def generate_test_report(self):
        """Create a report of app testing results."""
        total = len(self.packages)
        failed = len(self.crashed_apps)
        success = total - failed

        entries = []
        for pkg in self.packages:
            if pkg in self.crashed_apps:
                entry = {
                    "package": pkg,
                    "status":  "crashed",
                    "details": f"Errors: {self.crashed_apps[pkg]['error_count']}"
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
        QMessageBox.information(self, "Report", "App testing report saved in the current folder.")

    # ------------------------------------------------------------------
    #   Entry point
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
