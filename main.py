"""market-research-agent 入口。

用法：
    python main.py server          # 启动 Web 服务（http://localhost:8000）
    python main.py demo            # 演示模式跑一次完整调研（无需 LLM Key）
    python main.py cli "调研问题"   # 真实模式命令行执行
    python main.py eval            # 跑评测集，输出 eval_report
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv as _ld  # noqa: E402

_ld(PROJECT_ROOT / ".env", override=False)

from utils.logger_utils import configure_project_logging  # noqa: E402

configure_project_logging()


def _mock_enabled() -> bool:
    return os.getenv("MOCK_LLM", "0") == "1" or not os.getenv("DASHSCOPE_API_KEY", "")


async def run_cli(question: str):
    thread_id = f"cli-{uuid.uuid4().hex[:8]}"
    session_dir = PROJECT_ROOT / "output" / f"session_cli_{thread_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    if _mock_enabled():
        from agent.mock_runtime import run_mock_agent

        runner = run_mock_agent(str(session_dir), thread_id, question)
    else:
        from agent.llm import model
        from agent.main_agent import build_main_agent, run_deep_agent

        agent = await build_main_agent(model)
        runner = run_deep_agent(agent, str(session_dir), thread_id, question)

    print(f"会话目录: {session_dir}\n{'-' * 60}")
    async for event in runner:
        if event["type"] == "assistant_call":
            print(f"▶ 委派助手: {event['name']}")
        elif event["type"] == "tool_call":
            print(f"  · 工具: {event['name']}")
        elif event["type"] == "task_result":
            print(f"{'-' * 60}\n✅ 完成:\n{event.get('content', '')[:600]}")


async def run_eval():
    from eval.run_eval import run_evaluation

    await run_evaluation()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "server":
        import uvicorn

        uvicorn.run("api.server:app", host="0.0.0.0", port=8000, log_level="info")
    elif cmd == "demo":
        asyncio.run(run_cli("调研智能音箱行业的竞品格局，结合我们的销售数据出一份调研报告"))
    elif cmd == "cli":
        question = sys.argv[2] if len(sys.argv) > 2 else "智能音箱行业有哪些新动向？"
        asyncio.run(run_cli(question))
    elif cmd == "eval":
        asyncio.run(run_eval())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
