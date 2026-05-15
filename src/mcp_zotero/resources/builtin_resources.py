"""Resource MCP read-only bawaan."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.resource("project://about")
    def about() -> str:
        return ()

