# Via Completion and Free Deployment Plan

## Objective

Finish Via as a reliable local hackathon demo first. Deployment is a separate,
deferred phase and must not reduce or silently misrepresent the full local
feature set.

## Phase 1 - Complete Via

### Conversation intelligence

- Classify interruptions as stop, backchannel, clarification, side question,
  topic switch, resume, decline, or other.
- Give each decision a resume policy: discard, automatic, confirm,
  keep paused, or none.
- Use deterministic rules for obvious commands and Groq only for ambiguous
  turns, with a deterministic fallback during provider failures.
- Stop commands cancel immediately and discard the paused response.
- Backchannels continue naturally without becoming sidequests.
- Clarifications receive an answer and a contextual return only when useful.
- Independent side questions answer and then resume automatically.
- Topic switches discard the previous paused topic.
- Topic reminders do not create another confirmation loop.
- Remove the fixed "Does that clear things up?" response pattern.

### Emotion intelligence

- Confidence-gate raw Emotion2Vec results.
- Smooth reliable results over time and decay stale doubt.
- Treat explicit understanding phrases as stronger evidence than a noisy raw
  emotion label.
- Require strong or repeated stress evidence before adapting an answer.
- Show neutral, uncertain, confused, or stressed in the main interface.
- Keep raw provider labels only in expandable diagnostics.

### Lazy local models

- Emotion2Vec must not load during FastAPI startup or merely because a voice
  WebSocket connects. Load it on the first eligible completed utterance and
  reuse it thereafter.
- Whisper must not import or instantiate during normal Deepgram operation.
  Load it only after Deepgram fails and the user explicitly accepts fallback.
- FastEmbed must be one shared lazy service instead of several eager model
  instances.
- Every optional provider must fail safely without stopping the voice session.

### Provenance

- Do not speak uploaded filenames unless the user asks for the source name.
- Say "from the domain context", "from the material you shared", or
  "from my general knowledge".
- Show "Domain knowledge" in the normal interface while preserving exact
  source names in source details and Architecture diagnostics.

### Interface

- Use a calm, light, professional visual system with restrained teal accents.
- Reduce decorative glow, orbit effects, monospace labels, and dense telemetry.
- Keep the voice visualization focused on meaningful voice states.
- Show the latest exchange by default and make older history collapsible.
- Keep interim transcription visible.
- Make all error notices dismissible without removing retry actions.
- Add accessible Architecture help for mouse, keyboard, and touch.
- Explain traces as: user request, retrieval, emotion adaptation, provenance,
  and response latency.
- Put raw diagnostics behind progressive disclosure.

### Repository and documentation

- Move raw plans, backups, archives, generated exports, manual test artifacts,
  and uploads into an ignored `local-archive/` directory without deleting them.
- Keep runtime code, formal tests, demo data, polished docs, setup scripts,
  environment examples, and lockfiles in Git.
- Expand `.gitignore` so secrets, caches, uploads, models, archives, and build
  output cannot be pushed accidentally.
- Rewrite the README with a clear product explanation, architecture, local
  setup, run instructions, validation, and troubleshooting.

## Phase 2 - Deferred Free Deployment

Phase 2 starts only after Phase 1 is complete and accepted.

### Target

- Frontend: Vercel free tier.
- Backend: Render Free native Python runtime, without Docker.
- Durable state: Qdrant Cloud and Upstash Redis.

### Resource-constrained hosted profile

- Disable Emotion2Vec and Whisper fallback in the hosted Lite profile only.
- Replace Silero/PyTorch VAD with an adaptive lightweight energy VAD.
- Keep Deepgram, Groq, Cartesia, Qdrant, Redis, ingestion, interruption, and
  resumption enabled.
- Use a separate lightweight dependency file without Torch, FunASR, Silero,
  Faster Whisper, Torchaudio, AV, or CTranslate2.
- Require peak resident memory below 430 MB before claiming compatibility
  with Render's 512 MB free instance.
- Validate WebSockets, barge-in, ingestion, retrieval, and restoration in a
  clean environment where heavy ML packages are not installed.

### Hosted disclosure

When `NEXT_PUBLIC_DEPLOYMENT_PROFILE=lite`, the frontend will show:

> Resource-constrained demo build  
> Full emotional intelligence + Whisper fallback available in local/dev mode — this deployment is a resource-constrained demo build.

Emotion and Whisper must appear as "Local/dev only", never as broken or
failed.

### Known free-tier limits

- Render sleeps after approximately 15 idle minutes and can take about one
  minute to wake.
- Its free instance provides 512 MB RAM and 0.1 CPU.
- Local files are ephemeral; Qdrant and Redis remain durable.
- Provider quotas are separate from hosting limits.

## Phase 1 Acceptance Criteria

- Stop, backchannel, clarification, side question, topic switch, resume,
  decline, and topic-reminder scenarios behave distinctly.
- Emotion adaptation is confidence-gated and does not contradict explicit
  understanding.
- Emotion2Vec, Whisper, and FastEmbed load lazily and are reused.
- Uploaded filenames are not spoken by default.
- The frontend is responsive, accessible, understandable, and professionally
  presented.
- Backend tests, frontend lint, type checking, and production build pass.
- Git contains no secrets, local uploads, archives, environments, caches, or
  generated build output.
