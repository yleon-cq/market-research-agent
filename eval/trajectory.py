"""Agent 执行轨迹记录：为评测模块提供原料。

每次任务把「委派了哪些助手、调用了哪些工具、安全拦截了几次、
产出了什么文件」按时间序写入 output/trajectories/<thread_id>.jsonl。
评测脚本读轨迹算指标——改提示词/换模型后回归评测，看指标是否退化。
"""
import datetime
import json
from pathlib import Path


class TrajectoryRecorder:
    def __init__(self, thread_id: str, output_root: Path | None = None):
        self.thread_id = thread_id
        root = output_root or (Path(__file__).parents[1] / "output")
        self.dir = root / "trajectories"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{thread_id}.jsonl"
        self.events: list[dict] = []

    def record(self, event_type: str, name: str = "", detail: dict | None = None):
        evt = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "thread_id": self.thread_id,
            "type": event_type,
            "name": name,
        }
        if detail:
            evt["detail"] = detail
        self.events.append(evt)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    def summary(self) -> dict:
        """轨迹摘要（评测指标的输入）。"""
        return {
            "thread_id": self.thread_id,
            "total_events": len(self.events),
            "assistant_calls": sum(1 for e in self.events if e["type"] == "assistant_call"),
            "tool_calls": sum(1 for e in self.events if e["type"] == "tool_call"),
            "tool_names": sorted({e["name"] for e in self.events if e["type"] == "tool_call"}),
            "assistant_names": sorted({e["name"] for e in self.events if e["type"] == "assistant_call"}),
            "sql_guard_triggers": sum(1 for e in self.events if e["type"] == "sql_guard"),
            "files_generated": sorted({e["detail"]["file"] for e in self.events if e["type"] == "file_output" and e.get("detail")}),
        }
