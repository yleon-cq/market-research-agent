"""三个本地子智能体定义（网络搜索 / 数据库 / 知识库）。"""
from agent.load_prompt import sub_agents_config
from tools.docs_tools import search_knowledge_docs
from tools.internet_search_tool import internet_search
from tools.sqlite_tools import execute_sql_query, get_table_data, list_sql_tables


def build_internet_sub_agent() -> dict:
    cfg = sub_agents_config["internet"]
    return {
        "name": cfg["name"],
        "description": cfg["description"],
        "system_prompt": cfg["system_prompt"],
        "tools": [internet_search],
    }


def build_db_sub_agent() -> dict:
    cfg = sub_agents_config["db"]
    return {
        "name": cfg["name"],
        "description": cfg["description"],
        "system_prompt": cfg["system_prompt"],
        "tools": [list_sql_tables, get_table_data, execute_sql_query],
    }


def build_docs_sub_agent() -> dict:
    cfg = sub_agents_config["docs"]
    return {
        "name": cfg["name"],
        "description": cfg["description"],
        "system_prompt": cfg["system_prompt"],
        "tools": [search_knowledge_docs],
    }
