"""EMIR/MiFIR counterparty homonym — the schema the linter is pointed at.

Every identifier column below is a VARCHAR(20) holding an LEI. Nothing in the
DDL distinguishes the EMIR sense of "counterparty" from the MiFIR sense, which
is why a join between them runs, returns rows, and answers a question nobody
asked. The concept registry is where that distinction is written down.

Verified against semantido 0.5.3.
"""

from sqlalchemy import Column, Date, Numeric, String
from sqlalchemy.orm import DeclarativeBase

from semantido import (
    ConceptRegistry,
    OntologySource,
    SemanticBase,
    semantic_table,
)
from semantido.generators.concept_registry import exact_match


class Base(SemanticBase, DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Concept registry — portable meaning, slow and governed
# ---------------------------------------------------------------------------

FIBO_PARTY = "https://spec.edmcouncil.org/fibo/ontology/FBC/FunctionalEntities/Party"

registry = ConceptRegistry(namespace="regreport")
registry.add_source(
    OntologySource(
        name="regreport",
        namespace="urn:hikarilabs:regreport",
        version="1.0.0",
    )
)
registry.add_source(
    OntologySource(
        name="fibo",
        namespace="https://spec.edmcouncil.org/fibo/ontology/",
        version="2024Q3",
    )
)

cpty_emir = registry.concept(
    "counterparty.emir",
    "Either entity party to a derivative contract under EMIR Article 9. "
    "Both sides of the contract report; the counterparty is the entity on "
    "the other side of the contractual relationship, identified by LEI.",
    label="Counterparty",
    synonyms=["counterparty", "cpty"],
    grain="legal_entity",
    external=exact_match("fibo", FIBO_PARTY, because="EMIR Article 9 sense"),
)

cpty_mifir = registry.concept(
    "counterparty.mifir",
    "The market-side entity faced in a MiFIR RTS 22 transaction report. "
    "Follows the execution chain rather than the contractual relationship, "
    "so it is frequently a venue member rather than the contract party.",
    label="Counterparty",
    synonyms=["counterparty", "cpty"],
    grain="legal_entity",
    distinct_from=cpty_emir,
)


def add_contradictory_mapping() -> None:
    """Assert the contradiction SL010 exists to catch.

    counterparty.mifir claims skos:exactMatch to the same FIBO node that
    counterparty.emir already claims. exactMatch is transitive under SKOS,
    so this entails the two are interchangeable — which is precisely what
    the DISTINCT_FROM edge above denies.
    """
    cpty_mifir.mappings.append(
        exact_match("fibo", FIBO_PARTY, because="MiFIR RTS 22 sense")
    )


# ---------------------------------------------------------------------------
# Physical models — deployment facts, fast and accidental
# ---------------------------------------------------------------------------


@semantic_table(
    description="EMIR Article 9 dual-sided trade reports, one row per "
    "reporting counterparty per contract.",
    synonyms=["emir reports", "trade reports"],
    concept="counterparty.emir",
    time_dimension="reporting_date",
)
class EmirTradeReport(Base):
    __tablename__ = "emir_trade_report"

    uti = Column(String(52), primary_key=True)
    uti_description = "Unique Trade Identifier per ISO 23897. Shared by both sides."
    reporting_cpty_lei = Column(String(20))
    reporting_cpty_lei_concept = "counterparty.emir"
    other_cpty_lei = Column(String(20))
    other_cpty_lei_concept = "counterparty.emir"
    other_cpty_lei_description = "LEI of the contractual counterparty."
    notional = Column(Numeric(20, 2))
    notional_description = "Unsigned contract size. Not exposure."
    reporting_date = Column(Date)


@semantic_table(
    description="MiFIR RTS 22 transaction reports, one row per reportable execution.",
    synonyms=["mifir reports", "transaction reports"],
    concept="counterparty.mifir",
    time_dimension="trading_date",
)
class MifirTransactionReport(Base):
    __tablename__ = "mifir_transaction_report"

    tvtic = Column(String(52), primary_key=True)
    tvtic_description = "Trading Venue Transaction Identification Code."
    market_cpty_lei = Column(String(20))
    market_cpty_lei_concept = "counterparty.mifir"
    market_cpty_lei_description = (
        "LEI of the market-side entity faced. Loosely called the "
        "'counterparty' in venue documentation — it is NOT the "
        "EMIR-reporting counterparty."
    )
    price = Column(Numeric(20, 6))
    trading_date = Column(Date)


def build_layer(*, contradictory: bool = False):
    """Sync the layer. Set contradictory=True to arm the SL010 case."""
    if contradictory:
        add_contradictory_mapping()
    registry.validate()
    return Base.get_semantic_bridge().sync_from_models(concept_registry=registry)
