# MCP Zotero Server

Server MCP (Model Context Protocol) untuk integrasi Zotero dengan AI berbasis Python. Memungkinkan akses penuh ke pustaka Zotero, pencarian semantik lokal, manajemen koleksi, dan operasi advanced seperti deteksi duplikat melalui tools yang ekstensif.

**Nama project:** `mcp-zotero`  
**Modul Python:** `mcp_zotero`  
**Versi:** 0.1.0  
**Python minimum:** 3.11

---

## 📋 Daftar Isi

- [Instalasi](#instalasi)
- [Konfigurasi](#konfigurasi)
- [Tools Tersedia](#tools-tersedia)
- [Cara Penggunaan](#cara-penggunaan)
- [Struktur Project](#struktur-project)

---

## 🚀 Instalasi

### Prasyarat

- **Python 3.11+** (pastikan tersedia di PATH atau gunakan virtual environment)
- **Zotero** terinstal dan tersinkronisasi dengan akun online
- **pip** atau package manager lain

### Langkah-langkah

1. **Clone atau download project:**
   ```bash
   cd d:\mcp\mcp-with-claude
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   # Atau jika ada venv:
   python -m pip install -e .
   ```

3. **Verifikasi instalasi:**
   ```bash
   python -m mcp_zotero --doctor
   ```
   Output akan menampilkan daftar tools, prompts, dan resources yang tersedia.

---

## ⚙️ Konfigurasi

### Setup `.env` File

Buat file `.env` di root project (`d:\mcp\mcp-with-claude\.env`) dengan konfigurasi berikut:

```env
# ===== Zotero API =====
ZOTERO_API_KEY=your_api_key_here
ZOTERO_LIBRARY_ID=your_library_id
ZOTERO_LIBRARY_TYPE=user  # atau 'group' untuk library grup

# ===== Embedding (Pencarian Semantik) =====
EMBEDDING_API_KEY=sk-...  # OpenAI API key atau kompatibel
EMBEDDING_BASE_URL=https://api.openai.com/v1  # Bisa custom untuk local model
EMBEDDING_MODEL=text-embedding-3-small

# ===== Path Database (Opsional) =====
ZOTERO_SEMANTIC_DB_PATH=.zotero_semantic_index.sqlite3

# ===== Crossref & Unpaywall (untuk fetch metadata) =====
CROSSREF_MAILTO=your_email@example.com
UNPAYWALL_EMAIL=your_email@example.com
```

### Cara Mendapatkan Credential

1. **ZOTERO_API_KEY & ZOTERO_LIBRARY_ID:**
   - Login ke https://www.zotero.org/settings/keys
   - Buat API key baru
   - Salin key dan library ID dari settings

2. **EMBEDDING_API_KEY:**
   - Buat akun di https://platform.openai.com
   - Generate API key di https://platform.openai.com/api-keys

3. **Email untuk Crossref & Unpaywall:**
   - Gunakan email Anda sendiri (diperlukan untuk rate limiting yang lebih baik)

---

## 🛠️ Tools Tersedia

### Pencarian & Query

#### `zotero_search_items`
Pencarian cepat di Zotero dengan mode judul/penulis/creator.
- **Parameter:** `q` (query), `limit`, `start`, `qmode` (titleCreatorYear|everything)
- **Gunakan untuk:** Pencarian umum yang cepat

#### `zotero_advanced_search`
Pencarian advanced dengan kombinasi query, tag, itemType, dan koleksi.
- **Parameter:** `q`, `tag`, `item_type`, `qmode`, `collection_key`, `sort`, `direction`, `limit`, `start`
- **Gunakan untuk:** Pencarian kompleks dengan filter

#### `zotero_search_by_tag`
Filter items berdasarkan tag tertentu.
- **Parameter:** `tag`, `limit`, `start`

#### `zotero_search_notes`
Cari di catatan dan konten terindeks penuh.
- **Parameter:** `q` (query), `limit`

#### `zotero_search_by_citation_key`
Cari item berdasarkan Better BibTeX citation key di kolom extra.
- **Parameter:** `citation_key`, `max_scan`

#### `zotero_semantic_search`
Pencarian berdasarkan similarity semantik (embedding/vektor).
- **Parameter:** `query`, `top_k` (jumlah hasil top)
- **Catatan:** Memerlukan database indeks yang sudah dibangun

### Koleksi & Organisasi

#### `zotero_get_collections`
Dapatkan daftar semua koleksi.
- **Parameter:** `top_only` (hanya level atas jika True)

#### `zotero_get_collection_items`
Item dalam sebuah koleksi.
- **Parameter:** `collection_key`, `limit`, `start`, `top_only`

#### `zotero_create_collection`
Buat koleksi baru (parent_collection_key kosong = level atas).
- **Parameter:** `name`, `parent_collection_key`

#### `zotero_manage_collections`
Tambah atau hapus item dari koleksi.
- **Parameter:** `action` (add|remove), `collection_key`, `item_keys_csv`

### Item & Metadata

#### `zotero_get_recent`
Dapatkan item terbaru berdasarkan dateAdded.
- **Parameter:** `limit`

#### `zotero_get_item_metadata`
Metadata lengkap item dalam format JSON atau BibTeX.
- **Parameter:** `item_key`, `format` (json|bibtex)

#### `zotero_get_item_fulltext`
Konten teks lengkap yang diindeks Zotero.
- **Parameter:** `item_key`

#### `zotero_get_item_children`
Lampiran, catatan, dan item anak lainnya.
- **Parameter:** `item_key`

### Tags & Kategori

#### `zotero_get_tags`
Dapatkan daftar tag (dengan opsional filter).
- **Parameter:** `q`, `qmode`, `limit`

### Catatan & Anotasi

#### `zotero_get_notes`
Dapatkan catatan (tingkat atas atau anak item tertentu).
- **Parameter:** `parent_item_key`, `limit`

#### `zotero_get_annotations`
Anotasi (itemType annotation) di bawah parent item.
- **Parameter:** `parent_item_key`

#### `zotero_create_note`
Buat catatan baru di bawah item induk.
- **Parameter:** `item_key`, `note_text`

### Import & Add Items

#### `zotero_add_by_doi`
Tambahkan artikel dari DOI (otomatis fetch dari Crossref).
- **Parameter:** `doi`, `attach_oa_pdf` (coba attach PDF dari Unpaywall)
- **Fitur:** Otomatis ekstrak metadata, attach PDF jika tersedia

#### `zotero_add_from_file`
Import PDF/EPUB ke Zotero.
- **Parameter:** `file_path`, `collection_key`
- **Fitur:** Ekstrak DOI dari PDF, fallback ke document item jika DOI tidak ada

### Deteksi & Merge Duplikat

#### `zotero_find_duplicates`
Temukan item duplikat berdasarkan DOI dan/atau judul.
- **Parameter:** `by` (doi,title), `max_scan`

#### `zotero_merge_duplicates`
Gabungkan item duplikat ke item master.
- **Parameter:** `master_key`, `duplicate_keys_csv`, `dry_run`
- **Catatan:** Set `dry_run=True` untuk preview sebelum commit

### Indexing & Search Database

#### `zotero_update_search_database`
Bangun ulang indeks SQLite + vektor untuk semantic search.
- **Parameter:** `max_items`
- **Waktu:** Bisa memakan waktu bergantung jumlah item

#### `zotero_get_search_database_status`
Status file DB indeks semantik dan konfigurasi embedding.

### PDF & Document Processing

#### `zotero_get_pdf_outline`
Ekstrak outline (daftar isi) dari PDF attachment.
- **Parameter:** `attachment_item_key`
- **Gunakan untuk:** Dapatkan struktur dokumen PDF

---

## 📖 Cara Penggunaan

### Via Cursor/VS Code (MCP)

1. **Setup `mcp.json`:**
   Edit `C:\Users\salsa\AppData\Roaming\Code\User\mcp.json`:
   ```json
   {
     "servers": {
       "mcp-zotero": {
         "command": "python",
         "args": ["-m", "mcp_zotero", "--force-stdio"],
         "cwd": "D:\\mcp\\mcp-with-claude"
       }
     },
     "inputs": []
   }
   ```

2. **Restart MCP client** (Cursor/VS Code)

3. **Gunakan di prompt:**
   ```
   Gunakan tool zotero_search_items untuk cari artikel tentang "machine learning"
   ```

### Via Command Line (Direct)

```bash
# Cek status
python -m mcp_zotero --doctor

# Jalankan server (mode stdio)
python -m mcp_zotero --force-stdio
```

### Contoh Workflow

**Cari → Import → Organize:**
```
1. zotero_search_items(q="quantum computing")
2. zotero_add_by_doi(doi="10.1038/nature...")
3. zotero_manage_collections(action="add", collection_key="...", item_keys_csv="...")
```

**Deteksi & Merge Duplikat:**
```
1. zotero_find_duplicates(by="doi,title", max_scan=800)
2. Review hasil di output
3. zotero_merge_duplicates(master_key="...", duplicate_keys_csv="...", dry_run=False)
```

**Semantic Search:**
```
1. zotero_update_search_database(max_items=1000)  # Build index once
2. zotero_semantic_search(query="cara kerja neural networks", top_k=10)
```

---

## 📁 Struktur Project

```
d:\mcp\mcp-with-claude/
├── README.md                          # File ini
├── pyproject.toml                     # Konfigurasi project (dependencies, entry point)
├── .env                               # Environment variables (BUAT SENDIRI)
│
├── config/
│   └── cursor-mcp.template.json       # Template konfigurasi MCP untuk Cursor
│
└── src/mcp_zotero/
    ├── __init__.py
    ├── __main__.py                    # Entry point: python -m mcp_zotero
    ├── server.py                      # FastMCP server main
    │
    ├── config/
    │   ├── __init__.py
    │   └── settings.py                # Muat .env dan validasi config
    │
    ├── integrations/
    │   └── zotero/
    │       ├── __init__.py
    │       ├── client.py              # Zotero Web API v3 async client
    │       ├── embeddings.py          # OpenAI-compatible embedding API
    │       ├── semantic_index.py      # SQLite + vektor indexing
    │       ├── duplicates.py          # Deteksi & merge duplikat
    │       ├── metadata_fetch.py      # Crossref & Unpaywall fetch
    │       └── pdf_utils.py           # PDF parsing (DOI extraction, outline)
    │
    ├── tools/
    │   ├── __init__.py
    │   └── zotero_tools.py            # Semua MCP tool definitions
    │
    ├── resources/
    │   ├── __init__.py
    │   └── builtin_resources.py       # MCP resources (read-only)
    │
    └── prompts/
        ├── __init__.py
        └── builtin_prompts.py         # MCP prompts (templates)
```

---

## 🔧 Troubleshooting

### Server langsung berhenti saat restart

**Penyebab:** Import error atau missing `.env`

**Solusi:**
```bash
# Cek error:
python -m mcp_zotero --doctor

# Buat .env dengan minimal:
ZOTERO_API_KEY=fake_key_untuk_test
ZOTERO_LIBRARY_ID=12345
```

### "ZOTERO_API_KEY kosong"

**Solusi:** Lengkapi file `.env` dengan kredensial valid dari https://www.zotero.org/settings/keys

### Semantic search tidak bekerja

**Penyebab:** Database indeks belum dibangun

**Solusi:**
```bash
# Build index dulu (bisa lama):
zotero_update_search_database(max_items=1000)

# Kemudian baru bisa search:
zotero_semantic_search(query="...")
```

### "File .env tidak ditemukan"

**Catatan:** Opsional—program akan menggunakan default jika tidak ada. Tapi untuk Zotero functionality, `.env` sangat disarankan.

---

## 📚 Dependencies

Lihat [pyproject.toml](pyproject.toml):

- **mcp** ≥1.26 – Model Context Protocol framework
- **httpx** ≥0.27 – Async HTTP client
- **python-dotenv** ≥1.0 – Load .env files
- **pypdf** ≥5.0 – PDF parsing (DOI extraction, outline)

Dev:
- **ruff** ≥0.8 – Code formatter/linter

---

