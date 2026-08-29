# Semantic Layer

Machine-readable database schema for natural language queries

## Database Entities (3 tables)

### anna_register
- **Full Name**: anna_register
- **Primary Key**: isin
- **Description**: ANNA register, the issue-grain golden source. One row per ISIN.
- **Concept**: `isin`
- **Synonyms**: anna, issue register
- **Time Dimension**: registered_date — primary time axis; use for any per-day/month/quarter aggregation

#### Columns
- **isin** (VARCHAR)
  - Column: isin
  - *Concept*: `isin`
- **issuer_name** (VARCHAR)
  - Column: issuer_name
- **currency** (VARCHAR)
  - Issue currency. GBP for UK ordinary shares.
- **registered_date** (DATE)
  - Column: registered_date
  - *Secondary time dimension*

---

### bloomberg_feed
- **Full Name**: bloomberg_feed
- **Primary Key**: figi, extract_date
- **Description**: Bloomberg vendor feed, one row per listing per business date.
- **Concept**: `figi`
- **Synonyms**: bbg feed, bloomberg extract
- **Business Context**: Licence-encumbered. Redistribution of px_last outside the licensed desk is an audit exposure.
- **Time Dimension**: extract_date — primary time axis; use for any per-day/month/quarter aggregation
- **Realizes concepts**: `isin`

#### Columns
- **figi** (VARCHAR)
  - Listing-grain Bloomberg identifier.
  - *Concept*: `figi`
- **isin** (VARCHAR)
  - Issue-grain identifier, REPEATED across every listing row. Not a key on this table.
  - *Concept*: `isin`
- **venue** (VARCHAR)
  - ISO 10383 MIC of the listing venue.
- **px_last** (DECIMAL)
  - Last price in the venue's quote convention.
- **extract_date** (DATE)
  - Column: extract_date
  - *Secondary time dimension*

---

### refinitiv_feed
- **Full Name**: refinitiv_feed
- **Primary Key**: ric, extract_date
- **Description**: Refinitiv vendor feed, one row per listing per business date.
- **Concept**: `ric`
- **Synonyms**: rtr feed, refinitiv extract
- **Time Dimension**: extract_date — primary time axis; use for any per-day/month/quarter aggregation
- **Realizes concepts**: `isin`

#### Columns
- **ric** (VARCHAR)
  - Listing-grain Refinitiv identifier.
  - *Concept*: `ric`
- **isin** (VARCHAR)
  - Issue-grain identifier, REPEATED across every listing row. Not a key on this table.
  - *Concept*: `isin`
- **venue** (VARCHAR)
  - ISO 10383 MIC of the listing venue.
- **px_last** (DECIMAL)
  - Last price. UK equity RICs quote in PENCE while the ISIN-level record is denominated in GBP — a factor of 100.
- **extract_date** (DATE)
  - Column: extract_date
  - *Secondary time dimension*

---

## Relationships (3 connections)

### bloomberg_feed → refinitiv_feed
- **Type**: many_to_many
- **Join**: bloomberg_feed.figi = refinitiv_feed.ric
- **Description**: Cross-vendor listing identifier join.

### bloomberg_feed → refinitiv_feed
- **Type**: many_to_many
- **Join**: bloomberg_feed.isin = refinitiv_feed.ric
- **Description**: Issue identifier joined to a listing identifier.

### bloomberg_feed → refinitiv_feed
- **Type**: many_to_many
- **Join**: bloomberg_feed.isin = refinitiv_feed.isin
- **Description**: The reconciliation join from scene 2.

## Summary
- **Total Tables**: 3
- **Total Columns**: 14
- **Total Relationships**: 3

## Concepts (3 in scope)

Business concepts realized by this schema. The concept id is the authoritative reference; labels may collide (see Disambiguation).

### `figi` — figi
- **Definition**: OpenFIGI identifier. Identifies a listing — one instrument on one venue. A single issue carries many FIGIs by design; the share-class FIGI is the issue-level rollup and is a different concept.
- **Grain**: listing
- **Synonyms**: FIGI, Bloomberg FIGI
- **Realized by**: bloomberg_feed, bloomberg_feed.figi
- **Relation**: distinct from → `isin`

### `isin` — isin
- **Definition**: ISO 6166 International Securities Identification Number. Identifies an issue — one security as issued — irrespective of where it trades. ANNA and its national numbering agencies are authoritative for existence.
- **Grain**: issue
- **Synonyms**: ISIN, issue identifier
- **Realized by**: anna_register, anna_register.isin, bloomberg_feed.isin, refinitiv_feed.isin
- **Relation**: distinct from → `figi`
- **Relation**: distinct from → `ric`

### `ric` — ric
- **Definition**: Refinitiv Instrument Code. Identifies a listing on one venue, carrying vendor quote conventions — notably that UK equity RICs quote in pence while the ISIN-level record is denominated in GBP.
- **Grain**: listing
- **Synonyms**: RIC, Reuters code
- **Realized by**: refinitiv_feed, refinitiv_feed.ric
- **Relation**: distinct from → `isin`
