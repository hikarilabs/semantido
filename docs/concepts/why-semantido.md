---
title: Why semantido? (and how it compares)
description: What semantido is for, what it is not, and how it differs from the tools it sits near.
---

# Why semantido? (and how it compares)

semantido is **code-native semantic layer authoring**: a way to declare what your schema means, next to the SQLAlchemy models that define it, and export that meaning to whatever consumes it. This page is the honest version — what it is for, what it is *not*, and where it loses.

## The problem semantido solves

Agents are everywhere: Claude Code, Cursor, ChatGPT, LangChain pipelines, in-house copilots. None of them know what your data *means*. Point one at a warehouse and it writes confident, plausible, wrong SQL, because the meaning it needs never got written down anywhere it can read.

The specific things a schema doesn't say are remarkably consistent:

- bridge tables that fan out and silently double-count
- amount columns whose sign convention lives in a separate code column
- three different columns that all look like "the amount"
- four different columns that all look like "the date"

semantido's answer is narrow on purpose: put that meaning in the model file, and get a deterministic artifact out.

## How semantido compares

|  | Raw DDL in the prompt | A YAML semantic layer (dbt, Cube) | A semantic layer platform (Wren, AtScale) | **semantido** |
|---|---|---|---|---|
| Describes what columns *mean* | ❌ | ✅ | ✅ | ✅ |
| Cannot drift from the schema | ✅ | ❌ | ❌ | ✅ |
| Reviewed in the same PR as the migration | ✅ | ❌ | ❌ | ✅ |
| Runs queries / serves results | ❌ | ✅ | ✅ | ❌ |
| Ships a UI | ❌ | ❌ | ✅ | ❌ |
| Vendor-neutral export | n/a | partial | partial | ✅ (OSI) |
| Works without SQLAlchemy | ✅ | ✅ | ✅ | ❌ |

Distinctions worth being precise about:

- **vs. dumping DDL into the prompt:** this is the comparison people assume is close. It isn't. Raw DDL is high-volume, low-signal, and in our benchmark it had *negative* marginal value — see [Correctness](correctness.md).
- **vs. a YAML semantic layer:** dbt and Cube define metrics in files that live apart from the schema. That works, and it works across warehouses semantido never sees. The tradeoff is drift: nothing structurally prevents the YAML from describing a column that no longer exists.
- **vs. a semantic layer platform:** Wren, AtScale, and friends are *systems* — they run queries, serve dashboards, hold state. semantido is a library that produces a document. It does not compete with them; it can feed them.

## semantido is for you if…

- Your SQLAlchemy models are the **source of truth** for the schema you want agents to query.
- You are building **text-to-SQL or RAG** over a real, gnarly, production schema.
- You want semantic definitions that are **reviewable and versioned** in the repo the engineers already work in.
- You need to hand a semantic model to something else — a BI tool, a catalog, an agent framework — and don't want to bet on one vendor's format.
- You are in a **regulated environment** and need "who changed the definition of *notional*, when, and in which PR" to have an answer.

## Skip semantido if…

- **SQLAlchemy is not your source of truth.** If your models are generated from the warehouse, or the tables are owned by a dbt project, or your Python service reads tables it doesn't define, code-native authoring is the wrong shape. Use a warehouse-side layer.
- **You need query execution, caching, or aggregation.** semantido never touches your database. It reads mappers, not data.
- **You want a UI.** There isn't one, and there isn't going to be one.
- **You need cross-warehouse metric federation.** That is a platform problem.

## Where to go next

- [What is a code-native semantic layer?](what-is-a-code-native-semantic-layer.md) — the idea underneath
- [Where does semantido sit in my stack?](stack-position.md)
- [Quickstart](../get-started/quickstart.md)
