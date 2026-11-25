"""Builds the fictional data for Lesson 17: Cedarline Home Insurance, water-damage claims triage.
Everything here is made up. Writes docs_corpus/*.md (the source documents) and data/*.csv (facts already
extracted from those documents, each pointing at the exact document, section and quote it came from)."""
import csv, os, pathlib
H = pathlib.Path(__file__).parent; D = H / "docs_corpus"; DATA = H / "data"
D.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

DOCS = {
"WORD-2025": """# Cedarline Homeowner Policy Wording, 2025 edition
Applies to losses that occur before 2026-06-01.
## 4.1 Escape of water
Sudden and accidental escape of water from a plumbing system or appliance is covered.
## 4.2 Sewer backup
Water that backs up through a sewer, floor drain or sump is EXCLUDED.
## 4.3 Gradual seepage
Continuous or repeated seepage or leakage over 14 days or more is excluded.
""",
"WORD-2026": """# Cedarline Homeowner Policy Wording, 2026 edition
Applies to losses that occur on or after 2026-06-01. Replaces the 2025 edition.
## 4.1 Escape of water
Sudden and accidental escape of water from a plumbing system or appliance is covered.
## 4.2 Sewer backup
Water that backs up through a sewer, floor drain or sump is covered up to $25,000 per occurrence, after a $1,000 deductible.
## 4.3 Gradual seepage
Continuous or repeated seepage or leakage over 14 days or more is excluded.
## 4.4 Policy period
The loss must begin during the policy period. Damage that began before the policy start date is excluded.
""",
"GL-TRIAGE-v2": """# Claims Triage Guideline, version 2
Effective 2026-01-15. Superseded by version 3 on 2026-09-01.
## Routing
FAST_TRACK: covered cause, no conflicting facts, amount up to $25,000.
STANDARD_REVIEW: covered cause, amount over $25,000 and up to $50,000.
SENIOR_REVIEW: amount over $50,000.
""",
"GL-TRIAGE-v3": """# Claims Triage Guideline, version 3
Effective 2026-09-01. Replaces version 2.
## Routing
FAST_TRACK: covered cause, no conflicting facts, amount up to $10,000.
STANDARD_REVIEW: covered cause, no conflicting facts, amount over $10,000 and up to $50,000.
SENIOR_REVIEW: amount over $50,000.
REFER_ADJUSTER: two sources disagree on a material fact (date of loss, cause or amount). Do not auto-decide; send to a human adjuster and name the conflict.
DENY: an excluded cause, confirmed by consistent sources.
""",
"FNOL-2601": "# First notice of loss, claim CLM-2601\nPolicy HP-41207. Caller reports the kitchen sink supply line burst on 2026-09-28 and flooded the kitchen floor. Water shut off within 20 minutes.\n",
"ADJ-2601":  "# Adjuster field report, claim CLM-2601\nInspected 2026-09-30. Cause: sudden failure of braided supply line under the kitchen sink. Date of loss 2026-09-28 confirmed. Damage estimate $7,850.\n",
"FNOL-2602": "# First notice of loss, claim CLM-2602\nPolicy HP-38815. Caller reports water came up through the basement floor drain during the storm on 2026-08-19.\n",
"ADJ-2602":  "# Adjuster field report, claim CLM-2602\nInspected 2026-08-22. Cause: municipal sewer backup through the floor drain. Date of loss 2026-08-19 confirmed. Damage estimate $9,400.\n",
"FNOL-2603": "# First notice of loss, claim CLM-2603\nPolicy HP-52290, policy start date 2026-08-01. Caller reports a leak under the upstairs bathroom vanity, discovered on 2026-08-28.\n",
"INV-2603":  "# Plumber invoice, claim CLM-2603\nRepaired the vanity drain connection. Homeowner said ceiling staining below was first noticed around 2026-07-25. Invoice total $6,300.\n",
"ADJ-2603":  "# Adjuster field report, claim CLM-2603\nInspected 2026-09-02. Cause: leaking vanity drain connection. Damage estimate $6,300.\n",
"FNOL-2604": "# First notice of loss, claim CLM-2604\nPolicy HP-47731. Caller says a pipe under the laundry room floor burst suddenly on 2026-09-14.\n",
"ADJ-2604":  "# Adjuster field report, claim CLM-2604\nInspected 2026-09-17. Subfloor rot and mould consistent with gradual seepage over several months, not a sudden burst. Date of loss reported 2026-09-14. Damage estimate $18,700.\n",
"FNOL-2605": "# First notice of loss, claim CLM-2605\nPolicy HP-50164. Caller reports the dishwasher supply hose split on 2026-10-02 and soaked the kitchen and the basement ceiling below.\n",
"ADJ-2605":  "# Adjuster field report, claim CLM-2605\nInspected 2026-10-05. Cause: sudden split of the dishwasher supply hose. Date of loss 2026-10-02 confirmed. Damage estimate $14,600.\n",
}
for k, v in DOCS.items(): (D / f"{k}.md").write_text(v)

