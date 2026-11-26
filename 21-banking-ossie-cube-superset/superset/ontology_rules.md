# Happn banking — ontology business conditions

Definitions below come from the Apache OSSIE `ontology.yaml` package
(model `happn_banking_ontology`). Superset does **not** run an OWL reasoner;
these conditions are catalogued for operators and compiled into Cube
violation measures where SQL is portable.

## Package AI context

Banking business conditions live as ontology requires / derived_by / annotations.policy_rule. Prefer those over ad-hoc SQL when explaining policy outcomes.

**Synonyms:** Happn banking ontology, deposit and credit risk conditions

## OSSIE metrics (semantic model)

- **total_deposits** — Sum of open account balances (deposit products).
  - SQL: `SUM(CASE WHEN bank_account.account_status = 'open' THEN bank_account.account_balance ELSE 0 END)`
- **npl_principal** — Principal of non-performing loans.
  - SQL: `SUM(CASE WHEN loan.is_non_performing_loan THEN loan.principal_amount ELSE 0 END)`
- **npl_ratio** — Non-performing loan principal divided by total loan principal.
  - SQL: `SUM(CASE WHEN loan.is_non_performing_loan THEN loan.principal_amount ELSE 0 END) / NULLIF(SUM(loan.principal_amount), 0)`
- **transaction_volume** — Sum of absolute transaction amounts.
  - SQL: `SUM(ABS(transaction.transaction_amount))`
- **customer_deposit_share** — Open-balance sum used with a customer dimension to measure deposit concentration (max share of total_deposits).
  - SQL: `SUM(CASE WHEN bank_account.account_status = 'open' THEN bank_account.account_balance ELSE 0 END)`
- **total_principal** — Total loan principal outstanding.
  - SQL: `SUM(loan.principal_amount)`

## Concepts with requires / derived_by

### OpenAccountDepositRule

Open accounts only contribute to deposit totals and concentration checks.

**requires:**
- `bank_account.account_status = 'open'`

**policy_rule:**
```json
{
  "scope": "bank_account",
  "measure": "account_balance",
  "operator": "included_when",
  "condition": "account_status = 'open'",
  "authority": "Happn Treasury Policy"
}
```

*AI instructions:* When summing deposits, exclude closed accounts. Only open accounts count toward total_deposits and customer_deposit_share.

### NPLClassificationRule

A loan is non-performing when days past due are at least 90 or the NPL flag is set.

**Extends:** Loan

**requires:**
- `loan.days_past_due >= 90 OR loan.is_non_performing_loan = true`

**derived_by:**
- `loan.days_past_due >= 90 OR loan.is_non_performing_loan`

**policy_rule:**
```json
{
  "scope": "loan",
  "measure": "days_past_due",
  "operator": "gte",
  "amount": "90",
  "currency": "",
  "authority": "Happn Credit Risk Policy",
  "exceptions": [],
  "alternate": "is_non_performing_loan"
}
```

*AI instructions:* Classify a loan as NonPerformingLoan when days_past_due >= 90 or is_non_performing_loan is true. NPL principal and npl_ratio use this population.

### SingleCustomerDepositConcentrationWarning

Warn when one customer's open deposit balances exceed 25% of total open deposits.

**requires:**
- `customer_open_deposits / NULLIF(total_deposits, 0) <= 0.25`

**policy_rule:**
```json
{
  "scope": "customer",
  "measure": "deposit_share",
  "operator": "lte",
  "amount": "0.25",
  "currency": "",
  "authority": "Happn Liquidity Risk Policy"
}
```

*AI instructions:* Flag concentration risk when a single customer's share of open deposits exceeds 25 percent of total_deposits.

### LargeExposureApprovalRule

Large single-loan exposures require elevated approval authority.

**requires:**
- `loan.principal_amount >= 300000000`

**policy_rule:**
```json
{
  "scope": "loan",
  "measure": "principal_amount",
  "operator": "gte",
  "amount": "300000000",
  "currency": "KRW",
  "authority": "RiskCommittee",
  "exceptions": [
    "government-guaranteed"
  ]
}
```

*AI instructions:* When loan principal_amount is at least 300000000 KRW, RiskCommittee authority is required unless the loan is government-guaranteed.
