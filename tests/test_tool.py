from pathlib import Path
import sqlite3
import tool_collections_search.server as srv


def _bind(monkeypatch, corpus, db) -> None:
    monkeypatch.setenv("COLLECTIONS_ROOT", str(corpus))
    monkeypatch.setenv("COLLECTIONS_DB", str(db))


def _counts(db, path: str) -> tuple[int, int]:
    con = sqlite3.connect(db)
    try:
        docs = con.execute(
            "SELECT COUNT(*) FROM docs WHERE path = ?", (path,)
        ).fetchone()[0]
        files = con.execute(
            "SELECT COUNT(*) FROM files WHERE path = ?", (path,)
        ).fetchone()[0]
    finally:
        con.close()
    return docs, files


def test_search(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("Agentic loop uses local tools and FTS5.", encoding="utf-8")
    monkeypatch.setenv("COLLECTIONS_ROOT", str(corpus))
    monkeypatch.setenv("COLLECTIONS_DB", str(tmp_path / "db.sqlite"))
    srv.index_corpus(force=True)
    out = srv.run({"query": "local tools"})
    assert out["count"] >= 1
    assert out["hits"][0]["path"] == "note.md"


def test_edited_file_visible_without_reindex(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    note = corpus / "note.md"
    note.write_text("alpha_token", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    _bind(monkeypatch, corpus, db)
    srv.index_corpus(force=True)
    note.write_text("beta_token", encoding="utf-8")
    srv.index_corpus(force=False)
    found = srv.run({"query": "beta_token"})
    assert found["count"] >= 1
    assert found["hits"][0]["path"] == "note.md"
    assert srv.run({"query": "alpha_token"})["count"] == 0


def test_deleted_file_removed_from_index(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    gone = corpus / "gone.md"
    gone.write_text("gone_token", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    _bind(monkeypatch, corpus, db)
    srv.index_corpus(force=True)
    gone.unlink()
    srv.index_corpus(force=False)
    assert srv.run({"query": "gone_token"})["count"] == 0
    assert _counts(db, "gone.md") == (0, 0)


def test_unchanged_file_is_not_rewritten(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("steady_token", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    _bind(monkeypatch, corpus, db)
    srv.index_corpus(force=False)
    assert srv.index_corpus(force=False) == 0
    assert _counts(db, "note.md") == (1, 1)


def test_legacy_docs_restore_files_row(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("legacy_token", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    _bind(monkeypatch, corpus, db)
    srv.index_corpus(force=True)
    con = sqlite3.connect(db)
    try:
        con.execute("DELETE FROM files")
        con.commit()
    finally:
        con.close()
    assert srv.index_corpus(force=False) == 1
    assert _counts(db, "note.md") == (1, 1)


def test_force_drops_docs_not_on_disk(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("kept_token", encoding="utf-8")
    (corpus / "more.txt").write_text("second_token", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    _bind(monkeypatch, corpus, db)
    srv.index_corpus(force=False)
    con = sqlite3.connect(db)
    try:
        con.execute(
            "INSERT INTO docs(path, body) VALUES (?, ?)",
            ("not_on_disk.md", "extra_token"),
        )
        con.commit()
    finally:
        con.close()
    srv.index_corpus(force=True)
    assert _counts(db, "not_on_disk.md") == (0, 0)
    assert _counts(db, "note.md") == (1, 1)
    assert _counts(db, "more.txt") == (1, 1)


def test_duplicate_docs_row_collapses(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "note.md").write_text("dup_token", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    _bind(monkeypatch, corpus, db)
    srv.index_corpus(force=False)
    con = sqlite3.connect(db)
    try:
        con.execute(
            "INSERT INTO docs(path, body) VALUES (?, ?)",
            ("note.md", "dup_token"),
        )
        con.commit()
    finally:
        con.close()
    assert srv.index_corpus(force=False) == 1
    assert _counts(db, "note.md") == (1, 1)


def test_index_error_does_not_commit_wipe(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    note = corpus / "note.md"
    note.write_text("stable_token", encoding="utf-8")
    db = tmp_path / "db.sqlite"
    _bind(monkeypatch, corpus, db)
    srv.index_corpus(force=True)
    note.write_text("changed_token", encoding="utf-8")

    def boom(self, *args, **kwargs):
        raise OSError("disk")

    monkeypatch.setattr(Path, "read_text", boom)
    try:
        srv.index_corpus(force=True)
        raised = False
    except OSError:
        raised = True
    assert raised
    assert _counts(db, "note.md") == (1, 1)
    con = sqlite3.connect(db)
    try:
        body = con.execute(
            "SELECT body FROM docs WHERE path = ?", ("note.md",)
        ).fetchone()[0]
    finally:
        con.close()
    assert body == "stable_token"
