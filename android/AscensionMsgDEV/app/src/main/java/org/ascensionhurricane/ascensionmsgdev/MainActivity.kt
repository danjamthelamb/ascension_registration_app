package org.ascensionhurricane.ascensionmsgdev

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.telephony.SmsManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import org.ascensionhurricane.ascensionmsgdev.ui.theme.AscensionMsgDEVTheme
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.atomic.AtomicBoolean


const val EXTRA_SEND_ID =
    "send_id"

const val EXTRA_PART_INDEX =
    "part_index"

const val EXTRA_PART_COUNT =
    "part_count"

const val EXTRA_GATEWAY_RECIPIENT_ID =
    "gateway_recipient_id"

const val EXTRA_GATEWAY_CLAIM_TOKEN =
    "gateway_claim_token"

const val EXTRA_GATEWAY_URL =
    "gateway_url"

const val EXTRA_GATEWAY_TOKEN =
    "gateway_token"


data class SmsPartAggregate(
    val receivedParts: Int,
    val allPartsReceived: Boolean,
    val allSuccessful: Boolean,
)


data class GatewayClaimedItem(
    val recipientId: Long,
    val messageId: Long,
    val householdReference: String,
    val contactName: String,
    val phone: String,
    val children: String,
    val messageText: String,
    val claimToken: String,
    val isTest: Boolean,
)


data class GatewayMessageSummary(
    val messageId: Long,
    val messageStatus: String,
    val total: Int,
    val queued: Int,
    val claimed: Int,
    val submitted: Int,
    val sent: Int,
    val failed: Int,
    val cancelled: Int,
) {
    val processed: Int
        get() = submitted + sent + failed + cancelled

    val remaining: Int
        get() = queued + claimed
}


object SmsStatusStore {

    var activeSendId by mutableStateOf("")

    var expectedParts by mutableIntStateOf(0)

    val sentResults =
        mutableStateMapOf<Int, Int>()

    val deliveryResults =
        mutableStateMapOf<Int, Int>()

    var sendStatus by mutableStateOf("")

    var deliveryStatus by mutableStateOf("")

    var gatewayCallbackStatus by mutableStateOf("")

    var gatewayTerminalState by mutableStateOf("")

    var clearMessageSignal by mutableIntStateOf(0)

    private val gatewayTerminalReportsStarted =
        mutableSetOf<String>()

    private val sentResultsBySendId =
        mutableMapOf<String, MutableMap<Int, Int>>()

    private val deliveryResultsBySendId =
        mutableMapOf<String, MutableMap<Int, Int>>()


    @Synchronized
    fun beginSend(
        sendId: String,
        partCount: Int,
    ) {
        activeSendId = sendId
        expectedParts = partCount
        sentResults.clear()
        deliveryResults.clear()
        sentResultsBySendId[
            sendId
        ] = mutableMapOf()
        deliveryResultsBySendId[
            sendId
        ] = mutableMapOf()
        gatewayTerminalReportsStarted.remove(
            sendId
        )
        sendStatus = "Sending..."
        deliveryStatus = ""
        gatewayCallbackStatus = ""
        gatewayTerminalState = ""
    }


    @Synchronized
    fun recordSentResult(
        sendId: String,
        partIndex: Int,
        partCount: Int,
        resultCode: Int,
    ): SmsPartAggregate {

        val perSendResults =
            sentResultsBySendId
                .getOrPut(
                    sendId
                ) {
                    mutableMapOf()
                }

        perSendResults[
            partIndex
        ] = resultCode

        if (
            sendId == activeSendId
        ) {
            expectedParts = partCount
            sentResults[
                partIndex
            ] = resultCode
        }

        val results =
            perSendResults.values.toList()

        return SmsPartAggregate(
            receivedParts = results.size,
            allPartsReceived = (
                    results.size >= partCount
                    ),
            allSuccessful = (
                    results.isNotEmpty()
                            && results.all {
                        it == Activity.RESULT_OK
                    }
                    ),
        )
    }


    @Synchronized
    fun recordDeliveryResult(
        sendId: String,
        partIndex: Int,
        partCount: Int,
        resultCode: Int,
    ): SmsPartAggregate {

        val perSendResults =
            deliveryResultsBySendId
                .getOrPut(
                    sendId
                ) {
                    mutableMapOf()
                }

        perSendResults[
            partIndex
        ] = resultCode

        if (
            sendId == activeSendId
        ) {
            expectedParts = partCount
            deliveryResults[
                partIndex
            ] = resultCode
        }

        val results =
            perSendResults.values.toList()

        return SmsPartAggregate(
            receivedParts = results.size,
            allPartsReceived = (
                    results.size >= partCount
                    ),
            allSuccessful = (
                    results.isNotEmpty()
                            && results.all {
                        it == Activity.RESULT_OK
                    }
                    ),
        )
    }


    @Synchronized
    fun markGatewayTerminalReportStarted(
        sendId: String,
    ): Boolean {

        if (
            gatewayTerminalReportsStarted.contains(
                sendId
            )
        ) {
            return false
        }

        gatewayTerminalReportsStarted.add(
            sendId
        )

        return true
    }
}


class MainActivity : ComponentActivity() {

    override fun onCreate(
        savedInstanceState: Bundle?
    ) {

        super.onCreate(
            savedInstanceState
        )

        enableEdgeToEdge()

        setContent {

            AscensionMsgDEVTheme {

                Scaffold(
                    modifier =
                        Modifier.fillMaxSize()
                ) { innerPadding ->

                    MessengerScreen(
                        modifier =
                            Modifier
                                .padding(
                                    innerPadding
                                )
                                .padding(
                                    24.dp
                                )
                    )
                }
            }
        }
    }
}


