package com.innova.dhammamorning

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
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

    /** Refresh the one upcoming exact alarm, then repeat only after it fires. */
    fun sync(c: Context): Boolean {
        val alarm = c.getSystemService(AlarmManager::class.java)
        val intent = pending(c)
        alarm.cancel(intent)
        if (!DhammaPreferences.enabled(c)) return true
        if (DhammaPreferences.tracks(c).isEmpty()) return false
        if (!canScheduleExactly(c)) return false
        val trigger = nextStartMillis(DhammaPreferences.hour(c), DhammaPreferences.minute(c))
        return try {
            alarm.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, trigger, intent)
            true
        } catch (_: SecurityException) { false }
    }
}

/** Exact alarms are an OS-allowed foreground-service launch exemption for scheduled media playback. */
class PlaybackAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (!DhammaPreferences.enabled(context) || DhammaPreferences.tracks(context).isEmpty()) return
        // Arm tomorrow's alarm immediately; otherwise a stopped service could break recurrence.
        PlaybackScheduler.sync(context)
        val service = Intent(context, PlaybackService::class.java).apply {
            action = PlaybackScheduler.ACTION_PLAY
        }
        try { context.startForegroundService(service) } catch (_: Exception) {
            // OEM policy may still block playback; never silently record or request mic.
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
