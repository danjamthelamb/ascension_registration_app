package org.ascensionhurricane.ascensionmsgdev

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log


class SmsDeliveredReceiver : BroadcastReceiver() {

    override fun onReceive(
        context: Context?,
        intent: Intent?
    ) {

        Log.d(
            "SmsDeliveredReceiver",
            "DELIVERY CALLBACK RECEIVED resultCode=$resultCode"
        )

        val sendId =
            intent?.getStringExtra(
                EXTRA_SEND_ID
            )

        Log.d(
            "SmsDeliveredReceiver",
            "callback sendId=$sendId activeSendId=${SmsStatusStore.activeSendId}"
        )

        if (sendId == null) {

            Log.e(
                "SmsDeliveredReceiver",
                "Delivery callback contained no send ID."
            )

            return
        }

        if (
            sendId !=
            SmsStatusStore.activeSendId
        ) {

            Log.e(
                "SmsDeliveredReceiver",
                "Send ID does not match active send."
            )

            return
        }

        val partIndex =
            intent.getIntExtra(
                EXTRA_PART_INDEX,
                -1
            )

        if (partIndex < 0) {

            Log.e(
                "SmsDeliveredReceiver",
                "Invalid part index."
            )

            return
        }

        SmsStatusStore.deliveryResults[
            partIndex
        ] = resultCode

        Log.d(
            "SmsDeliveredReceiver",
            "receivedParts=${SmsStatusStore.deliveryResults.size} " +
                    "expectedParts=${SmsStatusStore.expectedParts}"
        )

        if (
            SmsStatusStore.expectedParts > 0
            &&
            SmsStatusStore.deliveryResults.size
            >= SmsStatusStore.expectedParts
        ) {

            val allDelivered =
                SmsStatusStore
                    .deliveryResults
                    .values
                    .all {
                        it == Activity.RESULT_OK
                    }

            SmsStatusStore.deliveryStatus =

                if (allDelivered) {

                    Log.d(
                        "SmsDeliveredReceiver",
                        "All parts delivered."
                    )

                    "Delivery confirmed."

                } else {

                    Log.e(
                        "SmsDeliveredReceiver",
                        "Delivery report returned failure."
                    )

                    "Delivery could not be confirmed."
                }
        }
    }
}