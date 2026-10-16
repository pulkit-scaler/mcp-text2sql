"""
End-to-end test of the agent loop without an OpenAI key.

A scripted stand-in for the OpenAI client replays the tool calls a real model
makes for "How many customers pay in EUR?". Everything else is real: agent.py's
ReAct loop, the MCP client, the MCP server subprocess over stdio, and SQLite.

Run:  uv run python -m pytest tests/test_agent_loop.py -v
"""

import json
import sys
from pathlib import Path

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage, ChatCompletionMessageFunctionToolCall

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import agent  # noqa: E402
from mcp_client import MCPClient  # noqa: E402

QUESTION = "How many customers pay in EUR?"
SCRIPT = [
    ("list_tables", {}),
    ("get_table_schema", {"table_name": "customers"}),
    ("execute_sql", {"query": "SELECT COUNT(*) AS eur_count FROM customers WHERE currency = 'EUR'"}),
    ("execute_sql", {"query": "DROP TABLE customers"}),
]
FINAL_ANSWER = "There are 4 customers who pay in EUR."


def _completion(message: ChatCompletionMessage) -> ChatCompletion:
    return ChatCompletion(
        id="scripted",
        object="chat.completion",
        created=0,
        model="scripted",
        choices=[{"index": 0, "finish_reason": "stop", "message": message}],
    )


class ScriptedOpenAI:
    """Mimics openai_client.chat.completions.create(), one scripted step per call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs) -> ChatCompletion:
        self.calls.append(kwargs)
        step = len(self.calls) - 1
        if step < len(SCRIPT):
            name, args = SCRIPT[step]
            tool_call = ChatCompletionMessageFunctionToolCall(
                id=f"call_{step}", type="function", function={"name": name, "arguments": json.dumps(args)}
            )
            return _completion(ChatCompletionMessage(role="assistant", content=None, tool_calls=[tool_call]))
        return _completion(ChatCompletionMessage(role="assistant", content=FINAL_ANSWER))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_agent_loop_end_to_end(monkeypatch, capsys):
    answers = iter([QUESTION, "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    llm = ScriptedOpenAI()

    async with MCPClient(command=sys.executable, args=[str(PROJECT_ROOT / "src" / "mcp_server.py")]) as client:
        await agent.run_agent_loop(client, llm)

    # The LLM was offered the MCP tools in OpenAI function-calling format
    offered = [t["function"]["name"] for t in llm.calls[0]["tools"]]
    assert offered == ["list_tables", "get_table_schema", "execute_sql"]
    assert llm.calls[0]["tools"][1]["function"]["parameters"]["required"] == ["table_name"]

    # What the model read back from each tool call (the final request carries the full history)
    tool_msgs = [m["content"] for m in llm.calls[-1]["messages"] if m["role"] == "tool"]
    assert tool_msgs[0].split("\n") == ["customers", "employees", "orders"]  # every table, not just the first
    assert all(f'"{c}"' in tool_msgs[1] for c in ["id", "name", "country", "currency", "balance"])
    assert tool_msgs[2].splitlines()[-1] == "4"
    assert "forbidden keyword: DROP" in tool_msgs[3]  # the guardrail's message reaches the model

    out = capsys.readouterr().out
    assert "protocol 2026-07-28" in out
    assert FINAL_ANSWER in out
