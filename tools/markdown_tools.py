"""Markdown 报告生成工具：所有产物强制落在会话工作目录内。"""
from pathlib import Path

from langchain_core.tools import tool

from agent.load_prompt import core_tools_config
from api.context import get_session_context
from api.monitor import monitor
from utils.logger_utils import logger
from utils.path_utils import resolve_path


def _safe_session_path(filename: str) -> Path:
    """解析并校验路径必须落在会话目录内（防止 LLM 传绝对路径逃逸）。"""
    session_dir = get_session_context()
    full_path = Path(resolve_path(filename, session_dir)).resolve()
    if session_dir:
        session_root = Path(session_dir).resolve()
        if session_root != full_path and session_root not in full_path.parents:
            raise ValueError(
                f"路径越权: {filename} 不在当前会话工作目录内，请在会话目录内操作。"
            )
    return full_path


@tool
def generate_markdown(filename: str, content: str) -> str:
    """生成 Markdown 文件并保存到当前任务工作目录。

    Args:
        filename: 文件名（如 report.md），不要携带目录前缀
        content: 完整的 Markdown 内容
    """
    monitor.report_tool("Markdown生成工具", {"filename": filename})
    try:
        file_path = _safe_session_path(filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info("Markdown 已生成: %s", file_path)
        return f"Markdown 文件已成功生成并保存: {filename}（{len(content)} 字符）"
    except Exception as e:
        return f"生成 Markdown 失败: {e}"


def read_uploaded_file(filename: str) -> str:
    """读取 upload/ 目录下的上传文件（文本类直接读，表格类转文本）。"""
    from utils.path_utils import resolve_path as _rp

    path = Path(_rp(filename)).resolve()
    if not path.exists():
        return f"文件不存在: {filename}"
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".csv", ".log", ".json"):
        return path.read_text(encoding="utf-8", errors="replace")[:20000]
    if suffix in (".xlsx", ".xls"):
        import pandas as pd

        df = pd.read_excel(path, sheet_name=0, nrows=100)
        return df.to_csv(index=False)
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:30])
    return f"暂不支持的文件类型: {suffix}（支持 txt/md/csv/json/xlsx/pdf）"


@tool
def upload_file_read(filename: str) -> str:
    """读取用户上传的文件内容。

    Args:
        filename: 上传文件的文件名（直接用文件名，不要带目录）
    """
    monitor.report_tool("上传文件读取工具", {"filename": filename})
    instruction = core_tools_config.get("file_read_instruction", "").strip()
    try:
        content = read_uploaded_file(filename)
        return f"{instruction}\n\n{content}" if instruction else content
    except Exception as e:
        return f"读取文件失败: {e}"
