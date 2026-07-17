---
title: Versioning and CI
description: Make the semantic layer a thing that fails the build, not a thing that rots.
---

# Versioning and CI

Code-native authoring makes drift *visible*. It does not make it impossible. What closes the gap is treating the semantic layer like the rest of your code: tested, gated, committed.

Everything here works because [the export is deterministic](../concepts/determinism.md).

## Test the layer

`sync_semantic_layer()` needs no database, so this is an ordinary unit test:

```python
def test_orders_declares_a_time_dimension():
    layer = Base.sync_semantic_layer()
    assert layer.tables["orders"].time_dimension == "ordered_at"


def test_pii_is_classified():
    layer = Base.sync_semantic_layer()
    email = next(c for c in layer.tables["customers"].columns if c.name == "email")
    assert email.privacy_level == PrivacyLevel.CONFIDENTIAL
```

Some checks are free because semantido raises at sync time: a `time_dimension` naming a column that doesn't exist, or isn't temporal, fails `sync_semantic_layer()` — so any test that builds the layer catches it.

## Gate on coverage

The failure that code-native authoring *doesn't* prevent: a new column lands with no description. Nothing breaks. The export just gets slightly less useful, forever.

Make it fail:

```python
FALLBACK = re.compile(r"^Column: |^Table: ")

def test_annotation_coverage():
    layer = Base.sync_semantic_layer()
    missing = [
        f"{t.name}.{c.name}"
        for t in layer.tables.values()
        for c in t.columns
        if FALLBACK.match(c.description)
        and not c.is_foreign_key
        and c.name != t.primary_key
    ]
    assert not missing, f"Columns with no description: {missing}"
```

Fallback descriptions (`"Column: status"`) are the tell. Keys are exempt — the mapper already explains them, and describing `order_id` adds tokens and no signal.

Ratchet rather than boil the ocean: start with an allowlist of known gaps, and make the rule that the list only shrinks.

!!! tip "Catch silent typos"
    `total_ammount_description` doesn't raise — it's just ignored. The coverage test catches it, because the column it was meant for still has a fallback description. This is the main reason to have the test.

## Snapshot the export

```python
def test_markdown_export_is_stable(snapshot):
    layer = Base.sync_semantic_layer()
    assert to_markdown(layer) == snapshot
```

The diff on this file is the review surface. When someone changes the definition of `notional`, the snapshot diff shows exactly that — and a reviewer sees a semantic change rather than a line buried in a migration PR.

Pin the semantido version if you snapshot exports. Exporter output is alpha and will move; the authoring surface is what's stable.

## Commit the artifact

```yaml
- name: Regenerate semantic model
  run: python -m myapp.export_semantics

- name: Fail if the committed model is stale
  run: git diff --exit-code model.osi.yaml
```

Same pattern as committed lockfiles or generated clients. Byte-identical output is what makes it work — without determinism the file churns every run and everyone learns to ignore it.

Worth it when something outside the repo consumes the model, or when you need a reviewable history of definitions. Skip it if the export is only ever built in-process at startup.

## Review it like code

The part that isn't automatable: a migration that changes what a column *means* without changing its name will not fail any check above. The description is now wrong, and only a human reading the diff will notice.

Two things help:

- **CODEOWNERS on model files** if definitions need a named approver — the finance lead on the revenue model, say.
- **A line in the PR template**: "Does this change what any annotated column means?"

In regulated environments this is the substance of the audit story. Every definition has a commit, an author, a date, and a reviewer. See [Privacy and governance](privacy-and-governance.md#auditability).

## Build once

```python
# myapp/semantics.py
from functools import lru_cache

@lru_cache(maxsize=1)
def context() -> str:
    return to_markdown(Base.sync_semantic_layer())
```

The layer is a pure function of the model files. It cannot change without a deploy. Rebuilding per request is waste.
