"""Concept registry for the EMIR/MiFIR trade reporting schema.

Article 02 of the series argues that semantics must come before ontology:
first say what a thing *is* in the context it is used, then build the graph
on top. This module is that argument in code. Each concept below is a
definition first — prose a domain expert would recognise — and only then a
node with edges.

The schema this registry describes encodes three classic text-to-SQL failure
modes. Two of them stop being prose warnings once the concepts are declared,
because the linter can then reject the query statically:

  * amount ambiguity — notional, valuation and price are three different
    measures at three different grains, all stored as NUMERIC. Declared
    DISTINCT_FROM one another, so equating them is an SL009 error.

  * identifier grain — a UTI identifies a contract, a MiFIR transaction
    reference identifies an execution, an ISIN identifies an issue. Joining
    across them is an SL008 error.

The third, bridge fan-out, is *not* caught — see the note at the foot of
this file.
"""

from semantido import ConceptRegistry, OntologySource

registry = ConceptRegistry(namespace="tradereporting")
registry.add_source(
    OntologySource(
        name="tradereporting",
        namespace="urn:hikarilabs:tradereporting",
        version="1.0.0",
    )
)

# --- identifiers, each at its own grain ------------------------------------

lei = registry.concept(
    "lei",
    "ISO 17442 Legal Entity Identifier. Identifies a legal entity, not a "
    "trading relationship and not an account.",
    synonyms=["LEI"],
    grain="legal_entity",
)

uti = registry.concept(
    "uti",
    "Unique Trade Identifier per ISO 23897. Identifies one derivative "
    "contract, shared bilaterally: both counterparties report the same UTI "
    "to their respective trade repositories.",
    synonyms=["UTI", "trade identifier"],
    grain="contract",
)

transaction_reference = registry.concept(
    "transaction_reference",
    "MiFIR RTS 22 transaction reference. Identifies one execution on a "
    "venue. A single block execution may be allocated into many contracts, "
    "so this is a finer grain than the UTI.",
    synonyms=["transaction reference"],
    grain="execution",
    distinct_from=uti,
)

isin = registry.concept(
    "isin",
    "ISO 6166 identifier. Identifies an issue — one security as issued, "
    "irrespective of where it trades.",
    synonyms=["ISIN"],
    grain="issue",
    distinct_from=uti,
)

# --- the counterparty homonym ---------------------------------------------

counterparty_emir = registry.concept(
    "counterparty.emir",
    "EMIR Article 9: either of the two entities party to a derivative "
    "contract. Both sides report, and both appear on the contract.",
    label="Counterparty",
    synonyms=["counterparty", "cpty"],
    grain="legal_entity",
)

party_mifir = registry.concept(
    "party.mifir",
    "MiFIR RTS 22: the buyer or seller in a transaction report. A client on "
    "whose behalf the firm deals is a buyer or seller here — it is NOT the "
    "EMIR counterparty, even though the same legal entity may occupy both "
    "roles on the same trade.",
    label="Buyer or seller",
    synonyms=["buyer", "seller"],
    grain="legal_entity",
    distinct_from=counterparty_emir,
)

# --- the three amounts, which are not the same measure ---------------------

notional = registry.concept(
    "notional",
    "Unsigned contract size, per contract. Not exposure and not market "
    "value. Economic direction lives in the direction code, never in the "
    "sign of this amount.",
    synonyms=["notional amount", "contract size"],
    grain="contract",
)

valuation = registry.concept(
    "valuation",
    "Signed mark-to-market valuation of a contract on a given date. Changes "
    "daily while the notional does not.",
    synonyms=["mark to market", "MTM", "exposure"],
    grain="contract_date",
    distinct_from=notional,
)

price = registry.concept(
    "price",
    "Execution price of a single transaction, in the venue's quote "
    "convention. Per execution, not per contract.",
    synonyms=["execution price"],
    grain="execution",
    distinct_from=[notional, valuation],
)

__all__ = [
    "registry",
    "lei",
    "uti",
    "transaction_reference",
    "isin",
    "counterparty_emir",
    "party_mifir",
    "notional",
    "valuation",
    "price",
]

# --- what this registry does NOT protect you from -------------------------
#
# The bridge fan-out. trade_parties links one trade to several counterparties
# by role; joining trade_reports through it and summing notional multiplies
# every contract by its party count. Both sides of that join carry the same
# concept at the same grain, so no shipped check sees it.
#
# Declaring a concept makes a class of error machine-checkable. It does not
# make every error machine-checkable, and an example that implied otherwise
# would be lying to you. See examples/07_security_master for the same limit
# in reference data.
