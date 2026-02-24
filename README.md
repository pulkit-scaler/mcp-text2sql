# 🛠️ MCP Text2SQL Demo — Mac Setup Guide (From Scratch)

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
uv add mcp openai python-dotenv pydantic httpx
uv add --dev pytest pytest-asyncio ruff
```

Verify:

```bash
python -c "import mcp; import openai; import dotenv; print('✅ All deps OK')"
```

**Expected:** `✅ All deps OK`

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

This is the core — it exposes the 3 Text2SQL tools via MCP.

```bash
cat > src/mcp_server.py << 'PYEOF'
"""
MCP Server — Text2SQL Tools
Exposes: list_tables, get_table_schema, execute_sql
"""

import logging
import os
import re
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
from pydantic import Field

load_dotenv()

DB_PATH = os.getenv(
    "DATABASE_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "sample.db"),
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("text2sql-mcp")

mcp = FastMCP("Text2SQL-MCP", log_level="INFO")


def _get_connection() -> sqlite3.Connection:
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run: python scripts/setup_db.py"
        )
    return sqlite3.connect(DB_PATH)


# ── TOOL 1: list_tables ─────────────────────────────────────────
@mcp.tool(
    name="list_tables",
    description=(
        "Get all table names from the SQLite database. "
        "Call this first to discover available tables."
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


# ── TOOL 2: get_table_schema ────────────────────────────────────
@mcp.tool(
    name="get_table_schema",
    description=(
        "Get column names and types for a specific table. "
        "Use after identifying the table with list_tables."
    ),
)
def get_table_schema(
    table_name: str = Field(description="The exact name of the table to inspect"),
) -> list[dict]:
    logger.info(f"🔧 get_table_schema called — table_name={table_name!r}")
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table_name):
        raise ValueError(f"Invalid table name: {table_name!r}")
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info(`{table_name}`);")
        rows = cur.fetchall()
        if not rows:
            raise ValueError(f"Table '{table_name}' not found in the database.")
        columns = [
            {"name": row[1], "type": row[2], "nullable": not row[3], "primary_key": bool(row[5])}
            for row in rows
        ]
        logger.info(f"   ↳ {len(columns)} columns: {[c['name'] for c in columns]}")
        return columns
    finally:
        conn.close()


# ── TOOL 3: execute_sql ─────────────────────────────────────────
@mcp.tool(
    name="execute_sql",
    description=(
        "Execute a SQL SELECT query and return results. "
        "ONLY SELECT allowed — no INSERT/UPDATE/DELETE/DROP."
    ),
)
def execute_sql(
    query: str = Field(description="A valid SQL SELECT query to execute"),
) -> str:
    logger.info(f"🔧 execute_sql called — query={query!r}")
    normalized = query.strip().upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "REPLACE"]
    for keyword in forbidden:
        if normalized.startswith(keyword) or f" {keyword} " in f" {normalized} ":
            raise ValueError(
                f"Only SELECT queries are allowed. Detected forbidden keyword: {keyword}"
            )
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        if not rows:
            return "(no rows returned)"
        header = " | ".join(columns)
        separator = "-+-".join("-" * max(len(col), 8) for col in columns)
        data_rows = [" | ".join(str(val) for val in row) for row in rows]
        result = f"{header}\n{separator}\n" + "\n".join(data_rows)
        logger.info(f"   ↳ returned {len(rows)} rows")
        return result
    except sqlite3.Error as e:
        error_msg = f"SQL Error: {e}"
        logger.error(f"   ↳ {error_msg}")
        return error_msg
    finally:
        conn.close()


# ── MCP Resources ────────────────────────────────────────────────
@mcp.resource("db://tables", mime_type="application/json")
def resource_list_tables() -> list[str]:
    return list_tables()


@mcp.resource("db://schema/{table_name}", mime_type="application/json")
def resource_table_schema(table_name: str) -> list[dict]:
    return get_table_schema(table_name)


# ── MCP Prompt ───────────────────────────────────────────────────
@mcp.prompt(
    name="text2sql_analyst",
    description="Generate a system prompt for a Text2SQL analyst.",
)
def text2sql_analyst_prompt(
    question: str = Field(description="The user's natural-language question"),
) -> list[base.Message]:
    prompt = f"""You are a Senior SQL Developer and Data Analyst.
Follow this workflow:
  1. List tables with list_tables.
  2. Get schema with get_table_schema.
  3. Write a SQLite SELECT query.
  4. Execute with execute_sql.
RULES: Only use confirmed names. Never modify data. Use SQLite syntax.
OUTPUT: Show SQL, result, and a brief summary.
USER QUESTION: {question}"""
    return [base.UserMessage(prompt)]


