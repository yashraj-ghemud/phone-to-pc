package com.yashraj.phonetopc

import android.Manifest
import android.content.ClipData
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {
    private lateinit var serverUrlInput: EditText
    private lateinit var tokenInput: EditText
    private lateinit var phoneNameInput: EditText
    private lateinit var statusText: TextView
    private lateinit var lastUploadText: TextView
    private lateinit var pairingStore: PairingStore
    private val apiClient = GatewayApiClient()
    private val backgroundExecutor: ExecutorService = Executors.newSingleThreadExecutor()

    private val picker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { uploadUri(it) }
    }

    private val notificationPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) setStatus("Notifications are disabled; upload still works")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        pairingStore = PairingStore(this)
        bindViews()
        loadPairing()
        bindActions()
        requestNotificationPermissionIfNeeded()
        handleIncomingShare(intent)
        if (pairingStore.isPaired()) startGatewayService()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIncomingShare(intent)
    }

    private fun bindViews() {
        serverUrlInput = findViewById(R.id.serverUrlInput)
        tokenInput = findViewById(R.id.tokenInput)
        phoneNameInput = findViewById(R.id.phoneNameInput)
        statusText = findViewById(R.id.statusText)
        lastUploadText = findViewById(R.id.lastUploadText)
    }

    private fun loadPairing() {
        serverUrlInput.setText(pairingStore.getServerUrl().ifBlank { "http://192.168.43.1:8765" })
        tokenInput.setText(pairingStore.getPairingToken())
        phoneNameInput.setText(pairingStore.getPhoneName())
        setStatus(if (pairingStore.isPaired()) "Pairing saved" else "Not paired yet")
    }

    private fun bindActions() {
        findViewById<Button>(R.id.savePairingButton).setOnClickListener {
            if (savePairingFromUi()) {
                startGatewayService()
                setStatus("Pairing saved. Background service is running.")
            }
        }
        findViewById<Button>(R.id.testConnectionButton).setOnClickListener {
            if (savePairingFromUi()) testConnection()
        }
        findViewById<Button>(R.id.pickImageButton).setOnClickListener {
            if (savePairingFromUi()) picker.launch("image/*")
        }
        findViewById<Button>(R.id.stopServiceButton).setOnClickListener {
            val stopIntent = Intent(this, UploadService::class.java).setAction(UploadService.ACTION_STOP)
            startService(stopIntent)
            setStatus("Background service stopped")
        }
    }

    private fun savePairingFromUi(): Boolean {
        val url = GatewayApiClient.normalizeBaseUrl(serverUrlInput.text.toString())
        val token = tokenInput.text.toString().trim()
        val phoneName = phoneNameInput.text.toString().trim()
        if (!GatewayApiClient.isValidBaseUrl(url)) {
            setStatus("Enter a valid PC URL, for example http://192.168.43.20:8765")
            return false
        }
        if (token.isBlank()) {
            setStatus("Enter the pairing token printed by the PC")
            return false
        }
        if (!pairingStore.savePairing(url, token, phoneName)) {
            setStatus("Could not save pairing")
            return false
        }
        serverUrlInput.setText(url)
        return true
    }

    private fun testConnection() {
        setStatus("Testing PC gateway…")
        backgroundExecutor.execute {
            val result = apiClient.checkHealth(pairingStore.getServerUrl())
            runOnUiThread { setStatus(result.message) }
        }
    }

    private fun handleIncomingShare(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND) return
        val uri = intent.getParcelableExtraCompat<Uri>(Intent.EXTRA_STREAM)
        if (uri == null) {
            setStatus("The shared item did not contain an image")
            return
        }
        if (!pairingStore.isPaired()) {
            setStatus("Save PC pairing before sharing an image")
            return
        }
        uploadUri(uri)
    }

    private fun uploadUri(uri: Uri) {
        if (!pairingStore.isPaired()) {
            setStatus("Pair the app with your PC first")
            return
        }
        val uploadIntent = Intent(this, UploadService::class.java).apply {
            action = UploadService.ACTION_UPLOAD
            data = uri
            putExtra(UploadService.EXTRA_URI, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            clipData = ClipData.newRawUri("phone-to-pc-image", uri)
        }
        ContextCompat.startForegroundService(this, uploadIntent)
        setStatus("Sending image in background…")
        lastUploadText.text = "Latest upload: queued"
    }

    private fun startGatewayService() {
        ContextCompat.startForegroundService(
            this,
            Intent(this, UploadService::class.java).setAction(UploadService.ACTION_START)
        )
    }

    private fun setStatus(message: String) {
        if (::statusText.isInitialized) statusText.text = message
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    override fun onDestroy() {
        backgroundExecutor.shutdownNow()
        super.onDestroy()
    }

    private inline fun <reified T : android.os.Parcelable> Intent.getParcelableExtraCompat(key: String): T? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(key, T::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(key)
        }
    }
}
