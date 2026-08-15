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

Mixin if you already have a base:

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
    to_markdown_schema, to_markdown_tables, to_markdown_concepts,   # v0.5.0 tiers
    to_ossie_dict, to_ossie_yaml,
    to_skos_turtle, to_skos_file,                                   # v0.4.1
    to_groundings_dict, to_groundings_yaml, to_groundings_file,     # v0.5.0
    load_groundings,                                                # v0.5.0
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
to_markdown(layer: SemanticLayer, include_empty: bool = False,
            include: tuple[str, ...] = ("schema", "enriched", "concepts")) -> str
to_markdown_file(layer: SemanticLayer, file_path: str,
                 include_empty: bool = False, table: bool = False,
                 include: tuple[str, ...] = ("schema", "enriched", "concepts")) -> None
```

*(v0.5.0)* `include` selects the tiers, rendered additively in this order:

| Section | Contents |
|-----------|----------|
| `schema` | Bare physical structure — tables, keys, column types, FK targets, relationships. |
| `enriched` | Authored semantics layered onto the schema — descriptions, synonyms, filters, glossary. Additive over `schema`: `include=("enriched",)` alone raises. |
| `concepts` | The concept registry sections, cross-referenced via *Realized by* / *Realizes concepts*. |

`"tables"` is accepted as a back-compat alias for `("schema", "enriched")`. Unknown section names raise `ValueError` listing the valid set.

The dedicated single-tier helpers:

```python
to_markdown_schema(layer: SemanticLayer, include_empty: bool = False) -> str
to_markdown_tables(layer: SemanticLayer, include_empty: bool = False) -> str
to_markdown_concepts(layer: SemanticLayer | ConceptRegistry, scope: str | None = None) -> str
```

`to_markdown_concepts` accepts a bare registry or a layer carrying one; `scope="bound"` (default) renders the closure referenced by the physical layer, `scope="all"` the entire registry.

`table=True` on `to_markdown_file` emits the table-shaped variant instead of the nested-list one. The function behind it, `to_markdown_table`, is importable from `semantido.exporters.markdown_exporter` but isn't part of the top-level export surface — treat it as less stable.

### Apache Ossie

```python
to_ossie_dict(
    semantic_layer: SemanticLayer,
    model_name: str,
    description: str | None = None,
    instructions: str | None = None,
    audit_pattern: re.Pattern = DEFAULT_AUDIT_PATTERN,
) -> dict

to_ossie_yaml(
    semantic_layer: SemanticLayer,
    model_name: str,
    path: str | None = None,
    **kwargs,          # forwarded to to_ossie_dict
) -> str
```

`to_ossie_yaml` requires PyYAML (`pip install 'semantido[ossie]'`) and raises a clear `ImportError` without it. `to_ossie_dict` doesn't. Returns the YAML text whether `path` is given.

Constants in `semantido.exporters.ossie_exporter`:

|                             |                                                                                                                                                                                      |
|-----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `APACHE_OSSIE_SPEC_VERSION` | `"0.2.0.dev0"`                                                                                                                                                                       |
| `DEFAULT_DIALECT`           | `"ANSI_SQL"`                                                                                                                                                                         |
| `VENDOR`                    | `"SEMANTIDO"`                                                                                                                                                                        |
| `DEFAULT_AUDIT_PATTERN`     | `created`/`updated`/`modified`/`inserted`/`deleted`/`loaded`/`ingested`/`processed`/`synced`/`etl`, optional `_at`/`_on`/`_ts`/`_time`/`_timestamp`/`_date` suffix, case-insensitive |

### SKOS *(v0.4.1)*

```python
to_skos_turtle(source: SemanticLayer | ConceptRegistry, base_uri: str | None = None) -> str
to_skos_file(source: SemanticLayer | ConceptRegistry, file_path: str,
             base_uri: str | None = None) -> None
