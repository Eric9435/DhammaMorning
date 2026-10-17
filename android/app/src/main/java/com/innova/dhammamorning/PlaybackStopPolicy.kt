package com.innova.dhammamorning

import java.util.Calendar

/** Shared policy for a finite playback session. Never repeats tracks in end-of-playlist mode. */
object PlaybackStopPolicy {
    const val DURATION = "duration"
    const val CLOCK = "clock"
    const val END_OF_PLAYLIST = "end_of_playlist"

    fun nextStopAt(hour: Int, minute: Int, after: Long): Long {
        require(hour in 0..23 && minute in 0..59)
        val cal = Calendar.getInstance().apply {
            timeInMillis = after
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (timeInMillis <= after) add(Calendar.DAY_OF_YEAR, 1)
        }
        return cal.timeInMillis
    }

    fun shouldFinishPlaylist(mode: String, nextIndex: Int, trackCount: Int): Boolean =
        mode == END_OF_PLAYLIST && nextIndex >= trackCount
}
