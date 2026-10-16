# Top-solution research — tool-collections-search

**Status: Partial** (claims below were checked against the cited page; gaps are listed at the end).

**Updated:** 2026-10-16

**Query:** Which frameworks, search engines, open-source packages, and models fit this tree as it is: one loopback process, Python 3.11+, stdlib HTTP, SQLite FTS5, no runtime dependencies, host pxpipe left outside the tool.

This note does not pick the design. It records what the sources support so the next slice can compare options.

## What the sources support

The search contract this repo already implements is the one SQLite FTS5 documents: a virtual table, `MATCH`, `snippet()`, and optional `ORDER BY rank`. FTS5 has shipped inside the SQLite amalgamation since 3.9.0 (2015-10-14) and is enabled by default for the amalgamation configure script. The checked-out `.venv` reports SQLite 3.53.4 with `ENABLE_FTS5`, and a `unicode61` table plus `snippet()` ran there. Nothing in the primary docs requires a second search process, a pure-Python index, or an embedding model for keyword `collections_search`.

The gaps in the current indexer and query are also FTS5 behaviors, not missing products. A self-contained FTS5 table accepts ordinary `INSERT` / `UPDATE` / `DELETE`. Skipping a path that is already present, without comparing bytes, is an application choice; the engine will not notice an edited file. A `MATCH` with no `ORDER BY` is defined to return rows in an arbitrary order, so `LIMIT` can drop the better hits. User text is not a safe `MATCH` string unless it is a bareword or a double-quoted FTS string. `AND`, `OR`, and `NOT` are reserved and case sensitive. Characters outside the bareword set must be quoted, and a query that is a syntax error today may mean something else in a later FTS5.

Host pxpipe (`127.0.0.1:8100`) and the gateway (`127.0.0.1:8110`) stay outside this process. No source below is a reason to call them from the search path or to replace them with a hosted API.

## FTS5, as documented

