"""Markdown -> PDF 转换（跨平台降级设计）。

优先级：
1. Windows + Microsoft Word：md 先转 docx，再由 Word COM 导出 PDF（排版最好）
2. 降级：生成带打印样式的 HTML（浏览器打开即可"打印为 PDF"）

为什么不用 weasyprint？它在 Windows 依赖 GTK 运行库，安装失败率高；
本项目的取舍是：Windows 一键 PDF，其他平台 HTML 保底，转换链路永不阻塞任务。
"""
import os
import platform
import re
from pathlib import Path

from langchain_core.tools import tool

from api.context import get_session_context
from api.monitor import monitor
from utils.logger_utils import logger
from utils.path_utils import resolve_path

from tools.markdown_tools import _safe_session_path


def _md_to_docx(md_path: Path, docx_path: Path) -> bool:
    """轻量 Markdown->docx：标题/列表/粗体/段落。"""
    import docx
    from docx.shared import Pt

    doc = docx.Document()
    text = md_path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            doc.add_heading(m.group(2).strip(), level=len(m.group(1)))
            continue
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            doc.add_paragraph(_strip_inline(m.group(1)), style="List Bullet")
            continue
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            doc.add_paragraph(_strip_inline(m.group(1)), style="List Number")
            continue
        if line.strip().startswith(("|", "```")):
            continue  # 表格/代码块简化处理
        doc.add_paragraph(_strip_inline(line))
    # 正文字号统一
    for p in doc.paragraphs:
        for run in p.runs:
            run.font.size = Pt(11)
    doc.save(str(docx_path))
    return True


def _strip_inline(s: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s).replace("`", "")


def _docx_to_pdf_via_word(docx_path: Path, pdf_path: Path) -> bool:
    """Windows + Word COM 导出 PDF。"""
    if platform.system() != "Windows":
        return False
    try:
        import win32com.client  # pywin32

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(docx_path.resolve()))
            doc.SaveAs(str(pdf_path.resolve()), FileFormat=17)  # wdFormatPDF
            doc.Close(False)
            return True
        finally:
            word.Quit()
    except Exception as e:
        logger.warning("Word COM 转换失败（%s），降级为 HTML 输出", e)
        return False


def _md_to_printable_html(md_path: Path, html_path: Path) -> None:
    """降级方案：生成带打印样式的 HTML。"""
    import markdown as md_lib

    body = md_lib.markdown(
        md_path.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"]
    )
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>{md_path.stem}</title><style>
body{{font-family:"Microsoft YaHei",sans-serif;max-width:800px;margin:0 auto;padding:40px;line-height:1.7;color:#222}}
h1{{border-bottom:2px solid #2c5aa0;padding-bottom:8px}} table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #999;padding:6px 10px}} th{{background:#f0f4fa}}
@media print{{body{{padding:0}}}}</style></head><body>{body}</body></html>"""
    html_path.write_text(html, encoding="utf-8")


@tool
def convert_md_to_pdf(md_filename: str) -> str:
    """将已生成的 Markdown 文件转换为 PDF（无 Word 环境时自动降级为 HTML）。

    Args:
        md_filename: 会话目录内已存在的 Markdown 文件名
    """
    monitor.report_tool("PDF转换工具", {"md_filename": md_filename})
    try:
        session_dir = get_session_context()
        md_path = Path(resolve_path(md_filename, session_dir)).resolve()
        if not md_path.exists():
            return f"Markdown 文件不存在: {md_filename}，请先用 generate_markdown 生成。"

        base = md_path.with_suffix("")
        docx_path = base.with_suffix(".docx")
        pdf_path = base.with_suffix(".pdf")

        if os.getenv("MOCK_LLM", "0") != "1":
            _md_to_docx(md_path, docx_path)
            if _docx_to_pdf_via_word(docx_path, pdf_path):
                docx_path.unlink(missing_ok=True)
                return f"PDF 已成功生成: {pdf_path.name}"

        html_path = base.with_suffix(".html")
        _md_to_printable_html(md_path, html_path)
        return (
            f"当前环境无 Word，已生成打印版 HTML: {html_path.name}"
            "（浏览器打开后 Ctrl+P 可另存为 PDF）"
        )
    except Exception as e:
        return f"转换失败: {e}"
