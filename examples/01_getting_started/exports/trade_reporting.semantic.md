# Semantic Layer

Machine-readable database schema for natural language queries

## Database Entities (6 tables)

### counterparties
- **Full Name**: counterparties
- **Primary Key**: counterparty_id
- **Unique Keys**: lei
- **Description**: Legal entities that are party to reportable derivative trades. One row per LEI. Includes both reporting counterparties and their trade counterparties (clients, CCPs, brokers).
- **Synonyms**: legal entity, client, trading party, LEI record
- **Application Context**: Reference data — updated via nightly GLEIF sync.
- **Business Context**: EMIR Art. 9 counterparty classification drives reporting obligations: FC (financial), NFC+ (non-financial above clearing threshold), NFC- (below threshold).
- **Realizes concepts**: `lei`

#### Columns
- **counterparty_id** (INTEGER)
  - Column: counterparty_id
- **lei** (VARCHAR, internal)
  - ISO 17442 Legal Entity Identifier (20 characters).
  - *Concept*: `lei`
  - *Examples*: 529900T8BM49AURSDO55, 213800MBWEIJDM5CU638
  - *Synonyms*: legal entity identifier
- **legal_name** (VARCHAR, confidential)
  - Registered legal name of the entity.
- **emir_classification** (VARCHAR)
  - EMIR counterparty classification: FC, NFC+ or NFC-.
  - *Examples*: FC, NFC+, NFC-
  - *Synonyms*: counterparty type, EMIR category
- **jurisdiction** (VARCHAR)
  - ISO 3166-1 alpha-2 country of incorporation.
  - *Examples*: GB, DE, FR, US
- **is_ccp** (BOOLEAN)
  - True when the entity is a central counterparty (clearing house).

---

### instruments
- **Full Name**: instruments
- **Primary Key**: instrument_id
- **Description**: Financial instruments referenced by trades. One row per ISIN (or internal identifier for OTC products without an ISIN).
- **Synonyms**: product, security, derivative contract
- **Business Context**: asset_class follows the EMIR taxonomy (IR, CR, EQ, FX, CO). cfi_code is the ISO 10962 classification used for MiFIR field 43.
- **Realizes concepts**: `isin`

#### Columns
- **instrument_id** (INTEGER)
  - Column: instrument_id
- **isin** (VARCHAR)
  - ISO 6166 ISIN. NULL for bespoke OTC products with no ISIN; such products are identified by instrument_id only.
  - *Concept*: `isin`
  - *Examples*: EZ9VVV8CQC69, DE000C6900B7
- **asset_class** (VARCHAR)
  - EMIR asset class: IR, CR, EQ, FX or CO.
  - *Examples*: IR, FX, CR
  - *Synonyms*: product class
- **cfi_code** (VARCHAR)
  - ISO 10962 CFI classification code.
- **notional_currency** (VARCHAR)
  - ISO 4217 currency of the notional amount.
  - *Examples*: EUR, USD, GBP

---

### mifir_transactions
- **Full Name**: mifir_transactions
- **Primary Key**: transaction_id
- **Unique Keys**: transaction_reference
- **Description**: MiFIR Art. 26 transaction reports. Transaction-level executions reported to the NCA — related to but distinct from EMIR trade reports (different scope, different lifecycle).
- **Synonyms**: MiFIR reports, transaction reports, RTS 22 reports
- **Business Context**: quantity and price are per MiFIR RTS 22: price excludes commission and accrued interest. buyer/seller are LEI references, not signed quantities — do not infer direction from quantity sign.
- **Time Dimension**: trading_datetime — primary time axis; use for any per-day/month/quarter aggregation
- **Default Filters**: report_status = 'ACPT'  -- accepted reports only
- **Realizes concepts**: `transaction_reference`, `party.mifir`, `price`

#### Columns
- **transaction_id** (INTEGER)
  - Column: transaction_id
- **transaction_reference** (VARCHAR)
  - Firm-assigned transaction reference number (MiFIR field 2).
  - *Concept*: `transaction_reference`
- **instrument_id** (INTEGER) ForeignKey → instruments.instrument_id
  - Column: instrument_id
- **buyer_id** (INTEGER) ForeignKey → counterparties.counterparty_id
  - MiFIR buyer. Not the EMIR counterparty.
  - *Concept*: `party.mifir`
