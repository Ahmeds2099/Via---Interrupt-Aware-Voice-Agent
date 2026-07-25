---
title: Via — Interview Prep
tags: [via, interview, prep, talking-points, questions, answers]
created: 2026-07-24
updated: 2026-07-24
status: current
aliases: [Interview Prep, Demo Prep, Talking Points]
---

# Via — Interview & Demo Prep

> [!IMPORTANT]
> Use this alongside [[ARCHITECTURE]], [[VOICE_PIPELINE]], and [[FILE_REFERENCE]]. This note is structured for rapid review before a technical interview or live demo.

---

## Related Notes

- [[ARCHITECTURE]] — System design and data flow
- [[VOICE_PIPELINE]] — Voice pipeline deep dive
- [[FILE_REFERENCE]] — File-by-file reference

---

## One-Page Elevator Pitch

> Via is a voice-first AI assistant that lets users have natural spoken conversations with their own documents. You upload a PDF, CSV, or JSON file, and Via indexes it into a vector database. Then you just talk — Via transcribes your speech in real time using Deepgram's streaming API, retrieves relevant document chunks from Qdrant, generates a response with a Groq-hosted LLM, and speaks the answer back using Cartesia TTS, all with sub-second pipeline latency.
>
> The part I'm most proud of is the interruption handling. When you start talking mid-response, Via stops playing immediately — no waiting for the current sentence to finish. It classifies your intent: are you asking a follow-up, asking it to stop, or asking it to continue? If you say "go on," it resumes from exactly where it left off, because the full LLM response was buffered in the background even while you were interrupting. That's the `PausedResponse` state machine.
>
> The system is also provenance-aware. For sensitive domains like medical or legal, Via refuses to answer without document support rather than hallucinating. Every response is labeled as either grounded in your documents or general knowledge.
>
> The stack is FastAPI + Python on the backend, Next.js + React on the frontend, with Qdrant for vectors, Upstash Redis for session persistence, and Emotion2Vec+ for speech emotion recognition that adapts the response style when the user sounds confused. Every external dependency has a fallback path so the system degrades gracefully rather than failing hard.

---

## Concepts You Must Explain Fluently

### WebSocket Voice Protocol
- Why binary frames over WebSocket instead of HTTP chunked transfer
- How the client/server message envelope works (segment lifecycle: `assistant_segment_start` → audio chunks → `assistant_segment_end` → `playback_ack`)
- Backpressure and flow control in a streaming audio WebSocket

### Streaming STT (Deepgram)
- Difference between interim and final transcripts and when to act on each
- Why you forward raw PCM16 rather than compressed audio
- Deepgram's streaming WebSocket API model (keep-alive, KeepAlive messages, endpointing config)

### Sentence-Level LLM→TTS Pipelining
- Why you chunk by sentence rather than token or full response
- The tradeoff: smaller chunks = lower latency but more TTS API calls and more audio scheduling complexity
- How `async_bridge.py` solves the sync generator / async event loop impedance mismatch

### Interruption Handling (Barge-in)
- Two-phase: VAD provisional → STT confirmation
- Why you continue LLM generation after barge-in (resume semantics)
- The watchdog timer pattern for false VAD triggers
- `PausedResponse` state: what gets tracked and why `playback_ack` is the ground truth for resume point

### RAG Pipeline
- Qdrant vector search with relevance threshold gating (0.55)
- Provenance-aware response modes: GROUNDED / GENERAL / UNSUPPORTED HIGH-RISK
- Domain safety classification and why it gates response behaviour

### Emotion-Adaptive Responses
- Multi-signal doubt scoring (model output + STT confidence + linguistic markers)
- Smoothing to prevent flicker
- How it feeds back into `build_messages()`

### Graceful Degradation
- Every external dependency has a fallback
- Why this matters for a real-time voice system — a hard failure mid-call is worse than degraded quality

---

## Interview Q&A

### Q: Walk me through what happens from the moment a user starts speaking to when they hear a response.

> The browser captures mic audio via ScriptProcessor, downsamples to 16kHz PCM16, and streams binary frames over a WebSocket to the FastAPI backend. The backend forwards those frames to Deepgram's streaming WebSocket. When Deepgram fires an `is_final` transcript, `AudioHandler` dispatches to `conversation_manager.stream_voice()`. That function runs a Qdrant semantic search for relevant document chunks, assembles the full prompt including history, memories, and RAG evidence, then streams tokens from Groq. As each sentence completes, it's sent to Cartesia for TTS. Cartesia streams audio bytes back, which we forward to the browser wrapped in segment envelopes. The browser schedules those chunks on the Web Audio API for gap-free playback and sends `playback_ack` messages back so we know exactly what the user heard.

---

### Q: How does your interruption handling work?