@Composable
fun MessengerScreen(
    modifier: Modifier = Modifier
) {

    val context =
        LocalContext.current


    // =====================================================
    // Gateway state
    // =====================================================

    var gatewayUrl by rememberSaveable {
        mutableStateOf(
            "http://192.168.4.46:8001"
        )
    }

    var gatewayToken by rememberSaveable {
        mutableStateOf("")
    }

    var gatewayStatus by rememberSaveable {
        mutableStateOf("")
    }

    var pendingLocalNetworkAction by rememberSaveable {
        mutableStateOf("")
    }


    // =====================================================
    // Claimed DEV test
    // =====================================================

    var fetchedRecipientId by rememberSaveable {
        mutableStateOf<Long?>(
            null
        )
    }

    var fetchedMessageId by rememberSaveable {
        mutableStateOf<Long?>(
            null
        )
    }

    var fetchedHousehold by rememberSaveable {
        mutableStateOf("")
    }

    var fetchedContact by rememberSaveable {
        mutableStateOf("")
    }

    var fetchedPhone by rememberSaveable {
        mutableStateOf("")
    }

    var fetchedChildren by rememberSaveable {
        mutableStateOf("")
    }

    var fetchedMessage by rememberSaveable {
        mutableStateOf("")
    }

    var fetchedClaimToken by rememberSaveable {
        mutableStateOf("")
    }

    var fetchedIsTest by rememberSaveable {
        mutableStateOf(false)
    }

    var fetchedSendState by rememberSaveable {
        mutableStateOf("")
    }


    // =====================================================
    // Controlled household batch
    // =====================================================

    var batchRunning by rememberSaveable {
        mutableStateOf(false)
    }

    var batchStopRequested by rememberSaveable {
        mutableStateOf(false)
    }

    var batchMessageId by rememberSaveable {
        mutableStateOf<Long?>(null)
    }

    var batchStatus by rememberSaveable {
        mutableStateOf("")
    }

    var batchTotal by rememberSaveable {
        mutableIntStateOf(0)
    }

    var batchQueued by rememberSaveable {
        mutableIntStateOf(0)
    }

    var batchClaimed by rememberSaveable {
        mutableIntStateOf(0)
    }

    var batchSubmitted by rememberSaveable {
        mutableIntStateOf(0)
    }

    var batchSent by rememberSaveable {
        mutableIntStateOf(0)
    }

    var batchFailed by rememberSaveable {
        mutableIntStateOf(0)
    }

    val batchStopSignal = remember {
        AtomicBoolean(false)
    }


    // =====================================================
    // Existing manual SMS diagnostics
    // =====================================================

    var phoneNumber by rememberSaveable {
        mutableStateOf("")
    }

    var message by rememberSaveable {
        mutableStateOf("")
    }

    val sendStatus =
        SmsStatusStore.sendStatus

    val deliveryStatus =
        SmsStatusStore.deliveryStatus

    val gatewayCallbackStatus =
        SmsStatusStore.gatewayCallbackStatus

    val gatewayTerminalState =
        SmsStatusStore.gatewayTerminalState

    val clearSignal =
        SmsStatusStore.clearMessageSignal

    LaunchedEffect(
        clearSignal
    ) {
        if (
            clearSignal > 0
        ) {
            message = ""
        }
    }

    // Keep the screen-level queue state synchronized with the
    // transport callback. Without this, a successful SMS can
    // remain visually stuck in HANDED_OFF and block the next claim.
    LaunchedEffect(
        gatewayTerminalState
    ) {
        if (
            !batchRunning
            && fetchedRecipientId != null
            && gatewayTerminalState in listOf(
                "sent",
                "failed",
            )
        ) {
            fetchedSendState =
                gatewayTerminalState
        }
    }

    // =====================================================
    // Helpers
    // =====================================================

    fun runOnUi(
        block: () -> Unit
    ) {
        (context as Activity)
            .runOnUiThread {
                block()
            }
    }


    fun clearFetchedItem() {
        fetchedRecipientId = null
        fetchedMessageId = null
        fetchedHousehold = ""
        fetchedContact = ""
        fetchedPhone = ""
        fetchedChildren = ""
        fetchedMessage = ""
        fetchedClaimToken = ""
        fetchedIsTest = false
        fetchedSendState = ""
        SmsStatusStore.sendStatus = ""
        SmsStatusStore.deliveryStatus = ""
        SmsStatusStore.gatewayCallbackStatus = ""
        SmsStatusStore.gatewayTerminalState = ""
    }



    fun applyFetchedItem(
        item: GatewayClaimedItem,
    ) {
        fetchedRecipientId =
            item.recipientId
        fetchedMessageId =
            item.messageId
        fetchedHousehold =
            item.householdReference
        fetchedContact =
            item.contactName
        fetchedPhone =
            item.phone
        fetchedChildren =
            item.children
        fetchedMessage =
            item.messageText
        fetchedClaimToken =
            item.claimToken
        fetchedIsTest =
            item.isTest
        fetchedSendState =
            "claimed"
    }


    fun currentFetchedItem(): GatewayClaimedItem? {

        val recipientId =
            fetchedRecipientId
                ?: return null

        val messageId =
            fetchedMessageId
                ?: return null

        return GatewayClaimedItem(
            recipientId = recipientId,
            messageId = messageId,
            householdReference = fetchedHousehold,
            contactName = fetchedContact,
            phone = fetchedPhone,
            children = fetchedChildren,
            messageText = fetchedMessage,
            claimToken = fetchedClaimToken,
            isTest = fetchedIsTest,
        )
    }


    fun updateBatchSummary(
        summary: GatewayMessageSummary,
    ) {
        batchMessageId =
            summary.messageId
        batchTotal =
            summary.total
        batchQueued =
            summary.queued
        batchClaimed =
            summary.claimed
        batchSubmitted =
            summary.submitted
        batchSent =
            summary.sent
        batchFailed =
            summary.failed
    }


    fun parseClaimedItem(
        recipient: JSONObject,
    ): GatewayClaimedItem {

        return GatewayClaimedItem(
            recipientId =
                recipient.getLong(
                    "recipient_id"
                ),
            messageId =
                recipient.getLong(
                    "message_id"
                ),
            householdReference =
                recipient.optString(
                    "household_reference"
                ),
            contactName =
                recipient.optString(
                    "contact_name"
                ),
            phone =
                recipient.optString(
                    "phone"
                ),
            children =
                recipient.optString(
                    "children"
                ),
            messageText =
                recipient.optString(
                    "message_text"
                ),
            claimToken =
                recipient.optString(
                    "claim_token"
                ),
            isTest =
                recipient.optBoolean(
                    "is_test",
                    false,
                ),
        )
    }


    fun claimNextForMessageBlocking(
        messageId: Long,
    ): GatewayClaimedItem? {

        val cleanBaseUrl =
            gatewayUrl
                .trim()
                .trimEnd('/')

        val cleanToken =
            gatewayToken.trim()

        val url =
            URL(
                "$cleanBaseUrl/gateway/messages/$messageId/claim-next"
            )

        val connection =
            url.openConnection()
                    as HttpURLConnection

        try {
            connection.requestMethod =
                "POST"

            connection.setRequestProperty(
                "Authorization",
                "Bearer $cleanToken",
            )

            connection.setRequestProperty(
                "Content-Type",
                "application/json",
            )

            connection.connectTimeout =
                5000

            connection.readTimeout =
                5000

            connection.doOutput =
                true

            connection
                .outputStream
                .use {
                    it.write(
                        "{}"
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

            if (
                responseCode !in 200..299
            ) {
                throw IllegalStateException(
                    "Same-message claim returned HTTP $responseCode."
                )
            }

            val root =
                JSONObject(
                    responseBody
                )

            if (
                root.isNull(
                    "recipient"
                )
            ) {
                return null
            }

            return parseClaimedItem(
                root.getJSONObject(
                    "recipient"
                )
            )

        } finally {
            connection.disconnect()
        }
    }


    fun fetchRecipientStatusBlocking(
        item: GatewayClaimedItem,
    ): String? {

        val cleanBaseUrl =
            gatewayUrl
                .trim()
                .trimEnd('/')

        val cleanToken =
            gatewayToken.trim()

        val url =
            URL(
                "$cleanBaseUrl/gateway/recipients/${item.recipientId}/status"
            )

        val connection =
            url.openConnection()
                    as HttpURLConnection

        try {
            connection.requestMethod =
                "POST"

            connection.setRequestProperty(
                "Authorization",
                "Bearer $cleanToken",
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
                        item.claimToken,
                    )

            connection
                .outputStream
                .use {
                    it.write(
                        body
                            .toString()
                            .toByteArray(
                                Charsets.UTF_8
                            )
                    )
                }

            val responseCode =
                connection.responseCode

            if (
                responseCode !in 200..299
            ) {
                return null
            }

            val responseBody =
                connection
                    .inputStream
                    .bufferedReader()
                    .use {
                        it.readText()
                    }

            val root =
                JSONObject(
                    responseBody
                )

            return root
                .getJSONObject(
                    "recipient"
                )
                .optString(
                    "status"
                )
                .ifBlank {
                    null
                }

        } finally {
            connection.disconnect()
        }
    }


    fun fetchMessageSummaryBlocking(
        messageId: Long,
    ): GatewayMessageSummary? {

        val cleanBaseUrl =
            gatewayUrl
                .trim()
                .trimEnd('/')

        val cleanToken =
            gatewayToken.trim()

        val url =
            URL(
                "$cleanBaseUrl/gateway/messages/$messageId/summary"
            )

        val connection =
            url.openConnection()
                    as HttpURLConnection

        try {
            connection.requestMethod =
                "GET"

            connection.setRequestProperty(
                "Authorization",
                "Bearer $cleanToken",
            )

            connection.connectTimeout =
                3500

            connection.readTimeout =
                3500

            val responseCode =
                connection.responseCode

            if (
                responseCode !in 200..299
            ) {
                return null
            }

            val responseBody =
                connection
                    .inputStream
                    .bufferedReader()
                    .use {
                        it.readText()
                    }

            val messageJson =
                JSONObject(
                    responseBody
                )
                    .getJSONObject(
                        "message"
                    )

            return GatewayMessageSummary(
                messageId =
                    messageJson.getLong(
                        "message_id"
                    ),
                messageStatus =
                    messageJson.optString(
                        "status"
                    ),
                total =
                    messageJson.optInt(
                        "total",
                        0,
                    ),
                queued =
                    messageJson.optInt(
                        "queued",
                        0,
                    ),
                claimed =
                    messageJson.optInt(
                        "claimed",
                        0,
                    ),
                submitted =
                    messageJson.optInt(
                        "submitted",
                        0,
                    ),
                sent =
                    messageJson.optInt(
                        "sent",
                        0,
                    ),
                failed =
                    messageJson.optInt(
                        "failed",
                        0,
                    ),
                cancelled =
                    messageJson.optInt(
                        "cancelled",
                        0,
                    ),
            )

        } finally {
            connection.disconnect()
        }
    }


    data class SmsHandoffResult(
        val sendId: String?,
        val error: String?,
    )


    fun handoffBatchSmsBlocking(
        item: GatewayClaimedItem,
    ): SmsHandoffResult {

        val latch =
            CountDownLatch(1)

        var result =
            SmsHandoffResult(
                sendId = null,
                error = "SMS handoff did not run.",
            )

        (context as Activity)
            .runOnUiThread {

                try {
                    val smsManager =
                        getSmsManager(
                            context
                        )

                    val messageParts =
                        smsManager.divideMessage(
                            item.messageText
                        )

                    val sendId =
                        UUID
                            .randomUUID()
                            .toString()

                    SmsStatusStore.beginSend(
                        sendId = sendId,
                        partCount = messageParts.size,
                    )

                    sendSms(
                        context = context,
                        smsManager = smsManager,
                        phoneNumber = item.phone,
                        messageParts = messageParts,
                        sendId = sendId,
                        gatewayRecipientId = item.recipientId,
                        gatewayClaimToken = item.claimToken,
                        gatewayUrl = gatewayUrl.trim().trimEnd('/'),
                        gatewayToken = gatewayToken.trim(),
                    )

                    result =
                        SmsHandoffResult(
                            sendId = sendId,
                            error = null,
                        )

                } catch (
                    exception: Exception
                ) {
                    result =
                        SmsHandoffResult(
                            sendId = null,
                            error =
                                exception.message
                                    ?: "Unknown Android send failure",
                        )

                } finally {
                    latch.countDown()
                }
            }

        latch.await()

        return result
    }


    fun startHouseholdBatchNow() {

        val firstItem =
            currentFetchedItem()
                ?: run {
                    gatewayStatus =
                        "Fetch and review one claimed household before starting a batch."
                    return
                }

        if (
            firstItem.isTest
            || fetchedSendState != "claimed"
            || firstItem.phone.isBlank()
            || firstItem.messageText.isBlank()
            || firstItem.claimToken.isBlank()
        ) {
            gatewayStatus =
                "Fetch and review one claimed household before starting a batch."
            return
        }

        if (
            gatewayToken.isBlank()
            || gatewayUrl.isBlank()
        ) {
            gatewayStatus =
                "Gateway URL and token are required before starting a batch."
            return
        }

        val targetMessageId =
            firstItem.messageId

        batchStopSignal.set(
            false
        )

        batchStopRequested =
            false

        batchRunning =
            true

        batchMessageId =
            targetMessageId

        batchStatus =
            "Starting Message #$targetMessageId batch..."

        Thread {

            var currentItem =
                firstItem

            try {

                fetchMessageSummaryBlocking(
                    targetMessageId
                )?.let { summary ->
                    runOnUi {
                        updateBatchSummary(
                            summary
                        )
                    }
                }

                while (
                    true
                ) {

                    runOnUi {
                        applyFetchedItem(
                            currentItem
                        )

                        fetchedSendState =
                            "sending"

                        batchStatus =
                            "Sending ${currentItem.contactName}..."
                    }

                    val handoff =
                        handoffBatchSmsBlocking(
                            currentItem
                        )

                    if (
                        handoff.error != null
                    ) {
                        val failedResult =
                            try {
                                GatewayApiReporter
                                    .postRecipientStatus(
                                        gatewayUrl = gatewayUrl,
                                        gatewayToken = gatewayToken,
                                        recipientId = currentItem.recipientId,
                                        claimToken = currentItem.claimToken,
                                        status = "failed",
                                        transport = "android_batch",
                                        errorMessage = handoff.error,
                                    )
                            } catch (
                                exception: Exception
                            ) {
                                null
                            }

                        runOnUi {
                            fetchedSendState =
                                "failed"

                            batchRunning =
                                false

                            batchStatus =
                                if (
                                    failedResult?.isSuccess == true
                                ) {
                                    "Batch stopped: Android rejected the current send before handoff. FAILED was recorded."
                                } else {
                                    "Batch stopped: Android rejected the current send before handoff, and failure reporting could not be confirmed. Verify Streamlit before continuing."
                                }
                        }

                        break
                    }

                    runOnUi {
                        fetchedSendState =
                            "handed_off"

                        gatewayStatus =
                            "Android accepted ${currentItem.contactName}. Recording SUBMITTED before the batch may advance."
                    }

                    val submittedResult =
                        try {
                            GatewayApiReporter
                                .postRecipientStatus(
                                    gatewayUrl = gatewayUrl,
                                    gatewayToken = gatewayToken,
                                    recipientId = currentItem.recipientId,
                                    claimToken = currentItem.claimToken,
                                    status = "submitted",
                                    transport = "android_batch",
                                )
                        } catch (
                            exception: Exception
                        ) {
                            null
                        }

                    // Do not stop the batch merely because the SUBMITTED POST
                    // itself returned an error or lost its response. A normal
                    // SMS sent callback may already have advanced this same
                    // recipient to SENT. Instead, verify the recipient's
                    // authoritative database state before deciding whether it
                    // is safe to continue.
                    val submittedPostConfirmed =
                        submittedResult?.isSuccess == true

                    if (
                        !submittedPostConfirmed
                    ) {
                        runOnUi {
                            batchStatus =
                                when {
                                    submittedResult == null ->
                                        "SUBMITTED report was interrupted. Checking the gateway's recorded recipient state before deciding whether the batch may continue..."

                                    else ->
                                        "SUBMITTED report returned HTTP ${submittedResult.responseCode}. Checking the gateway's recorded recipient state before deciding whether the batch may continue..."
                                }
                        }
                    }

                    // Give the normal SMS callback a short opportunity to
                    // upgrade SUBMITTED to SENT or report a definite failure.
                    // RCS may never produce that callback, so after five
                    // seconds a database-confirmed SUBMITTED is allowed to
                    // advance. If the initial SUBMITTED POST was not confirmed,
                    // this polling step must observe SUBMITTED or SENT before
                    // another household can ever be claimed.
                    val waitStarted =
                        System.currentTimeMillis()

                    var observedStatus =
                        if (
                            submittedPostConfirmed
                        ) {
                            "submitted"
                        } else {
                            "unknown"
                        }

                    while (
                        System.currentTimeMillis()
                        - waitStarted
                        < 5000L
                    ) {
                        Thread.sleep(
                            250L
                        )

                        val serverStatus =
                            fetchRecipientStatusBlocking(
                                currentItem
                            )

                        if (
                            serverStatus != null
                        ) {
                            observedStatus =
                                serverStatus
                        }

                        val elapsed =
                            System.currentTimeMillis()
                            - waitStarted

                        if (
                            observedStatus == "failed"
                        ) {
                            break
                        }

                        if (
                            observedStatus == "sent"
                            && elapsed >= 2000L
                        ) {
                            break
                        }
                    }

                    // One final status read immediately before considering
                    // another claim reduces the chance that a late definite
                    // SMS failure is missed.
                    fetchRecipientStatusBlocking(
                        currentItem
                    )?.let {
                        observedStatus =
                            it
                    }

                    if (
                        observedStatus == "failed"
                    ) {
                        fetchMessageSummaryBlocking(
                            targetMessageId
                        )?.let { summary ->
                            runOnUi {
                                updateBatchSummary(
                                    summary
                                )
                            }
                        }

                        runOnUi {
                            fetchedSendState =
                                "failed"

                            batchRunning =
                                false

                            batchStatus =
                                "Batch stopped on a definite send failure for ${currentItem.contactName}. No next household was claimed."
                        }

                        break
                    }

                    if (
                        observedStatus !in listOf(
                            "submitted",
                            "sent",
                        )
                    ) {
                        runOnUi {
                            batchRunning =
                                false

                            fetchedSendState =
                                "handed_off"

                            batchStatus =
                                if (
                                    observedStatus == "unknown"
                                ) {
                                    "Batch safety stop: Android handed off the current message, but the gateway never confirmed SUBMITTED or SENT. Do not resend it. Verify Streamlit before continuing."
                                } else {
                                    "Batch safety stop: the current recipient is in an unexpected gateway state ($observedStatus). Verify Streamlit before continuing."
                                }
                        }

                        break
                    }

                    val summaryAfterSend =
                        fetchMessageSummaryBlocking(
                            targetMessageId
                        )

                    if (
                        summaryAfterSend != null
                    ) {
                        runOnUi {
                            updateBatchSummary(
                                summaryAfterSend
                            )
                        }
                    }

                    runOnUi {
                        fetchedSendState =
                            observedStatus

                        batchStatus =
                            if (
                                observedStatus == "sent"
                            ) {
                                "${currentItem.contactName} is SENT."
                            } else {
                                "${currentItem.contactName} is SUBMITTED. No automatic retry will occur."
                            }
                    }

                    if (
                        batchStopSignal.get()
                    ) {
                        runOnUi {
                            batchRunning =
                                false

                            batchStopRequested =
                                false

                            batchStatus =
                                "Batch stopped after the current household as requested. No next household was claimed."
                        }

                        break
                    }

                    val nextItem =
                        claimNextForMessageBlocking(
                            targetMessageId
                        )

                    if (
                        nextItem == null
                    ) {
                        val finalSummary =
                            fetchMessageSummaryBlocking(
                                targetMessageId
                            )

                        runOnUi {
                            if (
                                finalSummary != null
                            ) {
                                updateBatchSummary(
                                    finalSummary
                                )
                            }

                            batchRunning =
                                false

                            batchStopRequested =
                                false

                            batchStatus =
                                if (
                                    finalSummary != null
                                    && finalSummary.remaining == 0
                                    && finalSummary.failed == 0
                                ) {
                                    "Message #$targetMessageId batch complete."
                                } else {
                                    "Batch paused: there is no additional claimable recipient for Message #$targetMessageId. Check Streamlit before continuing."
                                }
                        }

                        break
                    }

                    // If Stop After Current races with the claim request,
                    // immediately release the newly claimed item rather than
                    // sending it.
                    if (
                        batchStopSignal.get()
                    ) {
                        try {
                            GatewayApiReporter
                                .postRecipientStatus(
                                    gatewayUrl = gatewayUrl,
                                    gatewayToken = gatewayToken,
                                    recipientId = nextItem.recipientId,
                                    claimToken = nextItem.claimToken,
                                    status = "released",
                                    transport = "android_batch",
                                )
                        } catch (
                            exception: Exception
                        ) {
                            runOnUi {
                                applyFetchedItem(
                                    nextItem
                                )

                                fetchedSendState =
                                    "release_unknown"
                            }
                        }

                        runOnUi {
                            batchRunning =
                                false

                            batchStopRequested =
                                false

                            batchStatus =
                                "Batch stopped after the current household. A raced next claim was released without sending."
                        }

                        break
                    }

                    currentItem =
                        nextItem
                }

            } catch (
                exception: Exception
            ) {
                runOnUi {
                    batchRunning =
                        false

                    batchStatus =
                        "Batch safety stop: ${
                            exception.message
                                ?: "Unknown error"
                        }. Verify Streamlit before continuing."
                }
            }

        }.start()
    }


    fun hasLocalNetworkPermission(): Boolean {

        if (
            Build.VERSION.SDK_INT < 37
        ) {
            return true
        }

        return ContextCompat
            .checkSelfPermission(
                context,
                Manifest.permission.ACCESS_LOCAL_NETWORK
            ) ==
                PackageManager.PERMISSION_GRANTED
    }


    // =====================================================
    // Gateway health
    // =====================================================

    fun testGatewayNow() {

        gatewayStatus =
            "Testing gateway..."

        Thread {

            try {

                val cleanBaseUrl =
                    gatewayUrl
                        .trim()
                        .trimEnd('/')

                val url =
                    URL(
                        "$cleanBaseUrl/health"
                    )

                val connection =
                    url.openConnection()
                            as HttpURLConnection

                try {
                    connection.requestMethod =
                        "GET"

                    connection.connectTimeout =
                        5000

                    connection.readTimeout =
                        5000

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

                    val finalMessage =
                        if (
                            responseCode in 200..299
                        ) {
                            try {
                                val json =
                                    JSONObject(
                                        responseBody
                                    )

                                val service =
                                    json.optString(
                                        "service",
                                        "Gateway"
                                    )

                                "Connected to $service."

                            } catch (
                                exception: Exception
                            ) {
                                "Gateway connected successfully."
                            }
                        } else {
                            "Gateway returned HTTP $responseCode."
                        }

                    runOnUi {
                        gatewayStatus =
                            finalMessage
                    }

                } finally {
                    connection.disconnect()
                }

            } catch (
                exception: Exception
            ) {
                runOnUi {
                    gatewayStatus =
                        "Gateway connection failed: ${
                            exception.message
                                ?: "Unknown error"
                        }"
                }
            }

        }.start()
    }


    // =====================================================
    // Fetch one queued gateway recipient
    // =====================================================

    fun fetchQueuedItemNow(
        endpoint: String,
        expectedTest: Boolean,
        emptyMessage: String,
    ) {

        val cleanToken =
            gatewayToken.trim()

        if (
            cleanToken.isBlank()
        ) {
            gatewayStatus =
                "Enter the gateway token first."
            return
        }

        if (
            batchRunning
            || (
                fetchedRecipientId != null
                && fetchedSendState in listOf(
                "claimed",
                "cancelling",
                "cancel_unknown",
                "releasing",
                "release_unknown",
                "sending",
                "handed_off",
            )
            )
        ) {
            gatewayStatus =
                "Finish the currently claimed item before fetching another."
            return
        }

        gatewayStatus =
            if (
                expectedTest
            ) {
                "Fetching next queued DEV test..."
            } else {
                "Fetching next queued household..."
            }

        Thread {

            try {

                val cleanBaseUrl =
                    gatewayUrl
                        .trim()
                        .trimEnd('/')

                val url =
                    URL(
                        "$cleanBaseUrl$endpoint"
                    )

                val connection =
                    url.openConnection()
                            as HttpURLConnection

                try {

                    connection.requestMethod =
                        "POST"

                    connection.setRequestProperty(
                        "Authorization",
                        "Bearer $cleanToken"
                    )

                    connection.setRequestProperty(
                        "Content-Type",
                        "application/json"
                    )

                    connection.connectTimeout =
                        5000

                    connection.readTimeout =
                        5000

                    connection.doOutput =
                        true

                    connection
                        .outputStream
                        .use {
                            it.write(
                                "{}"
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

                    if (
                        responseCode !in 200..299
                    ) {
                        runOnUi {
                            gatewayStatus =
                                "Gateway returned HTTP $responseCode."
                        }
                        return@Thread
                    }

                    val root =
                        JSONObject(
                            responseBody
                        )

                    if (
                        root.isNull(
                            "recipient"
                        )
                    ) {
                        runOnUi {
                            clearFetchedItem()
                            gatewayStatus =
                                emptyMessage
                        }
                        return@Thread
                    }

                    val recipient =
                        root.getJSONObject(
                            "recipient"
                        )

                    val recipientId =
                        recipient.getLong(
                            "recipient_id"
                        )

                    val messageId =
                        recipient.getLong(
                            "message_id"
                        )

                    val householdReference =
                        recipient.optString(
                            "household_reference"
                        )

                    val contactName =
                        recipient.optString(
                            "contact_name"
                        )

                    val phone =
                        recipient.optString(
                            "phone"
                        )

                    val children =
                        recipient.optString(
                            "children"
                        )

                    val messageText =
                        recipient.optString(
                            "message_text"
                        )

                    val claimToken =
                        recipient.optString(
                            "claim_token"
                        )

                    val isTest =
                        recipient.optBoolean(
                            "is_test",
                            false
                        )

                    runOnUi {

                        clearFetchedItem()

                        fetchedRecipientId =
                            recipientId

                        fetchedMessageId =
                            messageId

                        fetchedHousehold =
                            householdReference

                        fetchedContact =
                            contactName

                        fetchedPhone =
                            phone

                        fetchedChildren =
                            children

                        fetchedMessage =
                            messageText

                        fetchedClaimToken =
                            claimToken

                        fetchedIsTest =
                            isTest

                        fetchedSendState =
                            "claimed"

                        gatewayStatus =
                            when {

                                expectedTest
                                && isTest ->
                                    "DEV test claimed successfully. Nothing has been sent yet."

                                !expectedTest
                                && !isTest ->
                                    "Household claimed successfully. Nothing has been sent yet."

                                isTest ->
                                    "Safety notice: the household endpoint returned a DEV test. Review it as a test before taking any action."

                                else ->
                                    "Safety notice: the DEV test endpoint returned a real household. Review it as a household before taking any action."
                            }
                    }

                } finally {
                    connection.disconnect()
                }

            } catch (
                exception: Exception
            ) {
                runOnUi {
                    gatewayStatus =
                        "Fetch failed: ${
                            exception.message
                                ?: "Unknown error"
                        }"
                }
            }

        }.start()
    }


    fun fetchNextQueuedTestNow() {

        fetchQueuedItemNow(
            endpoint =
                "/gateway/claim-next-test",

            expectedTest =
                true,

            emptyMessage =
                "No queued DEV tests are waiting.",
        )
    }


    fun fetchNextQueuedHouseholdNow() {

        fetchQueuedItemNow(
            endpoint =
                "/gateway/claim-next",

            expectedTest =
                false,

            emptyMessage =
                "No queued household messages are waiting.",
        )
    }


    // =====================================================
    // Cancel claimed DEV test from the owning Pixel
    // =====================================================

    fun cancelFetchedTestNow() {

        val recipientId =
            fetchedRecipientId

        if (
            recipientId == null
            || fetchedClaimToken.isBlank()
            || !fetchedIsTest
            || fetchedSendState != "claimed"
        ) {
            gatewayStatus =
                "There is no active claimed DEV test to cancel."
            return
        }

        fetchedSendState =
            "cancelling"

        gatewayStatus =
            "Cancelling claimed DEV test..."

        Thread {

            try {

                val apiResult =
                    GatewayApiReporter
                        .postRecipientStatus(
                            gatewayUrl = gatewayUrl,
                            gatewayToken = gatewayToken,
                            recipientId = recipientId,
                            claimToken = fetchedClaimToken,
                            status = "cancelled",
                            transport = "android_manual",
                        )

                runOnUi {

                    if (
                        apiResult.isSuccess
                    ) {
                        fetchedSendState =
                            "cancelled"

                        gatewayStatus =
                            "DEV test cancelled. It will not be sent or returned to the queue."

                    } else {
                        fetchedSendState =
                            "cancel_unknown"

                        gatewayStatus =
                            "Cancel returned HTTP ${apiResult.responseCode}. Do not send this item until you verify its status in Streamlit."
                    }
                }

            } catch (
                exception: Exception
            ) {
                runOnUi {
                    fetchedSendState =
                        "cancel_unknown"

                    gatewayStatus =
                        "Cancel failed: ${
                            exception.message
                                ?: "Unknown error"
                        }. Do not send this item until you verify its status in Streamlit."
                }
            }

        }.start()
    }


    // =====================================================
    // Release a claimed real household without sending
    // =====================================================

    fun releaseFetchedHouseholdNow() {

        val recipientId =
            fetchedRecipientId

        if (
            recipientId == null
            || fetchedClaimToken.isBlank()
            || fetchedIsTest
            || fetchedSendState != "claimed"
        ) {
            gatewayStatus =
                "There is no active claimed household to release."
            return
        }

        fetchedSendState =
            "releasing"

        gatewayStatus =
            "Releasing household back to the queue..."

        Thread {

            try {

                val apiResult =
                    GatewayApiReporter
                        .postRecipientStatus(
                            gatewayUrl = gatewayUrl,
                            gatewayToken = gatewayToken,
                            recipientId = recipientId,
                            claimToken = fetchedClaimToken,
                            status = "released",
                            transport = "android_manual",
                        )

                runOnUi {

                    if (
                        apiResult.isSuccess
                    ) {
                        clearFetchedItem()

                        gatewayStatus =
                            "Household released without sending. It is queued again and may be claimed later."

                    } else {
                        fetchedSendState =
                            "release_unknown"

                        gatewayStatus =
                            "Release returned HTTP ${apiResult.responseCode}. Do not send this item until you verify its status in Streamlit."
                    }
                }

            } catch (
                exception: Exception
            ) {
                runOnUi {
                    fetchedSendState =
                        "release_unknown"

                    gatewayStatus =
                        "Release failed: ${
                            exception.message
                                ?: "Unknown error"
                        }. Do not send this item until you verify its status in Streamlit."
                }
            }

        }.start()
    }


    // =====================================================
    // Send the currently claimed gateway item
    // =====================================================

    fun sendFetchedClaimNow() {

        val recipientId =
            fetchedRecipientId

        val cleanPhone =
            fetchedPhone.trim()

        val cleanMessage =
            fetchedMessage.trim()

        val cleanClaimToken =
            fetchedClaimToken.trim()

        val cleanGatewayToken =
            gatewayToken.trim()

        val cleanGatewayUrl =
            gatewayUrl
                .trim()
                .trimEnd('/')

        if (
            recipientId == null
            || fetchedSendState != "claimed"
            || cleanPhone.isBlank()
            || cleanMessage.isBlank()
            || cleanClaimToken.isBlank()
            || cleanGatewayToken.isBlank()
            || cleanGatewayUrl.isBlank()
        ) {
            gatewayStatus =
                "This message is not in a safe claimed state for sending."
            return
        }

        val itemLabel =
            if (
                fetchedIsTest
            ) {
                "DEV test"
            } else {
                "household message"
            }

        // Disable release/cancel immediately while Android is
        // attempting the handoff.
        fetchedSendState =
            "sending"

        try {

            val smsManager =
                getSmsManager(
                    context
                )

            val messageParts =
                smsManager.divideMessage(
                    cleanMessage
                )

            val sendId =
                UUID
                    .randomUUID()
                    .toString()

            SmsStatusStore.beginSend(
                sendId = sendId,
                partCount = messageParts.size,
            )

            sendSms(
                context = context,
                smsManager = smsManager,
                phoneNumber = cleanPhone,
                messageParts = messageParts,
                sendId = sendId,
                gatewayRecipientId = recipientId,
                gatewayClaimToken = cleanClaimToken,
                gatewayUrl = cleanGatewayUrl,
                gatewayToken = cleanGatewayToken,
            )

            // Important safety rule: once SmsManager accepts the call,
            // this item is no longer eligible for manual resend or release,
            // even if the API status report below fails. RCS may take over
            // and never return the normal SMS sent PendingIntent.
            fetchedSendState =
                "handed_off"

            SmsStatusStore.sendStatus =
                "Android accepted the send request. Waiting for gateway status report..."

            gatewayStatus =
                "Android accepted the $itemLabel. It will not be automatically retried."

            Thread {

                try {

                    val apiResult =
                        GatewayApiReporter
                            .postRecipientStatus(
                                gatewayUrl = cleanGatewayUrl,
                                gatewayToken = cleanGatewayToken,
                                recipientId = recipientId,
                                claimToken = cleanClaimToken,
                                status = "submitted",
                                transport = "android_auto",
                            )

                    runOnUi {

                        val callbackTerminalState =
                            SmsStatusStore.gatewayTerminalState

                        if (
                            callbackTerminalState in listOf(
                                "sent",
                                "failed",
                            )
                        ) {
                            // A transport callback is stronger than the
                            // earlier SUBMITTED handoff. Never downgrade a
                            // terminal local result back to HANDED_OFF.
                            fetchedSendState =
                                callbackTerminalState

                            gatewayStatus =
                                if (
                                    callbackTerminalState == "sent"
                                ) {
                                    "SMS send callback completed. This item is terminal and will not be resent."
                                } else {
                                    "Android reported a definite send failure. This item is terminal and will not be retried automatically."
                                }

                        } else if (
                            apiResult.isSuccess
                        ) {
                            fetchedSendState =
                                "submitted"

                            gatewayStatus =
                                "Gateway recorded SUBMITTED. If normal SMS callbacks arrive, it may upgrade to SENT. If RCS takes over, SUBMITTED remains terminal and will never auto-retry."

                        } else if (
                            apiResult.responseCode == 409
                        ) {
                            fetchedSendState =
                                "terminal"

                            gatewayStatus =
                                "Gateway had already advanced this item, likely from an SMS callback. No resend was attempted."

                        } else {
                            fetchedSendState =
                                "handed_off"

                            gatewayStatus =
                                "Android accepted the message, but the gateway status report returned HTTP ${apiResult.responseCode}. Do not resend this item automatically."
                        }
                    }

                } catch (
                    exception: Exception
                ) {
                    runOnUi {
                        val callbackTerminalState =
                            SmsStatusStore.gatewayTerminalState

                        fetchedSendState =
                            if (
                                callbackTerminalState in listOf(
                                    "sent",
                                    "failed",
                                )
                            ) {
                                callbackTerminalState
                            } else {
                                "handed_off"
                            }

                        gatewayStatus =
                            if (
                                callbackTerminalState == "sent"
                            ) {
                                "SMS send callback completed. The earlier SUBMITTED report failed, but this item will not be resent."
                            } else if (
                                callbackTerminalState == "failed"
                            ) {
                                "Android reported a definite send failure. The earlier SUBMITTED report also failed."
                            } else {
                                "Android accepted the message, but gateway reporting failed: ${
                                    exception.message
                                        ?: "Unknown error"
                                }. Do not resend this item automatically."
                            }
                    }
                }

            }.start()

        } catch (
            exception: Exception
        ) {

            fetchedSendState =
                "failed"

            SmsStatusStore.sendStatus =
                "Android rejected the send request: ${
                    exception.message
                        ?: "Unknown error"
                }"

            gatewayStatus =
                "Android rejected the send request before handoff. Recording FAILED..."

            Thread {

                try {

                    val apiResult =
                        GatewayApiReporter
                            .postRecipientStatus(
                                gatewayUrl = cleanGatewayUrl,
                                gatewayToken = cleanGatewayToken,
                                recipientId = recipientId,
                                claimToken = cleanClaimToken,
                                status = "failed",
                                transport = "android_auto",
                                errorMessage = (
                                        exception.message
                                            ?: "Android send request failed"
                                        ),
                            )

                    runOnUi {
                        gatewayStatus =
                            if (
                                apiResult.isSuccess
                            ) {
                                "Gateway recorded FAILED. This item will not be retried automatically."
                            } else {
                                "Android rejected the send request, and gateway failure reporting returned HTTP ${apiResult.responseCode}."
                            }
                    }

                } catch (
                    reportException: Exception
                ) {
                    runOnUi {
                        gatewayStatus =
                            "Android rejected the send request, but gateway failure reporting also failed: ${
                                reportException.message
                                    ?: "Unknown error"
                            }."
                    }
                }

            }.start()
        }
    }


    // =====================================================
    // Existing manual SMS diagnostics
    // =====================================================

    fun sendManualMessageNow() {

        val trimmedPhone =
            phoneNumber.trim()

        val trimmedMessage =
            message.trim()

        if (
            trimmedPhone.isBlank()
            || trimmedMessage.isBlank()
        ) {
            SmsStatusStore.sendStatus =
                "Enter a phone number and message first."
            SmsStatusStore.deliveryStatus =
                ""
            return
        }

        try {

            val smsManager =
                getSmsManager(
                    context
                )

            val messageParts =
                smsManager.divideMessage(
                    trimmedMessage
                )

            val sendId =
                UUID
                    .randomUUID()
                    .toString()

            SmsStatusStore.beginSend(
                sendId = sendId,
                partCount = messageParts.size,
            )

            sendSms(
                context = context,
                smsManager = smsManager,
                phoneNumber = trimmedPhone,
                messageParts = messageParts,
                sendId = sendId,
                gatewayRecipientId = null,
                gatewayClaimToken = null,
                gatewayUrl = null,
                gatewayToken = null,
            )

        } catch (
            exception: Exception
        ) {
            SmsStatusStore.sendStatus =
                "Send failed: ${
                    exception.message
                        ?: "Unknown error"
                }"
            SmsStatusStore.deliveryStatus =
                ""
        }
    }


    fun testSentCallback() {

        try {

            val sendId =
                UUID
                    .randomUUID()
                    .toString()

            SmsStatusStore.beginSend(
                sendId = sendId,
                partCount = 1,
            )

            SmsStatusStore.sendStatus =
                "Testing callback..."

            val pendingIntent =
                createSentPendingIntent(
                    context = context,
                    sendId = sendId,
                    partIndex = 0,
                    partCount = 1,
                    gatewayRecipientId = null,
                    gatewayClaimToken = null,
                    gatewayUrl = null,
                    gatewayToken = null,
                )

            pendingIntent.send(
                context,
                Activity.RESULT_OK,
                null
            )

        } catch (
            exception: Exception
        ) {
            SmsStatusStore.sendStatus =
                "Callback test failed: ${
                    exception.message
                        ?: "Unknown error"
                }"
        }
    }


    // =====================================================
    // Runtime permissions
    // =====================================================

    val localNetworkPermissionLauncher =
        rememberLauncherForActivityResult(
            contract =
                ActivityResultContracts
                    .RequestPermission()
        ) { permissionGranted ->

            val action =
                pendingLocalNetworkAction

            pendingLocalNetworkAction =
                ""

            if (
                !permissionGranted
            ) {
                gatewayStatus =
                    "Local network permission was not granted."
                return@rememberLauncherForActivityResult
            }

            when (
                action
            ) {
                "test" ->
                    testGatewayNow()

                "fetch_test" ->
                    fetchNextQueuedTestNow()

                "fetch_household" ->
                    fetchNextQueuedHouseholdNow()

                "cancel_test" ->
                    cancelFetchedTestNow()

                "release_household" ->
                    releaseFetchedHouseholdNow()
            }
        }


    fun requireLocalNetworkThen(
        action: String,
        block: () -> Unit,
    ) {

        if (
            hasLocalNetworkPermission()
        ) {
            block()
        } else {
            pendingLocalNetworkAction =
                action

            gatewayStatus =
                "Requesting local network permission..."

            localNetworkPermissionLauncher.launch(
                Manifest.permission.ACCESS_LOCAL_NETWORK
            )
        }
    }


    var pendingSmsAction by rememberSaveable {
        mutableStateOf("")
    }

    val smsPermissionLauncher =
        rememberLauncherForActivityResult(
            contract =
                ActivityResultContracts
                    .RequestPermission()
        ) { permissionGranted ->

            val action =
                pendingSmsAction

            pendingSmsAction =
                ""

            if (
                !permissionGranted
            ) {
                SmsStatusStore.sendStatus =
                    "SMS permission was not granted."
                return@rememberLauncherForActivityResult
            }

            when (
                action
            ) {
                "gateway_claim" ->
                    sendFetchedClaimNow()

                "gateway_batch" ->
                    startHouseholdBatchNow()

                "manual" ->
                    sendManualMessageNow()
            }
        }


    fun requireSmsThen(
        action: String,
        block: () -> Unit,
    ) {

        val hasPermission =
            ContextCompat
                .checkSelfPermission(
                    context,
                    Manifest.permission.SEND_SMS
                ) ==
                    PackageManager.PERMISSION_GRANTED

        if (
            hasPermission
        ) {
            block()
        } else {
            pendingSmsAction =
                action

            SmsStatusStore.sendStatus =
                "Requesting SMS permission..."

            smsPermissionLauncher.launch(
                Manifest.permission.SEND_SMS
            )
        }
    }


    // =====================================================
    // UI
    // =====================================================

    Column(
        modifier =
            modifier
                .fillMaxSize()
                .verticalScroll(
                    rememberScrollState()
                ),
        verticalArrangement =
            Arrangement.Top
    ) {

        Text(
            text =
                "Ascension Messenger DEV",
            style =
                MaterialTheme
                    .typography
                    .headlineMedium
        )

        Spacer(
            modifier =
                Modifier.height(
                    8.dp
                )
        )

        Text(
            text =
                "Local messaging gateway",
            style =
                MaterialTheme
                    .typography
                    .bodyMedium
        )

        Spacer(
            modifier =
                Modifier.height(
                    28.dp
                )
        )


        // -------------------------------------------------
        // Gateway connection
        // -------------------------------------------------

        Text(
            text =
                "Gateway",
            style =
                MaterialTheme
                    .typography
                    .titleLarge,
            fontWeight =
                FontWeight.Bold
        )

        Spacer(
            modifier =
                Modifier.height(
                    12.dp
                )
        )

        OutlinedTextField(
            value =
                gatewayUrl,
            onValueChange = {
                gatewayUrl = it
            },
            label = {
                Text(
                    "Gateway URL"
                )
            },
            singleLine =
                true,
            modifier =
                Modifier.fillMaxWidth()
        )

        Spacer(
            modifier =
                Modifier.height(
                    12.dp
                )
        )

        OutlinedTextField(
            value =
                gatewayToken,
            onValueChange = {
                gatewayToken = it
            },
            label = {
                Text(
                    "Gateway token"
                )
            },
            visualTransformation =
                PasswordVisualTransformation(),
            singleLine =
                true,
            modifier =
                Modifier.fillMaxWidth()
        )

        Spacer(
            modifier =
                Modifier.height(
                    12.dp
                )
        )

        Button(
            onClick = {
                requireLocalNetworkThen(
                    action = "test",
                    block = {
                        testGatewayNow()
                    },
                )
            },
            modifier =
                Modifier.fillMaxWidth()
        ) {
            Text(
                "Test Gateway"
            )
        }

        Spacer(
            modifier =
                Modifier.height(
                    18.dp
                )
        )

        Text(
            text =
                "DEV Test Queue",
            style =
                MaterialTheme
                    .typography
                    .titleMedium,
            fontWeight =
                FontWeight.Bold
        )

        Text(
            text =
                "Manual one-number test messages only.",
            style =
                MaterialTheme
                    .typography
                    .bodySmall
        )

        Spacer(
            modifier =
                Modifier.height(
                    8.dp
                )
        )

        Button(
            onClick = {
                requireLocalNetworkThen(
                    action = "fetch_test",
                    block = {
                        fetchNextQueuedTestNow()
                    },
                )
            },
            enabled = !batchRunning
                && !(
                fetchedRecipientId != null
                && fetchedSendState in listOf(
                    "claimed",
                    "cancelling",
                    "cancel_unknown",
                    "releasing",
                    "release_unknown",
                    "sending",
                    "handed_off",
                )
            ),
            modifier =
                Modifier.fillMaxWidth()
        ) {
            Text(
                "Fetch Next TEST"
            )
        }

        Spacer(
            modifier =
                Modifier.height(
                    18.dp
                )
        )

        Text(
            text =
                "Household Queue",
            style =
                MaterialTheme
                    .typography
                    .titleMedium,
            fontWeight =
                FontWeight.Bold
        )

        Text(
            text =
                "Fetch one household to review it. You can then send manually or start a controlled batch for that message only.",
            style =
                MaterialTheme
                    .typography
                    .bodySmall
        )

        Spacer(
            modifier =
                Modifier.height(
                    8.dp
                )
        )

        Button(
            onClick = {
                requireLocalNetworkThen(
                    action = "fetch_household",
                    block = {
                        fetchNextQueuedHouseholdNow()
                    },
                )
            },
            enabled = !batchRunning
                && !(
                fetchedRecipientId != null
                && fetchedSendState in listOf(
                    "claimed",
                    "cancelling",
                    "cancel_unknown",
                    "releasing",
                    "release_unknown",
                    "sending",
                    "handed_off",
                )
            ),
            modifier =
                Modifier.fillMaxWidth()
        ) {
            Text(
                "Fetch Next Household"
            )
        }

        if (
            batchMessageId != null
        ) {
            Spacer(
                modifier =
                    Modifier.height(
                        14.dp
                    )
            )

            Text(
                text =
                    "Batch Message #$batchMessageId",
                style =
                    MaterialTheme
                        .typography
                        .titleSmall,
                fontWeight =
                    FontWeight.Bold
            )

            Text(
                text =
                    "Processed: ${batchSubmitted + batchSent + batchFailed} of $batchTotal  •  Sent: $batchSent  •  Submitted: $batchSubmitted  •  Failed: $batchFailed  •  Remaining: ${batchQueued + batchClaimed}",
                style =
                    MaterialTheme
                        .typography
                        .bodySmall
            )

            if (
                batchStatus.isNotBlank()
            ) {
                Spacer(
                    modifier =
                        Modifier.height(
                            6.dp
                        )
                )

                Text(
                    text =
                        batchStatus,
                    style =
                        MaterialTheme
                            .typography
                            .bodySmall
                )
            }

            if (
                batchRunning
            ) {
                Spacer(
                    modifier =
                        Modifier.height(
                            10.dp
                        )
                )

                Button(
                    onClick = {
                        batchStopSignal.set(
                            true
                        )

                        batchStopRequested =
                            true

                        batchStatus =
                            "Stop requested. The current household will finish, then the batch will stop."
                    },
                    enabled =
                        !batchStopRequested,
                    modifier =
                        Modifier.fillMaxWidth()
                ) {
                    Text(
                        if (
                            batchStopRequested
                        ) {
                            "Stop Requested"
                        } else {
                            "Stop After Current"
                        }
                    )
                }
            }
        }


        if (
            gatewayStatus.isNotBlank()
        ) {
            Spacer(
                modifier =
                    Modifier.height(
                        12.dp
                    )
            )

            Text(
                text =
                    gatewayStatus,
                style =
                    MaterialTheme
                        .typography
                        .bodyMedium
            )
        }


        // -------------------------------------------------
        // Claimed gateway item
        // -------------------------------------------------

        if (
            fetchedRecipientId != null
        ) {

            Spacer(
                modifier =
                    Modifier.height(
                        24.dp
                    )
            )

            HorizontalDivider()

            Spacer(
                modifier =
                    Modifier.height(
                        20.dp
                    )
            )

            Text(
                text =
                    if (
                        fetchedIsTest
                    ) {
                        "TEST MESSAGE"
                    } else {
                        "HOUSEHOLD MESSAGE"
                    },
                style =
                    MaterialTheme
                        .typography
                        .titleLarge,
                fontWeight =
                    FontWeight.Bold
            )

            Spacer(
                modifier =
                    Modifier.height(
                        10.dp
                    )
            )

            Text(
                text =
                    "Message #$fetchedMessageId"
            )

            Text(
                text =
                    "Recipient: $fetchedContact"
            )

            Text(
                text =
                    "Phone: $fetchedPhone"
            )

            if (
                fetchedHousehold.isNotBlank()
            ) {
                Text(
                    text =
                        if (
                            fetchedIsTest
                        ) {
                            "Reference: $fetchedHousehold"
                        } else {
                            "Household: $fetchedHousehold"
                        }
                )
            }

            if (
                fetchedChildren.isNotBlank()
            ) {
                Text(
                    text =
                        if (
                            fetchedIsTest
                        ) {
                            "Source: $fetchedChildren"
                        } else {
                            "Children: $fetchedChildren"
                        }
                )
            }

            Text(
                text =
                    "State: ${
                        fetchedSendState
                            .ifBlank {
                                "unknown"
                            }
                            .uppercase()
                    }"
            )

            Spacer(
                modifier =
                    Modifier.height(
                        14.dp
                    )
            )

            Text(
                text =
                    fetchedMessage,
                style =
                    MaterialTheme
                        .typography
                        .bodyLarge
            )

            Spacer(
                modifier =
                    Modifier.height(
                        16.dp
                    )
            )

            if (
                fetchedSendState == "claimed"
            ) {

                Text(
                    text =
                        if (
                            fetchedIsTest
                        ) {
                            "Nothing has been sent yet. Review the number and message before continuing."
                        } else {
                            "Nothing has been sent yet. Review the household, recipient number, children, and exact message before continuing."
                        },
                    style =
                        MaterialTheme
                            .typography
                            .bodySmall
                )

                Spacer(
                    modifier =
                        Modifier.height(
                            12.dp
                        )
                )

                Button(
                    onClick = {
                        requireSmsThen(
                            action = "gateway_claim",
                            block = {
                                sendFetchedClaimNow()
                            },
                        )
                    },
                    modifier =
                        Modifier.fillMaxWidth()
                ) {
                    Text(
                        if (
                            fetchedIsTest
                        ) {
                            "Send This TEST"
                        } else {
                            "Send This Message"
                        }
                    )
                }

                Spacer(
                    modifier =
                        Modifier.height(
                            10.dp
                        )
                )

                if (
                    fetchedIsTest
                ) {

                    Button(
                        onClick = {
                            requireLocalNetworkThen(
                                action = "cancel_test",
                                block = {
                                    cancelFetchedTestNow()
                                },
                            )
                        },
                        modifier =
                            Modifier.fillMaxWidth()
                    ) {
                        Text(
                            "Cancel This Claimed TEST"
                        )
                    }

                } else {

                    Button(
                        onClick = {
                            requireSmsThen(
                                action = "gateway_batch",
                                block = {
                                    startHouseholdBatchNow()
                                },
                            )
                        },
                        enabled =
                            !batchRunning,
                        modifier =
                            Modifier.fillMaxWidth()
                    ) {
                        Text(
                            "Start This Message Batch"
                        )
                    }

                    Spacer(
                        modifier =
                            Modifier.height(
                                10.dp
                            )
                    )

                    Button(
                        onClick = {
                            requireLocalNetworkThen(
                                action = "release_household",
                                block = {
                                    releaseFetchedHouseholdNow()
                                },
                            )
                        },
                        modifier =
                            Modifier.fillMaxWidth()
                    ) {
                        Text(
                            "Release Without Sending"
                        )
                    }

                    Spacer(
                        modifier =
                            Modifier.height(
                                8.dp
                            )
                    )

                    Text(
                        text =
                            "Release returns this household to the queue. It does not mark the message sent and it does not skip the household permanently.",
                        style =
                            MaterialTheme
                                .typography
                                .bodySmall
                    )
                }
            }

            if (
                fetchedSendState in listOf(
                    "cancel_unknown",
                    "release_unknown",
                    "handed_off",
                )
            ) {

                Spacer(
                    modifier =
                        Modifier.height(
                            12.dp
                        )
                )

                Text(
                    text =
                        "Safety lock: do not resend or release this item until its database status is verified in Streamlit.",
                    style =
                        MaterialTheme
                            .typography
                            .bodySmall,
                    fontWeight =
                        FontWeight.Bold
                )
            }

            if (
                sendStatus.isNotBlank()
            ) {
                Spacer(
                    modifier =
                        Modifier.height(
                            12.dp
                        )
                )

                Text(
                    text =
                        sendStatus
                )
            }

            if (
                gatewayCallbackStatus.isNotBlank()
            ) {
                Spacer(
                    modifier =
                        Modifier.height(
                            8.dp
                        )
                )

                Text(
                    text =
                        gatewayCallbackStatus
                )
            }

            if (
                deliveryStatus.isNotBlank()
            ) {
                Spacer(
                    modifier =
                        Modifier.height(
                            8.dp
                        )
                )

                Text(
                    text =
                        deliveryStatus
                )
            }
        }


        Spacer(
            modifier =
                Modifier.height(
                    32.dp
                )
        )

        HorizontalDivider()

        Spacer(
            modifier =
                Modifier.height(
                    28.dp
                )
        )


        // -------------------------------------------------
        // Existing diagnostics kept for troubleshooting
        // -------------------------------------------------

        Text(
            text =
                "Manual SMS Diagnostics",
            style =
                MaterialTheme
                    .typography
                    .titleLarge,
            fontWeight =
                FontWeight.Bold
        )

        Spacer(
            modifier =
                Modifier.height(
                    16.dp
                )
        )

        OutlinedTextField(
            value =
                phoneNumber,
            onValueChange = {
                phoneNumber = it
            },
            label = {
                Text(
                    "Phone number"
                )
            },
            keyboardOptions =
                KeyboardOptions(
                    keyboardType =
                        KeyboardType.Phone
                ),
            singleLine =
                true,
            modifier =
                Modifier.fillMaxWidth()
        )

        Spacer(
            modifier =
                Modifier.height(
                    16.dp
                )
        )

        OutlinedTextField(
            value =
                message,
            onValueChange = {
                message = it
            },
            label = {
                Text(
                    "Message"
                )
            },
            minLines =
                4,
            modifier =
                Modifier.fillMaxWidth()
        )

        Spacer(
            modifier =
                Modifier.height(
                    8.dp
                )
        )

        Text(
            text =
                "${message.length} characters",
            style =
                MaterialTheme
                    .typography
                    .bodySmall
        )

        Spacer(
            modifier =
                Modifier.height(
                    20.dp
                )
        )

        Button(
            onClick = {
                if (
                    phoneNumber.isBlank()
                    || message.isBlank()
                ) {
                    SmsStatusStore.sendStatus =
                        "Enter a phone number and message first."
                } else {
                    requireSmsThen(
                        action = "manual",
                        block = {
                            sendManualMessageNow()
                        },
                    )
                }
            },
            modifier =
                Modifier.fillMaxWidth()
        ) {
            Text(
                "Send Manual Diagnostic"
            )
        }

        Spacer(
            modifier =
                Modifier.height(
                    12.dp
                )
        )

        Button(
            onClick = {
                testSentCallback()
            },
            modifier =
                Modifier.fillMaxWidth()
        ) {
            Text(
                "Test Callback Only"
            )
        }

        if (
            fetchedRecipientId == null
            && sendStatus.isNotBlank()
        ) {
            Spacer(
                modifier =
                    Modifier.height(
                        16.dp
                    )
            )

            Text(
                text =
                    sendStatus
            )
        }

        if (
            fetchedRecipientId == null
            && deliveryStatus.isNotBlank()
        ) {
            Spacer(
                modifier =
                    Modifier.height(
                        8.dp
                    )
            )

            Text(
                text =
                    deliveryStatus
            )
        }

        Spacer(
            modifier =
                Modifier.height(
                    40.dp
                )
        )
    }
}