if __name__ == "__main__":
    logger.info(f"Starting Text2SQL MCP Server (db={DB_PATH})")
    mcp.run(transport="stdio")
PYEOF
```

---

## 9. Create the MCP Client

```bash
cat > src/mcp_client.py << 'PYEOF'
"""MCP Client — Thin wrapper over mcp.ClientSession via stdio."""

import asyncio
import json
import logging
import sys
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

logger = logging.getLogger("text2sql-client")


class MCPClient:
    def __init__(self, command: str, args: list[str], env: Optional[dict] = None) -> None:
        self._command = command
        self._args = args
        self._env = env
        self._session: Optional[ClientSession] = None
        self._exit_stack = AsyncExitStack()

    async def connect(self) -> None:
        server_params = StdioServerParameters(
            command=self._command, args=self._args, env=self._env,
        )
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
        logger.info("MCP client connected to server")

    async def cleanup(self) -> None:
        await self._exit_stack.aclose()
        self._session = None

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.cleanup()

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError(
                "Client not connected. Use 'async with MCPClient(...)' or call connect()."
            )
        return self._session

    async def list_tools(self) -> list[types.Tool]:
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, tool_input: dict) -> types.CallToolResult:
        logger.info(f"Calling tool: {tool_name}")
        return await self.session.call_tool(tool_name, tool_input)

    async def list_prompts(self) -> list[types.Prompt]:
        result = await self.session.list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name: str, args: dict[str, str]) -> Any:
        result = await self.session.get_prompt(prompt_name, args)
        return result.messages

    async def read_resource(self, uri: str) -> Any:
        result = await self.session.read_resource(AnyUrl(uri))
        resource = result.contents[0]
        if isinstance(resource, types.TextResourceContents):
            if resource.mimeType == "application/json":
                return json.loads(resource.text)
            return resource.text
        return resource


async def _self_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    async with MCPClient(command="python", args=["src/mcp_server.py"]) as client:
        tools = await client.list_tools()
        print(f"\n✅ Connected. Available tools: {[t.name for t in tools]}")
        result = await client.call_tool("list_tables", {})
        print(f"📋 Tables: {result.content[0].text}")


if __name__ == "__main__":
    asyncio.run(_self_test())
PYEOF
```

---

## 10. Create the Agent

```bash
cat > src/agent.py << 'PYEOF'
"""Text2SQL Agent — ReAct loop wiring OpenAI LLM to MCP tools."""

import asyncio
import json
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from mcp_client import MCPClient

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("text2sql-agent")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_ITERATIONS = 15

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
  - Use SQLite syntax (e.g., || for concatenation, not CONCAT).

OUTPUT FORMAT:
Always respond with:
  1. The SQL query you generated
  2. The query result
  3. A short natural-language summary of the answer
"""


def _mcp_tools_to_openai_schema(tools) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


async def run_agent_loop(client: MCPClient, openai_client: OpenAI) -> None:
    mcp_tools = await client.list_tools()
    openai_tools = _mcp_tools_to_openai_schema(mcp_tools)
    tool_names = [t.name for t in mcp_tools]

    print("\n" + "=" * 60)
    print("  🗄️  Text2SQL Agent — powered by MCP")
    print("=" * 60)
    print(f"  Model:  {OPENAI_MODEL}")
    print(f"  Tools:  {tool_names}")
    print("  Type 'quit' or 'exit' to stop.\n")

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
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

        for iteration in range(MAX_ITERATIONS):
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.0,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )
            assistant_msg = response.choices[0].message

            if not assistant_msg.tool_calls:
                print(f"\n🤖 Agent:\n{assistant_msg.content}\n")
                messages.append({"role": "assistant", "content": assistant_msg.content})
                break

            messages.append(assistant_msg.model_dump())

            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                print(f"  🔧 [{iteration + 1}] Calling {fn_name}({json.dumps(fn_args)}) ...")

                try:
                    result = await client.call_tool(fn_name, fn_args)
                    tool_output = result.content[0].text if result.content else "(empty)"
                except Exception as e:
                    tool_output = f"Error: {e}"
                    logger.error(f"Tool call failed: {e}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_output,
                })
        else:
            print("⚠️  Max iterations reached.")


async def main() -> None:
    if not OPENAI_API_KEY:
        print("❌ Error: OPENAI_API_KEY not set. Copy .env.example → .env and add your key.")
        sys.exit(1)

    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    async with MCPClient(
        command="python",
        args=["src/mcp_server.py"],
    ) as mcp_client:
        await run_agent_loop(mcp_client, openai_client)


if __name__ == "__main__":
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
EOF

cp .env.example .env
open -e .env
```

**In the TextEdit window that opens**, change `sk-your-key-here` to your actual OpenAI API key. Save (`⌘S`) and close.

Verify:

```bash
python -c "
from dotenv import load_dotenv; import os; load_dotenv()
key = os.getenv('OPENAI_API_KEY', '')
print(f'✅ Key loaded ({key[:8]}...{key[-4:]})' if key.startswith('sk-') else '❌ Key not set')
"
```

---

## 12. Create Tests

```bash
cat > tests/test_tools.py << 'PYEOF'
"""Unit tests for the 3 MCP tools. No API key needed."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "sample.db")
os.environ["DATABASE_PATH"] = DB_PATH

