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
