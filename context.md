# Via Project Context & Modification Log

## Overview
Via is an interrupt-aware, emotion-adaptive, voice-first AI assistant built with FastAPI, Redis, Qdrant, Deepgram, Groq, Cartesia, and Next.js.

---

## Recent Session Modifications Log (Timestamp: 2026-07-25)

### Session Objectives & Summary
Executed technical refinements across persistent storage, dynamic prompt engineering, UI component fallbacks, real-time telemetry/architecture visualization, and emotion acknowledgment.

---

### Key Technical Changes & File Edits

#### 1. Persistent Session & Memory Storage (Redis / Qdrant)
- **`backend/app/services/session_repository.py`**:
  - Configured persistent session TTL (`SESSION_TTL_SECONDS = 86400` / 24 hours).
  - Configured long-term memory TTL (`MEMORY_TTL_SECONDS = 2505600` / 29 days).
  - Implemented `clear_session(client_id)` to flush Redis conversation turns and session keys.
  - Implemented `clear_memories(client_id)` to wipe vector points in Qdrant and key records.
- **`backend/app/services/conversation_service.py`**:
  - Updated `ConversationService.clear(session_id)` to purge local memory cache (`cls._states`, `cls._sessions`) and execute `session_repository.clear_session`.
- **`backend/app/services/memory_service.py`**:
  - Implemented `seed_architecture_memory(client_id)` to store Via's core architectural details into Qdrant vectors under payload key `system_architecture`.
  - Implemented `delete_client_memories(client_id)` using Qdrant `FilterSelector` with `MatchValue(value=client_id)` and deleted stored Redis memory keys.
- **`backend/app/services/voice/handlers/audio.py`**:
  - In `session_init`, triggered `seed_architecture_memory(client_id)` so Via can accurately explain its design.
  - In `_handle_transcript_event`, added voice trigger handlers for `"clear chats"`, `"clear conversation"`, and `"forget memories"` with confirmation state checks.
  - In `handle_control`, added WebSocket handlers for `"manual_clear_chats"` and `"manual_clear_memories"`.

#### 2. Dynamic Phrasing for General Knowledge
- **`backend/app/core/prompts.py`**:
  - Updated `SYSTEM_PROMPT` general provenance guidelines to blend fallbacks naturally into conversation without repeating repetitive robotic prefixes (e.g. "from my general knowledge").
- **`backend/app/services/prompt_builder.py`**:
  - Updated `evidence_instruction` when no retrieved context is present to request dynamic, varied conversational phrasing.

#### 3. Session Status Chip & Demo Documents Enhancement
- **`frontend/hooks/usevoice.ts`**:
  - Updated `socket.onSessionRestored` and `connect()` to set `restoredState` to `"New session"` by default whenever starting a new session or when 0 messages are restored, eliminating the old "Restored 0 messages and 0 memories" message.
  - Retained fallback initial state array for `demoDocuments` to guarantee instant one-click rendering.
- **`docs/demo-data/property-listings.csv` & `docs/demo-data/development-details.json`**:
  - Enhanced demo datasets with richer domain knowledge fields (HOA monthly breakdown, sqft, bathrooms, zoning R4, EV charging amenities, pet limits, and leasing policies) for grounded analysis questions.

#### 4. Ghost Response & False Interrupt State Cleanup
- **`frontend/hooks/usevoice.ts`**:
  - Refactored `socket.onTranscript` to purge lingering empty/dangling assistant turns (`turn.role === 'assistant' && !turn.text`) when a new user turn is recorded. This prevents permanently stuck "Preparing a response" skeletons and eliminates false interrupt states on subsequent questions.

#### 4. Real-Time Architecture Dashboard & Interruption Branching
- **`frontend/components/dashboard/architecturedashboard.tsx`**:
  - Implemented parent-child tree grouping in the **Conversation Trace** list (`nested-interrupt-turn`) to visually display interrupted turns as branched sub-articles.
- **`frontend/app/page.tsx`**:
  - Added dynamic stage-aware placeholder helper `stageToPlaceholder` (`"Transcribing..."`, `"Searching documents..."`, `"Thinking..."`, `"Synthesizing speech..."`).
  - Added **Clear chat** UI trigger button to `ConversationTimeline`.
  - Displayed `emotion-tag` badges on assistant conversation turns.

#### 5. Emotion Confusion & Stress Explicit Acknowledgment
- **`backend/app/core/prompts.py`**:
  - Updated `CLARIFICATION_MODE_PROMPT` so that whenever emotion analysis detects uncertainty, hesitation, stress, or confusion, Via **MUST** open its response with an explicit spoken acknowledgment (e.g., *"I can hear you seem a bit confused or stressed, so let me simplify this for you"*, *"I notice some uncertainty in your voice—let me break this down clearly"*).

---

## Instructions for Testing & Running Via

### Backend Launch
```bash
# Navigate to backend directory
cd backend

# Ensure virtual environment is active
.\venv\Scripts\activate

# Install dependencies if updated
pip install -r requirements.txt

# Launch Uvicorn dev server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend Launch
```bash
# Navigate to frontend directory
cd frontend

# Install Node modules if needed
npm install

# Launch Next.js dev server
npm run dev
```

### How to Test New Features:
1. **Persistent Session & Memory**:
   - Speak to Via, then reload the page. Your messages will be restored.
   - Say *"Clear chats"* or click **Clear chat** to flush Redis session history.
   - Ask Via: *"How does your architecture work?"* — Via will recall the seeded vector memory and explain its pipeline components.
2. **Dynamic General Knowledge Phrasing**:
   - Ask general questions without uploading documents. Via will respond naturally without repeating *"From my general knowledge"*.
3. **Demo Documents**:
   - Open the homepage and select any of the 3 demo document cards (**Real estate advisor**, **Property listings analyst**, **Development specialist**).
4. **Real-time Architecture & Interruption Trace**:
   - Switch to the **Architecture** tab while speaking. Observe real-time pipeline status.
   - Interrupt Via mid-sentence; the **Conversation Trace** panel will render the interrupted branch indented under the original question.
5. **Emotion Acknowledgment**:
   - Speak with an uncertain or hesitant voice tone. Via will recognize the tone and prefix its response with *"I can hear you're confused, let me simplify..."*.

---

## Next Steps
1. Add automated E2E tests for WebSocket memory clearing commands.
2. Expand Qdrant vector indexing to support multi-file domain cross-referencing.
3. Enhance emotion smoothing window parameters for fine-grained pitch variation handling.
