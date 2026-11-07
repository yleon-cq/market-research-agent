"""评测入口：跑 eval_set.jsonl，逐场景算指标，输出 eval_report.md / .json。

用法：
    python main.py eval
"""
import asyncio
import datetime
import json
import uuid
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

import os

PROJECT_ROOT = Path(__file__).parents[1].resolve()
EVAL_SET = Path(__file__).parent / "eval_set.jsonl"
REPORT_DIR = PROJECT_ROOT / "output" / "eval"


async def _run_one(query: str, thread_id: str) -> str:
    session_dir = REPORT_DIR / f"session_{thread_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    if os.getenv("MOCK_LLM", "0") == "1" or not os.getenv("DASHSCOPE_API_KEY", ""):
        from agent.mock_runtime import run_mock_agent

        runner = run_mock_agent(str(session_dir), thread_id, query)
    else:
        from agent.llm import model
        from agent.main_agent import build_main_agent, run_deep_agent

        agent = await build_main_agent(model)
        runner = run_deep_agent(agent, str(session_dir), thread_id, query)
    async for _ in runner:
        pass
    return str(session_dir)


async def run_evaluation():
    from eval.metrics import evaluate_summary
    from eval.trajectory import TrajectoryRecorder

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cases = [
        json.loads(line)
        for line in EVAL_SET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = []
    for case in cases:
        thread_id = f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"
        print(f"▶ 运行评测 {case['id']}: {case['query'][:40]}…")
        await _run_one(case["query"], thread_id)
        # 轨迹由运行时写入默认目录 output/trajectories/<thread_id>.jsonl
        recorder = TrajectoryRecorder(thread_id)
        if recorder.path.exists():
            for line in recorder.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    recorder.events.append(json.loads(line))
        summary = recorder.summary()
        metrics = evaluate_summary(summary, case["expected_dimensions"], case["expect_file"])
        results.append({"case": case, "summary": summary, "metrics": metrics})
        print(f"  score={metrics['score']} coverage={metrics['info_coverage']}")

    # 汇总报告
    avg_score = round(sum(r["metrics"]["score"] for r in results) / len(results), 3)
    report_lines = [
        "# Agent 评测报告",
        "",
        f"> 运行时间: {datetime.datetime.now().isoformat(timespec='seconds')} ｜ 用例数: {len(results)} ｜ 平均分: **{avg_score}**",
        "",
        "| 用例 | 场景 | 维度覆盖 | 任务完成 | 效率 | 总分 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        m, c = r["metrics"], r["case"]
        report_lines.append(
            f"| {c['id']} | {c['query'][:24]}… | {m['info_coverage']}（{','.join(m['covered_dimensions']) or '无'}）"
            f" | {'✅' if m['task_completed'] else '❌'} | {m['efficiency']} | **{m['score']}** |"
        )
    report_md = "\n".join(report_lines)
    (REPORT_DIR / "eval_report.md").write_text(report_md, encoding="utf-8")
    (REPORT_DIR / "eval_report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n✅ 评测完成，平均分 {avg_score}，报告: {REPORT_DIR / 'eval_report.md'}")
