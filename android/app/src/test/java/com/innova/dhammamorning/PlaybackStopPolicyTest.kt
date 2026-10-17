package com.innova.dhammamorning

import org.junit.Assert.*
import org.junit.Test
import java.util.Calendar

class PlaybackStopPolicyTest {
    @Test fun mp3EndStopsWithoutRepeating() {
        assertFalse(PlaybackStopPolicy.shouldFinishPlaylist("end_of_playlist",0,1))
        assertTrue(PlaybackStopPolicy.shouldFinishPlaylist("end_of_playlist",1,1))
        assertTrue(PlaybackStopPolicy.shouldFinishPlaylist("end_of_playlist",3,3))
    }
    @Test fun timedPlaybackMayLoop() {
        assertFalse(PlaybackStopPolicy.shouldFinishPlaylist("duration",3,3))
        assertFalse(PlaybackStopPolicy.shouldFinishPlaylist("clock",3,3))
    }
    @Test fun stopTimeCrossesMidnight() {
        val start = Calendar.getInstance().apply {
            set(2026, Calendar.OCTOBER,17,23,0,0)
            set(Calendar.MILLISECOND,0)
        }
        val stop=Calendar.getInstance().apply {
            timeInMillis=PlaybackStopPolicy.nextStopAt(1,0,start.timeInMillis)
        }
        assertEquals(18,stop.get(Calendar.DAY_OF_MONTH))
        assertEquals(1,stop.get(Calendar.HOUR_OF_DAY))
    }
}
