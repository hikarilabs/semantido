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

### What `to_json` gives you

The same layer as a machine-readable tree — empty values pruned by default, so un-authored fields cost nothing. An excerpt of the `orders` table:

```json
{
  "tables": {
    "orders": {
      "name": "orders",
      "description": "Customer orders — one row per order.",
      "primary_key": "order_id",
      "synonyms": ["orders", "purchases"],
      "business_context": "total_amount is gross, including tax and shipping.",
      "time_dimension": "ordered_at",
      "columns": [
        {
          "name": "customer_id",
          "data_type": "INTEGER",
          "description": "Column: customer_id",
          "is_foreign_key": true,
          "references": "customers.customer_id"
        },
        {
          "name": "ordered_at",
          "data_type": "TIMESTAMP",
          "description": "Column: ordered_at",
          "is_foreign_key": false,
          "is_time_dimension": true,
          "time_grain": "second"
        },
        {
          "name": "total_amount",
          "data_type": "DECIMAL",
          "description": "Gross order total, including tax and shipping.",
          "synonyms": ["order value", "revenue"],
          "is_foreign_key": false
        }
      ]
    }
  }
}
```

This is the format for when *your own code* is the consumer — chunking for retrieval, filtering before export, or feeding a tool schema. Note `references` and `is_time_dimension`: extracted and validated, never typed by hand.

??? example "Full `to_json` output (both tables + relationships)"

    ```json
    {
        "tables": {
            "customers": {
                "name": "customers",
                "description": "Customers who have placed at least one order.",
                "primary_key": "customer_id",
                "columns": [
                    {
                        "name": "customer_id",
                        "data_type": "INTEGER",
                        "description": "Column: customer_id",
                        "is_foreign_key": false
                    },
                    {
                        "name": "email",
                        "data_type": "VARCHAR",
                        "description": "Column: email",
                        "privacy_level": "confidential",
                        "is_foreign_key": false
                    }
                ]
            },
            "orders": {
                "name": "orders",
                "description": "Customer orders \u2014 one row per order.",
                "primary_key": "order_id",
                "synonyms": [
                    "orders",
                    "purchases"
                ],
                "business_context": "total_amount is gross, including tax and shipping.",
                "time_dimension": "ordered_at",
                "columns": [
                    {
                        "name": "order_id",
                        "data_type": "INTEGER",
                        "description": "Column: order_id",
                        "is_foreign_key": false
                    },
                    {
                        "name": "customer_id",
                        "data_type": "INTEGER",
                        "description": "Column: customer_id",
                        "is_foreign_key": true,
                        "references": "customers.customer_id"
                    },
                    {
                        "name": "ordered_at",
                        "data_type": "TIMESTAMP",
                        "description": "Column: ordered_at",
                        "is_foreign_key": false,
                        "is_time_dimension": true,
                        "time_grain": "second"
                    },
                    {
                        "name": "total_amount",
                        "data_type": "DECIMAL",
                        "description": "Gross order total, including tax and shipping.",
                        "synonyms": [
                            "order value",
                            "revenue"
                        ],
                        "is_foreign_key": false
                    },
                    {
                        "name": "status",
                        "data_type": "VARCHAR",
                        "description": "Column: status",
                        "sample_values": [
                            "PENDING",
                            "SHIPPED",
                            "CANCELLED"
                        ],
                        "is_foreign_key": false
                    },
                    {
                        "name": "created_at",
                        "data_type": "TIMESTAMP",
                        "description": "Column: created_at",
                        "is_foreign_key": false
                    }
                ]
            }
        },
        "relationships": [
            {
                "from_table": "customers",
                "to_table": "orders",
                "join_condition": "customers.customer_id = orders.customer_id",
                "relationship_type": "one-to-many",
                "description": "Relationship between customers and orders"
            },
            {
                "from_table": "orders",
                "to_table": "customers",
                "join_condition": "orders.customer_id = customers.customer_id",
                "relationship_type": "many-to-one",
                "description": "Relationship between orders and customers"
            }
        ]
    }
    ```

### What `to_osi_yaml` gives you

The complete OSI document for the two-table model — every line below was generated by the quickstart code above, nothing edited:

```yaml
version: 0.2.0.dev0
semantic_model:
- name: commerce
  custom_extensions:
  - vendor_name: SEMANTIDO
    data: '{"exporter": "semantido.exporters.osi"}'
  datasets:
  - name: customers
    source: customers
    primary_key:
    - customer_id
    description: Customers who have placed at least one order.
    fields:
    - name: customer_id
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: customer_id
      description: 'Column: customer_id'
    - name: email
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: email
      description: 'Column: email'
      custom_extensions:
      - vendor_name: SEMANTIDO
        data: '{"privacy_level": "confidential"}'
  - name: orders
    source: orders
    primary_key:
    - order_id
    description: Customer orders — one row per order.
    ai_context:
      instructions: total_amount is gross, including tax and shipping.
      synonyms:
      - orders
      - purchases
    fields:
    - name: order_id
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: order_id
      description: 'Column: order_id'
    - name: customer_id
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: customer_id
      description: 'Column: customer_id'
    - name: ordered_at
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: ordered_at
      description: 'Column: ordered_at'
      dimension:
        is_time: true
      ai_context:
        instructions: 'PRIMARY time dimension for this dataset. Native grain: second.'
      custom_extensions:
      - vendor_name: SEMANTIDO
        data: '{"is_primary_time_dimension": true, "time_grain": "second"}'
    - name: total_amount
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: total_amount
      description: Gross order total, including tax and shipping.
      ai_context:
        synonyms:
        - order value
        - revenue
    - name: status
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: status
      description: 'Column: status'
      custom_extensions:
      - vendor_name: SEMANTIDO
        data: '{"sample_values": ["PENDING", "SHIPPED", "CANCELLED"]}'
    - name: created_at
      expression:
        dialects:
        - dialect: ANSI_SQL
          expression: created_at
      description: 'Column: created_at'
      ai_context:
        instructions: Operational audit timestamp — do not use as a time axis for business
          questions.
  relationships:
  - name: customers_to_orders
    from: customers
    to: orders
    from_columns:
    - customer_id
    to_columns:
    - customer_id
    ai_context:
      instructions: Relationship between customers and orders
    custom_extensions:
    - vendor_name: SEMANTIDO
      data: '{"relationship_type": "one-to-many"}'
```

Worth pausing on what happened to the two timestamp columns:

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

Also note where the semantido-specific metadata went: `privacy_level`, `sample_values`, `time_grain`, and relationship cardinality ride in `custom_extensions` under the `SEMANTIDO` vendor, because OSI has no first-class home for them yet. A consumer that ignores extensions still gets the datasets, fields, and relationships. See [OSI export](../guides/osi.md).

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
