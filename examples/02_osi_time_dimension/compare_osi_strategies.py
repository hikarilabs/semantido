"""Exports the core banking models to OSI under three time-dimension
strategies and writes a comparison report.

Strategies:
    CURATED — semantido's default export policy: the declared primary axis
              gets ``dimension.is_time`` plus a PRIMARY marker and grain;
              secondary business dates keep ``is_time``; audit timestamps
              (created_at, updated_at, ...) are demoted with an explicit
              "do not use as a time axis" instruction.
    NAIVE — what blind type inference would produce: every DATE/TIMESTAMP
              column flagged ``is_time``, no primary, no demotion. Simulated
              by stripping the curated metadata and disabling the audit
              pattern.
    OFF — no time metadata at all: what the export looks like if the
              format's time dimension is not used.

Run from this directory:  python compare_osi_strategies.py
Outputs land in ./exports/
"""

import copy
import re
from pathlib import Path

import yaml

from semantido import SemanticDeclarativeBase
from semantido.exporters import to_osi_dict, to_osi_yaml

# Importing registers the mapped classes with the declarative base
from models.core_banking import AccountInfo, TransactionInfo  # noqa: F401

OUT = Path(__file__).parent / "exports"
NEVER_MATCH = re.compile(r"$^")  # disables audit demotion

MODEL_KWARGS = {
    "model_name": "core_banking_analytics",
    "description": "Core banking accounts and transactions, exported from semantido.",
    "instructions": (
        "Wholesale/retail core banking model. Respect each dataset's "
        "application context and default filters."
    ),
}


def build_layer():
    """Syncs the semantic layer and attaches the domain glossary."""
    layer = SemanticDeclarativeBase.sync_semantic_layer()
    layer.application_glossary.update(
        {
            "booking date": "date a movement is booked to the account (the axis)",
            "value date": "date a movement becomes interest-effective",
            "net flow": "signed sum of amounts over a period (not turnover)",
        }
    )
    return layer


def strip_time_curation(layer):
    """Returns a copy of the layer with all curated time metadata removed,
    reproducing what a model with no time semantics would sync to."""
    stripped = copy.deepcopy(layer)
    for table in stripped.tables.values():
        table.time_dimension = None
        for column in table.columns:
            column.is_time_dimension = False
            column.time_grain = None
    return stripped


def strip_dimension_blocks(doc):
    """Returns a copy of an OSI doc with every field's dimension block
    removed — the OFF strategy."""
    stripped = copy.deepcopy(doc)
    for model in stripped["semantic_model"]:
        for dataset in model["datasets"]:
            for field in dataset["fields"]:
                field.pop("dimension", None)
    return stripped


def time_dimensions_in(doc):
    """Map dataset name -> list of columns flagged is_time."""
    flagged = {}
    for model in doc["semantic_model"]:
        for dataset in model["datasets"]:
            flagged[dataset["name"]] = [
                f["name"]
                for f in dataset["fields"]
                if f.get("dimension", {}).get("is_time")
            ]
    return flagged


def main() -> None:
    OUT.mkdir(exist_ok=True)
    layer = build_layer()

    # CURATED — the library default, straight from the real exporter
    curated = to_osi_dict(layer, **MODEL_KWARGS)
    to_osi_yaml(layer, path=str(OUT / "osi_export_curated.yaml"), **MODEL_KWARGS)

    # NAIVE — no curation, no audit demotion: pure type inference
    naive_layer = strip_time_curation(layer)
    naive = to_osi_dict(naive_layer, audit_pattern=NEVER_MATCH, **MODEL_KWARGS)
    (OUT / "osi_export_naive.yaml").write_text(
        yaml.safe_dump(naive, sort_keys=False, allow_unicode=True, width=88)
    )

    # OFF — the naive doc with every dimension block removed
    off = strip_dimension_blocks(naive)
    (OUT / "osi_export_off.yaml").write_text(
        yaml.safe_dump(off, sort_keys=False, allow_unicode=True, width=88)
    )

    # Round-trip check: every written file reloads to its source document
    for name, doc in (("curated", curated), ("naive", naive), ("off", off)):
        reloaded = yaml.safe_load((OUT / f"osi_export_{name}.yaml").read_text())
        assert reloaded == doc, f"round-trip failed: {name}"

    # Comparison report — what an OSI consumer (agent, BI tool) sees
    lines = [
        "TIME-DIMENSION COMPARISON — what an OSI consumer sees",
        "=" * 60,
    ]
    for name, doc in (("OFF", off), ("NAIVE", naive), ("CURATED", curated)):
        lines.append(f"\nStrategy: {name}")
        for dataset, flagged in time_dimensions_in(doc).items():
            lines.append(f"  {dataset}: is_time -> {flagged or '(none)'}")

    lines += [
        "",
        "Agent task: 'monthly transaction volume' -> needs ONE GROUP BY",
        "column on transaction_info.",
        "  OFF     : 0 candidates flagged; the agent guesses from names and",
        "            types — booking vs value vs settlement is a coin toss.",
        "  NAIVE   : 5 candidates flagged, including created_at/updated_at.",
        "            Signal-to-noise 1:5; audit timestamps look identical",
        "            to business dates.",
        "  CURATED : booking_date is marked PRIMARY with grain DAY;",
        "            value_date/settlement_date remain secondary axes;",
        "            audit columns carry an explicit do-not-use instruction",
        "            and no dimension block.",
    ]
    report = "\n".join(lines)
    (OUT / "comparison_report.txt").write_text(report + "\n")
    print(report)
    print(f"\nWrote: {sorted(p.name for p in OUT.glob('*'))}")


if __name__ == "__main__":
    main()
