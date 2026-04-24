# Interview Bot Architecture Map

>This file contains two clean Mermaid diagrams: one for the overall project architecture and one for the LangGraph state machine. Every transition is labelled with the file name that owns or influences that step.

**Legend:**
- Local engine: `main.py` → `interviewer.py`
- Shared core: `context_parser.py`, `llm.py`, `prompts.py`, `report_generator.py`, `storage.py`
- Panel branch: `agent.py`, `agent 2.py`, `openrouter_client.py`

---

## System architecture

```mermaid
flowchart LR
  U[User: JD + Resume + Answers] -->|main.py| M[main.py]
  M -->|builds Interviewer| I[interviewer.py]

  subgraph Shared[Shared services]
    CP[context_parser.py]
    L[llm.py]
    P[prompts.py]
    R[report_generator.py]
    C[config.py]
    ST[storage.py]
    V[voice.py]
    W[watcher.py]
    UI[ui.py]
  end

  I -->|parse_interview_context| CP
  CP -->|LLMClient| L
  CP -->|question templates| P
  I -->|system prompt templates| P
  I -->|chat + streaming| L
  I -->|final report| R
  R -->|LLMClient for scoring| L
  I -->|speak / listen| V
  I -->|file change events| W
  I -->|terminal rendering| UI
  L -->|model + backend settings| C
  V -->|audio settings| C
  W -->|watch rules| C
  M -->|backend selection| C
  M -->|session persistence| ST

  subgraph Panel[Live multi-agent branch]
    AG[agent.py]
    AG2[agent 2.py]
    OR[openrouter_client.py]
  end

  AG -->|build_graph + routing| OR
  AG -->|session memory| ST
  AG2 -->|alternate flow| OR
  AG2 -->|session persistence| ST
  OR -->|LLM requests| L
  OR -->|model selection| C

  I -.->|migration target| AG
  I -.->|shared prompt patterns| P
  R -.->|structured output| ST
  CP -.->|competency extraction| ST
```

### Key Flows
- **Session bootstrap:** `main.py` reads CLI flags, loads the JD and resume, chooses the backend, and constructs the interviewer object. This is the session entry point.
- **Interview context:** The interviewer hands JD and resume text to `context_parser.py` so the system can infer competencies, tailor the question, and avoid generic prompts.
- **LLM-based parsing:** The parser relies on `LLMClient` for structured extraction. That keeps the parsing logic reusable and isolated from the flow controller.
- **Prompt management:** `prompts.py` owns the system prompt, greeting, question, hint, and observation templates. This lets you tune interview behavior without editing state-machine logic.
- **Conversation engine:** The interviewer delegates response generation and streaming to the model client. The flow decides when to speak; `llm.py` decides what to say.
- **Final evaluation:** At the end of the session, the transcript and final code are pushed into `report_generator.py` to create a structured, explainable PDF.
- **Panel branch:** The LangGraph / LiveKit branch routes node-level decisions through `openrouter_client.py`. That is the natural home for your moderator, specialist agents, and routing logic.
- **Session memory:** Both agent files should write session events, weak areas, and scores to `storage.py`. That gives the system memory across turns and supports analytics.

---

## LangGraph state machine

```mermaid
flowchart TD
  START[Start Session] -->|JD + Resume| PLANNER[Planner Node]
  PLANNER -->|competencies + interview plan| MODERATOR[Moderator Node]

  MODERATOR -->|route: dsa| DSA[DSA Agent]
  MODERATOR -->|route: system| SYSTEM[System Design Agent]
  MODERATOR -->|route: behavioral| BEHAVIORAL[Behavioral Agent]

  DSA -->|ask question| USER[User Response]
  SYSTEM -->|ask question| USER
  BEHAVIORAL -->|ask question| USER

  USER -->|response text| EVALUATOR[Evaluator Node]
  EVALUATOR -->|depth + score + gaps| TRACKER[Tracker Node]

  TRACKER -->|continue| MODERATOR
  TRACKER -->|switch topic| MODERATOR
  TRACKER -->|end| END[End Session]

  END -->|generate| REPORT[Final Report]
```

### State Machine Nodes
- **Planner Node:** Builds the session plan from resume + JD into competencies and a plan of attack.
- **Moderator Node:** Decides which interviewer should speak next and why, based on the current state and weak areas.
- **DSA / System / Behavioral Agents:** Each specialist asks one focused question and keeps the conversation on its own domain.
- **Evaluator Node:** Classifies the response depth, assigns a score, and captures evidence or gaps.
- **Tracker Node:** Decides whether to continue, switch topic, or end the interview, making the flow adaptive.
- **End Session → Final Report:** Once the tracker ends the session, the system generates the final report as a product artifact.
# Algo Collaborative Interview Agent

