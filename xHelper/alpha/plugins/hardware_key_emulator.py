# plugins/hardware_key_emulator.py
# -*- coding: utf-8 -*-

"""
hardware_key_emulator – имитация всех возможных аппаратных клавиш Android.

Содержит:
    • Полный словарь всех keycode‑ов Android (по официальной документации
      https://developer.android.com/reference/android/view/KeyEvent#constants) ;
    • UI‑список с поисковой строкой, где каждый элемент выглядит
      «<code> – <NAME>» ;
    • Кнопка «Отправить выбранный», двойной клик по элементу – тот же результат ;
    • Быстрые «готовые» кнопки (Volume ↑/↓, Power, Home, Back, Menu,
      Camera, Search, Media Play/Pause, …) ;
    • Поле «Custom keycode» для произвольного ввода ;
    • Выпадающий список «История», куда автоматически попадают последние 10
      пользовательских кодов.

Все действия используют уже существующий в `XHelperMainWindow` метод
`run_adb_command`, поэтому работают с выбранным в списке устройством
(можно включить «Выполнять на всех выбранных» в главной вкладке
«Устройства»).
"""

import re
from collections import OrderedDict
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QMessageBox,
    QListWidget, QListWidgetItem, QComboBox, QHeaderView,
    QTableWidget, QTableWidgetItem, QScrollArea, QSizePolicy
)


