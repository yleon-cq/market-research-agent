"""内部知识库检索工具：对 KNOWLEDGE_DOCS_DIR 下的 md/txt 文档做关键词检索。

轻量实现（分词打分，无外部依赖）。生产可替换为 RAGFlow / 向量检索，
接口不变——子智能体无需感知检索引擎差异。
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import tool

from api.monitor import monitor

load_dotenv()

_SPLIT_RE = re.compile(r"[\s，。；、！？：""''（）\[\]{}<>]+")


def get_docs_dir() -> Path:
    project_root = Path(__file__).parents[1].resolve()
    docs_dir = os.getenv("KNOWLEDGE_DOCS_DIR", "data/knowledge_docs")
    return (project_root / docs_dir).resolve()


def _score_document(text: str, keywords: list[str]) -> tuple[int, list[str]]:
    """简单相关性打分：关键词命中次数求和，并截取命中上下文。"""
    score = 0
    snippets = []
    lowered = text.lower()
    for kw in keywords:
        kw = kw.strip().lower()
        if not kw:
            continue
        count = lowered.count(kw)
        if count:
            score += count
            pos = lowered.find(kw)
            start = max(0, pos - 40)
            snippets.append(f"...{text[start:pos + len(kw) + 60]}...")
    return score, snippets


@tool
def search_knowledge_docs(keywords: str, top_k: int = 3) -> str:
    """在内部知识库文档中按关键词检索（支持逗号分隔多关键词）。

    Args:
        keywords: 关键词，多个用逗号分隔（如 "X3, 调研, 定价"）
        top_k: 返回最相关的文档数（默认 3）
    """
    monitor.report_tool("知识库检索工具", {"keywords": keywords})
    docs_dir = get_docs_dir()
    if not docs_dir.exists():
        return f"知识库目录不存在: {docs_dir}"

    keywords = [k for k in keywords.replace("，", ",").split(",") if k.strip()]
    scored = []
    for doc_path in sorted(docs_dir.rglob("*")):
        if doc_path.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            text = doc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        score, snippets = _score_document(text, keywords)
        if score > 0:
            scored.append((score, doc_path.name, snippets))

    if not scored:
        return "知识库中未找到与关键词相关的文档。"

    scored.sort(key=lambda x: -x[0])
    parts = [f"共命中 {len(scored)} 份文档，返回最相关 {min(top_k, len(scored))} 份："]
    for score, name, snippets in scored[:top_k]:
        parts.append(f"\n### 出处: {name}（命中 {score} 次）")
        parts.extend(snippets[:4])
    return "\n".join(parts)
