"""SQLite 查询工具（只读，双重防护）。

防失控设计（面试重点）：
1. 工具层 SQL 白名单拦截：仅放行 SELECT / SHOW / EXPLAIN / WITH 开头的语句，
   从源头拦截 UPDATE/DELETE/DROP/ALTER 等写操作，不依赖提示词自觉。
2. 连接层只读模式：sqlite3.connect(uri, mode=ro)，即使白名单被绕过，
   数据库本身也无法被修改。
"""
import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import tool

from api.monitor import monitor
from utils.logger_utils import logger
from utils.sql_guard import validate_readonly_sql

load_dotenv()

# 数据库文件路径（项目根相对，环境变量可覆盖）
def get_db_path() -> str:
    project_root = Path(__file__).parents[1].resolve()
    db_path = os.getenv("SQLITE_DB_PATH", "data/demo_market.db")
    return str((project_root / db_path).resolve())


def _rows_to_text(cursor: sqlite3.Cursor, rows: list) -> str:
    header = ",".join(col[0] for col in cursor.description) if cursor.description else ""
    data = "\n".join(",".join(map(str, r)) for r in rows)
    return f"{header}\n{data}" if header else "（无数据）"


def _run_query(sql: str) -> str:
    db_path = get_db_path()
    if not Path(db_path).exists():
        return f"数据库文件不存在: {db_path}，请先运行 python data/init_demo_db.py"
    try:
        # mode=ro：连接级只读，双保险
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cursor = conn.execute(sql)
            rows = cursor.fetchmany(200)
            return _rows_to_text(cursor, rows)
        finally:
            conn.close()
    except sqlite3.Error as e:
        return f"SQL 执行失败: {e}"


@tool
def list_sql_tables() -> str:
    """列出数据库中所有可用表名（了解数据结构的第一步）。"""
    monitor.report_tool("列出数据表工具")
    violation = validate_readonly_sql("SELECT name FROM sqlite_master WHERE type='table'")
    if violation:
        return violation
    try:
        conn = sqlite3.connect(f"file:{get_db_path()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if not rows:
                return "没有可用表"
            return "可用表: " + ", ".join(r[0] for r in rows)
        finally:
            conn.close()
    except sqlite3.Error as e:
        return f"数据库连接失败: {e}"


@tool
def get_table_data(table_name: str) -> str:
    """预览指定表的前 50 行数据，用于理解字段含义与取值格式。

    Args:
        table_name: 表名（先用 list_sql_tables 确认）
    """
    monitor.report_tool("表数据预览工具", {"table_name": table_name})
    if not re.fullmatch(r"[\w\u4e00-\u9fa5]+", table_name):
        return "拒绝执行：表名只能包含字母/数字/下划线/中文。"
    return _run_query(f"SELECT * FROM {table_name} LIMIT 50")


@tool
def execute_sql_query(sql: str) -> str:
    """执行自定义只读 SQL 查询（仅允许 SELECT，复杂筛选/聚合/联接时使用）。

    Args:
        sql: 完整的 SELECT 查询语句
    """
    monitor.report_tool("自定义SQL查询工具", {"sql": sql})
    logger.debug("execute_sql_query: %s", sql)
    violation = validate_readonly_sql(sql)
    if violation:
        return violation
    return _run_query(sql)
