"""Tools MCP: Zotero + indeks semantik lokal."""

from __future__ import annotations

import html
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp_zotero.config.settings import require_zotero_config
from mcp_zotero.integrations.zotero.client import ZoteroClient
from mcp_zotero.integrations.zotero.duplicates import (
    find_duplicate_groups,
    merge_items_into_master,
)
from mcp_zotero.integrations.zotero.metadata_fetch import (
    crossref_message_to_zotero_journal_article,
    fetch_crossref_work,
    fetch_unpaywall_pdf_url,
)
from mcp_zotero.integrations.zotero.pdf_utils import extract_doi_from_pdf, extract_pdf_outline
from mcp_zotero.integrations.zotero.semantic_index import (
    index_status,
    semantic_search,
    update_semantic_index,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _csv_keys(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


def _doi_from_data(data: dict[str, Any]) -> str | None:
    d = (data.get("DOI") or "").strip()
    if d:
        return d
    extra = data.get("extra") or ""
    if isinstance(extra, str):
        for line in extra.splitlines():
            if line.strip().lower().startswith("doi:"):
                cand = line.split(":", 1)[1].strip()
                if cand:
                    return cand
    return None


def _citation_key_from_extra(extra: str | None) -> str | None:
    if not extra:
        return None
    for line in extra.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith("citation key:") or low.startswith("citation key :"):
            parts = s.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
    return None


def _unwrap_data(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    if isinstance(raw, dict):
        return raw
    return {}


async def _add_by_doi_impl(doi: str, attach_oa_pdf: bool) -> dict[str, Any]:
    s = require_zotero_config()
    z = ZoteroClient(s)
    msg = await fetch_crossref_work(doi, s.crossref_mailto)
    tpl = await z.new_item_template("journalArticle")
    item = crossref_message_to_zotero_journal_article(tpl, msg, doi=doi)
    created = await z.write_items([item])
    parent_key = None
    if isinstance(created, dict) and created.get("successful"):
        sk = created["successful"].get("0")
        if isinstance(sk, dict):
            parent_key = sk.get("key")
    pdf_url = None
    if attach_oa_pdf and s.unpaywall_email:
        pdf_url = await fetch_unpaywall_pdf_url(doi, s.unpaywall_email)
    att_resp = None
    if pdf_url and parent_key:
        att = {
            "itemType": "attachment",
            "linkMode": "linked_url",
            "url": pdf_url,
            "title": "Full Text PDF",
            "parentItem": parent_key,
        }
        att_resp = await z.write_items([att])
    return {"created": created, "oa_pdf_url": pdf_url, "attachment": att_resp}


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="zotero_semantic_search")
    async def zotero_semantic_search(query: str, top_k: int = 10) -> dict[str, Any]:
        """Pencarian kemiripan semantik di indeks lokal (embedding)."""
        require_zotero_config()
        return await semantic_search(query, top_k=top_k)

    @mcp.tool(name="zotero_update_search_database")
    async def zotero_update_search_database(max_items: int | None = None) -> dict[str, Any]:
        """Membangun ulang indeks SQLite + vektor untuk item top-level Zotero."""
        require_zotero_config()
        return await update_semantic_index(max_items=max_items)

    @mcp.tool(name="zotero_get_search_database_status")
    async def zotero_get_search_database_status() -> dict[str, Any]:
        """Status file DB indeks semantik dan konfigurasi embedding."""
        require_zotero_config()
        return index_status()

    @mcp.tool(name="zotero_search_items")
    async def zotero_search_items(
        q: str,
        limit: int = 25,
        start: int = 0,
        qmode: str = "titleCreatorYear",
    ) -> dict[str, Any]:
        """Pencarian cepat judul/penulis/kreator (qmode: titleCreatorYear | everything)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        status, headers, data = await z.get_items(
            subpath="/items",
            params={"q": q, "limit": min(limit, 100), "start": start, "qmode": qmode},
        )
        return {
            "status": status,
            "total_results": headers.get("Total-Results"),
            "items": data,
        }

    @mcp.tool(name="zotero_advanced_search")
    async def zotero_advanced_search(
        q: str = "",
        tag: str = "",
        item_type: str = "",
        qmode: str = "titleCreatorYear",
        collection_key: str = "",
        sort: str = "dateModified",
        direction: str = "desc",
        limit: int = 25,
        start: int = 0,
    ) -> dict[str, Any]:
        """Pencarian item dengan kombinasi q, tag, itemType, dan opsional koleksi."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "start": start,
            "sort": sort,
            "direction": direction,
            "qmode": qmode,
        }
        if q:
            params["q"] = q
        if tag:
            params["tag"] = tag
        if item_type:
            params["itemType"] = item_type
        sub = "/items"
        if collection_key.strip():
            sub = f"/collections/{collection_key.strip()}/items"
        status, headers, data = await z.get_items(subpath=sub, params=params)
        return {
            "status": status,
            "total_results": headers.get("Total-Results"),
            "items": data,
        }

    @mcp.tool(name="zotero_get_collections")
    async def zotero_get_collections(top_only: bool = False) -> Any:
        """Daftar koleksi (top_only=True hanya level atas)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        return await z.get_collections(top=top_only)

    @mcp.tool(name="zotero_get_collection_items")
    async def zotero_get_collection_items(
        collection_key: str,
        limit: int = 25,
        start: int = 0,
        top_only: bool = False,
    ) -> dict[str, Any]:
        """Item dalam sebuah koleksi."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        sub = (
            f"/collections/{collection_key}/items/top"
            if top_only
            else f"/collections/{collection_key}/items"
        )
        status, headers, data = await z.get_items(
            subpath=sub, params={"limit": min(limit, 100), "start": start}
        )
        return {"status": status, "total_results": headers.get("Total-Results"), "items": data}

    @mcp.tool(name="zotero_get_tags")
    async def zotero_get_tags(
        q: str = "",
        qmode: str = "contains",
        limit: int = 100,
    ) -> Any:
        """Daftar tag (q opsional)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if q:
            params["q"] = q
            params["qmode"] = qmode
        return await z.get_tags(params=params)

    @mcp.tool(name="zotero_get_recent")
    async def zotero_get_recent(limit: int = 20) -> dict[str, Any]:
        """Item terbaru berdasarkan dateAdded."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        status, headers, data = await z.get_items(
            subpath="/items",
            params={
                "limit": min(limit, 100),
                "sort": "dateAdded",
                "direction": "desc",
            },
        )
        return {"status": status, "total_results": headers.get("Total-Results"), "items": data}

    @mcp.tool(name="zotero_search_by_tag")
    async def zotero_search_by_tag(tag: str, limit: int = 25, start: int = 0) -> dict[str, Any]:
        """Filter pustaka dengan tag tertentu (parameter API `tag`)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        status, headers, data = await z.get_items(
            subpath="/items",
            params={"tag": tag, "limit": min(limit, 100), "start": start},
        )
        return {"status": status, "total_results": headers.get("Total-Results"), "items": data}

    @mcp.tool(name="zotero_get_item_metadata")
    async def zotero_get_item_metadata(item_key: str, format: str = "json") -> Any:
        """Metadata item; format=`json` (data Zotero) atau `bibtex` (string BibTeX)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        fmt = format.strip().lower()
        if fmt == "bibtex":
            return await z.get_item_bibtex(item_key)
        return await z.get_item(item_key, params={"format": "json"})

    @mcp.tool(name="zotero_get_item_fulltext")
    async def zotero_get_item_fulltext(item_key: str) -> Any:
        """Konten teks lengkap yang diindeks Zotero untuk item tersebut."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        return await z.get_fulltext(item_key)

    @mcp.tool(name="zotero_get_item_children")
    async def zotero_get_item_children(item_key: str) -> Any:
        """Lampiran, catatan, dan anak item lain."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        return await z.get_children(item_key)

    @mcp.tool(name="zotero_get_annotations")
    async def zotero_get_annotations(parent_item_key: str) -> list[dict[str, Any]]:
        """Anotasi (itemType annotation) di bawah induk (biasanya entri PDF)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        ch = await z.get_children(parent_item_key)
        if not isinstance(ch, list):
            return []
        out: list[dict[str, Any]] = []
        for row in ch:
            if not isinstance(row, dict):
                continue
            data = row.get("data") or {}
            if isinstance(data, dict) and data.get("itemType") == "annotation":
                out.append(row)
        return out

    @mcp.tool(name="zotero_get_notes")
    async def zotero_get_notes(parent_item_key: str = "", limit: int = 50) -> Any:
        """Catatan: kosongkan parent_item_key untuk catatan top-level; isi untuk catatan anak."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        if not parent_item_key.strip():
            status, headers, data = await z.get_items(
                subpath="/items",
                params={"itemType": "note", "limit": min(limit, 100)},
            )
            return {"status": status, "total_results": headers.get("Total-Results"), "items": data}
        ch = await z.get_children(parent_item_key.strip())
        if not isinstance(ch, list):
            return []
        return [
            r
            for r in ch
            if isinstance(r, dict) and (r.get("data") or {}).get("itemType") == "note"
        ]

    @mcp.tool(name="zotero_search_notes")
    async def zotero_search_notes(q: str, limit: int = 25) -> dict[str, Any]:
        """Cari di catatan & konten terindeks (qmode everything)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        status, headers, data = await z.get_items(
            subpath="/items",
            params={
                "q": q,
                "itemType": "note || annotation",
                "qmode": "everything",
                "limit": min(limit, 100),
            },
        )
        return {"status": status, "total_results": headers.get("Total-Results"), "items": data}

    @mcp.tool(name="zotero_create_note")
    async def zotero_create_note(item_key: str, note_text: str) -> Any:
        """Buat catatan baru (HTML ringkas) di bawah item induk (beta)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        safe = html.escape(note_text, quote=True)
        body = f"<p>{safe}</p>"
        note_item = {
            "itemType": "note",
            "note": body,
            "parentItem": item_key,
            "tags": [],
        }
        return await z.write_items([note_item])

    @mcp.tool(name="zotero_add_by_doi")
    async def zotero_add_by_doi(doi: str, attach_oa_pdf: bool = True) -> dict[str, Any]:
        """Tambah artikel dari DOI (Crossref) + opsional lampiran URL PDF dari Unpaywall."""
        return await _add_by_doi_impl(doi, attach_oa_pdf)

    @mcp.tool(name="zotero_add_from_file")
    async def zotero_add_from_file(
        file_path: str,
        collection_key: str = "",
    ) -> dict[str, Any]:
        """Impor PDF/EPUB: ekstrak DOI dari PDF; jika ada, tambah via DOI + lampiran lokal."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        p = Path(file_path).expanduser()
        if not p.is_file():
            return {"error": f"Berkas tidak ada: {p}"}
        doi = None
        if p.suffix.lower() == ".pdf":
            doi = extract_doi_from_pdf(p)
        if doi:
            add_res = await _add_by_doi_impl(doi, attach_oa_pdf=True)
            parent_key = None
            cr = add_res.get("created")
            if isinstance(cr, dict) and cr.get("successful"):
                sk = cr["successful"].get("0")
                if isinstance(sk, dict):
                    parent_key = sk.get("key")
            att = None
            if parent_key:
                att_item = {
                    "itemType": "attachment",
                    "linkMode": "linked_file",
                    "title": p.name,
                    "path": str(p.resolve()),
                    "parentItem": parent_key,
                }
                att = await z.write_items([att_item])
            if collection_key.strip() and parent_key:
                await z.add_items_to_collection(collection_key.strip(), [parent_key])
            return {"mode": "doi", "doi": doi, "add_by_doi": add_res, "linked_file_attachment": att}
        tpl = await z.new_item_template("document")
        tpl["title"] = p.stem
        tpl["url"] = ""
        created = await z.write_items([tpl])
        parent_key = None
        if isinstance(created, dict) and created.get("successful"):
            sk = created["successful"].get("0")
            if isinstance(sk, dict):
                parent_key = sk.get("key")
        att = None
        if parent_key:
            att_item = {
                "itemType": "attachment",
                "linkMode": "linked_file",
                "title": p.name,
                "path": str(p.resolve()),
                "parentItem": parent_key,
            }
            att = await z.write_items([att_item])
        if collection_key.strip() and parent_key:
            await z.add_items_to_collection(collection_key.strip(), [parent_key])
        return {
            "mode": "fallback_document",
            "message": "DOI tidak ditemukan di PDF; dibuat entri document + lampiran lokal.",
            "created": created,
            "linked_file_attachment": att,
        }

    @mcp.tool(name="zotero_create_collection")
    async def zotero_create_collection(
        name: str,
        parent_collection_key: str = "",
    ) -> Any:
        """Buat koleksi; parent_collection_key kosong = koleksi tingkat atas."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        return await z.create_collection(
            name,
            parent_collection=parent_collection_key.strip() or None,
        )

    @mcp.tool(name="zotero_manage_collections")
    async def zotero_manage_collections(
        action: str,
        collection_key: str,
        item_keys_csv: str,
    ) -> dict[str, Any]:
        """action=`add` atau `remove`; item_keys_csv=kunci dipisah koma."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        keys = _csv_keys(item_keys_csv)
        act = action.strip().lower()
        if act == "add":
            await z.add_items_to_collection(collection_key, keys)
        elif act == "remove":
            await z.remove_items_from_collection(collection_key, keys)
        else:
            return {"error": "action harus `add` atau `remove`."}
        return {"ok": True, "action": act, "count": len(keys)}

    @mcp.tool(name="zotero_find_duplicates")
    async def zotero_find_duplicates(
        by: str = "doi,title",
        max_scan: int = 800,
    ) -> dict[str, Any]:
        """Temukan duplikat berdasarkan DOI dan/atau judul (scan item top)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        return await find_duplicate_groups(z, by=by, max_scan=max_scan)

    @mcp.tool(name="zotero_merge_duplicates")
    async def zotero_merge_duplicates(
        master_key: str,
        duplicate_keys_csv: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Gabungkan duplikat: pindahkan anak ke master lalu hapus duplikat."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        dups = _csv_keys(duplicate_keys_csv)
        return await merge_items_into_master(
            z, master_key=master_key, duplicate_keys=dups, dry_run=dry_run
        )

    @mcp.tool(name="zotero_get_pdf_outline")
    async def zotero_get_pdf_outline(attachment_item_key: str) -> dict[str, Any]:
        """Unduh lampiran PDF dari Zotero, lalu ekstrak outline (daftar isi) dengan pypdf."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        raw = await z.get_item(attachment_item_key)
        data = _unwrap_data(raw)
        if data.get("itemType") != "attachment":
            return {"error": "Bukan item attachment."}
        if (data.get("contentType") or "").lower() != "application/pdf" and not str(
            data.get("filename", "")
        ).lower().endswith(".pdf"):
            return {"warning": "Mungkin bukan PDF; mencoba tetap parse."}
        pdf_bytes = await z.download_file_bytes(attachment_item_key)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            outline = extract_pdf_outline(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return {"attachment_item_key": attachment_item_key, "outline": outline}

    @mcp.tool(name="zotero_search_by_citation_key")
    async def zotero_search_by_citation_key(
        citation_key: str,
        max_scan: int = 500,
    ) -> dict[str, Any]:
        """Cari Better BibTeX citation key di kolom `extra` (Citation Key: …)."""
        s = require_zotero_config()
        z = ZoteroClient(s)
        want = citation_key.strip().lower()
        hits: list[dict[str, Any]] = []
        start = 0
        limit = 100
        scanned = 0
        while scanned < max_scan:
            status, _, items = await z.get_items(
                subpath="/items/top",
                params={"limit": min(limit, max_scan - scanned), "start": start},
            )
            if status >= 400 or not isinstance(items, list) or not items:
                break
            for row in items:
                if scanned >= max_scan:
                    break
                scanned += 1
                if not isinstance(row, dict):
                    continue
                data = row.get("data") or {}
                if not isinstance(data, dict):
                    continue
                ck = _citation_key_from_extra(data.get("extra"))
                if ck and ck.lower() == want:
                    hits.append(
                        {
                            "key": row.get("key"),
                            "title": data.get("title"),
                            "extra": data.get("extra"),
                        }
                    )
            if len(items) < limit:
                break
            start += limit
        return {"citation_key": citation_key, "scanned": scanned, "matches": hits}
