# Build and verification notes — Dhamma Morning v0.2.0

## Scope

Entirely standalone Android and Windows audio playback project. Not an EricPDF extension; existing GitHub repositories were not edited during these changes.

## Verified locally

- Windows app Python syntax: `python -m py_compile windows/app.py windows/playback_logic.py` — passed.
- Windows pure playback logic: 6 `unittest` cases — passed (MP3-once stop, timed repeat, clock across midnight, timing format, etc.).
- Android `PlaybackStopPolicy.kt` Kotlin compilation via local `kotlinc` — passed.
- Android policy standalone smoke checks for MP3 stop, timed repeat and cross-midnight stop clock — 3 passed.
- Project file tree checked for separate Android/Windows GitHub Actions workflows and absence of bundled copyrighted media.

## Still requires CI and real device testing

- Android APK Gradle compilation and instrumentation/physical phone overnight tests — **not run** in this environment (no configured Android SDK/Gradle).
- Windows portable EXE PyInstaller build — **not run** in this Linux environment.
- Exact alarms on Android 12–15 and real speaker/headphone output under screen lock.
- OEM background playback differences and abrupt device restarts.
- Long MP3 and corrupted-media behavior, daylight saving time changes during an active schedule, and Windows sleep/resume.

## Playback semantics

- Default `end_of_playlist` stops at the final MP3 with no looping and no three-hour cutoff.
- `clock` repeats audio until a chosen local wall-clock time.
- `duration` repeats audio for a user-configurable minute limit.
- User-provided music/chant/sermon files remain local. No microphone permissions.

## GitHub

No create-repository operation is available in the linked GitHub connector. **No new remote GitHub repo or release has been published** as part of this ZIP. User must create an empty standalone repo first; upload from extracted ZIP or upload through the GitHub connector after connecting it.
