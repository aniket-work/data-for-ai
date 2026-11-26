"""Writes the fictional Kestrel Bay Bank policy & support knowledge base to kb/*.md.
Every name, number and rule here is invented for teaching. Front matter = metadata for filters."""
import os, textwrap
D = []
def doc(id, title, product, doc_type, audience, region, effective, status, *sections):
    D.append(dict(id=id, title=title, product=product, doc_type=doc_type, audience=audience, region=region,
                  effective=effective, status=status, sections=sections))

doc("KB-101", "Retained debit card at an automated banking machine", "cards", "procedure", "customer", "ALL", "2026-01-15", "current",
 ("When a card is retained", "An automated banking machine (ABM) may retain a debit card after three incorrect PIN entries, when the card has expired, or when the chip cannot be read. Retained cards are never returned to the customer; the machine destroys them during the next cash replenishment."),
 ("What to do", "Contact Kestrel Bay Bank card services on the number on the back of any Kestrel card, or use Card Controls in the mobile app, to block the retained card. A replacement card is issued with a new card number and mailed within 5 to 7 business days. Express replacement to a branch is available in 2 business days at no fee."),
 ("Your access in the meantime", "Mobile and online banking keep working while the replacement is on its way. Cash can be withdrawn at any Kestrel branch with government-issued photo ID."))
doc("KB-102", "Card Controls: temporarily lock and unlock a card", "cards", "faq", "customer", "ALL", "2026-03-01", "current",
 ("What Card Controls does", "Card Controls in the Kestrel mobile app lets a cardholder place a temporary lock on a debit or credit card. A locked card declines new purchases, ABM withdrawals and online payments. Pre-authorized payments such as subscriptions continue."),
 ("Locking versus reporting", "Use a temporary lock if a card is misplaced and may turn up. If a card is confirmed lost or stolen, report it instead: reporting permanently cancels the card number and orders a replacement."),
 ("Unlocking", "Unlocking takes effect immediately. A card can be locked and unlocked any number of times with no fee."))
doc("KB-103", "Unauthorized transactions and the zero liability guarantee", "cards", "policy", "customer", "ALL", "2026-02-01", "current",
 ("Coverage", "Kestrel Bay Bank reimburses cardholders for unauthorized transactions on their debit or credit card under the Zero Liability Guarantee, provided the cardholder protected their PIN and reported the loss or the unauthorized use promptly."),
 ("Reporting window", "Report unauthorized activity within 30 days of the statement date on which it first appears. Disputes are opened through the mobile app (Transactions > Dispute) or by calling card services. Provisional credit is normally applied within 10 business days while the investigation is open."),
 ("Exclusions", "The guarantee does not cover transactions the cardholder authorized, including payments to a merchant that later failed to deliver; those follow the merchant dispute (chargeback) process in KB-118."))
doc("KB-104", "Funds availability and cheque holds", "chequing", "policy", "customer", "ALL", "2026-01-01", "current",
 ("Standard availability", "Cheques deposited at a branch, ABM or by mobile deposit before 8 p.m. Eastern Time on a business day are credited the same day. Kestrel Bay Bank may place a hold on deposited cheques; the first $100 of each deposit is always available immediately."),
 ("Hold periods", "The maximum hold period is 4 business days for cheques up to $1,500 and 5 business days for larger cheques drawn on a Canadian financial institution. Cheques in U.S. dollars or drawn on foreign institutions may be held up to 15 business days."),
 ("Exceptions", "Holds may be extended when an account is less than 90 days old, when a cheque is post-dated or damaged, or when there is reason to suspect fraud. The customer is told the reason and the release date."))
doc("KB-105", "Mobile cheque deposit", "chequing", "faq", "customer", "ALL", "2026-01-01", "current",
 ("Limits", "Mobile deposit accepts cheques up to $10,000 each and $25,000 per day per customer. Write 'Deposited by Kestrel mobile' and the date on the back of the cheque before taking the photo."),
 ("Keeping the paper cheque", "Keep the original cheque for 30 days after the deposit, then destroy it securely. Do not deposit the same cheque again at a branch or ABM."))
