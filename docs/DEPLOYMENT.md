# Via Deployment Guide

This document outlines the deployment strategy for the Via voice assistant. Because of the intensive resource requirements of the machine learning models (Emotion2Vec, Silero VAD, Faster Whisper), Via supports two distinct deployment profiles: **Full** (for local/dedicated hosting) and **Lite** (for free-tier platforms like Render and Vercel).

---

## 1. Deployment Profiles

### Full Profile
The Full profile utilizes all advanced capabilities including neural emotion recognition, deep-learning based voice activity detection, and local STT fallback capabilities.
- **Environment:** Dedicated VPS, AWS EC2, or powerful local machines.
- **Memory Requirements:** ~2GB+ RAM.
- **Requirements File:** `backend/requirements.txt`
- **Settings:** `VOICE_ENABLE_EMOTION=true`, `VOICE_ALLOW_WHISPER_FALLBACK=true`, `VOICE_VAD_PROVIDER=silero`

### Lite Profile (Free Tier)
The Lite profile disables heavy ML models, replacing them with lightweight heuristics and graceful degradation mechanisms to fit within strict memory limits (e.g., Render's 512MB limit).
- **Environment:** Render (Backend), Vercel (Frontend).
- **Memory Requirements:** < 450MB RAM.
- **Requirements File:** `backend/requirements-lite.txt`
- **Settings:** `VOICE_ENABLE_EMOTION=false`, `VOICE_ALLOW_WHISPER_FALLBACK=false`, `VOICE_VAD_PROVIDER=energy`

---

## 2. Environment Variables

### General Configuration
- `ENVIRONMENT`: `development` | `production`
- `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g., `https://via-frontend.vercel.app`)

### Model & Feature Flags (Critical for Deployment)
- `VOICE_ENABLE_EMOTION`: `true` | `false` - Toggles Emotion2Vec neural model. Set to `false` for Lite.
- `VOICE_ALLOW_WHISPER_FALLBACK`: `true` | `false` - Toggles Faster Whisper fallback. Set to `false` for Lite.
- `VOICE_VAD_PROVIDER`: `silero` | `energy` - Selects Voice Activity Detection engine. Set to `energy` for Lite.

### Provider API Keys
- `DEEPGRAM_API_KEY`: Required for primary STT.
- `GROQ_API_KEY`: Required for ultra-low latency LLM inference.
- `CARTESIA_API_KEY`: Required for neural TTS.

### Vector Storage
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`: Connection details for Qdrant Cloud. (Use cloud instance for serverless environments).

### Frontend Variables
- `NEXT_PUBLIC_API_URL`: The backend URL (e.g., `https://via-backend.onrender.com`). WebSockets will automatically upgrade via `wss://`.
- `NEXT_PUBLIC_DEPLOYMENT_PROFILE`: `full` | `lite` - Modifies UI disclosures and telemetry labels.

---

## 3. Deploying to Render (Backend)

We deploy the Via backend to Render's Free Web Service tier (512MB RAM).

1. Connect your repository to Render.
2. Set the **Build Command**: `pip install -r backend/requirements-lite.txt` (Crucial to use the lite requirements).
3. Set the **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
   *(Limiting to 1 worker prevents loading duplicate copies of FastEmbed into memory.)*
4. Add all environment variables listed above (Ensure `VOICE_ENABLE_EMOTION=false`, `VOICE_ALLOW_WHISPER_FALLBACK=false`, and `VOICE_VAD_PROVIDER=energy`).
5. Render will automatically handle spin-down after 15 minutes of inactivity. The frontend is built with exponential backoff to handle ~1 minute spin-up delays smoothly.

---

## 4. Deploying to Vercel (Frontend)

1. Connect your repository to Vercel.
2. Ensure the Framework Preset is set to **Next.js**.
3. Set the **Root Directory** to `frontend`.
4. Add the Environment Variables:
   - `NEXT_PUBLIC_API_URL`: (Your Render URL)
   - `NEXT_PUBLIC_DEPLOYMENT_PROFILE=lite`
5. Deploy.

---

## Graceful Degradation Details

When running the Lite profile, Via still provides a highly performant and responsive experience:
- **Clarification Logic:** Adapts to purely rely on STT confidence and language cues instead of failing when emotion data is absent.
- **Dashboard Telemetry:** The Architecture dashboard dynamically labels missing ML providers as "Local/dev only" rather than error states.
- **Lazy Loading:** All heavy imports are lazily executed and explicitly shielded by environment variable checks to prevent `ImportError` crashes.
