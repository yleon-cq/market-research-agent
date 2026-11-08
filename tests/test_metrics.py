"""评测指标计算测试。"""
from eval.metrics import evaluate_summary


def _summary(tool_names, files=("竞品调研报告.md",), calls=None):
    return {
        "tool_names": tool_names,
        "files_generated": list(files),
        "tool_calls": calls if calls is not None else len(tool_names),
        "assistant_calls": 2,
    }


def test_full_coverage():
    s = _summary(["execute_sql_query", "search_knowledge_docs", "internet_search", "mcp_get_industry_events"])
    m = evaluate_summary(s, ["database", "knowledge", "network", "mcp"], expect_file=True)
    assert m["info_coverage"] == 1.0
    assert m["task_completed"] is True


def test_partial_coverage():
    s = _summary(["execute_sql_query"])
    m = evaluate_summary(s, ["database", "network"], expect_file=True)
    assert m["info_coverage"] == 0.5


def test_missing_file_fails_task():
    s = _summary(["execute_sql_query"], files=[])
    m = evaluate_summary(s, ["database"], expect_file=True)
    assert m["task_completed"] is False
    assert m["score"] < 1.0


def test_efficiency_penalizes_retries():
    many = ["internet_search"] * 20
    m1 = evaluate_summary(_summary(many), ["network"], expect_file=False)
    m2 = evaluate_summary(_summary(["internet_search"]), ["network"], expect_file=False)
    assert m2["efficiency"] > m1["efficiency"]
