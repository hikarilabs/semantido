"""Core banking models for the OSI time-dimension example.

The `transaction_info` table is deliberately adversarial: it carries FIVE
temporal columns of which exactly ONE — booking_date — is the business time
axis an agent should GROUP BY for questions like "monthly transaction volume".
This is the classic wholesale-banking failure mode (booking vs. value vs.
settlement dating) that the curated time dimension exists to solve.

Note on the primary time axis: the bridge reads it from the
``__semantic_time_dimension__`` class attribute. Until the
``@semantic_table(time_dimension=...)`` keyword lands, declare it directly in
the model body as shown below.
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from semantido import SemanticDeclarativeBase, semantic_table
from semantido.generators.semantic_layer import TimeGrain
from semantido.generators.semantic_layer import PrivacyLevel


@semantic_table(
    description=(
        "Master record for customer deposit and current accounts. One row per account."
    ),
    synonyms=["accounts", "customer accounts", "deposit accounts"],
    application_context=(
        "Default scope is ACTIVE accounts unless the user explicitly asks "
        "for closed or dormant accounts."
    ),
    business_context="Core banking — account master.",
    sql_filters=["account_status = 'ACTIVE'"],
    time_dimension="opened_date",
)
class AccountInfo(SemanticDeclarativeBase):
    """Customer account master."""

    __tablename__ = "account_info"

    account_id = Column(Integer, primary_key=True)
    account_id_privacy_level = PrivacyLevel.RESTRICTED

    account_status = Column(String(16))
    account_status_description = (
        "Lifecycle status: ACTIVE, DORMANT, CLOSED, FROZEN. "
        "Business questions default to ACTIVE."
    )
    account_status_sample_values = ["ACTIVE", "CLOSED"]

    currency_code = Column(String(3))
    currency_code_description = "ISO 4217 currency of the account."
    currency_code_sample_values = ["EUR", "USD", "GBP"]

    available_balance = Column(Numeric(18, 2))
    available_balance_description = (
        "Funds the customer can draw on now: ledger balance minus holds "
        "plus overdraft headroom. Prefer this for 'how much money' questions."
    )
    available_balance_privacy_level = PrivacyLevel.CONFIDENTIAL

    opened_date = Column(Date)
    opened_date_description = "Date the account was opened. Business date."
    opened_date_time_grain = TimeGrain.DAY

    created_at = Column(DateTime)
    created_at_description = "Row creation timestamp (ETL audit column)."
    updated_at = Column(DateTime)
    updated_at_description = "Row last-update timestamp (ETL audit column)."

    transactions = relationship("TransactionInfo", back_populates="account")
    transactions_relationship_description = "Movements posted to this account."


@semantic_table(
    description=(
        "Posted account transactions, one row per movement. The business "
        "time axis is booking_date: use it for any per-day/month/quarter "
        "aggregation unless the user explicitly asks about value or "
        "settlement dating."
    ),
    synonyms=["transactions", "postings", "account movements"],
    application_context=(
        "Amounts are signed: negative = debit, positive = credit. Sum of "
        "amount over a period is net flow, not turnover."
    ),
    business_context="Core banking — transaction ledger.",
    time_dimension="booking_date",
)
class TransactionInfo(SemanticDeclarativeBase):
    """Posted transactions with five temporal columns and one true axis."""

    __tablename__ = "transaction_info"

    transaction_id = Column(Integer, primary_key=True)
    transaction_id_privacy_level = PrivacyLevel.RESTRICTED

    account_id = Column(Integer, ForeignKey("account_info.account_id"))
    account_id_description = "Owning account."

    amount = Column(Numeric(18, 2))
    amount_description = (
        "Signed transaction amount in the account currency. Negative = debit."
    )
    amount_privacy_level = PrivacyLevel.CONFIDENTIAL

    booking_date = Column(Date)
    booking_date_description = (
        "Date the transaction was booked to the account. THE business time "
        "axis for time-series questions."
    )
    booking_date_time_grain = "day"  # strings are normalized to TimeGrain

    value_date = Column(Date)
    value_date_description = (
        "Date the amount becomes interest-effective. Only relevant for "
        "interest and value-dating questions."
    )
    value_date_is_time_dimension = True  # a secondary business axis
    value_date_time_grain = TimeGrain.DAY

    settlement_date = Column(Date)
    settlement_date_description = (
        "Date funds actually settled. Only relevant for settlement/ops questions."
    )

    created_at = Column(DateTime)
    created_at_description = "Row creation timestamp (ETL audit column)."
    updated_at = Column(DateTime)
    updated_at_description = "Row last-update timestamp (ETL audit column)."

    account = relationship("AccountInfo", back_populates="transactions")
    account_relationship_description = "The account this movement belongs to."