> It's two-phase. VAD fires immediately when the user starts speaking — we stop playback right away without waiting for a transcript, because latency matters. Then Deepgram confirms the transcript and `resume_intent.py` classifies the intent: resume, stop, side question, clarification, topic switch, or backchannel. Critically, LLM generation continues even after the barge-in so the full answer is buffered. If the user says "go on," we call `speak_only()` with the already-generated text from `PausedResponse` — no second LLM call needed. We also have a watchdog timer that recovers if VAD fired but no transcript arrives, which handles noise false positives.

---

### Q: What would you do to reduce end-to-end latency?

> The current pipeline already does sentence-level pipelining — TTS starts before LLM finishes. The next wins would be:
> 1. Migrate from `ScriptProcessor` to `AudioWorklet` to reduce audio processing jitter in the browser.
> 2. Add explicit latency telemetry so we can measure each stage and find the actual bottleneck rather than guessing.
> 3. Evaluate Deepgram's `endpointing` parameter — tuning how quickly it fires `is_final` is a direct latency lever.
> 4. Consider a smaller/faster LLM for the first sentence to get audio playing sooner, then switch to the full model for the rest.

---

### Q: What are the weaknesses in the current implementation?

> A few honest ones: no retry logic on Cartesia or Groq mid-stream failures — if TTS drops mid-sentence the user just gets silence. No backpressure between the LLM sentence queue and TTS — if Cartesia is slow, sentences queue up. The Whisper fallback is file-based, not streaming, so it's significantly higher latency than Deepgram. And `ScriptProcessor` is deprecated in the Web Audio API spec. I'd prioritise the retry logic first since it's a correctness issue, then the `AudioWorklet` migration.

---

### Q: How does your RAG pipeline decide when to answer vs. refuse?

> We classify uploaded documents into domains with safety categories — general, financial, legal, medical, regulated. When a query comes in, we run Qdrant semantic search with a relevance threshold of 0.55. If we find evidence above threshold, we answer in GROUNDED mode with citations. If no documents are uploaded or relevance is below threshold, we answer in GENERAL mode labeled as general knowledge. But if the domain is flagged as high-risk (medical, legal, financial) and we have no source support, we refuse rather than hallucinate — that's the UNSUPPORTED HIGH-RISK mode.

---

### Q: How do you handle state across a multi-turn conversation?

> Session state lives in two places. Conversation history and user memories are persisted in Upstash Redis with a 24-hour TTL for messages and 30-day TTL for memories. Within a single WebSocket connection, `VoiceSession` holds the runtime state — current response, paused stack, VAD state, audio buffer. `ConversationState` is the state machine for the current turn. When a session reconnects, `session_repository.py` restores history from Redis and sends a `session_restored` message to the client.

---

## Weak Points — Discuss Honestly

| Gap | How You'd Address It |
|---|---|
| No retry on Cartesia/Groq mid-stream | Wrap streaming generators with exponential backoff; on failure, send an error segment and offer to retry |
| No backpressure on TTS queue | Add a bounded async queue between sentence chunker and TTS; apply backpressure to LLM generation |
| Whisper fallback is not streaming | Use Whisper's streaming mode or a local Faster-Whisper server with WebSocket |
| `ScriptProcessor` deprecated | Migrate to `AudioWorklet` for lower-jitter audio processing |
| No latency telemetry | Instrument each pipeline stage with timestamps; export to a time-series store |
| No load testing | The WebSocket handler has no connection limits or per-connection resource caps |
| No auth on `/ws/voice` | Anyone can connect — add token-based auth in query param or WS subprotocol |

---

## Curated Resources

### Deepgram
- [Deepgram Streaming STT docs](https://developers.deepgram.com/docs/getting-started-with-live-streaming-audio) — endpointing, interim results, KeepAlive
- [Deepgram Python SDK source](https://github.com/deepgram/deepgram-python-sdk)

### Cartesia
- [Cartesia TTS API docs](https://docs.cartesia.ai) — streaming audio, voice IDs, latency model

### Groq
- [Groq API docs](https://console.groq.com/docs/openai) — streaming, rate limits, llama-3.3-70b-versatile context window

### Qdrant
- [Qdrant vector search docs](https://qdrant.tech/documentation/)
- [fastembed docs](https://github.com/qdrant/fastembed) — BAAI/bge-small-en-v1.5 embedding model

### Voice Pipeline Design
- [Livekit blog: Real-time voice AI latency](https://blog.livekit.io/latency-the-new-frontier-for-voice-ai-assistants/)
- [Web Audio API AudioWorklet migration guide](https://developer.chrome.com/blog/audio-worklet/)

### Interruption / Barge-in
- [Silero VAD](https://github.com/snakers4/silero-vad)
- [Emotion2Vec paper](https://arxiv.org/abs/2312.15185)

### FastAPI
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/)
