"""Registrasi semua tools ke instance FastMCP."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from . import zotero_tools


def register(mcp: FastMCP) -> None:
    """Daftarkan modul tools."""
    zotero_tools.register(mcp)