// =========================================================
// SmsManager
// =========================================================

private fun getSmsManager(
    context: Context
): SmsManager {

    return if (
        Build.VERSION.SDK_INT >=
        Build.VERSION_CODES.S
    ) {
        context.getSystemService(
            SmsManager::class.java
        )
    } else {
        @Suppress(
            "DEPRECATION"
        )
        SmsManager.getDefault()
    }
}


// =========================================================
// SMS handoff
// =========================================================

private fun sendSms(
    context: Context,
    smsManager: SmsManager,
    phoneNumber: String,
    messageParts: ArrayList<String>,
    sendId: String,
    gatewayRecipientId: Long?,
    gatewayClaimToken: String?,
    gatewayUrl: String?,
    gatewayToken: String?,
) {

    val partCount =
        messageParts.size

    if (
        partCount == 1
    ) {

        smsManager.sendTextMessage(
            phoneNumber,
            null,
            messageParts[0],
            createSentPendingIntent(
                context = context,
                sendId = sendId,
                partIndex = 0,
                partCount = 1,
                gatewayRecipientId = gatewayRecipientId,
                gatewayClaimToken = gatewayClaimToken,
                gatewayUrl = gatewayUrl,
                gatewayToken = gatewayToken,
            ),
            createDeliveredPendingIntent(
                context = context,
                sendId = sendId,
                partIndex = 0,
                partCount = 1,
            )
        )

        return
    }

    val sentIntents =
        ArrayList<PendingIntent>()

    val deliveryIntents =
        ArrayList<PendingIntent>()

    for (
    partIndex in messageParts.indices
    ) {

        sentIntents.add(
            createSentPendingIntent(
                context = context,
                sendId = sendId,
                partIndex = partIndex,
                partCount = partCount,
                gatewayRecipientId = gatewayRecipientId,
                gatewayClaimToken = gatewayClaimToken,
                gatewayUrl = gatewayUrl,
                gatewayToken = gatewayToken,
            )
        )

        deliveryIntents.add(
            createDeliveredPendingIntent(
                context = context,
                sendId = sendId,
                partIndex = partIndex,
                partCount = partCount,
            )
        )
    }

    smsManager.sendMultipartTextMessage(
        phoneNumber,
        null,
        messageParts,
        sentIntents,
        deliveryIntents
    )
}


