package com.yashraj.phonetopc

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.provider.OpenableColumns
import androidx.core.app.NotificationCompat
import java.io.BufferedInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class UploadService : Service() {
    private val executor = Executors.newSingleThreadExecutor()

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, notification("Ready to send images"))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_UPLOAD -> intent.data?.let { uri -> executor.execute { upload(uri) } }
            ACTION_START, null -> updateNotification("Connected and waiting")
        }
        return START_STICKY
    }

    private fun upload(uri: Uri) {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        val baseUrl = prefs.getString(SERVER_URL, "").orEmpty().trim().removeSuffix("/")
        val token = prefs.getString(TOKEN, "").orEmpty().trim()
        val phoneName = prefs.getString(PHONE_NAME, "Android phone").orEmpty()
        if (baseUrl.isBlank() || token.isBlank()) {
            updateNotification("Pair the app with your PC first")
            return
        }

        val filename = displayName(uri)
        updateNotification("Sending $filename…")
        var connection: HttpURLConnection? = null
        try {
            val connectionUrl = URL("$baseUrl/api/v1/upload")
            connection = connectionUrl.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.connectTimeout = 8_000
            connection.readTimeout = 20_000
            connection.setRequestProperty("X-Phone-Token", token)
            connection.setRequestProperty("X-Phone-Name", phoneName)
            connection.setRequestProperty("X-Filename", filename)
            val size = contentLength(uri)
            if (size > 0) connection.setFixedLengthStreamingMode(size)
            connection.setRequestProperty("Content-Type", mimeType(uri))
            contentResolver.openInputStream(uri).use { source ->
                requireNotNull(source) { "Cannot open selected file" }
                connection.outputStream.use { output ->
                    BufferedInputStream(source).use { input -> input.copyTo(output) }
                }
            }
            val code = connection.responseCode
            if (code in 200..299) {
                updateNotification("Sent $filename successfully")
            } else {
                updateNotification("PC rejected upload (HTTP $code)")
            }
        } catch (error: Exception) {
            updateNotification("Send failed: ${error.message ?: "network error"}")
        } finally {
            connection?.disconnect()
        }
    }

    private fun contentLength(uri: Uri): Long {
        contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) return cursor.getLong(0)
        }
        return -1L
    }

    private fun displayName(uri: Uri): String {
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) return cursor.getString(0)
        }
        return "capture.jpg"
    }

    private fun mimeType(uri: Uri): String = contentResolver.getType(uri) ?: "application/octet-stream"

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification(text))
    }

    private fun notification(text: String): Notification {
        val launchIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle("Phone-to-PC")
            .setContentText(text)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID, "Phone-to-PC background service", NotificationManager.IMPORTANCE_LOW
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        startService(Intent(this, UploadService::class.java).setAction(ACTION_START))
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        executor.shutdownNow()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val PREFS = "phone_to_pc_preferences"
        const val SERVER_URL = "server_url"
        const val TOKEN = "pairing_token"
        const val PHONE_NAME = "phone_name"
        const val ACTION_START = "com.yashraj.phonetopc.START"
        const val ACTION_UPLOAD = "com.yashraj.phonetopc.UPLOAD"
        private const val CHANNEL_ID = "phone_to_pc_service"
        private const val NOTIFICATION_ID = 8765
    }
}
