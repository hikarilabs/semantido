"""EMIR/MiFIR trade reporting schema — semantido sample implementation.

A synthetic regulatory reporting subset mirroring the schema used in the
Hikari Labs semantic layer benchmark. It deliberately encodes the three
text-to-SQL failure modes the benchmark targets:

1. Bridge fan-out — trade_parties links trades to counterparties in
                         multiple roles; naive joins double-count notional.
2. Sign conventions — notional_amount is always positive; economic
                         direction lives in the `direction` code (BYER/SLLR).
3. Amount ambiguity — notional vs. mark-to-market valuation vs. collateral
                         market value are distinct concepts on three tables.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship

from semantido import semantic_table, SemanticDeclarativeBase
from semantido.generators.semantic_layer import PrivacyLevel, TimeGrain


@semantic_table(
    description=(
        "Legal entities that are party to reportable derivative trades. "
        "One row per LEI. Includes both reporting counterparties and their "
        "trade counterparties (clients, CCPs, brokers)."
    ),
    synonyms=["legal entity", "client", "trading party", "LEI record"],
    business_context=(
        "EMIR Art. 9 counterparty classification drives reporting obligations: "
        "FC (financial), NFC+ (non-financial above clearing threshold), "
        "NFC- (below threshold)."
    ),
    application_context="Reference data — updated via nightly GLEIF sync.",
)
class Counterparty(SemanticDeclarativeBase):
    """A legal entity identified by LEI."""

    __tablename__ = "counterparties"

    counterparty_id = Column(Integer, primary_key=True)
    lei = Column(String(20), nullable=False, unique=True)
    legal_name = Column(String(255), nullable=False)
    emir_classification = Column(String(4), nullable=False)
    jurisdiction = Column(String(2), nullable=False)
    is_ccp = Column(Boolean, nullable=False, default=False)

    lei_description = "ISO 17442 Legal Entity Identifier (20 characters)."
    lei_synonyms = ["legal entity identifier"]
    lei_sample_values = ["529900T8BM49AURSDO55", "213800MBWEIJDM5CU638"]
    lei_privacy_level = PrivacyLevel.INTERNAL

    legal_name_description = "Registered legal name of the entity."
    legal_name_privacy_level = PrivacyLevel.CONFIDENTIAL

    emir_classification_description = (
        "EMIR counterparty classification: FC, NFC+ or NFC-."
    )
    emir_classification_sample_values = ["FC", "NFC+", "NFC-"]
    emir_classification_synonyms = ["counterparty type", "EMIR category"]

    jurisdiction_description = "ISO 3166-1 alpha-2 country of incorporation."
    jurisdiction_sample_values = ["GB", "DE", "FR", "US"]

    is_ccp_description = (
        "True when the entity is a central counterparty (clearing house)."
    )

    trade_roles = relationship("TradeParty", back_populates="counterparty")


@semantic_table(
    description=(
        "Financial instruments referenced by trades. One row per ISIN "
        "(or internal identifier for OTC products without an ISIN)."
    ),
    synonyms=["product", "security", "derivative contract"],
    business_context=(
        "asset_class follows the EMIR taxonomy (IR, CR, EQ, FX, CO). "
        "cfi_code is the ISO 10962 classification used for MiFIR field 43."
    ),
)
class Instrument(SemanticDeclarativeBase):
    """A reportable financial instrument."""

    __tablename__ = "instruments"

    instrument_id = Column(Integer, primary_key=True)
    isin = Column(String(12))
    asset_class = Column(String(2), nullable=False)
    cfi_code = Column(String(6))
    notional_currency = Column(String(3), nullable=False)

    isin_description = (
        "ISO 6166 ISIN. NULL for bespoke OTC products with no ISIN; "
        "such products are identified by instrument_id only."
    )
    isin_sample_values = ["EZ9VVV8CQC69", "DE000C6900B7"]

    asset_class_description = "EMIR asset class: IR, CR, EQ, FX or CO."
    asset_class_sample_values = ["IR", "FX", "CR"]
    asset_class_synonyms = ["product class"]

    cfi_code_description = "ISO 10962 CFI classification code."
    notional_currency_description = "ISO 4217 currency of the notional amount."
    notional_currency_sample_values = ["EUR", "USD", "GBP"]

    trades = relationship("TradeReport", back_populates="instrument")


@semantic_table(
    description=(
        "EMIR trade reports (trade state view). One row per UTI representing "
        "the latest reported state of a derivative trade."
    ),
    synonyms=["trades", "derivative trades", "EMIR reports", "trade state"],
    sql_filters=["action_type != 'E'  -- exclude error-cancelled reports"],
    business_context=(
        "notional_amount is ALWAYS POSITIVE regardless of direction. "
        "The economic side of the reporting counterparty is in `direction` "
        "(BYER = buyer/payer, SLLR = seller/receiver). Never infer sign "
        "from the amount. To aggregate exposure, join counterparties via "
        "trade_parties and filter role = 'REPORTING' to avoid fan-out."
    ),
    application_context=(
        "Sourced from the trade repository submission feed; refreshed T+1."
    ),
)
class TradeReport(SemanticDeclarativeBase):
    """Latest state of an EMIR-reportable derivative trade."""

    __tablename__ = "trade_reports"
    __semantic_time_dimension__ = "execution_timestamp"

    trade_id = Column(Integer, primary_key=True)
    uti = Column(String(52), nullable=False, unique=True)
    instrument_id = Column(
        Integer, ForeignKey("instruments.instrument_id"), nullable=False
    )
    execution_timestamp = Column(DateTime, nullable=False)
    effective_date = Column(Date, nullable=False)
    maturity_date = Column(Date)
    notional_amount = Column(Numeric(20, 2), nullable=False)
    direction = Column(String(4), nullable=False)
    action_type = Column(String(1), nullable=False)
    cleared = Column(Boolean, nullable=False, default=False)
    venue_mic = Column(String(4))
    created_at = Column(DateTime, nullable=False)

    uti_description = "Unique Trade Identifier (ISO 23897), max 52 chars."
    uti_synonyms = ["trade identifier", "UTI"]
    uti_privacy_level = PrivacyLevel.INTERNAL

    execution_timestamp_description = (
        "UTC timestamp when the trade was executed. Primary business time axis."
    )
    execution_timestamp_time_grain = TimeGrain.SECOND
    execution_timestamp_synonyms = ["trade date", "execution time"]

    effective_date_description = "Date the contract obligations become effective."
    effective_date_is_time_dimension = True
    effective_date_time_grain = "day"

    maturity_date_description = "Contract maturity/expiry date. NULL for open-ended."
    maturity_date_time_grain = TimeGrain.DAY

    notional_amount_description = (
        "Trade notional in notional_currency. Always positive; direction of "
        "risk is given by `direction`, never by sign."
    )
    notional_amount_synonyms = ["notional", "trade size"]
    notional_amount_application_rules = [
        "Never SUM across both trade_parties roles — double counts.",
        "Sign is always positive; use direction for buy/sell split.",
    ]

    direction_description = (
        "Side of the reporting counterparty: BYER (buyer/payer leg) or "
        "SLLR (seller/receiver leg)."
    )
    direction_sample_values = ["BYER", "SLLR"]
    direction_synonyms = ["side", "buy/sell indicator"]

    action_type_description = (
        "EMIR action type of the latest report: N=New, M=Modify, C=Terminate, "
        "E=Error, R=Correction, V=Valuation update."
    )
    action_type_sample_values = ["N", "M", "C"]

    cleared_description = "True when cleared through a CCP."
    venue_mic_description = (
        "ISO 10383 MIC of the execution venue. 'XXXX' or NULL for pure OTC."
    )
    created_at_description = "Row load timestamp (ETL audit only)."

    instrument = relationship("Instrument", back_populates="trades")
    instrument_relationship_description = (
        "The financial instrument underlying this trade report"
    )
    parties = relationship("TradeParty", back_populates="trade")
    valuations = relationship("TradeValuation", back_populates="trade")
    valuations_relationship_description = (
        "Daily mark-to-market valuation history for this trade"
    )


@semantic_table(
    description=(
        "Bridge table assigning counterparties to trades in specific roles. "
        "A trade has at least two rows here (REPORTING and OTHER), plus "
        "optional CCP, BROKER and CLEARING_MEMBER rows."
    ),
    synonyms=["trade counterparty roles", "party roles"],
    business_context=(
        "This is a fan-out bridge: joining trade_reports to trade_parties "
        "multiplies trade rows by the number of roles. Aggregations over "
        "trade amounts MUST filter on a single role (usually 'REPORTING')."
    ),
)
class TradeParty(SemanticDeclarativeBase):
    """Role-qualified link between a trade and a counterparty."""

    __tablename__ = "trade_parties"

    trade_party_id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("trade_reports.trade_id"), nullable=False)
    counterparty_id = Column(
        Integer, ForeignKey("counterparties.counterparty_id"), nullable=False
    )
    role = Column(String(16), nullable=False)

    role_description = (
        "Role of the counterparty on the trade: REPORTING, OTHER, CCP, "
        "BROKER or CLEARING_MEMBER."
    )
    role_sample_values = ["REPORTING", "OTHER", "CCP"]
    role_application_rules = [
        "Always filter to one role before aggregating trade amounts.",
    ]

    trade = relationship("TradeReport", back_populates="parties")
    counterparty = relationship("Counterparty", back_populates="trade_roles")


@semantic_table(
    description=(
        "Daily mark-to-market valuations per trade (EMIR Art. 11 / action "
        "type V). One row per trade per valuation date."
    ),
    synonyms=["valuations", "MTM", "mark-to-market"],
    business_context=(
        "valuation_amount is SIGNED from the reporting counterparty's "
        "perspective: positive = asset (in the money), negative = liability. "
        "This differs from notional_amount on trade_reports, which is "
        "unsigned. 'Exposure' questions usually mean valuation, not notional."
    ),
)
class TradeValuation(SemanticDeclarativeBase):
    """Signed daily MTM valuation of a trade."""

    __tablename__ = "trade_valuations"
    __semantic_time_dimension__ = "valuation_date"

    valuation_id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("trade_reports.trade_id"), nullable=False)
    valuation_date = Column(Date, nullable=False)
    valuation_amount = Column(Numeric(20, 2), nullable=False)
    valuation_currency = Column(String(3), nullable=False)
    valuation_type = Column(String(4), nullable=False)
    updated_at = Column(DateTime, nullable=False)

    valuation_date_description = "Business date of the valuation."
    valuation_date_time_grain = TimeGrain.DAY

    valuation_amount_description = (
        "Signed mark-to-market value from the reporting counterparty's view. "
        "Positive = in the money; negative = out of the money."
    )
    valuation_amount_synonyms = ["MTM value", "mark to market", "exposure"]
    valuation_amount_application_rules = [
        "Signed — do not take ABS() unless the question asks for gross MTM.",
        "For 'current exposure' use the latest valuation_date per trade.",
    ]

    valuation_currency_description = "ISO 4217 currency of valuation_amount."
    valuation_type_description = "MTMV = mark-to-market, MTMO = mark-to-model."
    valuation_type_sample_values = ["MTMV", "MTMO"]
    updated_at_description = "Row update timestamp (ETL audit only)."

    trade = relationship("TradeReport", back_populates="valuations")


@semantic_table(
    description=(
        "MiFIR Art. 26 transaction reports. Transaction-level executions "
        "reported to the NCA — related to but distinct from EMIR trade "
        "reports (different scope, different lifecycle)."
    ),
    synonyms=["MiFIR reports", "transaction reports", "RTS 22 reports"],
    sql_filters=["report_status = 'ACPT'  -- accepted reports only"],
    business_context=(
        "quantity and price are per MiFIR RTS 22: price excludes commission "
        "and accrued interest. buyer/seller are LEI references, not signed "
        "quantities — do not infer direction from quantity sign."
    ),
)
class MifirTransaction(SemanticDeclarativeBase):
    """A MiFIR RTS 22 transaction report."""

    __tablename__ = "mifir_transactions"
    __semantic_time_dimension__ = "trading_datetime"

    transaction_id = Column(Integer, primary_key=True)
    transaction_reference = Column(String(52), nullable=False, unique=True)
    instrument_id = Column(
        Integer, ForeignKey("instruments.instrument_id"), nullable=False
    )
    buyer_id = Column(
        Integer, ForeignKey("counterparties.counterparty_id"), nullable=False
    )
    seller_id = Column(
        Integer, ForeignKey("counterparties.counterparty_id"), nullable=False
    )
    trading_datetime = Column(DateTime, nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    quantity = Column(Numeric(20, 4), nullable=False)
    venue_mic = Column(String(4), nullable=False)
    report_status = Column(String(4), nullable=False)

    transaction_reference_description = (
        "Firm-assigned transaction reference number (MiFIR field 2)."
    )
    trading_datetime_description = (
        "UTC execution timestamp (MiFIR field 28). Primary time axis."
    )
    trading_datetime_time_grain = TimeGrain.SECOND

    price_description = (
        "Execution price excluding commission and accrued interest (field 33)."
    )
    quantity_description = (
        "Unsigned quantity (field 30). Direction is buyer_id/seller_id, "
        "never quantity sign."
    )
    quantity_application_rules = [
        "Always positive; do not infer buy/sell from sign.",
    ]
    venue_mic_description = "Execution venue MIC (field 36); 'XOFF' for off-venue."
    report_status_description = "NCA processing status: ACPT, RJCT or PDNG."
    report_status_sample_values = ["ACPT", "RJCT"]

    buyer = relationship("Counterparty", foreign_keys=[buyer_id])
    buyer_relationship_description = "The buying counterparty (LEI reference)"
    seller = relationship("Counterparty", foreign_keys=[seller_id])
    seller_relationship_description = "The selling counterparty (LEI reference)"
