package com.yashraj.phonetopc

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

object FileMetadataReader {
    data class PreparedUpload(
        val file: File,
        val displayName: String,
        val mimeType: String
    )

    fun prepare(context: Context, uri: Uri): PreparedUpload {
        val displayName = queryDisplayName(context, uri)
        val mimeType = context.contentResolver.getType(uri) ?: "application/octet-stream"
        val directory = File(context.cacheDir, "phone_to_pc_uploads").apply { mkdirs() }
        val safeName = displayName.replace(Regex("[^A-Za-z0-9._-]"), "_").take(80).ifBlank { "capture.jpg" }
        val target = File(directory, "${System.currentTimeMillis()}_$safeName.part")
        var copied = 0L
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(target).use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        copied += count
                        if (copied > GatewayApiClient.MAX_UPLOAD_BYTES) {
                            throw FileTooLargeException(copied)
                        }
                        output.write(buffer, 0, count)
                    }
                }
            } ?: throw IOException("Cannot read selected file")
            val finalFile = File(directory, target.name.removeSuffix(".part"))
            if (!target.renameTo(finalFile)) throw IOException("Cannot prepare selected file")
            return PreparedUpload(finalFile, displayName, mimeType)
        } catch (error: Exception) {
            target.delete()
            throw error
        }
    }

    private fun queryDisplayName(context: Context, uri: Uri): String {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (index >= 0 && cursor.moveToFirst()) {
                return cursor.getString(index).orEmpty().ifBlank { "capture.jpg" }
            }
        }
        return "capture.jpg"
    }

    class FileTooLargeException(val actualBytes: Long) : IOException(
        "File is larger than ${GatewayApiClient.MAX_UPLOAD_BYTES / (1024 * 1024)} MB"
    )
}
