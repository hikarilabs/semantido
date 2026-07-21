---
title: How does semantido keep agents from hallucinating?
description: It doesn't — not alone. Here is what the semantic layer measurably fixes, what it doesn't, and what you still have to build.
---

# How does semantido keep agents from hallucinating?

It doesn't, not on its own, and any library that claims otherwise is selling something.

What semantido does is remove a specific and dominant class of error: the model guessing at meaning it was never given. That class is large — large enough to be worth measuring — but it is not all of them.

## What we measured

We benchmarked LLM SQL generation accuracy across two schemas: a production fitness-tracking schema (`mushiki_bench`, private) and a synthetic EMIR/MiFIR regulatory reporting schema (`regreport_bench`, public), against GPT-4o and Claude Sonnet, with a shared scoring engine.

Two findings:

- **Semantic context improved accuracy by ~22 percentage points on average.**
- **Raw DDL had negative marginal value.** Adding a full `CREATE TABLE` dump to a prompt that already carried semantic context made results *worse*.

The second result surprises people. The mechanism is mundane: DDL is long, uniform, and uninformative about meaning. It pushes the ratio of signal to tokens down and gives the model more plausible-looking wrong columns to choose from. The `to_markdown` exporter emits no DDL for exactly this reason.

## The three failure modes

The [trade reporting example](https://github.com/hikarilabs/semantido/tree/main/examples/01_getting_started) is built around the three that recur on every real schema.

### Bridge fan-out

A many-to-many bridge table joined into an aggregate silently multiplies rows. The model sums `notional` across the join and reports a number that is 3.4× correct. Nothing errors.

The annotation that fixes it:

```python
notional_application_rules = [
    "Do not SUM across the trade_party bridge — it fans out. "
    "Aggregate on trades first, then join."
]
```

### Sign conventions

`amount` is always positive; the direction lives in `direction_code`. A model that sums `amount` gets gross where the user meant net.

```python
amount_description = (
    "Absolute value. Sign is carried by direction_code "
    "('P' = pay, 'R' = receive). Net = SUM(CASE WHEN direction_code = 'R' "
    "THEN amount ELSE -amount END)."
)
```

Note the shape: the description carries the *fix*, not just the warning. A model told "be careful" is not helped. A model given the CASE expression is.

### Amount ambiguity

`notional`, `notional_eur`, `mtm_value`, `collateral_value` — four columns, all plausibly "the amount". This is what `synonyms` and precise `description` exist for, and it is where most of the 22 points come from.

The same problem in the time domain — four plausible date columns — is severe enough to get [its own model](../guides/modelling-time.md).

## What semantido does not fix

Being blunt about the boundary:

- **It cannot validate SQL.** No parser, no `EXPLAIN`, no schema check. Bring your own.
- **It cannot detect ambiguity.** If the question is underspecified, semantido has no opinion. Clarification is a pipeline concern.
- **It cannot profile values.** `sample_values` is what *you* typed, not what is in the table. If it drifts from reality, semantido will not know.
- **It cannot retry or repair.** One attempt is all it participates in.
- **It cannot stop a model from ignoring an application rule.** They go in the prompt. The model is free to disregard them, and sometimes will.

## What to build around it

A production text-to-SQL system needs, roughly in order of return:

1. **Eval.** A held-out set of question–SQL pairs with expected results, run in CI. Without this you cannot tell whether an annotation helped, and you will not notice a regression when someone edits a description.
2. **Execution validation.** `EXPLAIN` the generated SQL before running it. Free, catches a lot.
3. **Read-only credentials and a row cap.** Not correctness, but the difference between a bad query and an incident.
4. **Ambiguity detection.** A cheap pre-flight classifier: is this question answerable from this schema?
5. **Retry with the error message.** The single highest-leverage loop, and it costs one extra call.

semantido is step zero. It is the highest-leverage single change, and it is not the system.

## In short

- Semantic context bought ~22pp; raw DDL cost accuracy.
- The wins come from naming the three things schemas never say: fan-out, sign, and ambiguity.
- Correctness is a system. semantido is one component of it, and only claims to be.
