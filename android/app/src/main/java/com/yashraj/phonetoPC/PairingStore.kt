package com.yashraj.phonetopc

import android.content.Context

class PairingStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getServerUrl(): String = preferences.getString(KEY_SERVER_URL, "").orEmpty()
    fun getPairingToken(): String = preferences.getString(KEY_PAIRING_TOKEN, "").orEmpty()
    fun getPhoneName(): String = preferences.getString(KEY_PHONE_NAME, DEFAULT_PHONE_NAME).orEmpty()

    fun isPaired(): Boolean = getServerUrl().isNotBlank() && getPairingToken().isNotBlank()

    fun savePairing(serverUrl: String, pairingToken: String, phoneName: String): Boolean {
        val normalizedUrl = GatewayApiClient.normalizeBaseUrl(serverUrl)
        val normalizedToken = pairingToken.trim()
        val normalizedName = phoneName.trim().ifBlank { DEFAULT_PHONE_NAME }
        if (!GatewayApiClient.isValidBaseUrl(normalizedUrl) || normalizedToken.isBlank()) return false
        preferences.edit()
            .putString(KEY_SERVER_URL, normalizedUrl)
            .putString(KEY_PAIRING_TOKEN, normalizedToken)
            .putString(KEY_PHONE_NAME, normalizedName)
            .apply()
        return true
    }

    fun clearPairing() {
        preferences.edit().clear().apply()
    }

    companion object {
        const val PREFS_NAME = "phone_to_pc_preferences"
        const val KEY_SERVER_URL = "server_url"
        const val KEY_PAIRING_TOKEN = "pairing_token"
        const val KEY_PHONE_NAME = "phone_name"
        const val DEFAULT_PHONE_NAME = "My Android phone"
    }
}