from mcp_server import list_tables, get_table_schema, execute_sql


class TestListTables:
    def test_returns_list(self):
        assert isinstance(list_tables(), list)

    def test_contains_expected_tables(self):
        tables = list_tables()
        assert "employees" in tables
        assert "customers" in tables
        assert "orders" in tables


class TestGetTableSchema:
    def test_employees_columns(self):
        cols = [c["name"] for c in get_table_schema("employees")]
        assert "name" in cols and "salary" in cols and "department" in cols

    def test_invalid_table_raises(self):
        with pytest.raises(ValueError, match="not found"):
            get_table_schema("nonexistent_xyz")

    def test_sql_injection_rejected(self):
        with pytest.raises(ValueError, match="Invalid table name"):
            get_table_schema("employees; DROP TABLE employees")


class TestExecuteSQL:
    def test_count_employees(self):
        assert "8" in execute_sql("SELECT COUNT(*) FROM employees")

    def test_eur_customers(self):
        assert "4" in execute_sql("SELECT COUNT(*) FROM customers WHERE currency = 'EUR'")

    def test_join_query(self):
        result = execute_sql(
            "SELECT c.name, o.product FROM orders o "
            "JOIN customers c ON o.customer_id = c.id WHERE c.country = 'Germany'"
        )
        assert "Acme GmbH" in result

    def test_delete_rejected(self):
        with pytest.raises(ValueError, match="forbidden"):
            execute_sql("DELETE FROM employees WHERE id = 1")

    def test_drop_rejected(self):
        with pytest.raises(ValueError, match="forbidden"):
            execute_sql("DROP TABLE employees")

    def test_empty_result(self):
        assert "no rows" in execute_sql(
            "SELECT * FROM employees WHERE city = 'Atlantis'"
        ).lower()
PYEOF
```

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
python -m pytest tests/test_tools.py -v
```

**Expected:**

```
tests/test_tools.py::TestListTables::test_returns_list PASSED
tests/test_tools.py::TestListTables::test_contains_expected_tables PASSED
tests/test_tools.py::TestGetTableSchema::test_employees_columns PASSED
tests/test_tools.py::TestGetTableSchema::test_invalid_table_raises PASSED
tests/test_tools.py::TestGetTableSchema::test_sql_injection_rejected PASSED
tests/test_tools.py::TestExecuteSQL::test_count_employees PASSED
tests/test_tools.py::TestExecuteSQL::test_eur_customers PASSED
tests/test_tools.py::TestExecuteSQL::test_join_query PASSED
tests/test_tools.py::TestExecuteSQL::test_delete_rejected PASSED
tests/test_tools.py::TestExecuteSQL::test_drop_rejected PASSED
tests/test_tools.py::TestExecuteSQL::test_empty_result PASSED

11 passed
```

No API key needed for this step.

---

## 16. Test MCP Client ↔ Server Connection

```bash
python src/mcp_client.py
```

**Expected:**

```
✅ Connected. Available tools: ['list_tables', 'get_table_schema', 'execute_sql']
📋 Tables: ["customers", "employees", "orders"]
```

This proves the MCP stdio transport works. No API key needed.

---

## 17. Run the Interactive Agent

```bash
cd src
python agent.py
```

**Expected startup:**

```
============================================================
  🗄️  Text2SQL Agent — powered by MCP
============================================================
  Model:  gpt-4o-mini
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

> **Important:** Run `agent.py` from inside the `src/` directory. The MCP server subprocess is spawned with the path `src/mcp_server.py` relative to the project root.

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
uv add mcp openai python-dotenv pydantic httpx
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
python -m pytest tests/test_tools.py -v

# ── MCP connection test (no API key needed) ──────────────
python src/mcp_client.py

# ── Run the agent ────────────────────────────────────────
cd src
python agent.py
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
| `Server process exited` | Run `python src/mcp_server.py` standalone to see the error |
| `RateLimitError` | Wait 60s and retry, or check billing at platform.openai.com/usage |
| Tests fail with import error | Make sure you're in the project root with venv active |

---

*Built for Google Startup School AI Engineering course.*
