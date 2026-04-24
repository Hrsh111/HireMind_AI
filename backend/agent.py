#!/usr/bin/env python3
"""LiveKit backend agent with LangGraph Questioner/Evaluator/Tracker nodes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from livekit import rtc
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
import livekit.plugins.google as google
from livekit.plugins import silero

from openrouter_client import OpenRouterClient
from storage import SessionStore

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

logger = logging.getLogger("algo-agent")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

RoundType = Literal["resume_grill", "dsa", "systems", "behavioral"]
NextAction = Literal["follow_up", "switch_topic", "end"]


class InterviewState(TypedDict):
    session_id: str
    round_type: RoundType
    resume_text: str
    resume_file_name: str
    code: str
    transcript: list[dict[str, str]]
    latest_user_answer: str
    weak_areas: list[str]
    scores: list[dict[str, Any]]
    next_action: NextAction
    tracker_reason: str
    questioner_text: str


@dataclass
class RuntimeContext:
    session_id: str = "session-local"
    round_type: RoundType = "resume_grill"
    resume_text: str = ""
    resume_file_name: str = ""
    code: str = ""
    transcript: list[dict[str, str]] = field(default_factory=list)
    weak_areas: list[str] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)

    def snapshot(self, latest_user_answer: str) -> InterviewState:
        return {
            "session_id": self.session_id,
            "round_type": self.round_type,
            "resume_text": self.resume_text,
            "resume_file_name": self.resume_file_name,
            "code": self.code,
            "transcript": self.transcript[-14:],
            "latest_user_answer": latest_user_answer,
            "weak_areas": self.weak_areas,
            "scores": self.scores,
            "next_action": "follow_up",
            "tracker_reason": "",
            "questioner_text": "",
        }

    def absorb(self, state: InterviewState) -> None:
        self.weak_areas = list(dict.fromkeys(state.get("weak_areas", [])))[:8]
        self.scores = state.get("scores", [])[-40:]


class QuestionerVoice(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Algo's Questioner voice. Only read supplied questioner text. "
                "Keep delivery concise, professional, and interview-like."
            )
        )


def compact_resume(resume: str, limit: int = 3500) -> str:
    cleaned = re.sub(r"\s+", " ", resume or "").strip()
    return cleaned[:limit] or "No resume provided."


def compact_transcript(turns: list[dict[str, str]]) -> str:
    return "\n".join(f"{t.get('role', 'unknown')}: {t.get('text', '')}" for t in turns[-10:]) or "No transcript yet."


def round_focus(round_type: str) -> str:
    return {
        "resume_grill": "resume projects, claimed impact, trade-offs, and depth behind listed experience",
        "dsa": "data structures, algorithms, complexity, edge cases, and implementation clarity",
        "systems": "requirements, APIs, data models, scaling bottlenecks, reliability, and trade-offs",
        "behavioral": "ownership, conflict, communication, ambiguity, leadership, and reflection",
    }.get(round_type, "general engineering interview performance")


def build_graph(llm: OpenRouterClient):
    graph = StateGraph(InterviewState)

    async def evaluator(state: InterviewState) -> InterviewState:
        answer = state["latest_user_answer"].strip()
        if not answer:
            return {**state, "scores": state["scores"], "weak_areas": state["weak_areas"]}

        fallback = {
            "scores": [
                {
                    "skill": "communication",
                    "score": 3,
                    "evidence": "Fallback score because evaluator JSON was unavailable.",
                }
            ],
            "weak_areas": state["weak_areas"],
        }
        system = "You are the Evaluator node. Return strict JSON only."
        user = f"""
Round: {state['round_type']}
Focus: {round_focus(state['round_type'])}
Resume: {compact_resume(state['resume_text'])}
Known weak areas: {', '.join(state['weak_areas']) or 'none'}
Recent transcript:
{compact_transcript(state['transcript'])}

Latest answer:
{answer}

Return JSON:
{{
  "scores": [
    {{"skill": "specific skill", "score": 1-5, "evidence": "one sentence"}}
  ],
  "weak_areas": ["area 1", "area 2"]
}}
"""
        result = await llm.json_chat(system, user, fallback=fallback)
        scores = list(state["scores"]) + list(result.get("scores", []))
        weak_areas = list(dict.fromkeys(list(state["weak_areas"]) + list(result.get("weak_areas", []))))[:8]
        return {**state, "scores": scores[-40:], "weak_areas": weak_areas}

    async def tracker(state: InterviewState) -> InterviewState:
        fallback = {
            "next_action": "follow_up",
            "reason": "Continue probing the current topic.",
        }
        system = "You are the Tracker node. Return strict JSON only."
        user = f"""
