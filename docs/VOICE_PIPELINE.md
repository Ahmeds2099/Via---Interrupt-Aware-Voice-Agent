---
title: Via — Voice Pipeline Deep Dive
tags: [via, voice, pipeline, stt, tts, llm, interruption, vad, deepgram, cartesia, groq]
created: 2026-07-24
updated: 2026-07-24
status: current
aliases: [Voice Pipeline, Audio Pipeline]
---

# Via — Voice Pipeline Deep Dive

> [!NOTE]
> This document covers every stage of the voice pipeline in detail: audio ingestion, STT, VAD, LLM, TTS, browser playback, interruption handling, and the emotion layer.

---

## Related Notes

- [[ARCHITECTURE]] — High-level system design
- [[FILE_REFERENCE]] — File-by-file reference
- [[INTERVIEW_PREP]] — Interview prep and talking points

---

## Stage 1 — Audio Ingestion (Browser → Server)

- `recorder.ts` taps `getUserMedia` via `ScriptProcessor` (4096-sample buffer)
- Samples downsampled from device native rate → **16kHz** via linear interpolation in `pcm.ts`
- Float32 → Int16 conversion → binary WebSocket frame
- No compression — raw **PCM16** keeps Deepgram latency minimal

> [!WARNING]
> `ScriptProcessor` is deprecated in the Web Audio API spec. Migration to `AudioWorklet` is a known gap — see [[#Known Gaps]].

---

## Stage 2 — STT: Deepgram Streaming

- `deepgram.py` opens a **persistent WebSocket** to Deepgram's streaming endpoint
- Each binary PCM16 frame from the browser is forwarded directly
- Deepgram returns two result types:
  - `interim` — low latency, unstable — forwarded to browser for live transcript display
  - `is_final` — committed transcript — triggers LLM dispatch in `audio.py`
- `audio.py` acts on `is_final` only for LLM dispatch

**Fallback**: if Deepgram fails or user opts in, `audio.py` buffers audio and sends to local Whisper via `stt_fallback_choice` protocol message. Whisper is file-based (not streaming) — significantly higher latency.

---

## Stage 3 — VAD: Voice Activity Detection

- `vad.py` runs on **every incoming audio frame**
- Two engines available:
  - **Silero** (neural, more accurate)
  - **Energy-based** (lighter, faster)
- VAD fires a **provisional interruption immediately** — playback stops without waiting for STT confirmation
- A **watchdog timer** in `audio.py` recovers if VAD fired but no transcript arrives within N ms (noise false positive)

---

## Stage 4 — LLM: Groq Streaming

`conversation_manager.build_messages()` assembles the prompt in this order:

1. System prompt (persona + RAG instructions)
2. Voice-specific prompt (brevity, spoken-word style)
3. Emotion context (if doubt score elevated)
4. Interruption context (if resuming)
5. Retrieved memories from Qdrant
6. Conversation history
7. RAG evidence chunks

Groq streams tokens. `conversation_manager` chunks by **sentence boundary** before sending to TTS.

> [!IMPORTANT]
> **Critical design:** LLM generation continues even after a barge-in so the full answer is available for resume without a second LLM call.

---

## Stage 5 — TTS: Cartesia Streaming

- Each sentence chunk is sent to Cartesia **as it arrives** from the LLM
- Cartesia streams audio bytes back
- `async_bridge.py` runs the blocking Cartesia generator on a **thread pool** to avoid blocking the asyncio event loop
- Audio bytes are sent to the browser wrapped in segment envelopes:

```
assistant_segment_start  (JSON control message)
  │
  ├─ binary audio chunk 1
  ├─ binary audio chunk 2
  └─ ...
  │
assistant_segment_end    (JSON control message)
  │
  ▼
Browser sends: playback_ack
```

---

## Stage 6 — Browser Playback

- `usevoice.ts` receives binary audio chunks and schedules them on the **Web Audio API `AudioContext`**
- **Gap-free scheduling**: each chunk's start time = end time of the previous chunk
- Text is revealed only when the **first audio chunk** of a segment plays — avoids text racing ahead of speech
- `playback_ack` messages flow back to the server per segment so the server knows exactly what the user heard

---

## Stage 7 — Interruption & Resume

### Full Interruption Flow

```
User speaks mid-response
  │
  ├─ VAD fires → stop AudioContext playback → send `interrupted` message
  │
  ├─ STT confirms transcript
  │    └─ resume_intent.py classifies:
  │         resume | stop | side_question | clarification | topic_switch | backchannel
  │
  └─ PausedResponse records:
       - generated_text (full buffered LLM output)
       - spoken_text (what was sent to Cartesia)
       - last_ack'd segment (what user confirmed hearing)
```

### Resume Flow

```
User says "go on" (intent: resume)
  │
  └─ speak_only() called with text from PausedResponse.resume_point()
       - Skips LLM entirely
       - Cartesia re-synthesizes from the resume point
       - No second LLM API call needed
```

### Intent Categories

| Intent | Action |
|---|---|
| `resume` | `speak_only()` from `PausedResponse.resume_point()` |
| `stop` | Discard paused stack entirely |
| `side_question` | Answer new question, push old response to paused stack |
| `clarification` | Simplified re-answer of current topic |
| `topic_switch` | Start fresh on new topic |
| `backchannel` | Acknowledge ("mm-hmm"), continue speaking |

---

## Stage 8 — Emotion Pipeline

- `emotion/provider.py` runs **Emotion2Vec+** on each audio segment (lazy-loaded, failure-safe)
- Derives `doubt_score` from three signals:
  1. **Emotion labels** — confusion/uncertainty labels mapped to higher doubt
  2. **Deepgram STT confidence** — low confidence → higher doubt
  3. **Linguistic markers** — "what?", "huh?", "I don't understand" in transcript
- Smoothed across N observations to prevent flicker
- When `doubt_score > threshold`:
  - `clarification_mode = True`
  - `build_messages()` injects a simpler language instruction into the prompt

---

## Latency Optimization Table

| Stage | Optimization |
|---|---|
| STT | Deepgram streaming — no batch wait |
| LLM→TTS | Sentence-level pipelining — TTS starts before LLM finishes |
| TTS→Browser | Streaming bytes — not waiting for full audio render |
| Interruption | VAD stops playback before STT confirms (provisional) |
| Sync generators | `async_bridge.py` prevents asyncio event loop blocking |

---

## Known Gaps

| Gap | Impact | Proposed Fix |
|---|---|---|
| No retry on Cartesia/Groq mid-stream | User gets silence on failure | Wrap generators with exponential backoff; send error segment |
| No backpressure on TTS queue | Sentences queue up if Cartesia is slow | Bounded async queue; apply backpressure to LLM chunker |
| Whisper fallback is file-based | Significantly higher latency than Deepgram streaming | Faster-Whisper local server with WebSocket |
| `ScriptProcessor` deprecated | Audio jitter in browser | Migrate to `AudioWorklet` |
| No latency telemetry | Can't measure actual bottlenecks | Instrument each stage; export to time-series store |
| No load testing | No connection limits or per-connection resource caps | Load test + add connection limiting |
| No auth on `/ws/voice` | Anyone can connect | Add WebSocket auth (token in query param or subprotocol) |

---

## Protocol Message Reference

| Message Type | Direction | Purpose |
|---|---|---|
| `binary frame` | Client → Server | Raw PCM16 audio |
| `stt_fallback_choice` | Client → Server | Switch to Whisper |
| `interrupted` | Client → Server | User started speaking mid-response |
| `playback_ack` | Client → Server | Segment was played back |
| `assistant_segment_start` | Server → Client | Begin audio segment |
| `assistant_segment_end` | Server → Client | End audio segment |
| `interim_transcript` | Server → Client | Live STT interim result |
| `session_restored` | Server → Client | History loaded from Redis |
