"""Registrasi prompts MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from mcp_zotero.prompts import builtin_prompts


def register(mcp: FastMCP) -> None:
    builtin_prompts.register(mcp)
