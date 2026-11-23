# Front desk how-to
To call clients about balances, pull first_nm, last_nm and phone from client and join to pmt.
Balance = SUM(inv_line.ext_amt_c) - SUM(pmt.amt_c) joined on inv_id.