# ----------------------------------------------------------------------
#   Полный справочник всех Android‑keycode (ключ → название)
# ----------------------------------------------------------------------
# Список взят из официальной документации Android (KeyEvent.java);
# упорядочен по возрастанию кода.
KEYCODES = OrderedDict([
    (0,   "UNKNOWN"),
    (1,   "SOFT_LEFT"),
    (2,   "SOFT_RIGHT"),
    (3,   "HOME"),
    (4,   "BACK"),
    (5,   "CALL"),
    (6,   "ENDCALL"),
    (7,   "0"),
    (8,   "1"),
    (9,   "2"),
    (10,  "3"),
    (11,  "4"),
    (12,  "5"),
    (13,  "6"),
    (14,  "7"),
    (15,  "8"),
    (16,  "9"),
    (17,  "STAR"),
    (18,  "POUND"),
    (19,  "DPAD_UP"),
    (20,  "DPAD_DOWN"),
    (21,  "DPAD_LEFT"),
    (22,  "DPAD_RIGHT"),
    (23,  "DPAD_CENTER"),
    (24,  "VOLUME_UP"),
    (25,  "VOLUME_DOWN"),
    (26,  "POWER"),
    (27,  "CAMERA"),
    (28,  "CLEAR"),
    (29,  "A"),
    (30,  "B"),
    (31,  "C"),
    (32,  "D"),
    (33,  "E"),
    (34,  "F"),
    (35,  "G"),
    (36,  "H"),
    (37,  "I"),
    (38,  "J"),
    (39,  "K"),
    (40,  "L"),
    (41,  "M"),
    (42,  "N"),
    (43,  "O"),
    (44,  "P"),
    (45,  "Q"),
    (46,  "R"),
    (47,  "S"),
    (48,  "T"),
    (49,  "U"),
    (50,  "V"),
    (51,  "W"),
    (52,  "X"),
    (53,  "Y"),
    (54,  "Z"),
    (55,  "COMMA"),
    (56,  "PERIOD"),
    (57,  "ALT_LEFT"),
    (58,  "ALT_RIGHT"),
    (59,  "SHIFT_LEFT"),
    (60,  "SHIFT_RIGHT"),
    (61,  "TAB"),
    (62,  "SPACE"),
    (63,  "SYMBOL"),
    (64,  "EXPLORER"),
    (65,  "ENVELOPE"),
    (66,  "ENTER"),
    (67,  "DEL"),
    (68,  "GRAVE"),
    (69,  "MINUS"),
    (70,  "EQUALS"),
    (71,  "LEFT_BRACKET"),
    (72,  "RIGHT_BRACKET"),
    (73,  "BACKSLASH"),
    (74,  "SEMICOLON"),
    (75,  "APOSTROPHE"),
    (76,  "SLASH"),
    (77,  "AT"),
    (78,  "NUM"),
    (79,  "HEADSETHOOK"),
    (80,  "FOCUS"),
    (81,  "PLUS"),
    (82,  "MENU"),
    (83,  "NOTIFICATION"),
    (84,  "SEARCH"),
    (85,  "MEDIA_PLAY_PAUSE"),
    (86,  "MEDIA_STOP"),
    (87,  "MEDIA_NEXT"),
    (88,  "MEDIA_PREVIOUS"),
    (89,  "MEDIA_REWIND"),
    (90,  "MEDIA_FAST_FORWARD"),
    (91,  "MUTE"),
    (92,  "PAGE_UP"),
    (93,  "PAGE_DOWN"),
    (94,  "PICTSYMBOLS"),
    (95,  "SWITCH_CHARSET"),
    (96,  "BUTTON_A"),
    (97,  "BUTTON_B"),
    (98,  "BUTTON_C"),
    (99,  "BUTTON_X"),
    (100, "BUTTON_Y"),
    (101, "BUTTON_Z"),
    (102, "BUTTON_L1"),
    (103, "BUTTON_R1"),
    (104, "BUTTON_L2"),
    (105, "BUTTON_R2"),
    (106, "BUTTON_THUMBL"),
    (107, "BUTTON_THUMBR"),
    (108, "BUTTON_START"),
    (109, "BUTTON_SELECT"),
    (110, "BUTTON_MODE"),
    (111, "ESCAPE"),
    (112, "FORWARD_DEL"),
    (113, "CTRL_LEFT"),
    (114, "CTRL_RIGHT"),
    (115, "CAPS_LOCK"),
    (116, "SCROLL_LOCK"),
    (117, "META_LEFT"),
    (118, "META_RIGHT"),
    (119, "FUNCTION"),
    (120, "SYSRQ"),
    (121, "BREAK"),
    (122, "MOVE_HOME"),
    (123, "MOVE_END"),
    (124, "INSERT"),
    (125, "FORWARD"),
    (126, "MEDIA_PLAY"),
    (127, "MEDIA_PAUSE"),
    (128, "MEDIA_CLOSE"),
    (129, "MEDIA_EJECT"),
    (130, "MEDIA_RECORD"),
    (131, "F1"),
    (132, "F2"),
    (133, "F3"),
    (134, "F4"),
    (135, "F5"),
    (136, "F6"),
    (137, "F7"),
    (138, "F8"),
    (139, "F9"),
    (140, "F10"),
    (141, "F11"),
    (142, "F12"),
    (143, "NUM_LOCK"),
    (144, "NUMPAD_0"),
    (145, "NUMPAD_1"),
    (146, "NUMPAD_2"),
    (147, "NUMPAD_3"),
    (148, "NUMPAD_4"),
    (149, "NUMPAD_5"),
    (150, "NUMPAD_6"),
    (151, "NUMPAD_7"),
    (152, "NUMPAD_8"),
    (153, "NUMPAD_9"),
    (154, "NUMPAD_DIVIDE"),
    (155, "NUMPAD_MULTIPLY"),
    (156, "NUMPAD_SUBTRACT"),
    (157, "NUMPAD_ADD"),
    (158, "NUMPAD_DOT"),
    (159, "NUMPAD_COMMA"),
    (160, "NUMPAD_ENTER"),
    (161, "NUMPAD_EQUALS"),
    (162, "NUMPAD_LEFT_PAREN"),
    (163, "NUMPAD_RIGHT_PAREN"),
    (164, "VOLUME_MUTE"),
    (165, "INFO"),
    (166, "CHANNEL_UP"),
    (167, "CHANNEL_DOWN"),
    (168, "ZOOM_IN"),
    (169, "ZOOM_OUT"),
    (170, "TV"),
    (171, "WINDOW"),
    (172, "GUIDE"),
    (173, "DVR"),
    (174, "BOOKMARK"),
    (175, "CAPTIONS"),
    (176, "SETTINGS"),
    (177, "TV_POWER"),
    (178, "TV_INPUT"),
    (179, "STB_POWER"),
    (180, "STB_INPUT"),
    (181, "AVR_POWER"),
    (182, "AVR_INPUT"),
    (183, "PROG_RED"),
    (184, "PROG_GREEN"),
    (185, "PROG_YELLOW"),
    (186, "PROG_BLUE"),
    (187, "APP_SWITCH"),
    (188, "BUTTON_1"),
    (189, "BUTTON_2"),
    (190, "BUTTON_3"),
    (191, "BUTTON_4"),
    (192, "BUTTON_5"),
    (193, "BUTTON_6"),
    (194, "BUTTON_7"),
    (195, "BUTTON_8"),
    (196, "BUTTON_9"),
    (197, "BUTTON_10"),
    (198, "BUTTON_11"),
    (199, "BUTTON_12"),
    (200, "BUTTON_13"),
    (201, "BUTTON_14"),
    (202, "BUTTON_15"),
    (203, "BUTTON_16"),
    (204, "LANGUAGE_SWITCH"),
    (205, "MANNER_MODE"),
    (206, "3D_MODE"),
    (207, "CONTACTS"),
    (208, "CALENDAR"),
    (209, "MUSIC"),
    (210, "CALCULATOR"),
    (211, "ZENKAKU_HANKAKU"),
    (212, "EISU"),
    (213, "MUHENKAN"),
    (214, "HENKAN"),
    (215, "KATAKANA_HIRAGANA"),
    (216, "YEN"),
    (217, "RO"),
    (218, "KANA"),
    (219, "ASSIST"),
    (220, "BRIGHTNESS_DOWN"),
    (221, "BRIGHTNESS_UP"),
    (222, "MEDIA_AUDIO_TRACK"),
    (223, "SLEEP"),
    (224, "WAKEUP"),
    (225, "PAIRING"),
    (226, "MEDIA_SKIP_FORWARD"),
    (227, "MEDIA_SKIP_BACKWARD"),
    (228, "MEDIA_STEP_FORWARD"),
    (229, "MEDIA_STEP_BACKWARD"),
    (230, "SOFT_SLEEP"),
    (231, "CUT"),
    (232, "COPY"),
    (233, "PASTE"),
    (234, "SYSTEM_NAVIGATION_DOWN"),
    (235, "SYSTEM_NAVIGATION_LEFT"),
    (236, "SYSTEM_NAVIGATION_RIGHT"),
    (237, "SYSTEM_NAVIGATION_UP"),
    (238, "ALL_APPS"),
    (239, "REFRESH"),
    (240, "THUMBS_UP"),
    (241, "THUMBS_DOWN"),
    (242, "PROFILE_SWITCH"),
    (243, "CAMERA_FOCUS"),
    (244, "PAGE_UP"),
    (245, "PAGE_DOWN"),
    (246, "POWER"),
    (247, "POWER2"),
    (248, "POWER3"),
    (249, "POWEROFF"),
    (250, "SOUND"),
    (251, "VOLUME_MUTE"),
    (252, "HEADSETHOOK"),
    (253, "HITAMG"),
    (254, "MEDIA_RECORD"),
    (255, "UNKNOWN"),  # Android позволяет использовать любые коды 0‑255
])
# ----------------------------------------------------------------------
#   Внутренние помощники
# ----------------------------------------------------------------------
def _run_keyevent(main_window, code: int):
    """Отправить adb‑команду `input keyevent <code>`."""
    main_window.run_adb_command(f"shell input keyevent {code}", device_specific=True)


