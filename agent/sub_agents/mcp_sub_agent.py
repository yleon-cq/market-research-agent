"""MCP 市场情报子智能体。

通过 langchain-mcp-adapters 以 stdio 方式拉起 mcp_server/market_mcp_server.py，
动态发现工具——Agent 不 import 情报服务的任何代码，只依赖 MCP 协议。
mcp / langchain-mcp-adapters 未安装或 ENABLE_MCP=0 时优雅降级（子智能体不注册）。
"""
import os
from pathlib import Path

from utils.logger_utils import logger

_project_root = Path(__file__).parents[2].resolve()


def mcp_enabled() -> bool:
    return (
        os.getenv("ENABLE_MCP", "1") == "1"
        and os.getenv("MOCK_LLM", "0") != "1"
    )


def _wrap_with_monitor(async_tool):
    """包装 MCP 工具：上报执行轨迹（监控推送 + 评测记录），再透传调用。"""
    from langchain_core.tools import StructuredTool

    async def _call(**kwargs) -> str:
        from api.monitor import monitor

        monitor.report_tool(f"MCP工具:{async_tool.name}", kwargs)
        result = await async_tool.ainvoke(kwargs)
        # MCP 返回内容块列表时提取纯文本，便于 LLM 阅读
        if isinstance(result, list):
            result = "\n".join(
                b.get("text", "") for b in result if isinstance(b, dict) and b.get("text")
            )
        return result

    return StructuredTool(
        name=f"mcp_{async_tool.name}",
        description=f"[MCP] {async_tool.description}",
        coroutine=_call,
        args_schema=async_tool.args_schema,
    )


async def get_mcp_tools() -> list:
    """连接 MCP server 并返回包装后的工具列表；失败返回空列表。"""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters 未安装，MCP 子智能体跳过（pip install langchain-mcp-adapters）")
        return []

    server_path = _project_root / "mcp_server" / "market_mcp_server.py"
    client = MultiServerMCPClient(
        {
            "market_intel": {
                "command": "python",
                "args": [str(server_path)],
                "transport": "stdio",
            }
        }
    )
    try:
        raw_tools = await client.get_tools()
        wrapped = [_wrap_with_monitor(t) for t in raw_tools]
        logger.info("MCP 工具发现成功: %s", [t.name for t in wrapped])
        return wrapped
    except Exception as e:
        logger.warning("MCP 连接失败，市场情报助手跳过: %s", e)
        return []


async def build_mcp_sub_agent() -> dict | None:
    """组装 MCP 子智能体；工具不可用时返回 None。"""
    if not mcp_enabled():
        logger.info("ENABLE_MCP=0 或 MOCK_LLM=1，MCP 子智能体关闭")
        return None
    tools = await get_mcp_tools()
    if not tools:
        return None
    from agent.load_prompt import sub_agents_config

    cfg = sub_agents_config["mcp"]
    return {
        "name": cfg["name"],
        "description": cfg["description"],
        "system_prompt": cfg["system_prompt"],
        "tools": tools,
    }
