"""Static analysis of candidate code: complexity metrics and heuristics.

Pure-Python with no third-party dependencies. Performs AST-based analysis for
Python source (cyclomatic complexity, loop nesting, recursion detection) and a
light line-based summary for other languages. The heuristics are intentionally
rough — they are decision aids for an interviewer, not a proof of complexity.
"""

from __future__ import annotations

import ast
from typing import Any

_LOOP_NODES = (ast.For, ast.AsyncFor, ast.While)
_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_ALLOCATIONS = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.SetComp, ast.DictComp)


def _line_metrics(source: str) -> dict[str, int]:
    lines = source.splitlines()
    return {
        "total_lines": len(lines),
        "code_lines": sum(1 for ln in lines if ln.strip()),
    }


def _cyclomatic_complexity(tree: ast.AST) -> int:
    complexity = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            complexity += 1 + len(node.ifs)
    return complexity


def _max_loop_depth(node: ast.AST, current: int = 0) -> int:
    best = current
    for child in ast.iter_child_nodes(node):
        nxt = current + 1 if isinstance(child, _LOOP_NODES) else current
        best = max(best, _max_loop_depth(child, nxt))
    return best


def _has_recursion(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, _FUNC_NODES):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            fn = sub.func
            called = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
            if called == node.name:
                return True
    return False


def _empty_result(language: str) -> dict[str, Any]:
    return {
        "language": language,
        "parse_ok": True,
        "syntax_error": None,
        "metrics": {
            "total_lines": 0,
            "code_lines": 0,
            "functions": 0,
            "classes": 0,
            "loops": 0,
            "comprehensions": 0,
            "max_loop_depth": 0,
            "cyclomatic_complexity": 0,
            "has_recursion": False,
        },
        "heuristics": {"estimated_time": "n/a", "estimated_space": "n/a"},
        "summary": "No code submitted.",
    }


def _time_hint(max_loop_depth: int, comprehensions: int, recursion: bool) -> str:
    if recursion:
        return "Recursive — analyze the recurrence; risk of exponential time without memoization."
    effective = max_loop_depth or (1 if comprehensions else 0)
    if effective == 0:
        return "~O(1) — no loops detected."
    if effective == 1:
        return "~O(n) — single-level iteration."
    return f"~O(n^{effective}) — {effective}-level nested loops."


def _space_hint(allocations: int, recursion: bool) -> str:
    if recursion:
        return "At least O(recursion depth) call-stack space; more if results are accumulated."
    if allocations:
        return "Allocates collections — likely O(n) auxiliary space."
    return "Likely O(1) auxiliary space (no obvious collection allocations)."


def analyze_code(source: str, language: str = "python") -> dict[str, Any]:
    """Return complexity metrics and heuristic time/space estimates for `source`."""
    source = source or ""
    language = (language or "python").lower()

    if not source.strip():
        return _empty_result(language)

    if language != "python":
        line_metrics = _line_metrics(source)
        return {
            "language": language,
            "parse_ok": True,
            "syntax_error": None,
            "metrics": {
                **line_metrics,
                "functions": 0,
                "classes": 0,
                "loops": 0,
                "comprehensions": 0,
                "max_loop_depth": 0,
                "cyclomatic_complexity": 0,
                "has_recursion": False,
            },
            "heuristics": {
                "estimated_time": "n/a (deep analysis supported for Python only)",
                "estimated_space": "n/a (deep analysis supported for Python only)",
            },
            "summary": f"{line_metrics['code_lines']} lines of {language}; deep analysis is Python-only.",
        }

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "language": "python",
            "parse_ok": False,
            "syntax_error": f"line {exc.lineno}: {exc.msg}",
            "metrics": {**_line_metrics(source), "functions": 0, "classes": 0, "loops": 0,
                        "comprehensions": 0, "max_loop_depth": 0, "cyclomatic_complexity": 0,
                        "has_recursion": False},
            "heuristics": {"estimated_time": "n/a", "estimated_space": "n/a"},
            "summary": f"Code has a syntax error (line {exc.lineno}: {exc.msg}).",
        }

    nodes = list(ast.walk(tree))
    functions = sum(isinstance(n, _FUNC_NODES) for n in nodes)
    classes = sum(isinstance(n, ast.ClassDef) for n in nodes)
    loops = sum(isinstance(n, _LOOP_NODES) for n in nodes)
    comprehensions = sum(isinstance(n, _COMPREHENSIONS) for n in nodes)
    allocations = sum(isinstance(n, _ALLOCATIONS) for n in nodes)
    max_loop_depth = _max_loop_depth(tree)
    recursion = _has_recursion(tree)
    cyclomatic = _cyclomatic_complexity(tree)

    metrics = {
        **_line_metrics(source),
        "functions": functions,
        "classes": classes,
        "loops": loops,
        "comprehensions": comprehensions,
        "max_loop_depth": max_loop_depth,
        "cyclomatic_complexity": cyclomatic,
        "has_recursion": recursion,
    }
    time_hint = _time_hint(max_loop_depth, comprehensions, recursion)
    space_hint = _space_hint(allocations, recursion)

    return {
        "language": "python",
        "parse_ok": True,
        "syntax_error": None,
        "metrics": metrics,
        "heuristics": {"estimated_time": time_hint, "estimated_space": space_hint},
        "summary": (
            f"{functions} function(s), {classes} class(es); cyclomatic complexity "
            f"{cyclomatic}; {time_hint}"
        ),
    }


def format_analysis(analysis: dict[str, Any]) -> str:
    """Render an analysis dict as a readable multi-line string."""
    if not analysis.get("parse_ok"):
        return f"Static analysis: {analysis.get('summary', 'unparseable code')}"
    m = analysis.get("metrics", {})
    h = analysis.get("heuristics", {})
    return (
        "Static code analysis:\n"
        f"  Lines (code/total): {m.get('code_lines', 0)}/{m.get('total_lines', 0)}\n"
        f"  Functions/Classes:  {m.get('functions', 0)}/{m.get('classes', 0)}\n"
        f"  Loops (max nesting): {m.get('loops', 0)} ({m.get('max_loop_depth', 0)})\n"
        f"  Cyclomatic complexity: {m.get('cyclomatic_complexity', 0)}\n"
        f"  Recursion: {'yes' if m.get('has_recursion') else 'no'}\n"
        f"  Estimated time:  {h.get('estimated_time', 'n/a')}\n"
        f"  Estimated space: {h.get('estimated_space', 'n/a')}"
    )
