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

from mcp_client import MCPClient

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
                "parameters": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
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
            # Append the assistant message (with tool_calls) to history
            messages.append(assistant_msg.model_dump())

            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"  🔧 [{iteration + 1}] Calling {fn_name}({json.dumps(fn_args)}) ...")

                try:
                    result = await client.call_tool(fn_name, fn_args)
                    # Extract text from MCP result
                    tool_output = result.content[0].text if result.content else "(empty)"
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