doc("KB-106", "Non-sufficient funds (NSF) and returned payments", "chequing", "policy", "customer", "ALL", "2026-01-01", "current",
 ("When a payment is returned", "If a cheque, pre-authorized debit or bill payment is presented and the account does not have enough available funds and no overdraft protection, the item is returned unpaid to the payee. This is called a non-sufficient funds (NSF) item."),
 ("Fee", "The NSF fee is listed in fee schedule FS-2026 (fee code NSF-02). Kestrel Bay Bank charges at most one NSF fee per item per business day, even if the payee presents the item again."),
 ("Avoiding returned items", "Customers can add Overdraft Protection (KB-107) or turn on Low Balance Alerts in the mobile app."))
doc("KB-107", "Overdraft Protection", "chequing", "faq", "customer", "ALL", "2026-01-01", "current",
 ("How it works", "Overdraft Protection covers payments up to an approved limit when the chequing balance is not enough. Interest of 21% per year applies to the overdrawn balance, calculated daily."),
 ("Fees", "The monthly Overdraft Protection fee is $5 in any month the account is overdrawn and $0 otherwise. There is no NSF fee for items covered by Overdraft Protection."))
doc("FS-2026", "Personal banking fee schedule 2026", "general", "fee_schedule", "customer", "ALL", "2026-01-01", "current",
 ("Everyday Chequing", "Monthly account fee $14.95, waived with a minimum daily balance of $3,000. Interac e-Transfer: free. Paper statement: $2.50 per month."),
 ("Returned items", "NSF-02 Non-sufficient funds item: $45.00. RPD-01 Returned pre-authorized debit (stop payment by customer): $12.50."),
 ("Wires and drafts", "WIR-OUT International wire transfer sent: $35.00 plus intermediary bank charges. WIR-IN Incoming wire: $15.00. DRF-01 Bank draft: $9.95."))
doc("FS-2025", "Personal banking fee schedule 2025 (superseded)", "general", "fee_schedule", "customer", "ALL", "2025-01-01", "superseded",
 ("Everyday Chequing", "Monthly account fee $13.95, waived with a minimum daily balance of $3,000. Interac e-Transfer: $1.00 per transfer. Paper statement: $2.00 per month."),
 ("Returned items", "NSF-02 Non-sufficient funds item: $48.00. RPD-01 Returned pre-authorized debit (stop payment by customer): $12.50."),
 ("Wires and drafts", "WIR-OUT International wire transfer sent: $30.00 plus intermediary bank charges. WIR-IN Incoming wire: $15.00. DRF-01 Bank draft: $8.95."))
doc("KB-108", "Sending an international wire transfer", "chequing", "procedure", "customer", "ALL", "2026-02-15", "current",
 ("What you need", "To send money to a bank account outside Canada you need the recipient's full name and address, the receiving bank's SWIFT/BIC code, and the account number or IBAN. Some countries also require a purpose-of-payment code."),
 ("Limits and timing", "Wires up to $10,000 per day can be sent in online banking. Larger wires must be requested at a branch using form KB-114. Most wires arrive within 1 to 3 business days; intermediary banks may deduct their own charges."),
 ("Fees and exchange", "The outgoing wire fee is fee code WIR-OUT in fee schedule FS-2026. Foreign exchange is converted at Kestrel's posted rate at the time the wire is sent."))
doc("KB-109", "Interac e-Transfer limits and Autodeposit", "chequing", "faq", "customer", "ALL", "2026-01-01", "current",
 ("Limits", "Customers can send up to $3,000 per transfer and $10,000 per rolling 7 days by Interac e-Transfer. Limits for Small Business accounts are set in the business banking agreement."),
 ("Autodeposit", "With Autodeposit registered, incoming e-Transfers to your email address or mobile number are deposited automatically with no security question."),
 ("Recalling a transfer", "A pending e-Transfer that the recipient has not yet accepted can be cancelled in the app; the funds return within 30 minutes."))