Round: {state['round_type']}
Focus: {round_focus(state['round_type'])}
Weak areas: {', '.join(state['weak_areas']) or 'none'}
Recent scores: {json.dumps(state['scores'][-6:])}
Recent transcript:
{compact_transcript(state['transcript'])}

Decide the next action. Use exactly one of: follow_up, switch_topic, end.
Return JSON:
{{"next_action": "follow_up|switch_topic|end", "reason": "short reason"}}
"""
        result = await llm.json_chat(system, user, fallback=fallback)
        next_action = str(result.get("next_action", "follow_up"))
        if next_action not in {"follow_up", "switch_topic", "end"}:
            next_action = "follow_up"
        return {
            **state,
            "next_action": next_action,  # type: ignore[typeddict-item]
            "tracker_reason": str(result.get("reason", "")),
        }

    async def questioner(state: InterviewState) -> InterviewState:
        system = "You are the Questioner node. You are the only node allowed to speak to the user."
        user = f"""
Generate the next spoken interviewer turn.

Round: {state['round_type']}
Focus: {round_focus(state['round_type'])}
Tracker action: {state['next_action']}
Tracker reason: {state['tracker_reason']}
Weak areas to target: {', '.join(state['weak_areas']) or 'none'}
Resume: {compact_resume(state['resume_text'])}
Current code, if relevant:
{state['code'][-3500:] if state['code'] else '(no code yet)'}
Recent transcript:
{compact_transcript(state['transcript'])}

