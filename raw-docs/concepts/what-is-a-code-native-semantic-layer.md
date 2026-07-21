---
title: What is a code-native semantic layer?
description: A semantic layer is the difference between an agent that can read your schema and an agent that can answer your questions. semantido keeps that layer where the schema already lives.
---

# What is a code-native semantic layer?

A semantic layer is the difference between an agent that can *read* your schema and an agent that can *answer* your questions.

DDL tells an agent that a table has columns. A semantic layer tells it what a row means, which enum value maps to which state, which joins fan out, and which date column an analyst actually means when they say "last month".

That distinction is not cosmetic. Text-to-SQL agents do not fail on production schemas because the model isn't smart enough. They fail because the meaning they need was never written down anywhere the agent can read — it lives in analysts' heads, in a Confluence page nobody updated, in the tribal knowledge that `status = 4` means *reversed*, not *refunded*.

## Why DDL is not enough

The intuition that "the model can just read the schema" is strong, and wrong in a specific and measurable way.

Raw DDL is high-volume, low-signal. It offers the model dozens of plausible-looking columns with no indication of which is canonical, dilutes the tokens that carry actual meaning, and invites the model to reconstruct business logic from column names. The model does what you'd expect: picks a plausible table, writes plausible SQL, returns a plausible number.

Plausible numbers are the failure mode that matters. A query that errors is free. A query that returns 4,182 when the answer is 3,907 is expensive, and in a regulated context it is a finding.

**Text-to-SQL over business data is bottlenecked on meaning, not on model capability.** The measurements are in [Correctness](correctness.md).

## The layers of meaning

For an agent to answer a real question on a real schema, it needs more than one kind of knowledge:

| Layer | What it answers | In semantido |
|---|---|---|
| **Structural** | What exists? | Extracted from the SQLAlchemy mapper |
| **Descriptive** | What does this mean? | `description`, `synonyms`, `sample_values` |
| **Temporal** | When is "when"? | `time_dimension`, `time_grain` |
| **Relational** | How does it connect? | Join conditions and cardinality, extracted |
| **Operational** | How must it be used? | `application_rules`, `sql_filters`, `privacy_level` |

The first and fourth you already have — SQLAlchemy knows them. The rest is what you are currently paying for in wrong answers.

## Why code-native

Most semantic layers ask you to describe your schema a second time: in YAML, in a different directory, maintained on a different cadence. This works right up until someone renames a column.

The failure is structural, not disciplinary. A YAML file describing a schema is a *copy* of the truth, and copies drift. There is no compiler, no test, and no code review that catches the moment a semantic definition stops describing the table it claims to describe. You find out when an agent confidently queries a column that was dropped two sprints ago.

semantido takes the other path: the semantic layer is authored **on the SQLAlchemy models themselves**.

This buys three properties a sidecar file cannot:

- **The definition cannot drift from the schema**, because it is attached to it. Delete the column, and the description goes with it.
- **It travels through code review.** Semantic changes appear in the same diff as the migration that caused them, in front of the person who understands both.
- **It is testable.** Your test suite already imports these models. `sync_semantic_layer()` needs no database, so asserting on the semantic layer is an ordinary unit test.

The cost is real and worth stating plainly: this only works if SQLAlchemy is your source of truth. See [Why semantido](why-semantido.md#skip-semantido-if).

## Context is not memory

Some semantic layer systems learn: they store confirmed question–SQL pairs and retrieve them for similar future questions. semantido does not, and this is a design position rather than a gap.

A learning loop makes the layer's behaviour a function of its history. That is useful for a hosted product and disqualifying for an artifact that has to be auditable. semantido's output is a **pure function of your model files** — same models in, byte-identical document out. See [Determinism](determinism.md).

If you want a memory layer, build it above semantido. Keep the substrate boring.

## In short

- **DDL** tells an agent what exists — and on its own, actively hurts.
- **Semantic definitions** tell an agent what the data means.
- **A code-native semantic layer** keeps those definitions true, because they live where the schema lives and die when it dies.
