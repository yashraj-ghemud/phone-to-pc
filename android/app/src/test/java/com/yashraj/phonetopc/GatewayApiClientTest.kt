package com.yashraj.phonetopc

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GatewayApiClientTest {
    @Test
    fun normalizeBaseUrlRemovesTrailingSlashAndKnownApiPaths() {
        assertEquals(
            "http://192.168.43.20:8765",
            GatewayApiClient.normalizeBaseUrl(" http://192.168.43.20:8765/api/v1/upload/ ")
        )
        assertEquals(
            "https://pc.example.test",
            GatewayApiClient.normalizeBaseUrl("https://pc.example.test/api/v1/health")
        )
    }

    @Test
    fun validBaseUrlRequiresHttpSchemeAndHost() {
        assertTrue(GatewayApiClient.isValidBaseUrl("http://192.168.43.20:8765"))
        assertTrue(GatewayApiClient.isValidBaseUrl("https://pc.example.test"))
        assertFalse(GatewayApiClient.isValidBaseUrl("192.168.43.20:8765"))
        assertFalse(GatewayApiClient.isValidBaseUrl("http://"))
    }
}
