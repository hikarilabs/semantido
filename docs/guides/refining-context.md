---
title: Refining context quality
description: How to improve accuracy after the first pass — measure, find the failing annotation, fix, re-measure.
---

# Refining context quality

The first pass of annotations gets most of the gain. Getting the rest is a loop, and the loop needs a measurement or you are guessing.

## Build the eval first

Ten to fifty question–SQL pairs with expected results. That's it. Run them in CI.

```python
CASES = [
    ("How much revenue did we book last month?",
     "SELECT SUM(total_amount) FROM orders "
     "WHERE ordered_at >= date_trunc('month', now() - interval '1 month') "
     "AND ordered_at < date_trunc('month', now())"),
]
```

Compare **result sets**, not SQL strings. There are many correct queries for any question, and string comparison will fail on all but one of them.

Without this you cannot tell whether an annotation helped, and you will not notice when someone edits a description and drops accuracy four points. Every step below assumes it exists.

## Read the failures, not the score

The score tells you there's a problem. The generated SQL tells you which annotation is missing. Diagnose by shape:

| The model did this | The missing annotation |
|---|---|
| Picked the wrong table | Table `description` too vague, or missing `synonyms` |
| Picked the wrong date column | `time_dimension` — see [Modelling time](modelling-time.md) |
| Summed and got a multiple of the right answer | Fan-out. `application_rules` on the measure, grain in the description |
| Filtered on a value that doesn't exist | `sample_values` |
| Used the wrong amount column | Imprecise `description` on the ambiguous cluster |
| Invented a join | Relationship missing from the retrieved context |
| Ignored a stated rule | The rule is prose, not an expression — give it the SQL |

That last row is the one people miss. If the model ignores your rule, the rule is usually unusable rather than unread:

- ❌ `"Be careful when aggregating across parties."`
- ✅ `"Do not SUM notional across trade_party — it fans out. Aggregate on trades first, then join."`

## Change one thing

Annotate one thing, re-run the eval, keep it if it helped. This is tedious and it is the job.

Batching five annotations and watching the score move three points tells you nothing about which of the five did the work — or whether one of them cost you a point while the others gained four.

## Prune

More context is not better context. This is the counterintuitive one, and it follows directly from the [benchmark result](../concepts/correctness.md) that raw DDL had *negative* marginal value.

Every token that carries no signal dilutes the ones that do. Delete:

- `customer_id_description = "The customer ID."` — the fallback is no worse and shorter.
- Synonyms nobody says. `["orders", "order table", "orders data", "the orders"]` is one useful synonym and three distractors.
- Sample values on high-cardinality columns. Five example emails teach the model nothing except that emails exist.
- Tables the agent should never query. Better: don't put them in the layer at all.

Empty values are pruned from `to_json` by default (`include_empty=False`), so a `None` costs nothing. A *bad* description costs.

## Scope the layer

If your agent only ever answers questions about three of your forty tables, exporting forty is forty tables' worth of dilution.

`sync_semantic_layer()` walks the whole registry. To scope, build the layer and filter before export:

```python
layer = Base.sync_semantic_layer()

ANALYTICS = {"orders", "customers", "order_lines"}
layer.tables = {n: t for n, t in layer.tables.items() if n in ANALYTICS}
layer.relationships = [
    r for r in layer.relationships
    if r.from_table in ANALYTICS and r.to_table in ANALYTICS
]

context = to_markdown(layer)
```

Filter relationships too, or you will ship dangling joins to tables that aren't in the document — which is worse than either extreme.

Above roughly 30–50 tables, filtering stops being enough and you want retrieval. See [How agents consume context](../concepts/how-agents-consume-context.md).

## The glossary

`layer.application_glossary` is a `dict[str, str]` for terms that belong to no single table:

```python
layer.application_glossary["ACV"] = "Annual contract value — see the finance definition, not the sales one."
layer.application_glossary["active customer"] = "Placed an order in the trailing 90 days."
```

It rides into the OSI export as model-level `ai_context.instructions`. It's the right home for cross-cutting definitions and the wrong home for anything that's really about one column.

## Watch for description rot

The annotation that describes a column correctly today describes it incorrectly after the migration that changes its meaning without changing its name. Code-native authoring makes this *visible* — the description is right there in the diff — but it does not make it *automatic*. Nothing checks that a description is still true.

Reviewing semantic annotations is part of reviewing a migration. It is the one part of this that is a human process.
