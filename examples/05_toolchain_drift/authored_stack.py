"""Path A: the hand-authored semantido stack over the shared warehouse.

An architect reads glossary.yaml and authors the registry with judgment —
this file is deliberately ordinary semantido authoring, identical in
style to production use. The warehouse models carry realized_by
annotations referencing the authored concept ids.
"""

from pathlib import Path

import yaml
from sqlalchemy import Column, Date, Float, String
from sqlalchemy.orm import DeclarativeBase

from semantido import SemanticBase, semantic_table
from semantido.concepts import (
    ConceptRegistry,
    ExternalMapping,
    MappingRelation,
    OntologySource,
)

GLOSSARY = yaml.safe_load(
    (Path(__file__).parent / "glossary.yaml").read_text(encoding="utf-8")
)


def _mapping(anchor: dict) -> ExternalMapping:
    return ExternalMapping(
        target=anchor["target"],
        relation=MappingRelation(
            anchor["relation"].replace("narrow_match", "narrower")
            .replace("broad_match", "broader")
            .replace("related_match", "related")
        ),
        source=anchor["source"],
        justification=anchor.get("because"),
    )


def build_authored_registry() -> ConceptRegistry:
    """The architect's derivation: faithful ids, full definitions,
    judged relations, per-source pins from the glossary."""
    registry = ConceptRegistry("hikari.golden.authored")
    for name, src in GLOSSARY["sources"].items():
        registry.add_source(
            OntologySource(
                name=name,
                namespace=src["namespace"],
                version=src["version"],
                profile=src.get("profile"),
            )
        )

    handles = {}
    # First pass: concepts without relations; second pass adds edges via
    # handles (single authoring path, declare-from-later rule).
    for term_id, term in GLOSSARY["terms"].items():
        kwargs = {}
        if term.get("broader") and term["broader"] in handles:
            kwargs["broader"] = handles[term["broader"]]
        if term.get("distinct_from") and term["distinct_from"] in handles:
            kwargs["distinct_from"] = handles[term["distinct_from"]]
        handles[term_id] = registry.concept(
            term_id,
            definition=term["definition"],
            label=term.get("label"),
            external=[_mapping(a) for a in term.get("anchors", [])],
            **kwargs,
        )
    registry.validate()
    return registry


class Warehouse(SemanticBase, DeclarativeBase):
    """One physical warehouse; BOTH stacks describe these same tables."""


@semantic_table(
    description="EMIR trade state report",
    time_dimension="reporting_date",
    concept="trade_report",
)
class EmirTradeState(Warehouse):
    __tablename__ = "emir_trade_state"
    uti = Column(String, primary_key=True)
    cpty_lei = Column(String)
    cpty_lei_description = "LEI of the counterparty to the contract"
    cpty_lei_concept = "counterparty_emir"
    notional = Column(Float)
    notional_description = "Contract notional amount in EUR"
    notional_concept = "notional"
    asset_class = Column(String)
    asset_class_concept = "asset_class"
    reporting_date = Column(Date)


@semantic_table(
    description="MiFIR transaction report",
    time_dimension="trade_date",
)
class MifirTransaction(Warehouse):
    __tablename__ = "mifir_transaction"
    tx_ref = Column(String, primary_key=True)
    buyer_lei = Column(String)
    buyer_lei_description = "LEI of the buyer"
    buyer_lei_concept = "counterparty_mifir"
    amount = Column(Float)
    amount_concept = "notional"
    trade_date = Column(Date)


SEED = {
    "emir_trade_state": [
        ("UTI-001", "LEI-AAA", 5_000_000.0, "IR"),
        ("UTI-002", "LEI-BBB", 7_500_000.0, "FX"),
    ],
    "mifir_transaction": [
        ("TX-901", "LEI-AAA", 2_000_000.0),
    ],
}
