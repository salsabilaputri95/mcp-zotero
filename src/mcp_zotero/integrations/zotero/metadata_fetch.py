"""Ambil metadata Crossref / Unpaywall dan isi template Zotero."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


async def fetch_crossref_work(doi: str, mailto: str) -> dict[str, Any]:
    if not mailto:
        raise RuntimeError("Set CROSSREF_MAILTO di `.env` (email kontak untuk Crossref).")
    doi = doi.strip()
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    headers = {"User-Agent": f"mcp-zotero/0.1 (mailto:{mailto})"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 404:
            raise RuntimeError(f"DOI tidak ditemukan di Crossref: {doi}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Crossref HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
    msg = data.get("message") or {}
    if not isinstance(msg, dict):
        raise RuntimeError("Respons Crossref tidak valid.")
    return msg


async def fetch_unpaywall_pdf_url(doi: str, email: str) -> str | None:
    if not email:
        return None
    doi = doi.strip()
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={quote(email)}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        if resp.status_code >= 400:
            return None
        data = resp.json()
    loc = data.get("best_oa_location") or {}
    if isinstance(loc, dict):
        u = loc.get("url_for_pdf") or loc.get("url")
        if isinstance(u, str) and u.startswith("http"):
            return u
    return None


def crossref_message_to_zotero_journal_article(
    template: dict[str, Any],
    msg: dict[str, Any],
    *,
    doi: str,
) -> dict[str, Any]:
    """Isi template `items/new` journalArticle dari objek Crossref `message`."""
    item = dict(template)
    item["itemType"] = "journalArticle"
    titles = msg.get("title") or []
    item["title"] = titles[0] if titles else item.get("title") or ""
    item["DOI"] = (msg.get("DOI") or doi).strip()
    if msg.get("URL"):
        item["url"] = str(msg["URL"])
    container = msg.get("container-title") or []
    if container:
        item["publicationTitle"] = str(container[0])
    if msg.get("ISSN"):
        issn = msg["ISSN"]
        item["ISSN"] = issn[0] if isinstance(issn, list) else str(issn)
    issued = (msg.get("issued") or {}).get("date-parts") or []
    if issued and isinstance(issued[0], list) and issued[0]:
        try:
            item["date"] = str(issued[0][0])
        except (IndexError, TypeError):
            pass
    if msg.get("volume"):
        item["volume"] = str(msg["volume"])
    if msg.get("issue"):
        item["issue"] = str(msg["issue"])
    page = msg.get("page")
    if page:
        item["pages"] = str(page)
    abstract = msg.get("abstract")
    if isinstance(abstract, str) and abstract.strip():
        # Crossref kadang bungkus JATS; ambil teks kasar
        text = abstract.replace("<jats:p>", "\n").replace("</jats:p>", "\n")
        text = text.replace("<", " <")
        item["abstractNote"] = " ".join(text.split())
    creators: list[dict[str, Any]] = []
    for a in (msg.get("author") or [])[:40]:
        if not isinstance(a, dict):
            continue
        fam = (a.get("family") or "").strip()
        giv = (a.get("given") or "").strip()
        if not fam and not giv:
            continue
        creators.append({"creatorType": "author", "firstName": giv, "lastName": fam})
    if creators:
        item["creators"] = creators
    return item
