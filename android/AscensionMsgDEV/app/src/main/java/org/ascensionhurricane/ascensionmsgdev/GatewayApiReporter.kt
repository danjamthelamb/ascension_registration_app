package org.ascensionhurricane.ascensionmsgdev

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL


data class GatewayApiResult(
    val responseCode: Int,
    val responseBody: String,
) {
    val isSuccess: Boolean
        get() = responseCode in 200..299
}


object GatewayApiReporter {

    fun postRecipientStatus(
        gatewayUrl: String,
        gatewayToken: String,
        recipientId: Long,
        claimToken: String,
        status: String,
        transport: String,
        errorMessage: String? = null,
    ): GatewayApiResult {

        val cleanBaseUrl =
            gatewayUrl
                .trim()
                .trimEnd('/')

        val cleanGatewayToken =
            gatewayToken.trim()

        val cleanClaimToken =
            claimToken.trim()

        require(cleanBaseUrl.isNotBlank()) {
            "Gateway URL is missing."
        }

        require(cleanGatewayToken.isNotBlank()) {
            "Gateway token is missing."
        }

        require(cleanClaimToken.isNotBlank()) {
            "Claim token is missing."
        }

        require(
            status in setOf(
                "submitted",
                "sent",
                "failed",
                "cancelled",
            )
        ) {
            "Unsupported gateway status: $status"
        }

        val url =
            URL(
                "$cleanBaseUrl/gateway/recipients/$recipientId/$status"
            )

        val connection =
            url.openConnection()
                    as HttpURLConnection

        try {

            connection.requestMethod =
                "POST"

            connection.setRequestProperty(
                "Authorization",
                "Bearer $cleanGatewayToken",
            )

            connection.setRequestProperty(
                "Content-Type",
                "application/json",
            )

            connection.connectTimeout =
                3500

            connection.readTimeout =
                3500

            connection.doOutput =
                true

            val body =
                JSONObject()
                    .put(
                        "claim_token",
                        cleanClaimToken,
                    )
                    .put(
                        "transport",
                        transport,
                    )

            if (
                status == "failed"
            ) {

                body.put(
                    "error_message",
                    errorMessage
                        ?.trim()
                        ?.ifBlank {
                            "Unknown Android send failure"
                        }
                        ?: "Unknown Android send failure",
                )
            }

            connection
                .outputStream
                .use { output ->

                    output.write(
                        body
                            .toString()
                            .toByteArray(
                                Charsets.UTF_8
                            )
                    )
                }

            val responseCode =
                connection.responseCode

            val responseBody =

                if (
                    responseCode in 200..299
                ) {

                    connection
                        .inputStream
                        .bufferedReader()
                        .use {
                            it.readText()
                        }

                } else {

                    connection
                        .errorStream
                        ?.bufferedReader()
                        ?.use {
                            it.readText()
                        }
                        ?: ""
                }

            return GatewayApiResult(
                responseCode =
                    responseCode,

                responseBody =
                    responseBody,
            )

        } finally {

            connection.disconnect()
        }
    }
}