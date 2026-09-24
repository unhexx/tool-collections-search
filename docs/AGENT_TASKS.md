# Задачи локальным агентам: tool-collections-search

- [ ] T-001 Инкрементальный индекс по mtime/size, не полная вставка при каждом старте. Критерий: повторный `index_corpus(False)` не дублирует документы.
- [ ] T-002 Исключить симлинки, уводящие за `COLLECTIONS_ROOT` (path traversal).
- [ ] T-003 Поддержка `.md` front matter: в выдачу добавить `title`, если есть.
- [ ] T-004 Опциональный экстрактор PDF через stdlib-only отказ + явный пункт «нужен пакет» — по умолчанию пропускать PDF.
- [ ] T-005 HTTP-контрактные тесты + фикстура корпуса в `tests/corpus`.
- [ ] T-006 Команда CLI `python -m tool_collections_search.server --reindex-only` для агентного цикла без HTTP.
- [ ] T-007 Ограничение размера одного файла (сейчас 200 КБ) вынести в env `COLLECTIONS_MAX_FILE`.

## Закрыто

- [x] T-000 FTS5 + тест поиска по `note.md`.

