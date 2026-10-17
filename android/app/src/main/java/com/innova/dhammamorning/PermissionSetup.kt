package com.innova.dhammamorning

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat

/** Users remain in control: normal permissions use Android dialogs,
 *  while special access opens the matching system page.
 */
internal object DhammaPermissions {
    fun notifications(c: Context): Boolean =
        Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(c, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    fun exactAlarm(c: Context): Boolean = PlaybackScheduler.canScheduleExactly(c)

    fun batteryExempt(c: Context): Boolean =
        (c.getSystemService(Context.POWER_SERVICE) as PowerManager)
            .isIgnoringBatteryOptimizations(c.packageName)

    fun openAppSettings(c: Context) {
        c.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.parse("package:${c.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun requestAlarm(c: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val intent = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply {
                data = Uri.parse("package:${c.packageName}")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            runCatching { c.startActivity(intent) }.onFailure { openAppSettings(c) }
        }
    }

    fun requestBattery(c: Context) {
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:${c.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        // Some brands do not expose the exemption dialog. Their App info screen
        // provides a manual route to Battery > Unrestricted and Autostart.
        runCatching { c.startActivity(intent) }.onFailure { openAppSettings(c) }
    }
}

@Composable
private fun PermissionStep(
    name: String,
    details: String,
    granted: Boolean,
    required: Boolean,
    onAllow: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.weight(1f)) {
                Text(name, fontWeight = FontWeight.SemiBold)
                Text(
                    when {
                        granted -> "Allowed"
                        required -> "Required for exact daily playback"
                        else -> "Recommended"
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = if (granted) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.error
                )
            }
            if (granted) {
                Text("✓ Ready", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary)
            } else {
                FilledTonalButton(onClick = onAllow) { Text("Allow") }
            }
        }
        Text(details, style = MaterialTheme.typography.bodySmall)
    }
}

/** First-launch setup that can be reopened from the main screen. */
@Composable
internal fun PermissionSetupDialog(
    context: Context,
    resumeRevision: Int,
    onDismiss: () -> Unit
) {
    var localRevision by remember { mutableIntStateOf(0) }
    val notifications = remember(resumeRevision, localRevision) {
        DhammaPermissions.notifications(context)
    }
    val exact = remember(resumeRevision, localRevision) {
        DhammaPermissions.exactAlarm(context)
    }
    val battery = remember(resumeRevision, localRevision) {
        DhammaPermissions.batteryExempt(context)
    }
    val notificationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) {
        localRevision++
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Enable automatic Dhamma playback") },
        text = {
            Column(
                modifier = Modifier.heightIn(max = 440.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Text(
                    "Please allow the Android permissions below. Tap Allow for each step; " +
                        "you'll see an Android prompt or the correct settings page. " +
                        "Return here after granting access.",
                    style = MaterialTheme.typography.bodyMedium
                )
                PermissionStep(
                    name = "1. Exact alarms",
                    details = "Needed to start your morning MP3 at the scheduled clock time, " +
                        "even when the screen is off.",
                    granted = exact, required = true,
                    onAllow = { DhammaPermissions.requestAlarm(context) }
                )
                HorizontalDivider()
                PermissionStep(
                    name = "2. Notifications",
                    details = "Shows a playback notification with a Stop control.",
                    granted = notifications, required = false,
                    onAllow = {
                        if (Build.VERSION.SDK_INT >= 33)
                            notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                )
                HorizontalDivider()
                PermissionStep(
                    name = "3. Battery optimization",
                    details = "Allow unrestricted/background operation for dependable morning playback.",
                    granted = battery, required = false,
                    onAllow = { DhammaPermissions.requestBattery(context) }
                )
                HorizontalDivider()
                Text("Some phones also require Auto-start to be enabled by the user in App settings.",
                    style = MaterialTheme.typography.bodySmall)
                TextButton(onClick = { DhammaPermissions.openAppSettings(context) }) {
                    Text("Open this app's Android settings")
                }
                if (exact && notifications && battery)
                    Text("All recommended Android permissions are ready.",
                        color = MaterialTheme.colorScheme.primary)
            }
        },
        confirmButton = {
            Button(onClick = onDismiss) { Text("Done") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Later") }
        }
    )
}
