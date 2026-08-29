"""Builds the semantic layer for the trade reporting schema, exports it, and
gates the result on the linter.

Four stages, matching the shape of a real pipeline:

  1. sync the layer from the annotated models and the concept registry
  2. lint it — errors fail the build, warnings do not
  3. export the agent context (JSON, Markdown, Ossie YAML)
  4. export the groundings document, which binds meaning to deployment

Stage 2 is the one that changed in v0.5. Before it existed, everything below
was documentation: true when written, unverifiable afterwards.

    pip install 'semantido[lint,ossie]>=0.5.3'
    python semantic.py
"""

import sys
from pathlib import Path

from semantido import SemanticDeclarativeBase
from semantido.exporters import (
    to_groundings_file,
    to_json_file,
    to_markdown_file,
    to_ossie_yaml,
)
from semantido.lint import lint_layer

from models.concepts import registry
from models.trade_reporting import (  # noqa: F401  (import registers the models)
    Counterparty,
    Instrument,
    MifirTransaction,
    TradeParty,
    TradeReport,
    TradeValuation,
)

OUT = Path(__file__).parent / "exports"


def gate(layer) -> None:
    """Fail the build on lint errors. Report warnings without failing."""
    findings = lint_layer(layer)
    errors = [f for f in findings if f.severity.value == "error"]
    warnings = [f for f in findings if f.severity.value == "warning"]

    for f in findings:
        print(f"  {f.code} {f.severity.value:<7} {f.location}: {f.message}")

    if errors:
        print(f"\nlint FAILED - {len(errors)} error(s)")
        sys.exit(1)
    print(f"lint clean - {len(warnings)} warning(s), 0 errors")


def main() -> None:
    registry.validate()
    layer = SemanticDeclarativeBase.sync_semantic_layer(concept_registry=registry)

    layer.application_glossary.update(
        {
            "UTI": "Unique Trade Identifier per ISO 23897",
            "notional": "unsigned contract size - not exposure",
            "exposure": "signed mark-to-market valuation (trade_valuations)",
            "NFC+": "non-financial counterparty above the clearing threshold",
        }
    )

    gate(layer)

    to_json_file(layer, str(OUT / "trade_reporting.semantic.json"))
    to_markdown_file(layer, str(OUT / "trade_reporting.semantic.md"))
    to_ossie_yaml(
        layer,
        model_name="emir_mifir_trade_reporting",
        description=(
            "Synthetic EMIR/MiFIR regulatory reporting schema used in the "
            "Hikari Labs semantic layer benchmark."
        ),
        instructions=(
            "Amounts are unsigned unless stated otherwise; direction always "
            "comes from a code column, never from an amount sign."
        ),
        path=str(OUT / "trade_reporting.ossie.yaml"),
    )
    to_groundings_file(layer, str(OUT / "groundings.yaml"))

    concepts = registry.to_dict()["concepts"]
    print(
        f"\ntables={len(layer.tables)} "
        f"relationships={len(layer.relationships)} "
        f"columns={sum(len(t.columns) for t in layer.tables.values())} "
        f"concepts={len(concepts)} "
        f"grains={len({c['grain'] for c in concepts.values() if c.get('grain')})}"
    )


if __name__ == "__main__":
    main()
