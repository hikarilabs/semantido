# Getting Started with semantido

This example walks you through building a fully annotated **semantic layer**
from a set of SQLAlchemy models and exporting it to three formats: JSON,
Markdown (for LLM prompt context), and OSI YAML (for interchange).

---
## Prerequisites

Install `semantido` with the OSI extra so all exporters are available:

```bash
pip install "semantido[osi]"
```
or with uv

```bash
uv add "semantido[osi]"
```
## Project layout

```
01_getting_started/
├── models/
│   ├── __init__.py          # empty — models register themselves on import
│   └── trade_reporting.py   # SQLAlchemy models decorated with @semantic_table
├── exports/                 # output directory (generated)
│   ├── trade_reporting.semantic.json
│   ├── trade_reporting.semantic.md
│   └── trade_reporting.osi.yaml
└── semantic.py              # entry point — builds and exports the semantic layer
```           

## Step 1 — Annotate your models

semantido extends your existing SQLAlchemy DeclarativeBase with SemanticDeclarativeBase. All models that inherit from it are automatically registered in the semantic layer.

Use the @semantic_table decorator to attach human-readable metadata, and class-level attributes to annotate individual columns:
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from semantido import semantic_table, SemanticDeclarativeBase
from semantido.generators.semantic_layer import PrivacyLevel, TimeGrain

```python
@semantic_table(
    description="EMIR trade reports — one row per UTI, latest reported state.",
    synonyms=["trades", "derivative trades", "EMIR reports"],
    sql_filters=["action_type != 'E'  -- exclude error-cancelled reports"],
    business_context=(
        "notional_amount is ALWAYS POSITIVE regardless of direction. "
        "Economic side lives in `direction` (BYER/SLLR), never in the sign."
    ),
)
class TradeReport(SemanticDeclarativeBase):
    __tablename__ = "trade_reports"
    __semantic_time_dimension__ = "execution_timestamp"  # primary time axis

    trade_id = Column(Integer, primary_key=True)
    uti = Column(String(52), nullable=False, unique=True)
    notional_amount = Column(Numeric(20, 2), nullable=False)
    direction = Column(String(4), nullable=False)
    execution_timestamp = Column(DateTime, nullable=False)

    # Column-level annotations — attribute name: <column>_<property>
    uti_description = "Unique Trade Identifier (ISO 23897)."
    uti_synonyms = ["trade identifier", "UTI"]
    uti_privacy_level = PrivacyLevel.INTERNAL

    notional_amount_description = (
        "Trade notional in notional_currency. Always positive; "
        "direction of risk is given by `direction`, never by sign."
    )
    notional_amount_synonyms = ["notional", "trade size"]
    notional_amount_application_rules = [
        "Sign is always positive; use direction for buy/sell split.",
    ]

    execution_timestamp_description = "UTC timestamp when the trade was executed."
    execution_timestamp_time_grain = TimeGrain.SECOND
```

The full schema used in this example — six tables covering counterparties, instruments, trade reports, party roles, valuations and MiFIR transactions — lives in [`models/trade_reporting.py`](https://github.com/hikarilabs/semantido/blob/main/examples/01_getting_started/models/trade_reporting.py).

## Step 2 — Import your models
Models must be imported before the semantic layer is built so that SQLAlchemy (and semantido) can register them. Import only what you need, or import the whole module as a side effect:

```python
# explicit — preferred when you want IDE support and type safety
from models.trade_reporting import (
    Counterparty,
    Instrument,
    TradeReport,
    TradeParty,
    TradeValuation,
    MifirTransaction,
)

# or implicit — useful for large schemas where listing every class is noisy
import models  # noqa: F401
```

Tip: Run semantic.py from the 01_getting_started/ directory so that the models package is on the Python path.

## Step 3 — Build the semantic layer
Call SemanticDeclarativeBase.sync_semantic_layer() after all models are imported. This inspects every registered table, resolves relationships, and returns a SemanticLayer object you can enrich and export.

```python
from pathlib import Path
from semantido import SemanticDeclarativeBase
from semantido.exporters import to_json_file, to_markdown_file, to_osi_yaml

from models.trade_reporting import (
    Counterparty, Instrument, TradeReport,
    TradeParty, TradeValuation, MifirTransaction,
)  # noqa: F401 — registers the mapped classes

OUT = Path(__file__).parent

layer = SemanticDeclarativeBase.sync_semantic_layer()
```

You can also attach a **domain glossary** that exporters will embed in the output — especially useful for LLM prompt context:

```python
layer.application_glossary.update(
    {
        "UTI": "Unique Trade Identifier per ISO 23897",
        "notional": "unsigned contract size — not exposure",
        "exposure": "signed mark-to-market valuation (trade_valuations)",
        "NFC+": "non-financial counterparty above the clearing threshold",
    }
)
```

## Step 4 — Export

### JSON

A machine-readable snapshot of the full semantic layer:

```python
to_json_file(layer, str(OUT / "exports" / "trade_reporting.semantic.json"))
```

### Markdown
A structured document optimised for pasting into LLM system prompts:

```python
to_markdown_file(layer, str(OUT / "exports" / "trade_reporting.semantic.md"))
# table=True renders a compact Markdown table format instead
to_markdown_file(layer, "...", table=True)
```

### OSI YAML
An interchange file following the Open Semantic Interchange format:

```python
to_osi_yaml(
    layer,
    model_name="emir_mifir_trade_reporting",
    description="Synthetic EMIR/MiFIR regulatory reporting schema.",
    instructions=(
        "Amounts are unsigned unless stated otherwise; direction always "
        "comes from a code column, never from an amount sign."
    ),
    path=str(OUT / "exports" / "trade_reporting.osi.yaml"),
)
```

Note: OSI export requires the PyYAML dependency. Install it with pip install "semantido[osi]"

### Step 5 — Run

From the 01_getting_started/ directory:

```python
python semantic.py
```

Expected output:

```text
tables=6 relationships=7 columns=42
```

The three export files will be written to the `exports/` directory.

## What's next?
- Browse the generated exports in the [`examples/01_getting_started/exports/`](https://github.com/hikarilabs/semantido/tree/main/examples/01_getting_started/exports) directory.
- Read the [Code Reference](../reference.md) for the full decorator and exporter API.
- Check [Why Semantido](../explanation.md) for the design philosophy behind the semantic layer approach.