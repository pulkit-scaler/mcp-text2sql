"""
MCP Server — Text2SQL Tools
============================
Exposes exactly the three tools defined in the Colab PDF:
  1. list_tables      — Get all table names in the database
  2. get_table_schema — Get column names for a specific table
  3. execute_sql      — Run a SELECT query and return results

Also exposes MCP resources and prompts for richer integration.

Built on the MCP Python SDK v2 (`MCPServer`, formerly `FastMCP`), which speaks
protocol revision 2026-07-28 and still serves older clients that use the
2025-era `initialize` handshake.

Run directly:  uv run python src/mcp_server.py
"""

import logging
import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.server.mcpserver.prompts import base
from pydantic import Field

# ── Configuration ────────────────────────────────────────────────
load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "sample.db"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("text2sql-mcp")

# ── MCP Server Instance ─────────────────────────────────────────
mcp = MCPServer("Text2SQL-MCP", log_level="INFO")


# ── Helper ───────────────────────────────────────────────────────
def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection. Raises if DB not found."""
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Run 'uv run python scripts/setup_db.py' first."
        )
    return sqlite3.connect(DB_PATH)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 1 — list_tables
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool(
    name="list_tables",
    description=(
        "Get all table names from the SQLite database. "
        "Call this first to discover which tables are available before writing any queries."
    ),
)
def list_tables() -> list[str]:
    logger.info("🔧 list_tables called")
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cur.fetchall()]
        logger.info(f"   ↳ found {len(tables)} tables: {tables}")
        return tables
    finally:
        conn.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 2 — get_table_schema
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool(
    name="get_table_schema",
    description=(
        "Get column names and types for a specific table. "
        "Use this after identifying the relevant table with list_tables."
    ),
)
def get_table_schema(
    table_name: str = Field(description="The exact name of the table to inspect"),
) -> list[dict]:
    logger.info(f"🔧 get_table_schema called — table_name={table_name!r}")

    # Prevent SQL injection via table name.
    # ToolError (not ValueError): in SDK v2 only a ToolError's message reaches the model.
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table_name):
        raise ToolError(f"Invalid table name: {table_name!r}")

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info(`{table_name}`);")
        rows = cur.fetchall()
        if not rows:
            raise ToolError(f"Table '{table_name}' not found in the database.")
        columns = [
            {"name": row[1], "type": row[2], "nullable": not row[3], "primary_key": bool(row[5])}
            for row in rows
        ]
        logger.info(f"   ↳ {len(columns)} columns: {[c['name'] for c in columns]}")
        return columns
    finally:
        conn.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 3 — execute_sql
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool(
    name="execute_sql",
    description=(
        "Execute a SQL SELECT query against the database and return results as rows. "
        "ONLY SELECT queries are allowed — no INSERT, UPDATE, DELETE, DROP, or ALTER."
    ),
)
def execute_sql(
    query: str = Field(description="A valid SQL SELECT query to execute"),
) -> str:
    logger.info(f"🔧 execute_sql called — query={query!r}")

    # Safety: reject anything that isn't a SELECT
    normalized = query.strip().upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "REPLACE"]
    for keyword in forbidden:
        if normalized.startswith(keyword) or f" {keyword} " in f" {normalized} ":
            raise ToolError(
                f"Only SELECT queries are allowed. "
                f"Detected forbidden keyword: {keyword}"
            )

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()

        # Format as a readable table string
        if not rows:
            result = "(no rows returned)"
        else:
            header = " | ".join(columns)
            separator = "-+-".join("-" * max(len(col), 8) for col in columns)
            data_rows = [" | ".join(str(val) for val in row) for row in rows]
            result = f"{header}\n{separator}\n" + "\n".join(data_rows)

        logger.info(f"   ↳ returned {len(rows)} rows")
        return result
    except sqlite3.Error as e:
        # Raised as a ToolError so the result is flagged is_error=True and the
        # model still reads the message and can retry with a corrected query.
        error_msg = f"SQL Error: {e}"
        logger.error(f"   ↳ {error_msg}")
        raise ToolError(error_msg) from e
    finally:
        conn.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP RESOURCE — Database info
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.resource("db://tables", mime_type="application/json")
def resource_list_tables() -> list[str]:
    """Resource: returns the list of table names as JSON."""
    return list_tables()


@mcp.resource("db://schema/{table_name}", mime_type="application/json")
def resource_table_schema(table_name: str) -> list[dict]:
    """Resource: returns column info for a table as JSON."""
    try:
        return get_table_schema(table_name)
    except ToolError as e:
        # Protocol "resource not found" (-32602 with the URI in error.data)
        raise ResourceNotFoundError(str(e)) from e


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP PROMPT — Text2SQL analyst prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.prompt(
    name="text2sql_analyst",
    description="Generate a system prompt for a Text2SQL analyst given a user question.",
)
def text2sql_analyst_prompt(
    question: str = Field(description="The user's natural-language question"),
) -> list[base.Message]:
    prompt = f"""You are a Senior SQL Developer and Data Analyst.

INSTRUCTIONS:
You generate and execute SQL queries against a SQLite database.
Follow this workflow for every user question:
  1. List all available tables using the list_tables tool.
  2. Get the schema (columns) of the relevant table(s) using get_table_schema.
  3. Write a syntactically correct SQLite SELECT query.
  4. Execute the query using execute_sql and return the results.

RULES:
  - ONLY use table and column names confirmed by the schema tool.
  - NEVER guess or invent table or column names.
  - NEVER run DELETE, DROP, UPDATE, INSERT, or any data-modifying SQL.
  - If the question is unclear, state your assumptions first.
  - If a query fails, analyze the error and retry with a corrected query.

OUTPUT FORMAT:
Always respond with:
  - The SQL query you generated
  - The query result
  - A short natural-language summary of the answer

USER QUESTION: {question}"""

    return [base.UserMessage(prompt)]


# ── Entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"Starting Text2SQL MCP Server (db={DB_PATH})")
    mcp.run(transport="stdio")
