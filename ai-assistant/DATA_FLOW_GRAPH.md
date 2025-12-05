┌─────────────────────────────────────────────────────────────────────────────┐
│                    FIDES AI ASSISTANT - DATA FLOW                            │
│                  From Sign-in to Continuous Audio Streaming                   │
└─────────────────────────────────────────────────────────────────────────────┘

1. USER AUTHENTICATION & SYNC
═══════════════════════════════════════════════════════════════════════════════
   [Mobile App]
        │
        │ POST /user/sync
        │ Headers: Authorization: Bearer <firebase_token>
        │ Body: { email, name, fcm_token }
        ▼
   [common_endpoints.py]
   └── user_sync()
        ├── Verify Firebase token → firebase_auth.verify_id_token()
        ├── Extract user_id (Firebase UID)
        ├── Store/Update in Weaviate → UserModelWeaviate.create_or_update()
        │   └── Save: user_id, email, name, fcm_token, last_login
        └── Return: { success: true, user_id, new_user }


2. WEBSOCKET CONNECTION SETUP
═══════════════════════════════════════════════════════════════════════════════
   [Mobile App]
        │
        │ WebSocket: ws://server:8080/ws?user_id=<firebase_uid>
        ▼
   [signaling_server.py]
   └── handle_websocket()
        ├── Extract user_id from query params
        ├── Create/Reuse AIAssistant instance
        │   └── user_assistants[user_id] = AIAssistant()
        │       └── [ai_assistant.py].__init__()
        │           ├── Initialize Google Cloud clients (STT, TTS, Gemini LLM)
        │           ├── Setup LangChain with chat history
        │           └── Load conversation history from Weaviate
        │               └── PersistentChatMessageHistory.load_from_store()
        │                   └── ChatMessageModelWeaviate.get_messages(user_id)
        │
        ├── Create PeerConnectionHandler
        │   └── [peer_connection_handler.py].__init__()
        │       ├── Store references: connection_id, ai_assistant, websocket
        │       ├── Create RTCPeerConnection
        │       └── Setup event handlers (@pc.on)
        │
        └── Start heartbeat monitoring loop


3. WEBRTC NEGOTIATION
═══════════════════════════════════════════════════════════════════════════════
   [Mobile App]
        │
        │ Message: { type: "offer", sdp: "<SDP>" }
        ▼
   [signaling_server.py]
   └── _handle_message() → routes to PeerConnectionHandler
        │
        ▼
   [peer_connection_handler.py]
   └── handle_offer()
        ├── pc.setRemoteDescription(offer)
        ├── Wait for audio track detection (track_ready event)
        ├── pc.createAnswer()
        ├── pc.setLocalDescription(answer)
        └── Send answer back via WebSocket
             │ { type: "answer", sdp: "<SDP>" }
             ▼
        [Mobile App]


4. AUDIO TRACK DETECTION & PROCESSOR INITIALIZATION
═══════════════════════════════════════════════════════════════════════════════
   [RTCPeerConnection]
        │
        │ @pc.on("track") event triggered
        ▼
   [peer_connection_handler.py]
   └── on_track()
        ├── Detect audio track from client
        ├── Create AudioProcessor
        │   └── [audio_processor.py].__init__()
        │       ├── connection_id, ai_assistant, input_track (from client)
        │       ├── output_track = AudioOutputTrack() (for sending to client)
        │       ├── audio_queue = asyncio.Queue() (for STT streaming)
        │       ├── Initialize echo detection attributes
        │       └── Setup interrupt handling
        │
        └── Start audio processing
             └── audio_processor.start()


5. AUDIO PROCESSOR START - PARALLEL TASKS
═══════════════════════════════════════════════════════════════════════════════
   [audio_processor.py]
   └── start()
        ├── Task 1: _process_audio() ────────────────────────────────┐
        │   └── Loop: Receive audio frames from WebRTC input track   │
        │       ├── input_track.recv() → AudioFrame                  │
        │       ├── Convert to numpy array (_frame_to_numpy)         │
        │       ├── Convert to bytes                                 │
        │       └── Queue for STT → audio_queue.put(audio_bytes)    │
        │                                                             │
        ├── Task 2: _continuous_stt() ───────────────────────────────┤
        │   ├── Create audio_generator() async generator             │
        │   │   └── Loop: Get audio from queue → yield to Google STT│
        │   │                                                         │
        │   └── Stream to Google STT                                 │
        │       └── ai_assistant.speech_to_text_continuous_stream()  │
        │           └── [ai_assistant.py]                            │
        │               ├── Google Cloud STT streaming API           │
        │               └── Yield: (transcript, is_final)            │
        │                   │                                         │
        │                   ├── If interim: Log only                 │
        │                   └── If final: Process transcript         │
        │                       ├── Check if AI speaking → Interrupt │
        │                       ├── Echo detection (_is_echo)        │
        │                       └── _process_final_transcript()      │
        │                                                             │
        └── Task 3: _play_greeting() (non-blocking) ─────────────────┘
            └── Generate & play welcome message


