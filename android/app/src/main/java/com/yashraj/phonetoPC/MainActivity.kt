package com.yashraj.phonetopc

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    private lateinit var serverUrlInput: EditText
    private lateinit var tokenInput: EditText
    private lateinit var phoneNameInput: EditText
    private lateinit var statusText: TextView

    private val picker = registerForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { uploadUri(it) }
    }

    private val notificationPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        serverUrlInput = findViewById(R.id.serverUrlInput)
        tokenInput = findViewById(R.id.tokenInput)
        phoneNameInput = findViewById(R.id.phoneNameInput)
        statusText = findViewById(R.id.statusText)

        val prefs = getSharedPreferences(UploadService.PREFS, MODE_PRIVATE)
        serverUrlInput.setText(prefs.getString(UploadService.SERVER_URL, "http://192.168.43.1:8765"))
        tokenInput.setText(prefs.getString(UploadService.TOKEN, ""))
        phoneNameInput.setText(prefs.getString(UploadService.PHONE_NAME, "My Android phone"))

        findViewById<Button>(R.id.savePairingButton).setOnClickListener {
            savePairing()
            statusText.text = "Pairing saved. Background service is running."
        }
        findViewById<Button>(R.id.pickImageButton).setOnClickListener {
            savePairing()
            picker.launch("image/*")
        }
        findViewById<Button>(R.id.shareButton).setOnClickListener {
            statusText.text = "Use Android's Share menu and select Phone-to-PC."
        }

        requestNotificationPermissionIfNeeded()
        handleIncomingShare(intent)
        if (prefs.getString(UploadService.TOKEN, "").orEmpty().isNotBlank()) {
            startGatewayService()
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        handleIncomingShare(intent)
    }

    private fun handleIncomingShare(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND) {
            val uri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
            if (uri != null) {
                uploadUri(uri)
            }
        }
    }

    private fun savePairing() {
        getSharedPreferences(UploadService.PREFS, MODE_PRIVATE).edit()
            .putString(UploadService.SERVER_URL, serverUrlInput.text.toString().trim().removeSuffix("/"))
            .putString(UploadService.TOKEN, tokenInput.text.toString().trim())
            .putString(UploadService.PHONE_NAME, phoneNameInput.text.toString().trim().ifBlank { "Android phone" })
            .apply()
        startGatewayService()
    }

    private fun uploadUri(uri: Uri) {
        savePairing()
        val serviceIntent = Intent(this, UploadService::class.java).apply {
            action = UploadService.ACTION_UPLOAD
            data = uri
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        ContextCompat.startForegroundService(this, serviceIntent)
        statusText.text = "Sending image in background…"
    }

    private fun startGatewayService() {
        ContextCompat.startForegroundService(
            this,
            Intent(this, UploadService::class.java).setAction(UploadService.ACTION_START)
        )
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}
