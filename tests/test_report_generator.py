from report_generator import _extract_json, _normalize_evaluation


def test_extract_json_plain():
    assert _extract_json('{"x": 1}') == {"x": 1}


def test_extract_json_embedded():
    assert _extract_json('text {"x": 1} more') == {"x": 1}


def test_extract_json_bad():
    assert _extract_json("nope") is None


def test_normalize_empty_payload_defaults():
    r = _normalize_evaluation(["A", "B", "C"], None)
    assert len(r["competency_scores"]) == 3
    assert all(1 <= c["score"] <= 5 for c in r["competency_scores"])
    assert len(r["actionable_feedback"]) >= 1


def test_normalize_clamps_high_score():
    payload = {"competency_scores": [{"competency": "A", "score": 99, "evidence": "x"}]}
    r = _normalize_evaluation(["A", "B", "C"], payload)
    a = next(c for c in r["competency_scores"] if c["competency"] == "A")
    assert a["score"] == 5


def test_normalize_clamps_low_score():
    payload = {"competency_scores": [{"competency": "A", "score": -3, "evidence": "x"}]}
    r = _normalize_evaluation(["A", "B", "C"], payload)
    a = next(c for c in r["competency_scores"] if c["competency"] == "A")
    assert a["score"] == 1


def test_normalize_truncates_to_three():
    r = _normalize_evaluation(["A", "B", "C", "D"], None)
    assert len(r["competency_scores"]) == 3


def test_generate_pdf_smoke(tmp_path):
    from report_generator import generate_pdf_report

    out = tmp_path / "report.pdf"
    generate_pdf_report(
        output_path=out,
        job_title="SWE",
        candidate_summary="summary",
        question_title="Q",
        question_description="desc",
        competencies=["A", "B", "C"],
        evaluation={
            "competency_scores": [{"competency": "A", "score": 4, "evidence": "e"}],
            "overall_summary": "s",
            "actionable_feedback": ["f"],
        },
        final_code="def f(a):\n    for x in a:\n        print(x)\n",
    )
    assert out.exists() and out.stat().st_size > 0
