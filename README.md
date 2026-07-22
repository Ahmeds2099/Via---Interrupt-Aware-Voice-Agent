# Via — Interrupt-Aware Voice Agent

Via is an adaptive, interruptible universal voice agent. It listens continuously, lets you barge in mid-sentence, tracks an interrupted explanation, answers document-grounded questions, adapts its delivery to emotional cues, and restores session context after reconnects.

Via can work as a general assistant without a document. Uploading a PDF, CSV, or JSON gives it a temporary professional domain grounded in that source — property data turns it into a real-estate mentor, a software spec turns it into a project specialist.

---

## 🔴 Live Demo

> **[→ Try the Live Demo](#)** *(link coming soon)*

> **[→ Watch the Demo Video](#)** *(video coming soon)*

---

## ⚠️ A Note on the Live Demo

**The public demo is intentionally limited.** Please read this before judging it.

The live demo runs on **Render's free tier (512 MB RAM)**, which imposes hard constraints that are not present when running locally. Specifically:

### What is disabled in the demo build:

| Feature | Local / Dev | Live Demo |
|---|---|---|
| Neural Emotion2Vec (Emotion recognition) | ✅ Enabled | ❌ Disabled |
| Whisper local STT fallback | ✅ Enabled | ❌ Disabled |
| Silero neural VAD | ✅ Enabled | ❌ Disabled (Energy VAD used instead) |
| Response length | Full, natural | Capped at 1–2 sentences |

### Why is the demo slow?

1. **Cold starts:** Render's free tier spins the backend down after 15 minutes of inactivity. When you first open the demo, it may take **30–60 seconds** to wake up. The frontend will show a "Waking up..." state and retry automatically — just wait.
2. **Shared infrastructure:** The free tier runs on shared, resource-constrained machines, not dedicated hardware.
3. **No local ML models:** The neural models that power Via's full emotional intelligence (Emotion2Vec, Silero VAD, Whisper) consume 1–2 GB of RAM each. They simply cannot run on a 512 MB free-tier container. This is a deployment constraint, not a code limitation.
4. **LLM responses are deliberately shortened:** To prevent Deepgram's streaming buffer from overflowing under the slower processing pipeline, Via's responses are limited to 1–2 sentences in the demo. This is enough to test barge-in, interruptions, and resumption.

### What the demo *does* prove:

Despite these constraints, the core architecture is fully functional in the demo:
- ✅ Real-time WebSocket voice streaming
- ✅ Deepgram live transcription with interim results
- ✅ Barge-in / interruption detection
- ✅ Response resumption after interruption
- ✅ Document upload and grounded Q&A (RAG)
- ✅ Session persistence via Redis

**To see Via at full capability, run it locally using the instructions below.**

---

## What Via can do (Full Local Build)

- Stream speech through Deepgram Nova-2 with interim and final transcripts
- Stop speaking as soon as you barge in
- Distinguish stop commands, acknowledgments, clarifications, side questions, topic switches, resume requests, and declines
- Resume an interrupted response from the last confirmed playback boundary
- Use Whisper locally only after Deepgram fails and you accept the fallback
- Ingest PDF, CSV, and JSON while preserving page, row, and JSON-path metadata
- Retrieve relevant domain context through FastEmbed and Qdrant
- Store resumable session state through Upstash Redis
- Use local Emotion2Vec cues when they are reliable and consistent
- Show real provider state, provenance, retrieval, interruption, and latency in the Architecture workspace

LangGraph and Vapi are intentionally not used. Via owns its voice state machine directly, keeping interruption, playback acknowledgment, and resumption visible and testable.

---

## Architecture

```text
Browser microphone
  -> Web Audio PCM at 16 kHz
  -> FastAPI WebSocket
  -> Silero VAD (local) / Energy VAD (lite)
  -> Deepgram streaming transcription
  -> Redis session and memory restoration
  -> FastEmbed query embedding
  -> Qdrant document retrieval
  -> Groq response generation
  -> optional Emotion2Vec response adaptation (local only)
  -> Cartesia streaming speech
  -> browser playback acknowledgment
```

### Component responsibilities

| Component | Responsibility |
| --- | --- |
| Next.js | Landing, voice session, source management, playback, and observability UI |
| FastAPI WebSocket | Owns the real-time session and routes audio, control, and telemetry events |
| Silero VAD | Neural speech detection for immediate barge-in *(local only)* |
| Energy VAD | Pure-Python amplitude-based VAD *(lite/demo build)* |
| Deepgram | Primary streaming speech-to-text provider |
| Whisper | Consent-based local transcription fallback *(local only)* |
| Groq | Answers questions and classifies ambiguous interruptions |
| Cartesia | Streams Via's spoken response as audio |
| Emotion2Vec | Local speech-emotion evidence, loaded on the first eligible utterance *(local only)* |
| FastEmbed | Shared lazy text-embedding model for document and memory retrieval |
| Qdrant | Durable semantic vectors for uploaded knowledge and long-term memories |
| Upstash Redis | Fast session snapshots, recent messages, and memory restoration |

---

## Interruption behavior

- **Stop:** cancels speech, discards the paused response, says a brief acknowledgment
- **Backchannel:** phrases such as "got it" continue the paused answer naturally
- **Clarification:** Via answers simply and ends with a contextual choice about returning to the paused topic
- **Independent question:** Via answers it and resumes automatically
- **Topic switch:** the old paused response is discarded
- **Topic reminder:** Via states what was being discussed without starting a new confirmation loop

## Emotion behavior

Emotion is supporting evidence, not a diagnosis. Low-confidence Emotion2Vec labels are ignored, reliable observations are smoothed over recent turns, and stale doubt decays. Explicit language overrides noisy stress classifications.

Emotion2Vec does not load at startup or socket connect. It loads on the first eligible utterance and is reused.

> In the Lite/demo build, emotion is fully disabled. Via falls back to STT confidence and language cues only.

---

## Requirements

- Python 3.11 recommended
- Node.js 20 or newer
- A Chromium-based browser with microphone permission
- Groq, Deepgram, Cartesia, Qdrant Cloud, and Upstash Redis credentials

## Configure

Copy the environment example and fill in your credentials:

```powershell
Copy-Item .env.example backend/.env
```

Required values:

```dotenv
GROQ_API_KEY=
DEEPGRAM_API_KEY=
CARTESIA_API_KEY=
CARTESIA_VOICE_ID=
QDRANT_URL=
QDRANT_API_KEY=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
```

For the full local experience keep:
```dotenv
VOICE_ENABLE_EMOTION=true
VOICE_ALLOW_WHISPER_FALLBACK=true
VOICE_VAD_PROVIDER=silero
```

## Install

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --upgrade pip
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

Optional prefetch before a live demo:

```powershell
backend/.venv/Scripts/python.exe scripts/prefetch_emotion_model.py
backend/.venv/Scripts/python.exe scripts/create_demo_assets.py
```

## Run locally

Backend:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
Set-Location frontend
npm run dev
```

Open `http://localhost:3000`.

---

## Deployment

Via supports two deployment profiles:

| | Local / Full | Render + Vercel (Lite) |
|---|---|---|
| `requirements.txt` | `requirements.txt` | `requirements-lite.txt` |
| `VOICE_ENABLE_EMOTION` | `true` | `false` |
| `VOICE_ALLOW_WHISPER_FALLBACK` | `true` | `false` |
| `VOICE_VAD_PROVIDER` | `silero` | `energy` |
| RAM required | ~2 GB | < 450 MB |

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for full step-by-step instructions.

---

## Troubleshooting

**Backend is unreachable** — Confirm Uvicorn is running. Open `/health` directly. Check that the frontend API URL and backend host use compatible addresses.

**CORS blocks a request** — Add the exact frontend origin to `CORS_ORIGINS`. Restart FastAPI after changing the environment.

**Voice WebSocket cannot open** — Confirm `/system/status` succeeds. HTTP frontends use `ws://`; HTTPS frontends require `wss://`.

**Emotion model slow on first use** — Run the prefetch script before the demo. Via remains usable if emotion loading fails.

**Qdrant missing payload index** — Restart the backend so collection initialization can create the `client_id` and `document_id` indexes.

**Demo is slow / Via takes too long to respond** — This is expected on the free-tier demo. Run locally for the full experience.
