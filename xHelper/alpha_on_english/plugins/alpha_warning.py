# plugins/alpha_warning.py
# -*- coding: utf-8 -*-

"""
alpha_warning – plugin module that shows a warning dialog when
starting xHelper α (version 1.0.1 LTS/ATS).

Dialog contents:
    • Text: “This program is an alpha version, use at your own risk.
      Do you want to start using the Alpha version?”
    • **“Yes”** button – closes the warning and continues.
    • **“No”** button – closes the application.
    • **“What does this mean?”** button – opens a second helper window
      that explains possible crashes, a short guide for using xHelper,
      and how to write plugins.

The plugin does not modify core logic and uses only the public API
`main_window` (logging, closing the window, timers).
"""

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QTextEdit, QMessageBox,
)


# ----------------------------------------------------------------------
#   Help text (HTML) – translated to English
# ----------------------------------------------------------------------
HELP_TEXT = """
<h2>⚠️  This is an Alpha version</h2>
<p>
The program <b>xHelper α (1.0.1 LTS/ATS)</b> is in <i>alpha stage</i>.
That means it may contain:
<ul>
<li>unfinished features;</li>
<li>unexpected crashes when using ADB/fastboot;</li>
<li>incorrect responses from the device;</li>
<li>UI glitches if several heavy operations run simultaneously.</li>
</ul>
We strongly recommend using this build <b>only for testing</b> and <b>not</b> in critical projects.
</p>

<hr>

<h2>📚  Quick guide to using xHelper</h2>
<ol>
<li><b>Connect a device</b> – open the “Devices” tab and click “Refresh device list”. Make sure the ADB driver is installed.</li>
<li><b>Manage apps</b> – in the “APK” tab you can install, uninstall or launch an app by specifying its package.</li>
<li><b>Mass installation</b> – the “Mass APK Installation” tab lets you select a folder with many <code>.apk</code> files and install them all at once.</li>
<li><b>File operations</b> – the “Files” tab lets you push/pull files using <code>adb push / pull</code>.</li>
<li><b>App testing</b> – the “App Testing” tab runs each app, collects <code>logcat</code> and marks apps that crashed.</li>
<li><b>Screen casting and screenshots</b> – the “Device Screen” tab can start <code>scrcpy</code> (if installed) or take a screenshot.</li>
<li><b>Backups</b> – the “Backup / Restore” tab creates a full ADB backup and can restore it.</li>
</ol>

<hr>

<h2>🔧  How to write your own plugins for xHelper</h2>
<p>A plugin is a regular <b>Python module</b> placed in the <code>plugins/</code> folder next to <code>main.py</code>. When the program starts, <code>XHelperMainWindow.load_plugins()</code> automatically imports every <code>*.py</code>, looks for a <code>register(main_window)</code> function and calls it, passing the main window object.</p>

<p>Minimal plugin template:</p>

<pre><code># plugins/example.py
# -*- coding: utf-8 -*-

def register(main_window):
    from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.addWidget(QLabel("Example plugin"))
    main_window.tabs.addTab(tab, "Example")
</code></pre>

<p>Inside <code>register</code> you have access to:</p>
<ul>
<li><code>main_window.run_adb_command(...)</code> – execute any ADB command.</li>