- **seller_id** (INTEGER) ForeignKey → counterparties.counterparty_id
  - MiFIR seller. Not the EMIR counterparty.
  - *Concept*: `party.mifir`
- **trading_datetime** (TIMESTAMP)
  - UTC execution timestamp (MiFIR field 28). Primary time axis.
  - *Time grain*: second
  - *Secondary time dimension*
- **price** (DECIMAL)
  - Execution price excluding commission and accrued interest (field 33).
  - *Concept*: `price`
- **quantity** (DECIMAL)
  - Unsigned quantity (field 30). Direction is buyer_id/seller_id, never quantity sign.
  - *Rule*: Always positive; do not infer buy/sell from sign.
- **venue_mic** (VARCHAR)
  - Execution venue MIC (field 36); 'XOFF' for off-venue.
- **report_status** (VARCHAR)
  - NCA processing status: ACPT, RJCT or PDNG.
  - *Examples*: ACPT, RJCT

---

### trade_parties
- **Full Name**: trade_parties
- **Primary Key**: trade_party_id
- **Description**: Bridge table assigning counterparties to trades in specific roles. A trade has at least two rows here (REPORTING and OTHER), plus optional CCP, BROKER and CLEARING_MEMBER rows.
- **Synonyms**: trade counterparty roles, party roles
- **Business Context**: This is a fan-out bridge: joining trade_reports to trade_parties multiplies trade rows by the number of roles. Aggregations over trade amounts MUST filter on a single role (usually 'REPORTING').
- **Realizes concepts**: `counterparty.emir`

#### Columns
- **trade_party_id** (INTEGER)
  - Column: trade_party_id
- **trade_id** (INTEGER) ForeignKey → trade_reports.trade_id
  - Column: trade_id
- **counterparty_id** (INTEGER) ForeignKey → counterparties.counterparty_id
  - The EMIR-sense counterparty on this contract. NOT interchangeable with the MiFIR buyer/seller on mifir_transactions, even when the same legal entity occupies both roles.
  - *Concept*: `counterparty.emir`
- **role** (VARCHAR)
  - Role of the counterparty on the trade: REPORTING, OTHER, CCP, BROKER or CLEARING_MEMBER.
  - *Examples*: REPORTING, OTHER, CCP
  - *Rule*: Always filter to one role before aggregating trade amounts.

---

### trade_reports
- **Full Name**: trade_reports
- **Primary Key**: trade_id
- **Unique Keys**: uti
- **Description**: EMIR trade reports (trade state view). One row per UTI representing the latest reported state of a derivative trade.
- **Synonyms**: trades, derivative trades, EMIR reports, trade state
- **Application Context**: Sourced from the trade repository submission feed; refreshed T+1.
- **Business Context**: notional_amount is ALWAYS POSITIVE regardless of direction. The economic side of the reporting counterparty is in `direction` (BYER = buyer/payer, SLLR = seller/receiver). Never infer sign from the amount. To aggregate exposure, join counterparties via trade_parties and filter role = 'REPORTING' to avoid fan-out.
- **Time Dimension**: execution_timestamp — primary time axis; use for any per-day/month/quarter aggregation
- **Default Filters**: action_type != 'E'  -- exclude error-cancelled reports
- **Realizes concepts**: `uti`, `notional`

#### Columns
- **trade_id** (INTEGER)
  - Column: trade_id
- **uti** (VARCHAR, internal)
  - Unique Trade Identifier (ISO 23897), max 52 chars.
  - *Concept*: `uti`
  - *Synonyms*: trade identifier, UTI
- **instrument_id** (INTEGER) ForeignKey → instruments.instrument_id
  - Column: instrument_id
- **execution_timestamp** (TIMESTAMP)
  - UTC timestamp when the trade was executed. Primary business time axis.
  - *Time grain*: second
  - *Secondary time dimension*
  - *Synonyms*: trade date, execution time
- **effective_date** (DATE)
  - Date the contract obligations become effective.
  - *Time grain*: day
  - *Secondary time dimension*
- **maturity_date** (DATE)
  - Contract maturity/expiry date. NULL for open-ended.
  - *Time grain*: day