6. GREETING GENERATION & PLAYBACK
═══════════════════════════════════════════════════════════════════════════════
   [audio_processor.py]
   └── _play_greeting()
        ├── Set is_ai_speaking = True (prevent interruption)
        ├── Generate greeting
        │   └── ai_assistant.get_greeting_audio(user_id)
        │       └── [ai_assistant.py]
        │           ├── Fetch user data from Weaviate
        │           │   └── data_provider.get_user_by_id(user_id)
        │           │       └── UserModelWeaviate.get_by_id()
        │           │           └── Extract: name, has_open_request
        │           │
        │           ├── Generate greeting text via LLM
        │           │   └── generate_greeting(user_name, has_open_request)
        │           │       └── GreetingGenerator.generate()
        │           │           ├── Build prompt with user context
        │           │           └── Call Gemini LLM → greeting text
        │           │
        │           ├── Save greeting to history
        │           │   └── history.add_message(AIMessage(greeting_text))
        │           │       └── PersistentChatMessageHistory
        │           │           └── ChatMessageModelWeaviate.create()
        │           │
        │           └── Generate TTS audio stream
        │               └── text_to_speech_stream(greeting_text)
        │                   └── Google Cloud TTS (gRPC streaming)
        │                       └── Yield audio chunks (48kHz, 16-bit)
        │
        ├── Queue audio for playback
        │   └── output_track.queue_audio(audio_chunk)
        │       └── [audio_track.py]
        │           └── Queue → WebRTC sends to mobile app
        │
        ├── Clear is_ai_speaking flag
        ├── Set echo detection timestamp (ai_speech_end_time)
        └── Signal greeting complete → greeting_complete.set()


7. USER SPEECH PROCESSING (Continuous Loop)
═══════════════════════════════════════════════════════════════════════════════
   [User speaks into microphone]
        │
        │ WebRTC audio stream → server
        ▼
   [audio_processor.py]
   └── _continuous_stt() receives final transcript
        │
        ├── Echo Detection Check
        │   └── _is_echo(transcript)
        │       ├── Cooldown check: time_since_ai_spoke < 2.0s?
        │       └── Word overlap: transcript ∩ last_ai_text > 60%?
        │       └── If echo → Skip processing ❌
        │
        ├── If not echo → Process
        │   └── _process_final_transcript(transcript)
        │       │
        │       ├── Set is_ai_speaking = True
        │       ├── Clear interrupt_event
        │       │
        │       ├── STAGE 1: LLM Processing (Streaming) ─────────────┐
        │       │   └── ai_assistant.generate_llm_response_stream()  │
        │       │       └── [ai_assistant.py]                        │
        │       │           ├── Save user message to history         │
        │       │           │   └── ChatMessageModelWeaviate.create()│
        │       │           │                                         │
        │       │           ├── Search providers (if needed)         │
        │       │           │   └── data_provider.search_providers() │
        │       │           │       └── Weaviate vector search       │
        │       │           │                                         │
        │       │           ├── Build conversation prompt            │
        │       │           │   ├── System prompt (stage-based)      │
        │       │           │   ├── Chat history                     │
        │       │           │   ├── Provider context                 │
        │       │           │   └── User message                     │
        │       │           │                                         │
        │       │           └── Stream from Gemini LLM               │
        │       │               └── Yield chunks of response text    │
        │       │                   │                                │
        │       ├── STAGE 2: Sentence Extraction ───────────────────┤
        │       │   └── Extract complete sentences from LLM stream  │
        │       │       ├── Regex: match .!? with whitespace        │
        │       │       ├── Merge short sentences (<3 words)        │
        │       │       └── Break long buffers at punctuation       │
        │       │           │                                        │
        │       ├── STAGE 3: TTS Processing (Parallel) ─────────────┤
        │       │   └── For each sentence:                          │
        │       │       └── process_sentence_to_audio()             │
        │       │           ├── Call TTS for sentence               │
        │       │           │   └── text_to_speech_stream()         │
        │       │           │       └── Google TTS API              │
        │       │           │           └── Yield audio chunks      │
        │       │           │                                        │
        │       │           ├── Collect all audio chunks            │
        │       │           ├── Apply fade-in/fade-out             │
        │       │           └── Wait for turn (ordered playback)    │
        │       │               │                                    │
        │       └── STAGE 4: Audio Playback (Ordered) ──────────────┘
        │           └── Queue audio to output_track
        │               └── output_track.queue_audio()
        │                   └── WebRTC → Mobile App speakers
        │
        └── Monitor playback completion
            └── _monitor_playback_completion()
                ├── Check output_track.audio_queue size
                ├── When empty for 100ms:
                │   ├── Set is_ai_speaking = False
                │   ├── Set ai_speech_end_time (echo cooldown)
                │   └── Track last_ai_text (for overlap detection)
                │
                └── Ready for next user input 🔄


