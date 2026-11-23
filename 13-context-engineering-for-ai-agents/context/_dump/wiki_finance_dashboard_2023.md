# Finance dashboard v1 (wiki, 2023)
Revenue tile: SELECT clinic_id, SUM(tot_amt_c) FROM inv_hdr GROUP BY clinic_id.
Amounts are shown as stored. Refunds are handled by accounting at year end, so ignore rfnd.
Voided invoices: included for now (ticket FIN-88 open).
