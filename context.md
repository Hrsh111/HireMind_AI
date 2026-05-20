# HireMind AI - Project Context

## Project Overview

**HireMind AI** is an AI-powered technical interview platform designed to conduct realistic DSA (Data Structures & Algorithms), system design, and behavioral interviews with real-time voice/video interaction. The system uses LLMs to generate contextual questions based on job descriptions and resumes, evaluates candidate responses, and produces detailed performance reports.

---

## Status Update — 2026-05-20 (hardening pass)

This pass made all three components runnable and delivered several roadmap items:

- **Cleanup:** removed duplicate `* 2.*` files, stray `.DS_Store`/`.pyc`, and a broken, disconnected root `agent.py`.
- **CLI runnable:** added `python-dotenv` to `requirements.txt`, dropped unused `pyttsx3`, added `.env.example`.
- **Cross-platform voice:** `voice.py` now selects macOS `say` / Linux `espeak-ng` / Windows PowerShell, with a silent no-op fallback (was macOS-only).
- **Resilience:** `context_parser.py` falls back to defaults instead of crashing when the LLM is unavailable; the backend agent's LLM calls retry with backoff and degrade per-node; env loading falls back `.env.local` → `.env`.
- **Storage query layer (roadmap #5):** `backend/storage.py` gained `get_session`, `list_sessions`, `get_events`, `get_skill_scores`, `export_session`, and `delete_session` (GDPR), plus a single-statement skill-score upsert.
- **Code-complexity evaluation (roadmap #9):** new `code_analysis.py` (AST cyclomatic complexity, loop nesting, recursion, time/space heuristics) wired into the PDF report.
- **Frontend:** portable `start-dev.sh`, `frontend/.env.example`, and a "Download transcript" action.
- **Tests:** added a `pytest` suite (`tests/`, 39 passing) + `requirements-dev.txt`.
- **Docs:** consolidated the two mashed-together READMEs into one accurate `README.md`.

Still open from the roadmap below: full multi-round specialist agents, web session start/end APIs, recordings/playback, admin dashboard, auth, and vector similarity search.

---

## Full Scope

### Core Capabilities (Target State)

1. **Multi-Round Interview Engine**
   - Resume grilling (HR-style questions)
   - DSA problem-solving (live coding with voice/text)
   - System design interviews (architecture discussion)
   - Behavioral interviews (competency assessment)

2. **Real-Time Interaction**
   - Voice I/O via LiveKit (audio streaming)
   - Video conferencing (WebRTC)
   - Live code editor with syntax highlighting
   - Live transcript with speaker identification

3. **Intelligent Evaluation**
   - LLM-powered question generation (contextual to JD/resume)
   - Real-time response evaluation and scoring
   - Competency mapping and weak area tracking
   - Code execution and validation

4. **Reporting & Analytics**
   - PDF interview reports with scores and feedback
   - Session history and playback
   - Competency scores by round
   - Candidate pipeline analytics

5. **Multi-Deployment Support**
   - Local CLI mode (single-threaded, terminal-based)
   - Cloud backend (Fly.io/Vercel)
   - Containerized (Docker Compose)
   - Multiple LLM providers (Groq, Ollama, OpenRouter)

---

## Architecture

### Backend Structure

```
Local Engine (Python)      Multi-Agent Branch (Python + LangGraph + LiveKit)
├── main.py               ├── backend/agent.py (LangGraph orchestrator)
├── interviewer.py        ├── backend/storage.py (persistence + queries)
├── context_parser.py     └── backend/openrouter_client.py (LLM routing)
├── llm.py
├── prompts.py            Database & Persistence
├── report_generator.py   └── backend/storage.py (PostgreSQL + pgvector)
└── voice.py

Shared Services
├── config.py (LLM & voice settings)
├── watcher.py (file monitoring)
└── ui.py (terminal rendering)
```

### Frontend Structure (Next.js)

```
frontend/
├── app/
│   ├── page.tsx (home/landing)
│   ├── layout.tsx (root layout)
│   └── api/
│       ├── execute/ (code execution)
│       ├── livekit-token/ (WebRTC token generation)
│       └── parse-resume/ (resume parsing)
├── components/
│   ├── RoomWorkspace.tsx (main interview UI)
│   ├── TranscriptPanel.tsx (live transcript)
│   └── InterviewSidebar.tsx (sidebar navigation)
└── lib/
    └── types.ts (TypeScript interfaces)
```

### Data Flow

```
User Input (JD + Resume + Answers)
    ↓
[main.py] Orchestrator
    ├→ [context_parser.py] Extract competencies & interview plan
    │   └→ [llm.py] LLMClient for structured extraction
    ├→ [interviewer.py] Run interview loop
    │   ├→ [prompts.py] Generate contextual questions
    │   ├→ [llm.py] Stream responses & chat
    │   └→ [voice.py] Audio capture/playback
    ├→ [agent.py] LangGraph multi-agent routing (NEW)
    │   ├→ Planner Node (interview plan)
    │   ├→ Moderator Node (routing)
    │   ├→ Specialist Agents (DSA, Systems, Behavioral)
    │   └→ Evaluator & Tracker Nodes
    └→ [report_generator.py] Generate final PDF report
        └→ [storage.py] Persist session to PostgreSQL
```

---

## What Has Been Done ✅

### 1. **Local CLI Interview Engine** (COMPLETE)
- ✅ Entry point with CLI argument parsing (`main.py`)
- ✅ Single-turn interview flow (`interviewer.py`)
- ✅ Resume & JD parsing (`context_parser.py`)
- ✅ Template-based prompt management (`prompts.py`)
- ✅ LLM abstraction layer (`llm.py`) supporting Groq and Ollama
- ✅ Voice pipeline (Silero VAD, Google TTS, faster-whisper STT) (`voice.py`)
- ✅ Terminal UI with rich formatting (`ui.py`)
- ✅ File watcher for code changes (`watcher.py`)

### 2. **LLM Integration** (MOSTLY COMPLETE)
- ✅ Groq integration with streaming
- ✅ Ollama (local) fallback support
- ✅ OpenRouter client for multi-model routing (`backend/openrouter_client.py`)
- ✅ Config management (`config.py`)

### 3. **Reporting** (PARTIAL)
- ✅ PDF generation framework (`report_generator.py`)
- ✅ Transcript & score aggregation
- ⚠️ Report API endpoint incomplete

### 4. **Database & Persistence** (PARTIAL)
- ✅ PostgreSQL schema with pgvector support (`backend/storage.py`)
- ✅ Session table (id, round_type, resume, weak_areas, timestamps)
- ✅ Session events table (transcript, scores, evaluations)
- ✅ Schema initialization
- ⚠️ Query layer partially implemented
- ⚠️ Vector embeddings not fully utilized

### 5. **Frontend Foundation** (PARTIAL)
- ✅ Next.js 14 project structure
- ✅ Tailwind CSS setup
- ✅ TypeScript configuration
- ✅ LiveKit components & client library
- ✅ Monaco editor for code display
- ⚠️ Main interview UI (`RoomWorkspace.tsx`) skeletal
- ⚠️ API routes mostly empty stubs
- ⚠️ Resume parsing endpoint not implemented

### 6. **LangGraph Multi-Agent Framework** (EARLY STAGE)
- ✅ State machine definition (`InterviewState` TypeDict)
- ✅ Runtime context manager (`RuntimeContext`)
- ✅ Basic node signatures (Planner, Moderator, Specialists, Evaluator, Tracker)
- ✅ LangGraph StateGraph initialization
- ⚠️ Node implementations incomplete
- ⚠️ Routing logic not tested
- ⚠️ Integration with OpenRouter client partial

### 7. **Deployment Infrastructure** (PARTIAL)
- ✅ Docker setup (`backend/Dockerfile`)
- ✅ Docker Compose configurations
- ✅ Fly.io configuration (`backend/fly.toml`)
- ✅ Vercel configuration (`vercel.json`)
- ⚠️ Environment variables not fully documented
- ⚠️ Database migrations not automated

---

## What Is Pending 🚧

### High Priority (MVP Blockers)

1. **Multi-Agent Completion** (`backend/agent.py`)
   - [ ] Implement Planner node (create interview plan from JD/resume)
   - [ ] Implement Moderator node (route between specialist agents)
   - [ ] Implement DSA Agent (generate coding problems, evaluate solutions)
   - [ ] Implement System Design Agent (generate architecture questions)
   - [ ] Implement Behavioral Agent (competency-based questions)
   - [ ] Implement Evaluator node (score responses)
   - [ ] Implement Tracker node (weak area identification, routing decisions)
   - [ ] Add retry logic and error handling

2. **Frontend Interview Room** (`frontend/components/RoomWorkspace.tsx`)
   - [ ] LiveKit room connection & state management
   - [ ] Real-time transcript rendering
   - [ ] Code editor integration (Monaco)
   - [ ] Audio/video stream display
   - [ ] Candidate response capture (text/voice)
   - [ ] UI for switching rounds/topics
   - [ ] Microphone/camera controls

3. **API Endpoint Completion** (`frontend/app/api/`)
   - [ ] `/api/execute/` - Code execution sandbox
   - [ ] `/api/livekit-token/` - Token generation logic
   - [ ] `/api/parse-resume/` - PDF/text resume parsing
   - [ ] `/api/interview/start` - Create session & start interview
   - [ ] `/api/interview/{sessionId}/end` - Finalize session & generate report

4. **Report Generation API**
   - [ ] Endpoint to generate final PDF report
   - [ ] Fetch session data from PostgreSQL
   - [ ] Compile scores, transcript, competency map
   - [ ] Return downloadable PDF

### Medium Priority (Post-MVP)

5. **Database Query Layer** (`backend/storage.py`)
   - [ ] Query session by ID
   - [ ] List sessions by candidate/date
   - [ ] Update session state
   - [ ] Vector similarity search for competencies
   - [ ] Analytics aggregation queries

6. **Interview Playback & History**
   - [ ] Store video/audio recordings
   - [ ] Playback UI with transcript sync
   - [ ] Session export (JSON, PDF)

7. **Admin Dashboard**
   - [ ] Candidate pipeline view
   - [ ] Bulk scheduling
   - [ ] Score analytics & trends
   - [ ] Interview templates management

8. **Voice Optimization**
   - [ ] Wake-word detection
   - [ ] Echo cancellation improvements
   - [ ] Real-time subtitle sync
   - [ ] Multi-language support

### Low Priority (Enhancement)

9. **Advanced Evaluation**
   - [ ] Code complexity analysis
   - [ ] Time/space complexity scoring
   - [ ] Communication quality metrics
   - [ ] Behavioral skill rubrics

10. **Security & Compliance**
    - [ ] User authentication (SSO)
    - [ ] Session encryption
    - [ ] GDPR-compliant data deletion
    - [ ] Audit logging

11. **Performance**
    - [ ] Caching (Redis)
    - [ ] Database indexing optimization
    - [ ] Frontend bundle size reduction
    - [ ] WebRTC optimizations

---

## Key Files Reference

| File | Status | Purpose |
|------|--------|---------|
| `main.py` | ✅ Complete | CLI entry point & session orchestrator |
| `interviewer.py` | ✅ Complete | Interview flow control (local mode) |
| `backend/agent.py` | 🚧 50% | LangGraph multi-agent orchestrator |
| `frontend/app/page.tsx` | 🚧 20% | Landing/setup page |
| `frontend/components/RoomWorkspace.tsx` | 🚧 10% | Main interview UI (critical blocker) |
| `backend/storage.py` | 🚧 40% | Database layer |
| `requirements.txt` | ✅ Complete | Python dependencies (local) |
| `backend/requirements.txt` | ✅ Complete | Backend dependencies (agents) |
| `frontend/package.json` | ✅ Complete | Frontend dependencies |
| `docker-compose.yml` | ✅ Complete | Local dev environment |
| `.env.local` | ⚠️ Missing | Environment variables (see config.py for required vars) |

---

## Environment Requirements

### Required Environment Variables
- `GROQ_API_KEY` - Groq API key for LLM
- `DATABASE_URL` - PostgreSQL connection string
- `LIVEKIT_URL` - LiveKit server URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_API_SECRET` - LiveKit secret

### Optional
- `OLLAMA_URL` - Ollama server URL (defaults to localhost:11434)
- `LOG_LEVEL` - Logging level (defaults to INFO)
- `OPENROUTER_API_KEY` - OpenRouter for model fallback

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| **Backend (Local)** | Python 3.11+, Groq/Ollama LLM |
| **Backend (Cloud)** | Python + LangGraph + LiveKit agents |
| **Database** | PostgreSQL + pgvector |
| **Frontend** | Next.js 14 + React 18 + TypeScript + Tailwind |
| **Real-Time** | LiveKit (WebRTC, audio/video) |
| **Code Editor** | Monaco Editor |
| **Voice** | Silero VAD + Google TTS + faster-whisper STT |
| **Deployment** | Docker Compose + Fly.io + Vercel |

---

## Next Steps (Recommended Order)

1. **Start with LangGraph nodes** - Complete `backend/agent.py` implementations (highest impact)
2. **Build interview room UI** - Complete `RoomWorkspace.tsx` and LiveKit integration
3. **Complete API layer** - Implement all `/api/` endpoints
4. **End-to-end test** - Run full interview flow from frontend to backend
5. **Database queries** - Add remaining query methods to `storage.py`
6. **Reporting** - Complete PDF generation and API
7. **Polish & deploy** - Error handling, UI refinement, production deployment

---

## Notes

- **Local vs. Cloud**: The local `interviewer.py` is fully functional for single-threaded testing. The `backend/agent.py` is the cloud-ready version using LangGraph.
- **LLM Flexibility**: All LLM calls route through `llm.py` to easily swap providers.
- **Prompt Engineering**: All templates live in `prompts.py` for easy iteration.
- **Session Persistence**: Both modes should write to `storage.py` for analytics.
