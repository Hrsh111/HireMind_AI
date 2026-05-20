from code_analysis import analyze_code, format_analysis


def test_empty_source():
    r = analyze_code("")
    assert r["summary"] == "No code submitted."
    assert r["metrics"]["cyclomatic_complexity"] == 0
    assert r["heuristics"]["estimated_time"] == "n/a"


def test_simple_function_constant_time():
    r = analyze_code("def f(x):\n    return x + 1\n")
    assert r["parse_ok"] is True
    assert r["metrics"]["functions"] == 1
    assert r["metrics"]["max_loop_depth"] == 0
    assert r["metrics"]["cyclomatic_complexity"] == 1
    assert "O(1)" in r["heuristics"]["estimated_time"]


def test_single_loop_linear():
    r = analyze_code("def f(a):\n    t = 0\n    for x in a:\n        t += x\n    return t\n")
    assert r["metrics"]["loops"] == 1
    assert r["metrics"]["max_loop_depth"] == 1
    assert "O(n)" in r["heuristics"]["estimated_time"]


def test_nested_loops_quadratic():
    src = "def f(a):\n    for i in a:\n        for j in a:\n            print(i, j)\n"
    r = analyze_code(src)
    assert r["metrics"]["max_loop_depth"] == 2
    assert "O(n^2)" in r["heuristics"]["estimated_time"]


def test_recursion_detected():
    src = "def fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\n"
    r = analyze_code(src)
    assert r["metrics"]["has_recursion"] is True
    assert "Recursive" in r["heuristics"]["estimated_time"]


def test_cyclomatic_counts_branches():
    src = (
        "def f(x):\n"
        "    if x > 0 and x < 10:\n"
        "        return 1\n"
        "    elif x == 0:\n"
        "        return 0\n"
        "    return -1\n"
    )
    r = analyze_code(src)
    # base(1) + if(1) + elif-as-If(1) + boolop 'and'(1) == 4
    assert r["metrics"]["cyclomatic_complexity"] == 4


def test_comprehension_is_linear():
    r = analyze_code("def f(a):\n    return [x * 2 for x in a]\n")
    assert r["metrics"]["comprehensions"] == 1
    assert "O(n)" in r["heuristics"]["estimated_time"]


def test_syntax_error():
    r = analyze_code("def f(:\n    pass\n")
    assert r["parse_ok"] is False
    assert r["syntax_error"] is not None
    assert "syntax error" in r["summary"].lower()


def test_non_python_language():
    r = analyze_code("function f(){ return 1; }", language="javascript")
    assert r["language"] == "javascript"
    assert "Python-only" in r["summary"]


def test_format_analysis_string():
    s = format_analysis(analyze_code("def f():\n    return 1\n"))
    assert "Static code analysis" in s
    assert "Cyclomatic complexity" in s
