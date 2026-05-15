"""Muat variabel lingkungan (termasuk `.env` di root proyek)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _load_dotenv_files() -> None:
    seen: set[Path] = set()
    candidates: list[Path] = [Path.cwd(), *Path(__file__).resolve().parents]
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        env_path = base / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=False)
            return


_load_dotenv_files()


@dataclass(frozen=True)
class Settings:
    zotero_api_key: str
    zotero_library_id: str
    zotero_library_type: str  # "user" | "group"

    embedding_api_key: str
    embedding_base_url: str
    embedding_model: str
    zotero_semantic_db_path: str | None

    crossref_mailto: str
    unpaywall_email: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        zotero_api_key=os.getenv("ZOTERO_API_KEY", "").strip(),
        zotero_library_id=os.getenv("ZOTERO_LIBRARY_ID", "").strip(),
        zotero_library_type=os.getenv("ZOTERO_LIBRARY_TYPE", "user").strip().lower() or "user",
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", "").strip(),
        embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        zotero_semantic_db_path=os.getenv("ZOTERO_SEMANTIC_DB_PATH", "").strip() or None,
        crossref_mailto=os.getenv("CROSSREF_MAILTO", "").strip(),
        unpaywall_email=os.getenv("UNPAYWALL_EMAIL", "").strip(),
    )


def default_semantic_db_path() -> Path:
    s = get_settings()
    if s.zotero_semantic_db_path:
        return Path(s.zotero_semantic_db_path)
    return Path.cwd() / ".zotero_semantic_index.sqlite3"


def require_zotero_config() -> Settings:
    s = get_settings()
    if not s.zotero_api_key or not s.zotero_library_id:
        raise RuntimeError(
            "Zotero belum dikonfigurasi: set ZOTERO_API_KEY dan ZOTERO_LIBRARY_ID di `.env` "
            "(lihat `.env.example`)."
        )
    if s.zotero_library_type not in ("user", "group"):
        raise RuntimeError("ZOTERO_LIBRARY_TYPE harus `user` atau `group`.")
    return s
