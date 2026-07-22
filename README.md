# Via

Via is an adaptive, interruptible universal voice agent built for the OneInbox
Voice AI Engineer Hackathon. It listens continuously, lets the user barge in,
keeps track of an interrupted explanation, answers document-grounded questions,
adapts its delivery to reliable emotional cues, and restores session context.

Via can work as a general assistant without a document. Uploading a PDF, CSV,
or JSON file gives it a temporary professional domain grounded in that source.
For example, property data turns Via into a grounded real-estate mentor while a
software specification turns it into a project specialist.

## What Via can do

- Stream speech through Deepgram Nova-2 with interim and final transcripts.
- Stop speaking as soon as the user barges in.
- Distinguish stop commands, acknowledgments, clarifications, side questions,
  topic switches, resume requests, and declines.
- Resume an interrupted response from the last confirmed playback boundary.
- Use Whisper locally only after Deepgram fails and the user accepts fallback.
- Ingest PDF, CSV, and JSON while preserving page, row, and JSON-path metadata.
- Retrieve relevant domain context through FastEmbed and Qdrant.
- Store resumable session state through Upstash Redis.
- Use local Emotion2Vec cues only when they are reliable and consistent.
- Show real provider state, provenance, retrieval, interruption, and latency in
  the Architecture workspace.

LangGraph and Vapi are intentionally not used. Via owns its voice state machine
directly, keeping interruption, playback acknowledgment, and resumption visible
and testable.

## Architecture

```text
Browser microphone
  -> Web Audio PCM at 16 kHz
  -> FastAPI WebSocket
  -> Silero voice activity detection
  -> Deepgram streaming transcription
  -> Redis session and memory restoration
  -> FastEmbed query embedding
  -> Qdrant document retrieval
  -> Groq response generation
  -> optional Emotion2Vec response adaptation
  -> Cartesia streaming speech
  -> browser playback acknowledgment
```

### Component responsibilities

| Component | Responsibility |
| --- | --- |
| Next.js | Landing, voice session, source management, playback, and observability UI |
| FastAPI WebSocket | Owns the real-time session and routes audio, control, and telemetry events |
| Silero VAD | Detects speech start for immediate barge-in and speech end for turn completion |
| Deepgram | Primary streaming speech-to-text provider |
| Whisper | Consent-based local transcription fallback, loaded only on demand |
| Groq | Answers questions and classifies only ambiguous interruptions |
| Cartesia | Streams Via's spoken response as audio |
| Emotion2Vec | Local speech-emotion evidence, loaded on the first eligible utterance |
| FastEmbed | Shared lazy text-embedding model for document and memory retrieval |
| Qdrant | Durable semantic vectors for uploaded knowledge and long-term memories |
| Upstash Redis | Fast session snapshots, recent messages, and memory restoration |

Qdrant and Redis are complementary. Qdrant answers semantic questions such as
"which stored passage is relevant?" Redis answers state questions such as
"what was this client discussing and what should be restored now?"

## Interruption behavior

Via does not treat every interruption as a sidequest:

- **Stop:** cancels speech, discards the paused response, and says only a brief
  acknowledgment.
- **Backchannel:** phrases such as "got it" continue the paused answer naturally.
- **Clarification:** Via answers simply and ends with a contextual choice about
  returning to the paused topic.
- **Independent question:** Via answers it and resumes automatically.
- **Topic switch:** the old paused response is discarded.
- **Topic reminder:** Via states what was being discussed without starting a new
  confirmation loop.

## Emotion behavior

Emotion is supporting evidence, not a diagnosis. Low-confidence Emotion2Vec
labels are ignored, reliable observations are smoothed over recent turns, and
stale doubt decays. Explicit language such as "I understand" overrides a noisy
stress classification. The main interface uses neutral, uncertain, confused,
or stressed; raw model labels remain available only in diagnostics.

Emotion2Vec does not load when FastAPI starts or when a socket merely connects.
It loads in a worker thread on the first eligible utterance and is reused.

## Requirements

- Python 3.11 recommended
- Node.js 20 or newer
- A Chromium-based browser with microphone permission
- Groq, Deepgram, Cartesia, Qdrant Cloud, and Upstash Redis credentials
- Windows PowerShell commands below, or equivalent commands for your shell

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

Keep `VOICE_STT_PROVIDER=deepgram` and
`VOICE_ALLOW_WHISPER_FALLBACK=true` for the complete local profile. Never put
backend secrets in a `NEXT_PUBLIC_` variable.

## Install

From the repository root:

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

The first model download can take several minutes. Prefetching prevents that
download from occurring during a presentation.

## Run locally

Backend terminal:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
Set-Location frontend
npm run dev
```

Open `http://localhost:3000`. The backend status endpoint is
`http://127.0.0.1:8000/system/status`.

Use the same hostname consistently. If the page is opened at `localhost:3000`,
keep the configured API URL on a loopback address. For testing from another
device, bind Uvicorn to `0.0.0.0`, configure the machine's LAN address in
`NEXT_PUBLIC_API_URL`, and add that frontend origin to `CORS_ORIGINS`.

## Recommended demo flow

1. Open `/system/status` and confirm Deepgram, Groq, Cartesia, Qdrant, and Redis.
2. Start Via and ask a general question.
3. Interrupt with an independent question and let Via resume automatically.
4. Interrupt with "stop now" to demonstrate semantic cancellation.
5. Load the real-estate PDF, CSV, or JSON demo.
6. Ask a source-specific question and show the Domain knowledge provenance.
7. Open Architecture to show the real retrieval path and measured latency.
8. Refresh and reconnect to demonstrate Redis-backed restoration.

## Validate

Backend:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Frontend:

```powershell
Set-Location frontend
npm run lint
npx tsc --noEmit
npm run build
```

## Troubleshooting

### Backend is unreachable

- Confirm Uvicorn is still running.
- Open `/health` directly.
- Check that the frontend API URL and backend host use compatible loopback or
  LAN addresses.
- On Windows, try another port if WinError 10013 indicates a reserved port.

### CORS blocks a successful request

Add the exact frontend origin, including scheme and port, to `CORS_ORIGINS`.
Restart FastAPI after changing the environment.

### Voice WebSocket cannot open

- Confirm `/system/status` succeeds first.
- HTTP frontends use `ws://`; HTTPS frontends require `wss://`.
- Check browser microphone permission and backend WebSocket logs.

### Emotion model is slow on first use

Run the prefetch script before the demo. Via remains usable if emotion loading
fails; the provider will be reported as unavailable instead of stopping voice.

### Qdrant reports a missing payload index

Restart the backend so collection initialization can create the required
`client_id` and `document_id` payload indexes.

### Provider rate limits

Wait for the provider window to reset or use a different valid key. Repeating a
mis-transcribed wake word can consume STT, LLM, and TTS quota, so Via includes
Deepgram keyword hints for its name.

## Deployment status

Free hosted deployment is intentionally deferred until the complete local
application is accepted. The planned Lite deployment uses Vercel and Render's
native Python runtime without Docker. It will disable Emotion2Vec and Whisper
only in the hosted resource-constrained profile while keeping them in local and
development mode.

The Lite profile will not be described as supported until a clean environment
stays below 430 MB peak memory and passes WebSocket, barge-in, retrieval, and
session-restoration tests.

The hosted frontend and deployment documentation will state:

> Full emotional intelligence + Whisper fallback available in local/dev mode — this deployment is a resource-constrained demo build.

See [Via Completion and Free Deployment Plan](docs/Via-Completion-and-Free-Deployment-Plan.md)
and [Via Demo Architecture Handbook](docs/Via-Demo-Architecture-Handbook.md).
