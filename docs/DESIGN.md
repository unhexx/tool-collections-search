# Дизайн: tool-collections-search

## Назначение

Локальная замена `collections_search` / `file_search` xAI. Полнотекст по каталогу корпуса, без облачных Collections.

## Границы

Входит: индексация текстовых файлов, FTS5-запрос, фильтр по пути, переиндексация.

Не входит: эмбеддинги, облачный upload, бинарные форматы как first-class (PDF — отдельная задача).

## Архитектура

```
corpus/  --index_corpus-->  SQLite FTS5 (COLLECTIONS_DB)
агент    --query---------->  snippet() + LIKE fallback
```

Корень корпуса: `COLLECTIONS_ROOT` (в образе `/app/corpus`).  
БД: `COLLECTIONS_DB` на writable volume / tmpfs.

## Контракт HTTP

`POST /v1/invoke` аргументы: `query`, `path?`, `limit?`, `reindex?`.

Ответ: `{hits:[{path,snippet}], count, root}`.

## Качества

- идемпотентная доиндексация без `reindex`
- `reindex=true` перестраивает таблицу
- лимит 1..50
- только расширения из белого списка

## Безопасность

Корпус монтируется read-only. БД не в git. Loopback + bearer token.

