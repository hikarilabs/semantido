---
title: Open source, support, and services
description: semantido is Apache-2.0, all of it. There is no paid tier. Here's what that means and where commercial help fits.
---

# Open source, support, and services

## There is no commercial tier

semantido is [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html), all of it. No open-core split, no feature gating, no license key, no hosted version, no "contact us for the enterprise exporter".

Everything documented on this site is in `pip install semantido`.

This is worth stating plainly because the pattern in this category is the opposite: an open library that stops exactly where the useful part begins. semantido isn't structured that way, and the reason is structural rather than generous — it's a library that produces a document. There is no server to host, no seat to meter, no execution to bill. The natural boundary for a paid tier doesn't exist.

## What that means for you

**No vendor lock-in on your definitions.** Your semantic layer is Python in your repo. If semantido is abandoned tomorrow, your annotations are still class attributes, and reading them takes about fifty lines. The [OSI export](guides/osi.md) exists so the same is true of the output.

**No roadmap leverage.** Nobody can hold a feature hostage to a contract. The flip side: nobody owes you a feature either.

**Support is best-effort.** [GitHub issues](https://github.com/hikarilabs/semantido/issues) are read and answered, with no SLA. That's the deal, and it should factor into your risk assessment for anything load-bearing.

## Status, honestly

**Alpha** (`Development Status :: 3 - Alpha`). Concretely:

- The **authoring surface** — `@semantic_table`, the `<column>_*` conventions — is used in production and won't break without a deprecation path.
- **Exporter output** is less settled. The OSI exporter targets a spec that is itself pre-1.0 (`0.2.0.dev0`) and will move as the spec does.
- **Pin the version** if you snapshot-test exports. See [Versioning and CI](guides/versioning-and-ci.md#snapshot-the-export).

## Contributing

Contributions are welcomed and encouraged — see [CONTRIBUTING.md](https://github.com/hikarilabs/semantido/blob/main/CONTRIBUTING.md).

```console
pip install 'semantido[dev]'
```

The dev extra pins the CI toolchain exactly (pytest, mypy, pylint, ruff), so a green run locally means a green run in CI.

The highest-value contributions are usually **not** features. They're annotation patterns from schemas that break the current model — a fan-out shape the docs don't cover, a time-dimension case the audit demoter gets wrong, a SQLAlchemy construct the bridge mishandles. The library is small on purpose; keeping it small is a feature.

## Where commercial help fits

semantido is built and maintained by [Hikari Labs](https://hikarilabs.co), a consultancy working on semantic layers and agentic analytics in regulated industries — banking and capital markets in particular.

The library is free and stays free. What Hikari Labs sells is the part the library doesn't do:

- **Semantic Layer Readiness Audit** — whether your schema and pipeline are in a state where any of this will work
- **Accuracy Remediation Sprint** — when text-to-SQL is in production and wrong
- **Agent-Ready Tool Layer** — building the system around the context: eval, validation, retrieval, governance
- **Vendor & Architecture Advisory** — Cube, AtScale, dbt, Wren, Snowflake, Databricks, and where code-native authoring does and doesn't fit

The relationship is the ordinary one: the library exists because the consulting work needed it, and it's open because a semantic layer nobody can inspect is a semantic layer nobody should trust.

You never need to talk to anyone to use semantido. If the accuracy problem is expensive and you'd rather not solve it twice, that's what the other thing is for.
