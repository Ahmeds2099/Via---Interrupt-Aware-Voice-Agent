---
title: Via — File Reference
tags: [via, files, reference, backend, frontend, api]
created: 2026-07-24
updated: 2026-07-24
status: current
aliases: [File Map, Codebase Reference]
---

# Via — File Reference

> [!NOTE]
> This is a navigational map of every significant file in the Via codebase. Use it alongside [[ARCHITECTURE]] and [[VOICE_PIPELINE]].

---

## Related Notes

- [[ARCHITECTURE]] — System design and data flow
- [[VOICE_PIPELINE]] — Voice pipeline deep dive
- [[INTERVIEW_PREP]] — Interview prep and talking points

---

## Backend

### Entry Points

| File | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app factory, mounts all routers, CORS config |
| `backend/app/core/config.py` | All env vars via Pydantic Settings — single source of truth |

---

### Voice Pipeline — `backend/app/services/voice/`

| File | Purpose | Key Exports |
|---|---|---|
| `handlers/audio.py` | Main WebSocket event orchestrator (~1300 lines) | `AudioHandler` — handles all client messages, STT events, interruption logic, Whisper fallback, watchdog timer |
| `session.py` | Per-connection state container | `VoiceSession` — holds voice task, playback tracker, VAD state, audio buffer, interruption flags |
| `vad.py` | Voice Activity Detection | `VADEngine` — pluggable Silero or energy-based VAD |
| `deepgram.py` | Streaming STT connection | `DeepgramSTT` — manages WebSocket to Deepgram, forwards PCM frames, fires transcript callbacks |
| `resume_intent.py` | Interruption intent classifier | `classify_intent()` — deterministic keyword rules + LLM fallback → returns `ResumeIntent` enum |
| `async_bridge.py` | Sync→async bridge | `run_sync_generator_async()` — runs blocking LLM/TTS generators on thread pool without blocking event loop |

---

### Conversation Layer

| File | Purpose | Key Exports |
|---|---|---|
| `conversation_manager.py` | Orchestrates full RAG+voice pipeline | `stream_voice()`, `speak_only()`, `build_messages()` |
| `conversation/conversation_state.py` | Runtime state machine | `ConversationState` — current response, paused stack, segment ack tracking |
| `conversation/paused_response.py` | Interrupted response tracker | `PausedResponse` — generated text, spoken text, acknowledged segments, resume point |
| `conversation/response_controller.py` | Thread-safe cancellation | `ResponseController` — cancel/complete signals shared between LLM, TTS, Cartesia threads |

---

### Supporting Services

| File | Purpose |
|---|---|
| `document_ingestion.py` | PDF/CSV/JSON → chunked Qdrant vectors (langchain splitter, 600 chars/120 overlap) |
| `domain_classifier.py` | LLM + keyword classifier → domain + safety category |
| `emotion/provider.py` | Emotion2Vec+ inference, doubt scoring, smoothing, clarification mode trigger |
| `session_repository.py` | Upstash Redis REST client with in-memory fallback; 24h message TTL, 30d memory TTL |
| `memory_service.py` | Store/retrieve user facts from Qdrant + Redis |
| `memory_extractor.py` | Pattern-based extraction of user facts from conversation text |

---

### API Routers — `backend/app/api/`

| Route | Method | Purpose |
|---|---|---|
| `/ws/voice` | WS | Real-time voice session |
| `/upload/` | POST | Document ingest |
| `/upload/demos` | GET | List demo documents |
| `/upload/demos/{slug}` | POST | Activate demo document |
| `/search/` | POST | Semantic search |
| `/ask/` | POST | RAG Q&A (non-streaming) |
| `/stream/` | POST | Streaming RAG response |
| `/stt/transcribe` | POST | File-based STT |
| `/tts/synthesize` | POST | TTS synthesis |
| `/system/status` | GET | Provider health check |

---

## Frontend

| File | Purpose |
|---|---|
| `frontend/hooks/usevoice.ts` | Central hook: WebSocket lifecycle, audio recording/playback, segment ack, doc uploads, health polling with exponential backoff |
| `frontend/lib/voice/websocket.ts` | Typed WebSocket wrapper with event handlers for the full voice protocol |
| `frontend/lib/voice/recorder.ts` | MediaStream → ScriptProcessor → PCM16 at 16kHz |
| `frontend/lib/voice/pcm.ts` | Linear interpolation downsampling + Float32→Int16 conversion |
| `frontend/components/voice/voiceorb.tsx` | Visual state indicator (idle/connecting/listening/thinking/speaking/interrupted/fallback/error) |
| `frontend/components/dashboard/architecturedashboard.tsx` | Live pipeline visualization with per-stage timing |
| `frontend/app/page.tsx` | Main UI: landing, session workspace, source drawer |

---

## Config & Environment

All environment variables are defined in `backend/app/core/config.py` (Pydantic Settings).

| Variable | Purpose | Default |
|---|---|---|
| `GROQ_API_KEY` | LLM (llama-3.3-70b-versatile) | — |
| `DEEPGRAM_API_KEY` | Primary STT | — |
| `CARTESIA_API_KEY` | TTS | — |
| `QDRANT_URL` | Vector DB | — |
| `UPSTASH_REDIS_REST_URL` | Session persistence | — |
| `VOICE_STT_PROVIDER` | `deepgram` or `whisper` | `deepgram` |
| `VOICE_ENABLE_EMOTION` | Toggle Emotion2Vec+ | `true` |
| `VOICE_MAX_TOKENS` | LLM token cap | `220` |
| `RAG_RELEVANCE_THRESHOLD` | Qdrant score cutoff | `0.55` |

---

## State Flow Between Files

```
WebSocket frame arrives
  │
  ▼
handlers/audio.py (AudioHandler)
  │  binary frame → deepgram.py
  │  transcript callback → conversation_manager.py
  │  VAD event → session.py (interruption flags)
  │
  ▼
conversation_manager.py (stream_voice)
  │  Qdrant search → RAG evidence
  │  build_messages() → prompt assembly
  │  Groq stream → sentence chunks
  │  Cartesia → audio bytes
  │
  ▼
session.py (VoiceSession)
  │  playback_ack tracking
  │  paused_response.py (PausedResponse)
  │  conversation_state.py (ConversationState)
  │
  ▼
response_controller.py
     cancel / complete signals
```
