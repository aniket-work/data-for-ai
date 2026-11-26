"""Synthetic customer-support messages for Kestrel Bay Bank (fictional), used ONLY to benchmark
vector indexes at a size where HNSW matters. Deterministic: seed 13."""
import random, json, os
random.seed(13)
OPEN = ["", "hi, ", "hello, ", "hey there, ", "good morning, ", "quick question: ", "urgent: ", "please help, ", "sorry to bother you, ", "not sure who to ask, "]
CLOSE = ["", " thanks", " thank you!", " please advise", " asap please", " can you call me back?", " this is the second time I'm asking", " appreciate it", " what are my options?"]
CTX = ["", "", "I run a small business and ", "as a senior, ", "for my son's account: ", "I'm a student and ", "my elderly mother asks: ", "I'm travelling right now and ", "new customer here, ", "I've banked with you 20 years and ", "on behalf of my spouse, ", "I'm at the branch in {city} and ", "French is my first language, sorry, ", "I already called once, ", "for our joint account, "]
CITY = ["Halifax", "Moncton", "Toronto", "Ottawa", "Montreal", "Winnipeg", "Calgary", "Saskatoon", "Vancouver", "Victoria"]
MER = ["a gas station", "an online shop", "a grocery store", "a hotel", "an airline", "a coffee shop", "a streaming service", "a pharmacy", "a hardware store", "a ride-share app"]
WHEN = ["yesterday", "this morning", "last night", "on Monday", "over the weekend", "two days ago", "last week", "an hour ago", "on Friday", "earlier today"]
AMT = lambda: f"${random.choice([random.randint(5, 99), random.randint(100, 999), random.randint(1000, 9000)]):,}"
CH = ["the app", "online banking", "the branch", "the ABM", "the phone line", "my laptop", "my new phone", "the website"]
INTENTS = {
 "card_retained": ["the ATM in {city} kept my card {when}", "machine swallowed my debit card at {city}", "my card got stuck in the cash machine {when}", "the ABM didn't give my card back after I typed the wrong PIN"],
 "card_lock": ["can I pause my card, I can't find it", "how do I freeze my credit card in {ch}", "I misplaced my wallet {when}, want to block the card for now", "turn my card off temporarily please"],
 "fraud": ["there's a charge of {amt} from {mer} I never made", "someone used my card at {mer} {when}", "I don't recognize a {amt} payment on my statement", "my account shows purchases I didn't do in {city}"],
 "cheque_hold": ["why is my cheque on hold", "deposited a {amt} cheque {when} and can't use the money", "how long until my cheque clears", "funds from my paycheque are still pending"],
 "mobile_deposit": ["the app won't take a photo of my cheque", "mobile deposit failed for a {amt} cheque", "what's the limit for depositing cheques in {ch}", "do I keep the paper cheque after I deposit it by phone"],
 "nsf": ["I got charged a fee because a payment bounced", "my rent cheque was returned {when}", "why was I charged {amt} for not enough money", "a pre-authorized payment failed and you charged me"],
 "overdraft": ["how does overdraft protection work", "I went into overdraft by {amt}", "can I get an overdraft limit on my chequing", "what is the interest on my overdraft"],
 "wire": ["I need to send {amt} to my brother overseas", "how do I wire money to Europe", "my international transfer hasn't arrived after 3 days", "what's the swift code needed to send money abroad"],
 "etransfer": ["my e-transfer to my landlord didn't go through", "how do I set up autodeposit", "I sent {amt} by e-transfer to the wrong email", "what is the weekly e-transfer limit"],
 "savings": ["what rate does the savings account pay now", "why was I charged for a withdrawal from savings", "how is interest calculated on my savings", "move {amt} from savings to chequing"],
 "gic": ["can I break my GIC early", "what happens when my GIC matures", "what's the rate on a one year GIC", "I want to cash in my term deposit before maturity"],
 "mortgage_prepay": ["can I put a {amt} lump sum on my mortgage", "how much extra can I pay on my mortgage this year", "what's the penalty to pay off my mortgage early", "increase my mortgage payment"],
 "hardship": ["I lost my job and can't pay the mortgage this month", "can I skip a mortgage payment, I'm sick", "need help with my loan payments after my hours were cut", "can I defer payments for a few months"],
 "disaster": ["the wildfire forced us out of our home near {city}", "storm damage to my house in {city}, help with payments", "we were evacuated {when}, what relief is there", "flooding damaged our place, can I pause the mortgage"],
 "loan_late": ["I'm going to be late on my personal loan", "will a late loan payment hurt my credit", "can I change my loan payment date", "I missed my loan payment {when}"],
 "address": ["I'm moving to {city}, how do I change my address", "update my mailing address please", "do I need a new account if I move provinces", "change my home branch to {city}"],
 "chargeback": ["the seller never shipped my order", "I was charged twice by {mer}", "item was broken and the merchant won't refund {amt}", "how do I dispute a credit card purchase"],
 "phishing": ["I got a text saying my account is locked, is it real", "someone called from 'the bank' asking for my code", "I clicked a link in an email and typed my password", "is this email from Kestrel legit"],
 "login": ["I can't log in from my new phone", "not receiving the verification code", "locked out of online banking {when}", "changed my number and now can't sign in"],
 "dormant": ["I found an old account I forgot about", "what happens to an account I don't use", "my account was marked dormant", "can I get money back from an inactive account"],
 "joint": ["my wife passed away, what happens to our joint account", "add my partner to my account", "remove an owner from a joint account", "who can withdraw from a joint account"],
 "poa": ["I have power of attorney for my father", "how do I manage my mom's accounts for her", "register a POA document", "my dad can't do his banking anymore"],
 "fees": ["why did my monthly fee go up", "how do I avoid the chequing account fee", "what is the fee for a bank draft", "how much is a paper statement"],
 "business_loc": ["when is my business line of credit review", "what financial statements do you need for the review", "can my line of credit limit be increased", "covenant breach on our business line"],
 "atm_cash": ["the ATM in {city} didn't give me the cash but took {amt}", "machine was out of money", "deposit at the ATM didn't show up", "ATM charged me a fee {when}"],
 "statement": ["where can I download my statements", "I need a statement for my mortgage application", "switch to paperless statements", "my statement shows the wrong address"],
}
def make(n):
    out = []; keys = list(INTENTS); seen = set()
    while len(out) < n:
        it = random.choice(keys); t = random.choice(INTENTS[it])
        s = (random.choice(OPEN) + random.choice(CTX) + t).format(city=random.choice(CITY), when=random.choice(WHEN), amt=AMT(), mer=random.choice(MER), ch=random.choice(CH)) + random.choice(CLOSE)
        if s in seen: continue
        seen.add(s)
        out.append(dict(id=len(out), intent=it, text=s, region=random.choice(["Atlantic", "Central", "Prairies", "Pacific"])))
    return out
if __name__ == "__main__":
    n = int(os.environ.get("N_TICKETS", 40000)); rows = make(n)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickets.jsonl")
    open(p, "w").write("".join(json.dumps(r) + "\n" for r in rows)); print(f"wrote {len(rows)} tickets, {len(INTENTS)} intents, all texts unique")
