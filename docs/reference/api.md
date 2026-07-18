---
title: API reference
description: The public surface — imports, signatures, defaults.
---

# API reference

## Top level

```python
from semantido import (
    semantic_table,             # the decorator
    SemanticDeclarativeBase,    # ready-made base
    SemanticBase,               # mixin for your own base
    SemanticLayer,              # the IR
    SQLAlchemySemanticBridge,   # the extraction engine
)
```

## Base classes

### `SemanticDeclarativeBase`

`SemanticBase` + SQLAlchemy's `DeclarativeBase`. Inherit from it and you're done.

### `SemanticBase`

Mixin, if you already have a base:

```python
class Base(SemanticBase, DeclarativeBase):
    pass
```

**`classmethod sync_semantic_layer(concept_registry: ConceptRegistry | None = None) -> SemanticLayer`**

Walks the registry and re-extracts every table, column, and relationship. No database connection. Deterministic. When a `concept_registry` is passed, every `concept=` / `<column>_concept` reference is validated against it — unresolved references raise `ValueError` listing all of them — and the registry is attached to the returned layer for export.

**`classmethod get_semantic_bridge() -> SQLAlchemySemanticBridge`**

Lazily builds the bridge by walking the MRO for the SQLAlchemy registry. Raises `RuntimeError` if there isn't one. You rarely need this.

## Decorator

```python
semantic_table(
    description: str,
    synonyms: list[str] | None = None,
    sql_filters: list[str] | None = None,
    application_context: str | None = None,
    business_context: str | None = None,
    time_dimension: str | None = None,
    concept: str | None = None,        # v0.4.0 — id of a registered concept
)
```

Full semantics in the [semantic metadata reference](semantic-metadata.md).

## Exporters

```python
from semantido.exporters import (
    to_json, to_json_file,
    to_markdown, to_markdown_file,
    to_osi_dict, to_osi_yaml,
)
```

### JSON

```python
to_json(semantic_layer: SemanticLayer, include_empty: bool = False) -> str
to_json_file(layer: SemanticLayer, file_path: str, include_empty: bool = False) -> None
```

`include_empty=False` prunes `None`, `[]`, `{}` recursively. File output is indented 4.

### Markdown

```python
to_markdown(layer: SemanticLayer, include_empty: bool = False) -> str
to_markdown_file(layer: SemanticLayer, file_path: str,
                 include_empty: bool = False, table: bool = False) -> None
```

`table=True` emits the table-shaped variant instead of the nested-list one. The function behind it, `to_markdown_table`, is importable from `semantido.exporters.markdown_exporter` but isn't part of the top-level export surface — treat it as less stable.

### OSI

```python
to_osi_dict(
    semantic_layer: SemanticLayer,
    model_name: str,
    description: str | None = None,
    instructions: str | None = None,
    audit_pattern: re.Pattern = DEFAULT_AUDIT_PATTERN,
) -> dict

to_osi_yaml(
    semantic_layer: SemanticLayer,
    model_name: str,
    path: str | None = None,
    **kwargs,          # forwarded to to_osi_dict
) -> str
```

`to_osi_yaml` requires PyYAML (`pip install 'semantido[osi]'`) and raises a clear `ImportError` without it. `to_osi_dict` doesn't. Returns the YAML text whether or not `path` is given.

Constants in `semantido.exporters.osi_exporter`:

| | |
|---|---|
| `OSI_SPEC_VERSION` | `"0.2.0.dev0"` |
| `DEFAULT_DIALECT` | `"ANSI_SQL"` |
| `VENDOR` | `"SEMANTIDO"` |
| `DEFAULT_AUDIT_PATTERN` | `created`/`updated`/`modified`/`inserted`/`deleted`/`loaded`/`ingested`/`processed`/`synced`/`etl`, optional `_at`/`_on`/`_ts`/`_time`/`_timestamp`/`_date` suffix, case-insensitive |

## Data model

`semantido.generators.semantic_layer` — plain dataclasses, safe to construct and mutate.

### `SemanticLayer`

```python
tables: dict[str, Table]
relationships: list[Relationship]
application_glossary: dict[str, str]
concept_registry: ConceptRegistry | None    # v0.4.0

add_table(table: Table)
add_relationship(relationship: Relationship)
to_dict(include_empty: bool = False) -> dict
```

!!! warning "Deprecated"
    `SemanticLayer.to_json()` and `.to_file()` are deprecated. Use `semantido.exporters.to_json` / `to_json_file`.

### `Table`

```python
name: str
description: str
columns: list[Column]
primary_key: str | None
schema: str | None = None
synonyms: list[str] | None = None
sql_filters: list[str] | None = None
application_context: str | None = None
business_context: str | None = None
time_dimension: str | None = None
concept: str | None = None           # v0.4.0
```

### `Column`

```python
name: str
data_type: str
description: str
privacy_level: PrivacyLevel
sample_values: list[str] | None = None
synonyms: list[str] | None = None
is_foreign_key: bool = False
references: str | None = None        # "table.column"
application_rules: list[str] | None = None
is_time_dimension: bool | None = False
time_grain: TimeGrain | None = None
concept: str | None = None           # v0.4.0
```

### `Relationship`

```python
from_table: str
to_table: str
join_condition: str
relationship_type: RelationshipType
description: str
```

### Enums

`PrivacyLevel`, `TimeGrain`, `RelationshipType` — see the [metadata reference](semantic-metadata.md#enums).

## Concepts — `semantido.concepts` *(v0.4.0)*

```python
from semantido.concepts import (
    ConceptRegistry, Concept, OntologySource,
    ConceptRelation, MappingRelation, ExternalMapping,
    exact_match, close_match, narrow_match, broad_match, related_match,
)
```

`semantido.concepts` is the canonical import path; the same objects live at `semantido.generators.concept_registry`.

### `ConceptRegistry`

| Method | Purpose |
|---|---|
| `concept(concept_id, definition, *, label=None, synonyms=None, broader=None, narrower=None, same_as=None, related=None, distinct_from=None, external=None) -> Concept` | The only authoring path. Relation kwargs take `Concept` handles (or iterables); symmetric relations (`same_as`, `related`, `distinct_from`) auto-reciprocate. |
| `add_source(source: OntologySource) -> None` | Registers a pinned external ontology release. |
| `find_homonyms() -> dict[str, list[str]]` | Labels/synonyms claimed by more than one concept → their ids. |
| `subset(concept_ids: set[str]) -> ConceptRegistry` | Self-contained sub-registry closed over the ids via relations. |
| `validate() -> None` | Referential checks; collects all violations, raises once. |
| `to_dict()` / `to_yaml(path=None)` | Serialization; YAML is the sidecar `concepts.yaml` form. |

### `Concept`

Fields: `id`, `label`, `definition`, `synonyms`, `mappings`, `relations`, plus computed `definition_checksum` — a stable fingerprint of the definition text.

### `OntologySource`

```python
OntologySource(name: str, namespace: str, version: str,
               location: str | None = None, profile: str | None = None)
```

`version` is required: an unpinned mapping cannot be validated or detected as stale.

### Mapping helpers

`exact_match(source, target, because=None)` and siblings (`close_match`, `narrow_match`, `broad_match`, `related_match`) each build an `ExternalMapping` carrying its SKOS relation — an untyped mapping is unrepresentable.

Full behaviour and worked example: [The concept registry](../guides/concept-registry.md).

## Requirements

Current release: **0.4.0**. Python ≥ 3.11 · SQLAlchemy ≥ 2.0 · typing-extensions ≥ 4.5

Extras: `osi` (PyYAML), `dev`, `publish`.
