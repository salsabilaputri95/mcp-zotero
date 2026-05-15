"""Indeks SQLite untuk pencarian semantik (vektor + metadata ringkas)."""

from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from mcp_zotero.config.settings import default_semantic_db_path, get_settings
from mcp_zotero.integrations.zotero.client import ZoteroClient
from mcp_zotero.integrations.zotero.embeddings import embed_texts


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS doc_index (
            item_key TEXT PRIMARY KEY,
            library_version INTEGER,
            fingerprint TEXT,
            title TEXT,
            snippet TEXT,
            dim INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _row_fp(title: str, snippet: str) -> str:
    return f"{title}\n{snippet}"[:8000]


def _item_to_text(data: dict[str, Any]) -> tuple[str, str, str]:
    title = (data.get("title") or "").strip() or "(tanpa judul)"
    parts: list[str] = [title]
    if data.get("abstractNote"):
        parts.append(str(data["abstractNote"]))
    if data.get("publicationTitle"):
        parts.append(str(data["publicationTitle"]))
    if data.get("DOI"):
        parts.append(f"DOI: {data['DOI']}")
    creators = data.get("creators") or []
    c_strs: list[str] = []
    for c in creators[:12]:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        if name:
            c_strs.append(str(name))
            continue
        first = (c.get("firstName") or "").strip()
        last = (c.get("lastName") or "").strip()
        if first or last:
            c_strs.append(f"{first} {last}".strip())
    if c_strs:
        parts.append("Penulis: " + "; ".join(c_strs))
    text = "\n".join(parts)
    snippet = text[:2000]
    return title, snippet, text


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


async def update_semantic_index(
    db_path: Path | None = None,
    *,
    max_items: int | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    path = db_path or default_semantic_db_path()
    client = ZoteroClient(settings)
    conn = await asyncio.to_thread(_connect, path)
    start = time.time()
    collected: list[tuple[str, int, str, str, str]] = []
    start_param = 0
    limit = 100
    total_seen = 0
    lib_ver = 0
    try:
        while True:
            status, headers, items = await client.get_items(
                subpath="/items/top",
                params={"limit": limit, "start": start_param, "format": "json"},
            )
            if status >= 400:
                raise RuntimeError(f"Gagal mengambil items/top: HTTP {status}")
            if not isinstance(items, list) or not items:
                break
            try:
                lib_ver = int(headers.get("Last-Modified-Version", "0"))
            except ValueError:
                lib_ver = 0
            for row in items:
                if max_items is not None and total_seen >= max_items:
                    break
                total_seen += 1
                if not isinstance(row, dict):
                    continue
                key = row.get("key")
                data = row.get("data")
                if not key or not isinstance(data, dict):
                    continue
                itype = data.get("itemType")
                if itype in ("attachment", "note", "annotation"):
                    continue
                title, snippet, _text = _item_to_text(data)
                fp = _row_fp(title, snippet)
                collected.append((str(key), lib_ver, fp, title, snippet))
            if max_items is not None and total_seen >= max_items:
                break
            if len(items) < limit:
                break
            start_param += limit

        if not collected:

            def _empty_meta() -> None:
                conn.execute(
                    "INSERT OR REPLACE INTO meta (k,v) VALUES (?,?)",
                    ("last_update_status", "no_items"),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO meta (k,v) VALUES (?,?)",
                    ("last_update_at", str(time.time())),
                )
                conn.commit()

            await asyncio.to_thread(_empty_meta)
            conn.close()
            return {
                "indexed": 0,
                "seconds": round(time.time() - start, 3),
                "message": "Tidak ada item top-level untuk diindeks.",
            }

        batch_size = 16
        indexed = 0
        for i in range(0, len(collected), batch_size):
            chunk = collected[i : i + batch_size]
            texts = [c[2] for c in chunk]
            vectors = await embed_texts(settings, texts)
            for (key, lv, _fp, title, snippet), vec in zip(chunk, vectors, strict=True):

                def _upsert(
                    key_b: str = key,
                    lv_b: int = lv,
                    fp_b: str = _fp,
                    title_b: str = title,
                    snippet_b: str = snippet,
                    vec_b: list[float] = vec,
                ) -> None:
                    conn.execute(
                        """
                        INSERT INTO doc_index (
                            item_key, library_version, fingerprint, title, snippet,
                            dim, vector_json, updated_at
                        )
                        VALUES (?,?,?,?,?,?,?,?)
                        ON CONFLICT(item_key) DO UPDATE SET
                            library_version=excluded.library_version,
                            fingerprint=excluded.fingerprint,
                            title=excluded.title,
                            snippet=excluded.snippet,
                            dim=excluded.dim,
                            vector_json=excluded.vector_json,
                            updated_at=excluded.updated_at
                        """,
                        (
                            key_b,
                            lv_b,
                            fp_b,
                            title_b,
                            snippet_b,
                            len(vec_b),
                            json.dumps(vec_b),
                            time.time(),
                        ),
                    )
                    conn.commit()

                await asyncio.to_thread(_upsert)
                indexed += 1

        def _finalize() -> None:
            conn.execute(
                "INSERT OR REPLACE INTO meta (k,v) VALUES (?,?)",
                ("last_library_version", str(lib_ver)),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (k,v) VALUES (?,?)",
                ("last_update_at", str(time.time())),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (k,v) VALUES (?,?)",
                ("last_update_status", "ok"),
            )
            conn.commit()
            conn.close()

        await asyncio.to_thread(_finalize)
        return {
            "indexed": indexed,
            "seconds": round(time.time() - start, 3),
            "library_version": lib_ver,
            "db_path": str(path),
        }
    except Exception:
        conn.close()
        raise


async def semantic_search(
    query: str, top_k: int = 10, db_path: Path | None = None
) -> dict[str, Any]:
    settings = get_settings()
    path = db_path or default_semantic_db_path()
    qvec = await embed_texts(settings, [query])
    q = qvec[0]

    def _load_all() -> list[tuple[str, str, str, list[float]]]:
        c = _connect(path)
        cur = c.execute("SELECT item_key, title, snippet, vector_json FROM doc_index")
        rows = []
        for key, title, snippet, vj in cur.fetchall():
            try:
                vec = json.loads(vj)
            except json.JSONDecodeError:
                continue
            if isinstance(vec, list):
                rows.append(
                    (str(key), str(title or ""), str(snippet or ""), [float(x) for x in vec])
                )
        c.close()
        return rows

    all_rows = await asyncio.to_thread(_load_all)
    scored: list[tuple[float, str, str, str]] = []
    for key, title, snippet, vec in all_rows:
        scored.append((_cosine(q, vec), key, title, snippet))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: max(1, top_k)]
    return {
        "query": query,
        "results": [
            {"score": round(s, 6), "item_key": k, "title": t, "snippet": sn[:500]}
            for s, k, t, sn in top
        ],
    }


def index_status(db_path: Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    path = db_path or default_semantic_db_path()
    if not path.is_file():
        return {
            "db_path": str(path),
            "exists": False,
            "rows": 0,
            "embedding_model": settings.embedding_model,
            "embedding_base_url": settings.embedding_base_url,
            "embedding_configured": bool(settings.embedding_api_key),
        }
    conn = _connect(path)
    n = conn.execute("SELECT COUNT(*) FROM doc_index").fetchone()[0]
    meta_rows = dict(conn.execute("SELECT k,v FROM meta").fetchall())
    conn.close()
    return {
        "db_path": str(path),
        "exists": True,
        "rows": int(n),
        "meta": meta_rows,
        "embedding_model": settings.embedding_model,
        "embedding_base_url": settings.embedding_base_url,
        "embedding_configured": bool(settings.embedding_api_key),
    }
