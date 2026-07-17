---
title: Architecture
description: How ~20 files turn annotated mappers into a semantic document.
---

# Architecture

semantido is a small library with a linear pipeline and no state. Reading it end to end takes about twenty minutes.

```
semantido/
├── decorators/
│   └── semantic_table.py        # writes dunders onto the class
├── models/
│   ├── semantic_base.py         # SemanticBase mixin — sync_semantic_layer()
│   └── declarative_base.py      # Base, SemanticDeclarativeBase
├── generators/
│   ├── semantic_bridge.py       # extraction engine: mappers -> SemanticLayer
│   ├── semantic_layer.py        # the dataclasses + enums (the IR)
│   └── utils/
│       ├── sqlalchemy_mapping.py    # type normalisation, metadata reads, FK resolution
│       └── time_grain.py            # grain normalisation + type compatibility
└── exporters/
    ├── json_exporter.py
    ├── markdown_exporter.py
    └── osi_exporter.py
```

## The pipeline

```
@semantic_table        →  dunders on the class
<col>_* attributes     →  plain class attributes
                              │
                              ▼
       SemanticBase.sync_semantic_layer()
                              │
                              ▼
       SQLAlchemySemanticBridge.sync_from_models()
         ├─ walk the declarative registry
         ├─ _extract_table       ← extract_table_metadata (dunders)
         ├─ _extract_column      ← extract_column_metadata (<col>_* attrs)
         │                       ← resolve_foreign_key (mapper)
         │                       ← normalize_time_grain
         └─ _extract_relationships  ← join conditions + direction (mapper)
                              │
                              ▼
                        SemanticLayer
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          to_json        to_markdown     to_osi_dict/yaml
```

Three stages: **author** (attributes on classes), **extract** (bridge → IR), **render** (exporter → text). Each is independently testable, and the seam between extract and render is why the same layer can serve a prompt and a BI tool.

## Why attributes instead of a column wrapper

The obvious design is a `SemanticColumn(...)` wrapper replacing `Column(...)`. semantido reads `<column>_description` class attributes instead. This trades IDE support for reach.

A wrapper only annotates columns you construct. The attribute convention annotates **any mapped column** — from a mixin, an inherited base, a `__table__` reflection, a hybrid property. Given that reflection against an existing warehouse is a first-class use case ([see dbt guide](../guides/dbt-and-warehouse-layers.md)), the wrapper design would have excluded it.

The cost is real and worth naming: typos are silent. That's what the [coverage test](../guides/versioning-and-ci.md#gate-on-coverage) is for.

## Why the IR exists

The `SemanticLayer` dataclass tree could have been skipped — the bridge could render Markdown directly. It exists because:

- **Exporters multiply.** N exporters × 1 IR beats N × mapper-walking code.
- **It's the test surface.** Asserting on `layer.tables["orders"].time_dimension` is a better test than grepping rendered Markdown.
- **It's the extension point.** Filter it, scope it, inject a glossary — all before export. The [privacy filtering pattern](../guides/privacy-and-governance.md#what-they-are-actually-for) only works because there's an object between extraction and rendering.

Plain dataclasses, no validation framework, no ORM of its own.

## Where determinism comes from

Two structural properties, no discipline required:

- **No I/O in the path.** No database, no network, no LLM. Nothing that can vary.
- **Ordering follows the mapper**, which follows declaration order in your files.

See [Determinism](../concepts/determinism.md).

## The bridge is cached, the layer is not

`get_semantic_bridge()` lazily builds one bridge per base and caches it on the class (`_semantic_bridge`). `sync_semantic_layer()` clears and re-extracts on **every call** — it is a full re-walk, not an incremental update.

That's cheap but not free. Call it once at startup; don't call it per request. See [Build once](../guides/versioning-and-ci.md#build-once).

## What isn't here

No CLI. No server. No config file. No plugin system. No database driver. No query engine.

The library does one thing — mappers in, document out — and the surface is deliberately small enough that the whole thing fits in your head.
