# -*- coding: utf-8 -*-
"""
Плагин «Extended Backups»

Позволяет пользователю формировать гибкие бэкапы:
 • отдельные мультимедийные каталоги (фото, видео, документы);
 • пользовательские приложения;
 • системные приложения (требует root‑доступ);
 • полное резервирование (как в штатной вкладке «Бэкап / Восстановление»).

Работает в составе xHelper alpha 1.0.1 LTS/ATS (или любой более новой
версии, где присутствует механизм загрузки плагинов).
"""

import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QPushButton,
    QLineEdit, QLabel, QFileDialog, QMessageBox,
    QProgressBar, QHBoxLayout
)


# ----------------------------------------------------------------------
#   Рабочий поток – реально делает всё резервирование
# ----------------------------------------------------------------------
class BackupWorker(QThread):
    """Выполняет выбранные пользователем операции резервирования."""
    log_signal      = pyqtSignal(str)   # сообщения, которые будут идти в консоль
    progress_signal = pyqtSignal(int)   # обновление прогресса
    finished_signal = pyqtSignal()      # сигнал завершения

    def __init__(self, main_window, dest_dir: str, opts: dict):
        """
        :param main_window: ссылка на главный объект XHelperMainWindow
        :param dest_dir:   абсолютный путь к папке, куда будет сохраняться бэкап
        :param opts:       словарь с конфигурацией (какие чекбоксы отмечены)
        """
        super().__init__()
        self.main = main_window
        self.dest_dir = Path(dest_dir)
        self.opts = opts
        self.adb = self.main.settings.get("adb_path", "adb")
        self.steps = self._count_steps()          # количество шагов для шкалы прогресса
        self.current_step = 0

    # ------------------------------------------------------------------
    #   Подсчёт количества отдельных шагов (нужен для корректного прогресса)
    # ------------------------------------------------------------------
    def _count_steps(self) -> int:
        steps = 0
        if self.opts.get("full_backup"):
            steps += 1
        else:
            if self.opts.get("photos"):
                steps += 1
            if self.opts.get("videos"):
                steps += 1
            if self.opts.get("documents"):
                steps += 1
            if self.opts.get("user_apps"):
                steps += 1
            if self.opts.get("system_apps"):
                steps += 1
        return max(steps, 1)

    # ------------------------------------------------------------------
    #   Вспомогательные функции, которые пишут в лог через сигнал
    # ------------------------------------------------------------------
    def _log(self, txt: str):
        self.log_signal.emit(txt)

    def _step(self):
        """Увеличивает счётчик шага и эмитит сигнал прогресса."""
        self.current_step += 1
        self.progress_signal.emit(int(self.current_step / self.steps * 100))

    # ------------------------------------------------------------------
    #   Основной метод потока
    # ------------------------------------------------------------------
    def run(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = self.dest_dir / f"tmp_backup_{timestamp}"
        try:
            # --------------------------------------------------------------
            #   Полный бэкап через adb backup  (если выбран)
            # --------------------------------------------------------------
            if self.opts.get("full_backup"):
                self._log("[Backup] Запуск полного бэкапа (adb backup …)")
                full_path = self.dest_dir / f"full_backup_{timestamp}.ab"
                cmd = [
                    self.adb,
                    "backup",
                    "-apk",          # включаем apk‑файлы
                    "-shared",       # включаем данные sdcard
                    "-all",          # все пакеты
                    "-f",
                    str(full_path)
                ]
                subprocess.run(cmd, check=True)
                self._log(f"[Backup] Полный бэкап сохранён в {full_path}")
                self._step()
                # Полный бэкап уже охватывает всё, поэтому остальные пункты не нужны
                self.finished_signal.emit()
                return

            # --------------------------------------------------------------
            #   Для частичного бэкапа создаём временную папку
            # --------------------------------------------------------------
            temp_dir.mkdir(parents=True, exist_ok=True)

            # --------------------------------------------------------------
            #   1) Фотографии   (/sdcard/DCIM)
            # --------------------------------------------------------------
            if self.opts.get("photos"):
                self._log("[Backup] Копируем фото (DCIM)…")
                remote = "/sdcard/DCIM"
                local  = temp_dir / "DCIM"
                subprocess.run([self.adb, "pull", remote, str(local)], check=True)
                self._log("[Backup] Фото скопированы")
                self._step()

            # --------------------------------------------------------------
            #   2) Видео   (/sdcard/Movies)
            # --------------------------------------------------------------
            if self.opts.get("videos"):
                self._log("[Backup] Копируем видео (Movies)…")
                remote = "/sdcard/Movies"
                local  = temp_dir / "Movies"
                subprocess.run([self.adb, "pull", remote, str(local)], check=True)
                self._log("[Backup] Видео скопированы")
                self._step()

            # --------------------------------------------------------------
            #   3) Документы   (/sdcard/Download и /sdcard/Documents)
            # --------------------------------------------------------------
            if self.opts.get("documents"):
                self._log("[Backup] Копируем документы (Download, Documents)…")
                for remote_dir in ("/sdcard/Download", "/sdcard/Documents"):
                    name = Path(remote_dir).name
                    local = temp_dir / name
                    subprocess.run([self.adb, "pull", remote_dir, str(local)], check=True)
                self._log("[Backup] Документы скопированы")
                self._step()

            # --------------------------------------------------------------
            #   4) Пользовательские приложения
            # --------------------------------------------------------------
            if self.opts.get("user_apps"):
                self._log("[Backup] Получаем список пользовательских пакетов…")
                out = subprocess.check_output(
                    [self.adb, "shell", "pm", "list", "packages", "-3"],
                    text=True
                )
                packages = [line.replace("package:", "").strip()
                            for line in out.splitlines()
                            if line.strip()]
                self._log(f"[Backup] Найдено пользовательских пакетов: {len(packages)}")
                apps_dir = temp_dir / "user_apps"
                apps_dir.mkdir(parents=True, exist_ok=True)
                for idx, pkg in enumerate(packages, start=1):
                    self._log(f"[Backup] Бэкап пакета {idx}/{len(packages)}: {pkg}")
                    out_path = apps_dir / f"{pkg}_{timestamp}.ab"
                    cmd = [
                        self.adb,
                        "backup",
                        "-apk",          # включаем .apk
                        "-noobb",        # без OBB (необязательно)
                        "-f",
                        str(out_path),
                        pkg
                    ]
                    subprocess.run(cmd, check=True)
                self._log("[Backup] Пользовательские приложения сохранены")
                self._step()

            # --------------------------------------------------------------
            #   5) Системные приложения (требует root)
            # --------------------------------------------------------------
            if self.opts.get("system_apps"):
                self._log("[Backup] Получаем список системных пакетов…")
                out = subprocess.check_output(
                    [self.adb, "shell", "pm", "list", "packages", "-s"],
                    text=True
                )
                packages = [line.replace("package:", "").strip()
                            for line in out.splitlines()
                            if line.strip()]
                self._log(f"[Backup] Найдено системных пакетов: {len(packages)}")
                sys_dir = temp_dir / "system_apps"
                sys_dir.mkdir(parents=True, exist_ok=True)
                for idx, pkg in enumerate(packages, start=1):
                    self._log(f"[Backup] Бэкап системного пакета {idx}/{len(packages)}: {pkg}")
                    out_path = sys_dir / f"{pkg}_{timestamp}.ab"
                    cmd = [
                        self.adb,
                        "backup",
                        "-noapk",       # без .apk – системные обычно менять нельзя
                        "-f",
                        str(out_path),
                        pkg
                    ]
                    subprocess.run(cmd, check=True)
                self._log("[Backup] Системные приложения сохранены")
                self._step()

            # --------------------------------------------------------------
            #   Сборка итогового zip‑файла
            # --------------------------------------------------------------
            self._log("[Backup] Формируем итоговый архив…")
            zip_name = self.dest_dir / f"xHelper_backup_{timestamp}.zip"
            with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        full_path = Path(root) / file
                        relative = full_path.relative_to(temp_dir)
                        zipf.write(full_path, arcname=relative)

            self._log(f"[Backup] Архив создан: {zip_name}")

        except subprocess.CalledProcessError as e:
            self._log(f"[Backup][ERROR] Команда завершилась с кодом {e.returncode}")
            self._log(e.output or "")
        except Exception as exc:
            self._log(f"[Backup][EXCEPTION] {exc}")
        finally:
            # ------------------------------------------------------------------
            #   Очистка временной папки (если она существует)
            # ------------------------------------------------------------------
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    self._log("[Backup] Удалена временная папка")
                except Exception as e_cleanup:
                    self._log(f"[Backup][WARN] Не удалось удалить temp‑dir: {e_cleanup}")

            # ------------------------------------------------------------------
            #   Сигналы о завершении
            # ------------------------------------------------------------------
            self.finished_signal.emit()


# ----------------------------------------------------------------------
#   Функция, вызываемая при загрузке плагина
# ----------------------------------------------------------------------
def register(main_window):
    """
    Добавляет во вкладку «Extended Backups» UI для выбора
    категорий резервирования и кнопку запуска.
    """
    # ------------------------------------------------------------------
    #   UI‑элементы вкладки
    # ------------------------------------------------------------------
    tab = QWidget()
    main_layout = QVBoxLayout(tab)

    # ----- Группа выбора категорий ---------------------------------
    group = QGroupBox("Что резервировать")
    grp_layout = QVBoxLayout(group)

    cb_photos       = QCheckBox("Фотографии ( /sdcard/DCIM )")
    cb_videos       = QCheckBox("Видео ( /sdcard/Movies )")
    cb_documents    = QCheckBox("Документы ( /sdcard/Download, /sdcard/Documents )")
    cb_user_apps    = QCheckBox("Пользовательские приложения")
    cb_system_apps  = QCheckBox("Системные приложения (требует root)")
    cb_full         = QCheckBox("Полный бэкап (как в штатной вкладке)")

    # по умолчанию чеков нет – пользователь выбирает явно
    for w in (cb_photos, cb_videos, cb_documents,
              cb_user_apps, cb_system_apps, cb_full):
        grp_layout.addWidget(w)

    # ----- Путь назначения -----------------------------------------
    dest_layout = QHBoxLayout()
    dest_label = QLabel("Папка назначения:")
    dest_edit = QLineEdit()
    dest_btn = QPushButton("Обзор")
    dest_layout.addWidget(dest_label)
    dest_layout.addWidget(dest_edit)
    dest_layout.addWidget(dest_btn)

    def choose_folder():
        folder = QFileDialog.getExistingDirectory(
            tab, "Выберите папку для сохранения бэкапа"
        )
        if folder:
            dest_edit.setText(folder)

    dest_btn.clicked.connect(choose_folder)

    # ----- Кнопка запуска -----------------------------------------
    btn_start = QPushButton("Создать резервную копию")
    progress = QProgressBar()
    progress.setVisible(False)

    # ----- Компоновка ---------------------------------------------
    main_layout.addWidget(group)
    main_layout.addLayout(dest_layout)
    main_layout.addWidget(btn_start)
    main_layout.addWidget(progress)

    # ------------------------------------------------------------------
    #   Обработчик кнопки «Создать резервную копию»
    # ------------------------------------------------------------------
    def start_backup():
        # validation ----------------------------------------------------
        if not any((cb_photos.isChecked(),
                    cb_videos.isChecked(),
                    cb_documents.isChecked(),
                    cb_user_apps.isChecked(),
                    cb_system_apps.isChecked(),
                    cb_full.isChecked())):
            QMessageBox.warning(
                tab,
                "Внимание",
                "Выберите хотя бы одну опцию для резервирования"
            )
            return

        dest_path = dest_edit.text().strip()
        if not dest_path:
            QMessageBox.warning(tab, "Внимание", "Укажите папку назначения")
            return

        # создаём словарь опций -----------------------------------------
        opts = {
            "photos"       : cb_photos.isChecked(),
            "videos"       : cb_videos.isChecked(),
            "documents"    : cb_documents.isChecked(),
            "user_apps"    : cb_user_apps.isChecked(),
            "system_apps"  : cb_system_apps.isChecked(),
            "full_backup"  : cb_full.isChecked()
        }

        # UI – блокируем элементы, показываем прогресс -----------------
        btn_start.setEnabled(False)
        progress.setVisible(True)
        progress.setValue(0)

        # создаём и запускаем рабочий поток
        worker = BackupWorker(main_window, dest_path, opts)
        worker.log_signal.connect(main_window.log_message)
        worker.progress_signal.connect(progress.setValue)
        worker.finished_signal.connect(lambda: backup_finished(worker))

        worker.start()

    def backup_finished(worker_instance):
        """Сброс UI после завершения потока."""
        btn_start.setEnabled(True)
        progress.setVisible(False)
        QMessageBox.information(
            tab,
            "Готово",
            "Резервное копирование завершено.\n"
            "Все файлы находятся в выбранной папке."
        )
        # корректно завершаем поток (на всякий случай)
        worker_instance.quit()
        worker_instance.wait()

    btn_start.clicked.connect(start_backup)

    # ------------------------------------------------------------------
    #   Добавляем готовую вкладку в главное окно
    # ------------------------------------------------------------------
    main_window.tabs.addTab(tab, "Extended Backups")
