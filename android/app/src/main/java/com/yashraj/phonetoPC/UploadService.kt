package com.yashraj.phonetopc

import android.app.Service
import android.content.Intent
import android.net.Uri
import android.content.pm.ServiceInfo
import android.os.IBinder
import androidx.core.app.ServiceCompat
import java.io.File
import java.util.concurrent.Executors

class UploadService : Service() {
    private lateinit var notificationHelper: NotificationHelper
    private lateinit var pairingStore: PairingStore
    private val executor = Executors.newSingleThreadExecutor()
    private val apiClient = GatewayApiClient()

    override fun onCreate() {
        super.onCreate()
        notificationHelper = NotificationHelper(this)
        pairingStore = PairingStore(this)
        ServiceCompat.startForeground(
            this,
            NotificationHelper.NOTIFICATION_ID,
            notificationHelper.build("Ready to send images"),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_UPLOAD -> {
                val uri = intent.data ?: intent.getParcelableExtraCompat(EXTRA_URI)
                if (uri == null) {
                    notificationHelper.notify("No image was provided")
                } else {
                    executor.execute { uploadWithRetry(uri) }
                }
            }
            ACTION_STOP -> stopService()
            ACTION_START, null -> notificationHelper.notify(
                if (pairingStore.isPaired()) "Connected and waiting" else "Pair the app with your PC"
            )
        }
        return START_STICKY
    }

    private fun uploadWithRetry(uri: Uri) {
        var preparedFile: File? = null
        try {
            val serverUrl = pairingStore.getServerUrl()
            val token = pairingStore.getPairingToken()
            val phoneName = pairingStore.getPhoneName()
            if (!pairingStore.isPaired()) {
                notificationHelper.notify("Pair the app with your PC first")
                return
            }

            val prepared = FileMetadataReader.prepare(this, uri)
            preparedFile = prepared.file
            notificationHelper.notify("Preparing ${prepared.displayName}")

            var result = GatewayApiClient.UploadResult(false, "Upload did not start")
            val delays = longArrayOf(0L, 1_000L, 3_000L, 8_000L)
            for (attempt in delays.indices) {
                if (delays[attempt] > 0) Thread.sleep(delays[attempt])
                notificationHelper.notify(
                    if (attempt == 0) "Sending ${prepared.displayName}"
                    else "Retrying ${prepared.displayName} ($attempt/3)"
                )
                result = apiClient.uploadFile(
                    baseUrl = serverUrl,
                    token = token,
                    phoneName = phoneName,
                    file = prepared.file,
                    displayName = prepared.displayName,
                    mimeType = prepared.mimeType
                )
                if (result.ok || !isRetryable(result.message) || attempt == delays.lastIndex) break
            }
            notificationHelper.notify(
                if (result.ok) "Sent ${prepared.displayName} successfully" else result.message
            )
        } catch (error: Exception) {
            notificationHelper.notify(error.message?.take(120) ?: "Send failed")
        } finally {
            preparedFile?.delete()
        }
    }

    private fun isRetryable(message: String): Boolean {
        return message.contains("not reachable", ignoreCase = true) ||
            message.contains("timed out", ignoreCase = true) ||
            message.contains("server error", ignoreCase = true)
    }

    private fun stopService() {
        executor.shutdownNow()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        if (!executor.isShutdown) executor.shutdownNow()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private inline fun <reified T : android.os.Parcelable> Intent.getParcelableExtraCompat(key: String): T? {
        return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(key, T::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(key)
        }
    }

    companion object {
        const val ACTION_START = "com.yashraj.phonetopc.action.START"
        const val ACTION_UPLOAD = "com.yashraj.phonetopc.action.UPLOAD"
        const val ACTION_STOP = "com.yashraj.phonetopc.action.STOP"
        const val EXTRA_URI = "extra_uri"
    }
}
