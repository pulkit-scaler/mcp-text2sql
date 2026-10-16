"""
Protocol-level tests for the MCP Text2SQL server (MCP spec 2026-07-28, SDK v2).

Unlike test_tools.py, these go through a real MCP connection:
  - in memory:  mcp.Client(server)          — fast, no subprocess
  - over stdio: MCPClient → subprocess      — exactly what agent.py does
No API keys required.

Run:  uv run python -m pytest tests/test_mcp_protocol.py -v
"""

import os
import sys
from pathlib import Path

import pytest
from mcp import Client, MCPError
from mcp.types import INVALID_PARAMS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
os.environ["DATABASE_PATH"] = str(PROJECT_ROOT / "data" / "sample.db")

from mcp_client import MCPClient, result_text  # noqa: E402
from mcp_server import mcp  # noqa: E402

MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"
SERVER_CMD = sys.executable
SERVER_ARGS = [str(PROJECT_ROOT / "src" / "mcp_server.py")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


# ── Connection / version negotiation ────────────────────────────
@pytest.mark.anyio
async def test_negotiates_2026_07_28(client: Client):
    assert client.protocol_version == MODERN_VERSION
    assert client.server_info is not None
    assert client.server_info.name == "Text2SQL-MCP"


@pytest.mark.anyio
async def test_legacy_handshake_still_supported():
    """Older (2025-era) clients that send `initialize` must still work."""
    async with Client(mcp, mode="legacy") as c:
        assert c.protocol_version == LEGACY_VERSION
        result = await c.call_tool("list_tables", {})
        assert result.structured_content == {"result": ["customers", "employees", "orders"]}


# ── Tools ────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_list_tools(client: Client):
    tools = (await client.list_tools()).tools
    assert [t.name for t in tools] == ["list_tables", "get_table_schema", "execute_sql"]
    schema = {t.name: t.input_schema for t in tools}["get_table_schema"]
    assert schema["required"] == ["table_name"]
    assert "description" in schema["properties"]["table_name"]


@pytest.mark.anyio
async def test_list_tables_returns_every_table(client: Client):
    result = await client.call_tool("list_tables", {})
    assert not result.is_error
    assert result.structured_content == {"result": ["customers", "employees", "orders"]}
    # A list result spans several content blocks; the agent must see all of them
    assert len(result.content) == 3
    assert result_text(result).split("\n") == ["customers", "employees", "orders"]


@pytest.mark.anyio
async def test_get_table_schema_returns_every_column(client: Client):
    result = await client.call_tool("get_table_schema", {"table_name": "customers"})
    assert not result.is_error
    cols = [c["name"] for c in result.structured_content["result"]]
    assert cols == ["id", "name", "country", "currency", "balance"]
    text = result_text(result)
    assert all(f'"{c}"' in text for c in cols)


@pytest.mark.anyio
async def test_execute_sql(client: Client):
    result = await client.call_tool(
        "execute_sql", {"query": "SELECT COUNT(*) AS eur_count FROM customers WHERE currency = 'EUR'"}
    )
    assert not result.is_error
    assert result_text(result).splitlines()[-1] == "4"


# ── Tool errors the model must be able to read (ToolError) ──────
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "args", "message"),
    [
        ("get_table_schema", {"table_name": "employees; DROP TABLE employees"}, "Invalid table name"),
        ("get_table_schema", {"table_name": "nonexistent_table_xyz"}, "not found in the database"),
        ("execute_sql", {"query": "DELETE FROM employees WHERE id = 1"}, "forbidden keyword: DELETE"),
        ("execute_sql", {"query": "SELECT currency_code FROM customers"}, "SQL Error: no such column"),
    ],
)
async def test_tool_errors_reach_the_model(client: Client, tool, args, message):
    result = await client.call_tool(tool, args)
    assert result.is_error
    assert message in result_text(result)


@pytest.mark.anyio
async def test_delete_did_not_modify_data(client: Client):
    await client.call_tool("execute_sql", {"query": "DELETE FROM employees WHERE id = 1"})
    result = await client.call_tool("execute_sql", {"query": "SELECT COUNT(*) FROM employees"})
    assert result_text(result).splitlines()[-1] == "8"


# ── Resources ────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_resources(client: Client):
    listed = [str(r.uri) for r in (await client.list_resources()).resources]
    templates = [t.uri_template for t in (await client.list_resource_templates()).resource_templates]
    assert listed == ["db://tables"]
    assert templates == ["db://schema/{table_name}"]

    tables = await client.read_resource("db://tables")
    assert tables.contents[0].mime_type == "application/json"
    assert '"customers"' in tables.contents[0].text

    schema = await client.read_resource("db://schema/orders")
    assert '"customer_id"' in schema.contents[0].text


@pytest.mark.anyio
async def test_missing_resource_is_invalid_params():
    """2026-07-28: resource not found is -32602 (was -32002) with the URI in data."""
    async with Client(mcp) as c:
        with pytest.raises(MCPError) as exc:
            await c.read_resource("db://schema/nope")
    assert exc.value.code == INVALID_PARAMS
    assert exc.value.data == {"uri": "db://schema/nope"}


# ── Prompts ──────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_prompt(client: Client):
    prompts = (await client.list_prompts()).prompts
    assert [p.name for p in prompts] == ["text2sql_analyst"]
    assert [a.name for a in prompts[0].arguments] == ["question"]

    rendered = await client.get_prompt("text2sql_analyst", {"question": "How many customers pay in EUR?"})
    assert rendered.messages[0].role == "user"
    assert "USER QUESTION: How many customers pay in EUR?" in rendered.messages[0].content.text


# ── Real stdio subprocess (what agent.py uses) ──────────────────
@pytest.mark.anyio
@pytest.mark.parametrize(("mode", "expected"), [("auto", MODERN_VERSION), ("legacy", LEGACY_VERSION)])
async def test_stdio_end_to_end(mode, expected):
    async with MCPClient(command=SERVER_CMD, args=SERVER_ARGS, mode=mode) as c:
        assert c.protocol_version == expected
        assert [t.name for t in await c.list_tools()] == ["list_tables", "get_table_schema", "execute_sql"]

        result = await c.call_tool(
            "execute_sql",
            {
                "query": "SELECT c.name, o.product FROM orders o "
                "JOIN customers c ON o.customer_id = c.id WHERE c.country = 'Germany'"
            },
        )
        assert "Acme GmbH" in result_text(result)

        assert await c.read_resource("db://tables") == ["customers", "employees", "orders"]
        messages = await c.get_prompt("text2sql_analyst", {"question": "q?"})
        assert "USER QUESTION: q?" in messages[0].content.text
