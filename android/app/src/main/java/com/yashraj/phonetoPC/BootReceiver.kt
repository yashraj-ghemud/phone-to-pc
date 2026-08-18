package com.yashraj.phonetopc

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != Intent.ACTION_BOOT_COMPLETED) return
        val prefs = context.getSharedPreferences(UploadService.PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(UploadService.TOKEN, "").orEmpty().isBlank()) return
        val serviceIntent = Intent(context, UploadService::class.java).setAction(UploadService.ACTION_START)
        ContextCompat.startForegroundService(context, serviceIntent)
    }
}