LiveKit interview platform with a Next.js frontend, a Python LangGraph backend agent, Piston code execution, and PostgreSQL + pgvector persistence.

## What It Does

- Upload a resume as PDF or text.
- Select a round: resume grill, DSA, systems, or behavioral.
- Join a LiveKit room with microphone and screen share.
- Edit and run Python code from Monaco via `/api/execute`.
- Send resume, round type, and code updates to the backend over LiveKit data channels.
- Run a backend LangGraph with three nodes:
  - `Questioner`: the only node that speaks to the candidate.
  - `Evaluator`: scores answers and updates weak areas.
  - `Tracker`: decides follow-up, topic switch, or end.
- Store sessions, transcript events, weak areas, and skill scores in PostgreSQL + pgvector.

## Local Setup

1. Create environment:

```bash
cp .env.example .env.local
```

2. Fill at least:

```bash
OPENROUTER_API_KEY=...
GOOGLE_API_KEY=...
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
DATABASE_URL=postgresql://algo:algo@localhost:5432/algo
```

3. Start LiveKit and Postgres:

```bash
docker compose up -d
```

4. Start the backend agent:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python agent.py dev
```

5. Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

6. Open `http://localhost:3000`.

## Frontend

Important files:

- `frontend/app/page.tsx`: main interview room UI.
- `frontend/components/InterviewSidebar.tsx`: resume upload, round selection, LiveKit controls.
- `frontend/components/RoomWorkspace.tsx`: LiveKit audio, screen share, data-channel publishing.
- `frontend/app/api/parse-resume/route.ts`: PDF/text resume parser.
- `frontend/app/api/execute/route.ts`: Piston execution with optional local fallback.
- `frontend/app/api/livekit-token/route.ts`: LiveKit token generation.

## Backend

Important files:

- `backend/agent.py`: LiveKit worker and LangGraph state machine.
- `backend/openrouter_client.py`: OpenRouter Gemini 1.5 Flash client.
- `backend/storage.py`: Postgres/pgvector persistence.
- `backend/db/init.sql`: schema for sessions, transcript events, and skill graph.

The backend uses OpenRouter for reasoning and LiveKit Google STT/TTS for voice input/output. Questioner text is generated by OpenRouter and then spoken with `AgentSession.say(...)`.

## Code Execution

`POST /api/execute` sends Piston-compatible payloads:

```json
{
  "language": "python",
  "version": "3.10.0",
  "files": [{ "name": "main.py", "content": "print('hello')" }]
}
```

Set `EXECUTE_FALLBACK=local` only for demos. Do not enable local subprocess execution in production.

## Deploy Frontend to Vercel

Recommended: deploy from `frontend/`.

```bash
cd frontend
vercel
vercel --prod
```

Set these Vercel environment variables:

```bash
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
NEXT_PUBLIC_LIVEKIT_URL=wss://your-livekit-host
NEXT_PUBLIC_DEFAULT_ROOM=algo-room
PISTON_TIMEOUT_MS=12000
```

## Deploy Backend to Fly.io

Create app:

```bash
fly apps create algo-multi-agent
```

Set secrets:

```bash
fly secrets set \
  LIVEKIT_URL=wss://your-livekit-host \
  LIVEKIT_API_KEY=... \
  LIVEKIT_API_SECRET=... \
  OPENROUTER_API_KEY=... \
  OPENROUTER_MODEL=google/gemini-flash-1.5 \
  GOOGLE_API_KEY=... \
  DATABASE_URL=postgresql://...
```

Deploy:

```bash
fly deploy -c backend/fly.toml
```

## Files Added

```text
backend/
  agent.py
  openrouter_client.py
  storage.py
  db/init.sql
  requirements.txt
  Dockerfile
  fly.toml
frontend/
  app/
    api/execute/route.ts
    api/livekit-token/route.ts
    api/parse-resume/route.ts
    globals.css
    layout.tsx
    page.tsx
  components/
    InterviewSidebar.tsx
    RoomWorkspace.tsx
    TranscriptPanel.tsx
  lib/types.ts
  vercel.json
docker-compose.yml
livekit.yaml
vercel.json
.env.example
```
