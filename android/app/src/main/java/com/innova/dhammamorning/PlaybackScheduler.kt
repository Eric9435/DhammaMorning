package com.innova.dhammamorning

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import java.text.DateFormat
import java.util.Date
import org.json.JSONArray
import java.util.Calendar

/** Local-only settings: selected audio URIs + daily wakeup schedule. */
object DhammaPreferences {
    private const val NAME = "dhamma_morning_settings"
    private fun pref(c: Context) = c.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    fun tracks(c: Context): List<Uri> = runCatching {
        val array = JSONArray(pref(c).getString("tracks", "[]") ?: "[]")
        (0 until array.length()).map { Uri.parse(array.getString(it)) }
    }.getOrDefault(emptyList())

    fun setTracks(c: Context, uris: List<Uri>) {
        val arr = JSONArray()
        uris.distinct().forEach { arr.put(it.toString()) }
        pref(c).edit().putString("tracks", arr.toString()).apply()
    }


    fun lastEvent(c: Context): String =
        pref(c).getString("lastEvent", "No scheduled alarm has fired yet.") ?: "No event"

    fun event(c: Context, message: String) {
        val whenText = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.MEDIUM)
            .format(Date())
        pref(c).edit().putString("lastEvent", "$whenText - $message").apply()
    }

    fun enabled(c: Context) = pref(c).getBoolean("enabled", false)
    fun hour(c: Context) = pref(c).getInt("hour", 6)
    fun minute(c: Context) = pref(c).getInt("minute", 0)
    fun durationMinutes(c: Context) = pref(c).getInt("durationMinutes", 60).coerceIn(1, 1440)
    fun stopMode(c: Context) = pref(c).getString("stopMode", "end_of_playlist")
        ?.takeIf { it in setOf("duration", "clock", "end_of_playlist") } ?: "end_of_playlist"
    fun stopHour(c: Context) = pref(c).getInt("stopHour", 7).coerceIn(0,23)
    fun stopMinute(c: Context) = pref(c).getInt("stopMinute", 0).coerceIn(0,59)

    fun save(c: Context, enabled: Boolean, hour: Int, minute: Int, duration: Int,
             mode: String, stopHour: Int, stopMinute: Int) {
        require(hour in 0..23 && minute in 0..59 && duration in 1..1440)
        require(mode in setOf("duration", "clock", "end_of_playlist"))
        require(stopHour in 0..23 && stopMinute in 0..59)
        pref(c).edit().putBoolean("enabled", enabled).putInt("hour", hour)
            .putInt("minute", minute).putInt("durationMinutes", duration)
            .putString("stopMode", mode).putInt("stopHour", stopHour)
            .putInt("stopMinute", stopMinute).apply()
    }
}

object PlaybackScheduler {
    const val ACTION_PLAY = "com.innova.dhammamorning.ACTION_PLAY"
    const val ACTION_STOP = "com.innova.dhammamorning.ACTION_STOP"
    const val ACTION_TEST = "com.innova.dhammamorning.ACTION_TEST_ALARM"

    fun canScheduleExactly(c: Context): Boolean {
        val manager = c.getSystemService(AlarmManager::class.java)
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.S || manager.canScheduleExactAlarms()
    }

    private fun pending(c: Context): PendingIntent = PendingIntent.getBroadcast(
        c, 34192, Intent(c, PlaybackAlarmReceiver::class.java),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
    )

    fun nextStartMillis(hour: Int, minute: Int, from: Long = System.currentTimeMillis()): Long {
        val cal = Calendar.getInstance().apply {
            timeInMillis = from
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (timeInMillis <= from) add(Calendar.DAY_OF_MONTH, 1)
        }
        return cal.timeInMillis
    }


    private fun arm(c: Context, whenMillis: Long, intent: PendingIntent): Boolean {
        if (!canScheduleExactly(c)) {
            DhammaPreferences.event(c, "NOT ARMED: Alarms & reminders permission missing")
            return false
        }
        val alarm = c.getSystemService(AlarmManager::class.java)
        val open = PendingIntent.getActivity(
            c, 911, Intent(c, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return try {
            // Visible alarm-clock alarms are prioritized even when the phone is idle.
            alarm.setAlarmClock(AlarmManager.AlarmClockInfo(whenMillis, open), intent)
            DhammaPreferences.event(
                c, "ARMED for " + DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
                    .format(Date(whenMillis))
            )
            true
        } catch (e: Exception) {
            DhammaPreferences.event(c, "NOT ARMED: ${e.javaClass.simpleName}: ${e.message}")
            false
        }
    }

    fun testIn90Seconds(c: Context): Boolean {
        if (DhammaPreferences.tracks(c).isEmpty()) {
            DhammaPreferences.event(c, "TEST FAILED: No MP3 selected")
            return false
        }
        val alarm = c.getSystemService(AlarmManager::class.java)
        val intent = PendingIntent.getBroadcast(
            c, 34193,
            Intent(c, PlaybackAlarmReceiver::class.java).apply { action = ACTION_TEST },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        alarm.cancel(intent)
        return arm(c, System.currentTimeMillis() + 90_000L, intent)
    }

    /** Refresh the one upcoming exact alarm, then repeat only after it fires. */
    fun sync(c: Context): Boolean {
        val alarm = c.getSystemService(AlarmManager::class.java)
        val intent = pending(c)
        alarm.cancel(intent)
        if (!DhammaPreferences.enabled(c)) {
            DhammaPreferences.event(c, "Daily playback disabled")
            return true
        }
        if (DhammaPreferences.tracks(c).isEmpty()) {
            DhammaPreferences.event(c, "NOT ARMED: No audio files")
            return false
        }
        val trigger = nextStartMillis(DhammaPreferences.hour(c), DhammaPreferences.minute(c))
        return arm(c, trigger, intent)
    }
}

/** Exact alarms are an OS-allowed foreground-service launch exemption for scheduled media playback. */
class PlaybackAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val isTest = intent?.action == PlaybackScheduler.ACTION_TEST
        if ((!isTest && !DhammaPreferences.enabled(context)) ||
            DhammaPreferences.tracks(context).isEmpty()) {
            DhammaPreferences.event(context, "Alarm ignored: schedule off or no MP3")
            return
        }
        DhammaPreferences.event(context, if (isTest) "TEST ALARM FIRED" else "DAILY ALARM FIRED")
        if (!isTest) PlaybackScheduler.sync(context)
        val service = Intent(context, PlaybackService::class.java).apply {
            action = PlaybackScheduler.ACTION_PLAY
        }
        try {
            context.startForegroundService(service)
            DhammaPreferences.event(context, "Alarm fired; starting audio service")
        } catch (e: Exception) {
            DhammaPreferences.event(context, "FAILED to start audio: ${e.javaClass.simpleName}: ${e.message}")
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action in listOf(Intent.ACTION_BOOT_COMPLETED, Intent.ACTION_MY_PACKAGE_REPLACED,
                Intent.ACTION_TIMEZONE_CHANGED, Intent.ACTION_TIME_CHANGED)) {
            PlaybackScheduler.sync(context)
        }
    }
}

class ExactAlarmPermissionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == AlarmManager.ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED) {
            PlaybackScheduler.sync(context)
        }
    }
}
