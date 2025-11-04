package com.fides.connectx

import android.media.AudioManager
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    private val CHANNEL = "connectx/audio_mode"
    private var audioFocusRequest: AudioFocusRequest? = null

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

                            // Request audio focus (API 26+ uses AudioFocusRequest)
                            var focusResult = AudioManager.AUDIOFOCUS_REQUEST_FAILED
                            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                                val attrs = AudioAttributes.Builder()
                                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                                    .build()
                                audioFocusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                                    .setAudioAttributes(attrs)
                                    .setOnAudioFocusChangeListener { /* no-op */ }
                                    .build()
                                focusResult = (getSystemService(AUDIO_SERVICE) as AudioManager)
                                    .requestAudioFocus(audioFocusRequest!!)
                            } else {
                                @Suppress("DEPRECATION")
                                focusResult = am.requestAudioFocus(
                                    null,
                                    AudioManager.STREAM_VOICE_CALL,
                                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT
                                )
                            }

                            result.success(
                                hashMapOf(
                                    "mode" to am.mode,
                                    "speakerphoneOn" to am.isSpeakerphoneOn,
                                    "microphoneMuted" to am.isMicrophoneMute,
                                    "audioFocus" to focusResult
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
