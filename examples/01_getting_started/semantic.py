"""Builds the semantic layer for the trade reporting schema and exports it
to JSON, Markdown (LLM prompt context) and OSI YAML (interchange)."""

from pathlib import Path

from semantido import SemanticDeclarativeBase
from semantido.exporters import to_json_file, to_markdown_file, to_osi_yaml

from models.trade_reporting import (
    Counterparty,
    Instrument,
    TradeReport,
    TradeParty,
    TradeValuation,
    MifirTransaction,
)  # noqa: F401— registers the mapped classes

OUT = Path(__file__).parent


def main() -> None:
    layer = SemanticDeclarativeBase.sync_semantic_layer()

    # Domain glossary consumed by the OSI model-level ai_context
    layer.application_glossary.update(
        {
            "UTI": "Unique Trade Identifier per ISO 23897",
            "notional": "unsigned contract size — not exposure",
            "exposure": "signed mark-to-market valuation (trade_valuations)",
            "NFC+": "non-financial counterparty above the clearing threshold",
        }
    )

    to_json_file(layer, str(OUT / "exports" / "trade_reporting.semantic.json"))
    to_markdown_file(layer, str(OUT / "exports" / "trade_reporting.semantic.md"))
    to_osi_yaml(
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
        path=str(OUT / "exports" / "trade_reporting.osi.yaml"),
    )

    print(
        f"tables={len(layer.tables)} "
        f"relationships={len(layer.relationships)} "
        f"columns={sum(len(t.columns) for t in layer.tables.values())}"
    )


if __name__ == "__main__":
    main()
