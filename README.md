# Semantido

[![PyPI - Version](https://img.shields.io/pypi/v/semantido.svg)](https://pypi.org/project/semantido)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/semantido.svg)](https://pypi.org/project/semantido)
[![CI](https://github.com/hikarilabs/semantido/actions/workflows/ci.yml/badge.svg)](https://github.com/hikarilabs/semantido/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://spdx.org/licenses/Apache-2.0.html)

**Code-native semantic layer authoring for SQLAlchemy.** Annotate your
models where they live and generate LLM-ready schema context for
text-to-SQL agents, RAG pipelines, and BI tools, as JSON, Markdown, or
vendor-neutral [Apache Ossie](https://open-semantic-interchange.org) YAML.

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

The core installation is dependency-light (SQLAlchemy only) and covers the
JSON and Markdown exporters plus `to_ossie_dict()`. For Apache Ossie YAML export
(`to_ossie_yaml()`), add the `ossie` extra, which pulls in PyYAML:

```console
pip install 'semantido[ossie]'
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
    time_dimension="ordered_at",
)
class Order(SemanticDeclarativeBase):
    __tablename__ = "orders"

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
from semantido.exporters import to_json, to_markdown, to_ossie_yaml

layer = SemanticDeclarativeBase.sync_semantic_layer()

to_json(layer)                                      # structured JSON
to_markdown(layer)                                  # LLM prompt context
to_ossie_yaml(layer, model_name="commerce")         # Apache OOssie  interchange (requires [ossie])
```

Relationships, join conditions, cardinality, foreign keys, and primary
keys are extracted automatically from the SQLAlchemy mappers — you only
author what the schema cannot express.

What gets captured
-----

| Concern                                        | Authored as                                                                        |
|------------------------------------------------|------------------------------------------------------------------------------------|
| Table meaning, business & application context  | `@semantic_table(...)` arguments                                                   |
| Column meaning, synonyms, sample values        | `<column>_description`, `<column>_synonyms`, `<column>_sample_values`              |
| Business rules an agent must respect           | `<column>_application_rules`                                                       |
| Data sensitivity                               | `<column>_privacy_level` (`PUBLIC` … `CONFIDENTIAL`)                               |
| Primary business time axis                     | `time_dimension=` in the decorator (or `__semantic_time_dimension__` on the class) |
| Secondary time axes & native grain             | `<column>_is_time_dimension`, `<column>_time_grain` (`TimeGrain` or `"day"`)       |
| Default filters / row-level security fragments | `sql_filters` on the table                                                         |
| Relationship semantics                         | `<relationship>_relationship_description`                                          |
| Join conditions, cardinality, FKs, PKs         | extracted automatically from SQLAlchemy                                            |

Exporters
-----

- **JSON** (`to_json`, `to_json_file`) — structured, machine-readable, empty
  values pruned by default.
- **Markdown** (`to_markdown`, `to_markdown_file`) — formatted for direct
  inclusion in LLM prompts for text-to-SQL and agentic analytics.
- **Apche Ossie YAML** (`to_ossie_dict`, `to_ossie_yaml`) — the
  [Open Semantic Interchange](https://open-semantic-interchange.org)
  format for exchanging semantic models across the wider data stack.
  Time dimensions are curated on export: declared axes are flagged
  `dimension.is_time`, while audit timestamps (`created_at`, `updated_at`,
  ...) are demoted with an explicit "do not use as a time axis"
  instruction, keeping the signal-to-noise high for agentic consumers.

Examples
-----

[`examples/`](examples) has eight runnable walkthroughs, each self-contained.
Start here:

| | Example | Demonstrates |
|---|---|---|
| 01 | [`01_getting_started`](examples/01_getting_started) | Full walkthrough: concepts, grain, exports, lint gate |
| 02 | [`02_osi_time_dimension`](examples/02_osi_time_dimension) | Time dimensions and the eight-false-axes problem |
| 03 | [`03_md_vs_osi_context`](examples/03_md_vs_osi_context) | Markdown vs Ossie YAML as text-to-SQL context |
| 04 | [`04_federated_agents`](examples/04_federated_agents) | Cross-institution concept alignment |
| 05 | [`05_toolchain_drift`](examples/05_toolchain_drift) | Drift between an authored and a generated registry |
| 06 | [`06_groundings_and_lint`](examples/06_groundings_and_lint) | Groundings lifecycle and the checks that guard it |
| 07 | [`07_security_master`](examples/07_security_master) | Grain, fan-out, and the limits of static checking |
| 08 | [`08_release_timeline`](examples/08_release_timeline) | What each release could express and enforce |

`01_getting_started` is a synthetic EMIR/MiFIR regulatory reporting subset
that deliberately encodes four classic text-to-SQL failure modes. Three are
now rejected statically by the linter; the fourth is not, and the example
says which and why. Reference exports in all four formats are committed
alongside it.

Full documentation: [semantido.ai](https://semantido.ai)

Contributing
-----
Contributions to this library are welcomed and highly encouraged.
See [CONTRIBUTING.md](https://github.com/hikarilabs/semantido/blob/main/CONTRIBUTING.md) for more information on how to get started.

License
-----
`semantido` is distributed under the terms of the [Apache License 2.0](https://spdx.org/licenses/Apache-2.0.html) license.
