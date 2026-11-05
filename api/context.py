"""基于 ContextVars 的协程级会话隔离。

为什么不用全局变量 / threading.local？
- asyncio 并发请求跑在同一个线程里：全局变量会"串台"（A 的文件写进 B 的目录）；
  threading.local 按线程隔离，在异步场景下失效。
- ContextVar 是协程级隔离：每个 asyncio Task 拥有独立上下文，
  任意深层的工具函数都能取到当前请求的 thread_id 与会话目录，
  任务结束后在 finally 中 reset，防止线程池复用导致上下文污染。
"""
from contextvars import ContextVar
from typing import Optional

_session_dir_ctx: ContextVar[Optional[str]] = ContextVar("session_dir", default=None)
_thread_id_ctx: ContextVar[Optional[str]] = ContextVar("thread_id", default=None)


def set_session_context(path: str):
    """绑定当前请求链路的工作目录，返回 token 供 finally 中 reset。"""
    return _session_dir_ctx.set(path)


def get_session_context() -> Optional[str]:
    return _session_dir_ctx.get()


def set_thread_context(thread_id: str):
    """绑定当前请求链路的 thread_id（WebSocket 定向推送依赖它）。"""
    return _thread_id_ctx.set(thread_id)


def get_thread_context() -> Optional[str]:
    return _thread_id_ctx.get()


def reset_session_context(session_token, thread_token=None):
    _session_dir_ctx.reset(session_token)
    if thread_token:
        _thread_id_ctx.reset(thread_token)
