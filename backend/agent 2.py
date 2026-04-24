#!/usr/bin/env python3
"""LiveKit multi-agent interviewer with LangGraph supervisor routing."""

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
from livekit import rtc
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.plugins import silero
import livekit.plugins.google as google
from langgraph.graph import END, StateGraph

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

logger = logging.getLogger("algo-multi-agent")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class RouterState(TypedDict):
    user_text: str
    transcript_tail: str
    next_agent: Literal["dsa", "system_design", "behavioral"]
    reason: str


@dataclass
class InterviewContext:
    """Shared session state consumed by supervisor + specialist agents."""

    job_description: str = ""
    resume: str = ""
    code: str = ""
    transcript: list[dict[str, str]] = field(default_factory=list)
    active_agent: str = "dsa"

    def transcript_tail(self, turns: int = 8) -> str:
        items = self.transcript[-turns:]
        return "\n".join(f"{x.get('role', 'unknown')}: {x.get('text', '')}" for x in items)


AGENT_CONFIG: dict[str, dict[str, str]] = {
    "dsa": {
        "label": "DSA Interviewer",
        "avatar": "🧠",
        "prompt": (
            "You are the DSA interviewer. Focus on algorithms, data structures, complexity, and edge cases. "
            "Ask compact, high-signal questions and guide without giving full solutions."
        ),
    },
    "system_design": {
        "label": "System Design Interviewer",
        "avatar": "🏗️",
        "prompt": (
            "You are the system design interviewer. Focus on requirements, APIs, scalability, reliability, "
            "tradeoffs, and bottlenecks. Keep answers concise and conversational."
        ),
    },
    "behavioral": {
        "label": "Behavioral Interviewer",
        "avatar": "💬",
        "prompt": (
            "You are the behavioral interviewer. Probe communication, ownership, conflict handling, and impact. "
            "Use STAR-style follow-up prompts and keep the tone professional."
        ),
    },
}


def _detect_agent(text: str) -> tuple[str, str]:
    """Keyword router for a lightweight free-tier supervisor policy."""
    lowered = text.lower()

    behavioral_hits = [
        "behavioral",
        "tell me about",
        "conflict",
        "leadership",
        "team",
        "stakeholder",
        "deadline",
        "failure",
        "ownership",
    ]
    sd_hits = [
        "system design",
        "scalable",
        "latency",
        "throughput",
        "cache",
        "load balancer",
        "database",
        "microservice",
        "architecture",
    ]

    if any(k in lowered for k in behavioral_hits):
        return "behavioral", "behavioral keywords detected"
    if any(k in lowered for k in sd_hits):
        return "system_design", "system design keywords detected"
    return "dsa", "defaulting to DSA for coding-focused turns"


def build_router_graph():
    graph = StateGraph(RouterState)

    def route_node(state: RouterState) -> RouterState:
        next_agent, reason = _detect_agent(state["user_text"])
        return {
            **state,
            "next_agent": next_agent,  # type: ignore[assignment]
            "reason": reason,
        }

    graph.add_node("route", route_node)
    graph.set_entry_point("route")
    graph.add_edge("route", END)
    return graph.compile()


ROUTER_GRAPH = build_router_graph()


class MultiAgentSupervisor(Agent):
    """Base LiveKit voice agent. Turn-level specialization is injected dynamically."""

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the supervisor for a multi-agent interview panel. "
                "You will receive turn-level specialist instructions before every response. "
                "Speak naturally, keep replies short, and do not output markdown."
            )
        )


