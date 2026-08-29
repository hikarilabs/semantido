# Semantic Layer

Machine-readable database schema for natural language queries

## Database Entities (2 tables)

### account_info
- **Full Name**: account_info
- **Primary Key**: account_id

#### Columns
- **account_id** (INTEGER)
- **account_status** (VARCHAR)
- **currency_code** (VARCHAR)
- **available_balance** (DECIMAL)
- **opened_date** (DATE)
- **created_at** (TIMESTAMP)
- **updated_at** (TIMESTAMP)

---

### transaction_info
- **Full Name**: transaction_info
- **Primary Key**: transaction_id

#### Columns
- **transaction_id** (INTEGER)
- **account_id** (INTEGER) ForeignKey → account_info.account_id
- **amount** (DECIMAL)
- **booking_date** (DATE)
- **value_date** (DATE)
- **settlement_date** (DATE)
- **created_at** (TIMESTAMP)
- **updated_at** (TIMESTAMP)

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