8. INTERRUPTION HANDLING
═══════════════════════════════════════════════════════════════════════════════
   [User speaks while AI is responding]
        │
        │ STT detects speech
        ▼
   [audio_processor.py]
   └── _continuous_stt() receives transcript
        │
        ├── Check: is_ai_speaking == True?
        │   └── Yes → _trigger_interrupt()
        │       ├── Set interrupt_event
        │       ├── Cancel ongoing TTS tasks
        │       ├── Clear output audio queue
        │       └── Set is_ai_speaking = False
        │
        └── Skip processing this transcript (it was just interrupt signal)
            └── Log: "⏭️ Skipping transcript that triggered interrupt"


9. CONVERSATION HISTORY PERSISTENCE
═══════════════════════════════════════════════════════════════════════════════
   All messages saved to Weaviate throughout conversation:
   
   [ai_assistant.py]
   └── PersistentChatMessageHistory
       ├── On user message:
       │   └── ChatMessageModelWeaviate.create(user_id, "human", content)
       │
       ├── On AI response:
       │   └── ChatMessageModelWeaviate.create(user_id, "assistant", content)
       │
       └── On reconnection:
           └── load_from_store()
               └── Fetch all messages for user_id
                   └── Restore conversation context


LEGEND
═══════════════════════════════════════════════════════════════════════════════
   → : Synchronous call
   ▼ : Data flow direction
   └── : Function/method call
   ├── : Parallel operation
   🔄 : Loop/continuous process
   ❌ : Blocked/skipped
   ✓ : Success path




┌─────────────────────────────────────────────────────────────────┐
│                    HEARTBEAT LIFECYCLE                           │
└─────────────────────────────────────────────────────────────────┘

1. CONNECTION ESTABLISHED
═══════════════════════════════════════════════════════════════════
   [Mobile App connects via WebSocket]
        ↓
   [signaling_server.py] handle_websocket()
        ↓
   Line 207: heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws, handler, user_id))
        ↓
   [Task starts running in background]


2. HEARTBEAT LOOP - CONTINUOUS MONITORING
═══════════════════════════════════════════════════════════════════
   _heartbeat_loop(ws, handler, user_id)
   │
   └─► while not ws.closed:  ◄──────────────────────┐
           │                                         │
           ├─► await asyncio.sleep(HEARTBEAT_INTERVAL)  # Default: 10s
           │                                         │
           ├─► Check staleness:                     │
           │   time_since_pong = time.time() - handler.last_pong
           │   if time_since_pong > CONNECTION_TIMEOUT:  # 30s
           │       └─► Close connection (stale)     │
           │                                         │
           ├─► Send ping:                           │
           │   await ws.send_json({                 │
           │       'type': 'ping',                  │
           │       'timestamp': time.time()         │
           │   })                                   │
           │       ↓                                 │
           │   [Mobile App]                         │
           │       ↓                                 │
           │   Responds with pong                   │
           │       ↓                                 │
           │   Back to server                       │
           │       ↓                                 │
           │   handle_websocket() message loop      │
           │       ↓                                 │
           │   if msg_type == 'pong':               │
           │       handler.last_pong = time.time()  │
           │                                         │
           └─────────────────────────────────────────┘


3. DISCONNECTION / LOGOUT - CLEANUP
═══════════════════════════════════════════════════════════════════
   [Scenario A: Client disconnects]
   [Scenario B: Network error]
   [Scenario C: User closes app]
        ↓
   handle_websocket() → async for msg in ws: exits
        ↓
   finally block executes:
        ↓
   Line 249: heartbeat_task.cancel()  ✓ YES - EXPLICITLY CANCELLED
        ↓
   Line 250-253: try/await to handle CancelledError
        ↓
   Line 256: await handler.close()  # Cleanup peer connection & audio
        ↓
   Line 259: del self.active_connections[connection_id]
        ↓
   [Heartbeat task terminated]


4. STALE CONNECTION DETECTION
═══════════════════════════════════════════════════════════════════
   If client stops responding to pings:
   
   _heartbeat_loop() detects:
        time_since_pong > CONNECTION_TIMEOUT (30s)
        ↓
   Line 119: await ws.close()  # Force close WebSocket
        ↓
   This triggers the finally block in handle_websocket()
        ↓
   Cleanup executes (same as normal disconnection above)