doc("KB-110", "High-Interest Savings account terms", "savings", "policy", "customer", "ALL", "2026-04-01", "current",
 ("Interest", "The High-Interest Savings account earns interest calculated on the daily closing balance and paid monthly. The current posted rate is 3.00% per year; rates can change at any time without notice."),
 ("Withdrawals", "Two self-serve withdrawals per month are free; each additional withdrawal costs $5. Transfers between your own Kestrel accounts in the app count as withdrawals."))
doc("KB-111", "1-Year GIC: early redemption and renewal", "gic", "policy", "customer", "ALL", "2026-03-01", "current",
 ("Product", "The 1-Year GIC (product code GIC-1Y) pays a fixed 4.25% per year at maturity. Minimum investment $500."),
 ("Early redemption", "The 1-Year GIC is non-redeemable. In cases of death or documented financial hardship, the bank may allow early redemption with interest reduced to 0.50% per year for the time held."),
 ("Renewal", "At maturity the GIC renews automatically for another one-year term at the posted rate unless the customer gives instructions within 10 days after maturity."))
doc("KB-112", "Fixed Mortgage prepayment privileges", "mortgage", "policy", "customer", "ALL", "2026-01-01", "current",
 ("Annual lump sum", "Each calendar year, a Fixed Mortgage borrower may prepay up to 15% of the original principal as a lump sum without a prepayment charge. Unused privilege does not carry forward."),
 ("Payment increase", "Regular payments can be increased once per calendar year by up to 15% of the current payment amount."),
 ("Prepayment charge", "Paying more than the privilege, or paying off the mortgage before the end of the term, triggers a prepayment charge equal to the greater of three months' interest or the interest rate differential (IRD)."))
doc("KB-113", "Mortgage payment deferral and financial hardship", "mortgage", "policy", "customer", "ALL", "2026-02-01", "current",
 ("Who qualifies", "Borrowers facing financial hardship, such as job loss, serious illness, or the death of a co-borrower, can ask the Financial Care team for help. Options include a payment deferral of up to 4 months, a temporary interest-only period, or extending the amortization."),
 ("What a deferral means", "During a deferral, interest continues to accrue and is added to the mortgage balance. A deferral is not payment forgiveness."),
 ("How to ask", "Contact the Financial Care team before missing a payment. Kestrel Bay Bank reviews each request individually and may ask for proof of income change."))
doc("KB-113P", "Prairies wildfire relief for mortgage and loan customers", "mortgage", "policy", "customer", "Prairies", "2026-06-15", "current",
 ("Eligibility", "Customers whose primary residence is in Alberta, Saskatchewan or Manitoba and who were ordered to evacuate, or whose home was damaged by a wildfire in 2026, are eligible for Prairies Wildfire Relief."),
 ("Relief offered", "Mortgage and Personal Loan payments can be skipped for up to 6 months with no late fees, and Kestrel waives the interest on skipped payments for the first 3 months. NSF fees are also refunded for the affected period."),
 ("How to apply", "Apply through the Calgary, Winnipeg or Saskatoon branches, or the Financial Care team. Provide the evacuation order or an insurance claim number."))
doc("KB-113A", "Atlantic storm relief for mortgage customers", "mortgage", "policy", "customer", "Atlantic", "2026-09-20", "current",
 ("Eligibility", "Customers in Nova Scotia, New Brunswick, Prince Edward Island and Newfoundland and Labrador whose home was damaged by a named hurricane or post-tropical storm in 2026 are eligible for Atlantic Storm Relief."),
 ("Relief offered", "Mortgage payments can be deferred for up to 3 months with no late fees. Interest continues to accrue. Kestrel also offers a repair line of credit at prime rate for up to 12 months."),
 ("How to apply", "Apply at the Halifax or Moncton branches or through the Financial Care team with an insurance claim number."))
