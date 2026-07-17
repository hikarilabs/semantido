---
title: Semantic metadata reference
description: Every attribute you can author, and what it maps to.
---

# Semantic metadata reference

The complete authoring surface. Two mechanisms: decorator arguments for tables, `<column>_<concern>` class attributes for fields.

## Table level — `@semantic_table`

```python
@semantic_table(
    description: str,                          # required
    synonyms: list[str] | None = None,
    sql_filters: list[str] | None = None,
    application_context: str | None = None,
    business_context: str | None = None,
    time_dimension: str | None = None,
)
```

| Argument | Type | Notes |
|---|---|---|
| `description` | `str` | **Required.** Put the grain here: "one row per order". |
| `synonyms` | `list[str]` | What users call this entity. `["client", "customer"]` |
| `sql_filters` | `list[str]` | Default-filter / RLS fragments. **Advisory** — not enforced. |
| `application_context` | `str` | Technical or functional scope within the app. |
| `business_context` | `str` | Business domain, and what to know before trusting a number. |
| `time_dimension` | `str` | Column name of the primary business time axis. Validated at sync. |

Each writes to a dunder you can set directly instead:

| Argument | Dunder |
|---|---|
| `description` | `__semantic_description__` |
| `synonyms` | `__semantic_synonyms__` |
| `sql_filters` | `__semantic_sql_filters__` |
| `application_context` | `__semantic_application_context__` |
| `business_context` | `__semantic_business_context__` |
| `time_dimension` | `__semantic_time_dimension__` |

`time_dimension` on the decorator and `__semantic_time_dimension__` on the **same class body** with different values raises `ValueError`. A dunder inherited from a mixin or base is overridable by the decorator — so a base can set a default.

Missing decorator → fallback description `"Table: <tablename>"`.

## Column level — `<column>_<concern>`

Attributes on the class body, named for the column they annotate.

| Attribute | Type | Notes |
|---|---|---|
| `<col>_description` | `str` | Falls back to `"Column: <name>"` |
| `<col>_synonyms` | `list[str]` | |
| `<col>_sample_values` | `list[str]` | Representative values. Useless on high-cardinality columns. |
| `<col>_application_rules` | `list[str]` | Constraints an agent must respect. Give expressions, not warnings. |
| `<col>_privacy_level` | `PrivacyLevel` | **Advisory** — a label, not a control. |
| `<col>_is_time_dimension` | `bool` | Marks a *secondary* time axis. |
| `<col>_time_grain` | `TimeGrain \| str` | Native resolution — the floor for `GROUP BY`. |

```python
class Order(SemanticDeclarativeBase):
    total_amount = Column(Numeric(12, 2))

    total_amount_description = "Gross order total, including tax and shipping."
    total_amount_synonyms = ["order value", "revenue"]
    total_amount_application_rules = [
        "Do not SUM across the order_lines join — it fans out."
    ]
```

!!! warning "Typos are silent"
    Attributes are read by name. `total_ammount_description` matches no column and is ignored — no error. See [Versioning and CI](../guides/versioning-and-ci.md#gate-on-coverage).

## Relationship level

| Attribute | Type |
|---|---|
| `<relationship_attr>_relationship_description` | `str` |

```python
    order_lines = relationship("OrderLine", back_populates="order")
    order_lines_relationship_description = (
        "One row per line item. Joining here multiplies order rows."
    )
```

Fallback: `"Relationship between <from> and <to>"`.

## Enums

All in `semantido.generators.semantic_layer`.

### `PrivacyLevel`

`PUBLIC` · `INTERNAL` · `RESTRICTED` · `CONFIDENTIAL`

### `TimeGrain`

`SECOND` · `MINUTE` · `HOUR` · `DAY` · `WEEK` · `MONTH` · `QUARTER` · `YEAR`

Ordered — `TimeGrain.DAY < TimeGrain.MONTH` is `True`. Accepts case-insensitive strings at authoring time (`"day"` → `TimeGrain.DAY`); invalid values raise at sync with the valid list. A grain finer than the column type supports (`SECOND` on a `Date`) warns.

### `RelationshipType`

`ONE_TO_ONE` · `ONE_TO_MANY` · `MANY_TO_ONE` · `MANY_TO_MANY`

Extracted automatically. You never author this.

## Extracted, never authored

| Concern | Source |
|---|---|
| Primary keys | Mapper |
| Foreign keys, `references` (`table.column`) | Mapper |
| Relationships, join conditions, cardinality | Mapper |
| Column data types (normalised) | Mapper |
| `schema` | `__table_args__` |

This is the core economy of the design. A join condition typed by hand is a join condition that can be wrong.

## Sync-time validation

`sync_semantic_layer()` raises on:

- `time_dimension` naming a column not on the table
- `time_dimension` naming a non-`Date`/`DateTime` column
- `<col>_time_grain` that isn't a valid `TimeGrain`
- `time_dimension` conflicting with `__semantic_time_dimension__` on the same class body

Warns on:

- a declared grain finer than the column type can carry

Silently ignores:

- `<col>_*` attributes matching no column
