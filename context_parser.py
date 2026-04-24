"""Context parser that generates a custom interview focus from JD + resume."""

from __future__ import annotations

import json
import re
from typing import Any

from config import GROQ_API_KEY, GROQ_MODEL
from llm import LLMClient


DEFAULT_CONTEXT = {
    "competencies": ["Problem Solving", "Data Structures", "Communication"],
    "custom_question_title": "Context-Aware Data Processing Pipeline",
    "custom_question_description": (
        "Design a function that processes a stream of records and returns the first non-repeating "
        "record key after each insertion. Explain the data structures you choose, handle high-volume "
        "input efficiently, and discuss trade-offs."
    ),
    "expected_time": "O(n)",
    "expected_space": "O(n)",
}


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def _sanitize_context(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return dict(DEFAULT_CONTEXT)

    competencies = payload.get("competencies", DEFAULT_CONTEXT["competencies"])
    if not isinstance(competencies, list):
        competencies = DEFAULT_CONTEXT["competencies"]
    cleaned_competencies = [str(c).strip() for c in competencies if str(c).strip()]
    if len(cleaned_competencies) < 3:
        for item in DEFAULT_CONTEXT["competencies"]:
            if item not in cleaned_competencies:
                cleaned_competencies.append(item)
            if len(cleaned_competencies) == 3:
                break
    cleaned_competencies = cleaned_competencies[:3]

    title = str(payload.get("custom_question_title", "")).strip() or DEFAULT_CONTEXT["custom_question_title"]
    description = str(payload.get("custom_question_description", "")).strip() or DEFAULT_CONTEXT["custom_question_description"]
    expected_time = str(payload.get("expected_time", "")).strip() or DEFAULT_CONTEXT["expected_time"]
    expected_space = str(payload.get("expected_space", "")).strip() or DEFAULT_CONTEXT["expected_space"]

    return {
        "competencies": cleaned_competencies,
        "custom_question_title": title,
        "custom_question_description": description,
        "expected_time": expected_time,
        "expected_space": expected_space,
    }


def parse_interview_context(jd_text, resume_text):
    """Extract target competencies and a custom interview question from JD + resume."""
    jd = (jd_text or "").strip()
    resume = (resume_text or "").strip()
    if not jd and not resume:
        return dict(DEFAULT_CONTEXT)

    llm = LLMClient(api_key=GROQ_API_KEY, model=GROQ_MODEL)
    llm.set_system_prompt(
        "You are a strict JSON generator for interview setup. "
        "Return valid JSON only with no markdown, notes, or extra text."
    )
    prompt = f"""\
You are preparing a DSA/systems interview based on the candidate's resume and a job description.

Return exactly one JSON object with this schema:
{{
  "competencies": ["<competency1>", "<competency2>", "<competency3>"],
  "custom_question_title": "<short title>",
  "custom_question_description": "<clear problem statement tailored to the candidate level>",
  "expected_time": "<expected asymptotic time complexity>",
  "expected_space": "<expected asymptotic space complexity>"
}}

Rules:
- Extract exactly 3 competencies from the JD that are relevant for coding interviews.
- Make the question adaptive to candidate seniority inferred from the resume.
- Keep question suitable for a 30-45 minute interview.
- Keep complexities realistic for the question.

Job Description:
{jd if jd else "(not provided)"}

Resume:
{resume if resume else "(not provided)"}
"""

    raw = llm.chat(prompt, stream=False)
    parsed = _extract_json_object(raw)
    return _sanitize_context(parsed)
