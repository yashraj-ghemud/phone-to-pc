package com.yashraj.phonetopc

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat

class NotificationHelper(private val context: Context) {
    init {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Phone-to-PC background service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows Phone-to-PC connection and upload status"
                setShowBadge(false)
            }
            context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    fun build(message: String): Notification {
        val pendingIntent = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle("Phone-to-PC")
            .setContentText(message)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }

    fun notify(message: String) {
        context.getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, build(message))
    }

    companion object {
        const val CHANNEL_ID = "phone_to_pc_service"
        const val NOTIFICATION_ID = 8765
    }
}
