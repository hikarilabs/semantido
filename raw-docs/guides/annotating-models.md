---
title: Annotating your models
description: The full authoring surface — what to write, where, and in what order.
---

# Annotating your models

There is no "connect your database" step in semantido. The equivalent first move is adopting the base class and annotating what the schema can't say.

## Adopt the base

```python
from semantido import SemanticDeclarativeBase

class Order(SemanticDeclarativeBase):
    ...
```

If you already have a `DeclarativeBase` of your own, mix in `SemanticBase` instead — it carries the machinery and leaves your base intact:

```python
from sqlalchemy.orm import DeclarativeBase
from semantido import SemanticBase

class Base(SemanticBase, DeclarativeBase):
    pass
```

Both give you `Base.sync_semantic_layer()`. Un-annotated models still export, with fallback descriptions (`"Table: orders"`, `"Column: status"`). Adoption is incremental — you can annotate one table today.

## Table level

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

`description` is the only required argument.

**Write the grain into the description.** "One row per order" is worth more than any other sentence you will write, because fan-out errors are silent. Compare:

- ❌ `"Order data."`
- ✅ `"Customer orders — one row per order. Line items are in order_lines."`

`sql_filters` are SQL fragments for default filtering or row-level security. They are **advisory** — semantido puts them in the export, it does not enforce them. A model can ignore them. Do not treat this as a security control.

## Column level

There is no column decorator. Annotate via class attributes named `<column>_<concern>`:

```python
class Order(SemanticDeclarativeBase):
    total_amount = Column(Numeric(12, 2))
    status = Column(String(16))
    email = Column(String(255))

    total_amount_description = "Gross order total, including tax and shipping."
    total_amount_synonyms = ["order value", "revenue"]
    total_amount_application_rules = [
        "Do not SUM across the order_lines join — it fans out."
    ]
    status_sample_values = ["PENDING", "SHIPPED", "CANCELLED"]
    email_privacy_level = PrivacyLevel.CONFIDENTIAL
```

Full list: [semantic metadata reference](../reference/semantic-metadata.md).

The convention costs you IDE autocomplete on the metadata. It buys you the ability to annotate any mapped column — including from mixins, inherited bases, or `__table__` reflection — without touching the column definition.

!!! warning "Typos are silent"
    `total_ammount_description` doesn't raise. It just doesn't appear. `<column>_*` attributes are read by name; a name that matches no column is ignored. See [Versioning and CI](versioning-and-ci.md) for the coverage check that catches this.

## Relationships

Join conditions, cardinality, and foreign keys are extracted. You only add *why*:

```python
    order_lines = relationship("OrderLine", back_populates="order")
    order_lines_relationship_description = (
        "One row per line item. Joining here multiplies order rows — "
        "aggregate order totals before joining."
    )
```

The attribute is `<relationship_attr>_relationship_description`. Without it, you get `"Relationship between orders and order_lines"`, which tells the model nothing it couldn't infer.

## What to write first

Annotating everything is a bad use of a week. Ordered by return:

1. **Grain, in every table description.** "One row per X."
2. **The time dimension.** One line, and it removes an entire error class. See [Modelling time](modelling-time.md).
3. **The ambiguous amounts.** Wherever three columns could all be "the amount", describe the difference precisely.
4. **The fan-out rules.** Every bridge and every one-to-many that gets summed.
5. **Enum meanings**, via `sample_values` — and if the values are codes, spell out what they mean in the description.
6. **Synonyms**, on the tables and columns users actually name.
7. Everything else, if you feel like it.

The first four are ~80% of the benchmark gain. Stop when your eval stops improving.

## Writing descriptions that work

**Carry the fix, not the warning.** A model told "be careful with sign conventions" is not helped. A model given the expression is:

```python
amount_description = (
    "Absolute value. Sign is carried by direction_code "
    "('P' = pay, 'R' = receive). Net = SUM(CASE WHEN direction_code = 'R' "
    "THEN amount ELSE -amount END)."
)
```

**Say what's different, not what's obvious.** `customer_id_description = "The customer ID"` is tokens with no signal. Delete it; the fallback is no worse.

**Name the trap.** If there's a deprecated column people still use, say so in the live one's description.
