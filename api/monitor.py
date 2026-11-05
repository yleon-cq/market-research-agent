"""工具执行监控：Agent 过程事件 -> WebSocket 定向推送 / 控制台日志。

ToolMonitor 为单例：任何工具内部 `from api.monitor import monitor` 即可上报，
无需层层传参。事件按 thread_id 定向推送给对应浏览器会话。
"""
import asyncio
import builtins
import datetime
import logging
from typing import Any, Dict, Optional

from api.context import get_thread_context

logger = logging.getLogger(__name__)


class ToolMonitor:
    """单例监控器。兼容 FastAPI WebSocket 与脚本模式（stream_writer）。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.websocket_manager = None
        return cls._instance

    def set_websocket_manager(self, manager):
        self.websocket_manager = manager

    def _emit(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None):
        payload = {
            "type": "monitor_event",
            "event": event_type,
            "message": message,
            "data": data or {},
            "timestamp": datetime.datetime.now().isoformat(),
        }

        # 1) WebSocket 定向推送
        if self.websocket_manager:
            try:
                thread_id = get_thread_context()
                manager_loop = self.websocket_manager.loop
                if manager_loop and thread_id:
                    try:
                        current_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        current_loop = None
                    if current_loop and current_loop == manager_loop:
                        current_loop.create_task(
                            self.websocket_manager.send_to_thread(payload, thread_id)
                        )
                    else:
                        # 跨线程调用必须线程安全地投递回事件循环
                        asyncio.run_coroutine_threadsafe(
                            self.websocket_manager.send_to_thread(payload, thread_id),
                            manager_loop,
                        )
            except Exception as e:  # 推送失败不阻断任务
                logger.warning("[Monitor] WebSocket send failed: %s", e)

        # 2) 脚本模式（MockRuntime / stream_writer）
        if builtins and hasattr(builtins, "runtime") and hasattr(builtins.runtime, "stream_writer"):
            try:
                builtins.runtime.stream_writer(payload)
            except Exception:
                pass

        # 3) 控制台保底
        logger.debug("[Monitor:%s] %s", event_type, message)

    def report_tool(self, tool_name: str, args: Dict[str, Any] = None):
        self._emit("tool_start", f"开始执行工具: {tool_name}", {"tool_name": tool_name, "args": args})

    def report_assistant(self, assistant_name: str, args: Dict[str, Any] = None):
        self._emit("assistant_call", f"正在调用助手: {assistant_name}",
                   {"assistant_name": assistant_name, "args": args})

    def report_task_result(self, result: str):
        self._emit("task_result", "任务执行完成", {"result": result})

    def report_session_dir(self, path: str):
        self._emit("session_created", f"工作目录已创建: {path}", {"path": path})


monitor = ToolMonitor()


class ConnectionManager:
    """WebSocket 连接管理：thread_id -> 连接实例。"""

    def __init__(self):
        self.active_connections: Dict[str, Any] = {}
        self.loop = None

    def set_loop(self, loop):
        """启动时绑定事件循环（跨线程投递依赖它）。"""
        self.loop = loop
        monitor.set_websocket_manager(self)

    async def connect(self, websocket, thread_id: str):
        await websocket.accept()
        self.active_connections[thread_id] = websocket

    def disconnect(self, websocket, thread_id: str):
        self.active_connections.pop(thread_id, None)

    async def send_to_thread(self, message: dict, thread_id: str):
        websocket = self.active_connections.get(thread_id)
        if websocket is not None:
            await websocket.send_json(message)


manager = ConnectionManager()
