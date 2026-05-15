"""Registrasi resources MCP."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from mcp_zotero.resources import builtin_resources


def register(mcp: FastMCP) -> None:
    builtin_resources.register(mcp)
