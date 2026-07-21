---
title: dbt and warehouse-side layers
description: When semantido is the wrong tool, when it's complementary, and how to avoid maintaining two truths.
---

# dbt and warehouse-side layers

This page is mostly about when **not** to use semantido.

## The question that decides it

**Which artifact is the source of truth for the schema your agent queries?**

- If it's a **SQLAlchemy model** → semantido is the right shape.
- If it's a **dbt model** → author in dbt. semantido would be describing a copy.

That's the whole decision. Everything below is elaboration.

## Why authoring in the wrong place is worse than not authoring

If dbt owns the marts and you annotate SQLAlchemy models that mirror them, you have rebuilt exactly the problem code-native authoring exists to solve: a description that lives apart from the thing it describes, free to drift.

Worse than the YAML case, in fact — at least dbt's YAML is drifting alongside the model it ships with. A SQLAlchemy mirror of a dbt mart drifts across a repository boundary, on a different release cadence, maintained by a different team.

**Accurate descriptions of the wrong schema are worse than no descriptions.** They make an agent confident.

## The common architectures

### Application database, SQLAlchemy-owned

Your app defines the tables; migrations are Alembic; agents query the same database.

**semantido, straightforwardly.** This is the case it's built for.

### dbt warehouse, no application models

Sources land in a warehouse, dbt transforms, agents query marts. No SQLAlchemy anywhere.

**Not semantido.** Use dbt's own `description:` fields, or a warehouse-side semantic layer. There's no mapper to read.

### Both — app OLTP plus a dbt warehouse

The common and awkward one. Your app is SQLAlchemy; analytics run on dbt marts derived from it.

Two truths, two audiences. Options, in order:

1. **Map the warehouse in SQLAlchemy.** Declare models against the marts — `__table__` reflection works, and `<column>_*` annotations attach to reflected columns fine. Now the mapper describes what the agent actually queries, and semantido is back in its element.

    ```python
    class OrdersMart(SemanticDeclarativeBase):
        __table__ = Table("fct_orders", metadata, autoload_with=engine)
        total_amount_description = "Gross order total, including tax and shipping."
    ```

    Cost: a model file that exists only for semantics. Benefit: it's *validated* against the real table at reflection time, which the dbt YAML isn't.

2. **Author in dbt, skip semantido for the analytics surface.** Perfectly reasonable. Use semantido only if you also have agents querying the OLTP side.

3. **Author in both, reconcile via OSI.** Both export OSI; merge downstream. Viable, more moving parts than most teams need, and now you have two places to forget to update.

**What not to do:** annotate the OLTP models and point the agent at the warehouse. That's drift with extra steps.

## Complementary, not competing

Where both exist legitimately, they're doing different jobs:

| | dbt | semantido |
|---|---|---|
| Describes | Warehouse marts | Application schema |
| Authored in | YAML beside the model | Python, on the model |
| Drift risk | Low within dbt; the YAML ships with the SQL | None — same object |
| Audience | Analysts, BI, catalogs | Agents, RAG, text-to-SQL |
| Exports OSI | Increasingly | Yes |

OSI is the meeting point. If both sides export it, a downstream consumer can read one merged model without either side adopting the other's tooling.

## Cube, AtScale, Wren

Different category. Those are **systems** — they hold definitions, run queries, serve results, cache aggregates. semantido produces a document and goes away.

The interesting composition is feeding them: author in code, export OSI, let the platform execute. You get code-native authoring and drift resistance; they get to do the part semantido has no interest in doing.

Whether that composition is worth it depends on how good their OSI import is this quarter. Check before you architect around it.