- **notional_amount** (DECIMAL)
  - Trade notional in notional_currency. Always positive; direction of risk is given by `direction`, never by sign.
  - *Concept*: `notional`
  - *Synonyms*: notional, trade size
  - *Rule*: Never SUM across both trade_parties roles — double counts.
  - *Rule*: Sign is always positive; use direction for buy/sell split.
- **direction** (VARCHAR)
  - Side of the reporting counterparty: BYER (buyer/payer leg) or SLLR (seller/receiver leg).
  - *Examples*: BYER, SLLR
  - *Synonyms*: side, buy/sell indicator
- **action_type** (VARCHAR)
  - EMIR action type of the latest report: N=New, M=Modify, C=Terminate, E=Error, R=Correction, V=Valuation update.
  - *Examples*: N, M, C
- **cleared** (BOOLEAN)
  - True when cleared through a CCP.
- **venue_mic** (VARCHAR)
  - ISO 10383 MIC of the execution venue. 'XXXX' or NULL for pure OTC.
- **created_at** (TIMESTAMP)
  - Row load timestamp (ETL audit only).

---

### trade_valuations
- **Full Name**: trade_valuations
- **Primary Key**: valuation_id
- **Description**: Daily mark-to-market valuations per trade (EMIR Art. 11 / action type V). One row per trade per valuation date.
- **Synonyms**: valuations, MTM, mark-to-market
- **Business Context**: valuation_amount is SIGNED from the reporting counterparty's perspective: positive = asset (in the money), negative = liability. This differs from notional_amount on trade_reports, which is unsigned. 'Exposure' questions usually mean valuation, not notional.
- **Time Dimension**: valuation_date — primary time axis; use for any per-day/month/quarter aggregation
- **Realizes concepts**: `valuation`

#### Columns
- **valuation_id** (INTEGER)
  - Column: valuation_id
- **trade_id** (INTEGER) ForeignKey → trade_reports.trade_id
  - Column: trade_id
- **valuation_date** (DATE)
  - Business date of the valuation.
  - *Time grain*: day
  - *Secondary time dimension*
- **valuation_amount** (DECIMAL)
  - Signed mark-to-market value from the reporting counterparty's view. Positive = in the money; negative = out of the money.
  - *Concept*: `valuation`
  - *Synonyms*: MTM value, mark to market, exposure
  - *Rule*: Signed — do not take ABS() unless the question asks for gross MTM.
  - *Rule*: For 'current exposure' use the latest valuation_date per trade.
- **valuation_currency** (VARCHAR)
  - ISO 4217 currency of valuation_amount.
- **valuation_type** (VARCHAR)
  - MTMV = mark-to-market, MTMO = mark-to-model.
  - *Examples*: MTMV, MTMO
- **updated_at** (TIMESTAMP)
  - Row update timestamp (ETL audit only).

---

## Relationships (10 connections)

### counterparties → trade_parties
- **Type**: one-to-many
- **Join**: counterparties.counterparty_id = trade_parties.counterparty_id
- **Description**: Relationship between counterparties and trade_parties

### instruments → trade_reports
- **Type**: one-to-many
- **Join**: instruments.instrument_id = trade_reports.instrument_id
- **Description**: Relationship between instruments and trade_reports

### mifir_transactions → counterparties
- **Type**: many-to-one
- **Join**: mifir_transactions.buyer_id = counterparties.counterparty_id
- **Description**: The buying counterparty (LEI reference)

### mifir_transactions → counterparties
- **Type**: many-to-one
- **Join**: mifir_transactions.seller_id = counterparties.counterparty_id
- **Description**: The selling counterparty (LEI reference)

### trade_parties → trade_reports
- **Type**: many-to-one
- **Join**: trade_parties.trade_id = trade_reports.trade_id
- **Description**: Relationship between trade_parties and trade_reports

### trade_parties → counterparties
- **Type**: many-to-one
- **Join**: trade_parties.counterparty_id = counterparties.counterparty_id
- **Description**: Relationship between trade_parties and counterparties

### trade_reports → instruments
- **Type**: many-to-one
- **Join**: trade_reports.instrument_id = instruments.instrument_id
- **Description**: The financial instrument underlying this trade report

