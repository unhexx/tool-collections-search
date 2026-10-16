# TASK_SPECIFICATION.md — tool-collections-search

**Project:** tool-collections-search
**Version Target:** 1.0
**Primary Goal:** SQLite FTS5 search over a local corpus on 127.0.0.1, a client-side replacement for collections_search.

## Business Objectives

- Bootstrap the Agentix loop in this repository
- Ship the first INVEST task with tests

## Scope

**In scope:** application code, tests, and docs for this repository
**Out of scope:** vendoring a copy of agentic_loop_template

## Success Criteria

- All INVEST tasks in `.agent/TODO.md` marked DONE with tests passing.
- Reviewer approves with `status=DONE` and clean git sync.

All loop output must use strict JSON handoffs per `HANDOFF_SCHEMA.md`.