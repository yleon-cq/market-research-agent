"""加载 prompt/prompts.yaml 配置，集中暴露 main / sub_agents 配置。"""
from pathlib import Path

import yaml

_yaml_path = Path(__file__).parents[1] / "prompt" / "prompts.yaml"


def load_yaml(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_yaml_dict = load_yaml(_yaml_path)

main_config = _yaml_dict["main_agent"]
sub_agents_config = _yaml_dict["sub_agents"]
core_tools_config = _yaml_dict.get("core_tools", {})