private fun createSentPendingIntent(
    context: Context,
    sendId: String,
    partIndex: Int,
    partCount: Int,
    gatewayRecipientId: Long?,
    gatewayClaimToken: String?,
    gatewayUrl: String?,
    gatewayToken: String?,
): PendingIntent {

    val intent =
        Intent(
            context,
            SmsSentReceiver::class.java
        ).apply {

            putExtra(
                EXTRA_SEND_ID,
                sendId
            )

            putExtra(
                EXTRA_PART_INDEX,
                partIndex
            )

            putExtra(
                EXTRA_PART_COUNT,
                partCount
            )

            if (
                gatewayRecipientId != null
                && gatewayRecipientId > 0L
                && !gatewayClaimToken.isNullOrBlank()
                && !gatewayUrl.isNullOrBlank()
                && !gatewayToken.isNullOrBlank()
            ) {
                putExtra(
                    EXTRA_GATEWAY_RECIPIENT_ID,
                    gatewayRecipientId
                )

                putExtra(
                    EXTRA_GATEWAY_CLAIM_TOKEN,
                    gatewayClaimToken
                )

                putExtra(
                    EXTRA_GATEWAY_URL,
                    gatewayUrl
                )

                putExtra(
                    EXTRA_GATEWAY_TOKEN,
                    gatewayToken
                )
            }
        }

    return PendingIntent.getBroadcast(
        context,
        sendId.hashCode() + partIndex,
        intent,
        PendingIntent.FLAG_UPDATE_CURRENT
                or PendingIntent.FLAG_MUTABLE
    )
}


private fun createDeliveredPendingIntent(
    context: Context,
    sendId: String,
    partIndex: Int,
    partCount: Int,
): PendingIntent {

    val intent =
        Intent(
            context,
            SmsDeliveredReceiver::class.java
        ).apply {

            putExtra(
                EXTRA_SEND_ID,
                sendId
            )

            putExtra(
                EXTRA_PART_INDEX,
                partIndex
            )

            putExtra(
                EXTRA_PART_COUNT,
                partCount
            )
        }

    return PendingIntent.getBroadcast(
        context,
        sendId
            .hashCode()
            .xor(
                0x40000000
            ) + partIndex,
        intent,
        PendingIntent.FLAG_UPDATE_CURRENT
                or PendingIntent.FLAG_MUTABLE
    )
}