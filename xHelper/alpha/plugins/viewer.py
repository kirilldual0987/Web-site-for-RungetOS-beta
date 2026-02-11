# plugins/folder_viewer.py
# -*- coding: utf-8 -*-
"""
Простой просмотр папок на подключённом Android-устройстве.
Показывает список файлов и папок с возможностью навигации.
"""

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QLineEdit,
    QToolBar, QStyle, QApplication, QSplitter, QFrame
)


# ----------------------------------------------------------------------
#   Вспомогательные функции для работы с ADB
# ----------------------------------------------------------------------
def _run_adb(main_window, cmd, timeout=5):
    """Выполняет ADB-команду и возвращает stdout."""
    adb = main_window.settings.get("adb_path", "adb") if hasattr(main_window, "settings") else "adb"
    try:
        result = subprocess.run(
            [adb] + cmd.split(),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


# ----------------------------------------------------------------------
#   Основная функция регистрации плагина
# ----------------------------------------------------------------------
def register(main_window):
    # Создаём вкладку
    tab = QWidget()
    tab.setObjectName("FolderViewerTab")
    main_layout = QVBoxLayout(tab)
    main_layout.setContentsMargins(4, 4, 4, 4)

    # ---------------------- Панель навигации ----------------------
    nav_bar = QHBoxLayout()
    
    # Кнопка "Назад"
    btn_back = QPushButton("←")
    btn_back.setToolTip("Назад")
    btn_back.setFixedSize(30, 30)
    btn_back.setEnabled(False)
    
    # Кнопка "Вверх"
    btn_up = QPushButton("↑")
    btn_up.setToolTip("В родительскую папку")
    btn_up.setFixedSize(30, 30)
    
    # Поле текущего пути
    lbl_path = QLabel("Путь:")
    edit_path = QLineEdit("/sdcard")
    edit_path.setReadOnly(True)
    
    # Кнопка обновления
    btn_refresh = QPushButton("⟳")
    btn_refresh.setToolTip("Обновить")
    btn_refresh.setFixedSize(30, 30)
    
    nav_bar.addWidget(btn_back)
    nav_bar.addWidget(btn_up)
    nav_bar.addWidget(lbl_path)
    nav_bar.addWidget(edit_path, 1)
    nav_bar.addWidget(btn_refresh)
    
    main_layout.addLayout(nav_bar)

    # ---------------------- Разделитель для списка файлов ----------------------
    splitter = QSplitter(Qt.Orientation.Vertical)
    main_layout.addWidget(splitter, 1)

    # Верхняя панель: список файлов и папок
    list_files = QListWidget()
    list_files.setAlternatingRowColors(True)
    list_files.setStyleSheet("""
        QListWidget::item { 
            padding: 8px; 
            border-bottom: 1px solid #eee;
        }
        QListWidget::item:hover { 
            background-color: #f0f0f0;
        }
        QListWidget::item:selected { 
            background-color: #0078d7; 
            color: white;
        }
    """)
    
    # Нижняя панель: информация о выбранном файле
    info_panel = QFrame()
    info_panel.setFrameShape(QFrame.Shape.StyledPanel)
    info_layout = QVBoxLayout(info_panel)
    info_layout.setContentsMargins(10, 10, 10, 10)
    
    lbl_info_title = QLabel("Информация о файле")
    lbl_info_title.setStyleSheet("font-weight: bold; font-size: 12pt; margin-bottom: 10px;")
    
    lbl_name = QLabel("Имя: -")
    lbl_size = QLabel("Размер: -")
    lbl_type = QLabel("Тип: -")
    lbl_date = QLabel("Дата: -")
    
    for widget in [lbl_name, lbl_size, lbl_type, lbl_date]:
        widget.setStyleSheet("margin: 2px;")
    
    info_layout.addWidget(lbl_info_title)
    info_layout.addWidget(lbl_name)
    info_layout.addWidget(lbl_size)
    info_layout.addWidget(lbl_type)
    info_layout.addWidget(lbl_date)
    info_layout.addStretch()
    
    splitter.addWidget(list_files)
    splitter.addWidget(info_panel)
    splitter.setSizes([400, 150])

    # ---------------------- Статус-бар ----------------------
    status_bar = QLabel()
    status_bar.setText("Готово.")
    status_bar.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
    main_layout.addWidget(status_bar)

    # ---------------------- Внутренние переменные ----------------------
    current_path = "/sdcard"
    path_history = []

    # ---------------------- Функции-обработчики ----------------------
    def get_file_info(path):
        """Получает информацию о файле через ADB."""
        if not path:
            return {}
        
        # Получаем детальную информацию через ls -la
        cmd = f'shell ls -la "{path}"'
        out = _run_adb(main_window, cmd)
        
        info = {
            'name': os.path.basename(path),
            'path': path,
            'size': '?',
            'type': 'Файл',
            'date': '?',
            'permissions': '?'
        }
        
        if out:
            lines = out.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('total'):
                    parts = line.split()
                    if len(parts) >= 9 and parts[-1] == os.path.basename(path):
                        # Определяем тип
                        if parts[0].startswith('d'):
                            info['type'] = 'Папка'
                        elif parts[0].startswith('l'):
                            info['type'] = 'Ссылка'
                        
                        info['permissions'] = parts[0]
                        info['size'] = parts[4] + " байт"
                        
                        # Собираем дату (части 5, 6, 7)
                        if len(parts) >= 8:
                            info['date'] = ' '.join(parts[5:8])
                        break
        
        return info

    def update_file_list():
        """Обновляет список файлов и папок в текущей директории."""
        nonlocal current_path
        
        list_files.clear()
        status_bar.setText(f"Загрузка {current_path}...")
        QApplication.processEvents()  # Обновляем UI
        
        # Команда для получения списка файлов
        cmd = f'shell ls -p "{current_path}"'
        out = _run_adb(main_window, cmd)
        
        if not out:
            status_bar.setText(f"Не удалось загрузить {current_path}")
            main_window.log_message(f"[FolderViewer] Ошибка загрузки {current_path}")
            return
        
        # Разделяем вывод на строки и сортируем: сначала папки, потом файлы
        items = []
        for line in out.split('\n'):
            if not line.strip():
                continue
            
            item_name = line.strip()
            is_dir = item_name.endswith('/')
            
            if is_dir:
                item_name = item_name[:-1]  # Убираем слеш в конце
                # Пропускаем специальные папки
                if item_name in ['.', '..']:
                    continue
            
            items.append((item_name, is_dir))
        
        # Сортируем: папки сначала, затем файлы
        items.sort(key=lambda x: (not x[1], x[0].lower()))
        
        # Добавляем в список
        for item_name, is_dir in items:
            item = QListWidgetItem(item_name)
            
            if is_dir:
                item.setIcon(QApplication.style().standardIcon(
                    QStyle.StandardPixmap.SP_DirIcon
                ))
                item.setForeground(Qt.GlobalColor.darkBlue)
                item.setData(Qt.ItemDataRole.UserRole, 'dir')
            else:
                # Определяем иконку по расширению
                ext = os.path.splitext(item_name)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                    icon = QApplication.style().standardIcon(
                        QStyle.StandardPixmap.SP_FileIcon
                    )
                    item.setForeground(Qt.GlobalColor.darkGreen)
                elif ext in ['.mp4', '.avi', '.mkv', '.mov']:
                    icon = QApplication.style().standardIcon(
                        QStyle.StandardPixmap.SP_MediaPlay
                    )
                    item.setForeground(Qt.GlobalColor.darkMagenta)
                elif ext in ['.mp3', '.wav', '.flac']:
                    icon = QApplication.style().standardIcon(
                        QStyle.StandardPixmap.SP_MediaVolume
                    )
                    item.setForeground(Qt.GlobalColor.darkCyan)
                else:
                    icon = QApplication.style().standardIcon(
                        QStyle.StandardPixmap.SP_FileIcon
                    )
                    item.setForeground(Qt.GlobalColor.darkGray)
                
                item.setIcon(icon)
                item.setData(Qt.ItemDataRole.UserRole, 'file')
            
            list_files.addItem(item)
        
        # Обновляем путь в поле
        edit_path.setText(current_path)
        
        # Обновляем кнопку "Назад"
        btn_back.setEnabled(len(path_history) > 0)
        
        # Обновляем статус
        status_bar.setText(f"Загружено {len(items)} элементов")
        main_window.log_message(f"[FolderViewer] Загружена папка: {current_path}")

    def on_item_double_clicked(item):
        """Обработчик двойного клика по элементу."""
        nonlocal current_path, path_history
        
        item_name = item.text()
        is_dir = item.data(Qt.ItemDataRole.UserRole) == 'dir'
        
        if is_dir:
            # Сохраняем текущий путь в историю
            path_history.append(current_path)
            
            # Переходим в папку
            if current_path == "/":
                current_path = f"/{item_name}"
            else:
                current_path = f"{current_path}/{item_name}"
            
            update_file_list()
            
            # Сбрасываем информацию о файле
            lbl_name.setText("Имя: -")
            lbl_size.setText("Размер: -")
            lbl_type.setText("Тип: -")
            lbl_date.setText("Дата: -")

    def on_item_selected():
        """Обработчик выбора элемента в списке."""
        current_item = list_files.currentItem()
        if not current_item:
            return
        
        item_name = current_item.text()
        is_dir = current_item.data(Qt.ItemDataRole.UserRole) == 'dir'
        
        # Формируем полный путь
        if current_path == "/":
            full_path = f"/{item_name}"
        else:
            full_path = f"{current_path}/{item_name}"
        
        # Получаем информацию о файле
        info = get_file_info(full_path)
        
        # Обновляем панель информации
        lbl_name.setText(f"Имя: {info['name']}")
        lbl_size.setText(f"Размер: {info['size']}")
        lbl_type.setText(f"Тип: {info['type']}")
        lbl_date.setText(f"Дата: {info['date']}")

    def go_up():
        """Переход в родительскую папку."""
        nonlocal current_path, path_history
        
        if current_path == "/":
            return
        
        # Сохраняем текущий путь в историю
        path_history.append(current_path)
        
        # Переходим на уровень выше
        if current_path.count('/') == 1:  # Корневая папка типа /sdcard
            current_path = "/"
        else:
            current_path = os.path.dirname(current_path)
        
        update_file_list()

    def go_back():
        """Возврат к предыдущей папке."""
        nonlocal current_path, path_history
        
        if not path_history:
            return
        
        # Восстанавливаем предыдущий путь
        current_path = path_history.pop()
        update_file_list()

    # ---------------------- Связывание сигналов ----------------------
    list_files.itemDoubleClicked.connect(on_item_double_clicked)
    list_files.currentItemChanged.connect(on_item_selected)
    btn_up.clicked.connect(go_up)
    btn_back.clicked.connect(go_back)
    btn_refresh.clicked.connect(update_file_list)
    
    # Обработчик изменения пути через Enter
    def on_path_edited():
        nonlocal current_path
        new_path = edit_path.text().strip()
        if new_path and new_path != current_path:
            # Проверяем существование пути
            cmd = f'shell ls -d "{new_path}"'
            out = _run_adb(main_window, cmd)
            if out:
                current_path = new_path
                update_file_list()
            else:
                QMessageBox.warning(tab, "Ошибка", f"Путь {new_path} не найден на устройстве.")
                edit_path.setText(current_path)
    
    edit_path.returnPressed.connect(on_path_edited)

    # ---------------------- Контекстное меню ----------------------
    def show_context_menu(pos):
        """Показывает контекстное меню для элемента списка."""
        item = list_files.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        
        # Создаем действия меню
        act_open = menu.addAction("Открыть")
        act_copy_path = menu.addAction("Копировать путь")
        menu.addSeparator()
        act_refresh = menu.addAction("Обновить список")
        
        # Показываем меню
        action = menu.exec(list_files.mapToGlobal(pos))
        
        if action == act_open:
            on_item_double_clicked(item)
        elif action == act_copy_path:
            item_name = item.text()
            if current_path == "/":
                full_path = f"/{item_name}"
            else:
                full_path = f"{current_path}/{item_name}"
            
            clipboard = QApplication.clipboard()
            clipboard.setText(full_path)
            status_bar.setText(f"Путь скопирован: {full_path}")
        elif action == act_refresh:
            update_file_list()

    list_files.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    list_files.customContextMenuRequested.connect(show_context_menu)

    # ---------------------- Инициализация ----------------------
    # Загружаем начальный список файлов
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(100, update_file_list)

    # ---------------------- Добавляем вкладку в главное окно ----------------------
    main_window.tabs.addTab(tab, "Просмотр папок")
    main_window.log_message("[FolderViewer] Плагин 'Просмотр папок' загружен.")