doc("KB-114", "Branch wire request form KB-114", "chequing", "procedure", "customer", "ALL", "2026-02-15", "current",
 ("Purpose", "Form KB-114 is used for wire transfers above the online daily limit of $10,000, and for wires to countries that require additional documentation."),
 ("Completing the form", "Bring photo ID and the recipient details. A branch officer verifies the request by calling the customer back on the phone number on file before the wire is released."))
doc("KB-115", "Personal Loan: missed payments and collections", "personal_loan", "policy", "customer", "ALL", "2026-01-01", "current",
 ("Late payments", "A Personal Loan payment not received within 10 days of the due date is late. A $25 late fee applies and the missed payment may be reported to the credit bureaus after 30 days."),
 ("Getting help", "Customers who expect to miss a payment should contact the Financial Care team. Options include moving the payment date or a short-term reduced payment plan."))
doc("KB-116", "Business Line of Credit annual review", "line_of_credit", "policy", "customer", "ALL", "2026-01-01", "current",
 ("Annual review", "Each Business Line of Credit is reviewed every 12 months. The business must provide year-end financial statements within 120 days of its fiscal year end."),
 ("Covenants", "Lines above $250,000 carry a debt service coverage covenant of at least 1.25 times. A missed covenant may lead to a reduced limit or a higher rate."))
doc("KB-117", "Updating your address and moving between provinces", "general", "faq", "customer", "ALL", "2026-01-01", "current",
 ("Changing your address", "Update your mailing and residential address in the mobile app under Profile, or at any branch. Address changes apply to all your accounts and cards."),
 ("Moving to another province", "Accounts stay open when you move within Canada. Your home branch can be changed to the nearest Kestrel branch. Mortgages remain on the same terms; if the property is sold, the prepayment rules in KB-112 apply."))
doc("KB-118", "Merchant disputes and chargebacks", "cards", "procedure", "customer", "ALL", "2026-01-01", "current",
 ("When to use", "If you paid a merchant with your Kestrel credit card and the goods were never delivered, were not as described, or you were charged twice, you can ask Kestrel to start a chargeback after first trying to resolve it with the merchant."),
 ("Time limits", "Chargeback requests must be made within 120 days of the transaction date. Kestrel may ask for receipts, emails or tracking information."))
doc("KB-119", "Phishing, scam calls and protecting your account", "digital", "faq", "customer", "ALL", "2026-05-01", "current",
 ("What Kestrel will never ask", "Kestrel Bay Bank will never ask for your password, full PIN or a one-time passcode by phone, text or email. Never share a one-time passcode with anyone, even if the caller says they are from the bank."),
 ("If you shared information", "Change your online banking password immediately, lock your cards in Card Controls (KB-102), and call card services. Report suspicious messages using Report Fraud in the app."))
doc("KB-120", "Two-step verification and new device sign-in", "digital", "faq", "customer", "ALL", "2026-05-01", "current",
 ("How it works", "When you sign in to online banking from a new device, Kestrel sends a one-time passcode to the mobile number on file. Codes expire after 10 minutes."),
 ("Changing your phone number", "If you changed your mobile number and cannot receive codes, visit a branch with photo ID or call the digital support line; the number cannot be changed in an unverified session."))
doc("KB-121", "Account closure and dormant accounts", "general", "policy", "customer", "ALL", "2026-01-01", "current",
 ("Closing an account", "Accounts can be closed at a branch or by secure message. Any balance is paid by bank draft or transfer. Accounts closed within 90 days of opening have a $20 early closure fee."),
 ("Dormant accounts", "An account with no customer-initiated activity for 2 years is dormant. Kestrel sends notices at 2, 5 and 9 years. After 10 years of inactivity, unclaimed balances are transferred to the Bank of Canada."))
doc("KB-122", "Joint accounts and survivorship", "chequing", "faq", "customer", "ALL", "2026-01-01", "current",
 ("Ownership", "A joint account is owned by two or more people. Each owner can make deposits and withdrawals unless the account requires all signatures."),
 ("When an owner dies", "For joint accounts with right of survivorship, the funds pass to the surviving owner. The bank needs a death certificate to update the account. Estates are handled by the Estate Services team."))