def _safe_json_load(payload: bytes) -> dict[str, Any] | None:
    try:
        text = payload.decode("utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _extract_user_text(data: dict[str, Any]) -> str:
    for key in ("text", "utterance", "transcript", "message"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_screen_share_source(publication: rtc.RemoteTrackPublication) -> bool:
    source = getattr(publication, "source", None)
    if source is None:
        return False
    source_name = getattr(source, "name", str(source)).upper()
    return "SCREEN_SHARE" in source_name


async def _publish_supervisor_event(
    room: rtc.Room,
    *,
    event_type: str,
    agent_key: str,
    text: str,
    reason: str,
):
    details = AGENT_CONFIG.get(agent_key, AGENT_CONFIG["dsa"])
    payload = {
        "type": event_type,
        "agent": agent_key,
        "agent_name": details["label"],
        "avatar": details["avatar"],
        "text": text,
        "reason": reason,
    }
    encoded = json.dumps(payload)

    try:
        await room.local_participant.publish_data(
            encoded,
            reliable=True,
            topic="agent-transcript",
        )
    except Exception as exc:
        logger.warning("Failed to publish supervisor event: %s", exc)


async def run_session(ctx: JobContext):
    """LiveKit room entrypoint with supervisor + LangGraph routing."""
    interview_ctx = InterviewContext()
    turn_lock = asyncio.Lock()

    session = AgentSession(
        vad=silero.VAD.load(),  # turn detection via VAD
        llm=google.beta.realtime.RealtimeModel(
            model=os.getenv("LIVEKIT_REALTIME_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"),
            voice=os.getenv("LIVEKIT_VOICE", "puck"),
            enable_affective_dialog=True,
            proactivity=True,
        ),
    )

    async def handle_user_turn(user_text: str):
        cleaned = re.sub(r"\s+", " ", user_text).strip()
        if not cleaned:
            return

        interview_ctx.transcript.append({"role": "user", "text": cleaned})

        route_state: RouterState = ROUTER_GRAPH.invoke(
            {
                "user_text": cleaned,
                "transcript_tail": interview_ctx.transcript_tail(),
                "next_agent": "dsa",
                "reason": "",
            }
        )
        next_agent = route_state["next_agent"]
        reason = route_state["reason"]
        interview_ctx.active_agent = next_agent

        agent_cfg = AGENT_CONFIG[next_agent]
        specialist_prompt = f"""\
Current specialist: {agent_cfg['label']} {agent_cfg['avatar']}
Routing reason: {reason}

Candidate resume context:
{interview_ctx.resume or '(not provided)'}

Job description context:
{interview_ctx.job_description or '(not provided)'}

Latest editor content:
{interview_ctx.code[-5000:] if interview_ctx.code else '(no code yet)'}

Specialist instructions:
{agent_cfg['prompt']}

User's latest utterance:
{cleaned}

Respond as {agent_cfg['label']} in 1-3 concise spoken sentences, then hand control back to supervisor.
"""

        await _publish_supervisor_event(
            ctx.room,
            event_type="agent_handoff",
            agent_key=next_agent,
            text=f"{agent_cfg['label']} is responding.",
            reason=reason,
        )

        async with turn_lock:
            await session.generate_reply(instructions=specialist_prompt)

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        try:
            if _is_screen_share_source(publication):
                logger.info("Subscribed to screen share track from %s", participant.identity)
        except Exception as exc:
            logger.warning("track_subscribed handler failed: %s", exc)

    @ctx.room.on("data_received")
    def on_data_received(packet: rtc.DataPacket):
        payload = _safe_json_load(packet.data)
        if not payload:
            return

        message_type = str(payload.get("type", "")).lower()
        if message_type == "interview_context":
            interview_ctx.job_description = str(payload.get("jd_text", ""))
            interview_ctx.resume = str(payload.get("resume_text", ""))
            logger.info("Received interview context from frontend")
            return

        if message_type == "code_update":
            interview_ctx.code = str(payload.get("code", ""))
            return

        if message_type in {"user_utterance", "frontend_transcript"}:
            text = _extract_user_text(payload)
            if text:
                asyncio.create_task(handle_user_turn(text))

    @ctx.room.on("transcription_received")
    def on_transcription_received(
        segments: list[rtc.TranscriptionSegment],
        participant: rtc.Participant,
        publication: rtc.TrackPublication,
    ):
        for seg in segments:
            text = (getattr(seg, "text", "") or "").strip()
            is_final = bool(getattr(seg, "final", True))
            if text and is_final:
                asyncio.create_task(handle_user_turn(text))

    await session.start(
        room=ctx.room,
        agent=MultiAgentSupervisor(),
    )

    await session.generate_reply(
        instructions=(
            "Introduce yourself as Algo's supervisor. Say that DSA, system design, and behavioral specialists "
            "will dynamically take turns based on the user's speech. Ask what they want to start with."
        )
    )


server = AgentServer()


@server.rtc_session(agent_name="algo-multi-agent")
async def entrypoint(ctx: JobContext):
    await run_session(ctx)


if __name__ == "__main__":
    cli.run_app(server)
