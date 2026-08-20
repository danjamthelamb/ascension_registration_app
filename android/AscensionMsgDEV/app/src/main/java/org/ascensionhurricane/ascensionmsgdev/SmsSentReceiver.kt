package org.ascensionhurricane.ascensionmsgdev

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.telephony.SmsManager
import android.util.Log


class SmsSentReceiver : BroadcastReceiver() {

    override fun onReceive(
        context: Context,
        intent: Intent,
    ) {

        val sendId =
            intent.getStringExtra(
                EXTRA_SEND_ID
            )
                ?: return

        val partIndex =
            intent.getIntExtra(
                EXTRA_PART_INDEX,
                0,
            )

        val partCount =
            intent.getIntExtra(
                EXTRA_PART_COUNT,
                1,
            )

        val callbackResult =
            resultCode

        Log.d(
            "SmsSentReceiver",
            "CALLBACK RECEIVED resultCode=$callbackResult " +
                    "sendId=$sendId partIndex=$partIndex expectedParts=$partCount",
        )

        val aggregate =
            SmsStatusStore.recordSentResult(
                sendId = sendId,
                partIndex = partIndex,
                partCount = partCount,
                resultCode = callbackResult,
            )

        if (
            callbackResult != Activity.RESULT_OK
        ) {

            val failureDescription =
                smsResultDescription(
                    callbackResult
                )

            SmsStatusStore.sendStatus =
                "Android reported send failure: $failureDescription"

            SmsStatusStore.gatewayTerminalState =
                "failed"

            reportGatewayTerminalStatusIfPresent(
                intent = intent,
                sendId = sendId,
                status = "failed",
                errorMessage = failureDescription,
            )

            return
        }

        if (
            aggregate.allPartsReceived
            && aggregate.allSuccessful
        ) {

            SmsStatusStore.sendStatus =
                "SMS sent callback received successfully."

            SmsStatusStore.gatewayTerminalState =
                "sent"

            Log.d(
                "SmsSentReceiver",
                "All parts successfully sent for sendId=$sendId",
            )

            reportGatewayTerminalStatusIfPresent(
                intent = intent,
                sendId = sendId,
                status = "sent",
                errorMessage = null,
            )

        } else {

            SmsStatusStore.sendStatus =
                "Waiting for remaining SMS callbacks " +
                        "(${aggregate.receivedParts}/$partCount)..."
        }
    }


    private fun reportGatewayTerminalStatusIfPresent(
        intent: Intent,
        sendId: String,
        status: String,
        errorMessage: String?,
    ) {

        val recipientId =
            intent.getLongExtra(
                EXTRA_GATEWAY_RECIPIENT_ID,
                -1L,
            )

        val claimToken =
            intent.getStringExtra(
                EXTRA_GATEWAY_CLAIM_TOKEN
            )
                .orEmpty()

        val gatewayUrl =
            intent.getStringExtra(
                EXTRA_GATEWAY_URL
            )
                .orEmpty()

        val gatewayToken =
            intent.getStringExtra(
                EXTRA_GATEWAY_TOKEN
            )
                .orEmpty()

        if (
            recipientId <= 0L
            || claimToken.isBlank()
            || gatewayUrl.isBlank()
            || gatewayToken.isBlank()
        ) {
            return
        }

        if (
            !SmsStatusStore
                .markGatewayTerminalReportStarted(
                    sendId
                )
        ) {
            return
        }

        val pendingResult =
            goAsync()

        Thread {

            try {

                val apiResult =
                    GatewayApiReporter
                        .postRecipientStatus(
                            gatewayUrl =
                                gatewayUrl,

                            gatewayToken =
                                gatewayToken,

                            recipientId =
                                recipientId,

                            claimToken =
                                claimToken,

                            status =
                                status,

                            transport =
                                "sms",

                            errorMessage =
                                errorMessage,
                        )

                if (
                    apiResult.isSuccess
                ) {

                    postGatewayStatus(
                        if (
                            status == "sent"
                        ) {
                            "Gateway upgraded this test to SENT."
                        } else {
                            "Gateway recorded the definite send failure."
                        }
                    )

                } else if (
                    apiResult.responseCode == 409
                ) {

                    postGatewayStatus(
                        "Gateway status had already advanced; " +
                                "no resend was attempted."
                    )

                } else {

                    postGatewayStatus(
                        "SMS callback arrived, but gateway reporting " +
                                "returned HTTP ${apiResult.responseCode}. " +
                                "Do not resend automatically."
                    )
                }

            } catch (
                exception: Exception
            ) {

                postGatewayStatus(
                    "SMS callback arrived, but gateway reporting failed: " +
                            "${exception.message ?: "unknown error"}. " +
                            "Do not resend automatically."
                )

                Log.e(
                    "SmsSentReceiver",
                    "Gateway callback report failed",
                    exception,
                )

            } finally {

                pendingResult.finish()
            }

        }.start()
    }


    private fun postGatewayStatus(
        message: String,
    ) {

        Handler(
            Looper.getMainLooper()
        ).post {

            SmsStatusStore.gatewayCallbackStatus =
                message
        }
    }


    private fun smsResultDescription(
        resultCode: Int,
    ): String {

        return when (
            resultCode
        ) {

            SmsManager.RESULT_ERROR_GENERIC_FAILURE ->
                "Generic SMS failure"

            SmsManager.RESULT_ERROR_NO_SERVICE ->
                "No cellular service"

            SmsManager.RESULT_ERROR_NULL_PDU ->
                "Null PDU"

            SmsManager.RESULT_ERROR_RADIO_OFF ->
                "Cellular radio is off"

            else ->
                "SMS result code $resultCode"
        }
    }
}