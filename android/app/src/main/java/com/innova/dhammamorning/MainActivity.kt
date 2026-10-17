package com.innova.dhammamorning

import android.Manifest
import android.app.AlarmManager
import android.app.TimePickerDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay
import java.text.DateFormat
import java.util.Date

private val Night = Color(0xFF13243A)
private val Sea = Color(0xFF296E6A)
private val Cream = Color(0xFFF6F7F3)

class MainActivity : ComponentActivity() {
    private val resumeRevision = mutableIntStateOf(0)
    override fun onResume() {
        super.onResume()
        resumeRevision.intValue++
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(
                primary = Sea, onPrimary = Color.White, background = Cream,
                surface = Color.White, onSurface = Night
            )) { DhammaHome(resumeRevision.intValue) }
        }
    }
}

private fun fileTitle(c: Context, uri: Uri): String {
    return runCatching {
        c.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { if (it.moveToFirst()) it.getString(0) else null }
    }.getOrNull() ?: (uri.lastPathSegment ?: "Audio file")
}

private fun clock(hour: Int, minute: Int) = "%02d:%02d".format(hour, minute)

@Composable
private fun DhammaHome(resumeRevision: Int) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val setupPreferences = remember {
        context.getSharedPreferences("dhamma_permission_setup", Context.MODE_PRIVATE)
    }
    var showPermissionSetup by remember {
        mutableStateOf(
            !setupPreferences.getBoolean("setupViewed", false) &&
                (!DhammaPermissions.exactAlarm(context) ||
                 !DhammaPermissions.notifications(context) ||
                 !DhammaPermissions.batteryExempt(context))
        )
    }
    if (showPermissionSetup) {
        PermissionSetupDialog(
            context = context,
            resumeRevision = resumeRevision,
            onDismiss = {
                setupPreferences.edit().putBoolean("setupViewed", true).apply()
                showPermissionSetup = false
            }
        )
    }
    var tracks by remember { mutableStateOf(DhammaPreferences.tracks(context)) }
    var hour by remember { mutableIntStateOf(DhammaPreferences.hour(context)) }
    var minute by remember { mutableIntStateOf(DhammaPreferences.minute(context)) }
    var duration by remember { mutableIntStateOf(DhammaPreferences.durationMinutes(context)) }
    var durationText by remember { mutableStateOf(duration.toString()) }
    var stopMode by remember { mutableStateOf(DhammaPreferences.stopMode(context)) }
    var stopHour by remember { mutableIntStateOf(DhammaPreferences.stopHour(context)) }
    var stopMinute by remember { mutableIntStateOf(DhammaPreferences.stopMinute(context)) }
    var scheduled by remember { mutableStateOf(DhammaPreferences.enabled(context)) }
    fun saveSettings() {
        DhammaPreferences.save(context, scheduled, hour, minute, duration,
            stopMode, stopHour, stopMinute)
        if (scheduled) PlaybackScheduler.sync(context)
    }
    var status by remember { mutableStateOf("Ready for your morning practice") }
    var isPlaying by remember { mutableStateOf(PlaybackService.playing) }
    var exactReady by remember { mutableStateOf(PlaybackScheduler.canScheduleExactly(context)) }
    var alarmEvent by remember { mutableStateOf(DhammaPreferences.lastEvent(context)) }

    val pickAudio = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments()
    ) { selection ->
        val accepted = selection.filter { uri ->
            try {
                context.contentResolver.takePersistableUriPermission(
                    uri, Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
                true
            } catch (_: Exception) { false }
        }
        if (accepted.isNotEmpty()) {
            tracks = (tracks + accepted).distinct()
            DhammaPreferences.setTracks(context, tracks)
            status = "Added ${accepted.size} audio file(s)"
            if (scheduled) PlaybackScheduler.sync(context)
        } else if (selection.isNotEmpty()) {
            status = "Could not retain access. Choose local audio from your Files app."
        }
    }
    val askNotifications = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { allowed ->
        if (!allowed) status = "Notifications disabled. The Android player can still run, but alerts may be hidden."
    }
    fun notifyPermission() {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(
                context, Manifest.permission.POST_NOTIFICATIONS
            ) != PackageManager.PERMISSION_GRANTED) {
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
    fun persistEnabled(value: Boolean) {
        scheduled = value
        DhammaPreferences.save(context, value, hour, minute, duration,
            stopMode, stopHour, stopMinute)
        if (value && !PlaybackScheduler.canScheduleExactly(context)) {
            status = "Exact-alarm permission is required. Tap Allow in the permission setup."
            showPermissionSetup = true
        } else {
            val armed = PlaybackScheduler.sync(context)
            status = when {
                !value -> "Daily playback disabled"
                armed -> "Daily playback scheduled for ${clock(hour, minute)}"
                else -> "Unable to schedule; check exact alarm permission"
            }
        }
    }
    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            isPlaying = PlaybackService.playing
            alarmEvent = DhammaPreferences.lastEvent(context)
            val allowed = PlaybackScheduler.canScheduleExactly(context)
            if (allowed != exactReady) {
                exactReady = allowed
                if (allowed && scheduled && tracks.isNotEmpty()) PlaybackScheduler.sync(context)
            }
        }
    }
    Column(Modifier.fillMaxSize().background(Cream)) {
        Column(Modifier.fillMaxWidth().background(Night).padding(22.dp)) {
            Text("DHAMMA MORNING", color = Color(0xFFACCFC9),
                style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text("Wake up to Dhamma", color = Color.White,
                style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("Your morning audio, automatically — no recording, no cloud.",
                color = Color(0xFFD7E0E8), style = MaterialTheme.typography.bodyMedium)
        }
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            item {
                ElevatedCard(shape = RoundedCornerShape(16.dp)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Automatic playback permissions", fontWeight = FontWeight.Bold)
                        Text(
                            "Exact alarms: " + if (DhammaPermissions.exactAlarm(context)) "Allowed" else "Needs Allow",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            "Notifications: " + if (DhammaPermissions.notifications(context)) "Allowed" else "Needs Allow",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            "Battery background access: " + if (DhammaPermissions.batteryExempt(context)) "Allowed" else "Needs Allow",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text("Android may require extra Auto-start access for your phone brand.",
                            style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                        Button(onClick = { showPermissionSetup = true }) {
                            Text("Review / Allow permissions")
                        }
                    }
                }
            }
            item {
                ElevatedCard(shape = RoundedCornerShape(16.dp)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("Daily morning schedule", fontWeight = FontWeight.Bold)
                                Text(if (scheduled) "Enabled" else "Disabled",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (scheduled) Sea else Color.Gray)
                            }
                            Switch(checked = scheduled, onCheckedChange = { newValue ->
                                if (newValue && tracks.isEmpty()) {
                                    status = "Choose at least one Dhamma audio file first."
                                } else {
                                    notifyPermission()
                                    persistEnabled(newValue)
                                }
                            })
                        }
                        Spacer(Modifier.height(10.dp))
                        OutlinedButton(onClick = {
                            TimePickerDialog(context, { _, h, m ->
                                hour = h; minute = m
                                saveSettings()
                            }, hour, minute, true).show()
                        }) {
                            Text("Start: ${clock(hour, minute)}")
                        }
                        Spacer(Modifier.height(6.dp))
                        Text("Stop playback", style = MaterialTheme.typography.labelMedium)
                        Spacer(Modifier.height(7.dp))
                        Row(Modifier.horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            listOf(
                                PlaybackStopPolicy.END_OF_PLAYLIST to "When MP3 ends",
                                PlaybackStopPolicy.CLOCK to "At set time",
                                PlaybackStopPolicy.DURATION to "After duration"
                            ).forEach { (value, label) ->
                                FilterChip(selected = stopMode == value, onClick = {
                                    stopMode = value; saveSettings()
                                }, label = { Text(label) })
                            }
                        }
                        when (stopMode) {
                            PlaybackStopPolicy.CLOCK -> {
                                Spacer(Modifier.height(7.dp))
                                OutlinedButton(onClick = {
                                    TimePickerDialog(context, { _, h, m ->
                                        stopHour = h; stopMinute = m; saveSettings()
                                    }, stopHour, stopMinute, true).show()
                                }) { Text("Stop at: ${clock(stopHour, stopMinute)}") }
                                Text("Stops at the selected local time, including after midnight.",
                                    style = MaterialTheme.typography.bodySmall)
                            }
                            PlaybackStopPolicy.DURATION -> {
                                Spacer(Modifier.height(7.dp))
                                Row(Modifier.horizontalScroll(rememberScrollState()),
                                    horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    listOf(15, 30, 60, 120, 180, 240, 360).forEach { m ->
                                        FilterChip(selected = duration == m, onClick = {
                                            duration = m; durationText = m.toString(); saveSettings()
                                        }, label = { Text(if (m < 60) "${m}m" else "${m / 60}h") })
                                    }
                                }
                                OutlinedTextField(value = durationText,
                                    onValueChange = { raw ->
                                        if (raw.length <= 4 && raw.all(Char::isDigit)) {
                                            durationText = raw
                                            raw.toIntOrNull()?.takeIf { it in 1..1440 }?.let {
                                                duration = it; saveSettings()
                                            }
                                        }
                                    }, label = { Text("Custom duration (minutes, 1–1440)") },
                                    singleLine = true,
                                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                    modifier = Modifier.fillMaxWidth())
                            }
                            else -> Text("Plays each selected MP3 once and stops after the last file.",
                                style = MaterialTheme.typography.bodySmall)
                        }
                        Spacer(Modifier.height(7.dp))
                        val next = if (scheduled && exactReady) PlaybackScheduler.nextStartMillis(hour, minute) else null
                        Text(
                            if (next != null) "Next: " + DateFormat.getDateTimeInstance(
                                DateFormat.MEDIUM, DateFormat.SHORT).format(Date(next))
                            else if (scheduled) "Exact alarm permission REQUIRED"
                            else "Schedule is off",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (next != null) Sea else Color.Gray
                        )
                        Spacer(Modifier.height(8.dp))
                        if (!exactReady) {
                            Button(onClick = {
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                                    runCatching {
                                        context.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply {
                                            data = Uri.parse("package:${context.packageName}")
                                        })
                                    }.onFailure { status = "Open Settings > Alarms & reminders manually." }
                                }
                            }) { Text("Grant Alarms & reminders") }
                        }
                        OutlinedButton(
                            enabled = tracks.isNotEmpty() && exactReady,
                            onClick = {
                                val ok = PlaybackScheduler.testIn90Seconds(context)
                                status = if (ok) "Test scheduled for 90 seconds. Lock your phone; audio should start automatically."
                                    else "Test failed. Check alarm status below."
                            }
                        ) { Text("TEST AUTO PLAY (90 SEC)") }
                        Text("Last alarm status: $alarmEvent",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (alarmEvent.contains("FAILED") || alarmEvent.contains("NOT ARMED"))
                                MaterialTheme.colorScheme.error else Sea)
                    }
                }
            }
            item {
                ElevatedCard(shape = RoundedCornerShape(16.dp)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("Dhamma audio playlist", fontWeight = FontWeight.Bold)
                                Text("${tracks.size} local audio file(s)",
                                    style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                            }
                            Button(onClick = {
                                pickAudio.launch(arrayOf("audio/*"))
                            }) { Text("Add audio") }
                        }
                        if (tracks.isEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            Text("Choose MP3, M4A or WAV files from your device. " +
                                "At end of playlist, playback stops unless a timed mode is selected.",
                                style = MaterialTheme.typography.bodySmall)
                        }
                        tracks.forEachIndexed { index, uri ->
                            HorizontalDivider(Modifier.padding(vertical = 5.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("${index + 1}. " + fileTitle(context, uri),
                                    maxLines = 1, overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier.weight(1f))
                                TextButton(onClick = {
                                    tracks = tracks.filterNot { it == uri }
                                    DhammaPreferences.setTracks(context, tracks)
                                    if (tracks.isEmpty() && scheduled) persistEnabled(false)
                                    else if (scheduled) PlaybackScheduler.sync(context)
                                }) { Text("Remove") }
                            }
                        }
                    }
                }
            }
            item {
                ElevatedCard(shape = RoundedCornerShape(16.dp)) {
                    Column(Modifier.fillMaxWidth().padding(16.dp)) {
                        Text("Playback controls", fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(10.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                enabled = tracks.isNotEmpty() && !isPlaying,
                                onClick = {
                                    notifyPermission()
                                    try {
                                        ContextCompat.startForegroundService(context,
                                            Intent(context, PlaybackService::class.java).apply {
                                                action = PlaybackScheduler.ACTION_PLAY
                                            })
                                        status = "Starting Dhamma audio"
                                    } catch (e: Exception) { status = "Unable to play: ${e.message}" }
                                }, modifier = Modifier.weight(1f)
                            ) { Text("Play now") }
                            OutlinedButton(onClick = {
                                context.startService(Intent(context, PlaybackService::class.java).apply {
                                    action = PlaybackScheduler.ACTION_STOP
                                })
                                status = "Playback stopped"
                            }, enabled = isPlaying) { Text("Stop") }
                        }
                        Spacer(Modifier.height(8.dp))
                        Text(if (isPlaying) "● Playing" else "Not playing",
                            style = MaterialTheme.typography.labelMedium,
                            color = if (isPlaying) Sea else Color.Gray)
                    }
                }
            }
            item {
                Text(status, color = Sea, style = MaterialTheme.typography.bodySmall)
                Text("Morning volume follows your device's media volume. Keep your " +
                    "phone charged, grant Alarms & reminders access, and test playback first. " +
                    "Dhamma Morning never accesses the microphone.",
                    color = Color.Gray, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
