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

    LaunchedEffect(
        gatewayTerminalState
    ) {
        if (
            fetchedRecipientId != null
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


    fun clearFetchedTest() {
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
    // Fetch one DEV-only queued test
    // =====================================================

    fun fetchNextQueuedTestNow() {

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
            fetchedRecipientId != null
            && fetchedSendState == "claimed"
        ) {
            gatewayStatus =
                "A test is already claimed on this screen. Send or cancel it before claiming another."
            return
        }

        gatewayStatus =
            "Fetching next queued DEV test..."

        Thread {

            try {

                val cleanBaseUrl =
                    gatewayUrl
                        .trim()
                        .trimEnd('/')

                val url =
                    URL(
                        "$cleanBaseUrl/gateway/claim-next-test"
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
                            clearFetchedTest()
                            gatewayStatus =
                                "No queued DEV tests are waiting."
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

                        clearFetchedTest()

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
                            if (
                                isTest
                            ) {
                                "DEV test claimed successfully. Nothing has been sent yet."
                            } else {
                                "Safety stop: gateway returned a non-test item. Sending is disabled."
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
                        gatewayStatus =
                            "Cancel returned HTTP ${apiResult.responseCode}. Do not send until you verify the test status in Streamlit."
                    }
                }

            } catch (
                exception: Exception
            ) {
                runOnUi {
                    gatewayStatus =
                        "Cancel failed: ${
                            exception.message
                                ?: "Unknown error"
                        }. Do not send until you verify the test status in Streamlit."
                }
            }

        }.start()
    }


    // =====================================================
    // Send the currently claimed DEV test
    // =====================================================

    fun sendFetchedTestNow() {

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
            || !fetchedIsTest
            || fetchedSendState != "claimed"
            || cleanPhone.isBlank()
            || cleanMessage.isBlank()
            || cleanClaimToken.isBlank()
            || cleanGatewayToken.isBlank()
            || cleanGatewayUrl.isBlank()
        ) {
            gatewayStatus =
                "This DEV test is not in a safe claimed state for sending."
            return
        }

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
            // this item is no longer eligible for manual resend even if
            // the API status report below fails. RCS may take over and
            // never return the normal SMS sent PendingIntent.
            fetchedSendState =
                "handed_off"

            SmsStatusStore.sendStatus =
                "Android accepted the send request. Waiting for gateway status report..."

            gatewayStatus =
                "Android accepted the send request. This test will not be automatically retried."

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

                        if (
                            apiResult.isSuccess
                        ) {
                            fetchedSendState =
                                "submitted"

                            gatewayStatus =
                                "Gateway recorded SUBMITTED. If normal SMS callbacks arrive, it will upgrade to SENT. If RCS takes over, SUBMITTED remains terminal and will never auto-retry."

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
                                "Android accepted the message, but the gateway status report returned HTTP ${apiResult.responseCode}. Do not resend this test automatically."
                        }
                    }

                } catch (
                    exception: Exception
                ) {
                    runOnUi {
                        fetchedSendState =
                            "handed_off"

                        gatewayStatus =
                            "Android accepted the message, but gateway reporting failed: ${
                                exception.message
                                    ?: "Unknown error"
                            }. Do not resend this test automatically."
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

                "fetch" ->
                    fetchNextQueuedTestNow()

                "cancel" ->
                    cancelFetchedTestNow()
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
                "gateway_test" ->
                    sendFetchedTestNow()

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

        Row(
            modifier =
                Modifier.fillMaxWidth(),
            horizontalArrangement =
                Arrangement.spacedBy(
                    12.dp
                )
        ) {

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
                    Modifier.weight(
                        1f
                    )
            ) {
                Text(
                    "Test Gateway"
                )
            }

            Button(
                onClick = {
                    requireLocalNetworkThen(
                        action = "fetch",
                        block = {
                            fetchNextQueuedTestNow()
                        },
                    )
                },
                enabled = !(
                        fetchedRecipientId != null
                                && fetchedSendState == "claimed"
                        ),
                modifier =
                    Modifier.weight(
                        1f
                    )
            ) {
                Text(
                    "Fetch Next TEST"
                )
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
        // Claimed test
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
                        "SAFETY STOP - NON-TEST ITEM"
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
                        "Reference: $fetchedHousehold"
                )
            }

            if (
                fetchedChildren.isNotBlank()
            ) {
                Text(
                    text =
                        "Source: $fetchedChildren"
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
                fetchedIsTest
                && fetchedSendState == "claimed"
            ) {

                Text(
                    text =
                        "Nothing has been sent yet. Review the number and message before continuing.",
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
                            action = "gateway_test",
                            block = {
                                sendFetchedTestNow()
                            },
                        )
                    },
                    modifier =
                        Modifier.fillMaxWidth()
                ) {
                    Text(
                        "Send This TEST"
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
                            action = "cancel",
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