Primary page: [SQLite FTS5](https://www.sqlite.org/fts5.html) (page timestamp on that copy: 2026-10-09). Local probe: `.venv` SQLite 3.53.4, `PRAGMA compile_options` contains `ENABLE_FTS5`, `THREADSAFE=1`.

- FTS5 is a virtual table module. After `CREATE VIRTUAL TABLE`, rows are written with `INSERT`, `UPDATE`, and `DELETE`. There is an implicit `rowid`. Naming a column `rowid` or `rank` is an error. The current table `docs(path, body)` does not use those names.
- Without `ORDER BY`, match order is arbitrary. `ORDER BY rank` sorts best match first. The hidden `rank` column is the same value as `bm25()` with no extra arguments, and reading `rank` is the faster way to sort. `bm25()` is multiplied by -1 so a better match is a smaller number. `ORDER BY bm25(docs)` and `ORDER BY rank` are the ascending forms that return best first. Column weights are extra numeric arguments, for example `bm25(ft, 10.0, 5.0)`, or a per-query `rank MATCH 'bm25(10.0, 5.0)'`.
- `snippet()` takes the table name plus five arguments: column index (negative means auto-select), text before a match, text after a match, ellipsis text, and a token count. The count must be greater than zero and at most 64. The current call uses column 1 (`body`) and 16 tokens, which is inside that range. `highlight()` returns the whole column instead of a fragment.
- `unicode61` is the default tokenizer. It splits on Unicode 6.1 separators, case-folds, and by default removes Latin diacritics (`remove_diacritics` default `"1"`; `"2"` folds the rare multi-diacritic codepoints). `tokenchars` can keep characters such as `-` and `_` inside tokens. The table already sets `tokenize='unicode61'`, which is that default.
- `porter` wraps another tokenizer (unicode61 if none is named) and stems with the Porter algorithm. The documentation says it is for English only and that other languages may or may not get better search. It does not discuss source code. This corpus includes `.py`, `.yml`, `.yaml`, `.json`, and `.toml`, so Porter is not a justified default.
- `trigram` indexes every three-character span so substring search works. A snippet length is then counted in those spans, not in words. That is a different index, not a flag on the current tokenizer.
- The `content` option has three shapes. Empty `content=''` is contentless: column reads other than `rowid` return SQL NULL, so `snippet()` has nothing to excerpt, and `UPDATE` / `DELETE` are not supported. A non-empty `content='table'` is an external-content index: every FTS5 feature works, including snippets, but only while the index matches the content table. The documented sync is three triggers (insert, delete, update). The delete trigger must pass the old column values; if they differ from what was indexed, later queries are unreliable. External-content tables do not honor `REPLACE`; those statements abort. `'delete-all'` (`INSERT INTO ft(ft) VALUES('delete-all')`) exists only for external-content and contentless tables. The current `DELETE FROM docs` is the normal-table form, and it matches a content-bearing FTS table.
- Rebuild of an external-content index is `INSERT INTO fts(fts) VALUES('rebuild')`, which walks the content table again. That does not apply to the current self-contained table.
- An FTS string is either a double-quoted string (embedded quotes doubled) or a bareword that is not `AND`, `OR`, or `NOT` (case sensitive). A bareword is only non-ASCII codepoints, ASCII letters, digits, underscore, or codepoint 26. Anything else must be quoted. Whitespace between phrases is an implicit `AND`. Operators in the documented examples are uppercase. The full-text query syntax section warns that a character that is a syntax error today may become meaningful later, so quoting user text is the stable shape.
- `MATCH` on a bad string raises `sqlite3.OperationalError`. The current `run()` catches that and searches `body LIKE`, and that fallback does not apply the path predicate. Quoting the user string removes the usual reason to take that branch. Placeholders (`?`) are how the `sqlite3` docs say to bind values; the current `MATCH` and `LIKE` already bind that way. The injection risk is the FTS expression language, not SQL concatenation.

A content-bearing FTS table plus an application check of file bytes (size, mtime, or a hash) before `DELETE` + `INSERT` stays inside the API above. An external-content table plus triggers is the documented shape when path, mtime, and a hash need to live in a normal table and the index must not store a second copy. Both are FTS5. Neither needs another package.

## stdlib HTTP

Primary page: [http.server](https://docs.python.org/3/library/http.server.html). [sqlite3](https://docs.python.org/3/library/sqlite3.html).

- `http.server` is not recommended for production. It only implements basic security checks. `ThreadingHTTPServer` is `HTTPServer` plus `ThreadingMixIn`, added in 3.7, so it is in the 3.11+ range this repo requires. The stated reason it exists is browsers that pre-open sockets, which would stall a single-threaded `HTTPServer`.
- `send_header` and `send_response_only` do not reject CRLF, so unsanitized header values are an injection risk. Since 3.12, control characters are scrubbed from the default stderr access log. This server silences that log. Binding to loopback and requiring a bearer token are application controls; they are not described as making `http.server` a production server. They do match a tool that is published only on `127.0.0.1`.
- `sqlite3` is optional and talks to the system SQLite library. `connect(..., check_same_thread=True)` is the default: using one connection from another thread raises `ProgrammingError`. The default lock wait is five seconds, then `OperationalError`. `index_corpus` and `run` each open a connection and close it, so they do not share one connection across handler threads. Two overlapping requests can still lock the same file. `THREADSAFE=1` on this interpreter means the library allows that; it does not remove the lock.
- The same sqlite3 page says the module is not built with loadable-extension support by default, because some platform libraries (notably macOS) omit it. Enabling it is a configure flag (`--enable-loadable-sqlite-extensions`). On this `.venv`, `enable_load_extension(True)` did not raise, and `PRAGMA compile_options` did not list `ENABLE_LOAD_EXTENSION`. No extension was loaded. That is not evidence that `sqlite-vec` or any other `.so` is available.

Replacing `ThreadingHTTPServer` with Flask, FastAPI, or another ASGI stack would add a runtime dependency and a second HTTP implementation. The docs do not say the stdlib server is wrong for a loopback tool with a fixed set of routes.

## Other search software

These were checked as replacements, not as libraries to vendor.

| Option | What the source says | Fit for this tree |
| --- | --- | --- |
| SQLite FTS5 in-process | Virtual table in the database file. No extra server. See the FTS5 page above. | Matches the stack: stdlib `sqlite3`, one process, no runtime dependency. |
| [Whoosh](https://github.com/mchaput/whoosh) and [whoosh3](https://pypi.org/project/whoosh3/) | Whoosh is a pure-Python index with its own API. The PyPI page for whoosh3 3.54.0 (released 2026-09-21) says the original project went dormant, whoosh-reloaded was later marked unmaintained, and that fork is maintained by an automated agent. | A second index and a runtime package. The current tests and schema would not carry over. Not required for keyword search that FTS5 already does. |
| [tantivy](https://pypi.org/project/tantivy/) 0.26.2 | Official Python bindings for the Rust engine. `pip install tantivy`. If no wheel exists, the build needs a Rust toolchain. | Native dependency, separate index format, outside the zero-dependency rule. |
| [Meilisearch self-hosting](https://meilisearch.com/docs/resources/self_hosting/overview) | A separate binary. Their docs call Meilisearch Cloud the recommended way to run it, and self-hosting a second process (reverse proxy, master key, systemd or Docker). The install page shows `./meilisearch` and a Docker image. | A second server. This repo's rule is no third-party search service. |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | Loadable C extension, `vec0` virtual tables, `pip install sqlite-vec`. The README says it is pre-v1 and to expect breaking changes. Install paths are language bindings, not the SQLite amalgamation. | Extra package plus extension loading. Python's sqlite3 docs say loadable extensions are off by default. Pre-v1 is a poor base for the only index. |

No source above says a local keyword tool of this size should leave FTS5 for one of those products. They are alternatives when the requirements change (custom analysis and spelling, a large dedicated index, or vectors).

## Models and hybrid search

No embedding model was selected. Model cards were not opened in this pass, so this note does not name one.

- Keyword ranking for the current tool is `bm25` / `rank` inside FTS5. That is part of SQLite, not a downloadable model.
- `sqlite-vec` can store float, int8, and binary vectors and answer a KNN `MATCH`, but only after the extension is loaded. It does not replace FTS5, and the README marks it pre-v1. Adding it would also add a pip dependency and an embedding step that does not exist in this process.
- Hybrid fusion (BM25 plus vectors, then reciprocal rank fusion) shows up in third-party projects and in one arXiv write-up of a SQLite library. Those pages were not used as a reason to add a model here. They all assume an embedding runtime this repo does not have.
- Porter is the only "model-like" component inside stock FTS5. It is an English stemmer, not a neural model, and the FTS5 page limits it to English.

pxpipe is a host HTTP front for the Agentix loop. Using it to embed queries would put this tool's search path on that process and would ignore the rule that pxpipe is not baked in. If a later design wants semantic search, the documented fallback pattern in this space is lexical search when the embedder is absent. That is an option to reject or defer, not a dependency of `collections_search`.

## What the next slice can compare

Three families follow from the sources, without a winner:

1. Stay on the content-bearing FTS5 table. Refresh a row when the file bytes change. `ORDER BY rank`. Pass user text as a quoted FTS string. Keep `ThreadingHTTPServer` on loopback. No new package. pxpipe untouched.
2. Move the file bytes to a normal table (path, mtime or hash, body) and an external-content FTS5 table with the documented triggers, still with `ORDER BY rank` and quoted queries. Still no new package. More schema, one copy of the body.
3. Leave FTS5 for Whoosh, Tantivy, Meilisearch, or `sqlite-vec` plus an embedding model. Each of those adds a package, a second index, or a second process, and conflicts with the stack this repo already fixed.

## Coverage and uncertainty

- FTS5 behavior above was read from https://www.sqlite.org/fts5.html. The local `.venv` probe only shows that this interpreter can create a `unicode61` table and return `snippet()` plus `rank`. It does not measure the Debian image in `Dockerfile`.
- `enable_load_extension(True)` succeeded here and no library was loaded. Do not treat that as "extensions work" or "extensions are impossible".
- Whoosh, tantivy, Meilisearch, and sqlite-vec were read from the linked README or docs pages. They were not installed or benchmarked against `corpus/`.
- No Hugging Face or vendor model card was opened. Any specific embedding name would be invented and is omitted.
- pxpipe's API was not researched. The project rule is to leave it on the host.
- The LIKE fallback, the path-only incremental skip, and the missing `ORDER BY` are facts from `src/tool_collections_search/server.py`, not from the FTS5 page. The FTS5 page explains why those choices drop or scramble hits.
