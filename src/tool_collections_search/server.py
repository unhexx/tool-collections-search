"""Local collections_search / file_search: SQLite FTS5 over a data directory."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any

from tool_http import serve

TOOL = "collections_search"
SCHEMA = {
    "type": "function",
    "name": "collections_search",
    "description": "Search locally ingested documents (FTS5). No cloud collections. Use for project files, notes, and uploaded corpora.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Full-text query"},
            "path": {"type": "string", "description": "Optional path substring filter"},
            "limit": {"type": "integer", "default": 8},
            "reindex": {"type": "boolean", "default": False},
        },
        "required": ["query"],
    },
}

_TEXT_EXT = {".md", ".txt", ".rst", ".json", ".yml", ".yaml", ".csv", ".py", ".toml"}


def _root() -> Path:
    return Path(os.environ.get("COLLECTIONS_ROOT", "/app/corpus")).resolve()


def _db() -> Path:
    return Path(os.environ.get("COLLECTIONS_DB", "/tmp/tool-data/collections.sqlite")).resolve()


def _connect() -> sqlite3.Connection:
    _db().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(_db()))
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(path, body, tokenize='unicode61')"
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            digest TEXT NOT NULL
        )
        """
    )
    return con


def _digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def index_corpus(force: bool = False) -> int:
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    con = _connect()
    try:
        if force:
            con.execute("DELETE FROM docs")
            con.execute("DELETE FROM files")
        known = {
            row["path"]: row["digest"]
            for row in con.execute("SELECT path, digest FROM files")
        }
        doc_counts: dict[str, int] = {}
        for row in con.execute("SELECT path FROM docs"):
            doc_counts[row["path"]] = doc_counts.get(row["path"], 0) + 1
        count = 0
        seen: set[str] = set()
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in _TEXT_EXT:
                continue
            rel = str(p.relative_to(root))
            body = p.read_text(encoding="utf-8", errors="replace")[:200_000]
            digest = _digest(body)
            seen.add(rel)
            if known.get(rel) == digest and doc_counts.get(rel) == 1:
                continue
            con.execute("DELETE FROM docs WHERE path = ?", (rel,))
            con.execute("DELETE FROM files WHERE path = ?", (rel,))
            con.execute("INSERT INTO docs(path, body) VALUES (?, ?)", (rel, body))
            con.execute(
                "INSERT INTO files(path, digest) VALUES (?, ?)", (rel, digest)
            )
            count += 1
        for rel in (set(known) | set(doc_counts)) - seen:
            con.execute("DELETE FROM docs WHERE path = ?", (rel,))
            con.execute("DELETE FROM files WHERE path = ?", (rel,))
        con.commit()
        return count
    finally:
        con.close()


def run(arguments: dict[str, Any]) -> dict[str, Any]:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required")
    if arguments.get("reindex"):
        index_corpus(force=True)
    else:
        index_corpus(force=False)
    limit = int(arguments.get("limit") or 8)
    limit = max(1, min(limit, 50))
    path_filter = arguments.get("path")
    con = _connect()
    sql = "SELECT path, snippet(docs, 1, '[', ']', ' … ', 16) AS snip FROM docs WHERE docs MATCH ?"
    params: list[Any] = [query]
    if isinstance(path_filter, str) and path_filter:
        sql += " AND path LIKE ?"
        params.append(f"%{path_filter}%")
    sql += " LIMIT ?"
    params.append(limit)
    try:
        rows = list(con.execute(sql, params))
    except sqlite3.OperationalError:
        # fallback: LIKE search if MATCH syntax fails
        rows = list(con.execute(
            "SELECT path, substr(body,1,240) AS snip FROM docs WHERE body LIKE ? LIMIT ?",
            (f"%{query}%", limit),
        ))
    con.close()
    return {
        "hits": [{"path": r["path"], "snippet": r["snip"]} for r in rows],
        "count": len(rows),
        "root": str(_root()),
    }


def main() -> None:
    index_corpus(force=False)
    serve(TOOL, SCHEMA, run)


if __name__ == "__main__":
    main()
