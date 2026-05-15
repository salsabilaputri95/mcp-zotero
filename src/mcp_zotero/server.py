"""Titik masuk server MCP (stdio, cocok untuk Cursor / Claude Desktop)."""

from __future__ import annotations

import asyncio
import os
import sys

from mcp.server.fastmcp import FastMCP

from mcp_zotero.prompts import register as register_prompts
from mcp_zotero.resources import register as register_resources
from mcp_zotero.tools import register as register_tools


def build_mcp() -> FastMCP:
    """Buat instance FastMCP dan daftarkan tools, resources, prompts."""
    mcp = FastMCP(
        "mcp-zotero",
        instructions=(
            "Server MCP untuk proyek mcp-zotero. "
            "Gunakan tools untuk aksi; resources untuk konteks statis; prompts untuk template. "
            "Integrasi Zotero: set ZOTERO_* dan (untuk semantik) EMBEDDING_* di `.env`; indeks lokal SQLite."
        ),
    )
    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)
    return mcp


async def _doctor() -> None:
    """Cetak ringkasan tools/prompts/resources (untuk cek instalasi, bukan stdio MCP)."""
    mcp = build_mcp()
    tools = await mcp.list_tools()
    prompts = await mcp.list_prompts()
    resources = await mcp.list_resources()
    print("Tools:", ", ".join(t.name for t in tools) or "(tidak ada)")
    print("Prompts:", ", ".join(p.name for p in prompts) or "(tidak ada)")
    print("Resources:", ", ".join(str(r.uri) for r in resources) or "(tidak ada)")


def main() -> None:
    """Stdio MCP, atau ``--doctor`` untuk verifikasi tanpa klien MCP."""
    argv = sys.argv[1:]
    if "--doctor" in argv:
        asyncio.run(_doctor())
        return

    force_stdio = "--force-stdio" in argv or os.getenv("MCP_FORCE_STDIO") == "1"
    if sys.stdin.isatty() and not force_stdio:
        print(
            "Server MCP stdio tidak untuk terminal interaktif biasa: setiap Enter "
            "bukan pesan JSON-RPC sehingga muncul error validasi.\n"
            "Gunakan Cursor (mcp.json) agar stdin terhubung pipa ke klien MCP.\n"
            "Cek instalasi: python -m mcp_zotero --doctor\n"
            "Paksa mode lama (tidak disarankan): --force-stdio atau MCP_FORCE_STDIO=1",
            file=sys.stderr,
        )
        raise SystemExit(2)

    build_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
