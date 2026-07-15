# Semantic Layer

Machine-readable database schema for natural language queries

## Database Entities (2 tables)

### account_info
- **Full Name**: account_info
- **Primary Key**: account_id
- **Description**: Master record for customer deposit and current accounts. One row per account.
- **Synonyms**: accounts, customer accounts, deposit accounts
- **Application Context**: Default scope is ACTIVE accounts unless the user explicitly asks for closed or dormant accounts.
- **Business Context**: Core banking — account master.

#### Columns
- **account_id** (INTEGER, restricted)
  - Column: account_id
- **account_status** (VARCHAR)
  - Lifecycle status: ACTIVE, DORMANT, CLOSED, FROZEN. Business questions default to ACTIVE.
  - *Examples*: ACTIVE, CLOSED
- **currency_code** (VARCHAR)
  - ISO 4217 currency of the account.
  - *Examples*: EUR, USD, GBP
- **available_balance** (DECIMAL, confidential)
  - Funds the customer can draw on now: ledger balance minus holds plus overdraft headroom. Prefer this for 'how much money' questions.
- **opened_date** (DATE)
  - Date the account was opened. Business date.
- **created_at** (TIMESTAMP)
  - Row creation timestamp (ETL audit column).
- **updated_at** (TIMESTAMP)
  - Row last-update timestamp (ETL audit column).

---

### transaction_info
- **Full Name**: transaction_info
- **Primary Key**: transaction_id
- **Description**: Posted account transactions, one row per movement. The business time axis is booking_date: use it for any per-day/month/quarter aggregation unless the user explicitly asks about value or settlement dating.
- **Synonyms**: transactions, postings, account movements
- **Application Context**: Amounts are signed: negative = debit, positive = credit. Sum of amount over a period is net flow, not turnover.
- **Business Context**: Core banking — transaction ledger.

#### Columns
- **transaction_id** (INTEGER, restricted)
  - Column: transaction_id
- **account_id** (INTEGER) ForeignKey → account_info.account_id
  - Owning account.
- **amount** (DECIMAL, confidential)
  - Signed transaction amount in the account currency. Negative = debit.
- **booking_date** (DATE)
  - Date the transaction was booked to the account. THE business time axis for time-series questions.
- **value_date** (DATE)
  - Date the amount becomes interest-effective. Only relevant for interest and value-dating questions.
- **settlement_date** (DATE)
  - Date funds actually settled. Only relevant for settlement/ops questions.
- **created_at** (TIMESTAMP)
  - Row creation timestamp (ETL audit column).
- **updated_at** (TIMESTAMP)
  - Row last-update timestamp (ETL audit column).

---

## Relationships (2 connections)

### account_info → transaction_info
- **Type**: one-to-many
- **Join**: account_info.account_id = transaction_info.account_id
- **Description**: Movements posted to this account.

### transaction_info → account_info
- **Type**: many-to-one
- **Join**: transaction_info.account_id = account_info.account_id
- **Description**: The account this movement belongs to.

## Summary
- **Total Tables**: 2
- **Total Columns**: 15
- **Total Relationships**: 2
## Time semantics and defaults

- account_info: PRIMARY time dimension = opened_date (use for any per-day/month/quarter aggregation)
- account_info.opened_date: native grain day
- account_info.created_at: operational audit timestamp — do not use as a time axis
- account_info.updated_at: operational audit timestamp — do not use as a time axis
- account_info: default filter -> account_status = 'ACTIVE'
- transaction_info: PRIMARY time dimension = booking_date (use for any per-day/month/quarter aggregation)
- transaction_info.booking_date: native grain day
- transaction_info.value_date: native grain day
- transaction_info.value_date: secondary time dimension
- transaction_info.created_at: operational audit timestamp — do not use as a time axis
- transaction_info.updated_at: operational audit timestamp — do not use as a time axis

## Glossary

- booking date: date a movement is booked to the account (the axis)
- value date: date a movement becomes interest-effective
- net flow: signed sum of amounts over a period (not turnover)