### trade_reports → trade_parties
- **Type**: one-to-many
- **Join**: trade_reports.trade_id = trade_parties.trade_id
- **Description**: Relationship between trade_reports and trade_parties

### trade_reports → trade_valuations
- **Type**: one-to-many
- **Join**: trade_reports.trade_id = trade_valuations.trade_id
- **Description**: Daily mark-to-market valuation history for this trade

### trade_valuations → trade_reports
- **Type**: many-to-one
- **Join**: trade_valuations.trade_id = trade_reports.trade_id
- **Description**: Relationship between trade_valuations and trade_reports

## Glossary (4 terms)

- **UTI**: Unique Trade Identifier per ISO 23897
- **notional**: unsigned contract size - not exposure
- **exposure**: signed mark-to-market valuation (trade_valuations)
- **NFC+**: non-financial counterparty above the clearing threshold

## Summary
- **Total Tables**: 6
- **Total Columns**: 44
- **Total Relationships**: 10

## Concepts (9 in scope)

Business concepts realized by this schema. The concept id is the authoritative reference; labels may collide (see Disambiguation).

### `counterparty.emir` — Counterparty
- **Definition**: EMIR Article 9: either of the two entities party to a derivative contract. Both sides report, and both appear on the contract.
- **Grain**: legal_entity
- **Synonyms**: counterparty, cpty
- **Realized by**: trade_parties.counterparty_id
- **Relation**: distinct from → `party.mifir`

### `isin` — isin
- **Definition**: ISO 6166 identifier. Identifies an issue — one security as issued, irrespective of where it trades.
- **Grain**: issue
- **Synonyms**: ISIN
- **Realized by**: instruments.isin
- **Relation**: distinct from → `uti`

### `lei` — lei
- **Definition**: ISO 17442 Legal Entity Identifier. Identifies a legal entity, not a trading relationship and not an account.
- **Grain**: legal_entity
- **Synonyms**: LEI
- **Realized by**: counterparties.lei

### `notional` — notional
- **Definition**: Unsigned contract size, per contract. Not exposure and not market value. Economic direction lives in the direction code, never in the sign of this amount.
- **Grain**: contract
- **Synonyms**: notional amount, contract size
- **Realized by**: trade_reports.notional_amount
- **Relation**: distinct from → `valuation`
- **Relation**: distinct from → `price`

### `party.mifir` — Buyer or seller
- **Definition**: MiFIR RTS 22: the buyer or seller in a transaction report. A client on whose behalf the firm deals is a buyer or seller here — it is NOT the EMIR counterparty, even though the same legal entity may occupy both roles on the same trade.
- **Grain**: legal_entity
- **Synonyms**: buyer, seller
- **Realized by**: mifir_transactions.buyer_id, mifir_transactions.seller_id
- **Relation**: distinct from → `counterparty.emir`

### `price` — price
- **Definition**: Execution price of a single transaction, in the venue's quote convention. Per execution, not per contract.
- **Grain**: execution
- **Synonyms**: execution price
- **Realized by**: mifir_transactions.price
- **Relation**: distinct from → `notional`
- **Relation**: distinct from → `valuation`

### `transaction_reference` — transaction reference
- **Definition**: MiFIR RTS 22 transaction reference. Identifies one execution on a venue. A single block execution may be allocated into many contracts, so this is a finer grain than the UTI.
- **Grain**: execution
- **Synonyms**: transaction reference
- **Realized by**: mifir_transactions.transaction_reference
- **Relation**: distinct from → `uti`

### `uti` — uti
- **Definition**: Unique Trade Identifier per ISO 23897. Identifies one derivative contract, shared bilaterally: both counterparties report the same UTI to their respective trade repositories.
- **Grain**: contract
- **Synonyms**: UTI, trade identifier
- **Realized by**: trade_reports.uti
- **Relation**: distinct from → `transaction_reference`
- **Relation**: distinct from → `isin`

### `valuation` — valuation
- **Definition**: Signed mark-to-market valuation of a contract on a given date. Changes daily while the notional does not.
- **Grain**: contract_date
- **Synonyms**: mark to market, MTM, exposure
- **Realized by**: trade_valuations.valuation_amount
- **Relation**: distinct from → `notional`
- **Relation**: distinct from → `price`
