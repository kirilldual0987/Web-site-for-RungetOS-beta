# -*- coding: utf-8 -*-
"""
Extended Backups plugin

Allows the user to create flexible backups:
 • individual media directories (photos, videos, documents);
 • user apps;
 • system apps (requires root);
 • full backup (as in the built‑in “Backup / Restore” tab).

Works with xHelper alpha 1.0.1 LTS/ATS (or any newer version that
supports the plugin‑loading mechanism).
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
#   Worker thread – actually performs all backup operations
# ----------------------------------------------------------------------
class BackupWorker(QThread):
    """Executes the backup steps selected by the user."""
    log_signal      = pyqtSignal(str)   # messages that go to the console
    progress_signal = pyqtSignal(int)   # progress bar updates
    finished_signal = pyqtSignal()      # completion signal

    def __init__(self, main_window, dest_dir: str, opts: dict):
        """
        :param main_window: reference to the main XHelperMainWindow
        :param dest_dir:   absolute path to the folder where the backup will be saved
        :param opts:       dict with configuration (which checkboxes are ticked)
        """
        super().__init__()
        self.main = main_window
        self.dest_dir = Path(dest_dir)
        self.opts = opts
        self.adb = self.main.settings.get("adb_path", "adb")
        self.steps = self._count_steps()          # number of steps for the progress bar
        self.current_step = 0

    # ------------------------------------------------------------------
    #   Count steps for progress calculation
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
    #   Helper functions that log via signal
    # ------------------------------------------------------------------
    def _log(self, txt: str):
        self.log_signal.emit(txt)

    def _step(self):
        """Increment step counter and emit progress."""
        self.current_step += 1
        self.progress_signal.emit(int(self.current_step / self.steps * 100))

    # ------------------------------------------------------------------
    #   Main thread method
    # ------------------------------------------------------------------
    def run(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = self.dest_dir / f"tmp_backup_{timestamp}"
        try:
            # --------------------------------------------------------------
            #   Full backup via adb backup (if selected)
            # --------------------------------------------------------------
            if self.opts.get("full_backup"):
                self._log("[Backup] Starting full backup (adb backup …)")
                full_path = self.dest_dir / f"full_backup_{timestamp}.ab"
                cmd = [
                    self.adb,
                    "backup",
                    "-apk",
                    "-shared",
                    "-all",
                    "-f",
                    str(full_path)
                ]
                subprocess.run(cmd, check=True)
                self._log(f"[Backup] Full backup saved to {full_path}")
                self._step()
                # Full backup already covers everything; skip other steps
                self.finished_signal.emit()
                return

            # --------------------------------------------------------------
            #   For partial backup, create temporary folder
            # --------------------------------------------------------------
            temp_dir.mkdir(parents=True, exist_ok=True)

            # --------------------------------------------------------------
            #   1) Photos (/sdcard/DCIM)
            # --------------------------------------------------------------
            if self.opts.get("photos"):
                self._log("[Backup] Pulling photos (DCIM)…")
                remote = "/sdcard/DCIM"
                local  = temp_dir / "DCIM"
                subprocess.run([self.adb, "pull", remote, str(local)], check=True)
                self._log("[Backup] Photos copied")
                self._step()

            # --------------------------------------------------------------
            #   2) Videos (/sdcard/Movies)
            # --------------------------------------------------------------
            if self.opts.get("videos"):
                self._log("[Backup] Pulling videos (Movies)…")
                remote = "/sdcard/Movies"
                local  = temp_dir / "Movies"
                subprocess.run([self.adb, "pull", remote, str(local)], check=True)
                self._log("[Backup] Videos copied")
                self._step()

            # --------------------------------------------------------------
            #   3) Documents (/sdcard/Download and /sdcard/Documents)
            # --------------------------------------------------------------
            if self.opts.get("documents"):
                self._log("[Backup] Pulling documents (Download, Documents)…")
                for remote_dir in ("/sdcard/Download", "/sdcard/Documents"):
                    name = Path(remote_dir).name
                    local = temp_dir / name
                    subprocess.run([self.adb, "pull", remote_dir, str(local)], check=True)
                self._log("[Backup] Documents copied")
                self._step()

            # --------------------------------------------------------------
            #   4) User applications
            # --------------------------------------------------------------
            if self.opts.get("user_apps"):
                self._log("[Backup] Getting list of user packages…")
                out = subprocess.check_output(
                    [self.adb, "shell", "pm", "list", "packages", "-3"],
                    text=True
                )
                packages = [line.replace("package:", "").strip()
                            for line in out.splitlines()
                            if line.strip()]
                self._log(f"[Backup] Found {len(packages)} user packages")
                apps_dir = temp_dir / "user_apps"
                apps_dir.mkdir(parents=True, exist_ok=True)
                for idx, pkg in enumerate(packages, start=1):
                    self._log(f"[Backup] Backing up package {idx}/{len(packages)}: {pkg}")
                    out_path = apps_dir / f"{pkg}_{timestamp}.ab"
                    cmd = [
                        self.adb,
                        "backup",
                        "-apk",
                        "-noobb",
                        "-f",
                        str(out_path),
                        pkg
                    ]
                    subprocess.run(cmd, check=True)
                self._log("[Backup] User apps saved")
                self._step()

            # --------------------------------------------------------------
            #   5) System applications (requires root)
            # --------------------------------------------------------------
            if self.opts.get("system_apps"):
                self._log("[Backup] Getting list of system packages…")
                out = subprocess.check_output(
                    [self.adb, "shell", "pm", "list", "packages", "-s"],
                    text=True
                )
                packages = [line.replace("package:", "").strip()
                            for line in out.splitlines()
                            if line.strip()]
                self._log(f"[Backup] Found {len(packages)} system packages")
                sys_dir = temp_dir / "system_apps"
                sys_dir.mkdir(parents=True, exist_ok=True)
                for idx, pkg in enumerate(packages, start=1):
                    self._log(f"[Backup] Backing up system package {idx}/{len(packages)}: {pkg}")
                    out_path = sys_dir / f"{pkg}_{timestamp}.ab"
                    cmd = [
                        self.adb,
                        "backup",
                        "-noapk",
                        "-f",
                        str(out_path),
                        pkg
                    ]
                    subprocess.run(cmd, check=True)
                self._log("[Backup] System apps saved")
                self._step()

            # --------------------------------------------------------------
            #   Assemble final zip archive
            # --------------------------------------------------------------
            self._log("[Backup] Creating final archive…")
            zip_name = self.dest_dir / f"xHelper_backup_{timestamp}.zip"
            with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        full_path = Path(root) / file
                        relative = full_path.relative_to(temp_dir)
                        zipf.write(full_path, arcname=relative)

            self._log(f"[Backup] Archive created: {zip_name}")

        except subprocess.CalledProcessError as e:
            self._log(f"[Backup][ERROR] Command exited with code {e.returncode}")
            self._log(e.output or "")
        except Exception as exc:
            self._log(f"[Backup][EXCEPTION] {exc}")
        finally:
            # ------------------------------------------------------------------
            #   Clean up temporary folder (if it exists)
            # ------------------------------------------------------------------
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    self._log("[Backup] Temporary folder removed")
                except Exception as e_cleanup:
                    self._log(f"[Backup][WARN] Could not delete temp‑dir: {e_cleanup}")

            # ------------------------------------------------------------------
            #   Emit completion signals
            # ------------------------------------------------------------------
            self.finished_signal.emit()


# ----------------------------------------------------------------------
#   Function called when the plugin is loaded
# ----------------------------------------------------------------------
def register(main_window):
    """
    Adds a UI under the “Extended Backups” tab for selecting
    backup categories and a start button.
    """
    # ------------------------------------------------------------------
    #   UI elements for the tab
    # ------------------------------------------------------------------
    tab = QWidget()
    main_layout = QVBoxLayout(tab)

    # ----- Category selection group ---------------------------------
    group = QGroupBox("What to backup")
    grp_layout = QVBoxLayout(group)

    cb_photos       = QCheckBox("Photos (/sdcard/DCIM)")
    cb_videos       = QCheckBox("Videos (/sdcard/Movies)")
    cb_documents    = QCheckBox("Documents (/sdcard/Download, /sdcard/Documents)")
    cb_user_apps    = QCheckBox("User apps")
    cb_system_apps  = QCheckBox("System apps (requires root)")
    cb_full         = QCheckBox("Full backup (as in built‑in tab)")

    # No checks by default – user chooses explicitly
    for w in (cb_photos, cb_videos, cb_documents,
              cb_user_apps, cb_system_apps, cb_full):
        grp_layout.addWidget(w)

    # ----- Destination path -----------------------------------------
    dest_layout = QHBoxLayout()
    dest_label = QLabel("Destination folder:")
    dest_edit = QLineEdit()
    dest_btn = QPushButton("Browse")
    dest_layout.addWidget(dest_label)
    dest_layout.addWidget(dest_edit)
    dest_layout.addWidget(dest_btn)

    def choose_folder():
        folder = QFileDialog.getExistingDirectory(
            tab, "Select folder to save the backup"
        )
        if folder:
            dest_edit.setText(folder)

    dest_btn.clicked.connect(choose_folder)

    # ----- Start button --------------------------------------------
    btn_start = QPushButton("Create backup")
    progress = QProgressBar()
    progress.setVisible(False)

    # ----- Layout -------------------------------------------------
    main_layout.addWidget(group)
    main_layout.addLayout(dest_layout)
    main_layout.addWidget(btn_start)
    main_layout.addWidget(progress)

    # ------------------------------------------------------------------
    #   Handler for “Create backup” button
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
                "Warning",
                "Select at least one backup option"
            )
            return

        dest_path = dest_edit.text().strip()
        if not dest_path:
            QMessageBox.warning(tab, "Warning", "Specify a destination folder")
            return

        # build options dict -----------------------------------------
        opts = {
            "photos":       cb_photos.isChecked(),
            "videos":       cb_videos.isChecked(),
            "documents":    cb_documents.isChecked(),
            "user_apps":    cb_user_apps.isChecked(),
            "system_apps":  cb_system_apps.isChecked(),
            "full_backup":  cb_full.isChecked()
        }

        # UI – disable elements, show progress -------------------------
        btn_start.setEnabled(False)
        progress.setVisible(True)
        progress.setValue(0)

        # create and start worker thread
        worker = BackupWorker(main_window, dest_path, opts)
        worker.log_signal.connect(main_window.log_message)
        worker.progress_signal.connect(progress.setValue)
        worker.finished_signal.connect(lambda: backup_finished(worker))

        worker.start()

    def backup_finished(worker_instance):
        """Reset UI after thread finishes."""
        btn_start.setEnabled(True)
        progress.setVisible(False)
        QMessageBox.information(
            tab,
            "Done",
            "Backup completed.\nAll files are saved in the chosen folder."
        )
        # cleanly stop the thread (just in case)
        worker_instance.quit()
        worker_instance.wait()

    btn_start.clicked.connect(start_backup)

    # ------------------------------------------------------------------
    #   Add the tab to the main window
    # ------------------------------------------------------------------
    main_window.tabs.addTab(tab, "Extended Backups")
