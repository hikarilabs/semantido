---
title: OSI (Open Semantic Interchange)
description: Export a vendor-neutral semantic model — how the mapping works, what's lossy, and why you'd want it.
---

# OSI (Open Semantic Interchange)

[OSI](https://open-semantic-interchange.org) is a vendor-neutral format for exchanging semantic models. semantido exports to it, which means: author once in code, hand the model to whatever consumes it.

```console
pip install 'semantido[osi]'
```

```python
from semantido.exporters import to_osi_dict, to_osi_yaml

layer = Base.sync_semantic_layer()

to_osi_yaml(layer, model_name="commerce", path="model.osi.yaml")
to_osi_dict(layer, model_name="commerce")     # no PyYAML needed
```

Only YAML serialisation needs PyYAML. `to_osi_dict()` works on the core install — useful if you're handing the structure to a JSON API or your own writer.

## Why bother

The semantic layer market is unsettled and will stay that way for a while. Cube, dbt, AtScale, Wren, Snowflake, Databricks, and a dozen others all want your definitions in their format, and the switching cost is the definitions themselves.

OSI is the bet that you shouldn't have to make that choice permanent. Author in code, export to the interchange format, let the consumer of the month read it.

The honest caveat: **OSI is pre-1.0.** semantido targets spec version `0.2.0.dev0`. Ecosystem support is early. This is a position on where things are going, not a description of where they are.

## The mapping

| semantido | OSI |
|---|---|
| `Table` | `dataset` (with `source = schema.table`) |
| `Column` | `field`, with an ANSI SQL `expression` |
| `Table.primary_key` | `dataset.primary_key` |
| `Table.description` | `dataset.description` |
| `business_context` | `dataset.ai_context.instructions` |
| `synonyms` | `ai_context.synonyms` |
| `time_dimension` | `field.dimension.is_time` + primacy note in `ai_context` |
| `Relationship` | `relationships[]` with `from_columns` / `to_columns` |
| `application_glossary` | model-level `ai_context.instructions` |
| `privacy_level`, `sample_values`, `time_grain`, cardinality | `custom_extensions` (vendor `SEMANTIDO`) |

Field expressions are emitted in the `ANSI_SQL` dialect.

## What lands in custom_extensions

OSI has no first-class home for some of what semantido captures, so it goes into vendor extensions:

```yaml
custom_extensions:
- vendor_name: SEMANTIDO
  data: '{"privacy_level": "confidential"}'
```

Affected: `privacy_level`, `sample_values`, `time_grain`, relationship cardinality, and primary-time-dimension primacy.

**This is the lossy part, and it's worth being clear-eyed about.** A consumer that doesn't know the `SEMANTIDO` vendor will read the datasets, fields, descriptions, and relationships fine — and silently drop the privacy classification and the sample values. If your reason for exporting is to carry the classification somewhere, verify the consumer reads extensions before you rely on it.

## Time dimension curation

The OSI exporter does something the other exporters don't: it takes a position on which temporal columns matter.

- Declared primary axis → `dimension.is_time: true`, plus `PRIMARY time dimension for this dataset. Native grain: second.`
- Declared secondary axes (`<col>_is_time_dimension = True`) → `dimension.is_time: true`, no primacy claim
- Temporal columns matching the audit pattern → **demoted**, with `Operational audit timestamp — do not use as a time axis for business questions.`

That demotion is active, not passive. Saying nothing about `created_at` is not neutral — a model looking for a date column will find it. See [Modelling time](modelling-time.md) for overriding the pattern.

## Options

```python
to_osi_yaml(
    layer,
    model_name="commerce",              # required
    description="Commerce domain.",     # model-level description
    instructions="Prefer orders over legacy_orders.",   # model ai_context
    audit_pattern=re.compile(r"$^"),    # disable demotion
    path="model.osi.yaml",              # also write to disk
)
```

`instructions` and `application_glossary` are concatenated into the model-level `ai_context.instructions`, glossary appended as `Glossary — term: meaning; ...`.

`to_osi_yaml` returns the YAML text whether or not you pass `path`.

## Commit the output

The export is [deterministic](../concepts/determinism.md), so a committed `model.osi.yaml` produces no diff until a definition actually changes — at which point the diff *is* the semantic change, isolated and reviewable. That property is most of why the format is worth having in the repo at all.
