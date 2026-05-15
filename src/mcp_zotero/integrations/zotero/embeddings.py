"""Panggilan embedding OpenAI-compatible (REST)."""

from __future__ import annotations

from typing import Any

import httpx

from mcp_zotero.config.settings import Settings


async def embed_texts(settings: Settings, texts: list[str]) -> list[list[float]]:
    if not settings.embedding_api_key:
        raise RuntimeError(
            "EMBEDDING_API_KEY kosong — isi `.env` untuk pencarian semantik "
            "(lihat `.env.example`)."
        )
    url = f"{settings.embedding_base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.embedding_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": settings.embedding_model,
        "input": texts,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Embedding API HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
    out = data.get("data") or []
    try:
        out_sorted = sorted(out, key=lambda x: x.get("index", 0))
    except TypeError:
        out_sorted = out
    vectors: list[list[float]] = []
    for row in out_sorted:
        vec = row.get("embedding")
        if not isinstance(vec, list):
            raise RuntimeError("Format embedding tidak dikenali.")
        vectors.append([float(x) for x in vec])
    if len(vectors) != len(texts):
        raise RuntimeError("Jumlah vektor embedding tidak cocok dengan jumlah teks.")
    return vectors


async def embed_text(settings: Settings, text: str) -> list[float]:
    vecs = await embed_texts(settings, [text])
    return vecs[0]
