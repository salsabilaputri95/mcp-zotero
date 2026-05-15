"""Prompt MCP bawaan."""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.prompt(name="review_snippet", description="")
    def review_snippet(code: str) -> str:
        return ()

