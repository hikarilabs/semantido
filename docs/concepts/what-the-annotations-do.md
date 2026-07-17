---
title: What do the annotations do for the agent?
description: The causal chain from what you write, to what gets built, to what the model actually reads.
---

# What do the annotations do for the agent?

An annotation is not decoration. Every attribute you author lands somewhere specific and does a specific job for the model reading it.

This page is the chain: **what you write → what gets built → what the agent sees**.

## The two authoring surfaces

semantido deliberately has only two.

### The decorator — table-level meaning

```python
@semantic_table(
    description="Customer orders — one row per order.",
    synonyms=["orders", "purchases"],
    business_context="total_amount is gross, including tax and shipping.",
    application_context="Checkout and fulfilment.",
    sql_filters=["orders.tenant_id = :tenant_id"],
    time_dimension="ordered_at",
)
class Order(SemanticDeclarativeBase):
    ...
```

Each argument answers a question the schema can't:

| Argument | The question it answers |
|---|---|
| `description` | What is a row of this table? |
| `synonyms` | What might a user call this thing? |
| `business_context` | What must someone know before trusting a number from here? |
| `application_context` | Which part of the system owns this? |
| `sql_filters` | What should always apply — tenancy, soft deletes? |
| `time_dimension` | When someone says "last month", which column do they mean? |

The decorator writes these to dunders (`__semantic_description__`, and so on); you can set those directly instead. `time_dimension` and `__semantic_time_dimension__` conflicting on the same class body raises `ValueError` rather than silently picking one.

### The column convention — field-level meaning

There is no column decorator. semantido reads class attributes named `<column>_<concern>`:

```python
class Order(SemanticDeclarativeBase):
    total_amount = Column(Numeric(12, 2))

    total_amount_description = "Gross order total, including tax and shipping."
    total_amount_synonyms = ["order value", "revenue"]
    total_amount_application_rules = ["Do not SUM across order_lines — it fans out."]
    status_sample_values = ["PENDING", "SHIPPED", "CANCELLED"]
    email_privacy_level = PrivacyLevel.CONFIDENTIAL
    ordered_at_time_grain = TimeGrain.SECOND
```

This looks unusual and is a deliberate trade — it costs IDE autocomplete on the metadata, and buys the ability to annotate **any** mapped column, including from mixins, inherited bases, or `__table__` reflection. See [Architecture](../reference/architecture.md#why-attributes-instead-of-a-column-wrapper).

Full list: [semantic metadata reference](../reference/semantic-metadata.md).

## What you never author

Everything the mapper already knows is extracted:

- primary keys
- foreign keys and their `table.column` targets
- relationships, their **join conditions**, and their **cardinality**
- column data types, normalised

This is the core economy of the design. You author what the schema cannot express, and nothing else. A join condition typed by hand is a join condition that can be wrong.

## What gets built

`sync_semantic_layer()` walks the registry and produces a `SemanticLayer` — a plain dataclass tree:

```
SemanticLayer
├── tables: dict[str, Table]
│   └── Table(name, description, columns, primary_key, schema, synonyms,
│             sql_filters, application_context, business_context, time_dimension)
│       └── columns: list[Column]
│           └── Column(name, data_type, description, privacy_level, sample_values,
│                     synonyms, is_foreign_key, references, application_rules,
│                     is_time_dimension, time_grain)
├── relationships: list[Relationship]
│   └── Relationship(from_table, to_table, join_condition, relationship_type, description)
└── application_glossary: dict[str, str]
```

No database connection, no I/O. Build it, assert on it in tests, mutate it before export.

## What the agent sees

The `SemanticLayer` is not what reaches the model — an **exporter** is, and the choice matters:

- **`to_markdown`** — terse, prose-shaped, for the system prompt.
- **`to_json`** — the tree, empty values pruned, for your own code.
- **[`to_osi_yaml`](../guides/osi.md)** — interchange, when something else is the consumer.

`to_markdown` renders roughly this:

```markdown
### orders
- **Primary Key**: order_id
- **Description**: Customer orders — one row per order.
- **Synonyms**: orders, purchases
- **Business Context**: total_amount is gross, including tax and shipping.

#### Columns
- **total_amount** (DECIMAL)
  - Gross order total, including tax and shipping.
  - *Synonyms*: order value, revenue
```

Note what's absent: no `CREATE TABLE`, no nullability, no indexes. That absence is the product — see [Correctness](correctness.md).

## In short

- The **decorator** carries table meaning; the **`<column>_*` convention** carries field meaning.
- The **mapper** carries structure, and you should never retype it.
- The **`SemanticLayer`** is the IR — inspectable, testable, plain.
- The **exporter** decides what the model reads, and the Markdown one is deliberately thin.
