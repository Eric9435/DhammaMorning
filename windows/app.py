"""Dhamma Morning — standalone, local-only daily audio playback for Windows."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from playback_logic import next_occurrence, should_stop_at_playlist_end, duration_clock
from browser_schedule import (install_chrome_task, remove_chrome_task, open_chrome_now,
                              next_website_time, normalize_url, chrome_settings_page)
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtGui import QAction, QPalette, QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton,
    QSlider, QSystemTrayIcon, QTimeEdit, QVBoxLayout, QWidget, QCheckBox, QSpinBox, QScrollArea,
    QStyle, QLineEdit, QDialog,
)

APP_NAME = "Dhamma Morning"
APP_ID = "innovateX.DhammaMorning"
DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "DhammaMorning"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "settings.json"
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
DURATIONS = ((15, "15 minutes"), (30, "30 minutes"), (60, "1 hour"), (120, "2 hours"),
             (180, "3 hours"), (240, "4 hours"), (360, "6 hours"), (480, "8 hours"))
STOP_MODES = (("end_of_playlist", "When MP3 / playlist finishes"),
              ("clock", "At selected clock time"),
              ("duration", "After chosen duration"))


def default_settings() -> dict:
    return {
        "paths": [], "hour": 6, "minute": 0, "duration_minutes": 60,
        "stop_mode": "end_of_playlist", "stop_hour": 7, "stop_minute": 0,
        "enabled": False, "volume": 70, "autostart": False,
        "website_enabled": False, "website_url": "", "website_hour": 6, "website_minute": 0,
        "chrome_audio_mode": False, "chrome_setup_seen": False,
    }


def load_settings() -> dict:
    data = default_settings()
    try:
        stored = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in data})
    except (FileNotFoundError, ValueError, OSError):
        pass
    return data


def save_settings(config: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, CONFIG_FILE)


def startup_script_path() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "DhammaMorning.cmd"


def set_startup(enabled: bool) -> tuple[bool, str]:
    try:
        target = startup_script_path()
        if not enabled:
            target.unlink(missing_ok=True)
            return True, "Disabled launch at Windows sign-in"
        if not getattr(sys, "frozen", False):
            return False, "Startup registration requires the packaged Windows EXE."
        # Windows start command expects a window title in the first pair of quotes.
        command = f'@echo off\r\nstart "" "{sys.executable}"\r\n'
        target.write_text(command, encoding="utf-8")
        return True, "Will open at Windows sign-in"
    except Exception as exc:
        return False, f"Unable to update Startup: {exc}"


class DhammaWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_settings()
        self.paths: list[str] = [str(x) for x in self.config.get("paths", []) if Path(str(x)).is_file()]
        self.playing = False
        self.track_index = 0
        self.consecutive_errors = 0
        self.started_mono = 0.0
        self.stop_after = 60 * 60
        self.stop_at: datetime | None = None
        self.active_stop_mode = "end_of_playlist"
        self.next_alarm: datetime | None = None
        self.quitting = False
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.player.errorOccurred.connect(self._media_error)

        self.setWindowTitle("Dhamma Morning · Mindful Audio Scheduler")
        self.resize(860, 745)
        self.setMinimumSize(660, 540)
        self._create_layout()
        self._create_tray()
        self._restore_form()
        self._apply_schedule()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(500)
        if self.config.get("website_enabled", False) and not self.config.get("chrome_setup_seen", False):
            QTimer.singleShot(350, self._chrome_setup)

    def _create_layout(self) -> None:
        body = QWidget()
        body.setObjectName("root")
        outer = QVBoxLayout(body)
        outer.setContentsMargins(26, 22, 26, 20)
        outer.setSpacing(14)
        eyebrow = QLabel("DHAMMA MORNING  /  BY innovateX")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)
        title = QLabel("Wake up to Dhamma")
        title.setObjectName("title")
        outer.addWidget(title)
        subtitle = QLabel("Schedule local MP3 playback or automatically open a website in Google Chrome.")
        subtitle.setObjectName("sub")
        outer.addWidget(subtitle)

        schedule = self._card("Morning routine")
        form = QFormLayout()
        form.setSpacing(11)
        self.time_field = QTimeEdit()
        self.time_field.setDisplayFormat("hh:mm AP")
        self.time_field.timeChanged.connect(self._save_form)
        form.addRow("Daily start", self.time_field)
        self.stop_mode_field = QComboBox()
        for value, label in STOP_MODES:
            self.stop_mode_field.addItem(label, userData=value)
        self.stop_mode_field.currentIndexChanged.connect(self._stop_mode_changed)
        form.addRow("Stop playback", self.stop_mode_field)
        self.duration_field = QSpinBox()
        self.duration_field.setRange(1, 1440)
        self.duration_field.setSuffix(" minutes")
        self.duration_field.valueChanged.connect(self._save_form)
        form.addRow("Time limit", self.duration_field)
        self.end_time_field = QTimeEdit()
        self.end_time_field.setDisplayFormat("hh:mm AP")
        self.end_time_field.timeChanged.connect(self._save_form)
        form.addRow("Stop at", self.end_time_field)
        self.mode_hint = QLabel("One MP3: play once, then stop. Multiple tracks: play once each, then stop.")
        self.mode_hint.setObjectName("hint")
        self.mode_hint.setWordWrap(True)
        schedule.addWidget(self.mode_hint)
        schedule.addLayout(form)
        enabled_row = QHBoxLayout()
        self.enabled_field = QCheckBox("Enable every-morning playback")
        self.enabled_field.toggled.connect(self._schedule_toggled)
        enabled_row.addWidget(self.enabled_field)
        enabled_row.addStretch()
        schedule.addLayout(enabled_row)
        self.next_label = QLabel("Schedule disabled")
        self.next_label.setObjectName("hint")
        schedule.addWidget(self.next_label)
        outer.addWidget(schedule.parentWidget())


        # Website scheduling is independent of the MP3 timer above.
        browser = self._card("Daily website in Google Chrome")
        browser_form = QFormLayout()
        browser_form.setSpacing(11)
        self.website_url_field = QLineEdit()
        self.website_url_field.setPlaceholderText("https://example.com/dhamma")
        self.website_url_field.setClearButtonEnabled(True)
        self.website_url_field.editingFinished.connect(self._website_form_changed)
        browser_form.addRow("Website URL", self.website_url_field)
        self.website_time_field = QTimeEdit()
        self.website_time_field.setDisplayFormat("hh:mm AP")
        self.website_time_field.timeChanged.connect(self._website_form_changed)
        browser_form.addRow("Open every day", self.website_time_field)
        browser.addLayout(browser_form)
        self.website_enabled_field = QCheckBox(
            "Automatically open this URL in Chrome at the selected time"
        )
        self.website_enabled_field.toggled.connect(self._website_toggle)
        browser.addWidget(self.website_enabled_field)
        website_buttons = QHBoxLayout()
        self.website_save_button = QPushButton("Save website schedule")
        self.website_save_button.setObjectName("accent")
        self.website_save_button.clicked.connect(self._website_apply)
        website_buttons.addWidget(self.website_save_button)
        self.website_open_button = QPushButton("Open in Chrome now")
        self.website_open_button.clicked.connect(self._website_open_now)
        website_buttons.addWidget(self.website_open_button)
        browser.addLayout(website_buttons)
        self.chrome_setup_button = QPushButton("Chrome Sound / Auto-Play Setup")
        self.chrome_setup_button.clicked.connect(self._chrome_setup)
        browser.addWidget(self.chrome_setup_button)
        self.website_status = QLabel("Set a URL and enable daily automatic Chrome opening.")
        self.website_status.setObjectName("hint")
        self.website_status.setWordWrap(True)
        browser.addWidget(self.website_status)
        self.website_note = QLabel(
            "The app sets up Windows scheduling for you. Chrome can open while "
            "Dhamma Morning is closed, provided your Windows user is signed in and "
            "the PC is awake/wakeable. Use Chrome Sound / Auto-Play Setup to "
            "review audio permission. Website autoplay is not guaranteed."
        )
        self.website_note.setObjectName("hint")
        self.website_note.setWordWrap(True)
        browser.addWidget(self.website_note)
        outer.addWidget(browser.parentWidget())

        lib = self._card("Your Dhamma audio")
        row = QHBoxLayout()
        self.add_button = QPushButton("+ Add MP3 / audio")
        self.add_button.clicked.connect(self._add_audio)
        row.addWidget(self.add_button)
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.clicked.connect(self._remove_audio)
        row.addWidget(self.remove_button)
        self.up_button = QPushButton("Move up")
        self.up_button.clicked.connect(lambda: self._move(-1))
        row.addWidget(self.up_button)
        self.down_button = QPushButton("Move down")
        self.down_button.clicked.connect(lambda: self._move(1))
        row.addWidget(self.down_button)
        lib.addLayout(row)
        self.playlist = QListWidget()
        self.playlist.setMinimumHeight(105)
        self.playlist.setMaximumHeight(165)
        lib.addWidget(self.playlist)
        outer.addWidget(lib.parentWidget())

        playback = self._card("Playback")
        action_row = QHBoxLayout()
        self.start_button = QPushButton("▶  Play now")
        self.start_button.setObjectName("accent")
        self.start_button.clicked.connect(self._toggle_play)
        action_row.addWidget(self.start_button)
        self.stop_button = QPushButton("■ Stop")
        self.stop_button.clicked.connect(self._stop)
        action_row.addWidget(self.stop_button)
        playback.addLayout(action_row)
        vol = QHBoxLayout()
        vol.addWidget(QLabel("Media volume"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        vol.addWidget(self.volume_slider)
        self.volume_value = QLabel("70%")
        vol.addWidget(self.volume_value)
        playback.addLayout(vol)
        self.playing_label = QLabel("Not playing")
        playback.addWidget(self.playing_label)
        outer.addWidget(playback.parentWidget())

        self.autostart_box = QCheckBox("Launch Dhamma Morning when I sign in to Windows")
        self.autostart_box.toggled.connect(self._startup_changed)
        outer.addWidget(self.autostart_box)
        self.status = QLabel("Local-only audio · No microphone · No AI or account")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        outer.addStretch()
        scroll = QScrollArea(self)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        self.setStyleSheet("""
            /* Explicit text color is essential when Windows is in dark mode.
               System palette text was white on custom light controls previously. */
            QMainWindow, QWidget#root, QScrollArea {
                background-color: #F5F7F4; color: #173047;
            }
            QScrollArea { border: none; }
            QLabel, QCheckBox, QRadioButton {
                color: #173047; background: transparent;
            }
            QLabel#title { font-size:31px; font-weight:750; color:#173047; }
            QLabel#eyebrow { font-size:11px; font-weight:700; color:#2D8278; }
            QLabel#sub { color:#526779; font-size:13px; }
            QLabel#hint { color:#43586A; font-size:12px; }
            QLabel#section { font-size:16px; font-weight:700; color:#173047; }
            QFrame#card {
                background-color:#FFFFFF;
                border:1px solid #DCE6E4; border-radius:14px;
            }
            QFrame#card QLabel, QFrame#card QCheckBox {
                background:transparent; border:none;
            }
            QPushButton {
                padding:9px 12px; border-radius:8px;
                background-color:#EAF0EF; border:1px solid #D7E4E2;
                font-weight:650; color:#173047;
            }
            QPushButton:hover { background-color:#DCEDE9; color:#173047; }
            QPushButton:disabled { color:#5E7081; background-color:#F2F4F4; }
            QPushButton#accent {
                background-color:#296F67; color:#FFFFFF; border:none;
            }
            QPushButton#accent:hover { background-color:#20564F; color:#FFFFFF; }
            QLineEdit, QTimeEdit, QComboBox, QSpinBox, QListWidget {
                color:#173047; background-color:#FFFFFF;
                border:1px solid #B9CCC9; border-radius:8px;
                padding:6px;
                selection-color:#FFFFFF; selection-background-color:#296F67;
            }
            QLineEdit:disabled, QTimeEdit:disabled,
            QComboBox:disabled, QSpinBox:disabled {
                color:#586D7D; background-color:#F0F3F3;
            }
            QLineEdit[placeholderText] { placeholder-text-color:#60788B; }
            QComboBox QAbstractItemView {
                color:#173047; background-color:#FFFFFF;
                selection-color:#FFFFFF; selection-background-color:#296F67;
            }
            QListWidget::item { color:#173047; }
            QListWidget::item:selected { color:#FFFFFF; background:#296F67; }
            QScrollBar:vertical { background:#ECF1F0; width:12px; }
            QScrollBar::handle:vertical {
                background:#A5B7B6; border-radius:5px; min-height:28px;
            }
        """)

    def _card(self, title: str) -> QVBoxLayout:
        # Each card owns its vertical layout; callers place the frame into the root layout.
        frame = QFrame(self)
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 12, 15, 14)
        layout.setSpacing(10)
        section = QLabel(title)
        section.setObjectName("section")
        layout.addWidget(section)
        if not hasattr(self, "_cards"):
            self._cards = []
        self._cards.append(frame)
        return layout

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        menu = QMenu()
        show = QAction("Open Dhamma Morning", self)
        show.triggered.connect(self.showNormal)
        menu.addAction(show)
        stop = QAction("Stop audio", self)
        stop.triggered.connect(self._stop)
        menu.addAction(stop)
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self._exit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.showNormal()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _restore_form(self) -> None:
        from PySide6.QtCore import QTime
        self.time_field.blockSignals(True)
        self.duration_field.blockSignals(True)
        self.stop_mode_field.blockSignals(True)
        self.end_time_field.blockSignals(True)
        self.enabled_field.blockSignals(True)
        self.volume_slider.blockSignals(True)
        self.autostart_box.blockSignals(True)
        self.website_url_field.blockSignals(True)
        self.website_time_field.blockSignals(True)
        self.website_enabled_field.blockSignals(True)
        self.time_field.setTime(QTime(int(self.config["hour"]), int(self.config["minute"])))
        minutes = int(self.config["duration_minutes"])
        self.duration_field.setValue(min(max(minutes, 1), 1440))
        self.stop_mode_field.setCurrentIndex(max(0, self.stop_mode_field.findData(
            str(self.config.get("stop_mode", "end_of_playlist")))))
        self.end_time_field.setTime(QTime(int(self.config.get("stop_hour", 7)),
                                      int(self.config.get("stop_minute", 0))))
        self.enabled_field.setChecked(bool(self.config["enabled"]))
        self.volume_slider.setValue(int(self.config["volume"]))
        self.volume_value.setText(f'{int(self.config["volume"])}%')
        self.audio.setVolume(int(self.config["volume"]) / 100)
        self.autostart_box.setChecked(bool(self.config.get("autostart", False)))
        self.website_url_field.setText(str(self.config.get("website_url", "")))
        self.website_time_field.setTime(QTime(
            int(self.config.get("website_hour", 6)),
            int(self.config.get("website_minute", 0))
        ))
        self.website_enabled_field.setChecked(bool(self.config.get("website_enabled", False)))
        self._refresh_website_status()
        self.playlist.addItems([Path(p).name for p in self.paths])
        self.time_field.blockSignals(False)
        self.duration_field.blockSignals(False)
        self.stop_mode_field.blockSignals(False)
        self.end_time_field.blockSignals(False)
        self.enabled_field.blockSignals(False)
        self._stop_mode_changed()
        self.volume_slider.blockSignals(False)
        self.autostart_box.blockSignals(False)
        self.website_url_field.blockSignals(False)
        self.website_time_field.blockSignals(False)
        self.website_enabled_field.blockSignals(False)

    def _stop_mode_changed(self, *_unused) -> None:
        mode = self.stop_mode_field.currentData() or "end_of_playlist"
        self.duration_field.setEnabled(mode == "duration")
        self.end_time_field.setEnabled(mode == "clock")
        if mode == "end_of_playlist":
            self.mode_hint.setText("Play every selected MP3 once, then stop automatically. No looping.")
        elif mode == "clock":
            self.mode_hint.setText("Repeat the playlist until the selected stop time, including after midnight.")
        else:
            self.mode_hint.setText("Repeat the playlist until your selected time limit expires.")
        self._save_form()

    def _save_form(self, *_unused) -> None:
        self.config.update({
            "hour": self.time_field.time().hour(),
            "minute": self.time_field.time().minute(),
            "duration_minutes": int(self.duration_field.value()),
            "stop_mode": str(self.stop_mode_field.currentData() or "end_of_playlist"),
            "stop_hour": self.end_time_field.time().hour(),
            "stop_minute": self.end_time_field.time().minute(),
            "paths": self.paths,
            "enabled": bool(self.enabled_field.isChecked()),
            "volume": self.volume_slider.value(),
        })
        save_settings(self.config)
        self._apply_schedule()

    def _apply_schedule(self) -> None:
        if self.config["enabled"] and self.paths:
            self.next_alarm = next_occurrence(int(self.config["hour"]), int(self.config["minute"]))
            self.next_label.setText(f'Next playback: {self.next_alarm:%a, %d %b %Y, %I:%M %p}')
        elif self.config["enabled"]:
            self.next_alarm = None
            self.next_label.setText("Add audio files to activate the daily schedule")
        else:
            self.next_alarm = None
            self.next_label.setText("Schedule disabled")

    def _schedule_toggled(self, value: bool) -> None:
        if value and not self.paths:
            QMessageBox.information(self, "Choose Dhamma audio", "Add one or more audio files before enabling the schedule.")
            self.enabled_field.blockSignals(True)
            self.enabled_field.setChecked(False)
            self.enabled_field.blockSignals(False)
        self._save_form()


    def _refresh_website_status(self) -> None:
        if self.config.get("website_enabled", False):
            target = next_website_time(
                int(self.config.get("website_hour", 6)),
                int(self.config.get("website_minute", 0))
            )
            experimental = bool(self.config.get("chrome_audio_mode", False))
            audio_label = " · Experimental audio attempt enabled" if experimental else ""
            self.website_status.setText(
                f"Windows task registered · Next Chrome launch: {target:%a, %d %b, %I:%M %p}"
                + audio_label
            )
        else:
            self.website_status.setText("Automatic website opening is disabled.")

    def _website_form_changed(self, *_unused) -> None:
        if self.website_enabled_field.isChecked():
            self.website_status.setText(
                "Unsaved changes · Click Save website schedule to update the Windows task."
            )
        else:
            self.website_status.setText("Click Save website schedule to register this URL.")

    def _website_toggle(self, *_unused) -> None:
        self._website_apply()

    def _website_apply(self, *_unused) -> None:
        enabled = self.website_enabled_field.isChecked()
        hour = self.website_time_field.time().hour()
        minute = self.website_time_field.time().minute()
        url = self.website_url_field.text().strip()
        if enabled:
            ok, message = install_chrome_task(
                url, hour, minute, bool(self.config.get("chrome_audio_mode", False))
            )
        else:
            ok, message = remove_chrome_task()
        if not ok:
            self.website_status.setText(message)
            QMessageBox.warning(self, "Chrome schedule could not be saved", message)
            previous = bool(self.config.get("website_enabled", False))
            self.website_enabled_field.blockSignals(True)
            self.website_enabled_field.setChecked(previous)
            self.website_enabled_field.blockSignals(False)
            return
        if enabled:
            # Save normalized address, without changing the target scheduled task.
            url = normalize_url(url)
            self.website_url_field.blockSignals(True)
            self.website_url_field.setText(url)
            self.website_url_field.blockSignals(False)
        self.config.update({
            "website_url": url,
            "website_hour": hour,
            "website_minute": minute,
            "website_enabled": enabled,
        })
        save_settings(self.config)
        self._refresh_website_status()
        self.status.setText(message)
        if enabled and not self.config.get("chrome_setup_seen", False):
            QTimer.singleShot(0, self._chrome_setup)

    def _website_open_now(self) -> None:
        ok, message = open_chrome_now(
            self.website_url_field.text(),
            bool(self.config.get("chrome_audio_mode", False))
        )
        self.website_status.setText(message)
        if not ok:
            QMessageBox.warning(self, "Chrome could not open", message)


    def _chrome_setup(self) -> None:
        """Guided site-audio setup; never silently changes the user's Chrome settings."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Chrome Sound & Automatic Website Audio")
        dialog.setMinimumWidth(570)
        dialog.setModal(True)
        outer = QVBoxLayout(dialog)
        outer.setSpacing(13)

        title = QLabel("Prepare Chrome for morning Dhamma audio")
        title.setStyleSheet("font-size:19px; font-weight:700; color:#173047")
        outer.addWidget(title)

        intro = QLabel(
            "Dhamma Morning can open Chrome settings, but only you can grant site permissions. "
            "Chrome Sound permission is separate from audible autoplay. Follow these steps:"
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        step_one = QLabel(
            "1. Open Chrome Sound Settings. Make sure websites can play sound. "
            "If your Dhamma website is muted, allow sound for that site."
        )
        step_one.setWordWrap(True)
        outer.addWidget(step_one)
        sound_button = QPushButton("Open Chrome Sound Settings")
        outer.addWidget(sound_button)
        site_button = QPushButton("Open Chrome Site Permissions")
        outer.addWidget(site_button)

        step_two = QLabel(
            "2. Open your Dhamma website in Chrome. Use the icon next to the address "
            "to review Site Settings > Sound. Click Play on the page and listen at "
            "least once. Website behaviour varies."
        )
        step_two.setWordWrap(True)
        outer.addWidget(step_two)
        website_button = QPushButton("Open Website & Test Sound")
        outer.addWidget(website_button)

        guide = QLabel(
            "3. Optional: attempt unattended audio autoplay. This launches the "
            "scheduled website in a separate Chrome profile with an experimental "
            "autoplay option. It does not modify your regular Chrome profile or "
            "silently grant permissions. The website must still support automatic "
            "playback. Some Chrome versions may ignore this option."
        )
        guide.setWordWrap(True)
        outer.addWidget(guide)

        experimental = QCheckBox(
            "Try automatic audio playback (experimental, separate Chrome profile)"
        )
        experimental.setChecked(bool(self.config.get("chrome_audio_mode", False)))
        experimental.setToolTip(
            "The separate Chrome profile may allow site audio without a click. "
            "Only use that profile for trusted Dhamma websites."
        )
        outer.addWidget(experimental)

        warning = QLabel(
            "CAUTION: Audio from any page opened in the separate profile may "
            "play without a click. Use only trusted sites. Existing Chrome "
            "bookmarks and logins are not automatically shared with that profile."
        )
        warning.setStyleSheet("color:#8A5B31")
        warning.setWordWrap(True)
        outer.addWidget(warning)

        response = QLabel("Permissions are not changed automatically.")
        response.setWordWrap(True)
        outer.addWidget(response)

        def do_sound() -> None:
            ok, message = chrome_settings_page("sound", experimental.isChecked())
            response.setText(message)
            if not ok:
                QMessageBox.warning(dialog, "Chrome settings", message)

        def do_website() -> None:
            ok, message = open_chrome_now(self.website_url_field.text(),
                                          experimental.isChecked())
            response.setText(message)
            if not ok:
                QMessageBox.warning(dialog, "Chrome website", message)

        sound_button.clicked.connect(do_sound)
        site_button.clicked.connect(
            lambda: response.setText(
                chrome_settings_page("sites", experimental.isChecked())[1]
            )
        )
        website_button.clicked.connect(do_website)

        controls = QHBoxLayout()
        close_button = QPushButton("Later")
        close_button.clicked.connect(dialog.reject)
        controls.addWidget(close_button)
        controls.addStretch()
        save_button = QPushButton("Save Chrome Audio Setup")
        save_button.setObjectName("accent")
        controls.addWidget(save_button)
        outer.addLayout(controls)

        def save_setup() -> None:
            requested = experimental.isChecked()
            enabled = bool(self.config.get("website_enabled", False))
            if enabled and requested != bool(self.config.get("chrome_audio_mode", False)):
                ok, message = install_chrome_task(
                    str(self.config.get("website_url", "")),
                    int(self.config.get("website_hour", 6)),
                    int(self.config.get("website_minute", 0)),
                    requested
                )
                if not ok:
                    response.setText(message)
                    QMessageBox.warning(dialog, "Schedule update failed", message)
                    return
            self.config["chrome_audio_mode"] = requested
            self.config["chrome_setup_seen"] = True
            save_settings(self.config)
            self._refresh_website_status()
            dialog.accept()

        save_button.clicked.connect(save_setup)
        dialog.exec()

    def _refresh_list(self) -> None:
        selection = self.playlist.currentRow()
        self.playlist.clear()
        self.playlist.addItems([Path(p).name for p in self.paths])
        if self.paths:
            self.playlist.setCurrentRow(min(max(selection, 0), len(self.paths) - 1))
        self._save_form()

    def _add_audio(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose local Dhamma talks", str(Path.home()),
            "Audio files (*.mp3 *.m4a *.wav *.aac *.ogg *.flac)"
        )
        for path in paths:
            if Path(path).is_file() and Path(path).suffix.lower() in AUDIO_EXTENSIONS and path not in self.paths:
                self.paths.append(path)
        self._refresh_list()
        if paths:
            self.status.setText(f"Playlist has {len(self.paths)} audio file(s). Files stay on this PC.")

    def _remove_audio(self) -> None:
        row = self.playlist.currentRow()
        if 0 <= row < len(self.paths):
            self.paths.pop(row)
            self._refresh_list()

    def _move(self, offset: int) -> None:
        old = self.playlist.currentRow()
        new = old + offset
        if 0 <= old < len(self.paths) and 0 <= new < len(self.paths):
            self.paths[old], self.paths[new] = self.paths[new], self.paths[old]
            self._refresh_list()
            self.playlist.setCurrentRow(new)

    def _volume_changed(self, value: int) -> None:
        self.audio.setVolume(value / 100)
        self.volume_value.setText(f"{value}%")
        self._save_form()

    def _startup_changed(self, enabled: bool) -> None:
        ok, message = set_startup(enabled)
        self.status.setText(message)
        if not ok:
            self.autostart_box.blockSignals(True)
            self.autostart_box.setChecked(False)
            self.autostart_box.blockSignals(False)
        self.config["autostart"] = ok and enabled
        save_settings(self.config)

    def _toggle_play(self) -> None:
        if self.playing:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        self.paths = [p for p in self.paths if Path(p).is_file()]
        if not self.paths:
            self._refresh_list()
            self.status.setText("No usable files. Add at least one local audio file.")
            return
        self.playing = True
        self.started_mono = time.monotonic()
        self.active_stop_mode = str(self.config.get("stop_mode", "end_of_playlist"))
        self.stop_after = int(self.config["duration_minutes"]) * 60
        if self.active_stop_mode == "clock":
            self.stop_at = next_occurrence(int(self.config["stop_hour"]),
                                           int(self.config["stop_minute"]))
        else:
            self.stop_at = None
        self.track_index = 0
        self.consecutive_errors = 0
        self.start_button.setText("■ Stop playback")
        self._play_next()

    def _play_next(self) -> None:
        if not self.playing:
            return
        if not self.paths or self.consecutive_errors >= len(self.paths):
            self._stop()
            self.status.setText("Unable to decode any audio file. Try MP3 or WAV.")
            return
        if should_stop_at_playlist_end(self.active_stop_mode, self.track_index, len(self.paths)):
            self._stop()
            self.status.setText("MP3 / playlist finished • playback stopped automatically.")
            return
        path = self.paths[self.track_index % len(self.paths)]
        self.track_index += 1
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(Path(path))))
        self.player.play()
        self.playing_label.setText(f"Playing: {Path(path).name}")

    def _media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.playing:
            self.consecutive_errors = 0
            self._play_next()

    def _media_error(self, error: QMediaPlayer.Error, message: str) -> None:
        if error != QMediaPlayer.Error.NoError and self.playing:
            self.consecutive_errors += 1
            self.status.setText(f"Cannot play track: {message or error.name}")
            QTimer.singleShot(50, self._play_next)

    def _stop(self) -> None:
        self.playing = False
        self.player.stop()
        self.playing_label.setText("Not playing")
        self.start_button.setText("▶  Play now")

    def _tick(self) -> None:
        now = datetime.now()
        if self.next_alarm is not None and now >= self.next_alarm:
            # Daily alarm is rescheduled immediately; a missed alarm is not replayed indefinitely.
            self.next_alarm = next_occurrence(int(self.config["hour"]),
                                              int(self.config["minute"]), after=now)
            self.next_label.setText(f'Next playback: {self.next_alarm:%a, %d %b %Y, %I:%M %p}')
            if not self.playing:
                self._start()
        if self.playing:
            elapsed = time.monotonic() - self.started_mono
            if self.active_stop_mode == "duration":
                remaining = max(0.0, self.stop_after - elapsed)
                if remaining <= 0:
                    self._stop()
                    self.status.setText("Selected duration reached • playback stopped.")
                else:
                    self.status.setText(f"Dhamma playing • {duration_clock(remaining)} remaining")
            elif self.active_stop_mode == "clock":
                remaining = (self.stop_at - now).total_seconds() if self.stop_at else 0
                if remaining <= 0:
                    self._stop()
                    self.status.setText("Chosen stop time reached • playback stopped.")
                else:
                    self.status.setText(
                        f"Dhamma playing • auto-stop at {self.stop_at:%I:%M %p}"
                    )
            else:
                self.status.setText(
                    f"Dhamma playing • track {min(self.track_index, len(self.paths))} "
                    f"of {len(self.paths)} • stopping at playlist end"
                )

    def _exit(self) -> None:
        self.quitting = True
        self._stop()
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        if not self.quitting and (self.config["enabled"] or self.playing):
            if QSystemTrayIcon.isSystemTrayAvailable():
                self.hide()
                self.tray.showMessage(
                    "Dhamma Morning is active",
                    "Scheduled audio will play while this app is running and Windows stays awake.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2500,
                )
                event.ignore()
                return
            confirmation = QMessageBox.question(self, "Close audio scheduler?",
                "Closing this application will stop scheduled playback. Exit anyway?")
            if confirmation != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._stop()
        event.accept()
        # Without a scheduled job, exit normally rather than leaving a hidden Qt process.
        QTimer.singleShot(0, QApplication.instance().quit)


def install_light_palette(app: QApplication) -> None:
    """Keep text readable regardless of Windows light/dark system appearance."""
    app.setStyle("Fusion")
    palette = app.palette()
    for role, hex_color in (
        (QPalette.ColorRole.Window, "#F5F7F4"),
        (QPalette.ColorRole.WindowText, "#173047"),
        (QPalette.ColorRole.Base, "#FFFFFF"),
        (QPalette.ColorRole.AlternateBase, "#F3F6F5"),
        (QPalette.ColorRole.Text, "#173047"),
        (QPalette.ColorRole.Button, "#EAF0EF"),
        (QPalette.ColorRole.ButtonText, "#173047"),
        (QPalette.ColorRole.Highlight, "#296F67"),
        (QPalette.ColorRole.HighlightedText, "#FFFFFF"),
        (QPalette.ColorRole.PlaceholderText, "#5E7081"),
    ):
        palette.setColor(role, QColor(hex_color))
    app.setPalette(palette)


def main() -> int:
    app = QApplication(sys.argv)
    install_light_palette(app)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("innovateX")
    app.setQuitOnLastWindowClosed(False)
    win = DhammaWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
