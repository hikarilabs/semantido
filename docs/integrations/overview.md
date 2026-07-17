---
title: Integrations
description: What exists today, what's early, and what you'll build yourself.
---

# Integrations

The honest inventory. semantido produces strings and dicts, which makes integration easy and means there are fewer official adapters than you might expect — for most frameworks, an adapter would be a one-line wrapper around `to_markdown`.

## What ships in the library

| | |
|---|---|
| **Markdown export** | ✅ Stable. Prompt context. |
| **JSON export** | ✅ Stable. For your own code. |
| **OSI YAML export** | ⚠️ Works; tracks a pre-1.0 spec (`0.2.0.dev0`). [Guide](../guides/osi.md) |

That's the whole shipped surface. Everything below is either a separate package or something you write.

## semantido-mcp

An MCP server giving agents access to semantido-annotated SQLAlchemy schemas, with enterprise bridge tools targeting DataHub and AtScale.

**Status: early, separate package.** Check the [Hikari Labs GitHub org](https://github.com/hikarilabs) for current state before planning around it. Do not assume the interface below is final.

The case for tool-serving over prompt-stuffing is governance surface: a prompt-stuffed schema is all-or-nothing, while a tool-served one is a place to put access control, filtering, and audit. See [How agents consume context](../concepts/how-agents-consume-context.md#path-3-tool-served-over-mcp).

## LLM frameworks

There is no `semantido-langchain` package, and there probably shouldn't be. The integration is:

```python
from semantido.exporters import to_markdown

context = to_markdown(Base.sync_semantic_layer())
```

Then put `context` in your system prompt. That's the same line for LangChain, LlamaIndex, DSPy, the raw API, or Claude Code. A package wrapping it would add a dependency and a version to track, and remove nothing.

Where a real adapter would earn its keep — retrieval over a chunked layer, tool-schema generation — the shape is too application-specific to be worth freezing into a library. The [retrieval pattern](../concepts/how-agents-consume-context.md#path-2-retrieval-over-the-layer) is about fifteen lines; copy it and own it.

## BI tools and catalogs

Via [OSI](../guides/osi.md), with a caveat worth taking seriously: OSI is pre-1.0 and ecosystem support is early. semantido puts `privacy_level`, `sample_values`, `time_grain`, and cardinality into `custom_extensions` under the `SEMANTIDO` vendor — a consumer that doesn't read extensions silently drops them.

**Verify against the actual consumer before you architect around it.** Export a model, import it, check what survived.

## dbt

Not an integration — an architectural decision about which artifact owns the truth. See [dbt and warehouse-side layers](../guides/dbt-and-warehouse-layers.md).

## What you'll build yourself

Realistically, most of the pipeline:

- **Retrieval**, above ~30–50 tables
- **SQL validation** (`EXPLAIN` before execute)
- **Retry with the error message**
- **Eval** — the one you cannot skip
- **Access filtering** — [filter the layer before export](../guides/privacy-and-governance.md#what-they-are-actually-for)

This is the design, not an omission. semantido is a context source. [Correctness is a system](../concepts/correctness.md), and the system is yours.