```

Serializes the concept registry as a SKOS concept scheme in Turtle. Accepts a bare registry or a layer carrying one. Concept URIs are minted as `{base_uri}{concept_id}`; `base_uri` defaults to a URN derived from the registry namespace (`urn:semantido:{namespace}:`), so the export is valid without owning a domain. No dependencies beyond core.

### Groundings *(v0.5.0)*

```python
to_groundings_dict(layer: SemanticLayer) -> dict
to_groundings_yaml(layer: SemanticLayer) -> str        # needs PyYAML
to_groundings_file(layer: SemanticLayer, file_path: str) -> None
load_groundings(source: str | dict) -> dict
```

The deployment-side half of the meaning/deployment split: which tables and columns realize each concept in *this* schema, stamped with each concept's `definition_checksum` at recording time. `load_groundings` accepts a path or an already-parsed dict and validates the document shape (`format: semantido/groundings`). Consumed by `semantido.lint` for SL007 staleness checks in both directions. See [the groundings guide](../guides/groundings.md).

Anchor strings are `table.column`; table names may themselves contain dots (Kafka topic names like `etd.executions`) — the final segment is the column *(v0.5.1)*.

## Lint — `semantido.lint` *(v0.5.0)*

```python
from semantido.lint import lint_layer, Finding, Severity

lint_layer(layer, groundings: str | dict | None = None) -> list[Finding]
```

Tier-2 static checks for the seams between claim systems — SL001–SL010, deterministic order, errors first. Passing `groundings` (a path or dict) enables SL007. Requires sqlglot (`pip install 'semantido[lint]'`).

`Finding` is a dataclass: `code`, `severity`, `location`, `message`. `Severity` is an enum: `ERROR`, `WARNING`. Errors should gate CI; warnings should not. Check semantics: [Linting the layer](../guides/lint.md).

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
unique_keys: list[list[str]] | None = None   # v0.5.0 — extracted UniqueConstraints, PK excluded
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

| Method                                                                                                                                                                 | Purpose                                                                                                                                                       |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `concept(concept_id, definition, *, label=None, synonyms=None, broader=None, narrower=None, same_as=None, related=None, distinct_from=None, external=None, grain=None) -> Concept` | The only authoring path. Relation kwargs take `Concept` handles (or iterables); symmetric relations (`same_as`, `related`, `distinct_from`) auto-reciprocate. |
| `add_source(source: OntologySource) -> None`                                                                                                                           | Registers a pinned external ontology release.                                                                                                                 |
| `find_homonyms() -> dict[str, list[str]]`                                                                                                                              | Labels/synonyms claimed by more than one concept → their ids.                                                                                                 |
| `subset(concept_ids: set[str]) -> ConceptRegistry`                                                                                                                     | Self-contained sub-registry closed over the ids via relations.                                                                                                |
| `validate() -> None`                                                                                                                                                   | Referential checks; collects all violations, raises once.                                                                                                     |
| `to_dict()` / `to_yaml(path=None)`                                                                                                                                     | Serialization; YAML is the sidecar `concepts.yaml` form.                                                                                                      |

### `Concept`

Fields: `id`, `label`, `definition`, `synonyms`, `mappings`, `relations`, `grain` *(v0.5.0)*, plus computed `definition_checksum` — a stable fingerprint of the definition text.

`grain` declares the level at which the concept identifies or measures its subject (`"issue"` / `"listing"` / `"product"` in the security-master idiom). Free-form, compared verbatim by the linter: joins between columns bound to concepts of different grain are SL008 errors. Grain is about cardinality only: two concepts may share a grain and still denote different things, which is what `distinct_from` and SL009 cover.

### `OntologySource`

```python
OntologySource(name: str, namespace: str, version: str,
               location: str | None = None, profile: str | None = None)
```

`version` is required: an unpinned mapping cannot be validated or detected as stale.

### Mapping helpers

`exact_match(source, target, because=None)` and siblings (`close_match`, `narrow_match`, `broad_match`, `related_match`) each build an `ExternalMapping` carrying its SKOS relation — an untyped mapping is unrepresentable.

Full behavior and worked example: [The concept registry](../guides/concept-registry.md).

## Requirements

Current release: **0.5.2**. Python ≥ 3.11 · SQLAlchemy ≥ 2.0 · typing-extensions ≥ 4.5

Extras: `ossie` (PyYAML), `lint` (sqlglot), `dev`, `publish`.
