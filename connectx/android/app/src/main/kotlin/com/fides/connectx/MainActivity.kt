package com.fides.connectx

import android.media.AudioManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    private val CHANNEL = "connectx/audio_mode"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "forceModeInCommunication" -> {
                        try {
                            val am = getSystemService(AUDIO_SERVICE) as AudioManager
                            am.mode = AudioManager.MODE_IN_COMMUNICATION
                            am.isSpeakerphoneOn = true
                            am.isMicrophoneMute = false

                            result.success(
                                hashMapOf(
                                    "mode" to am.mode,
                                    "speakerphoneOn" to am.isSpeakerphoneOn,
                                    "microphoneMuted" to am.isMicrophoneMute
                                )
                            )
                        } catch (e: Exception) {
                            result.error("AUDIO_MODE_ERROR", e.message, null)
                        }
                    }

                    else -> result.notImplemented()
                }
            }
    }
}
