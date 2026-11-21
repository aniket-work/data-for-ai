// Cube Core config for the Kestrel Bay Bank semantic layer.
// The security context says who is asking, e.g. { groups: ["regional_manager"], region: "Prairies" }.
// REST and GraphQL: it is the payload of a JWT signed with CUBEJS_API_SECRET.
// SQL API: it comes from the user name you log in with (see roles.json).
const roles = require('./roles.json');

// Balances are month-end snapshots: they add up across accounts, never across months.
const POINT_IN_TIME = ['total_deposits', 'loan_book', 'delinquent_loans', 'delinquency_rate']
  .map((m) => `balance_sheet.${m}`);
const SNAPSHOT = 'balance_sheet.snapshot_date';

function lastMonthOf(range) {
  // ["2026-07-01", "2026-09-30"] -> ["2026-09-01", "2026-09-30"]
  const end = String(range[range.length - 1]).slice(0, 10);
  return [`${end.slice(0, 7)}-01`, end];
}

module.exports = {
  // Map the security context to the groups used by access_policy in the views.
  contextToGroups: ({ securityContext }) => (securityContext && securityContext.groups) || [],

  // SQL API login: one shared demo password, one security context per user name.
  checkSqlAuth: (req, user, password) => {
    const ctx = roles[user];
    if (!ctx) throw new Error('Access denied');
    if (password && password !== process.env.CUBEJS_SQL_PASSWORD) throw new Error('Access denied');
    return { password: process.env.CUBEJS_SQL_PASSWORD, securityContext: ctx };
  },

  // Semi-additive rule, enforced for every API: a point-in-time measure is read at ONE month-end.
  queryRewrite: (query) => {
    if (!(query.measures || []).some((m) => POINT_IN_TIME.includes(m))) return query;
    const td = (query.timeDimensions || []).find((t) => t.dimension === SNAPSHOT);
    if (!td || !td.dateRange) {
      throw new Error('Balances are month-end snapshots: ask for a period (a date range on balance_sheet.snapshot_date).');
    }
    if (td.granularity && td.granularity !== 'month' && td.granularity !== 'day') {
      throw new Error('Balances are month-end snapshots: use granularity "month", or no granularity.');
    }
    const flows = query.measures.filter((m) => m.startsWith('balance_sheet.') && !POINT_IN_TIME.includes(m));
    if (!td.granularity && flows.length) {
      throw new Error(`Ask ${flows.join(', ')} in a separate query: it adds up over months, balances do not.`);
    }
    if (!td.granularity && Array.isArray(td.dateRange)) {
      td.dateRange = lastMonthOf(td.dateRange); // "Q3" -> the September 30 snapshot
    }
    return query;
  },
};
