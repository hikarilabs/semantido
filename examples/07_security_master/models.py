"""Security master — three vendor feeds, three grains, one instrument.

The point of this file: every identifier column below is a VARCHAR. Nothing
in the DDL distinguishes an issue-grain identifier from a listing-grain one,
which is why an agent handed raw schema joins them to each other. The concept
registry is where that distinction is written down.

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


class Base(SemanticBase, DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Concept registry — meaning, portable across deployments
# ---------------------------------------------------------------------------

registry = ConceptRegistry(namespace="secmaster")
registry.add_source(
    OntologySource(
        name="secmaster",
        namespace="urn:hikarilabs:secmaster",
        version="1.0.0",
    )
)

isin = registry.concept(
    "isin",
    "ISO 6166 International Securities Identification Number. Identifies an "
    "issue — one security as issued — irrespective of where it trades. ANNA "
    "and its national numbering agencies are authoritative for existence.",
    synonyms=["ISIN", "issue identifier"],
    grain="issue",
)

figi = registry.concept(
    "figi",
    "OpenFIGI identifier. Identifies a listing — one instrument on one venue. "
    "A single issue carries many FIGIs by design; the share-class FIGI is the "
    "issue-level rollup and is a different concept.",
    synonyms=["FIGI", "Bloomberg FIGI"],
    grain="listing",
    distinct_from=isin,
)

ric = registry.concept(
    "ric",
    "Refinitiv Instrument Code. Identifies a listing on one venue, carrying "
    "vendor quote conventions — notably that UK equity RICs quote in pence "
    "while the ISIN-level record is denominated in GBP.",
    synonyms=["RIC", "Reuters code"],
    grain="listing",
    distinct_from=isin,
)

# distinct_from is reciprocated automatically: isin now carries the edge back
# to both figi and ric.


# ---------------------------------------------------------------------------
# Physical models — deployment facts, change at migration speed
# ---------------------------------------------------------------------------


@semantic_table(
    description="Bloomberg vendor feed, one row per listing per business date.",
    synonyms=["bbg feed", "bloomberg extract"],
    business_context="Licence-encumbered. Redistribution of px_last outside "
    "the licensed desk is an audit exposure.",
    concept="figi",
    time_dimension="extract_date",
)
class BloombergFeed(Base):
    __tablename__ = "bloomberg_feed"

    figi = Column(String(12), primary_key=True)
    figi_concept = "figi"
    figi_description = "Listing-grain Bloomberg identifier."
    isin = Column(String(12))
    isin_concept = "isin"
    isin_description = (
        "Issue-grain identifier, REPEATED across every listing row. "
        "Not a key on this table."
    )
    venue = Column(String(4))
    venue_description = "ISO 10383 MIC of the listing venue."
    px_last = Column(Numeric(18, 6))
    px_last_description = "Last price in the venue's quote convention."
    extract_date = Column(Date, primary_key=True)


@semantic_table(
    description="Refinitiv vendor feed, one row per listing per business date.",
    synonyms=["rtr feed", "refinitiv extract"],
    concept="ric",
    time_dimension="extract_date",
)
class RefinitivFeed(Base):
    __tablename__ = "refinitiv_feed"

    ric = Column(String(20), primary_key=True)
    ric_concept = "ric"
    ric_description = "Listing-grain Refinitiv identifier."
    isin = Column(String(12))
    isin_concept = "isin"
    isin_description = (
        "Issue-grain identifier, REPEATED across every listing row. "
        "Not a key on this table."
    )
    venue = Column(String(4))
    venue_description = "ISO 10383 MIC of the listing venue."
    px_last = Column(Numeric(18, 6))
    px_last_description = (
        "Last price. UK equity RICs quote in PENCE while the ISIN-level "
        "record is denominated in GBP — a factor of 100."
    )
    extract_date = Column(Date, primary_key=True)


@semantic_table(
    description="ANNA register, the issue-grain golden source. One row per ISIN.",
    synonyms=["anna", "issue register"],
    concept="isin",
    time_dimension="registered_date",
)
class AnnaRegister(Base):
    __tablename__ = "anna_register"

    isin = Column(String(12), primary_key=True)
    isin_concept = "isin"
    issuer_name = Column(String(140))
    currency = Column(String(3))
    currency_description = "Issue currency. GBP for UK ordinary shares."
    registered_date = Column(Date)


def build_layer():
    registry.validate()
    return Base.get_semantic_bridge().sync_from_models(concept_registry=registry)
