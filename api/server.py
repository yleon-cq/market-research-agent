"""FastAPI 服务：任务接口 + WebSocket 过程推送 + 文件上传/下载（含越权校验）。"""
import asyncio
import datetime
import shutil
import uuid
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

from fastapi import FastAPI, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from agent.main_agent import build_main_agent, run_deep_agent
from agent.mock_runtime import run_mock_agent
from api.monitor import manager
from utils.logger_utils import logger

app = FastAPI(title="market-research-agent", version="1.0.0")
PROJECT_ROOT = Path(__file__).parents[1].resolve()
OUTPUT_ROOT = PROJECT_ROOT / "output"
UPLOAD_ROOT = PROJECT_ROOT / "upload"
WEB_DIR = PROJECT_ROOT / "web"

_task_results: dict[str, str] = {}
_shared_agent = None  # 真实模式下复用主智能体（子智能体组装一次，会话隔离靠 ContextVars）


@app.on_event("startup")
async def _startup():
    manager.set_loop(asyncio.get_running_loop())
    OUTPUT_ROOT.mkdir(exist_ok=True)
    UPLOAD_ROOT.mkdir(exist_ok=True)
    import os

    if os.getenv("MOCK_LLM", "0") != "1":
        from agent.llm import model

        if model is None:
            logger.warning("未配置 DASHSCOPE_API_KEY，将以演示模式运行（MOCK_LLM 效果一致）")
            app.state.use_mock = True
        else:
            global _shared_agent
            _shared_agent = await build_main_agent(model)
            app.state.use_mock = False
            logger.info("主智能体组装完成（真实模式）")
    else:
        app.state.use_mock = True


class TaskRequest(BaseModel):
    message: str
    thread_id: str | None = None


def _new_session_dir(thread_id: str) -> Path:
    session_dir = OUTPUT_ROOT / f"session_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{thread_id[:8]}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


async def _execute_task(thread_id: str, message: str):
    session_dir = _new_session_dir(thread_id)
    try:
        if app.state.use_mock:
            runner = run_mock_agent(session_dir, thread_id, message)
        else:
            runner = run_deep_agent(_shared_agent, session_dir, thread_id, message)
        async for event in runner:
            if event["type"] == "task_result":
                _task_results[thread_id] = event.get("content", "")
                await manager.send_to_thread(
                    {"type": "task_result", "message": event.get("content", "")}, thread_id
                )
    except Exception as e:
        logger.exception("任务执行失败: %s", e)
        _task_results[thread_id] = f"任务执行失败: {e}"
        await manager.send_to_thread({"type": "task_result", "message": str(e)}, thread_id)


@app.post("/api/task")
async def create_task(req: TaskRequest):
    thread_id = req.thread_id or f"t-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    asyncio.create_task(_execute_task(thread_id, req.message))
    return {"thread_id": thread_id, "mock": app.state.use_mock}


@app.get("/api/task_result/{thread_id}")
async def task_result(thread_id: str):
    return {"thread_id": thread_id, "result": _task_results.get(thread_id, "")}


@app.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    await manager.connect(websocket, thread_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, thread_id)


@app.post("/api/upload")
async def upload_file(file: UploadFile):
    UPLOAD_ROOT.mkdir(exist_ok=True)
    dest = UPLOAD_ROOT / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": file.filename, "size": dest.stat().st_size}


@app.get("/api/files/{thread_id}")
async def list_files(thread_id: str):
    """列出某会话生成的文件（防止跨会话探测：只按目录名包含 thread_id 前缀匹配）。"""
    results = []
    for session_dir in OUTPUT_ROOT.glob(f"*_{thread_id[:8]}"):
        for f in session_dir.iterdir():
            if f.is_file():
                results.append({"name": f.name, "size": f.stat().st_size, "path": f.name})
    return {"files": results}


@app.get("/api/download/{thread_id}/{filename}")
async def download_file(thread_id: str, filename: str):
    """下载会话产物。越权校验：文件名与会话目录均不允许路径逃逸。"""
    safe_name = Path(filename).name  # 剥离任何目录成分
    for session_dir in OUTPUT_ROOT.glob(f"*_{thread_id[:8]}"):
        target = (session_dir / safe_name).resolve()
        if session_dir.resolve() in target.parents and target.exists():
            return FileResponse(str(target), filename=safe_name)
    return HTMLResponse("文件不存在或无权访问", status_code=404)


@app.get("/")
async def index():
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))
