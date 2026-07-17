---
title: Installation
description: Install semantido and its optional extras.
---

# Installation

```console
pip install semantido
```

That's it. There is no server, no daemon, no configuration file, and nothing to connect to.

## Requirements

| | |
|---|---|
| Python | **≥ 3.11** |
| SQLAlchemy | **≥ 2.0** |
| Also installs | `typing-extensions ≥ 4.5` |

The core install is deliberately dependency-light — SQLAlchemy and nothing else — because semantido is meant to sit in the dependency tree of applications that already have opinions about their dependencies.

SQLAlchemy 2.0 is a hard floor. semantido reads the 2.0 mapper API and does not support the 1.x declarative style.

## Extras

### `osi` — OSI YAML export

The core install covers the JSON and Markdown exporters, plus `to_osi_dict()`. Serialising to OSI **YAML** needs PyYAML:

```console
pip install 'semantido[osi]'
```

If you call `to_osi_yaml()` without it, you get a clear `ImportError` telling you to install the extra — not a stack trace.

Note the split: `to_osi_dict()` works without the extra, because producing the OSI document structure needs no YAML. Only serialisation does. If you are handing the dict to something else — a JSON API, your own writer — you don't need PyYAML at all.

### `dev` — contributing

```console
pip install 'semantido[dev]'
```

Pins the toolchain used in CI: pytest, pytest-cov, mypy, pylint, ruff, PyYAML, python-dotenv. Pinned exactly, so a green run locally means a green run in CI. See [CONTRIBUTING.md](https://github.com/hikarilabs/semantido/blob/main/CONTRIBUTING.md).

## Verifying

```python
import semantido
print(semantido.__version__)
```

A fuller smoke test — no database required:

```python
from sqlalchemy import Column, Integer
from semantido import semantic_table, SemanticDeclarativeBase
from semantido.exporters import to_markdown

@semantic_table(description="Smoke test.")
class Thing(SemanticDeclarativeBase):
    __tablename__ = "things"
    id = Column(Integer, primary_key=True)

print(to_markdown(SemanticDeclarativeBase.sync_semantic_layer()))
```

If that prints a Markdown document, you are done.

## Stability

semantido is classified **alpha**. In practice:

- The **authoring surface** — `@semantic_table` and the `<column>_*` conventions — is what production code depends on and is not expected to break without a deprecation path.
- The **exporter output** is less settled. The OSI exporter tracks a spec that is itself pre-1.0 (`0.2.0.dev0`); its output will move as the spec does.

If you snapshot-test exports (and you should — see [Versioning and CI](../guides/versioning-and-ci.md)), pin the semantido version.

## Next

- [Quickstart](quickstart.md) — annotate and export in five minutes
