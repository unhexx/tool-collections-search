# Brainstorm — one top solution

**Updated:** 2026-10-16

**Source of the three families:** `docs/research/top-solution-research.md`. No new packages or models were introduced here.

**Pick:** option A, content-bearing FTS5 with a digest side table.

## Option A — keep the FTS table, fix freshness and rank

Leave `docs` as `fts5(path, body, tokenize='unicode61')`. Add a normal table `files(path TEXT PRIMARY KEY, digest TEXT NOT NULL)` whose digest is the SHA-256 of the body that was indexed (the same 200_000-character cap as today).

On each scan:

- New path: insert into `docs` and `files`.
- Same path, same digest: skip.
- Same path, different digest: `DELETE FROM docs WHERE path = ?`, then insert the new body and digest.
- Path on disk gone: delete that path from both tables.
- `reindex` / `force`: delete every row in both tables, then insert what is on disk.

On search:

- Reject a blank query, as now.
- Split the query on whitespace. Quote each piece as an FTS string (wrap in `"`, double any embedded `"`). Join the pieces with ` AND `. That keeps today's "several words" behavior (implicit AND, not one phrase) and makes punctuation and the reserved words `AND` / `OR` / `NOT` legal.
- `ORDER BY rank` before `LIMIT`.
- Keep the optional `path LIKE` predicate on the FTS query.
- If `MATCH` still raises `OperationalError`, the LIKE fallback must use the same path predicate. It must not search the whole corpus when the caller passed `path`.

HTTP stays `ThreadingHTTPServer` on loopback with the existing bearer token. No new runtime dependency. pxpipe is not called.

## Option B — external-content FTS5 plus triggers

Put path, digest, and body in a normal table. Point an FTS5 table at it with `content=` and `content_rowid=`, and install the insert, delete, and update triggers from the FTS5 docs. Search still uses a quoted `MATCH` and `ORDER BY rank`.

The body is stored once. Snippets still work, but only while the index matches the content table. Deletes must pass the old column values. `'delete-all'` replaces the current `DELETE FROM docs`. The directory walker does not go away: files are not rows until Python writes them.

## Option C — another engine or a vector model

Whoosh / whoosh3, Tantivy, Meilisearch, or `sqlite-vec` plus an embedding model. Research already recorded why each one adds a package, a native build, a second process, or a pre-v1 extension. No model card was opened, so this option does not name a model. pxpipe is not an embedder for this tool.

## Why A wins for this tree

The tool is one process, stdlib HTTP, and a content-bearing FTS5 table. `snippet(docs, 1, ...)` already reads column 1 (`body`). The single test indexes `note.md` and searches `local tools`. Option A keeps that table, that snippet call, and that query shape (two terms, AND, not a phrase).

The defects that matter are in `server.py`, and A fixes them inside documented FTS5:

- A path that is already present is never updated, so an edit stays stale until `reindex`. A digest of the indexed bytes makes the skip honest. Removing a file deletes its row, which the current scan never does.
- `MATCH` without `ORDER BY` is an arbitrary order, so `LIMIT` can drop the better hit. `ORDER BY rank` is the documented sort.
- A raw user string is not always a legal `MATCH`. Quoting each whitespace piece and joining with ` AND ` avoids the syntax error without turning `local tools` into the phrase `"local tools"`. The LIKE fallback keeps the path filter so a syntax error cannot widen the search.

Option B is the same search behavior with more schema. One copy of the body does not matter here: the corpus drop directory is empty aside from a README, each body is capped at 200_000 characters, and the database is a local index, not a system of record. Triggers do not watch the filesystem. They add the external-content pitfalls (stale index, delete values must match, no `REPLACE`) for a walker that still lives in Python. A side table of digests does not change the FTS column list, so existing databases and the snippet column index stay valid.

Option C breaks the stack this repo already fixed: no runtime dependencies, no second search service, loopback only, pxpipe left on the host. FTS5 is already enabled in the project `.venv` (SQLite 3.53.4, `ENABLE_FTS5`). Replacing it is not justified by the keyword contract `collections_search` implements.

Out of this pick, on purpose: Porter and trigram (wrong tokenizer for mixed notes and code), any embedding model, calling pxpipe, and replacing `ThreadingHTTPServer`. The compose file names a volume `collections_data` without a top-level `volumes:` key. That is a deploy nit, not a reason to change the search engine. The design can schedule it as its own small change or leave it.

## What design should treat as the solution

In-process content-bearing FTS5, digest side table, per-token quoted `AND` query, `ORDER BY rank`, path filter kept on the LIKE fallback, stdlib HTTP unchanged, pxpipe not in the tool.
