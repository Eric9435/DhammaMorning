# Dhamma Morning · Auto Audio Player (Android + Windows)

**Independent project** for playing user-selected Dhamma sermons, chanting, or other MP3/audio automatically every morning. No microphone, recording, cloud account, AI API, or streaming server.

**Important:** This project is intentionally **not** part of EricPDF or any other user's existing repository.

## How playback works

1. Pick one or more local MP3, M4A, or WAV tracks.
2. Select **daily start time** (initially 06:00 local device time) and enable the schedule.
3. Choose one of three independent **stop modes**:

| Stop mode | What actually happens |
| --- | --- |
| **When MP3/playlist finishes** *(default)* | Play each selected track **once**, in order. After the final track ends, **stop automatically**. No repeat and no three-hour timer. |
| **At selected clock time** | For example start at 06:00 and **stop at 07:30**. The playlist **repeats as needed** until the chosen local wall-clock time. Clock time can cross midnight. |
| **After chosen duration** | Play for an adjustable number of minutes (e.g. **20, 45, 90, or 180**), repeating the playlist as needed, then stop. There is **no fixed three-hour default**. |

Manual **Play now** and **Stop** also work. The chosen stop mode applies to scheduled and manual playback.

## Android

Native Kotlin/Jetpack Compose, Android API 26+ (Android 8+). Selected local audio URIs and schedule stay on the phone. AlarmManager schedules the next exact RTC wakeup alarm, a broadcast receiver starts the foreground media playback service, and the app re-arms a daily alarm after each fire and after restart/time changes. Exact alarm access may require explicit approval on Android 12+; Android 13+ notification permission allows playback status visibility. Some phone makers' battery policies can still interfere; test with screen off.

To build in Android Studio, open `android/`, install Android SDK platform 35, JDK 17, and Gradle 8.13. Run `:app:assembleDebug :app:testDebugUnitTest`. In a new GitHub repo, `.github/workflows/android.yml` will build an APK artifact when its job succeeds.

## Windows

Desktop PySide6 / QtMultimedia GUI with local file picker, playlist ordering, time scheduling, **three stop modes**, adjustable volume, and system-tray controls. The PC must remain powered on, awake and signed into Windows, with the application running (possibly minimized to tray). Optionally enable startup-at-Windows-login.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r windows\requirements.txt
python windows\app.py
```

Run `windows/build.ps1` or `.github/workflows/windows.yml` to produce a portable `DhammaMorning.exe` on Windows. Python unit tests are located at `windows/test_playback_logic.py`.

## Create the **new, dedicated** GitHub repository

This ChatGPT GitHub connection permits writing to **existing** repositories, but does **not** expose a `create repository` action. Consequently **no GitHub repository has been created or updated** for this package. To publish it as its own project:

1. Sign into GitHub and create a **new empty** repository named `DhammaMorning` (Public or Private is your choice). **Do not** initialize it with a README, `.gitignore`, or license.
2. Extract this ZIP. Open a terminal in the extracted `DhammaMorning` folder and run:

```bash
git init -b main
git add .
git commit -m "Initial Dhamma Morning Android and Windows audio player"
git remote add origin https://github.com/YOUR-USERNAME/DhammaMorning.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub login. With an empty repo created and connected, ChatGPT can also upload the prepared files through the connected GitHub integration. Both platform build workflows run on push and produce artifacts if compilation succeeds.

## Notes and boundaries

- User supplies their own local MP3/audio files; sample religious audio is not bundled.
- Windows playback does not start if the PC is sleeping or off. Android scheduled playback can be affected by alarm permission, battery restrictions, reboot behavior and vendor firmware.
- Scheduled daily start time and stop-clock are based on the **device's local time zone**.
- Source tests passed for basic stop-mode logic; full app builds, device playback, and overnight reliability **are not yet certified**. No installable APK/EXE is claimed to exist in this ZIP.
- Each platform stores its own local settings; there is **no cross-device synchronization**.

Developed by **innovateX** · Dhamma Morning.
