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

Desktop PySide6 / QtMultimedia GUI with local file picker, playlist ordering, time scheduling, **three stop modes**, adjustable volume, and system-tray controls. The local MP3 scheduler requires Dhamma Morning to remain running (possibly minimized to the system tray). You can optionally enable launch at Windows sign-in.

### Automatically open a Chrome website every day

Configure **Daily website in Google Chrome** entirely within the Dhamma Morning Windows app:

1. Enter your website address (HTTPS is used automatically when omitted).
2. Choose a daily clock time.
3. Check **Automatically open this URL in Chrome at the selected time**.
4. Click **Save website schedule**. Use **Open in Chrome now** to test the URL immediately.

The app registers or removes its own ordinary **Windows Task Scheduler** task on your behalf. You do not need to open Task Scheduler. The task launches **Chrome directly**, even when the Dhamma Morning app is closed. However, Windows must remain **powered on and your user signed in**. For sleep, the task requests wake permission but PC hardware and wake timer settings control whether wake succeeds. When the scheduled time is missed, Windows may open Chrome after the user becomes available.

### Chrome Sound & Auto-Play Setup dialog

On first enabling a website schedule (or launching a previously scheduled app for the first time after this update), Dhamma Morning displays a guided Chrome audio setup dialog. You can reopen it with **Chrome Sound / Auto-Play Setup**:

1. **Open Chrome Sound Settings**: Navigate to `chrome://settings/content/sound` in the relevant Chrome profile, then review and allow website sound yourself.
2. **Open Chrome Site Permissions** and review sound permission for the Dhamma domain.
3. **Open Website & Test Sound**: Start playback manually on the website at least once.
4. Optionally tick **Try automatic audio playback (experimental, separate Chrome profile)**, then **Save Chrome Audio Setup**. The Windows scheduled task is updated with an *isolated* Chrome profile and the experimental Chromium startup option `--autoplay-policy=no-user-gesture-required`. This option is an opt-in attempt, not an operating-system or Chrome permission grant. Some Chrome versions and websites may ignore it. Only browse trusted sites using the separate profile; it can allow sound to autoplay without a click. The normal Chrome profile, bookmarks, permissions and login sessions are not modified or shared.

**Limitations:** The app cannot silently click Allow in Chrome or force an arbitrary webpage to implement audio autoplay. The **Sound Allow** setting does not itself guarantee **autoplay with sound**. Chrome may block playback depending on the site's code, whether the visitor has previously interacted with the domain, and browser policies. The website schedule and local MP3 playback schedule are independent; neither automatically stops or closes the other.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r windows\requirements.txt
python windows\app.py
```

Run `windows/build.ps1` or `.github/workflows/windows.yml` to produce a portable `DhammaMorning.exe` on Windows. Python unit tests are located at `windows/test_playback_logic.py`.

## GitHub repository

The dedicated, standalone GitHub repository is [Eric9435/DhammaMorning](https://github.com/Eric9435/DhammaMorning). GitHub Actions builds separate Android APK and Windows EXE artifacts. This project is completely separate from EricPDF.

## Notes and boundaries

- User supplies their own local MP3/audio files; sample religious audio is not bundled.
- Windows local MP3 playback requires the Dhamma Morning process running; website opening uses a separately registered Windows task. Neither scheduled action runs on a PC that is shut down. Android scheduled playback can be affected by alarm permission, battery restrictions, reboot behavior and vendor firmware.
- Scheduled daily start time and stop-clock are based on the **device's local time zone**.
- GitHub Actions builds APK and EXE artifacts. Automated tests validate timing and input safety, but overnight playback and Chrome autoplay must still be tested on a real device/PC.
- Each platform stores its own local settings; there is **no cross-device synchronization**.

Developed by **innovateX** · Dhamma Morning.
