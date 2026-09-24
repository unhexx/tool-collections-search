from pathlib import Path
import os
import tool_collections_search.server as srv


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
