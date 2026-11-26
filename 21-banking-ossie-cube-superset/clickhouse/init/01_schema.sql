-- Happn Community Bank physical tables (demo warehouse).
CREATE DATABASE IF NOT EXISTS banking;

CREATE TABLE IF NOT EXISTS banking.branches
(
    branch_id String,
    name String,
    region String,
    city String,
    country String,
    opened_on Date
) ENGINE = MergeTree
ORDER BY branch_id;

CREATE TABLE IF NOT EXISTS banking.customers
(
    customer_id String,
    branch_id String,
    name String,
    segment String,
    since_date Date,
    status String
) ENGINE = MergeTree
ORDER BY customer_id;

CREATE TABLE IF NOT EXISTS banking.accounts
(
    account_id String,
    customer_id String,
    branch_id String,
    product String,
    balance Float64,
    status String,
    opened_on Date
) ENGINE = MergeTree
ORDER BY account_id;

CREATE TABLE IF NOT EXISTS banking.transactions
(
    transaction_id String,
    account_id String,
    booked_at DateTime,
    amount Float64,
    txn_type String,
    memo String
) ENGINE = MergeTree
ORDER BY transaction_id;

CREATE TABLE IF NOT EXISTS banking.loans
(
    loan_id String,
    customer_id String,
    branch_id String,
    principal Float64,
    rate Float64,
    status String,
    days_past_due Int64,
    npl_flag Bool,
    originated_on Date,
    matures_on Date
) ENGINE = MergeTree
ORDER BY loan_id;

CREATE TABLE IF NOT EXISTS banking.risk_ratings
(
    customer_id String,
    as_of Date,
    rating String,
    score Int64
) ENGINE = MergeTree
ORDER BY (customer_id, as_of);
