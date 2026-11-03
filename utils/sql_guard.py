"""SQL 只读校验（纯逻辑，无框架依赖，便于单测与 CI）。

策略：
1. 首关键字白名单：仅放行 SELECT / WITH / EXPLAIN / SHOW
2. 危险关键字兜底：语句任何位置出现写操作关键字即拒绝（防 CTE 夹带）
3. 单语句限制：拒绝分号堆叠（防 "SELECT 1; DROP TABLE x"）
"""
import re

_READ_ONLY_PATTERN = re.compile(
    r"^\s*(select|with|explain|show|pragma\s+table_info|pragma\s+table_list)\b",
    re.IGNORECASE,
)
_FORBIDDEN_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|vacuum|reindex)\b",
    re.IGNORECASE,
)


def validate_readonly_sql(sql: str) -> str | None:
    """校验 SQL 只读合法性；非法时返回原因，合法返回 None。"""
    if not sql or not sql.strip():
        return "拒绝执行：SQL 语句为空。"
    if _FORBIDDEN_PATTERN.search(sql):
        return "拒绝执行：检测到写操作关键字，本工具仅允许只读查询（SELECT）。"
    if not _READ_ONLY_PATTERN.match(sql):
        return "拒绝执行：仅允许 SELECT / WITH / EXPLAIN 开头的只读查询。"
    stripped = sql.rstrip().rstrip(";")
    if ";" in stripped:
        return "拒绝执行：一次只允许执行一条查询语句。"
    return None
