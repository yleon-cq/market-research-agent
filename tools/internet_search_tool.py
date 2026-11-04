"""联网搜索工具（Tavily）。未配置 key 时返回友好提示，不阻断任务。"""
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient

from api.monitor import monitor
from utils.logger_utils import logger

load_dotenv()

_tavily_client = None


def _get_client():
    global _tavily_client
    if _tavily_client is None:
        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            return None
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


@tool
def internet_search(
    query: str,
    topic: Literal["general", "news", "finance"] = "general",
    max_results: int = 5,
    include_raw_content: bool = False,
) -> str:
    """联网搜索工具：查询互联网公开信息（行业动态、竞品公开新闻、市场数据）。

    Args:
        query: 搜索关键词
        topic: general=综合 / news=新闻 / finance=财经
        max_results: 返回条数（默认 5）
        include_raw_content: 是否返回网页正文全文
    """
    logger.debug("internet_search: %s (topic=%s)", query, topic)
    monitor.report_tool("网络搜索工具", {"query": query, "topic": topic})

    client = _get_client()
    if client is None:
        return (
            "TAVILY_API_KEY 未配置，无法联网检索。"
            "请改用其他信息源（数据库/知识库/MCP 情报），或在最终报告中注明该部分缺失。"
        )

    try:
        result = client.search(
            query=query,
            topic=topic,
            max_results=max_results,
            include_raw_content=include_raw_content,
        )
        lines = []
        for i, item in enumerate(result.get("results", []), 1):
            title = item.get("title", "")
            url = item.get("url", "")
            content = (item.get("content") or "")[:500]
            lines.append(f"[{i}] {title}\nURL: {url}\n摘要: {content}")
        return "\n\n".join(lines) if lines else "未检索到相关结果。"
    except Exception as e:
        return f"网络搜索失败: {e}"
