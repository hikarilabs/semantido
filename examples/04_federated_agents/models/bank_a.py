"""Bank A: a derivatives desk reporting under EMIR.

Local vocabulary: "cpty" for counterparty, "notional", "uti".
Registry namespace: bank_a.glossary.
"""

from sqlalchemy import Column, Date, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase

from semantido import SemanticBase, semantic_table
from semantido.concepts import (
    ConceptRegistry,
    OntologySource,
    exact_match,
    narrow_match,
)


def build_registry() -> ConceptRegistry:
    registry = ConceptRegistry("bank_a.glossary")

    # Shared anchor, identical pin on both sides -> exact bridge possible
    registry.add_source(
        OntologySource(
            name="gleif", namespace="urn:gleif:lei", version="2026-06"
        )
    )
    # Shared anchor, DIFFERENT pin than Bank B (2025Q3 vs 2026Q1)
    registry.add_source(
        OntologySource(
            name="fibo",
            namespace="https://spec.edmcouncil.org/fibo/ontology/",
            version="2025Q3",
            profile="fnd-parties",
        )
    )
    # Regulator field list only Bank A uses
    registry.add_source(
        OntologySource(
            name="esma_emir",
            namespace="urn:eu:emir:rts",
            version="2024refit",
        )
    )
    # Second shared anchor for amounts, SAME pin both sides: one valid
    # rendezvous is enough even while the fibo pins disagree.
    registry.add_source(
        OntologySource(
            name="iso20022", namespace="urn:iso:20022", version="2025"
        )
    )

    legal_entity = registry.concept(
        "legal_entity",
        definition="An LEI-identified legal person or structure.",
        external=exact_match("gleif", "lei"),
    )
    registry.concept(
        "counterparty.emir",
        label="counterparty",
        definition="Counterparty within the meaning of EMIR Art. 2(8)-(9).",
        broader=legal_entity,
        external=[
            narrow_match(
                "fibo",
                "FND/Parties/Parties/Counterparty",
                because="EMIR sense is jurisdiction- and instrument-scoped",
            ),
            exact_match("esma_emir", "field:1.9"),
        ],
    )
    registry.concept(
        "notional",
        definition="Notional amount of the derivative contract, EUR.",
        external=[
            exact_match("fibo", "DER/DerivativesContracts/NotionalAmount"),
            exact_match("iso20022", "auth:NotionalAmount"),
        ],
    )
    registry.concept(
        "asset_class",
        definition="EMIR asset class of the derivative (IR, FX, CR, EQ, CO).",
        external=exact_match(
            "fibo", "FBC/FinancialInstruments/InstrumentClassification"
        ),
    )
    registry.concept(
        "trade_report",
        definition="An EMIR trade-state submission to the trade repository.",
        # deliberately no external mapping: the NO_BRIDGE case
    )
    return registry


class BaseA(SemanticBase, DeclarativeBase):
    pass


@semantic_table(
    description="EMIR trade state report, one row per open derivative",
    time_dimension="reporting_date",
    concept="trade_report",
)
class EmirTradeState(BaseA):
    __tablename__ = "emir_trade_state"

    uti = Column(String, primary_key=True)
    uti_description = "Unique transaction identifier"

    cpty_lei = Column(String)
    cpty_lei_description = "LEI of the counterparty to the contract"
    cpty_lei_concept = "counterparty.emir"

    notional = Column(Float)
    notional_description = "Contract notional amount in EUR"
    notional_concept = "notional"

    asset_class = Column(String)
    asset_class_description = "Asset class of the contract"
    asset_class_concept = "asset_class"

    reporting_date = Column(Date)


SEED_ROWS = [
    ("UTI-001", "LEI-AAA", 5_000_000.0, "IR"),
    ("UTI-002", "LEI-AAA", 3_000_000.0, "FX"),
    ("UTI-003", "LEI-BBB", 7_500_000.0, "IR"),
    ("UTI-004", "LEI-CCC", 1_250_000.0, "CR"),
]
