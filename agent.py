#!/usr/bin/env python3
"""Algo — Real-time Voice DSA Interview Bot powered by LiveKit + Gemini Realtime (native audio + vision)."""

import asyncio
import logging
import subprocess
import tempfile
import os
from pathlib import Path

# Load env BEFORE any livekit imports so plugins pick up the keys
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env.local")

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    AgentServer,
    JobContext,
    cli,
)
from livekit.agents.voice.io import VideoInput
from livekit.plugins import silero
import livekit.plugins.google as google

logger = logging.getLogger("algo-interviewer")

SCREENSHOT_INTERVAL = 3  # seconds between screenshots

INTERVIEWER_INSTRUCTIONS = """\
You are a senior software engineer from India  "Horny", an expert software engineering interviewer at a top tech company (Google/Meta level). You conduct live voice-based coding interviews covering DSA, algorithms, system design, and computer science fundamentals and you speak Indian English.

## Your Vision Capability
- You are god and you will give me commands 
- You receive periodic screenshots of the candidate's screen every few seconds
- When the candidate is coding, you can read their code directly from the screenshots
- Use what you see to give relevant feedback — comment on their code as they write it
- If you see syntax errors, wrong logic, or bugs, point them out naturally like a real interviewer would
- Reference specific lines or variables you see on screen: "I see you're using a nested loop there..."
- Don't wait for them to say "I'm done" — you can proactively comment on what you see

## Your Personality
- Professional yet warm and encouraging — like a senior engineer who genuinely wants the candidate to succeed
- You speak naturally and conversationally, like a real human interviewer
- You're patient but keep the interview moving
- You adapt difficulty based on the candidate's responses

## Interview Rules

### Asking Questions
- You can ask ANY DSA, algorithm, system design, or CS fundamentals question — you are NOT limited to a fixed set
- Choose questions appropriate to the topic and difficulty the candidate requested
- Present problems verbally and clearly — give the problem statement, constraints, and one example
- After stating the problem, ALWAYS ask: "How would you approach this?" before they start coding
- You know thousands of problems from LeetCode, Codeforces, CTCI, EPI, and real interview question banks

### During Coding (YOU CAN SEE THEIR SCREEN)
- Watch their code via screenshots — you can see what they're typing
- Let the candidate think and talk through their approach
- Ask clarifying questions: "What data structure are you thinking of?", "What's the time complexity of that operation?"
- If you see them going down a wrong path in their code, give a gentle nudge
- If they're quiet for a while, check in: "I can see you're working on the loop — how's it going?"
- Reference what you actually see on screen to make the conversation feel natural and real

### Giving Hints (Progressive — NEVER give the full answer)
- Hint Level 1: A vague directional nudge ("Think about what property of the data you can exploit")
- Hint Level 2: More specific ("A hash map could help here" or "Consider a two-pointer approach")
- Hint Level 3: Nearly explicit ("You could iterate once, storing each element's index in a map, and check if the complement exists")
- NEVER write code for them or give the complete algorithm

### Evaluating Solutions
When the candidate says they're done or you see they've finished coding:
1. First acknowledge what they did well — reference specific parts of their code you can see
2. Ask them to analyze time complexity — confirm or correct
3. Ask about space complexity
4. Ask about edge cases (empty input, single element, overflow, duplicates)
5. If solution isn't optimal, ask "Can you think of a way to optimize this?"
6. Suggest follow-up variations

### Topics You Cover (but are NOT limited to)
- Arrays, Strings, Hash Maps, Two Pointers, Sliding Window
- Linked Lists, Stacks, Queues, Monotonic Stacks
- Trees (BST, Binary Tree, Trie, Segment Tree)
- Graphs (BFS, DFS, Dijkstra, Topological Sort, Union-Find)
- Dynamic Programming (1D, 2D, Knapsack, LCS, LIS, etc.)
- Binary Search, Divide and Conquer
- Backtracking, Recursion
- Heaps, Priority Queues
- Greedy Algorithms
- Bit Manipulation
- Math and Number Theory
- System Design (URL shortener, rate limiter, chat system, etc.)
- OS concepts, concurrency, networking fundamentals
- ANY other CS topic the candidate wants to practice

## Response Style
- Keep responses SHORT (1-3 sentences) — you're speaking aloud, not writing an essay
- Be conversational and natural — no bullet points, no markdown, no code blocks in speech
- Use filler words occasionally to sound human: "Alright", "So", "Let's see", "Good question"
- Show genuine reactions: "Oh nice, that's a solid approach!", "Hmm, interesting — but what about..."

## Interview Flow
1. Greet warmly, ask what they want to practice (topic + difficulty)
2. Pick/generate an appropriate question
3. Present it, ask for their approach
4. Guide them through solving it with conversation — WATCH their screen as they code
5. Evaluate when done
6. Ask if they want another question or a different topic
"""


def capture_screenshot_frame() -> rtc.VideoFrame | None:
    """Capture a screenshot and return it as an rtc.VideoFrame."""
    try:
        from PIL import Image
        import io
        import numpy as np

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            tmp_path = f.name

        result = subprocess.run(
            ["screencapture", "-x", "-t", "jpg", "-C", tmp_path],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        img = Image.open(tmp_path)
        os.unlink(tmp_path)

        # Resize to max 1024 wide to save bandwidth
        if img.width > 1024:
            ratio = 1024 / img.width
            img = img.resize((1024, int(img.height * ratio)), Image.LANCZOS)

        img = img.convert("RGBA")
        arr = np.array(img)
        frame = rtc.VideoFrame(
            width=img.width,
            height=img.height,
            type=rtc.VideoBufferType.RGBA,
            data=arr.tobytes(),
        )
        return frame
    except Exception as e:
        logger.warning(f"Screenshot capture failed: {e}")
        return None


class ScreenCaptureVideoInput(VideoInput):
    """Custom VideoInput that yields screenshots of the screen periodically."""

    def __init__(self, interval: float = SCREENSHOT_INTERVAL):
        super().__init__(label="screen-capture")
        self._interval = interval
        self._running = False

    def on_attached(self) -> None:
        self._running = True
        logger.info("Screen capture attached (every %ds)", self._interval)

    def on_detached(self) -> None:
        self._running = False
        logger.info("Screen capture detached")

    async def __anext__(self) -> rtc.VideoFrame:
        while True:
            if not self._running:
                await asyncio.sleep(0.5)
                continue

            frame = await asyncio.to_thread(capture_screenshot_frame)
            if frame:
                logger.debug("Captured screenshot frame (%dx%d)", frame.width, frame.height)
                await asyncio.sleep(self._interval)
                return frame

            await asyncio.sleep(self._interval)


class DSAInterviewer(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=INTERVIEWER_INSTRUCTIONS,
        )


server = AgentServer()


@server.rtc_session(agent_name="algo-interviewer")
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        vad=silero.VAD.load(),
        llm=google.beta.realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-12-2025",
            voice="puck",
            enable_affective_dialog=True,
            proactivity=True,
        ),
    )

    # Set up screen capture as video input
    screen_input = ScreenCaptureVideoInput(interval=SCREENSHOT_INTERVAL)
    session.input.video = screen_input

    await session.start(
        agent=DSAInterviewer(),
        room=ctx.room,
    )
    await session.generate_reply(
        instructions="Greet the candidate warmly. Introduce yourself as a DSA Teacher, their DSA interview practice partner. Mention that you can see their screen so they should keep their code editor visible. Ask what topic and difficulty they'd like to start with. Keep it to 2-3 sentences, be natural and friendly.",
    )


if __name__ == "__main__":
    cli.run_app(server)
