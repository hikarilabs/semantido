---
title: Where does semantido sit in my stack?
description: Between your SQLAlchemy models and everything that needs to understand them. Not in the query path.
---

# Where does semantido sit in my stack?

semantido sits at **build time**, between your model files and whatever needs to understand them. It is not in the query path, does not hold state, and never sees a row of your data.

```
                     ┌───────────────────────────────┐
                     │  SQLAlchemy models (.py)      │
                     │  + semantic annotations       │
                     └──────────────┬────────────────┘
                                    │  sync_semantic_layer()
                                    │  (no DB connection)
                                    ▼
                     ┌───────────────────────────────┐
                     │  SemanticLayer  (dataclasses) │
                     └──────────────┬────────────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼
        to_markdown()          to_json()            to_osi_yaml()
              │                     │                      │
              ▼                     ▼                      ▼
        LLM prompt /          your own code /       BI tools, catalogs,
        RAG index             MCP server            other semantic layers
```

Your application still talks to the database through SQLAlchemy exactly as it did. semantido is a second, read-only consumer of the same model definitions.

## What this means practically

**No connection, no credentials, no runtime cost.** `sync_semantic_layer()` reads the mapper registry. You can run it in CI, in a test, or at import time in a process that has no database access at all.

**It runs at build time, not request time.** Build the layer once when your app starts, or generate the artifact in CI and commit it. Rebuilding per request is pure waste — the answer cannot change without a code change.

**It is additive.** Nothing about your existing models has to change except adopting `SemanticDeclarativeBase` (or mixing in `SemanticBase`). Un-annotated models still export, with generated fallback descriptions.

## Where it sits relative to the neighbours

**Relative to dbt / your warehouse.** If dbt owns the transformation layer and your SQLAlchemy models read the marts, semantido describes the marts as your application understands them. That may or may not be the right place to author — see [dbt and warehouse layers](../guides/dbt-and-warehouse-layers.md) for when it isn't.

**Relative to Cube / AtScale / Wren.** Those are systems that hold semantic definitions and serve queries against them. semantido produces a document. Via OSI, it can *feed* them rather than compete with them: author in code, export to the platform's format, let the platform do execution.

**Relative to a data catalog.** Catalogs are discovery surfaces for humans; semantido's output is context for machines. The OSI export is the bridge — same definitions, catalog-shaped.

**Relative to your agent framework.** semantido is upstream of all of it. LangChain, LlamaIndex, a bare API call, Claude Code — they consume a string. semantido produces the string.

## Two schemas, one truth

The awkward case worth naming: your OLTP models are SQLAlchemy, but the agent queries a warehouse where the same concepts have different names.

semantido describes what its mappers describe. If the warehouse table is a different shape, annotating the OLTP model does not help — the agent gets accurate descriptions of the wrong schema, which is worse than nothing.

The options, in order of preference:

1. **Map the warehouse.** Declare SQLAlchemy models against the warehouse tables (`__table__` reflection works, and annotations attach to reflected columns fine). Now the mapper describes what the agent queries.
2. **Author warehouse-side.** If the marts are dbt-owned and dbt-shaped, put the semantics in dbt and skip semantido for that surface.
3. **Do both, and reconcile via OSI.** Viable, and more moving parts than most teams need.

Do not annotate the OLTP schema and point the agent at the warehouse. That is drift with extra steps.
