import sys
import os
import subprocess
import threading
import time
import queue
import json
import re
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QListWidget, QTextEdit, 
                             QLabel, QFileDialog, QMessageBox, QTabWidget,
                             QGroupBox, QLineEdit, QGridLayout, QProgressBar,
                             QTreeWidget, QTreeWidgetItem, QHeaderView, QSplitter,
                             QCheckBox, QSpinBox, QComboBox, QTableWidget, 
                             QTableWidgetItem, QInputDialog, QMenu, QSystemTrayIcon,
                             QStyle, QDialog, QDialogButtonBox, QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint
from PyQt6.QtGui import QIcon, QFont, QColor, QAction, QPixmap, QImage

class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    data_signal = pyqtSignal(object)
    
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        
    def run(self):
        try:
            self.function(*self.args, **self.kwargs)
        except Exception as e:
            self.log_signal.emit(f"Ошибка в потоке: {str(e)}")
        finally:
            self.finished_signal.emit()

class AppInfoDialog(QDialog):
    def __init__(self, app_info, parent=None):
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

class xHelperMainWindow(QMainWindow):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("xHelper pre-alpha 0.4.7 LTS/ATS")
        self.setGeometry(100, 100, 1400, 900)
        
        # Подключаем сигналы к слотам
        self.log_signal.connect(self.log_message)
        self.progress_signal.connect(self.update_test_progress)
        
        # Центральный виджет и основной макет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Создаем виджет с вкладками
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Создаем различные вкладки
        self.create_device_tab()
        self.create_apk_tab()
        self.create_mass_apk_tab()
        self.create_file_operations_tab()
        self.create_command_tab()
        self.create_logcat_tab()
        self.create_reboot_tab()
        self.create_app_tester_tab()
        self.create_screen_mirror_tab()
        
        # Консоль вывода
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        main_layout.addWidget(self.console)
        
        # Инициализация ADB
        self.check_adb()
        
        # Переменные для массовой установки APK
        self.apk_files = []
        self.install_in_progress = False
        self.stop_installation = False
        
        # Переменные для тестирования приложений
        self.packages = []
        self.crashed_apps = {}
        self.testing = False
        
    def check_adb(self):
        """Проверка доступности ADB"""
        try:
            result = subprocess.run(['adb', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.log_message("ADB доступен в системе")
                self.get_devices()
            else:
                self.log_message("ADB не найден. Убедитесь, что он установлен и добавлен в PATH")
        except FileNotFoundError:
            self.log_message("ADB не найден. Убедитесь, что он установлен и добавлен в PATH")
    
    def get_devices(self):
        """Получение списка подключенных устройств"""
        result = subprocess.run(['adb', 'devices'], 
                              capture_output=True, text=True)
        output = result.stdout.split('\n')[1:]
        devices = []
        for line in output:
            if line.strip() and '\tdevice' in line:
                devices.append(line.split('\t')[0])
        
        self.device_list.clear()
        if devices:
            for device in devices:
                self.device_list.addItem(device)
            self.log_message(f"Найдено устройств: {len(devices)}")
        else:
            self.log_message("Устройства не найдены")
    
    def run_adb_command(self, command, device_specific=True):
        """Выполнение ADB команды"""
        if device_specific and self.device_list.currentItem():
            device = self.device_list.currentItem().text()
            full_command = ['adb', '-s', device] + command.split()
        else:
            full_command = ['adb'] + command.split()
        
        try:
            self.log_message(f"Выполняем: {' '.join(full_command)}")
            result = subprocess.run(full_command, 
                                  capture_output=True, text=True, timeout=30)
            
            if result.stdout:
                self.log_message("Результат:")
                self.log_message(result.stdout)
            if result.stderr:
                self.log_message("Ошибки:")
                self.log_message(result.stderr)
            if result.returncode != 0:
                self.log_message(f"Команда завершилась с кодом: {result.returncode}")
                
        except subprocess.TimeoutExpired:
            self.log_message("Команда выполнена с таймаутом")
        except Exception as e:
            self.log_message(f"Ошибка при выполнении команды: {str(e)}")
    
    def log_message(self, message):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.console.append(formatted_message)
    
    def create_device_tab(self):
        """Вкладка управления устройствами"""
        device_tab = QWidget()
        layout = QVBoxLayout(device_tab)
        
        # Группа устройств
        device_group = QGroupBox("Подключенные устройства")
        device_layout = QVBoxLayout(device_group)
        
        self.device_list = QListWidget()
        refresh_btn = QPushButton("Обновить список устройств")
        refresh_btn.clicked.connect(self.get_devices)
        
        device_layout.addWidget(self.device_list)
        device_layout.addWidget(refresh_btn)
        
        # Группа reboot
        reboot_group = QGroupBox("Управление питанием")
        reboot_layout = QGridLayout(reboot_group)
        
        reboot_btns = [
            ("Перезагрузка", "reboot"),
            ("Recovery", "reboot recovery"),
            ("Bootloader", "reboot bootloader"),
            ("Fastboot", "reboot fastboot")
        ]
        
        for i, (text, cmd) in enumerate(reboot_btns):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            reboot_layout.addWidget(btn, i // 2, i % 2)
        
        layout.addWidget(device_group)
        layout.addWidget(reboot_group)
        self.tabs.addTab(device_tab, "Устройства")
    
    def create_apk_tab(self):
        """Вкладка управления APK"""
        apk_tab = QWidget()
        layout = QVBoxLayout(apk_tab)
        
        # Установка APK
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
        
        package_btns = [
            ("Список приложений", "shell pm list packages"),
            ("Список системных приложений", "shell pm list packages -s"),
            ("Список сторонних приложений", "shell pm list packages -3"),
            ("Очистить данные", "shell pm clear"),
            ("Удалить приложение", "uninstall"),
            ("Запуск приложения", "shell monkey -p")
        ]
        
        for i, (text, cmd) in enumerate(package_btns):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            package_layout.addWidget(btn, i // 3, i % 3)
        
        layout.addWidget(install_group)
        layout.addWidget(package_group)
        self.tabs.addTab(apk_tab, "APK")
    
    def create_mass_apk_tab(self):
        """Вкладка массовой установки APK"""
        mass_apk_tab = QWidget()
        layout = QVBoxLayout(mass_apk_tab)
        
        # Выбор папки
        folder_group = QGroupBox("Выбор папки с APK")
        folder_layout = QVBoxLayout(folder_group)
        
        self.folder_path = QLineEdit()
        browse_folder_btn = QPushButton("Выбрать папку с APK")
        browse_folder_btn.clicked.connect(self.select_apk_folder)
        
        folder_layout.addWidget(QLabel("Путь к папке с APK:"))
        folder_layout.addWidget(self.folder_path)
        folder_layout.addWidget(browse_folder_btn)
        
        # Управление установкой
        install_group = QGroupBox("Массовая установка")
        install_layout = QVBoxLayout(install_group)
        
        self.apk_count_label = QLabel("APK файлов не выбрано")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        start_btn = QPushButton("Начать установку")
        start_btn.clicked.connect(self.start_mass_installation)
        
        stop_btn = QPushButton("Остановить установку")
        stop_btn.clicked.connect(self.stop_mass_installation)
        
        install_layout.addWidget(self.apk_count_label)
        install_layout.addWidget(self.progress_bar)
        install_layout.addWidget(start_btn)
        install_layout.addWidget(stop_btn)
        
        layout.addWidget(folder_group)
        layout.addWidget(install_group)
        self.tabs.addTab(mass_apk_tab, "Массовая установка APK")
    
    def create_reboot_tab(self):
        """Вкладка перезагрузки устройства"""
        reboot_tab = QWidget()
        layout = QVBoxLayout(reboot_tab)
        
        reboot_group = QGroupBox("Режимы перезагрузки")
        reboot_layout = QGridLayout(reboot_group)
        
        reboot_buttons = [
            ("🔄 Обычная перезагрузка", "reboot"),
            ("🛠 Перезагрузка в Recovery", "reboot recovery"),
            ("⚡ Fastboot / Bootloader", "reboot bootloader"),
            ("🛡 Безопасный режим", "shell am broadcast -a android.intent.action.REBOOT --ez android.intent.extra.IS_SAFE_MODE true"),
            ("📡 Режим EDL (Qualcomm)", "reboot edl"),
            ("⏻ Выключить устройство", "shell reboot -p")
        ]
        
        for i, (text, cmd) in enumerate(reboot_buttons):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            reboot_layout.addWidget(btn, i // 2, i % 2)
        
        layout.addWidget(reboot_group)
        self.tabs.addTab(reboot_tab, "Перезагрузка")
    
    def create_app_tester_tab(self):
        """Вкладка тестирования приложений"""
        app_tester_tab = QWidget()
        layout = QVBoxLayout(app_tester_tab)
        
        # Управление
        control_group = QGroupBox("Управление тестированием")
        control_layout = QVBoxLayout(control_group)
        
        # Задержка между тестами
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Задержка между тестами (сек):"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(5, 60)
        self.delay_spinbox.setValue(10)
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()
        
        # Кнопки управления
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
        
        control_layout.addLayout(delay_layout)
        control_layout.addLayout(btn_layout)
        
        # Прогресс
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        control_layout.addWidget(self.test_progress)
        
        # Таблица результатов
        result_group = QGroupBox("Результаты тестирования")
        result_layout = QVBoxLayout(result_group)
        
        self.app_tree = QTreeWidget()
        self.app_tree.setHeaderLabels(["Имя приложения", "Пакет", "Статус"])
        self.app_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        result_layout.addWidget(self.app_tree)
        
        # Кнопки действий
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
        
        layout.addWidget(control_group)
        layout.addWidget(result_group)
        self.tabs.addTab(app_tester_tab, "Тестирование приложений")
    
    def create_screen_mirror_tab(self):
        """Вкладка управления экраном устройства"""
        screen_tab = QWidget()
        layout = QVBoxLayout(screen_tab)
        
        # Управление скринкастом
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
    
    def create_file_operations_tab(self):
        """Вкладка файловых операций"""
        file_tab = QWidget()
        layout = QVBoxLayout(file_tab)
        
        # Push файлов
        push_group = QGroupBox("Отправка файлов на устройство")
        push_layout = QVBoxLayout(push_group)
        
        self.push_local = QLineEdit()
        self.push_remote = QLineEdit("/sdcard/")
        
        browse_push_btn = QPushButton("Выбрать файл для отправки")
        browse_push_btn.clicked.connect(self.select_push_file)
        
        push_btn = QPushButton("Отправить файл")
        push_btn.clicked.connect(self.push_file)
        
        push_layout.addWidget(QLabel("Локальный файл:"))
        push_layout.addWidget(self.push_local)
        push_layout.addWidget(browse_push_btn)
        push_layout.addWidget(QLabel("Удаленный путь:"))
        push_layout.addWidget(self.push_remote)
        push_layout.addWidget(push_btn)
        
        # Pull файлов
        pull_group = QGroupBox("Получение файлов с устройства")
        pull_layout = QVBoxLayout(pull_group)
        
        self.pull_remote = QLineEdit("/sdcard/")
        self.pull_local = QLineEdit("./")
        
        browse_pull_btn = QPushButton("Выберите папку для сохранения")
        browse_pull_btn.clicked.connect(self.select_pull_folder)
        
        pull_btn = QPushButton("Получить файл")
        pull_btn.clicked.connect(self.pull_file)
        
        pull_layout.addWidget(QLabel("Удаленный файл:"))
        pull_layout.addWidget(self.pull_remote)
        pull_layout.addWidget(QLabel("Локальная папка:"))
        pull_layout.addWidget(self.pull_local)
        pull_layout.addWidget(browse_pull_btn)
        pull_layout.addWidget(pull_btn)
        
        layout.addWidget(push_group)
        layout.addWidget(pull_group)
        self.tabs.addTab(file_tab, "Файлы")
    
    def create_command_tab(self):
        """Вкладка с общими командами"""
        command_tab = QWidget()
        layout = QVBoxLayout(command_tab)
        
        # Системные команды
        system_group = QGroupBox("Системные команды")
        system_layout = QGridLayout(system_group)
        
        system_commands = [
            ("Получить свойства", "shell getprop"),
            ("Информация о батарее", "shell dumpsys battery"),
            ("Информация о процессоре", "shell cat /proc/cpuinfo"),
            ("Информация о памяти", "shell cat /proc/meminfo"),
            ("Сетевые соединения", "shell netstat"),
            ("Текущая активность", "shell dumpsys activity activities | grep mResumedActivity"),
            ("Запущенные процессы", "shell ps"),
            ("Информация о WiFi", "shell dumpsys wifi"),
            ("Информация о дисплее", "shell dumpsys display"),
            ("Свободная память", "shell df -h")
        ]
        
        for i, (text, cmd) in enumerate(system_commands):
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            system_layout.addWidget(btn, i // 2, i % 2)
        
        layout.addWidget(system_group)
        self.tabs.addTab(command_tab, "Команды")
    
    def create_logcat_tab(self):
        """Вкладка для работы с логами"""
        logcat_tab = QWidget()
        layout = QVBoxLayout(logcat_tab)
        
        log_group = QGroupBox("Логирование")
        log_layout = QVBoxLayout(log_group)
        
        log_btns = [
            ("Запуск logcat", "logcat"),
            ("Очистка логов", "logcat -c"),
            ("Дамп логов в файл", "logcat -d -f /sdcard/logcat.txt"),
            ("Логи только ошибки", "logcat *:E"),
            ("Полный дамп системы", "bugreport")
        ]
        
        for text, cmd in log_btns:
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, c=cmd: self.run_adb_command(c))
            log_layout.addWidget(btn)
        
        layout.addWidget(log_group)
        self.tabs.addTab(logcat_tab, "Логи")
    
    def select_apk(self):
        """Выбор APK файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите APK файл", "", "APK Files (*.apk)"
        )
        if file_path:
            self.apk_path.setText(file_path)
    
    def install_apk(self):
        """Установка APK"""
        apk_file = self.apk_path.text()
        if not apk_file:
            QMessageBox.warning(self, "Ошибка", "Выберите APK файл")
            return
        
        if not os.path.exists(apk_file):
            QMessageBox.warning(self, "Ошибка", "APK файл не существует")
            return
        
        self.run_adb_command(f"install -r {apk_file}")
    
    def select_apk_folder(self):
        """Выбор папки с APK файлами"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Выберите папку с APK файлами"
        )
        if folder_path:
            self.folder_path.setText(folder_path)
            self.apk_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                             if f.lower().endswith('.apk')]
            self.apk_count_label.setText(f"Найдено APK файлов: {len(self.apk_files)}")
    
    def start_mass_installation(self):
        """Запуск массовой установки APK"""
        if not self.apk_files:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите папку с APK файлами")
            return
        
        if self.install_in_progress:
            QMessageBox.information(self, "Информация", "Установка уже выполняется")
            return
        
        self.install_in_progress = True
        self.stop_installation = False
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.apk_files))
        self.progress_bar.setValue(0)
        
        # Запуск установки в отдельном потоке
        self.worker_thread = WorkerThread(self.install_apks_thread)
        self.worker_thread.log_signal.connect(self.log_message)
        self.worker_thread.progress_signal.connect(self.progress_bar.setValue)
        self.worker_thread.finished_signal.connect(self.mass_installation_finished)
        self.worker_thread.start()
    
    def stop_mass_installation(self):
        """Остановка массовой установки APK"""
        self.stop_installation = True
        self.log_message("Установка прервана пользователем")
    
    def mass_installation_finished(self):
        """Завершение массовой установки APK"""
        self.install_in_progress = False
        self.progress_bar.setVisible(False)
    
    def install_apks_thread(self):
        """Поток для массовой установки APK"""
        total_files = len(self.apk_files)
        success_count = 0
        fail_count = 0
        log_file = f"install_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        self.log_message(f"Начало установки {total_files} APK файлов")
        self.log_message(f"Лог будет сохранен в файл: {log_file}")
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"Лог установки APK - {datetime.now()}\n")
            f.write("="*50 + "\n")
            
            for i, apk_path in enumerate(self.apk_files):
                if self.stop_installation:
                    break
                    
                self.log_message(f"[{i+1}/{total_files}] Установка {apk_path}...")
                
                try:
                    # Выполняем команду adb install с увеличенным таймаутом (360 секунд)
                    result = subprocess.run(
                        ['adb', 'install', '-r', apk_path],
                        capture_output=True,
                        text=True,
                        timeout=360  # Увеличенный таймаут (6 минут)
                    )
                    
                    if result.returncode == 0:
                        success_count += 1
                        log_msg = f"УСПЕХ: {apk_path}"
                        self.log_message(log_msg)
                        f.write(log_msg + "\n")
                    else:
                        fail_count += 1
                        log_msg = f"ОШИБКА: {apk_path} - {result.stderr}"
                        self.log_message(log_msg)
                        f.write(log_msg + "\n")
                        
                except subprocess.TimeoutExpired:
                    fail_count += 1
                    log_msg = f"ТАЙМАУТ: {apk_path} - превышено время установки (6 минут)"
                    self.log_message(log_msg)
                    f.write(log_msg + "\n")
                except Exception as e:
                    fail_count += 1
                    log_msg = f"ИСКЛЮЧЕНИЕ: {apk_path} - {str(e)}"
                    self.log_message(log_msg)
                    f.write(log_msg + "\n")
                
                # Обновляем прогресс
                self.progress_signal.emit(i + 1)
            
            # Записываем итоги в лог файл
            f.write("="*50 + "\n")
            f.write(f"Установлено успешно: {success_count}\n")
            f.write(f"Не удалось установить: {fail_count}\n")
            f.write(f"Всего обработано: {success_count + fail_count}\n")
        
        # Выводим итоги
        self.log_message(f"Установка завершена! Успешно: {success_count}, Ошибки: {fail_count}")
        
        # Показываем уведомление
        if fail_count == 0:
            QMessageBox.information(self, "Завершено", "Все APK файлы установлены успешно!")
        else:
            QMessageBox.warning(self, "Завершено", 
                               f"Установка завершена с ошибками.\nУспешно: {success_count}\nОшибки: {fail_count}")
    
    def get_user_packages(self):
        """Получение списка пользовательских приложений"""
        self.log_message("Получение списка приложений...")
        
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
                self.packages = [line.replace("package:", "") for line in result.stdout.splitlines()]
                self.log_message(f"Найдено {len(self.packages)} пользовательских приложений")
                self.start_test_btn.setEnabled(True)
                
                # Очищаем таблицу
                self.app_tree.clear()
                
                # Заполняем таблицу
                for package in self.packages:
                    item = QTreeWidgetItem(self.app_tree)
                    item.setText(0, "Еще не тестировано")
                    item.setText(1, package)
                    item.setText(2, "Ожидание")
                    item.setForeground(2, QColor("gray"))
            else:
                self.log_message("Не найдено пользовательских приложений")
                
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка при получении списка приложений: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить список приложений: {e}")
    
    def start_app_testing(self):
        """Запуск тестирования приложений"""
        if not self.packages:
            QMessageBox.warning(self, "Предупреждение", "Сначала получите список приложений")
            return
            
        self.testing = True
        self.crashed_apps = {}
        self.start_test_btn.setEnabled(False)
        self.stop_test_btn.setEnabled(True)
        self.test_progress.setVisible(True)
        self.test_progress.setMaximum(len(self.packages))
        self.test_progress.setValue(0)
        self.log_message("Начало тестирования приложений...")
        
        # Запуск тестирования в отдельном потоке
        self.test_worker_thread = WorkerThread(self.test_applications_thread)
        self.test_worker_thread.finished_signal.connect(self.app_testing_finished)
        self.test_worker_thread.start()
    
    def stop_app_testing(self):
        """Остановка тестирования приложений"""
        self.testing = False
        self.log_message("Тестирование остановлено по запросу пользователя")
    
    def app_testing_finished(self):
        """Завершение тестирования приложений"""
        self.testing = False
        self.start_test_btn.setEnabled(True)
        self.stop_test_btn.setEnabled(False)
        self.test_progress.setVisible(False)
        
        if self.crashed_apps:
            self.delete_selected_btn.setEnabled(True)
            self.delete_all_btn.setEnabled(True)
    
    def test_applications_thread(self):
        """Поток для тестирования приложений"""
        try:
            # Получаем задержку из интерфейса
            delay = self.delay_spinbox.value()
            
            # Тестируем каждое приложение
            for i, package in enumerate(self.packages):
                if not self.testing:
                    break
                    
                # Тестируем приложение
                result = self.test_application(package)
                
                # Обновляем результат в GUI
                if result["crashed"]:
                    self.update_app_test_status(i, f"Ошибок: {result['error_count']}", "red")
                    self.crashed_apps[package] = result
                else:
                    self.update_app_test_status(i, "Успешно", "green")
                
                # Обновляем прогресс-бар
                self.progress_signal.emit(i + 1)
                
                # Задержка перед следующим приложением
                for sec in range(delay, 0, -1):
                    if not self.testing:
                        break
                    self.log_signal.emit(f"Ожидание перед следующему приложению: {sec} сек...")
                    time.sleep(1)
                
            # Завершаем тестирование
            if self.crashed_apps:
                self.log_signal.emit(f"Тестирование завершено. Найдено {len(self.crashed_apps)} проблемных приложений")
            else:
                self.log_signal.emit("Тестирование завершено. Проблемных приложений не найдено")
                
        except Exception as e:
            self.log_signal.emit(f"Ошибка при тестировании: {e}")
    
    def update_app_test_status(self, index, status, color_name):
        """Обновление статуса тестирования приложения"""
        item = self.app_tree.topLevelItem(index)
        if item:
            item.setText(2, status)
            item.setForeground(2, QColor(color_name))
    
    def update_test_progress(self, value):
        """Обновление прогресс-бара тестирования"""
        self.test_progress.setValue(value)
    
    def test_application(self, package_name):
        """Тестирование одного приложения"""
        result = {
            "crashed": False,
            "error_count": 0,
            "name": package_name
        }
        
        try:
            # Очищаем логи
            subprocess.run(["adb", "logcat", "-c"], capture_output=True)
            
            # Запускаем приложение
            subprocess.run(["adb", "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"], 
                          capture_output=True, timeout=5)
            
            # Ждем немного
            time.sleep(3)
            
            # Собираем логи
            log_process = subprocess.run(
                ["adb", "logcat", "-d", "-v", "brief", "*:E"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Анализируем логи на наличие ошибки
            if log_process.stdout:
                error_count = log_process.stdout.count("FATAL") + log_process.stdout.count("CRASH")
                if error_count > 0 and package_name in log_process.stdout:
                    result["crashed"] = True
                    result["error_count"] = error_count
            
            # Останавливаем приложение
            subprocess.run(["adb", "shell", "am", "force-stop", package_name])
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            result["crashed"] = True
            result["error_count"] = 1
            
        return result
    
    def delete_selected_apps(self):
        """Удаление выбранных приложений"""
        selected_items = self.app_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Не выбрано ни одного приложения для удаления")
            return
            
        # Подтверждение удаления
        confirm = QMessageBox.question(
            self,
            "Подтверждение", 
            f"Вы уверены, что хотите удалить {len(selected_items)} приложение(й)?"
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Удаляем приложения
        success_count = 0
        for item in selected_items:
            package = item.text(1)
            if self.uninstall_package(package):
                success_count += 1
                # Удаляем из таблицы
                self.app_tree.takeTopLevelItem(self.app_tree.indexOfTopLevelItem(item))
                
        QMessageBox.information(
            self,
            "Результат", 
            f"Успешно удалено {success_count} из {len(selected_items)} приложение(й)"
        )
        
    def delete_all_problematic_apps(self):
        """Удаление всех проблемных приложений"""
        if not self.crashed_apps:
            QMessageBox.warning(self, "Предупреждение", "Нет проблемных приложений для удаления")
            return
            
        # Подтверждение удаления
        confirm = QMessageBox.question(
            self,
            "Подтверждение", 
            f"Вы уверены, что хотите удалить все {len(self.crashed_apps)} проблемных приложений?"
        )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
            
        # Удаляем приложения
        success_count = 0
        packages_to_remove = list(self.crashed_apps.keys())
        
        for package in packages_to_remove:
            if self.uninstall_package(package):
                success_count += 1
                # Удаляем из таблицы
                for i in range(self.app_tree.topLevelItemCount()):
                    item = self.app_tree.topLevelItem(i)
                    if item.text(1) == package:
                        self.app_tree.takeTopLevelItem(i)
                        break
                
        # Очищаем список проблемных приложений
        self.crashed_apps.clear()
        
        QMessageBox.information(
            self,
            "Результат", 
            f"Успешно удалено {success_count} из {len(packages_to_remove)} приложение(й)"
        )
        
        # Отключаем кнопки удаления
        self.delete_selected_btn.setEnabled(False)
        self.delete_all_btn.setEnabled(False)

    def uninstall_package(self, package_name):
        """Удаление приложения"""
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
                self.log_message(f"Ошибка удаления {package_name}: {result.stdout}")
                return False
                
        except subprocess.CalledProcessError as e:
            self.log_message(f"Ошибка удаления {package_name}: {e}")
            return False
    
    def start_screen_stream(self):
        """Запуск скринкаста устройства"""
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return

        self.log_message("Запуск скринкаста через scrcpy...")
        self.start_stream_btn.setEnabled(False)
        self.stop_stream_btn.setEnabled(True)
        
        # Запускаем scrcpy в отдельном процессе
        self.scrcpy_process = subprocess.Popen(["scrcpy", "--max-fps", "60", "--window-title", "xHelper pre-alpha 0.4.7 LTS/ATS - Android Screen"])
    
    def stop_screen_stream(self):
        """Остановка скринкаста устройства"""
        if hasattr(self, 'scrcpy_process'):
            self.scrcpy_process.terminate()
            self.scrcpy_process = None
            self.log_message("Скринкаст остановлен")
        
        self.start_stream_btn.setEnabled(True)
        self.stop_stream_btn.setEnabled(False)
    
    def take_screenshot(self):
        """Создание скриншота"""
        if not self.check_device_connected():
            QMessageBox.critical(self, "Ошибка", "Устройство не найдено!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить скриншот", f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png", "PNG Files (*.png)"
        )
        
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f, check=True)
                self.log_message(f"Скриншот сохранен: {file_path}")
                QMessageBox.information(self, "Успех", f"Скриншот сохранен:\n{file_path}")
            except subprocess.CalledProcessError as e:
                self.log_message(f"Ошибка при создании скриншота: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать скриншот: {e}")
    
    def check_device_connected(self):
        """Проверка подключения устройства"""
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
    
    def select_push_file(self):
        """Выбор файла для отправки на устройство"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл для отправки", ""
        )
        if file_path:
            self.push_local.setText(file_path)
    
    def select_pull_folder(self):
        """Выбор папка для сохранения файлов"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Выберите папку для сохранения"
        )
        if folder_path:
            self.pull_local.setText(folder_path)
    
    def push_file(self):
        """Отправка файла на устройство"""
        local_file = self.push_local.text()
        remote_path = self.push_remote.text()
        
        if not local_file or not remote_path:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        
        if not os.path.exists(local_file):
            QMessageBox.warning(self, "Ошибка", "Локальный файл не существует")
            return
        
        self.run_adb_command(f"push {local_file} {remote_path}")
    
    def pull_file(self):
        """Получение файла с устройства"""
        remote_file = self.pull_remote.text()
        local_path = self.pull_local.text()
        
        if not remote_file or not local_path:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        
        self.run_adb_command(f"pull {remote_file} {local_path}")
    
    def update_logs(self):
        """Обновление логов (заглушка для совместимости)"""
        pass

def main():
    app = QApplication(sys.argv)
    window = xHelperMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()