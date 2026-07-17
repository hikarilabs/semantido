---
title: Modelling time
description: Every fact table has four plausible date columns. This is the annotation with the highest return in semantido.
---

# Modelling time

Most semantic layer specs treat time as one more dimension. In practice it is the single largest source of silent wrongness in generated SQL.

The reason is easy to see once stated: every fact table has three or four plausible date columns, and the model has no way to know which one the analyst means.

`created_at`, `updated_at`, `completed_at`, `reported_at`, `value_date`, `trade_date`, `settlement_date`.

In capital markets that last cluster is not a naming quibble. Trade date and settlement date differ by two business days; picking wrong is a reporting break, and the query still returns a number.

## Declare the primary axis

```python
@semantic_table(
    description="Customer orders — one row per order.",
    time_dimension="ordered_at",
)
class Order(SemanticDeclarativeBase):
    ordered_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime)
```

One line. It means: when someone says "last month", they mean `ordered_at`.

It is **validated at sync time**, not at export. If the named column doesn't exist on the table, or isn't a `Date`/`DateTime`, `sync_semantic_layer()` raises. A typo here fails your test suite instead of quietly producing a model with no time axis.

Equivalent, if you prefer the class body:

```python
class Order(SemanticDeclarativeBase):
    __semantic_time_dimension__ = "ordered_at"
```

Setting both to *different* values on the same class body raises `ValueError`. A dunder inherited from a mixin is overridable by the decorator — that's intentional, so a base class can set a default.

## Declare the grain

```python
    ordered_at_time_grain = TimeGrain.SECOND
```

The grain is the **floor for `GROUP BY`** — the native resolution of the column. A `DATE` column with `TimeGrain.DAY` tells the consumer that grouping by hour is meaningless, not merely unhelpful.

Values: `SECOND`, `MINUTE`, `HOUR`, `DAY`, `WEEK`, `MONTH`, `QUARTER`, `YEAR`. Strings work too, so model files don't need the import:

```python
    booking_date_time_grain = "day"      # normalised to TimeGrain.DAY
```

Invalid values raise at sync time with the valid list. Declaring a grain finer than the column type supports — `TimeGrain.SECOND` on a `Date` column — emits a warning, since a `DATE` cannot carry sub-day information.

`TimeGrain` is ordered, so `TimeGrain.DAY < TimeGrain.MONTH` is `True` if you need to reason about grain in your own code.

## Secondary axes

A table can have more than one legitimate business time axis. Trade date *and* settlement date are both real questions.

```python
class Trade(SemanticDeclarativeBase):
    trade_date = Column(Date)
    settlement_date = Column(Date)

    __semantic_time_dimension__ = "trade_date"        # the default

    settlement_date_is_time_dimension = True          # also legitimate
    settlement_date_time_grain = "day"
    settlement_date_description = (
        "Settlement date, normally T+2. Use for cash and liquidity questions. "
        "Regulatory reporting deadlines are driven by trade_date, not this."
    )
```

`time_dimension=` marks the **primary** axis; `<column>_is_time_dimension = True` marks additional ones. In the OSI export the primary is labelled `PRIMARY time dimension for this dataset`, and secondaries are flagged `dimension.is_time` without the primacy claim.

## Audit column demotion

This is the part that does work you didn't ask for.

Temporal columns whose names look like audit timestamps are **automatically demoted** on OSI export — flagged with an explicit instruction not to use them as a time axis:

```yaml
- name: created_at
  ai_context:
    instructions: Operational audit timestamp — do not use as a time axis
      for business questions.
```

The default pattern catches `created`, `updated`, `modified`, `inserted`, `deleted`, `loaded`, `ingested`, `processed`, `synced`, `etl` — with or without an `_at` / `_on` / `_ts` / `_time` / `_timestamp` / `_date` suffix, case-insensitive.

This matters because *not saying anything* about `created_at` is not neutral. A model looking for a date column will find it and use it. Silence is a vote.

Override per export:

```python
import re

to_osi_yaml(layer, model_name="commerce",
            audit_pattern=re.compile(r"(^|_)(etl|ingested)_at$"))

to_osi_yaml(layer, model_name="commerce",
            audit_pattern=re.compile(r"$^"))          # disable demotion entirely
```

Override it if your `created_at` genuinely *is* the business event — an append-only event log is the common case. Check the export rather than assuming; the default is a heuristic on names, and heuristics on names are sometimes wrong.

!!! note "Markdown export"
    Demotion is an OSI-export behaviour. The Markdown exporter renders what the layer holds. If you rely on prompt context and want the same signal, put it in the description:

    ```python
    created_at_description = "Row insert time. Not a business date — use ordered_at."
    ```

## In short

- Declare `time_dimension` on every fact table. One line, validated, removes an error class.
- Declare `time_grain` where the floor matters.
- Mark secondary axes explicitly; describe how they differ.
- Check what the audit demoter did, and override when your `created_at` is real.
