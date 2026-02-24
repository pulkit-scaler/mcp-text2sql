"""
MCP Client — Thin wrapper over mcp.ClientSession via stdio transport.

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

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl

logger = logging.getLogger("text2sql-client")


class MCPClient:
    """Async-context-manager MCP client that spawns & connects to an MCP server."""

    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[dict] = None,
    ) -> None:
        self._command = command
        self._args = args
        self._env = env
        self._session: Optional[ClientSession] = None
        self._exit_stack = AsyncExitStack()

    # ── Connection lifecycle ─────────────────────────────────────
    async def connect(self) -> None:
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
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

    # ── Session accessor ─────────────────────────────────────────
    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError("Client not connected. Use 'async with MCPClient(...)' or call connect().")
        return self._session

    # ── Tool operations ──────────────────────────────────────────
    async def list_tools(self) -> list[types.Tool]:
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, tool_name: str, tool_input: dict) -> types.CallToolResult:
        logger.info(f"Calling tool: {tool_name} with input: {json.dumps(tool_input, default=str)[:200]}")
        result = await self.session.call_tool(tool_name, tool_input)
        return result

    # ── Prompt operations ────────────────────────────────────────
    async def list_prompts(self) -> list[types.Prompt]:
        result = await self.session.list_prompts()
        return result.prompts

    async def get_prompt(self, prompt_name: str, args: dict[str, str]) -> Any:
        result = await self.session.get_prompt(prompt_name, args)
        return result.messages

    # ── Resource operations ──────────────────────────────────────
    async def read_resource(self, uri: str) -> Any:
        result = await self.session.read_resource(AnyUrl(uri))
        resource = result.contents[0]
        if isinstance(resource, types.TextResourceContents):
            if resource.mimeType == "application/json":
                return json.loads(resource.text)
            return resource.text
        return resource


# ── Quick self-test ──────────────────────────────────────────────
async def _self_test() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    async with MCPClient(command="uv", args=["run", "python", "src/mcp_server.py"]) as client:
        tools = await client.list_tools()
        print(f"\n✅ Connected. Available tools: {[t.name for t in tools]}")

        # Quick tool call
        result = await client.call_tool("list_tables", {})
        print(f"📋 Tables: {result.content[0].text}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_self_test())
