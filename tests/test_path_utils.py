"""路径安全解析测试：LLM 幻觉路径清洗 / 会话目录防逃逸。"""
from utils.path_utils import resolve_path

SESSION = "/abs/fake/output/session_20260101_abc"


def test_virtual_prefix_cleaned(tmp_path):
    session = str(tmp_path / "session_x")
    assert resolve_path("/workspace/report.md", session).endswith("report.md")
    assert resolve_path("/mnt/data/report.md", session).endswith("report.md")


def test_relative_path_joins_session(tmp_path):
    session = str(tmp_path / "session_x")
    result = resolve_path("report.md", session)
    assert result.startswith(session)


def test_inside_session_absolute_kept(tmp_path):
    session = str(tmp_path / "session_x")
    inner = str(tmp_path / "session_x" / "a.md")
    assert resolve_path(inner, session) == str((tmp_path / "session_x" / "a.md").resolve())


def test_session_nesting_removed(tmp_path):
    session = str(tmp_path / "session_x")
    nested = str(tmp_path / "session_x" / "session_x" / "a.md")
    result = resolve_path(nested, session)
    assert result.count("session_x") == 1


def test_output_prefix_stripped(tmp_path):
    session = str(tmp_path / "session_x")
    assert resolve_path("output/report.md", session).startswith(session)