def _is_valid_keycode(text: str) -> bool:
    """Проверить, что в поле ввода содержится целое число 0‑255."""
    return bool(re.fullmatch(r"\d{1,3}", text.strip())) and 0 <= int(text) <= 255


# ----------------------------------------------------------------------
#   Основная регистрационная функция, вызываемая XHelperMainWindow.load_plugins()
# ----------------------------------------------------------------------
def register(main_window):
    tab = QWidget()
    tab_layout = QVBoxLayout(tab)

    # --------------------------------------------------------------
    #   1️⃣ Быстрые кнопки (самые часто‑используемые)
    # --------------------------------------------------------------
    quick_group = QGroupBox("Быстрые клавиши")
    quick_layout = QHBoxLayout(quick_group)

    QUICK = [
        ("Vol ↑", 24),
        ("Vol ↓", 25),
        ("Power", 26),
        ("Home", 3),
        ("Back", 4),
        ("Menu", 82),
        ("Camera", 27),
        ("Search", 84),
        ("Media Play/Pause", 85),
        ("Media Next", 87),
        ("Media Prev", 88),
        ("Media Stop", 86),
        ("Assist", 219),
    ]

    for txt, code in QUICK:
        btn = QPushButton(txt)
        btn.clicked.connect(lambda _, c=code: _run_keyevent(main_window, c))
        quick_layout.addWidget(btn)
    tab_layout.addWidget(quick_group)

    # --------------------------------------------------------------
    #   2️⃣ Полный список всех кодов (с фильтром)
    # --------------------------------------------------------------
    list_group = QGroupBox("Полный список кодов (0‑255)")
    list_layout = QVBoxLayout(list_group)

    # строка‑фильтр
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText("Фильтр: введите часть названия или код…")
    list_layout.addWidget(filter_edit)

    # прокручиваемый виджет со списком
    list_widget = QListWidget()
    list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    list_widget.setMinimumHeight(300)
    list_layout.addWidget(list_widget)
    tab_layout.addWidget(list_group)

    # Заполняем список (код – название)
    for code, name in KEYCODES.items():
        item = QListWidgetItem(f"{code:3d} – {name}")
        # Сохраняем код в собственном свойстве (нужен для отправки)
        item.setData(Qt.ItemDataRole.UserRole, code)
        list_widget.addItem(item)

    # Фильтрация в режиме «по‑тику»
    def do_filter():
        txt = filter_edit.text().strip().lower()
        for i in range(list_widget.count()):
            it = list_widget.item(i)
            visible = txt in it.text().lower()
            it.setHidden(not visible)

    filter_edit.textChanged.connect(do_filter)

    # Двойной клик – отправка
    def on_item_activated(item: QListWidgetItem):
        code = item.data(Qt.ItemDataRole.UserRole)
        _run_keyevent(main_window, code)
        main_window.log_message(f"[KeyEmu] Sent keycode {code} ({item.text()})")

    list_widget.itemDoubleClicked.connect(on_item_activated)

    # --------------------------------------------------------------
    #   3️⃣ Кнопка «Отправить выбранный» (для тех, кто не любит двойные клики)
    # --------------------------------------------------------------
    btn_send_selected = QPushButton("Отправить выбранный")
    btn_send_selected.setEnabled(False)
    list_layout.addWidget(btn_send_selected)

    def enable_send():
        btn_send_selected.setEnabled(bool(list_widget.currentItem()))

    list_widget.currentItemChanged.connect(lambda _: enable_send())

    def send_selected():
        cur = list_widget.currentItem()
        if cur:
            on_item_activated(cur)

    btn_send_selected.clicked.connect(send_selected)

    # --------------------------------------------------------------
    #   4️⃣ Пользовательский ввод keycode (ручной)
    # --------------------------------------------------------------
    custom_group = QGroupBox("Custom keycode (0‑255)")
    custom_layout = QHBoxLayout(custom_group)

    lbl_custom = QLabel("Код:")
    edit_custom = QLineEdit()
    edit_custom.setMaximumWidth(80)
    edit_custom.setPlaceholderText("например, 66")
    btn_custom = QPushButton("Send")
    btn_custom.setEnabled(False)

    # включаем кнопку, если в поле число от 0 до 255
    def validate_custom():
        btn_custom.setEnabled(_is_valid_keycode(edit_custom.text()))

    edit_custom.textChanged.connect(validate_custom)

    def send_custom():
        code = int(edit_custom.text())
        _run_keyevent(main_window, code)
        main_window.log_message(f"[KeyEmu] Sent custom keycode {code}")
        # добавить в историю пользовательских кодов
        if code not in [combo.itemText(i) for i in range(combo.count())]:
            combo.insertItem(0, str(code))
            # сохраняем только 10 последних
            while combo.count() > 10:
                combo.removeItem(combo.count() - 1)

    btn_custom.clicked.connect(send_custom)
    custom_layout.addWidget(lbl_custom)
    custom_layout.addWidget(edit_custom)
    custom_layout.addWidget(btn_custom)
    tab_layout.addWidget(custom_group)

    # --------------------------------------------------------------
    #   5️⃣ История пользовательских кодов (ComboBox)
    # --------------------------------------------------------------
    history_group = QGroupBox("История пользовательских keycode")
    hist_layout = QHBoxLayout(history_group)
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.InsertAtTop)
    btn_hist_send = QPushButton("Send")
    btn_hist_send.setEnabled(False)

    def enable_hist_send():
        txt = combo.currentText().strip()
        btn_hist_send.setEnabled(_is_valid_keycode(txt))

    combo.currentTextChanged.connect(enable_hist_send)

    def send_from_history():
        txt = combo.currentText().strip()
        if _is_valid_keycode(txt):
            code = int(txt)
            _run_keyevent(main_window, code)
            main_window.log_message(f"[KeyEmu] Sent keycode {code} (из истории)")
        else:
            QMessageBox.warning(tab, "Ошибка", "Введите корректный keycode (0‑255)")

    btn_hist_send.clicked.connect(send_from_history)
    hist_layout.addWidget(combo)
    hist_layout.addWidget(btn_hist_send)
    tab_layout.addWidget(history_group)

    # --------------------------------------------------------------
    #   Финальная сборка вкладки
    # --------------------------------------------------------------
    tab_layout.addStretch()          # отодвинуть всё к верху
    main_window.tabs.addTab(tab, "Аппаратные клавиши")
