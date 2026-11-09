"""演示运行时（MOCK_LLM=1）：跳过 LLM 推理，按预置轨迹真实调用工具。

设计动机：让"没有 API Key 也能完整体验链路"——数据库查询、知识库检索、
MCP 情报调用、报告落盘全部真实发生，只有"下一步做什么"的决策是预置的。
这也是评测模块的安全回放基础：轨迹格式与真实运行完全一致。
"""
import datetime
import uuid
from pathlib import Path

from api.context import (
    reset_session_context,
    set_session_context,
    set_thread_context,
)
from api.monitor import monitor
from eval.trajectory import TrajectoryRecorder
from tools.docs_tools import search_knowledge_docs
from tools.internet_search_tool import internet_search
from tools.markdown_tools import generate_markdown
from tools.pdf_tools import convert_md_to_pdf
from tools.sqlite_tools import execute_sql_query, list_sql_tables


def _log_tool(recorder: TrajectoryRecorder, name: str, result: str) -> str:
    """记录工具调用轨迹（评测指标的数据来源）。"""
    recorder.record("tool_call", name)
    return result


async def run_mock_agent(session_dir: str, thread_id: str, user_message: str):
    """预置轨迹执行：委派 4 助手 → 汇总 → 生成报告。"""
    recorder = TrajectoryRecorder(thread_id)
    session_token = set_session_context(session_dir)
    thread_token = set_thread_context(thread_id)
    monitor.report_session_dir(session_dir)

    try:
        # 1) 数据库助手：真实查询 SQLite
        monitor.report_assistant("数据库查询助手")
        recorder.record("assistant_call", "数据库查询助手")
        yield {"type": "assistant_call", "name": "数据库查询助手"}

        tables = _log_tool(recorder, "list_sql_tables", list_sql_tables.invoke({}))
        yield {"type": "tool_call", "name": "list_sql_tables"}

        sales_sql = (
            "SELECT p.product_name, p.brand, SUM(s.quantity) AS total_qty, "
            "ROUND(SUM(s.quantity * s.unit_price), 2) AS revenue "
            "FROM sales_records s JOIN products p ON p.product_id = s.product_id "
            "GROUP BY p.product_id ORDER BY revenue DESC LIMIT 5"
        )
        sales = _log_tool(recorder, "execute_sql_query", execute_sql_query.invoke({"sql": sales_sql}))
        yield {"type": "tool_call", "name": "execute_sql_query"}

        competitor_sql = (
            "SELECT p.product_name, p.brand, p.price, "
            "ROUND(AVG(sr.rating), 2) AS avg_rating, SUM(sr.quantity) AS total_qty "
            "FROM products p LEFT JOIN sales_records sr ON p.product_id = sr.product_id "
            "GROUP BY p.product_id ORDER BY total_qty DESC"
        )
        competitors = _log_tool(recorder, "execute_sql_query", execute_sql_query.invoke({"sql": competitor_sql}))
        yield {"type": "tool_call", "name": "execute_sql_query"}

        # 2) 知识库助手：真实检索本地文档
        monitor.report_assistant("知识库检索助手")
        recorder.record("assistant_call", "知识库检索助手")
        yield {"type": "assistant_call", "name": "知识库检索助手"}

        docs = _log_tool(recorder, "search_knowledge_docs", search_knowledge_docs.invoke({"keywords": "竞品, 调研, 价格"}))
        yield {"type": "tool_call", "name": "search_knowledge_docs"}

        # 3) 市场情报助手：MCP 真实调用（未启用则跳过）
        mcp_lines = ""
        try:
            from agent.sub_agents.mcp_sub_agent import get_mcp_tools

            mcp_tools = await get_mcp_tools()
            if mcp_tools:
                monitor.report_assistant("市场情报助手")
                recorder.record("assistant_call", "市场情报助手")
                yield {"type": "assistant_call", "name": "市场情报助手"}

                by_name = {t.name: t for t in mcp_tools}
                for tool_name, kw in [
                    ("mcp_get_industry_events", {}),
                    ("mcp_get_competitor_sentiment", {"competitor": "声浪科技"}),
                ]:
                    if tool_name in by_name:
                        out = await by_name[tool_name].ainvoke(kw)
                        mcp_lines += f"\n{out}"
                        _log_tool(recorder, tool_name, str(out))
                        yield {"type": "tool_call", "name": tool_name}
        except Exception as exc:  # MCP 可选，失败不阻断
            recorder.record("tool_call", "mcp_skipped", {"reason": str(exc)})

        # 4) 网络搜索助手（Tavily 可选）
        monitor.report_assistant("网络搜索助手")
        recorder.record("assistant_call", "网络搜索助手")
        yield {"type": "assistant_call", "name": "网络搜索助手"}

        web = _log_tool(recorder, "internet_search", internet_search.invoke({"query": "智能音箱 行业报告 市场规模 2026"}))
        yield {"type": "tool_call", "name": "internet_search"}

        # 5) 生成报告（模板汇总真实工具输出）
        monitor.report_assistant("报告生成")
        yield {"type": "assistant_call", "name": "报告生成"}

        today = datetime.date.today().isoformat()
        report = f"""# 智能音箱行业竞品调研报告（演示模式）

> 生成时间：{today} ｜ 模式：MOCK_LLM（预置决策轨迹，工具调用真实执行）

## 一、任务规划
- [x] 查询内部销售与竞品明细（数据库）
- [x] 检索内部调研纪要与定价结论（知识库）
- [x] 获取竞品舆情与行业事件（MCP 市场情报）
- [x] 补充公开市场信息（网络搜索）
- [x] 汇总生成调研报告并导出

## 二、内部数据视角（来自数据库真实查询）

**本公司各型号销量/收入 TOP5：**

```
{sales}
```

**竞品对比（销量、均价、评分）：**

```
{competitors}
```

## 三、内部文档结论（来自知识库真实检索）

```
{docs[:1200]}
```

## 四、外部情报

### MCP 市场情报
{mcp_lines or "（MCP 未启用，跳过）"}

### 网络公开信息
```
{web[:800]}
```

## 五、结论与建议
1. 内部数据显示收入集中在头部两个型号，中长尾型号存在 SKU 瘦身空间。
2. 竞品近期在高端段发力（评分与声量双高），建议跟进下一代降噪方案立项。
3. 行业端侧大模型交互成本下降，为下半年价格战预留了降本空间。

---
*本报告由 market-research-agent 演示模式生成，决策轨迹预置、数据真实查询。*
"""
        _log_tool(recorder, "generate_markdown", generate_markdown.invoke({"filename": "竞品调研报告.md", "content": report}))
        yield {"type": "tool_call", "name": "generate_markdown"}

        _log_tool(recorder, "convert_md_to_pdf", convert_md_to_pdf.invoke({"md_filename": "竞品调研报告.md"}))
        recorder.record("file_output", "report", {"file": "竞品调研报告.md"})
        yield {"type": "tool_call", "name": "convert_md_to_pdf"}

        final_text = "竞品调研报告已生成完毕。包含任务规划、内部数据、文档结论与外部情报四部分。"
        recorder.record("task_result", "done")
        monitor.report_task_result(final_text[:500])
        yield {"type": "task_result", "content": final_text}
    finally:
        reset_session_context(session_token, thread_token)


def new_thread_id() -> str:
    return f"mock-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
