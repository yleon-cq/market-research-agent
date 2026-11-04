"""统一路径解析：清洗 LLM 幻觉路径，保证所有文件操作落在会话目录内。

大模型经常幻觉出 /workspace、/mnt/data 这类"训练语料里常见"的虚拟路径，
也可能把文件写到会话目录之外。resolve_path 统一处理：
1. 清洗虚拟路径前缀（/workspace、/mnt/data、/home/user）
2. upload/ 重定向：上传文件始终解析到项目 upload/ 目录
3. 会话目录防嵌套（session_x/session_x）
4. 相对路径一律拼接到会话目录
"""
import os
from pathlib import Path
from typing import Optional

VIRTUAL_PREFIXES = ["/workspace", "/mnt/data", "/home/user", "/tmp"]


def resolve_path(filename: str, session_dir: Optional[str] = None) -> str:
    """解析文件路径为安全的绝对路径。

    Args:
        filename: LLM 给出的文件名或路径
        session_dir: 当前会话工作目录（绝对路径），为 None 时按 CWD 解析
    """
    path_str = str(filename).replace("\\", "/").strip()

    # 1. 虚拟路径前缀清洗
    for prefix in VIRTUAL_PREFIXES:
        if path_str.startswith(prefix + "/") or path_str == prefix:
            path_str = path_str[len(prefix):].lstrip("/")
            break

    # 2. upload/ 重定向：包含 upload/ 段时，取 upload/ 起的后缀相对 CWD 解析
    if "upload/" in path_str:
        idx = path_str.find("upload/")
        return str(Path(path_str[idx:]).resolve())

    if not session_dir:
        return str(Path(path_str).resolve())

    session_path = Path(session_dir).resolve()
    session_name = session_path.name
    path = Path(path_str)

    is_unix_abs = path_str.startswith("/")

    # 3. 绝对路径：校验是否落在会话目录内
    if path.is_absolute() or (os.name == "nt" and is_unix_abs and not path.drive):
        if os.name == "nt" and is_unix_abs and not path.drive:
            full_path = session_path / path_str.lstrip("/")
        else:
            full_path = path.resolve()

        try:
            if session_path in full_path.parents or full_path == session_path:
                # 3.1 防嵌套：session_x/session_x/file -> session_x/file
                parts = full_path.parts
                for i in range(len(parts) - 1):
                    if parts[i] == session_name and parts[i + 1] == session_name:
                        return str(session_path / full_path.name)
                return str(full_path)
        except (OSError, ValueError):
            pass
        # 会话外的绝对路径保持原样（由调用方做最终校验）
        return str(full_path)

    # 4. 相对路径：防嵌套 / 去 output 前缀 / 拼接会话目录
    parts = path.parts
    if session_name in parts:
        return str(session_path / path.name)
    if parts and parts[0] == "output":
        return str(session_path / path.name)
    return str(session_path / path)
