"""
Unit tests for the MCP Text2SQL tools.

These test the tool functions directly (no MCP transport, no LLM).
They only need the sample database — no API keys required.

Run:  uv run python -m pytest tests/test_tools.py -v
"""

import os
import sys
import sqlite3
from pathlib import Path

import pytest

# Add src/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set DB_PATH before importing the server module
DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "sample.db")
os.environ["DATABASE_PATH"] = DB_PATH

from mcp_server import list_tables, get_table_schema, execute_sql  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def ensure_db():
    """Make sure the sample database exists before tests run."""
    if not Path(DB_PATH).exists():
        # Create it inline (same as setup_db.py)
        from scripts.setup_db import setup
        setup()
    assert Path(DB_PATH).exists(), f"Database not found at {DB_PATH}"


# ── Tool 1: list_tables ─────────────────────────────────────────
class TestListTables:
    def test_returns_list(self):
        result = list_tables()
        assert isinstance(result, list)

    def test_contains_expected_tables(self):
        result = list_tables()
        assert "employees" in result
        assert "customers" in result
        assert "orders" in result

    def test_returns_at_least_three_tables(self):
        result = list_tables()
        assert len(result) >= 3


# ── Tool 2: get_table_schema ────────────────────────────────────
class TestGetTableSchema:
    def test_employees_columns(self):
        result = get_table_schema("employees")
        col_names = [c["name"] for c in result]
        assert "id" in col_names
        assert "name" in col_names
        assert "department" in col_names
        assert "salary" in col_names

    def test_returns_type_info(self):
        result = get_table_schema("employees")
        for col in result:
            assert "name" in col
            assert "type" in col
            assert "primary_key" in col

    def test_invalid_table_raises(self):
        with pytest.raises(ValueError, match="not found"):
            get_table_schema("nonexistent_table_xyz")

    def test_sql_injection_rejected(self):
        with pytest.raises(ValueError, match="Invalid table name"):
            get_table_schema("employees; DROP TABLE employees")


# ── Tool 3: execute_sql ─────────────────────────────────────────
class TestExecuteSQL:
    def test_simple_count(self):
        result = execute_sql("SELECT COUNT(*) as cnt FROM employees")
        assert "8" in result  # 8 employees in sample data

    def test_select_returns_data(self):
        result = execute_sql("SELECT name, department FROM employees WHERE city = 'Berlin'")
        assert "Alice" in result
        assert "Engineering" in result

    def test_eur_customers(self):
        """Matches the Colab's demo question: How many customers pay in EUR?"""
        result = execute_sql("SELECT COUNT(*) as eur_count FROM customers WHERE currency = 'EUR'")
        assert "4" in result  # 4 EUR customers in sample data

    def test_join_query(self):
        result = execute_sql(
            "SELECT c.name, o.product FROM orders o "
            "JOIN customers c ON o.customer_id = c.id "
            "WHERE c.country = 'Germany'"
        )
        assert "Acme GmbH" in result

    def test_delete_rejected(self):
        with pytest.raises(ValueError, match="forbidden"):
            execute_sql("DELETE FROM employees WHERE id = 1")

    def test_drop_rejected(self):
        with pytest.raises(ValueError, match="forbidden"):
            execute_sql("DROP TABLE employees")

    def test_empty_result(self):
        result = execute_sql("SELECT * FROM employees WHERE city = 'Atlantis'")
        assert "no rows" in result.lower()
