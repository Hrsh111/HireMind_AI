"""Generate explainability evaluation JSON and PDF report."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from llm import LLMClient


def _extract_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        return None
    return None


def _normalize_evaluation(competencies: list[str], payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        payload = {}

    incoming = payload.get("competency_scores", [])
    score_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(incoming, list):
        for item in incoming:
            if not isinstance(item, dict):
                continue
            name = str(item.get("competency", "")).strip()
            if not name:
                continue
            score_by_name[name.lower()] = {
                "competency": name,
                "score": item.get("score", 3),
                "evidence": str(item.get("evidence", "")).strip(),
            }

    normalized_scores: list[dict[str, Any]] = []
    for comp in competencies[:3]:
        key = comp.lower()
        item = score_by_name.get(key)
        if not item:
            item = {
                "competency": comp,
                "score": 3,
                "evidence": "Limited direct signal in transcript; partial demonstration observed.",
            }
        try:
            score = int(item.get("score", 3))
        except (TypeError, ValueError):
            score = 3
        score = max(1, min(5, score))
        evidence = str(item.get("evidence", "")).strip() or "No clear evidence captured."
        normalized_scores.append(
            {
                "competency": comp,
                "score": score,
                "evidence": evidence,
            }
        )

    overall_summary = str(payload.get("overall_summary", "")).strip() or (
        "The candidate showed mixed performance across target competencies."
    )
    actionable_feedback = payload.get("actionable_feedback", [])
    if not isinstance(actionable_feedback, list):
        actionable_feedback = []
    actionable_feedback = [str(item).strip() for item in actionable_feedback if str(item).strip()]
    if not actionable_feedback:
        actionable_feedback = [
            "Practice articulating complexity trade-offs out loud before coding.",
            "Add edge-case checks early and validate assumptions with examples.",
            "Explain why each data structure choice supports the intended complexity.",
        ]

    return {
        "competency_scores": normalized_scores,
        "overall_summary": overall_summary,
        "actionable_feedback": actionable_feedback[:5],
    }


def build_competency_evaluation(
    llm: LLMClient,
    competencies: list[str],
    chat_history_text: str,
    final_code: str,
    question_title: str,
    question_description: str,
) -> dict[str, Any]:
    """Request strict competency scoring JSON from the LLM."""
    evaluator = LLMClient(api_key=getattr(llm, "_api_key", ""), model=getattr(llm, "_model", ""))
    evaluator.set_system_prompt(
        "You are a strict evaluator. Return only valid JSON and no markdown."
    )

    comp_a, comp_b, comp_c = (competencies + ["Problem Solving", "Code Quality", "Communication"])[:3]
    prompt = f"""\
Evaluate this interview and return ONLY JSON with this schema:
{{
  "competency_scores": [
    {{"competency": "{comp_a}", "score": 1-5, "evidence": "1-2 sentences"}},
    {{"competency": "{comp_b}", "score": 1-5, "evidence": "1-2 sentences"}},
    {{"competency": "{comp_c}", "score": 1-5, "evidence": "1-2 sentences"}}
  ],
  "overall_summary": "2-3 sentences",
  "actionable_feedback": ["bullet 1", "bullet 2", "bullet 3"]
}}

Scoring rules:
- Scores are integers from 1 to 5.
- Each competency must include evidence grounded in transcript/code behavior.
- Keep evidence factual and concise.

Interview problem title: {question_title}
Interview problem description:
{question_description}

Transcript:
{chat_history_text}

Candidate final code:
```text
{final_code}
```
"""

    raw = evaluator.chat(prompt, stream=False)
    parsed = _extract_json(raw)
    return _normalize_evaluation([comp_a, comp_b, comp_c], parsed)


def generate_pdf_report(
    output_path: str | Path,
    job_title: str,
    candidate_summary: str,
    question_title: str,
    question_description: str,
    competencies: list[str],
    evaluation: dict[str, Any],
    final_code: str,
):
    """Generate the interview_evaluation.pdf file."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = Path(output_path)
    doc = SimpleDocTemplate(str(output), pagesize=LETTER, leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )
    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=8,
    )
    body_style = styles["BodyText"]
    body_style.leading = 14

    story = [
        Paragraph("Interview Explainability Report", title_style),
        Spacer(1, 0.12 * inch),
        Paragraph(f"<b>Role:</b> {job_title or 'Software Engineer'}", body_style),
        Paragraph(f"<b>Candidate Summary:</b> {candidate_summary or 'Not provided'}", body_style),
        Spacer(1, 0.15 * inch),
        Paragraph("Interview Problem", heading_style),
        Paragraph(f"<b>{question_title}</b>", body_style),
        Paragraph(question_description, body_style),
        Spacer(1, 0.18 * inch),
        Paragraph("Competency Scores", heading_style),
    ]

    table_data = [["Competency", "Score (1-5)", "Evidence"]]
    for item in evaluation.get("competency_scores", []):
        table_data.append(
            [
                str(item.get("competency", "")),
                str(item.get("score", "")),
                str(item.get("evidence", "")),
            ]
        )

    table = Table(table_data, colWidths=[1.8 * inch, 1.1 * inch, 3.5 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("Overall Summary", heading_style))
    story.append(Paragraph(str(evaluation.get("overall_summary", "")), body_style))
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("Actionable Feedback", heading_style))
    for item in evaluation.get("actionable_feedback", []):
        story.append(Paragraph(f"- {item}", body_style))
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("Target Competencies", heading_style))
    story.append(Paragraph(", ".join(competencies[:3]) if competencies else "Not available", body_style))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Final Code Snapshot", heading_style))
    code_excerpt = (final_code or "(no code submitted)").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    story.append(Paragraph(f"<font name='Courier'>{code_excerpt[:6000]}</font>", body_style))

    doc.build(story)


def generate_explainability_report(
    llm: LLMClient,
    output_path: str | Path,
    job_title: str,
    candidate_summary: str,
    competencies: list[str],
    question_title: str,
    question_description: str,
    chat_history_text: str,
    final_code: str,
) -> dict[str, Any]:
    """Build JSON evaluation and write the final PDF report."""
    evaluation = build_competency_evaluation(
        llm=llm,
        competencies=competencies,
        chat_history_text=chat_history_text,
        final_code=final_code,
        question_title=question_title,
        question_description=question_description,
    )
    generate_pdf_report(
        output_path=output_path,
        job_title=job_title,
        candidate_summary=candidate_summary,
        question_title=question_title,
        question_description=question_description,
        competencies=competencies,
        evaluation=evaluation,
        final_code=final_code,
    )
    return evaluation
