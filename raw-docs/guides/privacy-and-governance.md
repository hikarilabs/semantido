---
title: Privacy and governance
description: What privacy_level and sql_filters do — and, more importantly, what they don't.
---

# Privacy and governance

semantido carries two governance-shaped annotations. Both are **advisory**. Understanding that precisely is the difference between using them well and shipping a false sense of security.

## Privacy levels

```python
from semantido.generators.semantic_layer import PrivacyLevel

class Customer(SemanticDeclarativeBase):
    email = Column(String(255))
    email_privacy_level = PrivacyLevel.CONFIDENTIAL
```

Four levels: `PUBLIC`, `INTERNAL`, `RESTRICTED`, `CONFIDENTIAL`.

The level travels into every export — as a suffix in Markdown (`**email** (VARCHAR, confidential)`), as a field in JSON, and as a vendor extension in OSI:

```yaml
custom_extensions:
- vendor_name: SEMANTIDO
  data: '{"privacy_level": "confidential"}'
```

## What this does not do

**It does not restrict access.** semantido never touches your database. A `CONFIDENTIAL` label on `email` does not stop an agent selecting it, does not stop the query running, and does not stop the value reaching a user. It is a string in a document.

Same for `sql_filters`:

```python
@semantic_table(
    description="Customer orders — one row per order.",
    sql_filters=["orders.tenant_id = :tenant_id"],
)
```

This is a **hint** that lands in the export. semantido does not inject it, does not rewrite queries, and cannot verify a generated query respects it. A model can ignore it and sometimes will.

!!! danger "Do not use these as security controls"
    Tenancy isolation belongs in a database role and row-level security policy. If your multi-tenant safety depends on an LLM honouring a prompt instruction, you do not have multi-tenant safety.

    Enforce in the database. Annotate so the model doesn't fight the enforcement.

## What they are actually for

Given that, why bother?

**They make the agent's SQL match the policy the database enforces.** An agent that knows about `tenant_id` writes queries that RLS lets through. An agent that doesn't writes queries that come back empty and then retries, confused. Same security, fewer wasted round-trips.

**They let you build the real control on top.** The privacy level is machine-readable, which is the point. You can filter the layer before it ever reaches the model:

```python
layer = Base.sync_semantic_layer()

if not user.has_pii_access:
    for table in layer.tables.values():
        table.columns = [
            c for c in table.columns
            if c.privacy_level != PrivacyLevel.CONFIDENTIAL
        ]

context = to_markdown(layer)
```

Now the confidential columns are not in the prompt at all. The model cannot select what it has never heard of. This is a real control, and it is one you build — semantido supplies the labels, you supply the enforcement.

This is the strongest use of `privacy_level`, and it is why the annotation exists.

**They document the classification where it can be reviewed.** When someone adds a column carrying personal data and labels it `PUBLIC`, that's a line in a diff a reviewer can catch. Compare to the same decision living in a data catalog nobody opens.

## Auditability

The governance property semantido does deliver is **provenance**, and it comes free from the design rather than from any annotation.

Because the layer is authored in code and the export is [deterministic](../concepts/determinism.md), every semantic definition has a commit, an author, a date, and a reviewer. When the definition of `notional` changes, `git log -p` on the model file answers who, when, and — via the PR — why.

In a regulated environment this is the difference between an explanation and a finding. "The AI decided" is not an audit response. A diff is.

Make it real:

- Commit the generated export (`model.osi.yaml`, or the Markdown). Diffs on it are semantic changes, isolated from code churn.
- Put model files behind CODEOWNERS if definitions need a named approver.
- Fail CI when a column arrives with no description. See [Versioning and CI](versioning-and-ci.md).

## In short

- `privacy_level` and `sql_filters` are **labels**, not controls.
- Enforce in the database. Always.
- The labels earn their keep by letting you **filter the layer before export** — that's a control you build, and it works.
- The real governance win is provenance, and it's structural.
