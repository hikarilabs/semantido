# Semantido

[![PyPI - Version](https://img.shields.io/pypi/v/semantido.svg)](https://pypi.org/project/semantido)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/semantido.svg)](https://pypi.org/project/semantido)
[![CI](https://github.com/hikarilabs/semantido/actions/workflows/ci.yml/badge.svg)](https://github.com/hikarilabs/semantido/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://spdx.org/licenses/Apache-2.0.html)

**Code-native semantic layer authoring for SQLAlchemy.** Annotate your
models where they live, and generate LLM-ready schema context for
text-to-SQL agents, RAG pipelines, and BI tools — as JSON, Markdown, or
vendor-neutral [OSI](https://open-semantic-interchange.org) YAML.

-----

Table of Contents
-----

- [Why](#why)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [What gets captured](#what-gets-captured)
- [Exporters](#exporters)
- [Example: trade reporting](#example-trade-reporting)
- [Contributing](#contributing)
- [License](#license)

Why
-----
A database schema tells an LLM what your tables are called — not what
they *mean*. Text-to-SQL systems fail on exactly the things a schema
doesn't say: bridge tables that fan out and double-count, amount columns
whose sign convention lives in a code column, three different columns
that all look like "the amount".

`semantido` closes that gap without introducing a separate modeling
language or YAML repository to keep in sync. Semantic metadata is
declared **next to the SQLAlchemy models it describes** — reviewed in
the same pull request, versioned in the same git history, refactored by
the same tools. One `sync_semantic_layer()` call extracts models,
columns, and relationships (with join conditions and cardinality) into a
semantic layer you can export wherever your stack needs it.

Output is **deterministic**: the same models always produce byte-identical
exports, so generated artifacts can be committed, diffed, and cached.

Installation
-----

```console
pip install semantido
```

The core install is dependency-light (SQLAlchemy only) and covers the
JSON and Markdown exporters plus `to_osi_dict()`. For OSI YAML export
(`to_osi_yaml()`), add the `osi` extra, which pulls in PyYAML:

```console
pip install 'semantido[osi]'
```

Quickstart
-----

Annotate your models with the `@semantic_table` decorator and
column-level attributes:

```python
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from semantido import semantic_table, SemanticDeclarativeBase
from semantido.generators.semantic_layer import PrivacyLevel, TimeGrain


@semantic_table(
    description="Customer orders — one row per order.",
    synonyms=["orders", "purchases"],
    business_context="total_amount is gross, including tax and shipping.",
)
class Order(SemanticDeclarativeBase):
    __tablename__ = "orders"
    __semantic_time_dimension__ = "ordered_at"

    order_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"))
    ordered_at = Column(DateTime, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(String(16), nullable=False)

    ordered_at_time_grain = TimeGrain.SECOND
    total_amount_description = "Gross order total, including tax and shipping."
    total_amount_synonyms = ["order value", "revenue"]
    status_sample_values = ["PENDING", "SHIPPED", "CANCELLED"]

    customer = relationship("Customer", back_populates="orders")


@semantic_table(description="Customers who have placed at least one order.")
class Customer(SemanticDeclarativeBase):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)

    email_privacy_level = PrivacyLevel.CONFIDENTIAL

    orders = relationship("Order", back_populates="customer")
```

Then build the layer and export it:

```python
from semantido.exporters import to_json, to_markdown, to_osi_yaml

layer = SemanticDeclarativeBase.sync_semantic_layer()

to_json(layer)                                    # structured JSON
to_markdown(layer)                                # LLM prompt context
to_osi_yaml(layer, model_name="commerce")         # OSI interchange (requires [osi])
```

Relationships, join conditions, cardinality, foreign keys, and primary
keys are extracted automatically from the SQLAlchemy mappers — you only
author what the schema cannot express.

What gets captured
-----

| Concern | Authored as |
|---|---|
| Table meaning, business & application context | `@semantic_table(...)` arguments |
| Column meaning, synonyms, sample values | `<column>_description`, `<column>_synonyms`, `<column>_sample_values` |
| Business rules an agent must respect | `<column>_application_rules` |
| Data sensitivity | `<column>_privacy_level` (`PUBLIC` … `CONFIDENTIAL`) |
| Primary business time axis | `__semantic_time_dimension__` on the table |
| Secondary time axes & native grain | `<column>_is_time_dimension`, `<column>_time_grain` (`TimeGrain` or `"day"`) |
| Default filters / row-level security fragments | `sql_filters` on the table |
| Relationship semantics | `<relationship>_relationship_description` |
| Join conditions, cardinality, FKs, PKs | extracted automatically from SQLAlchemy |

Exporters
-----

- **JSON** (`to_json`, `to_json_file`) — structured, machine-readable, empty
  values pruned by default.
- **Markdown** (`to_markdown`, `to_markdown_file`) — formatted for direct
  inclusion in LLM prompts for text-to-SQL and agentic analytics.
- **OSI YAML** (`to_osi_dict`, `to_osi_yaml`) — the
  [Open Semantic Interchange](https://open-semantic-interchange.org)
  format for exchanging semantic models across the wider data stack.
  Time dimensions are curated on export: declared axes are flagged
  `dimension.is_time`, while audit timestamps (`created_at`, `updated_at`,
  ...) are demoted with an explicit "do not use as a time axis"
  instruction, keeping the signal-to-noise high for agentic consumers.

Example: trade reporting
-----

[`examples/01_getting_started`](examples/01_getting_started) is a full
walkthrough on a realistic wholesale-banking schema: a synthetic
EMIR/MiFIR regulatory reporting subset that deliberately encodes three
classic text-to-SQL failure modes — bridge fan-out, sign conventions,
and amount ambiguity — and shows how semantic annotations counter each
one. Reference exports in all three formats are committed alongside it.

Full documentation: [semantido.ai](https://semantido.ai)

Contributing
-----
Contributions to this library are welcomed and highly encouraged.
See [CONTRIBUTING.md](https://github.com/hikarilabs/semantido/blob/main/CONTRIBUTING.md) for more information on how to get started.

License
-----
`semantido` is distributed under the terms of the [Apache License 2.0](https://spdx.org/licenses/Apache-2.0.html) license.
