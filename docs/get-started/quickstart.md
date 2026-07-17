---
title: Quickstart
description: Annotate two models and export LLM-ready context in five minutes. No database required.
---

# Quickstart

We'll annotate a two-table commerce schema and export it three ways. **No database connection is needed at any point** — semantido reads mappers, not data.

```console
pip install 'semantido[osi]'
```

## 1. Annotate your models

```python
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from semantido import semantic_table, SemanticDeclarativeBase
from semantido.generators.semantic_layer import PrivacyLevel, TimeGrain


@semantic_table(
    description="Customer orders — one row per order.",
    synonyms=["orders", "purchases"],
    business_context="total_amount is gross, including tax and shipping.",
    time_dimension="ordered_at",
)
class Order(SemanticDeclarativeBase):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"))
    ordered_at = Column(DateTime, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(16), nullable=False)
    created_at = Column(DateTime)

    ordered_at_time_grain = TimeGrain.SECOND
    total_amount_description = "Gross order total, including tax and shipping."
    total_amount_synonyms = ["order value", "revenue"]
    status_sample_values = ["PENDING", "SHIPPED", "CANCELLED"]

    customer = relationship("Customer", back_populates="orders")


@semantic_table(description="Customers who have placed at least one order.")
class Customer(SemanticDeclarativeBase):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)

    email_privacy_level = PrivacyLevel.CONFIDENTIAL

    orders = relationship("Order", back_populates="customer")
```

Two things to notice, because they are the whole design:

- **You inherit from `SemanticDeclarativeBase`** instead of your own `DeclarativeBase`. That's the only structural change to an existing model file.
- **You never wrote a join.** `customer_id → customers.customer_id`, the cardinality, and the join condition all come out of the mapper. You author what the schema can't express, and nothing else.

## 2. Build the layer

```python
layer = SemanticDeclarativeBase.sync_semantic_layer()
```

`layer` is a plain dataclass tree — `layer.tables`, `layer.relationships`, `layer.application_glossary`. Inspect it, assert on it in tests, mutate it before export.

## 3. Export

```python
from semantido.exporters import to_json, to_markdown, to_osi_yaml

to_markdown(layer)                          # LLM prompt context
to_json(layer)                              # structured, machine-readable
to_osi_yaml(layer, model_name="commerce")   # vendor-neutral interchange
```

### What `to_markdown` gives you

```markdown
### orders
- **Full Name**: orders
- **Primary Key**: order_id
- **Description**: Customer orders — one row per order.
- **Synonyms**: orders, purchases
- **Business Context**: total_amount is gross, including tax and shipping.

#### Columns
- **order_id** (INTEGER)
- **customer_id** (INTEGER) ForeignKey → customers.customer_id
- **total_amount** (DECIMAL)
  - Gross order total, including tax and shipping.
  - *Synonyms*: order value, revenue
- **status** (VARCHAR)
  - *Examples*: PENDING, SHIPPED, CANCELLED

## Relationships (2 connections)

### customers → orders
- **Type**: one-to-many
- **Join**: customers.customer_id = orders.customer_id
```

Note what's missing: no `CREATE TABLE`, no nullability, no index definitions. That absence is the point — see [Correctness](../concepts/correctness.md).

### What `to_osi_yaml` gives you

The interesting part is what happened to the two timestamp columns:

```yaml
- name: ordered_at
  dimension:
    is_time: true
  ai_context:
    instructions: 'PRIMARY time dimension for this dataset. Native grain: second.'

- name: created_at
  ai_context:
    instructions: Operational audit timestamp — do not use as a time axis
      for business questions.
```

You declared `time_dimension="ordered_at"`. You said nothing about `created_at` — semantido recognised it as an audit column by name and **actively demoted it**, telling the consumer not to use it. Left alone, `created_at` is one of the most reliable sources of wrong answers in text-to-SQL. See [Modelling time](../guides/modelling-time.md).

## 4. Put it in a prompt

```python
system_prompt = f"""You are a SQL analyst. Write PostgreSQL only.

{to_markdown(layer)}
"""
```

That's the whole integration. semantido produces a string; what you do with it is your pipeline.

## A realistic example

The two-table version above is a tutorial. [`examples/01_getting_started`](https://github.com/hikarilabs/semantido/tree/main/examples/01_getting_started) is a walkthrough on a synthetic EMIR/MiFIR regulatory reporting subset that deliberately encodes the three classic text-to-SQL failure modes — bridge fan-out, sign conventions, and amount ambiguity — and shows the annotations that counter each. Reference exports in all three formats are committed alongside it.

## Next

- [Annotating your models](../guides/annotating-models.md) — the full authoring surface
- [Modelling time](../guides/modelling-time.md) — the highest-value annotation you can write
- [Quickstart with your agent](quickstart-with-agent.md)
