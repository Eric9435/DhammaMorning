"""Register a daily Chrome URL launch from within the Dhamma Morning Windows app.

Uses the Windows Task Scheduler so the user never needs to open Task Scheduler.
The task launches chrome.exe directly (no hidden Dhamma Morning process needed).
The Windows account must be signed in, and the PC must be awake/wakeable.
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

TASK_NAME = "DhammaMorning Chrome Website"


def normalize_url(raw: str) -> str:
    """Accept only ordinary HTTP(S) URLs; never execute browser flags or scripts."""
    value = raw.strip()
    if not value:
        raise ValueError("Enter a website URL before enabling the schedule.")
    if len(value) > 2048 or any(ord(c) < 32 or c.isspace() or c in '"\\' for c in value):
        raise ValueError("The website address has unsupported characters.")
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError("Use a valid https:// or http:// website URL.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Do not include a username or password in the URL.")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid website port.") from exc
    if parsed.hostname.startswith("-") or "." not in parsed.hostname and parsed.hostname != "localhost":
        raise ValueError("Enter the full website domain, e.g. https://example.com.")
    return value


def find_chrome() -> Path | None:
    """Find the actual chrome.exe, preferring the registered Windows installation."""
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                    value, _ = winreg.QueryValueEx(key, "")
                    if value and Path(value).is_file():
                        return Path(value)
            except OSError:
                continue
    except ImportError:
        pass
    roots = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    for root in roots:
        if root:
            candidate = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if candidate.is_file():
                return candidate
    chrome = shutil.which("chrome.exe")
    return Path(chrome) if chrome else None


def _ps_literal(value: str) -> str:
    """Single-quoted PowerShell string without interpolation or code execution."""
    return "'" + value.replace("'", "''") + "'"


def registration_script(chrome: Path, url: str, hour: int, minute: int) -> str:
    """Safe script for Windows ScheduledTasks. Runs only in the signed-in desktop."""
    value = normalize_url(url)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Choose a valid start time.")
    # Quoted URL is passed as a *Chrome argument*, not an executable command.
    arguments = '--new-window "' + value + '"'
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$action = New-ScheduledTaskAction -Execute " + _ps_literal(str(chrome))
        + " -Argument " + _ps_literal(arguments),
        "$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours("
        + str(hour) + ").AddMinutes(" + str(minute) + "))",
        "$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable "
        "-MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0)",
        "$principal = New-ScheduledTaskPrincipal -UserId "
        "([Security.Principal.WindowsIdentity]::GetCurrent().Name) "
        "-LogonType Interactive -RunLevel Limited",
        "Register-ScheduledTask -TaskName " + _ps_literal(TASK_NAME)
        + " -Action $action -Trigger $trigger -Principal $principal "
        "-Settings $settings -Description "
        + _ps_literal("Open a Dhamma website in Google Chrome at the selected time. "
                      "Managed by Dhamma Morning.") + " -Force | Out-Null",
    ])


def _powershell(script: str) -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Scheduled website launch requires Windows."
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
             "Bypass", "-EncodedCommand", encoded],
            capture_output=True, text=True, errors="replace", timeout=35,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Windows Task Scheduler could not be reached: {exc}"
    if result.returncode:
        message = (result.stderr or result.stdout or "Task Scheduler rejected the request.").strip()
        return False, message[:450]
    return True, ""


def install_chrome_task(url: str, hour: int, minute: int) -> tuple[bool, str]:
    try:
        address = normalize_url(url)
        chrome = find_chrome()
        if chrome is None:
            return False, "Google Chrome was not found. Please install Chrome first."
        script = registration_script(chrome, address, hour, minute)
    except ValueError as exc:
        return False, str(exc)
    ok, detail = _powershell(script)
    if not ok:
        return False, "Unable to register the Chrome schedule: " + detail
    return True, "Chrome website scheduled daily at {:02d}:{:02d}.".format(hour, minute)


def remove_chrome_task() -> tuple[bool, str]:
    # A missing task is not an error when switching the schedule off.
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$task = Get-ScheduledTask -TaskName " + _ps_literal(TASK_NAME)
        + " -ErrorAction SilentlyContinue\n"
        "if ($null -ne $task) { "
        "Unregister-ScheduledTask -TaskName " + _ps_literal(TASK_NAME)
        + " -Confirm:$false }\n"
    )
    ok, detail = _powershell(script)
    return (True, "Daily Chrome launch disabled.") if ok else (False, detail)


def open_chrome_now(url: str) -> tuple[bool, str]:
    try:
        address = normalize_url(url)
    except ValueError as exc:
        return False, str(exc)
    chrome = find_chrome()
    if not chrome:
        return False, "Google Chrome was not found. Please install Chrome first."
    try:
        subprocess.Popen([str(chrome), "--new-window", address],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as exc:
        return False, f"Could not open Chrome: {exc}"
    return True, "Opening website in Chrome."


def next_website_time(hour: int, minute: int) -> datetime:
    from datetime import timedelta
    now = datetime.now()
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)