doc("KB-123", "Power of attorney on Kestrel accounts", "general", "procedure", "customer", "ALL", "2026-01-01", "current",
 ("Registering a POA", "An attorney named in a valid power of attorney document can act on the grantor's accounts once the document has been reviewed by Kestrel's Legal Services team. Review normally takes 5 business days."),
 ("Limits", "The attorney cannot change beneficiaries or add themselves as a joint owner."))
doc("KB-124", "Accessibility services", "general", "faq", "customer", "ALL", "2026-01-01", "current",
 ("Formats", "Statements and documents are available in large print, braille and audio. Ask at any branch or through secure message."),
 ("Branch support", "All Kestrel branches have step-free access. Customers can bring a support person or service animal."))
doc("KB-125", "Safety deposit boxes", "general", "faq", "customer", "Central", "2026-01-01", "current",
 ("Availability", "Safety deposit boxes are offered at the Toronto King West, Ottawa Glebe and Montreal Plateau branches only. Annual rent starts at $65 for a small box."),
 ("Access", "Box holders can access the box during branch hours with photo ID. Kestrel does not insure the contents."))
doc("KB-126", "Foreign currency cash orders", "general", "faq", "customer", "Pacific", "2026-01-01", "current",
 ("Ordering currency", "U.S. dollars are available same day at the Vancouver Gastown and Victoria Harbour branches. Other currencies can be ordered for pickup in 2 business days. Orders above $2,500 must be placed in advance."))
doc("ST-201", "Staff: identity verification for card replacement", "cards", "procedure", "staff", "ALL", "2026-01-15", "current",
 ("Verification steps", "Before ordering a replacement card by phone, staff must verify the caller with two factors: a one-time code sent to the phone on file, plus one knowledge question. Never read the address on file aloud; ask the caller to state it."),
 ("Escalation", "If verification fails twice, place a 24-hour fraud hold on the profile and transfer the call to Fraud Operations."))
doc("ST-202", "Staff: fee reversal authority", "general", "procedure", "staff", "ALL", "2026-01-01", "current",
 ("Limits", "Front-line staff can reverse up to two NSF fees per customer per calendar year without approval. Branch managers can reverse up to $250 in fees per customer per year. Larger reversals need regional approval."),
 ("Documentation", "Every reversal must include a reason code in the customer profile."))
doc("ST-203", "Staff: handling a hardship call", "mortgage", "procedure", "staff", "ALL", "2026-02-01", "current",
 ("Script", "Acknowledge the situation, do not promise an outcome, and book a Financial Care appointment within 2 business days. Record the hardship reason code in the profile."),
 ("Regional programs", "Check for active regional relief programs (for example KB-113P or KB-113A) before offering the standard deferral in KB-113."))

