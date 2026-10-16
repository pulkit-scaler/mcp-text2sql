# 🛠️ MCP Text2SQL Demo — Mac Setup Guide (From Scratch)

> **Updated for MCP spec `2026-07-28`** (MCP Python SDK v2). See [§22](#22-what-changed-in-mcp-2026-07-28-sdk-v2) for what changed.

Every command is copy-paste ready. Tested on macOS. Uses your preferred `uv init` → `uv venv` → `source .venv/bin/activate` workflow.

---

## Table of Contents

1. [Install uv](#1-install-uv)
2. [Get an OpenAI API Key](#2-get-an-openai-api-key)
3. [Create the Project](#3-create-the-project)
4. [Create and Activate Virtual Environment](#4-create-and-activate-virtual-environment)
5. [Add Dependencies](#5-add-dependencies)
6. [Create the Project Structure](#6-create-the-project-structure)
7. [Create the Sample Database Script](#7-create-the-sample-database-script)
8. [Create the MCP Server](#8-create-the-mcp-server)
9. [Create the MCP Client](#9-create-the-mcp-client)
10. [Create the Agent](#10-create-the-agent)
11. [Create the Environment File](#11-create-the-environment-file)
12. [Create Tests](#12-create-tests)
13. [Create .gitignore](#13-create-gitignore)
14. [Run the Database Setup](#14-run-the-database-setup)
15. [Run Unit Tests](#15-run-unit-tests)
16. [Test MCP Client ↔ Server Connection](#16-test-mcp-client--server-connection)
17. [Run the Interactive Agent](#17-run-the-interactive-agent)
18. [Sample Prompts to Try](#18-sample-prompts-to-try)
19. [How a Question Flows Through the System](#19-how-a-question-flows-through-the-system)
20. [Full Command Summary](#20-full-command-summary)
21. [Troubleshooting](#21-troubleshooting)
22. [What Changed in MCP 2026-07-28 (SDK v2)](#22-what-changed-in-mcp-2026-07-28-sdk-v2)

---

## 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

Verify:

```bash
uv --version
```

**Expected:** `uv 0.7.x` (or newer)

> If you see `command not found`, add to your `~/.zshrc`:
> ```bash
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
> source ~/.zshrc
> ```

---

## 2. Get an OpenAI API Key

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **"Create new secret key"**
3. Copy the key (starts with `sk-`)
4. Save it — you'll paste it in Step 11

> **Cost:** `gpt-4o-mini` costs ~$0.001–0.005 per question. The whole demo costs less than $0.10.

---

## 3. Create the Project

```bash
cd ~/Projects   # or wherever you keep repos
uv init mcp-text2sql
cd mcp-text2sql
```

This creates `pyproject.toml`, `main.py`, and `README.md`. We'll replace the contents.

---

## 4. Create and Activate Virtual Environment

```bash
uv venv
source .venv/bin/activate
```

Your prompt should now show:

```
(.venv) ~/Projects/mcp-text2sql $
```

---

## 5. Add Dependencies

```bash
uv add "mcp[cli]>=2.3,<3" openai python-dotenv pydantic httpx
uv add --dev pytest pytest-asyncio ruff
```

Verify:

```bash
python -c "import importlib.metadata as m, mcp, openai, dotenv; print('✅ All deps OK — mcp', m.version('mcp'))"
```

**Expected:** `✅ All deps OK — mcp 2.3.0` (any `2.x` works; `1.x` is the pre-2026 SDK and will not run this code)

---

## 6. Create the Project Structure

```bash
rm -f main.py    # remove the default uv init file
mkdir -p src scripts examples tests data
touch src/__init__.py tests/__init__.py data/.gitkeep
```

Your tree should now look like:

```
mcp-text2sql/
├── pyproject.toml
├── README.md
├── data/
├── examples/
├── scripts/
├── src/
│   └── __init__.py
└── tests/
    └── __init__.py
```

---

## 7. Create the Sample Database Script

```bash
cat > scripts/setup_db.py << 'PYEOF'
"""Create the sample SQLite database."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sample.db"


def setup() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # ── employees (from the Colab demo) ──────────────────────────
    cur.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            department TEXT NOT NULL, salary REAL NOT NULL, city TEXT NOT NULL
        );
    """)
    cur.executemany(
        "INSERT INTO employees VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Alice", "Engineering", 95000, "Berlin"),
            (2, "Bob", "Engineering", 88000, "Berlin"),
            (3, "Carol", "Marketing", 72000, "Prague"),
            (4, "David", "Marketing", 68000, "Prague"),
            (5, "Eve", "Engineering", 102000, "London"),
            (6, "Frank", "Sales", 61000, "London"),
            (7, "Grace", "Sales", 59000, "Berlin"),
            (8, "Heidi", "Engineering", 97000, "Prague"),
        ],
    )

    # ── customers (supports "How many customers pay in EUR?") ────
    cur.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            country TEXT NOT NULL, currency TEXT NOT NULL, balance REAL NOT NULL
        );
    """)
    cur.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Acme GmbH", "Germany", "EUR", 15400.50),
            (2, "Prague Widgets", "Czech Republic", "CZK", 342000.00),
            (3, "Berlin Tech", "Germany", "EUR", 88200.00),
            (4, "London Analytics", "UK", "GBP", 45000.00),
            (5, "CZ Solutions", "Czech Republic", "CZK", 198000.00),
            (6, "Euro Supplies", "France", "EUR", 23100.75),
            (7, "Nordic Data", "Sweden", "SEK", 67000.00),
            (8, "Praha Services", "Czech Republic", "CZK", 410000.00),
            (9, "Milan Corp", "Italy", "EUR", 54200.00),
            (10, "Swiss Holdings", "Switzerland", "CHF", 120000.00),
        ],
    )

    # ── orders (enables multi-table JOIN queries) ────────────────
    cur.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL,
            product TEXT NOT NULL, amount REAL NOT NULL, order_date TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );
    """)
    cur.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "Widget A", 2500.00, "2024-11-15"),
            (2, 1, "Widget B", 1800.00, "2025-01-10"),
            (3, 2, "Gadget X", 5400.00, "2025-02-01"),
            (4, 3, "Widget A", 3200.00, "2025-01-20"),
            (5, 4, "Service Pro", 9000.00, "2025-03-05"),
            (6, 5, "Gadget X", 2700.00, "2024-12-22"),
            (7, 6, "Widget B", 1100.00, "2025-02-14"),
            (8, 9, "Service Pro", 6500.00, "2025-01-30"),
            (9, 3, "Gadget Y", 4100.00, "2025-03-12"),
            (10, 7, "Widget A", 1900.00, "2025-02-28"),
        ],
    )

    conn.commit()
    conn.close()
    print(f"✅ Database created at {DB_PATH}")
    print(f"   Tables: employees, customers, orders")
    print(f"   Rows:   8 employees, 10 customers, 10 orders")


if __name__ == "__main__":
    setup()
PYEOF
```

---

## 8. Create the MCP Server

This is the core — it exposes the 3 Text2SQL tools via MCP. It uses `MCPServer` (SDK v2's name for `FastMCP`), and tools raise `ToolError` so the model can read what went wrong and retry.

```bash
cat > src/mcp_server.py << 'PYEOF'
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
PYEOF
```

---

## 9. Create the MCP Client

`mcp.Client` connects with whichever protocol the server speaks: it asks the server `server/discover` (2026-07-28, no handshake) and falls back to the old `initialize` handshake for older servers.

```bash
cat > src/mcp_client.py << 'PYEOF'
"""
MCP Client — Thin wrapper over mcp.Client via stdio transport.

`mcp.Client` (MCP Python SDK v2) negotiates the protocol version on connect:
it probes `server/discover` (protocol 2026-07-28, no handshake, no session) and
falls back to the legacy `initialize` handshake for older servers.

Usage:
    async with MCPClient(command="uv", args=["run", "python", "src/mcp_server.py"]) as client:
        tools = await client.list_tools()
        result = await client.call_tool("list_tables", {})
"""

import asyncio
import json
import logging
import sys
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import Client, StdioServerParameters, types

logger = logging.getLogger("text2sql-client")


class MCPClient:
    """Async-context-manager MCP client that spawns & connects to an MCP server."""

    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[dict] = None,
        mode: str = "auto",
    ) -> None:
        self._command = command
        self._args = args
        self._env = env
        self._mode = mode  # "auto" (default), "legacy", or a pinned version like "2026-07-28"
        self._client: Optional[Client] = None
        self._exit_stack = AsyncExitStack()

    # ── Connection lifecycle ─────────────────────────────────────
    async def connect(self) -> None:
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        # Spawns the server subprocess and negotiates the protocol version
        self._client = await self._exit_stack.enter_async_context(
            Client(server_params, mode=self._mode)
        )
        logger.info(f"MCP client connected to server (protocol {self._client.protocol_version})")

    async def cleanup(self) -> None:
        await self._exit_stack.aclose()
        self._client = None

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.cleanup()

    # ── Connection accessors ─────────────────────────────────────
    @property
    def client(self) -> Client:
        if self._client is None:
            raise ConnectionError("Client not connected. Use 'async with MCPClient(...)' or call connect().")
        return self._client

    @property
    def protocol_version(self) -> str:
        return self.client.protocol_version

    @property
    def server_info(self) -> Optional[types.Implementation]:
        return self.client.server_info

    # ── Tool operations ──────────────────────────────────────────
    async def list_tools(self) -> list[types.Tool]:
        result = await self.client.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, tool_input: dict) -> types.CallToolResult:
        logger.info(f"Calling tool: {tool_name} with input: {json.dumps(tool_input, default=str)[:200]}")
        result = await self.client.call_tool(tool_name, tool_input)
        return result

    # ── Prompt operations ────────────────────────────────────────
    async def list_prompts(self) -> list[types.Prompt]:
        result = await self.client.list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name: str, args: dict[str, str]) -> Any:
        result = await self.client.get_prompt(prompt_name, args)
        return result.messages

    # ── Resource operations ──────────────────────────────────────
    async def read_resource(self, uri: str) -> Any:
        result = await self.client.read_resource(uri)
        resource = result.contents[0]
        if isinstance(resource, types.TextResourceContents):
            if resource.mime_type == "application/json":
                return json.loads(resource.text)
            return resource.text
        return resource


def result_text(result: types.CallToolResult) -> str:
    """Join every text block of a tool result.

    A tool returning a list (e.g. list_tables) yields one content block per item,
    so reading only content[0] would drop everything after the first item.
    """
    texts = [block.text for block in result.content if isinstance(block, types.TextContent)]
    return "\n".join(texts) if texts else "(empty)"


# ── Quick self-test ──────────────────────────────────────────────
async def _self_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    async with MCPClient(command="uv", args=["run", "python", "src/mcp_server.py"]) as client:
        tools = await client.list_tools()
        print(f"\n✅ Connected. Protocol: {client.protocol_version}")
        print(f"🧰 Available tools: {[t.name for t in tools]}")

        # Quick tool call
        result = await client.call_tool("list_tables", {})
        print(f"📋 Tables: {result.structured_content['result']}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_self_test())
PYEOF
```

---

## 10. Create the Agent

```bash
cat > src/agent.py << 'PYEOF'
"""
Text2SQL Agent — Orchestration Loop
=====================================
Connects an OpenAI LLM to the MCP Text2SQL server and runs an interactive
ReAct loop: the LLM reasons → calls tools → observes results → repeats.

Usage:
    uv run python src/agent.py
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from mcp_client import MCPClient, result_text

# ── Configuration ────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("text2sql-agent")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_ITERATIONS = 15  # safety limit to prevent infinite loops


# ── Persona (from Colab Component 1) ────────────────────────────
SYSTEM_PROMPT = """You are a Senior SQL Developer and Data Analyst.

INSTRUCTIONS:
You generate and execute SQL queries against a SQLite database.
Follow this workflow for every user question:
  1. List all available tables using the list_tables tool.
  2. Get the schema (columns) of the relevant table(s) using get_table_schema.
  3. Write a syntactically correct SQLite SELECT query.
  4. Execute the query using execute_sql and return the results.

RULES:
  - ONLY use table and column names confirmed by the schema tools.
  - NEVER guess or invent table or column names.
  - NEVER run DELETE, DROP, UPDATE, INSERT, or any data-modifying SQL.
  - If the question is unclear, state your assumptions first.
  - If a query fails, analyze the error and retry with a corrected query.
  - Use SQLite syntax (e.g., use || for string concatenation, not CONCAT).

OUTPUT FORMAT:
Always respond with:
  1. The SQL query you generated
  2. The query result
  3. A short natural-language summary of the answer
"""


def _mcp_tools_to_openai_schema(tools) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to OpenAI function-calling format."""
    openai_tools = []
    for tool in tools:
        schema = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema if tool.input_schema else {"type": "object", "properties": {}},
            },
        }
        openai_tools.append(schema)
    return openai_tools


async def run_agent_loop(client: MCPClient, openai_client: OpenAI) -> None:
    """Interactive REPL: user asks questions, agent uses MCP tools to answer."""

    # 1. Discover tools from the MCP server
    mcp_tools = await client.list_tools()
    openai_tools = _mcp_tools_to_openai_schema(mcp_tools)
    tool_names = [t.name for t in mcp_tools]

    print("\n" + "=" * 60)
    print("  🗄️  Text2SQL Agent — powered by MCP")
    print("=" * 60)
    print(f"  Model:  {OPENAI_MODEL}")
    print(f"  MCP:    protocol {client.protocol_version}")
    print(f"  Tools:  {tool_names}")
    print(f"  Type 'quit' or 'exit' to stop.\n")

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        # ── Get user input ───────────────────────────────────────
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("👋 Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # ── ReAct loop: call LLM → maybe call tool → repeat ─────
        for iteration in range(MAX_ITERATIONS):
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.0,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )

            assistant_msg = response.choices[0].message

            # Case A: LLM produced a final text answer
            if not assistant_msg.tool_calls:
                print(f"\n🤖 Agent:\n{assistant_msg.content}\n")
                messages.append({"role": "assistant", "content": assistant_msg.content})
                break

            # Case B: LLM wants to call one or more tools
            # Append the assistant message (with tool_calls) to history.
            # Only the standard fields: OpenAI-compatible providers (e.g. Groq)
            # reject OpenAI-only extras such as "annotations".
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_msg.content,
                    "tool_calls": [tc.model_dump(exclude_none=True) for tc in assistant_msg.tool_calls],
                }
            )

            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"  🔧 [{iteration + 1}] Calling {fn_name}({json.dumps(fn_args)}) ...")

                try:
                    result = await client.call_tool(fn_name, fn_args)
                    # Extract text from MCP result (all blocks — list results span several)
                    tool_output = result_text(result)
                except Exception as e:
                    tool_output = f"Error: {e}"
                    logger.error(f"Tool call failed: {e}")

                # Append tool result to messages
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_output,
                    }
                )
        else:
            print("⚠️  Max iterations reached. The agent may need a simpler question.")


# ── Main ─────────────────────────────────────────────────────────
async def main() -> None:
    if not OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Spawn MCP server as a subprocess and connect
    async with MCPClient(
        command="uv",
        args=["run", "python", "src/mcp_server.py"],
    ) as mcp_client:
        await run_agent_loop(mcp_client, openai_client)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
PYEOF
```

---

## 11. Create the Environment File

```bash
cat > .env.example << 'EOF'
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
DATABASE_PATH=./data/sample.db
# Using Groq (or another OpenAI-compatible provider)? Set these instead:
# OPENAI_API_KEY=gsk_your-groq-key
# OPENAI_BASE_URL=https://api.groq.com/openai/v1
# OPENAI_MODEL=openai/gpt-oss-120b
EOF

cp .env.example .env
open -e .env
```

**In the TextEdit window that opens**, change `sk-your-key-here` to your actual OpenAI API key. Save (`⌘S`) and close.

> **Using Groq instead?** Groq's API is OpenAI-compatible, so the agent needs no code changes. Put your Groq key (`gsk_...`) in `OPENAI_API_KEY`, and set `OPENAI_BASE_URL=https://api.groq.com/openai/v1` and a tool-calling model such as `OPENAI_MODEL=openai/gpt-oss-120b` (the commented lines in `.env.example`). The `openai` library reads `OPENAI_BASE_URL` on its own.

Verify:

```bash
python -c "
from dotenv import load_dotenv; import os; load_dotenv()
key = os.getenv('OPENAI_API_KEY', '')
print(f'✅ Key loaded ({key[:8]}...{key[-4:]})' if key and key != 'sk-your-key-here' else '❌ Key not set')
"
```

---

## 12. Create Tests

```bash
cat > tests/test_tools.py << 'PYEOF'
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
from mcp.server.mcpserver.exceptions import ToolError

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
        with pytest.raises(ToolError, match="not found"):
            get_table_schema("nonexistent_table_xyz")

    def test_sql_injection_rejected(self):
        with pytest.raises(ToolError, match="Invalid table name"):
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
        with pytest.raises(ToolError, match="forbidden"):
            execute_sql("DELETE FROM employees WHERE id = 1")

    def test_drop_rejected(self):
        with pytest.raises(ToolError, match="forbidden"):
            execute_sql("DROP TABLE employees")

    def test_empty_result(self):
        result = execute_sql("SELECT * FROM employees WHERE city = 'Atlantis'")
        assert "no rows" in result.lower()

    def test_sql_error_raised(self):
        with pytest.raises(ToolError, match="SQL Error: no such column"):
            execute_sql("SELECT currency_code FROM customers")
PYEOF
```

The repo also ships two connection-level test files (copy them from the repo):

- `tests/test_mcp_protocol.py` — talks to the server over a real MCP connection (in memory and over stdio) and checks the negotiated protocol (`2026-07-28`, plus the legacy `2025-11-25` handshake), every tool, resource and prompt, and that tool errors reach the model.
- `tests/test_agent_loop.py` — runs `agent.py`'s ReAct loop against the real server with a scripted stand-in for OpenAI, so the whole agent → MCP → SQLite path is tested without an API key.

---

## 13. Create .gitignore

```bash
cat > .gitignore << 'EOF'
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
.python-version
.DS_Store
data/*.db
!data/.gitkeep
EOF
```

---

## 14. Run the Database Setup

```bash
python scripts/setup_db.py
```

**Expected:**

```
✅ Database created at .../data/sample.db
   Tables: employees, customers, orders
   Rows:   8 employees, 10 customers, 10 orders
```

Verify:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/sample.db')
cur = conn.cursor()
for t in ['employees','customers','orders']:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'  {t}: {cur.fetchone()[0]} rows')
conn.close()
"
```

**Expected:**

```
  employees: 8 rows
  customers: 10 rows
  orders: 10 rows
```

---

## 15. Run Unit Tests

```bash
python -m pytest tests -v
```

**Expected** (abridged):

```
tests/test_agent_loop.py::test_agent_loop_end_to_end PASSED
tests/test_mcp_protocol.py::test_negotiates_2026_07_28 PASSED
tests/test_mcp_protocol.py::test_legacy_handshake_still_supported PASSED
...
tests/test_mcp_protocol.py::test_stdio_end_to_end[auto-2026-07-28] PASSED
tests/test_mcp_protocol.py::test_stdio_end_to_end[legacy-2025-11-25] PASSED
tests/test_tools.py::TestListTables::test_returns_list PASSED
...
tests/test_tools.py::TestExecuteSQL::test_sql_error_raised PASSED

32 passed
```

No API key needed for this step. `bash scripts/smoke_test.sh` runs these tests plus the connection check from §16 in one go.

---

## 16. Test MCP Client ↔ Server Connection

```bash
python src/mcp_client.py
```

**Expected:**

```
✅ Connected. Protocol: 2026-07-28
🧰 Available tools: ['list_tables', 'get_table_schema', 'execute_sql']
📋 Tables: ['customers', 'employees', 'orders']
```

This proves the MCP stdio transport works and that client and server agreed on protocol `2026-07-28`. No API key needed.

---

## 17. Run the Interactive Agent

```bash
python src/agent.py
```

**Expected startup:**

```
============================================================
  🗄️  Text2SQL Agent — powered by MCP
============================================================
  Model:  gpt-4o-mini
  MCP:    protocol 2026-07-28
  Tools:  ['list_tables', 'get_table_schema', 'execute_sql']
  Type 'quit' or 'exit' to stop.

You: _
```

Type your first question:

```
How many customers pay in EUR?
```

**Expected:**

```
  🔧 [1] Calling list_tables({}) ...
  🔧 [2] Calling get_table_schema({"table_name": "customers"}) ...
  🔧 [3] Calling execute_sql({"query": "SELECT COUNT(*) AS eur_count FROM customers WHERE currency = 'EUR'"}) ...

🤖 Agent:
**SQL Query:** SELECT COUNT(*) AS eur_count FROM customers WHERE currency = 'EUR'
**Result:** 4
**Summary:** There are 4 customers who pay in EUR.
```

Type `quit` to exit.

> **Important:** Run the agent from the **project root** (`python src/agent.py`), not from inside `src/`. The MCP server subprocess is spawned with the path `src/mcp_server.py` relative to the directory you start in; from inside `src/` it fails with `MCPError: Connection closed`.

---

## 18. Sample Prompts to Try

### Simple queries
```
How many customers pay in EUR?
List all employees in Berlin.
What is the average salary?
```

### Aggregations
```
What is the average salary by department?
Which department has the highest total salary?
How many employees are in each city?
```

### Multi-table JOINs
```
Show me all orders from German customers with the customer name and product.
What is the total order amount per customer?
Which customer has placed the most orders?
```

### Ratio / comparison (from the Colab)
```
What is the ratio of customers who pay in EUR vs CZK?
Compare average salary between Engineering and Marketing.
```

### Edge cases (tests agent guardrails)
```
Delete all employees.
Show me everything about the database.
What's the weather like?
```

---

## 19. How a Question Flows Through the System

```
 YOU: "How many customers pay in EUR?"
  │
  ▼
 agent.py  →  sends question + tool schemas to OpenAI
  │
  ▼
 OpenAI LLM  →  decides: "call list_tables first"
  │                returns: {tool_call: "list_tables", args: {}}
  ▼
 mcp_client.py  →  sends JSON-RPC over stdio pipe
  │                (2026-07-28: protocol version rides in each request's _meta; no handshake)
  │
  ▼
 mcp_server.py  →  list_tables()
  │                 SELECT name FROM sqlite_master
  │                 returns: ["customers", "employees", "orders"]
  ▼
 agent.py  →  feeds result back to OpenAI
  │
  ▼
 OpenAI LLM  →  decides: "call get_table_schema(customers)"
  │
  ▼
 mcp_server.py  →  get_table_schema("customers")
  │                 PRAGMA table_info(customers)
  │                 returns: [id, name, country, currency, balance]
  ▼
 agent.py  →  feeds result back to OpenAI
  │
  ▼
 OpenAI LLM  →  writes SQL, decides: "call execute_sql"
  │
  ▼
 mcp_server.py  →  execute_sql("SELECT COUNT(*) ... WHERE currency='EUR'")
  │                 returns: "4"
  ▼
 agent.py  →  feeds result back to OpenAI
  │
  ▼
 OpenAI LLM  →  has all info, produces final text answer
  │
  ▼
 YOU see: "There are 4 customers who pay in EUR."
```

---

## 20. Full Command Summary

Copy-paste from zero to running agent:

```bash
# ── Install uv ───────────────────────────────────────────
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# ── Create project ───────────────────────────────────────
uv init mcp-text2sql
cd mcp-text2sql

# ── Virtual environment ──────────────────────────────────
uv venv
source .venv/bin/activate

# ── Dependencies ─────────────────────────────────────────
uv add "mcp[cli]>=2.3,<3" openai python-dotenv pydantic httpx
uv add --dev pytest pytest-asyncio ruff

# ── Project structure ────────────────────────────────────
rm -f main.py
mkdir -p src scripts examples tests data
touch src/__init__.py tests/__init__.py data/.gitkeep

# ── Create files (sections 7-13 above) ──────────────────
# ... or unzip the provided repo into this directory

# ── Environment ──────────────────────────────────────────
cp .env.example .env
open -e .env    # paste your OpenAI API key, save, close

# ── Database ─────────────────────────────────────────────
python scripts/setup_db.py

# ── Tests (no API key needed) ────────────────────────────
python -m pytest tests -v

# ── MCP connection test (no API key needed) ──────────────
python src/mcp_client.py

# ── Run the agent (from the project root) ────────────────
python src/agent.py
```

---

## 21. Troubleshooting

| Error | Fix |
|-------|-----|
| `uv: command not found` | `source $HOME/.local/bin/env` or restart terminal |
| `(.venv) not in prompt` | `source .venv/bin/activate` |
| `ModuleNotFoundError: No module named 'mcp'` | Make sure venv is active, then `uv add mcp` |
| `FileNotFoundError: Database not found` | `python scripts/setup_db.py` |
| `OPENAI_API_KEY not set` | `cp .env.example .env` → paste your key |
| `openai.AuthenticationError` | Key is invalid — regenerate at platform.openai.com |
| `400 ... property 'annotations' is unsupported` (Groq and other OpenAI-compatible APIs) | Agent code sends OpenAI-only fields back in the history. Append only `role`, `content` and `tool_calls` for assistant messages, as `src/agent.py` does |
| `Server process exited` | Run `python src/mcp_server.py` standalone to see the error |
| `RateLimitError` | Wait 60s and retry, or check billing at platform.openai.com/usage |
| Tests fail with import error | Make sure you're in the project root with venv active |
| `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` | Code written for SDK v1. `FastMCP` is now `MCPServer`: `from mcp.server.mcpserver import MCPServer` (see §22) |
| `AttributeError: 'Tool' object has no attribute 'inputSchema'` | SDK v2 uses snake_case attributes: `tool.input_schema`, `result.is_error`, `resource.mime_type` |
| `MCPError: Connection closed` when starting the agent | Run from the project root: `python src/agent.py` |
| Model only sees `Error executing tool <name>` | The tool raised a plain exception. Raise `ToolError` so the message reaches the model |

---

## 22. What Changed in MCP 2026-07-28 (SDK v2)

The MCP spec revision **2026-07-28** and the **MCP Python SDK 2.x** (released the same day) changed how clients connect and renamed parts of the SDK. Here is what that meant for this project:

| Change | What it means here |
|--------|--------------------|
| No more `initialize` handshake or protocol sessions. Each request carries its protocol version in `_meta`, and servers answer a new `server/discover` request | `mcp_client.py` uses `mcp.Client`, which runs `server/discover` and falls back to the old handshake for older servers. A hand-made `ClientSession` + `initialize()` would still speak the old protocol |
| `FastMCP` renamed to `MCPServer` (`mcp.server.fastmcp` → `mcp.server.mcpserver`) | Updated imports in `mcp_server.py` |
| Python field names are snake_case (`inputSchema` → `input_schema`, `mimeType` → `mime_type`, `isError` → `is_error`) | Updated in `agent.py` and `mcp_client.py`. The JSON on the wire is still camelCase |
| Resource URIs are plain `str` (no `pydantic.AnyUrl`) | `read_resource("db://tables")` takes the string directly |
| A plain exception in a tool now reaches the model only as `Error executing tool <name>`; only `ToolError` messages pass through | All tool errors raise `ToolError`, so the model can still read "Invalid table name…" or "SQL Error: no such column…" and retry |
| Missing resource is error `-32602` (was `-32002`), with the URI in `error.data` | `db://schema/<missing>` raises `ResourceNotFoundError` |
| Every result carries `resultType`, and list results carry `ttlMs`/`cacheScope` caching hints | Handled by the SDK; nothing to change |
| MCP's Logging feature (plus Roots and Sampling) is deprecated: log to `stderr` instead | The server already logs to `stderr` with Python `logging` |

Older 2025-era clients (anything that still sends `initialize`) keep working against this server; `tests/test_mcp_protocol.py` checks both protocols.

**Also fixed in this update:** a tool that returns a list (`list_tables`, `get_table_schema`) produces one content block per item, and the agent used to read only the first block, so the model saw just `customers` instead of every table. `agent.py` now joins all blocks (`result_text()` in `mcp_client.py`).

References: [Spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) · [SDK v1 → v2 migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md)
