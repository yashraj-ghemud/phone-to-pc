package com.yashraj.phonetopc

import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

class GatewayApiClient {
    data class HealthResult(val ok: Boolean, val message: String)
    data class UploadResult(val ok: Boolean, val message: String, val serverFilename: String? = null)

    fun checkHealth(baseUrl: String): HealthResult {
        val connection = openConnection("${normalizeBaseUrl(baseUrl)}$API_HEALTH_PATH", "GET")
        return try {
            val status = connection.responseCode
            val body = readBody(connection, status)
            if (status == HttpURLConnection.HTTP_OK) {
                val ok = JSONObject(body).optBoolean("ok", false)
                HealthResult(ok, if (ok) "Connected to PC gateway" else "PC gateway returned an unhealthy status")
            } else {
                HealthResult(false, errorMessage(status))
            }
        } catch (error: Exception) {
            HealthResult(false, readableNetworkError(error))
        } finally {
            connection.disconnect()
        }
    }

    fun uploadFile(
        baseUrl: String,
        token: String,
        phoneName: String,
        file: File,
        displayName: String,
        mimeType: String
    ): UploadResult {
        if (file.length() <= 0L) return UploadResult(false, "Selected file is empty")
        if (file.length() > MAX_UPLOAD_BYTES) return UploadResult(false, "File is larger than 25 MB")
        val encodedName = displayName.replace(Regex("[\\r\\n]"), "_").take(100).ifBlank { "capture.jpg" }
        val connection = openConnection("${normalizeBaseUrl(baseUrl)}$API_UPLOAD_PATH", "POST")
        return try {
            connection.doOutput = true
            connection.setFixedLengthStreamingMode(file.length())
            connection.setRequestProperty(HEADER_PHONE_TOKEN, token)
            connection.setRequestProperty(HEADER_PHONE_NAME, phoneName.take(80))
            connection.setRequestProperty(HEADER_FILENAME, encodedName)
            connection.setRequestProperty("Content-Type", mimeType.ifBlank { "application/octet-stream" })
            file.inputStream().use { input ->
                connection.outputStream.use { output ->
                    input.copyTo(output, DEFAULT_BUFFER_SIZE)
                }
            }
            val status = connection.responseCode
            val body = readBody(connection, status)
            if (status in 200..299) {
                val serverFilename = runCatching {
                    JSONObject(body).optJSONObject("file")?.optString("filename").orEmpty().ifBlank { null }
                }.getOrNull()
                UploadResult(true, "Sent successfully", serverFilename)
            } else {
                UploadResult(false, errorMessage(status))
            }
        } catch (error: Exception) {
            UploadResult(false, readableNetworkError(error))
        } finally {
            connection.disconnect()
        }
    }

    private fun openConnection(url: String, method: String): HttpURLConnection {
        return (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            useCaches = false
            doInput = true
        }
    }

    private fun readBody(connection: HttpURLConnection, status: Int): String {
        val stream = if (status >= 400) connection.errorStream else connection.inputStream
        return stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
    }

    private fun errorMessage(status: Int): String = when (status) {
        HttpURLConnection.HTTP_BAD_REQUEST -> "PC rejected the file (bad request)"
        HttpURLConnection.HTTP_UNAUTHORIZED -> "Wrong pairing token"
        HttpURLConnection.HTTP_NOT_FOUND -> "PC URL or API path is incorrect"
        in 500..599 -> "PC storage/server error (HTTP $status)"
        else -> "PC returned HTTP $status"
    }

    private fun readableNetworkError(error: Exception): String = when (error) {
        is java.net.ConnectException -> "PC gateway is not reachable; check Wi-Fi, IP, and firewall"
        is java.net.SocketTimeoutException -> "PC gateway timed out"
        else -> error.message?.take(120) ?: "Network error"
    }

    companion object {
        const val API_HEALTH_PATH = "/api/v1/health"
        const val API_UPLOAD_PATH = "/api/v1/upload"
        const val HEADER_PHONE_TOKEN = "X-Phone-Token"
        const val HEADER_PHONE_NAME = "X-Phone-Name"
        const val HEADER_FILENAME = "X-Filename"
        const val MAX_UPLOAD_BYTES = 25L * 1024L * 1024L
        private const val CONNECT_TIMEOUT_MS = 8_000
        private const val READ_TIMEOUT_MS = 20_000

        fun normalizeBaseUrl(input: String): String {
            var value = input.trim().removeSuffix("/")
            if (value.endsWith(API_HEALTH_PATH)) value = value.removeSuffix(API_HEALTH_PATH)
            if (value.endsWith(API_UPLOAD_PATH)) value = value.removeSuffix(API_UPLOAD_PATH)
            return value.removeSuffix("/")
        }

        fun isValidBaseUrl(value: String): Boolean {
            return (value.startsWith("http://") || value.startsWith("https://")) &&
                runCatching { URL(value).host.isNotBlank() }.getOrDefault(false)
        }
    }
}
