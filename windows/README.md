# Dhamma Morning — Windows Desktop

A dedicated Qt-based MP3 player for morning sermons and chanting. Add local files, set a daily start time, then choose:

- **When MP3 / playlist finishes**: play each track **once**, in order, then stop (default; never loop).
- **At selected clock time**: repeat the playlist until the chosen local stop time, even when it falls after midnight.
- **After chosen duration**: repeat the playlist for a custom **1–1440 minute** limit then stop.

Manual Play and Stop buttons work independently of the daily scheduler. Volume is adjustable; closing the main window keeps the app in the system tray if playback or scheduling is enabled. Settings are under `%APPDATA%\DhammaMorning\settings.json` and MP3 files are never uploaded.

### Run

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r windows\requirements.txt
python -m unittest discover -s windows -p 'test_*.py' -v
python windows\app.py
```

### Package an EXE

```powershell
pip install -r windows\requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name DhammaMorning windows\app.py
```

Or use the standalone `.github/workflows/windows.yml` from a **dedicated new repo**. A compiled EXE needs Windows and the Qt multimedia decoding components. Windows may warn about unsigned developer executables. Test speakers, Windows media codec support, and a one-minute schedule before use. The app cannot wake a sleeping or powered-off PC; enable Startup at Login so the scheduler launches with Windows when signed in. No microphone is used.