doc("AGR-01", "Kestrel Bay Bank personal account agreement", "general", "policy", "customer", "ALL", "2026-01-01", "current",
 ("1. About this agreement", "This agreement applies to every personal deposit account you hold with Kestrel Bay Bank, including Everyday Chequing and High-Interest Savings, together with the account disclosures, the fee schedule and any program terms we give you. In this agreement 'you' means each account holder and 'we' means Kestrel Bay Bank. If this agreement conflicts with a program term, the program term applies to that program only. Please read it together with the current personal banking fee schedule, which forms part of it, and keep a copy for your records."),
 ("2. Opening and identification", "To open an account we must verify your identity using government-issued photo identification or other methods allowed by law. We may refuse to open an account, or may restrict it, if we cannot verify your identity, if the account would be used for an unlawful purpose, or if you have given us false information. You must tell us promptly if your name, address, phone number, email address, citizenship or tax residency changes, so that our records stay accurate."),
 ("3. Deposits", "You can make deposits at a branch, at an automated banking machine, by mobile deposit, or by electronic transfer. Every deposit is subject to verification and to our funds availability rules. If an item you deposit is later returned unpaid, for any reason, we will debit its amount from your account, together with any fee shown in the fee schedule, even if you have already used the funds."),
 ("4. Withdrawals and payments", "You may withdraw available funds by any channel we offer, subject to daily limits. We may refuse a withdrawal or payment if the account does not have enough available funds, if the instruction is incomplete or unclear, or if we suspect fraud or unauthorized use. We are not required to make a payment that would overdraw the account unless you have overdraft protection."),
 ("5. Statements and errors", "We provide a statement each month, or a passbook update, for each account. You must review every statement and tell us about any error, omission or unauthorized entry within 60 days of the statement date. After those 60 days, the statement is considered correct and final, except for amounts improperly credited to you, which we may always reverse."),
 ("6. Interest", "Interest on interest-bearing accounts is calculated daily on the closing balance and paid monthly at the rate we post. We can change posted rates at any time. Accounts with a negative balance do not earn interest, and interest on overdrawn balances is charged as set out in the overdraft protection terms."),
 ("7. Changes to fees and to this agreement", "We may change this agreement or any fee. We will give you at least 30 days' written notice before a new fee or a fee increase takes effect, by statement message, by notice in our branches and online, or by email. If you do not accept a change, you may close the account without paying any closure fee within 30 days after the change takes effect."),
 ("8. Right of set-off", "If you owe us money that is due and unpaid on any loan, line of credit, mortgage or credit card, we may use money in any of your deposit accounts, including joint accounts, to pay that debt, without prior notice to you. This is called the right of set-off. We will tell you after we have done so."),
 ("9. Dormant and unclaimed balances", "If there is no customer-initiated activity on an account for two years, the account becomes dormant, and dormant account notices are sent as described in our dormant account policy. Balances that remain unclaimed for ten years are transferred to the Bank of Canada as required by law."),
 ("10. Closing your account", "You can close your account at any time. We can close your account by giving you 30 days' notice. We may close it immediately and without prior notice if you have been abusive to our staff, if we suspect fraud, or if keeping it open would break the law or expose us to legal or reputational risk."),
 ("11. Complaints", "If you have a complaint, contact your branch or the customer care centre first. If you are not satisfied, escalate it to the Kestrel Bay Bank Office of the Ombudsman. If your complaint is not resolved within 56 days, or you are not satisfied with our final answer, you may take it to the independent external complaints body approved for our bank, at no cost to you."),
 ("12. Privacy", "We collect, use and disclose your personal information as described in the Kestrel Bay Bank privacy code. We do not sell your personal information. You can withdraw consent for marketing at any time, but not for uses required to operate your account or required by law."),
 ("13. Our liability", "We are responsible for direct losses caused by our gross negligence or wilful misconduct. We are not liable for indirect losses, or for losses caused by events beyond our reasonable control, such as power failures, natural disasters or the failure of a payment network."),
 ("14. Electronic communications", "You agree that we may send you notices, statements and disclosures electronically, through online banking or to the email address you gave us. Electronic notices have the same effect as paper notices. You can ask for paper copies, and paper statement fees in the fee schedule may apply."),
 ("15. Governing law", "This agreement is governed by the laws of the province or territory in Canada where your home branch is located, and by the federal laws of Canada that apply there. If you move, your home branch, and so the governing law, changes only when we update your home branch at your request."))

def write(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for d in D:
        fm = "\n".join(f"{k}: {d[k]}" for k in ("id", "title", "product", "doc_type", "audience", "region", "effective", "status"))
        body = "\n\n".join(f"## {h}\n\n" + textwrap.fill(t, 100) for h, t in d["sections"])
        open(os.path.join(out_dir, f"{d['id']}.md"), "w").write(f"---\n{fm}\n---\n# {d['title']}\n\n{body}\n")
    print(f"wrote {len(D)} documents to {out_dir}")

if __name__ == "__main__":
    write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kb"))
