package com.innova.dhammamorning

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock

/** Plays user-selected Dhamma talks in order, looping the playlist until auto-stop. */
class PlaybackService : Service() {
    companion object {
        @Volatile var playing = false
            private set
    }

    private val handler = Handler(Looper.getMainLooper())
    private var player: MediaPlayer? = null
    private var tracks: List<Uri> = emptyList()
    private var nextTrack = 0
    private var failures = 0
    private var deadlineElapsed = Long.MAX_VALUE
    private var stopAtWall = Long.MAX_VALUE
    private var stopMode = PlaybackStopPolicy.END_OF_PLAYLIST
    private var wakeLock: PowerManager.WakeLock? = null
    private val checkStop = object : Runnable {
        override fun run() {
            if (!playing) return
            if (stopDue()) stopPlayback()
            else handler.postDelayed(this, 1_000L)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel("dhamma_playback", "Dhamma audio playback", NotificationManager.IMPORTANCE_LOW)
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            PlaybackScheduler.ACTION_STOP -> stopPlayback()
            PlaybackScheduler.ACTION_PLAY -> if (!playing) startPlayback()
        }
        return START_NOT_STICKY
    }

    private fun foreground() {
        val stopIntent = PendingIntent.getService(this, 200, Intent(this, PlaybackService::class.java).apply {
            action = PlaybackScheduler.ACTION_STOP
        }, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val openIntent = PendingIntent.getActivity(this, 201, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val notification = Notification.Builder(this, "dhamma_playback")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle("Dhamma Morning")
            .setContentText("Morning Dhamma is playing • stops automatically")
            .setContentIntent(openIntent)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(null, "Stop", stopIntent).build())
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            startForeground(932, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
        else startForeground(932, notification)
    }

    private fun startPlayback() {
        tracks = DhammaPreferences.tracks(this)
        if (tracks.isEmpty()) {
            DhammaPreferences.event(this, "Playback failed: no MP3 files")
            stopSelf(); return
        }
        try { foreground() } catch (e: Exception) {
            DhammaPreferences.event(this, "Playback service blocked: ${e.javaClass.simpleName}: ${e.message}")
            stopSelf(); return
        }
        stopMode = DhammaPreferences.stopMode(this)
        val durationMs = DhammaPreferences.durationMinutes(this).toLong() * 60_000L
        deadlineElapsed = if (stopMode == PlaybackStopPolicy.DURATION)
            SystemClock.elapsedRealtime() + durationMs else Long.MAX_VALUE
        stopAtWall = if (stopMode == PlaybackStopPolicy.CLOCK)
            PlaybackStopPolicy.nextStopAt(
                DhammaPreferences.stopHour(this), DhammaPreferences.stopMinute(this),
                System.currentTimeMillis()
            ) else Long.MAX_VALUE
        // MediaPlayer holds its own streaming wakelock; the service is foregrounded.
        // For finite modes, hold one bounded extra lock for robust short morning playback.
        if (stopMode != PlaybackStopPolicy.END_OF_PLAYLIST) {
            val maxWaitMs = if (stopMode == PlaybackStopPolicy.DURATION) durationMs
                else (stopAtWall - System.currentTimeMillis()).coerceAtLeast(1L)
            wakeLock = (getSystemService(POWER_SERVICE) as PowerManager)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "DhammaMorning:Playback").apply {
                    setReferenceCounted(false)
                    acquire(maxWaitMs + 120_000L)
                }
        }
        playing = true
        failures = 0
        nextTrack = 0
        handler.removeCallbacks(checkStop)
        handler.post(checkStop)
        playNext()
    }

    private fun stopDue(): Boolean =
        (stopMode == PlaybackStopPolicy.DURATION &&
            SystemClock.elapsedRealtime() >= deadlineElapsed) ||
        (stopMode == PlaybackStopPolicy.CLOCK && System.currentTimeMillis() >= stopAtWall)

    private fun playNext() {
        if (!playing) return
        if (stopDue() || PlaybackStopPolicy.shouldFinishPlaylist(stopMode, nextTrack, tracks.size)) {
            stopPlayback(); return
        }
        if (failures >= tracks.size) { stopPlayback(); return }
        val uri = tracks[nextTrack % tracks.size]
        nextTrack++
        player?.release()
        player = null
        try {
            val mp = MediaPlayer()
            player = mp
            mp.setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
            mp.setWakeMode(this, PowerManager.PARTIAL_WAKE_LOCK)
            mp.setDataSource(this, uri)
            mp.setOnPreparedListener {
                if (playing && !stopDue()) {
                    failures = 0
                    it.start()
                    DhammaPreferences.event(this, "AUDIO PLAYING: track ${nextTrack} of ${tracks.size}")
                } else it.release()
            }
            mp.setOnCompletionListener { handler.post { if (playing) playNext() } }
            mp.setOnErrorListener { _, what, extra ->
                DhammaPreferences.event(this, "MP3 error: code $what / $extra")
                failures++
                handler.post { playNext() }
                true
            }
            mp.prepareAsync()
        } catch (e: Exception) {
            DhammaPreferences.event(this, "Audio file cannot open: ${e.javaClass.simpleName}: ${e.message}")
            failures++
            handler.post { playNext() }
        }
    }

    private fun stopPlayback() {
        playing = false
        handler.removeCallbacks(checkStop)
        runCatching { player?.stop() }
        runCatching { player?.release() }
        player = null
        runCatching { if (wakeLock?.isHeld == true) wakeLock?.release() }
        wakeLock = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        playing = false
        handler.removeCallbacks(checkStop)
        player?.release()
        player = null
        runCatching { if (wakeLock?.isHeld == true) wakeLock?.release() }
        wakeLock = null
        super.onDestroy()
    }
}
