SELECT
  branch__region
  , CAST(delinquent_loans AS DOUBLE) / CAST(NULLIF(loan_book, 0) AS DOUBLE) AS delinquency_rate
FROM (
  SELECT
    subq_8.branch__region AS branch__region
    , SUM(subq_8.__delinquent_loans) AS delinquent_loans
    , SUM(subq_8.__loan_book) AS loan_book
  FROM (
    SELECT
      subq_4.balance_date__day AS balance_date__day
      , branches_src_10000.region AS branch__region
      , subq_4.__loan_book AS __loan_book
      , subq_4.__delinquent_loans AS __delinquent_loans
    FROM (
      SELECT
        DATE_TRUNC('day', balance_date) AS balance_date__day
        , branch_id AS branch
        , case when product_type = 'loan' then balance end AS __loan_book
        , case when product_type = 'loan' and days_past_due >= 30 then balance end AS __delinquent_loans
      FROM "bank"."main"."fct_monthly_balances" monthly_balances_src_10000
      WHERE DATE_TRUNC('day', balance_date) BETWEEN '2026-10-01' AND '2026-10-31'
    ) subq_4
    LEFT OUTER JOIN
      "bank"."main"."dim_branches" branches_src_10000
    ON
      subq_4.branch = branches_src_10000.branch_id
  ) subq_8
  INNER JOIN (
    SELECT
      MAX(subq_4.balance_date__day) AS balance_date__day__complete
    FROM (
      SELECT
        DATE_TRUNC('day', balance_date) AS balance_date__day
        , branch_id AS branch
      FROM "bank"."main"."fct_monthly_balances" monthly_balances_src_10000
      WHERE DATE_TRUNC('day', balance_date) BETWEEN '2026-10-01' AND '2026-10-31'
    ) subq_4
    LEFT OUTER JOIN
      "bank"."main"."dim_branches" branches_src_10000
    ON
      subq_4.branch = branches_src_10000.branch_id
  ) subq_10
  ON
    subq_8.balance_date__day = subq_10.balance_date__day__complete
  GROUP BY
    subq_8.branch__region
) subq_14
