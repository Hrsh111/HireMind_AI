# Algo Multi-Agent Interview Platform (APOGEE 2026 Track D)

This project implements a **LiveKit-based multi-agent interview system** with:

- Next.js frontend (`frontend/`)
- Python LiveKit agent with LangGraph supervisor (`backend/`)
- Code execution API using Piston with local fallback (`/api/execute`)
- Local LiveKit runtime via Docker Compose
- Deployment guides for Vercel (frontend) + Fly.io (backend)

## 1. Architecture

### Frontend (`frontend/`)
- Uses `@livekit/components-react` + `livekit-client` for room connection.
- Uses `@monaco-editor/react` for code editor.
- Publishes:
  - JD/resume context over LiveKit data channel (`type=interview_context`)
  - editor code updates (`type=code_update`)
  - optional typed user turns (`type=user_utterance`)
- Receives multi-agent messages (`type=agent_handoff` / `agent_message`) and renders transcript with agent avatar/name.

### Backend (`backend/agent.py`)
- Connects to LiveKit as `algo-multi-agent` worker.
- Uses `silero` VAD for turn detection.
- Uses LangGraph `StateGraph` as supervisor router (`dsa`, `system_design`, `behavioral`).
- Uses screen-share subscription signal and frontend code updates (preferred) for coding context.

### Execution API (`frontend/app/api/execute/route.ts`)
- Primary: Piston (`https://emkc.org/api/v2/piston/execute`)
- Fallback: local subprocess execution (Python only, demo mode)

## 2. Local Setup

## Prerequisites
- Node.js 20+
- Python 3.11+
- Docker
- Google API key (for LiveKit Google realtime model plugin)

## Clone and env
1. Copy env file:
```bash
cp .env.example .env.local
```
2. Fill `.env.local` values, especially:
- `GOOGLE_API_KEY`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

## Start LiveKit locally
```bash
docker compose up -d
```

LiveKit will run at `ws://localhost:7880`.

## Start backend agent
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python agent.py dev
```

## Start frontend
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Connect flow
1. Enter `LiveKit URL` (default: `ws://localhost:7880`)
2. Enter room + identity
3. Click **Generate Token**
4. Click **Connect**
5. Optional: **Share Screen**
6. Use mic or typed input for interview turns

## 3. API Routes

### `POST /api/livekit-token`
Body:
```json
{
  "roomName": "algo-room",
  "identity": "candidate-123"
}
```

Response:
```json
{
  "token": "<jwt>",
  "identity": "candidate-123",
  "roomName": "algo-room"
}
```

### `POST /api/execute`
Body (Piston format):
```json
{
  "language": "python",
  "version": "3.10.0",
  "files": [{ "name": "main.py", "content": "print('hi')" }]
}
```

Behavior:
- tries Piston first
- if failed/slow, optionally runs local fallback when `EXECUTE_FALLBACK=local`

## 4. ngrok local backend testing (optional)

If you need to expose local services:

```bash
ngrok config add-authtoken $NGROK_AUTHTOKEN
ngrok http 7880
```

Then use the generated `wss://...` URL in frontend `LiveKit URL` and environment configs.

## 5. Deploy Frontend to Vercel

From `frontend/`:

```bash
npm i -g vercel
vercel
```

Set project env vars in Vercel:
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `NEXT_PUBLIC_LIVEKIT_URL` (your hosted LiveKit URL)
- `NEXT_PUBLIC_DEFAULT_ROOM`
- optional execution vars (`EXECUTE_FALLBACK`, etc.)

Deploy production:
```bash
vercel --prod
```

## 6. Deploy Backend Agent to Fly.io

### Prepare app
1. Install Fly CLI and login:
```bash
fly auth login
```
2. Create app (once):
```bash
fly apps create algo-multi-agent
```

### Set secrets
```bash
fly secrets set \
  LIVEKIT_URL=wss://<your-livekit-host> \
  LIVEKIT_API_KEY=<key> \
  LIVEKIT_API_SECRET=<secret> \
  GOOGLE_API_KEY=<google-key> \
  LIVEKIT_REALTIME_MODEL=gemini-2.5-flash-native-audio-preview-12-2025 \
  LIVEKIT_VOICE=puck
```

### Deploy
```bash
fly deploy -c backend/fly.toml
```

This worker is long-lived and suitable for Fly/Railway/Cloud Run (not Vercel).

## 7. Production Notes

- Prefer hosted LiveKit Cloud or a dedicated LiveKit server for stable WebRTC.
- Keep local subprocess code execution disabled in production (`EXECUTE_FALLBACK` unset).
- Piston is best-effort free service; add retry/backoff if needed.
- For robust routing, replace keyword supervisor with an LLM router node in LangGraph.

## 8. Project Structure

```text
backend/
  agent.py
  requirements.txt
  Dockerfile
  fly.toml
frontend/
  app/
    api/execute/route.ts
    api/livekit-token/route.ts
    globals.css
    layout.tsx
    page.tsx
  components/
    InterviewSidebar.tsx
    RoomWorkspace.tsx
    TranscriptPanel.tsx
  lib/types.ts
  package.json
  tsconfig.json
  next.config.mjs
  postcss.config.js
  tailwind.config.ts

.env.example
docker-compose.yml
livekit.yaml
README.md
```

## 9. Quick Smoke Test

1. `docker compose up -d`
2. backend: `python backend/agent.py dev`
3. frontend: `npm --prefix frontend run dev`
4. open `http://localhost:3000`
5. generate token, connect, send typed message:
   - `ask me a DSA question`
   - `switch to system design`
   - `behavioral question about conflict`

You should see transcript handoff labels from different agents.