SOURCES = [  # doc_id, kind, credibility (how much we trust this kind of source), valid_from, valid_until
 ("WORD-2025", "policy_wording", 1.0, "2025-01-01", "2026-06-01"), ("WORD-2026", "policy_wording", 1.0, "2026-06-01", ""),
 ("GL-TRIAGE-v2", "guideline", 1.0, "2026-01-15", "2026-09-01"), ("GL-TRIAGE-v3", "guideline", 1.0, "2026-09-01", ""),
] + [(k, {"FNOL": "fnol_call", "ADJ": "adjuster_report", "INV": "contractor_invoice"}[k.split("-")[0]],
      {"FNOL": 0.6, "ADJ": 0.9, "INV": 0.8}[k.split("-")[0]], "", "") for k in DOCS if k.split("-")[0] in ("FNOL", "ADJ", "INV")]
with open(DATA / "sources.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["doc_id", "kind", "credibility", "valid_from", "valid_until"]); w.writerows(SOURCES)

POLICIES = [("HP-41207", "CLM-2601", "2025-11-01"), ("HP-38815", "CLM-2602", "2024-04-01"), ("HP-52290", "CLM-2603", "2026-08-01"),
            ("HP-47731", "CLM-2604", "2023-02-01"), ("HP-50164", "CLM-2605", "2026-01-10")]
with open(DATA / "policies.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["policy_id", "claim_id", "start_date"]); w.writerows(POLICIES)

# Facts extracted from the documents: claim, property, value, source doc, section, exact quote.
F = [
 ("CLM-2601", "date_of_loss", "2026-09-28", "FNOL-2601", "call note", "supply line burst on 2026-09-28"),
 ("CLM-2601", "date_of_loss", "2026-09-28", "ADJ-2601", "field report", "Date of loss 2026-09-28 confirmed"),
 ("CLM-2601", "cause", "sudden_escape", "ADJ-2601", "field report", "sudden failure of braided supply line"),
 ("CLM-2601", "amount", "7850", "ADJ-2601", "field report", "Damage estimate $7,850"),
 ("CLM-2602", "date_of_loss", "2026-08-19", "FNOL-2602", "call note", "during the storm on 2026-08-19"),
 ("CLM-2602", "date_of_loss", "2026-08-19", "ADJ-2602", "field report", "Date of loss 2026-08-19 confirmed"),
 ("CLM-2602", "cause", "sewer_backup", "ADJ-2602", "field report", "municipal sewer backup through the floor drain"),
 ("CLM-2602", "amount", "9400", "ADJ-2602", "field report", "Damage estimate $9,400"),
 ("CLM-2603", "date_of_loss", "2026-08-28", "FNOL-2603", "call note", "discovered on 2026-08-28"),
 ("CLM-2603", "date_of_loss", "2026-07-25", "INV-2603", "invoice note", "first noticed around 2026-07-25"),
 ("CLM-2603", "cause", "sudden_escape", "ADJ-2603", "field report", "leaking vanity drain connection"),
 ("CLM-2603", "amount", "6300", "ADJ-2603", "field report", "Damage estimate $6,300"),
 ("CLM-2604", "date_of_loss", "2026-09-14", "FNOL-2604", "call note", "burst suddenly on 2026-09-14"),
 ("CLM-2604", "cause", "sudden_escape", "FNOL-2604", "call note", "a pipe under the laundry room floor burst suddenly"),
 ("CLM-2604", "cause", "gradual_seepage", "ADJ-2604", "field report", "consistent with gradual seepage over several months"),
 ("CLM-2604", "amount", "18700", "ADJ-2604", "field report", "Damage estimate $18,700"),
 ("CLM-2605", "date_of_loss", "2026-10-02", "FNOL-2605", "call note", "supply hose split on 2026-10-02"),
 ("CLM-2605", "date_of_loss", "2026-10-02", "ADJ-2605", "field report", "Date of loss 2026-10-02 confirmed"),
 ("CLM-2605", "cause", "sudden_escape", "ADJ-2605", "field report", "sudden split of the dishwasher supply hose"),
 ("CLM-2605", "amount", "14600", "ADJ-2605", "field report", "Damage estimate $14,600"),
]
with open(DATA / "facts.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["fact_id", "claim_id", "property", "value", "source_doc", "location", "quote"])
    for i, r in enumerate(F, 1):
        assert r[5] in DOCS[r[3]], r  # every quote really appears in its source document
        w.writerow([f"F{i:02d}", *r])
print(f"wrote {len(DOCS)} documents to docs_corpus/, {len(F)} facts, {len(POLICIES)} claims, {len(SOURCES)} sources to data/")
