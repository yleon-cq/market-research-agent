"""SQL 只读拦截测试：防失控设计回归。"""
import pytest

from utils.sql_guard import validate_readonly_sql


def test_select_allowed():
    assert validate_readonly_sql("SELECT * FROM products") is None
    assert validate_readonly_sql("  select name from sqlite_master") is None


def test_cte_allowed():
    assert validate_readonly_sql(
        "WITH t AS (SELECT 1) SELECT * FROM t"
    ) is None


def test_write_blocked():
    for sql in [
        "DELETE FROM products",
        "DROP TABLE products",
        "UPDATE products SET price=1",
        "INSERT INTO products VALUES (1)",
        "ALTER TABLE products ADD COLUMN x INT",
    ]:
        assert validate_readonly_sql(sql) is not None


def test_write_hidden_in_cte_blocked():
    assert validate_readonly_sql(
        "WITH t AS (SELECT 1) , s AS (DELETE FROM products RETURNING *) SELECT * FROM t"
    ) is not None


def test_multi_statement_blocked():
    assert validate_readonly_sql("SELECT 1; DROP TABLE products") is not None


def test_non_select_blocked():
    assert validate_readonly_sql("VACUUM") is not None
