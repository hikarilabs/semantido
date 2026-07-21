---
title: Quickstart with your agent
description: Wire a semantido export into a text-to-SQL loop — the minimum that works, and the parts you must not skip.
---

# Quickstart with your agent

semantido produces a string. Here is the smallest honest thing you can build around it.

## The minimum

```python
import anthropic
from semantido.exporters import to_markdown
from myapp.models import Base

client = anthropic.Anthropic()
layer = Base.sync_semantic_layer()          # once, at startup — not per request
context = to_markdown(layer)

SYSTEM = f"""You are a SQL analyst for a PostgreSQL warehouse.

Return only a SQL query. No prose, no markdown fences.
Respect every application rule stated below — they encode
constraints the schema cannot express.

{context}
"""

def to_sql(question: str) -> str:
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM,
        messages=[{"role": "user", "content": question}],
    )
    return resp.content[0].text
```

Build the layer **once**. It is a pure function of your model files, so rebuilding per request is pure waste.

## The parts you should not skip

The block above will demo well and fail in production. Three additions carry most of the difference, and none is more than a few lines.

### Validate before you execute

```python
def validate(sql: str, conn) -> tuple[bool, str | None]:
    try:
        conn.execute(text(f"EXPLAIN {sql}"))
        return True, None
    except Exception as exc:
        return False, str(exc)
```

`EXPLAIN` is free, needs no data, and catches every hallucinated column and every broken join before the query touches a row.

### Retry with the error

```python
def to_sql_checked(question: str, conn, attempts: int = 2) -> str:
    sql = to_sql(question)
    for _ in range(attempts - 1):
        ok, err = validate(sql, conn)
        if ok:
            return sql
        sql = to_sql(f"{question}\n\nYour previous SQL failed:\n{sql}\n\nError: {err}")
    return sql
```

One retry carrying the database's own error message is the highest-leverage loop in the whole system, and it costs one extra call.

### Read-only, with a cap

Connect with a read-only role and a `statement_timeout`. This is not correctness — it is the difference between a bad query and an incident.

## What semantido is not doing here

Being explicit, because the boundary is the point:

- It does not run the query.
- It does not check the SQL.
- It does not remember the last question.
- It does not know whether the answer was right.

All of that is your pipeline. semantido is the context source. See [How agents consume context](../concepts/how-agents-consume-context.md) for the delivery paths, and [Correctness](../concepts/correctness.md) for what the surrounding system needs.

## Before you call it done: eval

Ten question–SQL pairs with expected results, run in CI, is the difference between engineering and vibes. Without it you cannot tell whether an annotation helped, and you will not notice when someone edits a description and drops accuracy four points.

Write the eval before you write the tenth annotation.
