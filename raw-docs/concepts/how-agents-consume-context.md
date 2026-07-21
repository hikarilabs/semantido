---
title: How does an agent consume semantido context?
description: The three delivery paths — prompt context, structured JSON, and interchange — and how to choose between them.
---

# How does an agent consume semantido context?

semantido produces a document. It does not decide how that document reaches a model. That decision is yours, and it has more consequence than most teams expect.

There are three paths, and they are not interchangeable.

## Path 1 — Markdown in the system prompt

The simplest thing that works, and for most schemas it is the right answer.

```python
from semantido.exporters import to_markdown

layer = Base.sync_semantic_layer()
system_prompt = f"""You are a SQL analyst. Write PostgreSQL.

{to_markdown(layer)}

Rules: return only SQL. Respect all application rules stated above.
"""
```

**Use when:** the whole schema fits comfortably in context — roughly up to 30–50 tables, depending on how richly annotated they are.

**The failure mode is silent.** As the schema grows, the model doesn't error, it just starts attending less well to any given table. Accuracy degrades gradually and you will not get a signal. Watch for it; measure it.

## Path 2 — Retrieval over the layer

Above a certain size, the whole layer stops being the right prompt. Chunk it and retrieve.

Because `SemanticLayer` is a plain dataclass tree, you can chunk it yourself at whatever grain suits — usually per table:

```python
layer = Base.sync_semantic_layer()

for name, table in layer.tables.items():
    text = "\n".join(
        [f"{table.name}: {table.description}"]
        + [f"  {c.name} ({c.data_type}): {c.description}" for c in table.columns]
        + [f"  synonyms: {', '.join(table.synonyms or [])}"]
    )
    index.add(id=name, text=text, metadata={"table": name})
```

Two things to get right:

- **Embed the synonyms.** They exist precisely to catch the vocabulary mismatch between how a user asks and how a column is named. Leaving them out of the embedded text wastes the annotation.
- **Always include relationships for retrieved tables.** Retrieving `orders` and `customers` without the join between them produces a model that invents one. Relationships live on `layer.relationships`; filter them by the retrieved table set and append.

## Path 3 — Tool-served over MCP

Instead of stuffing context into a prompt, serve it. The agent retrieves the models it needs, when it needs them, through a tool call.

The difference is governance surface. A prompt-stuffed schema is all-or-nothing — every request carries every table, whether the caller is entitled to it or not. A tool-served schema is a place you can put access control, filtering, and audit.

See [Integrations](../integrations/overview.md) for the current state of `semantido-mcp`.

## What the agent does not get

Worth being explicit, because it shapes what you build on top:

- **No execution.** semantido never connects to your database. It cannot tell an agent whether the SQL ran, or what came back.
- **No validation.** It will not check the generated SQL against the schema. Do that yourself with `EXPLAIN` or a parser.
- **No retry loop, no repair, no memory.** If the first attempt is wrong, semantido has nothing to say about the second.

These are the responsibilities of the pipeline around semantido, not the library. It is a context source, and it tries to be a very good one, and nothing else.

## Choosing

| Situation | Path |
|---|---|
| < ~30 tables, one agent | Markdown in prompt |
| Large schema, or many domains | Retrieval |
| Multiple agents, or access control matters | MCP |
| A BI tool or catalog is the consumer | [OSI export](../guides/osi.md) |
