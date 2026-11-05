"""LLM 初始化：统一走 OpenAI 兼容接口（通义千问 / DeepSeek 均可）。"""
import os

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv(find_dotenv())


def build_model():
    """构建 ChatModel；MOCK_LLM=1 或缺 key 时返回 None（演示模式）。"""
    if os.getenv("MOCK_LLM", "0") == "1":
        return None
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        return None
    return init_chat_model(
        model=os.getenv("LLM_MODEL", "qwen-plus"),
        model_provider="openai",
        api_key=api_key,
        base_url=os.getenv("DASHSCOPE_BASE_URL"),
    )


model = build_model()
