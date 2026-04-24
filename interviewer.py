"""Core interview engine — dynamic context state machine and logic."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from config import MAX_HINTS
from context_parser import parse_interview_context
from llm import LLMClient
from report_generator import generate_explainability_report
from voice import VoicePipeline
from watcher import FileWatcher
import prompts
import ui


class State(Enum):
    GREETING = auto()
    TOPIC_SELECT = auto()
    ASK_QUESTION = auto()
    CODING = auto()
    EVALUATE = auto()
    FINISHED = auto()


@dataclass
class DynamicQuestion:
    title: str
    description: str
    expected_time: str
    expected_space: str


class Interviewer:
    def __init__(
        self,
        llm: LLMClient,
        voice: VoicePipeline,
        watcher: FileWatcher | None,
        jd_text: str = "",
        resume_text: str = "",
    ):
        self.llm = llm
        self.voice = voice
        self.watcher = watcher

        self.jd_text = (jd_text or "").strip()
        self.resume_text = (resume_text or "").strip()
        self.job_title = self._extract_job_title(self.jd_text)
        self.candidate_summary = self._extract_candidate_summary(self.resume_text)

        self.state = State.GREETING
        self.difficulty: str = "adaptive"
        self.current_question: DynamicQuestion | None = None
        self.target_competencies: list[str] = []
        self.hints_used: int = 0
        self.last_code_change: float = 0
        self.last_code: str = ""
        self._code_change_pending = False

        self.chat_history: list[dict[str, str]] = []
        self.report_generated = False
        self.report_path = Path("interview_evaluation.pdf")
        self.last_evaluation_json: dict | None = None

        self._refresh_interview_context()

        self.llm.set_system_prompt(
            prompts.build_system_prompt(
                job_title=self.job_title,
                candidate_summary=self.candidate_summary,
                target_competencies=self.target_competencies,
            )
        )

    def _extract_job_title(self, jd_text: str) -> str:
        if not jd_text.strip():
            return "Software Engineer"

        # Prefer explicit role/title lines from the JD.
        title_patterns = [
            r"(?:job\s*title|role|position)\s*[:\-]\s*(.+)",
            r"^(.{3,80}?engineer.{0,40})$",
            r"^(.{3,80}?developer.{0,40})$",
        ]
        lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
        for line in lines[:25]:
            for pattern in title_patterns:
                match = re.search(pattern, line, flags=re.IGNORECASE)
                if match:
                    return match.group(1).strip().strip(".")
        return "Software Engineer"

    def _extract_candidate_summary(self, resume_text: str) -> str:
        if not resume_text.strip():
            return "Candidate summary unavailable."

        cleaned = [line.strip(" -\t") for line in resume_text.splitlines() if line.strip()]
        if not cleaned:
            return "Candidate summary unavailable."
        return " | ".join(cleaned[:3])[:350]

    def _refresh_interview_context(self):
        context = parse_interview_context(self.jd_text, self.resume_text)
        competencies = context.get("competencies", [])
        self.target_competencies = [str(c).strip() for c in competencies if str(c).strip()][:3]
        if len(self.target_competencies) < 3:
            defaults = ["Problem Solving", "Code Quality", "Communication"]
            for item in defaults:
                if item not in self.target_competencies:
                    self.target_competencies.append(item)
                if len(self.target_competencies) == 3:
                    break

        self.current_question = DynamicQuestion(
            title=str(context.get("custom_question_title", "Custom Coding Question")).strip(),
            description=str(context.get("custom_question_description", "Solve the problem and discuss trade-offs.")).strip(),
            expected_time=str(context.get("expected_time", "O(n)")).strip(),
            expected_space=str(context.get("expected_space", "O(n)")).strip(),
        )

    def _log_turn(self, role: str, text: str):
        content = (text or "").strip()
        if not content:
            return
        self.chat_history.append({"role": role, "text": content})

    def on_code_change(self, filepath: str, content: str):
        """Callback from file watcher when code changes."""
        self.last_code = content
        self.last_code_change = time.time()
        self._code_change_pending = True
        ui.print_file_change(filepath)

    def _say(self, text: str):
        """Display text and speak it."""
        ui.print_bot(text)
        self.voice.speak(text)
        self._log_turn("assistant", text)

    def _ask_llm(self, prompt: str) -> str:
        """Send prompt to LLM, display + speak in real-time as chunks arrive."""
        stream = self.llm.chat_stream(prompt)

        def display_and_yield():
            from rich.console import Console

            console = Console()
            console.print("\n [bold blue]Algo:[/bold blue] ", end="")
            for chunk in stream:
                console.print(chunk, end="", highlight=False)
                yield chunk
            console.print()

        full_text = self.voice.speak_streamed(display_and_yield())
        self._log_turn("assistant", full_text)
        return full_text

    def _get_user_input(self) -> str:
        """Get input from user via voice or text."""
        if self.voice.stt_available:
            ui.print_info("Press Enter to speak, or type your response:")
            text = ui.get_input()
            if text == "":
                text = self.voice.listen()
                if text:
                    ui.print_user(text)
                else:
                    ui.print_info("Didn't catch that. Please type instead.")
                    text = ui.get_input()
            self._log_turn("user", text)
            return text

        text = ui.get_input()
        self._log_turn("user", text)
        return text

    def run(self):
        """Main interview loop."""
        ui.print_banner()

        while self.state != State.FINISHED:
            if self.state == State.GREETING:
                self._handle_greeting()
            elif self.state == State.TOPIC_SELECT:
                self._handle_topic_select()
            elif self.state == State.ASK_QUESTION:
                self._handle_ask_question()
            elif self.state == State.CODING:
                self._handle_coding()
            elif self.state == State.EVALUATE:
                self._handle_evaluate()

        self._finalize_session()

    def _handle_greeting(self):
        prompt = prompts.GREETING_PROMPT_TEMPLATE.format(
            job_title=self.job_title,
            target_competencies=", ".join(self.target_competencies),
        )
        self._ask_llm(prompt)
        self.state = State.ASK_QUESTION

    def _handle_topic_select(self):
        self._say(
            "I will generate a new role-aligned question using your resume and job description context."
        )
        self.state = State.ASK_QUESTION

    def _handle_ask_question(self):
        self._refresh_interview_context()
        self.hints_used = 0

        if not self.current_question:
            self._say("I could not generate a custom question. Let me retry.")
            return

        ui.print_question(
            self.current_question.title,
            self.current_question.description,
            self.difficulty,
            [],
        )

        prompt = prompts.QUESTION_PROMPT_TEMPLATE.format(
            title=self.current_question.title,
            description=self.current_question.description,
            expected_time=self.current_question.expected_time,
            expected_space=self.current_question.expected_space,
            target_competencies=", ".join(self.target_competencies),
        )
        self._ask_llm(prompt)

        ui.print_status("custom", self.difficulty, self.hints_used, MAX_HINTS, self.voice.enabled)
        self.last_code_change = time.time()
        self.last_code = ""
        self._code_change_pending = False
        self.state = State.CODING

    def _handle_coding(self):
        """Interactive coding phase — user codes, bot observes."""
        if self.watcher:
            ui.print_info("Start coding! I'm watching your file for changes.")

        user_input = self._get_user_input()
        if self._check_quit(user_input):
            return

        lower = user_input.lower().strip()

        if lower == "hint":
            self._give_hint()
            return
        if lower == "done":
            self.state = State.EVALUATE
            return
        if lower == "skip":
            self._say("No problem. I will generate a new question aligned to your target competencies.")
            self.state = State.ASK_QUESTION
            return
        if lower == "topic":
            self.state = State.TOPIC_SELECT
            return
        if lower.startswith("voice"):
            self._toggle_voice(lower)
            return

        if self._code_change_pending and self.current_question:
            self._code_change_pending = False
            observe_prompt = prompts.CODE_OBSERVATION_TEMPLATE.format(
                title=self.current_question.title,
                code=self.last_code[-3000:],
                hints_given=self.hints_used,
                max_hints=MAX_HINTS,
                target_competencies=", ".join(self.target_competencies),
            )
            response = self.llm.chat(observe_prompt, stream=False)
            if response.strip() and response.strip() != "...":
                self._say(response)

        if user_input:
            context = ""
            if self.last_code:
                context = f"\n[Current code state:\n{self.last_code[-2000:]}\n]\n"
            self._ask_llm(context + user_input)

    def _give_hint(self):
        if not self.current_question:
            self._say("Let me give you a general hint based on your current approach.")
            self._ask_llm(
                "The candidate asked for a hint. Provide one short nudge tied to the target competencies."
            )
            return

        if self.hints_used >= MAX_HINTS:
            self._say(
                "I've given all available hints for this problem. Try to continue from here, or say skip."
            )
            return

        self.hints_used += 1
        hint_seed = f"Candidate requested hint level {self.hints_used}"
        prompt = prompts.HINT_TEMPLATE.format(
            title=self.current_question.title,
            code=self.last_code[-2000:] if self.last_code else "(no code yet)",
            hint_number=self.hints_used,
            max_hints=MAX_HINTS,
            hint_text=hint_seed,
            target_competencies=", ".join(self.target_competencies),
        )

        self._ask_llm(prompt)
        ui.print_status("custom", self.difficulty, self.hints_used, MAX_HINTS, self.voice.enabled)

    def _handle_evaluate(self):
        if not self.last_code and self.watcher:
            self.last_code = self.watcher.current_code

        if self.current_question:
            prompt = prompts.EVALUATE_TEMPLATE.format(
                title=self.current_question.title,
                expected_time=self.current_question.expected_time,
                expected_space=self.current_question.expected_space,
                target_competencies=", ".join(self.target_competencies),
                code=self.last_code[-3000:] if self.last_code else "(no code submitted)",
            )
        else:
            prompt = (
                "The candidate says they are done. Evaluate correctness and complexity, then score target competencies.\n"
                f"Target competencies: {', '.join(self.target_competencies)}\n"
                f"Code:\n```\n{self.last_code[-3000:]}\n```"
            )

        response = self._ask_llm(prompt)
        ui.print_evaluation(response)

        self._say("Would you like another context-tailored question, or should we end this session?")
        user_input = self._get_user_input()
        if self._check_quit(user_input):
            return

        lower = user_input.lower()
        if "topic" in lower or "change" in lower or "new" in lower:
            self.state = State.TOPIC_SELECT
        elif "quit" in lower or "exit" in lower:
            self.state = State.FINISHED
        else:
            self.state = State.ASK_QUESTION

    def _toggle_voice(self, command: str):
        if "off" in command:
            self.voice.enabled = False
            ui.print_info("Voice disabled. Text mode only.")
        elif "on" in command:
            self.voice.enabled = True
            ui.print_info("Voice enabled.")
        ui.print_status("custom", self.difficulty, self.hints_used, MAX_HINTS, self.voice.enabled)

    def _check_quit(self, text: str) -> bool:
        if text.lower().strip() in ("quit", "exit", "q"):
            self._say("Great session. I'll generate your explainability report now.")
            self.state = State.FINISHED
            return True
        return False

    def _finalize_session(self):
        if self.report_generated:
            return

        if not self.last_code and self.watcher:
            self.last_code = self.watcher.current_code

        question = self.current_question or DynamicQuestion(
            title="Custom Interview Question",
            description="Context-driven coding problem.",
            expected_time="O(n)",
            expected_space="O(n)",
        )
        transcript = "\n".join(
            f"{turn['role'].upper()}: {turn['text']}" for turn in self.chat_history
        )
        if len(transcript) > 12000:
            transcript = transcript[-12000:]

        try:
            self.last_evaluation_json = generate_explainability_report(
                llm=self.llm,
                output_path=self.report_path,
                job_title=self.job_title,
                candidate_summary=self.candidate_summary,
                competencies=self.target_competencies,
                question_title=question.title,
                question_description=question.description,
                chat_history_text=transcript,
                final_code=self.last_code[-6000:] if self.last_code else "(no code submitted)",
            )
            self.report_generated = True
            ui.print_info(f"Explainability report generated: {self.report_path.resolve()}")
        except Exception as exc:
            ui.print_error(f"Failed to generate explainability report: {exc}")
