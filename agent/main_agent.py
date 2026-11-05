"""主智能体：组装 1 主 N 专多智能体，流式执行并推送过程。"""
import asyncio
import builtins
import datetime
import re
from typing import AsyncGenerator

from agent.load_prompt import main_config
from agent.sub_agents.local_sub_agents import (
    build_db_sub_agent,
    build_docs_sub_agent,
    build_internet_sub_agent,
)
from api.context import (
    get_thread_context,
    reset_session_context,
    set_session_context,
    set_thread_context,
)
from api.monitor import monitor
from eval.trajectory import TrajectoryRecorder
from tools.markdown_tools import generate_markdown, upload_file_read
from tools.pdf_tools import convert_md_to_pdf
from utils.logger_utils import logger

_SUB_AGENT_NAME_MAP = {
    "网络搜索助手": "网络搜索助手",
    "数据库查询助手": "数据库查询助手",
    "知识库检索助手": "知识库检索助手",
    "市场情报助手": "市场情报助手",
}


async def build_main_agent(model):
    """组装主智能体。MCP 子智能体按配置动态注册。"""
    from deepagents import create_deep_agent

    subagents = [build_internet_sub_agent(), build_db_sub_agent(), build_docs_sub_agent()]

    from agent.sub_agents.mcp_sub_agent import build_mcp_sub_agent

    mcp_sub_agent = await build_mcp_sub_agent()
    if mcp_sub_agent:
        subagents.append(mcp_sub_agent)
        logger.info("MCP 子智能体已注册，当前子智能体: %s", [s["name"] for s in subagents])

    return create_deep_agent(
        model=model,
        tools=[generate_markdown, convert_md_to_pdf, upload_file_read],
        system_prompt=main_config["system_prompt"],
        subagents=subagents,
    )


def _extract_tool_calls(update: dict) -> list[tuple[str, dict]]:
    """从 langgraph update 中提取本轮 (工具名, 参数)。"""
    calls: list[tuple[str, dict]] = []
    for node_payload in update.values():
        messages = (node_payload or {}).get("messages", []) if isinstance(node_payload, dict) else []
        for msg in messages:
            for tc in getattr(msg, "tool_calls", None) or []:
                calls.append((tc.get("name", ""), tc.get("args", {}) or {}))
    return calls


async def run_deep_agent(
    agent,
    session_dir: str,
    thread_id: str,
    user_message: str,
) -> AsyncGenerator[dict, None]:
    """流式执行主智能体：推送过程事件 + 记录轨迹。"""
    recorder = TrajectoryRecorder(thread_id)
    session_token = set_session_context(session_dir)
    thread_token = set_thread_context(thread_id)
    monitor.report_session_dir(session_dir)

    injected = (
        f"{user_message}\n\n"
        f"【工作环境指令】本次任务的工作目录为: {session_dir}\n"
        f"所有文件的生成与读取都必须在该目录内完成，并把该路径告知你调用的助手。"
    )

    try:
        final_text = ""
        async for update in agent.astream(
            {"messages": [("user", injected)]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="updates",
        ):
            for tool_name, args in _extract_tool_calls(update):
                if tool_name == "task":
                    assistant = args.get("description") or args.get("subagent_type") or "子智能体"
                    monitor.report_assistant(assistant, args)
                    recorder.record("assistant_call", assistant, {"args_keys": list(args.keys())})
                    yield {"type": "assistant_call", "name": assistant}
                else:
                    recorder.record("tool_call", tool_name, {"args": str(args)[:200]})
                    yield {"type": "tool_call", "name": tool_name}
                if "sql" in tool_name.lower():
                    pass

            messages = None
            for node_payload in update.values():
                if isinstance(node_payload, dict) and "messages" in node_payload:
                    messages = node_payload["messages"]
            if messages:
                for msg in messages:
                    content = getattr(msg, "content", "")
                    if isinstance(content, str) and content and getattr(msg, "tool_calls", None) is None:
                        final_text = content

        recorder.record("task_result", "done")
        monitor.report_task_result(final_text[:500])
        yield {"type": "task_result", "content": final_text}
    finally:
        reset_session_context(session_token, thread_token)


def is_sql_blocked_text(text: str) -> bool:
    """辅助判断工具输出是否为 SQL 只读拦截（评测安全指标用）。"""
    return bool(re.search(r"拒绝执行", text or ""))
