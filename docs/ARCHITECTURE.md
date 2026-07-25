---
title: Via — System Architecture
tags: [via, architecture, voice, rag, backend, frontend]
created: 2026-07-24
updated: 2026-07-24
status: current
aliases: [Architecture, System Design]
---

# Via — System Architecture

> [!NOTE]
> Via is a **voice-first RAG assistant**. Users speak into a browser, audio streams over WebSocket to a FastAPI backend, which runs STT → LLM → TTS and streams audio back in real time.

---

## Related Notes

- [[FILE_REFERENCE]] — Full file-by-file reference
- [[VOICE_PIPELINE]] — Deep dive into the voice pipeline
- [[INTERVIEW_PREP]] — Interview Q&A and talking points

---

## High-Level Data Flow

```
Browser (Next.js)
  │
  │  WebSocket /ws/voice
  │  ← binary PCM16 audio frames (16kHz, 16-bit, mono)
  │  → binary TTS audio + JSON control messages
  │
FastAPI Backend
  │
  ├─ Deepgram (streaming WebSocket)  ← real-time STT
  │    └─ fallback: Whisper (local, file-based)
  │
  ├─ Groq API (llama-3.3-70b-versatile)  ← LLM streaming
  │
  ├─ Cartesia API  ← TTS streaming
  │
  ├─ Qdrant  ← vector search (RAG + memory)
  │
  ├─ Upstash Redis  ← session/message persistence
  │    └─ fallback: in-memory dict
  │
  └─ Emotion2Vec+  ← local speech emotion recognition
```

---

## End-to-End Voice Turn

```
1. Browser captures mic → PCM16 @ 16kHz via ScriptProcessor
2. Binary frames sent over WebSocket
3. backend/app/services/voice/deepgram.py forwards frames to Deepgram
4. Deepgram fires is_final transcript event
5. audio.py (AudioHandler) receives transcript
6. Emotion2Vec+ scores the audio for doubt
7. conversation_manager.py.stream_voice() runs:
   a. Qdrant semantic search (RAG retrieval)
   b. build_messages() assembles full prompt
   c. Groq streaming LLM → sentence chunker
   d. Each sentence → Cartesia TTS → binary audio chunks
   e. Chunks sent to browser with segment_start/end envelope
8. Browser AudioContext schedules chunks gap-free
9. Browser sends playback_ack per segment
10. Server tracks what was heard (for resume-from-interruption)
```

---

## Interruption Flow

```
User speaks mid-response
  │
  ├─ VAD fires → provisional interruption
  │    └─ playback stops immediately
  │
  ├─ STT confirms transcript
  │    └─ resume_intent.py classifies:
  │         resume | stop | side_question | clarification | topic_switch | backchannel
  │
  ├─ LLM generation continues in background (full answer buffered)
  │
  └─ Based on intent:
       resume       → speak_only() from paused_response.py resume point
       stop         → discard paused stack
       side_question → answer new question, push old to paused stack
```

---

## RAG Response Modes

| Mode | Condition | Behavior |
|---|---|---|
| **GROUNDED** | Evidence found in Qdrant above threshold | Answer with citations |
| **GENERAL** | No docs uploaded / low relevance score | Answer labeled as general knowledge |
| **UNSUPPORTED HIGH-RISK** | Sensitive domain (medical/legal/financial) + no source | Refuse to answer |

---

## Graceful Degradation Map

| Dependency Down | Fallback Behaviour |
|---|---|
| Qdrant | No RAG retrieval — still responds from LLM knowledge |
| Upstash Redis | In-memory dict for session state |
| Deepgram | Whisper (local, file-based, higher latency) |
| Emotion2Vec+ | Skipped silently, no emotion adaptation |
| Cartesia | Error segment sent to browser |

---

## Key Design Decisions

### Why binary WebSocket frames?
Raw PCM16 binary frames have minimal overhead vs HTTP chunked transfer. Deepgram's streaming API expects a live byte stream — encoding/decoding would add unnecessary latency.

### Why sentence-level LLM→TTS pipelining?
TTS starts before LLM finishes. Smaller chunks = lower perceived latency. The tradeoff is more TTS API calls and more complex audio scheduling, but perceived responsiveness wins.

### Why continue LLM generation after barge-in?
So the full answer is buffered. If the user says "go on", `speak_only()` resumes from `PausedResponse` without a second LLM call.

### Why `playback_ack` as the resume ground truth?
The server cannot infer what the user actually heard from its own state — network jitter and browser buffering mean audio chunks may arrive late or be dropped. `playback_ack` is the user-side confirmation.
