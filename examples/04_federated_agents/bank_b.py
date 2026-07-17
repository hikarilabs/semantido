"""Bank B: an investment firm reporting under MiFIR RTS 22.

Local vocabulary diverges from Bank A on every term: "party" not
"legal entity", "transaction_amount" not "notional", "counterparty"
in the legally distinct MiFIR sense.
Registry namespace: bank_b.vocab.
"""

from sqlalchemy import Column, Date, Float, String
from sqlalchemy.orm import DeclarativeBase

from semantido import SemanticBase, semantic_table
from semantido.concepts import (
    ConceptRegistry,
    OntologySource,
    exact_match,
    narrow_match,
)


def build_registry() -> ConceptRegistry:
    registry = ConceptRegistry("bank_b.vocab")

    # Same anchor and SAME pin as Bank A -> exact bridge
    registry.add_source(
        OntologySource(
            name="gleif", namespace="urn:gleif:lei", version="2026-06"
        )
    )
    # Same anchor, NEWER pin than Bank A (2026Q1 vs 2025Q3)
    registry.add_source(
        OntologySource(
            name="fibo",
            namespace="https://spec.edmcouncil.org/fibo/ontology/",
            version="2026Q1",
            profile="fnd-parties",
        )
    )
    registry.add_source(
        OntologySource(
            name="esma_mifir",
            namespace="urn:eu:mifir:rts22",
            version="2021",
        )
    )
    registry.add_source(
        OntologySource(
            name="iso20022", namespace="urn:iso:20022", version="2025"
        )
    )

    party = registry.concept(
        "party",
        definition="Any LEI-identified participant on either side of a transaction.",
        external=exact_match("gleif", "lei"),
    )
    registry.concept(
        "counterparty.mifir",
        label="counterparty",
        definition=(
            "Buyer/seller identification in a MiFIR transaction report "
            "(RTS 22); legally distinct from the EMIR notion."
        ),
        broader=party,
        external=[
            narrow_match(
                "fibo",
                "FND/Parties/Parties/Counterparty",
                because="MiFIR sense is execution-report-scoped",
            ),
            exact_match("esma_mifir", "fields:7-16"),
        ],
    )
    registry.concept(
        "transaction_amount",
        definition="Monetary amount of the executed transaction, EUR.",
        external=[
            exact_match("fibo", "DER/DerivativesContracts/NotionalAmount"),
            exact_match("iso20022", "auth:NotionalAmount"),
        ],
    )
    registry.concept(
        "instrument_class",
        definition="Classification of the reported financial instrument.",
        external=exact_match(
            "fibo", "FBC/FinancialInstruments/InstrumentClassification"
        ),
    )
    registry.concept(
        "execution_report",
        definition="A MiFIR RTS 22 transaction report submission.",
        # no external mapping: NO_BRIDGE from the other side too
    )
    return registry


class BaseB(SemanticBase, DeclarativeBase):
    pass


@semantic_table(
    description="MiFIR transaction report, one row per execution",
    time_dimension="trade_date",
    concept="execution_report",
)
class MifirTransaction(BaseB):
    __tablename__ = "mifir_transaction"

    tx_ref = Column(String, primary_key=True)
    tx_ref_description = "Transaction reference number"

    buyer_lei = Column(String)
    buyer_lei_description = "LEI of the buyer"
    buyer_lei_concept = "counterparty.mifir"

    amount = Column(Float)
    amount_description = "Executed amount in EUR"
    amount_concept = "transaction_amount"

    trade_date = Column(Date)


SEED_ROWS = [
    ("TX-901", "LEI-AAA", 2_000_000.0),
    ("TX-902", "LEI-DDD", 4_400_000.0),
    ("TX-903", "LEI-BBB", 900_000.0),
]
