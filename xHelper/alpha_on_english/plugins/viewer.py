# plugins/folder_viewer.py
# -*- coding: utf-8 -*-
"""
Simple folder viewer for a connected Android device.
Shows file and directory listings with navigation.
"""

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QLineEdit,
    QToolBar, QStyle, QApplication, QSplitter, QFrame, QMenu
)


def _run_adb(main_window, cmd, timeout=5):
    """Execute an ADB command and return its stdout."""
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


def register(main_window):
    tab = QWidget()
    tab.setObjectName("FolderViewerTab")
    main_layout = QVBoxLayout(tab)
    main_layout.setContentsMargins(4, 4, 4, 4)

    # ---------------------- Navigation bar ----------------------
    nav_bar = QHBoxLayout()
    
    btn_back = QPushButton("←")
    btn_back.setToolTip("Back")
    btn_back.setFixedSize(30, 30)
    btn_back.setEnabled(False)
    
    btn_up = QPushButton("↑")
    btn_up.setToolTip("Parent folder")
    btn_up.setFixedSize(30, 30)
    
    lbl_path = QLabel("Path:")
    edit_path = QLineEdit("/sdcard")
    edit_path.setReadOnly(True)
    
    btn_refresh = QPushButton("⟳")
    btn_refresh.setToolTip("Refresh")
    btn_refresh.setFixedSize(30, 30)
    
    nav_bar.addWidget(btn_back)
    nav_bar.addWidget(btn_up)
    nav_bar.addWidget(lbl_path)
    nav_bar.addWidget(edit_path, 1)
    nav_bar.addWidget(btn_refresh)
    
    main_layout.addLayout(nav_bar)

    # ---------------------- Splitter with file list & info panel ----------------------
    splitter = QSplitter(Qt.Orientation.Vertical)
    main_layout.addWidget(splitter, 1)

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
    
    info_panel = QFrame()
    info_panel.setFrameShape(QFrame.Shape.StyledPanel)
    info_layout = QVBoxLayout(info_panel)
    info_layout.setContentsMargins(10, 10, 10, 10)
    
    lbl_info_title = QLabel("File information")
    lbl_info_title.setStyleSheet("font-weight: bold; font-size: 12pt; margin-bottom: 10px;")
    
    lbl_name = QLabel("Name: -")
    lbl_size = QLabel("Size: -")
    lbl_type = QLabel("Type: -")
    lbl_date = QLabel("Date: -")
    
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

    # ---------------------- Status bar ----------------------
    status_bar = QLabel()
    status_bar.setText("Ready.")
    status_bar.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
    main_layout.addWidget(status_bar)

    # ---------------------- Internal variables ----------------------
    current_path = "/sdcard"
    path_history = []

    # ---------------------- Helper functions ----------------------
    def get_file_info(path):
        """Retrieve file information via ADB."""
        if not path:
            return {}
        cmd = f'shell ls -la "{path}"'
        out = _run_adb(main_window, cmd)
        info = {
            'name': os.path.basename(path),
            'path': path,
            'size': '?',
            'type': 'File',
            'date': '?',
            'permissions': '?'
        }
        if out:
            lines = out.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('total'):
                    parts = line.split()
                    if len(parts) >= 9 and parts[-1] == os.path.basename(path):
                        if parts[0].startswith('d'):
                            info['type'] = 'Folder'
                        elif parts[0].startswith('l'):
                            info['type'] = 'Symlink'
                        info['permissions'] = parts[0]
                        info['size'] = parts[4] + " bytes"
                        if len(parts) >= 8:
                            info['date'] = ' '.join(parts[5:8])
                        break
        return info

    def update_file_list():
        """Refresh the list of files/folders in the current directory."""
        nonlocal current_path
        
        list_files.clear()
        status_bar.setText(f"Loading {current_path}...")
        QApplication.processEvents()
        
        cmd = f'shell ls -p "{current_path}"'
        out = _run_adb(main_window, cmd)
        
        if not out:
            status_bar.setText(f"Failed to load {current_path}")
            main_window.log_message(f"[FolderViewer] Error loading {current_path}")
            return
        
        items = []
        for line in out.split('\n'):
            if not line.strip():
                continue
            item_name = line.strip()
            is_dir = item_name.endswith('/')
            if is_dir:
                item_name = item_name[:-1]
                if item_name in ['.', '..']:
                    continue
            items.append((item_name, is_dir))
        
        items.sort(key=lambda x: (not x[1], x[0].lower()))
        
        for item_name, is_dir in items:
            item = QListWidgetItem(item_name)
            if is_dir:
                item.setIcon(QApplication.style().standardIcon(
                    QStyle.StandardPixmap.SP_DirIcon
                ))
                item.setForeground(Qt.GlobalColor.darkBlue)
                item.setData(Qt.ItemDataRole.UserRole, 'dir')
            else:
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
        
        edit_path.setText(current_path)
        btn_back.setEnabled(len(path_history) > 0)
        status_bar.setText(f"Loaded {len(items)} items")
        main_window.log_message(f"[FolderViewer] Loaded folder: {current_path}")

    def on_item_double_clicked(item):
        """Handle double‑click on a list item."""
        nonlocal current_path, path_history
        
        item_name = item.text()
        is_dir = item.data(Qt.ItemDataRole.UserRole) == 'dir'
        
        if is_dir:
            path_history.append(current_path)
            if current_path == "/":
                current_path = f"/{item_name}"
            else:
                current_path = f"{current_path}/{item_name}"
            update_file_list()
            lbl_name.setText("Name: -")
            lbl_size.setText("Size: -")
            lbl_type.setText("Type: -")
            lbl_date.setText("Date: -")

    def on_item_selected():
        """Update the info panel for the selected item."""
        current_item = list_files.currentItem()
        if not current_item:
            return
        item_name = current_item.text()
        is_dir = current_item.data(Qt.ItemDataRole.UserRole) == 'dir'
        full_path = f"/{item_name}" if current_path == "/" else f"{current_path}/{item_name}"
        info = get_file_info(full_path)
        lbl_name.setText(f"Name: {info['name']}")
        lbl_size.setText(f"Size: {info['size']}")
        lbl_type.setText(f"Type: {info['type']}")
        lbl_date.setText(f"Date: {info['date']}")

    def go_up():
        """Navigate to the parent folder."""
        nonlocal current_path, path_history
        
        if current_path == "/":
            return
        path_history.append(current_path)
        if current_path.count('/') == 1:
            current_path = "/"
        else:
            current_path = os.path.dirname(current_path)
        update_file_list()

    def go_back():
        """Return to the previous folder."""
        nonlocal current_path, path_history
        
        if not path_history:
            return
        current_path = path_history.pop()
        update_file_list()

    list_files.itemDoubleClicked.connect(on_item_double_clicked)
    list_files.currentItemChanged.connect(lambda _: on_item_selected())
    btn_up.clicked.connect(go_up)
    btn_back.clicked.connect(go_back)
    btn_refresh.clicked.connect(update_file_list)
    
    def on_path_edited():
        nonlocal current_path
        new_path = edit_path.text().strip()
        if new_path and new_path != current_path:
            cmd = f'shell ls -d "{new_path}"'
            out = _run_adb(main_window, cmd)
            if out:
                current_path = new_path
                update_file_list()
            else:
                QMessageBox.warning(tab, "Error", f"Path {new_path} not found on device.")
                edit_path.setText(current_path)
    
    edit_path.returnPressed.connect(on_path_edited)

    # ---------------------- Context menu ----------------------
    def show_context_menu(pos):
        item = list_files.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        act_open = menu.addAction("Open")
        act_copy_path = menu.addAction("Copy path")
        menu.addSeparator()
        act_refresh = menu.addAction("Refresh list")
        
        action = menu.exec(list_files.mapToGlobal(pos))
        
        if action == act_open:
            on_item_double_clicked(item)
        elif action == act_copy_path:
            item_name = item.text()
            full_path = f"/{item_name}" if current_path == "/" else f"{current_path}/{item_name}"
            clipboard = QApplication.clipboard()
            clipboard.setText(full_path)
            status_bar.setText(f"Path copied: {full_path}")
        elif action == act_refresh:
            update_file_list()

    list_files.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    list_files.customContextMenuRequested.connect(show_context_menu)

    QTimer.singleShot(100, update_file_list)

    main_window.tabs.addTab(tab, "Folder Viewer")
    main_window.log_message("[FolderViewer] Plugin 'Folder Viewer' loaded")