Rules:
- Ask exactly one primary question or follow-up.
- If action is end, give a concise closing summary with 2 next steps.
- For DSA, ask for approach and complexity before code when appropriate.
- For systems, ask for requirements or trade-offs before deep design.
- For resume grill, challenge a concrete project or metric from the resume.
- Keep it under 70 words.
"""
        text = await llm.chat(system, user, temperature=0.45, max_tokens=220)
        return {**state, "questioner_text": text}

    graph.add_node("Evaluator", evaluator)
    graph.add_node("Tracker", tracker)
    graph.add_node("Questioner", questioner)
    graph.set_entry_point("Evaluator")
    graph.add_edge("Evaluator", "Tracker")
    graph.add_edge("Tracker", "Questioner")
    graph.add_edge("Questioner", END)
    return graph.compile()


def parse_packet(payload: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(payload.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def publish_agent_message(room: rtc.Room, text: str, *, metadata: dict[str, Any] | None = None) -> None:
    payload = {
        "type": "agent_message",
        "agent_name": "Questioner",
        "avatar": "Q",
        "role": "agent",
        "text": text,
        "metadata": metadata or {},
    }
    try:
        await room.local_participant.publish_data(
            json.dumps(payload),
            reliable=True,
            topic="agent-transcript",
        )
    except Exception as exc:
        logger.warning("Could not publish agent_message: %s", exc)


async def run_session(ctx: JobContext) -> None:
    logger.info("[Agent] run_session started for JobContext: %s", ctx)
    runtime = RuntimeContext()
    llm = OpenRouterClient()
    store = SessionStore()
    graph = build_graph(llm)
    turn_lock = asyncio.Lock()

    await store.ensure_schema()

    tts_kwargs: dict[str, Any] = {
        "language": os.getenv("GOOGLE_TTS_LANGUAGE", "en-US"),
        "speaking_rate": float(os.getenv("GOOGLE_TTS_RATE", "1.03")),
    }
    if os.getenv("GOOGLE_TTS_VOICE"):
        tts_kwargs["voice_name"] = os.getenv("GOOGLE_TTS_VOICE")

    session = AgentSession(
        stt=google.STT(model=os.getenv("GOOGLE_STT_MODEL", "latest_long")),
        vad=silero.VAD.load(),
        tts=google.TTS(**tts_kwargs),
    )

    async def run_turn(user_text: str) -> None:
        answer = re.sub(r"\s+", " ", user_text).strip()
        if not answer:
            logger.debug("[Agent] run_turn: empty user_text received, skipping.")
            return

        logger.info("[Agent] run_turn: received user_text: %s", answer)
        async with turn_lock:
            runtime.transcript.append({"role": "user", "text": answer})
            await store.upsert_session(
                session_id=runtime.session_id,
                round_type=runtime.round_type,
                resume_text=runtime.resume_text,
                resume_file_name=runtime.resume_file_name,
                weak_areas=runtime.weak_areas,
            )
            await store.add_event(runtime.session_id, "user", answer, {"round_type": runtime.round_type})

            state = await graph.ainvoke(runtime.snapshot(answer))
            runtime.absorb(state)

            questioner_text = state.get("questioner_text", "").strip()
            if not questioner_text:
                questioner_text = "Let's keep going. Can you expand on your reasoning?"

            logger.info("[Agent] run_turn: questioner_text generated: %s", questioner_text)
            runtime.transcript.append({"role": "questioner", "text": questioner_text})
            await store.upsert_session(
                session_id=runtime.session_id,
                round_type=runtime.round_type,
                resume_text=runtime.resume_text,
                resume_file_name=runtime.resume_file_name,
                weak_areas=runtime.weak_areas,
            )
            await store.add_event(
                runtime.session_id,
                "questioner",
                questioner_text,
                {"next_action": state.get("next_action"), "weak_areas": runtime.weak_areas},
            )
            await store.upsert_skill_scores(runtime.session_id, runtime.scores[-8:])

            await publish_agent_message(
                ctx.room,
                questioner_text,
                metadata={
                    "next_action": state.get("next_action"),
                    "tracker_reason": state.get("tracker_reason"),
                    "weak_areas": runtime.weak_areas,
                },
            )
            await session.say(questioner_text, allow_interruptions=True)

    async def start_round() -> None:
        logger.info("[Agent] start_round: starting new round.")
        async with turn_lock:
            state = await graph.ainvoke(runtime.snapshot(""))
            runtime.absorb(state)
            questioner_text = state.get("questioner_text", "").strip()
            logger.info("[Agent] start_round: questioner_text generated: %s", questioner_text)
            runtime.transcript.append({"role": "questioner", "text": questioner_text})
            await store.upsert_session(
                session_id=runtime.session_id,
                round_type=runtime.round_type,
                resume_text=runtime.resume_text,
                resume_file_name=runtime.resume_file_name,
                weak_areas=runtime.weak_areas,
            )
            await store.add_event(runtime.session_id, "questioner", questioner_text, {"initial": True})
            await publish_agent_message(ctx.room, questioner_text, metadata={"initial": True})
            await session.say(questioner_text, allow_interruptions=True)

    @ctx.room.on("data_received")
    def on_data_received(packet: rtc.DataPacket) -> None:
        logger.info("[Agent] data_received: packet received: %s", packet)
        data = parse_packet(packet.data)
        if not data:
            logger.warning("[Agent] data_received: could not parse packet data.")
            return

        message_type = str(data.get("type", ""))
        logger.info("[Agent] data_received: message_type=%s, data=%s", message_type, data)
        if message_type == "interview_context":
            runtime.session_id = str(data.get("session_id") or runtime.session_id)
            round_type = str(data.get("round_type") or runtime.round_type)
            if round_type in {"resume_grill", "dsa", "systems", "behavioral"}:
                runtime.round_type = round_type  # type: ignore[assignment]
            runtime.resume_text = str(data.get("resume_text", ""))
            runtime.resume_file_name = str(data.get("resume_file_name", ""))
            logger.info("[Agent] data_received: interview_context received, starting round.")
            asyncio.create_task(start_round())
            return

        if message_type == "code_update":
            runtime.code = str(data.get("code", ""))
            logger.info("[Agent] data_received: code_update received.")
            return

        if message_type == "user_utterance":
            logger.info("[Agent] data_received: user_utterance received.")
            asyncio.create_task(run_turn(str(data.get("text", ""))))

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        source = getattr(publication, "source", "")
        logger.info("[Agent] track_subscribed: Subscribed to %s from %s", source, participant.identity)

    @ctx.room.on("transcription_received")
    def on_transcription_received(
        segments: list[rtc.TranscriptionSegment],
        participant: rtc.Participant,
        publication: rtc.TrackPublication,
    ) -> None:
        logger.info("[Agent] transcription_received: segments=%s, participant=%s", segments, participant)
        for segment in segments:
            text = (getattr(segment, "text", "") or "").strip()
            is_final = bool(getattr(segment, "final", True))
            logger.info("[Agent] transcription_received: text='%s', is_final=%s", text, is_final)
            if text and is_final:
                asyncio.create_task(run_turn(text))

    await session.start(room=ctx.room, agent=QuestionerVoice())


server = AgentServer()


@server.rtc_session(agent_name="algo-multi-agent")
async def entrypoint(ctx: JobContext) -> None:
    await run_session(ctx)


if __name__ == "__main__":
    cli.run_app(server)
