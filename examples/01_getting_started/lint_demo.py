"""The three failure modes, and which of them the linter can now reject.

`models/trade_reporting.py` has always documented three classic text-to-SQL
traps in its docstring. Until v0.5 that docstring was the only defence: prose,
true when written, unverifiable afterwards.

Two of the three are now machine-checkable, because the concepts are declared.
The third is not, and this file says so rather than quietly omitting it.

    pip install 'semantido[lint]>=0.5.3'
    python lint_demo.py
"""

from semantido import SemanticDeclarativeBase
from semantido.generators.semantic_layer import Relationship
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

RULE = "-" * 76

CASES = [
    (
        "Amount ambiguity",
        "trade_reports.notional_amount = trade_valuations.valuation_amount",
        "trade_reports",
        "trade_valuations",
        "Both are NUMERIC(20,2). One is unsigned contract size, the other a "
        "signed daily mark-to-market. Equating them is meaningless.",
    ),
    (
        "Identifier grain",
        "trade_reports.uti = mifir_transactions.transaction_reference",
        "trade_reports",
        "mifir_transactions",
        "A UTI identifies a contract; a transaction reference identifies an "
        "execution. One block execution allocates into many contracts.",
    ),
    (
        "Party homonym",
        "trade_parties.counterparty_id = mifir_transactions.buyer_id",
        "trade_parties",
        "mifir_transactions",
        "Both are entity references and the same firm may occupy both roles. "
        "They are not the same concept, and the join returns plausible rows.",
    ),
]


def probe(layer, condition: str, frm: str, to: str) -> list[str]:
    idx = len(layer.relationships)
    layer.add_relationship(
        Relationship(
            from_table=frm,
            to_table=to,
            join_condition=condition,
            relationship_type="many_to_many",
            description="probe",
        )
    )
    codes = sorted(
        {
            f.code
            for f in lint_layer(layer)
            if f.location.endswith(f"[{idx}]") and f.severity.value == "error"
        }
    )
    del layer.relationships[idx:]
    return codes


def main() -> None:
    registry.validate()
    layer = SemanticDeclarativeBase.sync_semantic_layer(concept_registry=registry)

    print("=" * 76)
    print("WHAT THE DECLARED CONCEPTS NOW REJECT")
    print("=" * 76)

    for title, condition, frm, to, why in CASES:
        codes = probe(layer, condition, frm, to)
        verdict = "+".join(codes) if codes else "NOT CAUGHT"
        print(f"\n{title}")
        print(RULE)
        print(f"  {condition}")
        print(f"  {why}")
        print(f"  -> {verdict}")

    print("\n\nBridge fan-out")
    print(RULE)
    print("  trade_reports JOIN trade_parties ON trade_id, then SUM(notional)")
    print(
        "  trade_parties links one contract to several counterparties by "
        "role,\n  so the sum multiplies every contract by its party count."
    )
    print("  -> NOT CAUGHT")
    print(
        "\n  Both sides of that join carry the same concept at the same "
        "grain, so\n  no shipped check sees it. Cardinality is a separate "
        "axis from grain and\n  needs the column tuple that makes a row "
        "unique."
    )

    print("\n" + RULE)
    print("Two of three enforced. The third is still a docstring.")
    print(RULE)


if __name__ == "__main__":
    main()
