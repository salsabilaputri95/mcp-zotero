"""Utilitas PDF: ekstraksi DOI dan kerangka (outline)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


def extract_doi_from_pdf(path: str | Path, *, max_pages: int = 5) -> str | None:
    p = Path(path)
    reader = PdfReader(str(p))
    for page in reader.pages[:max_pages]:
        text = page.extract_text() or ""
        m = _DOI_RE.search(text)
        if m:
            return m.group(0).strip().rstrip(").,]")
    return None


def extract_pdf_outline(path: str | Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(path))
    rows: list[dict[str, Any]] = []

    def walk(node: Any, depth: int) -> None:
        if node is None:
            return
        if isinstance(node, list):
            for x in node:
                walk(x, depth)
            return
        title = getattr(node, "title", None)
        if title is None and isinstance(node, dict):
            title = node.get("/Title")
        if title is not None:
            rows.append({"depth": depth, "title": str(title)})
        children = getattr(node, "children", None)
        if children:
            walk(children, depth + 1)

    walk(reader.outline, 0)
    return rows
