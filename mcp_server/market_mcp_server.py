"""市场情报 MCP Server（stdio 模式）。

通过 MCP 协议向 Agent 暴露两个情报工具。Agent 侧无需 import 本模块，
只通过协议发现与调用工具——这就是 MCP 的价值：工具与 Agent 解耦，
情报源可以独立演进（换真实舆情 API 时 Agent 零改动）。

启动：python mcp_server/market_mcp_server.py （由 MCP 客户端以 stdio 拉起）
"""
import random
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("market-intel")

# ---- 内置演示数据集（生产环境替换为真实舆情 API / 数据库） ----
_COMPETITOR_SENTIMENTS = {
    "声浪科技": [
        ("新品 X5 Pro 发布，评测普遍好评", 85, "positive"),
        ("部分用户反馈固件升级后断连", -40, "negative"),
        ("官宣降价 200 元，讨论度高", 60, "neutral"),
    ],
    "聆悦电子": [
        ("高端型号口碑下滑，退货率上升传闻", -55, "negative"),
        ("签约知名代言人，社媒声量上涨", 45, "positive"),
    ],
    "极目智能": [
        ("开放 API 生态，开发者社区活跃", 70, "positive"),
        ("被曝供应链产能吃紧", -30, "negative"),
    ],
    "our_company": [
        ("产品稳定性好评居多", 50, "positive"),
        ("售后响应速度被部分用户吐槽", -25, "negative"),
    ],
}

_INDUSTRY_EVENTS = [
    ("2026-09-12", "政策", "行业协会发布智能音频设备新能效标准，10 月起实施"),
    ("2026-09-28", "市场", "第三方机构上调全年智能音箱出货量预期至 +18%"),
    ("2026-10-15", "竞品", "声浪科技发布 X5 Pro，主打 AI 降噪与长续航"),
    ("2026-10-22", "渠道", "主流电商平台启动双 11 预售，头部品牌集中投放资源"),
    ("2026-10-29", "技术", "端侧大模型语音交互方案成本首次降至 30 元以内"),
]


@mcp.tool()
def get_competitor_sentiment(competitor: str, days: int = 30) -> str:
    """查询指定竞品近 N 天的舆情热度摘要。

    Args:
        competitor: 竞品公司名（如：声浪科技 / 聆悦电子 / 极目智能）
        days: 回溯天数（默认 30）
    """
    data = _COMPETITOR_SENTIMENTS.get(competitor.strip())
    if not data:
        known = ", ".join(k for k in _COMPETITOR_SENTIMENTS if k != "our_company")
        return f"未收录该公司「{competitor}」的舆情数据。已收录：{known}"
    base = datetime.now() - timedelta(days=days)
    lines = [f"【{competitor}】近 {days} 天舆情摘要（共 {len(data)} 条）："]
    for i, (title, heat, polarity) in enumerate(data, 1):
        day = (base + timedelta(days=i * 5)).strftime("%m-%d")
        lines.append(f"[{day}] 热度 {heat:+d}（{polarity}）{title}")
    avg = sum(d[1] for d in data) / len(data)
    lines.append(f"整体舆情倾向: {'偏正面' if avg > 20 else '偏负面' if avg < -20 else '中性'}（均值 {avg:+.0f}）")
    return "\n".join(lines)


@mcp.tool()
def get_industry_events(days: int = 60) -> str:
    """查询近 N 天行业事件时间线（政策/市场/竞品/技术）。

    Args:
        days: 回溯天数（默认 60）
    """
    cutoff = datetime.now() - timedelta(days=days)
    lines = [f"近 {days} 天行业事件（共 {len(_INDUSTRY_EVENTS)} 条）："]
    for date_str, category, desc in _INDUSTRY_EVENTS:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt >= cutoff:
            lines.append(f"[{date_str}] ({category}) {desc}")
    return "\n".join(lines)


@mcp.tool()
def ping() -> str:
    """健康检查。"""
    return f"market-intel MCP server OK @ {datetime.now().isoformat()}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
