---
title: Overview
description: semantido is code-native semantic layer authoring for SQLAlchemy — annotate your models where they live, export LLM-ready context wherever your stack needs it.
---

# semantido

**Code-native semantic layer authoring for SQLAlchemy.** Annotate your models where they live, and generate LLM-ready schema context for text-to-SQL agents, RAG pipelines, and BI tools — as JSON, Markdown, or vendor-neutral [OSI](https://open-semantic-interchange.org) YAML.

A database schema tells an LLM what your tables are called — not what they *mean*. semantido closes that gap without introducing a separate modelling language or a YAML repository to keep in sync.

```console
pip install semantido
```

## The shape of it

Semantic metadata is declared next to the SQLAlchemy models it describes:

```python
from semantido import semantic_table, SemanticDeclarativeBase

@semantic_table(
    description="Customer orders — one row per order.",
    synonyms=["orders", "purchases"],
    business_context="total_amount is gross, including tax and shipping.",
    time_dimension="ordered_at",
)
class Order(SemanticDeclarativeBase):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True)
    total_amount = Column(Numeric(12, 2), nullable=False)

    total_amount_description = "Gross order total, including tax and shipping."
    total_amount_synonyms = ["order value", "revenue"]
```

One call extracts models, columns, and relationships — with join conditions and cardinality — into a semantic layer you can export anywhere:

```python
from semantido.exporters import to_json, to_markdown, to_osi_yaml

layer = SemanticDeclarativeBase.sync_semantic_layer()

to_markdown(layer)                          # LLM prompt context
to_json(layer)                              # structured, machine-readable
to_osi_yaml(layer, model_name="commerce")   # vendor-neutral interchange
```

## Why this and not a YAML repo

Because a YAML file describing a schema is a *copy* of the truth, and copies drift. There is no compiler and no code review that catches the moment a semantic definition stops describing the table it claims to describe.

Annotations attached to the model are reviewed in the same pull request, versioned in the same git history, and refactored by the same tools. Delete the column, and its description goes with it.

## Where to go next

- **[Installation](get-started/installation.md)** and **[Quickstart](get-started/quickstart.md)** — running in five minutes
- **[What is a code-native semantic layer?](concepts/what-is-a-code-native-semantic-layer.md)** — the idea underneath
- **[Why semantido (and how it compares)](concepts/why-semantido.md)** — the honest version, including when to skip it
- **[Semantic metadata reference](reference/semantic-metadata.md)** — every attribute you can author

## Status

semantido is **alpha** (`Development Status :: 3 - Alpha`). The authoring surface — `@semantic_table` and the `<column>_*` conventions — is stable in practice and used in production. Exporter output, particularly OSI, tracks a spec that is itself pre-1.0 and should be expected to move.

Apache-2.0. [Source on GitHub](https://github.com/hikarilabs/semantido).
