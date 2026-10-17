"""Pure unit tests for Chrome scheduling and input safety.

Windows Task Scheduler is integration-tested manually on a signed-in Windows PC.
"""
import unittest
from pathlib import Path
from unittest.mock import patch

from browser_schedule import (
    TASK_NAME, normalize_url, registration_script, install_chrome_task,
    remove_chrome_task, open_chrome_now, chrome_settings_page, chrome_launch_args,
)


class BrowserScheduleTests(unittest.TestCase):
    def test_normalizes_plain_domain_to_https(self):
        self.assertEqual(normalize_url(" example.org/watch?part=1&play=yes "),
                         "https://example.org/watch?part=1&play=yes")

    def test_preserves_explicit_https(self):
        self.assertEqual(normalize_url("https://www.example.com/sermon"),
                         "https://www.example.com/sermon")

    def test_disallows_unsafe_urls_and_parameters(self):
        bad = (
            "javascript:alert(1)", "file:///C:/Windows/system.ini",
            "--incognito", "https://ok.example/\nexploit",
            'https://ok.example/" --disable-web-security',
            "https://user:pass@example.org/", "https://example.org:broken",
            "https://exam ple.org", "ftp://example.org/",
            "https://", "",
        )
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_url(value)

    def test_registration_script_contains_hour_and_logged_on_principal(self):
        script = registration_script(
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            "https://example.org/watch?v=1&list=2", 6, 45
        )
        self.assertIn("New-ScheduledTaskTrigger -Daily", script)
        self.assertIn("AddHours(6).AddMinutes(45)", script)
        self.assertIn("-LogonType Interactive", script)
        self.assertIn("New-ScheduledTaskSettingsSet -WakeToRun", script)
        self.assertIn("Chrome Website", script)
        self.assertIn('--new-window "https://example.org/watch?v=1&list=2"', script)

    def test_ps_quote_prevents_interpolation(self):
        script = registration_script(
            Path(r"C:\Users\O'Neil\chrome.exe"),
            "https://example.com/o'neil?test=1", 7, 1
        )
        self.assertIn(r"C:\Users\O''Neil\chrome.exe", script)
        self.assertIn("example.com/o''neil", script)

    @patch("browser_schedule._powershell", return_value=(True, ""))
    @patch("browser_schedule.find_chrome", return_value=Path(r"C:\Chrome\chrome.exe"))
    def test_registers_without_launching_the_application(self, _chrome, shell):
        ok, status = install_chrome_task("dhamma.example.com/audio", 5, 30)
        self.assertTrue(ok)
        self.assertIn("05:30", status)
        script = shell.call_args.args[0]
        self.assertIn("Register-ScheduledTask", script)
        self.assertNotIn("DhammaMorning.exe", script)

    @patch("browser_schedule._powershell", return_value=(True, ""))
    def test_unregistration(self, shell):
        ok, _ = remove_chrome_task()
        self.assertTrue(ok)
        self.assertIn("Unregister-ScheduledTask", shell.call_args.args[0])

    @patch("browser_schedule.find_chrome", return_value=None)
    def test_missing_chrome_reported(self, _chrome):
        ok, message = open_chrome_now("https://example.com")
        self.assertFalse(ok)
        self.assertIn("not found", message)

    def test_experimental_autoplay_is_explicit_and_isolated(self):
        normal = registration_script(Path(r"C:\\Chrome\\chrome.exe"),
                                     "https://example.org/sermon", 6, 0)
        self.assertNotIn("--autoplay-policy=", normal)
        enabled = registration_script(Path(r"C:\\Chrome\\chrome.exe"),
                                      "https://example.org/sermon", 6, 0, True)
        self.assertIn("--autoplay-policy=no-user-gesture-required", enabled)
        self.assertIn("--user-data-dir=", enabled)
        self.assertIn("ChromeAudioProfile", enabled)
        self.assertIn('--new-window "https://example.org/sermon"', enabled)

    def test_chrome_args_never_change_the_normal_profile(self):
        self.assertEqual(chrome_launch_args("https://example.com"),
                         ["--new-window", "https://example.com"])
        separate = chrome_launch_args("https://example.com", True)
        self.assertTrue(separate[0].startswith("--user-data-dir="))
        self.assertIn("ChromeAudioProfile", separate[0])
        self.assertIn("--autoplay-policy=no-user-gesture-required", separate)

    @patch("browser_schedule.find_chrome", return_value=Path(r"C:\\Chrome\\chrome.exe"))
    @patch("browser_schedule.subprocess.Popen")
    def test_sound_settings_are_opened_with_opt_in_profile(self, popen, _chrome):
        ok, _ = chrome_settings_page("sound", True)
        self.assertTrue(ok)
        args = popen.call_args.args[0]
        self.assertIn("chrome://settings/content/sound", args)
        self.assertIn("--autoplay-policy=no-user-gesture-required", args)

    def test_settings_page_uses_only_known_routes(self):
        ok, _ = chrome_settings_page("chrome://evil/test")
        self.assertFalse(ok)

    def test_time_validation(self):
        for hour, minute in ((24, 0), (-1, 0), (5, 60)):
            with self.assertRaises(ValueError):
                registration_script(Path("chrome.exe"), "https://example.com", hour, minute)


if __name__ == "__main__":
    unittest.main()
