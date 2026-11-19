"""One business, four forms: taxonomy, ontology, knowledge graph and semantic layer.
The same fictional bike-share ("Harbourline Bikes") modeled four ways, then asked the same questions.
Everything in this file is OUR OWN TEACHING CODE (rdflib + owlrl + DuckDB), not a product feature.

  python four_forms.py taxonomy            # SKOS terms, synonyms, hierarchy
  python four_forms.py ontology            # OWL classes, properties, cardinality, rules
  python four_forms.py kg [--inject-bad-trip]   # ontology + instance data + inference + checks
  python four_forms.py query               # multi-hop SPARQL over the knowledge graph
  python four_forms.py semantic            # governed metric compiled to SQL on DuckDB
  python four_forms.py homes [ebike active-rider empty-risk]
  python four_forms.py ask [1 2 3 4]       # the same questions to all four forms
  python four_forms.py scorecard
"""
import csv, os, sys, time, pathlib, datetime as dt
import duckdb, owlrl
from rdflib import Graph, Namespace, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.syntax import Syntax
from rich.panel import Panel
from rich import box
import semantic_compiler as SC

HERE = pathlib.Path(__file__).parent; DATA = HERE / "data"; OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
BS = Namespace("https://example.org/harbourline/ontology#"); TX = Namespace("https://example.org/harbourline/taxonomy#")
AS_OF = dt.datetime(2026, 6, 30, 18, 0)
con = Console(width=int(os.environ.get("DEMO_WIDTH", 120)), highlight=False)
YES, PART, NO = "[bold green]✔ answers[/]", "[bold yellow]~ partly[/]", "[bold red]✘ can't[/]"
FORM_COL = {"Taxonomy": "cyan", "Ontology": "magenta", "Knowledge graph": "bright_blue", "Semantic layer": "green"}

def rows(name): return list(csv.DictReader(open(DATA / name)))
def short(u): return str(u).split("#")[-1]
def title(text, color="cyan"): con.print(f"\n[bold {color}]▌ {text}[/]")

# ------------------------------------------------------------------ form 1: taxonomy
def load_taxonomy():
    g = Graph(); g.parse(HERE / "taxonomy" / "bikeshare_taxonomy.ttl"); return g
def label(g, c): return str(g.value(c, SKOS.prefLabel))
def find_term(g, text):
    text = text.lower()
    for c in g.subjects(RDF.type, SKOS.Concept):
        if text in [str(l).lower() for l in list(g.objects(c, SKOS.prefLabel)) + list(g.objects(c, SKOS.altLabel))]: return c
def broader_chain(g, c):
    out = []
    while (c := g.value(c, SKOS.broader)) is not None: out.append(c)
    return out

def cmd_taxonomy():
    g = load_taxonomy()
    title("Form 1 · Taxonomy (SKOS): terms, synonyms, broader / narrower", "cyan")
    con.print(f"  loaded {len(g)} triples, {len(set(g.subjects(RDF.type, SKOS.Concept)))} concepts")
    tree = Tree("[bold]Harbourline Bikes vocabulary[/]")
    def add(node, c):
        alts = sorted(str(a) for a in g.objects(c, SKOS.altLabel))
        br = node.add(f"[bold cyan]{label(g, c)}[/]" + (f"  [dim]aka {', '.join(alts)}[/]" if alts else ""))
        for n in sorted(g.subjects(SKOS.broader, c), key=lambda x: label(g, x)): add(br, n)
    for top in sorted(g.objects(TX.scheme, SKOS.hasTopConcept), key=lambda x: label(g, x)): add(tree, top)
    con.print(tree)
    c = find_term(g, "electric bike")
    con.print(f"  lookup [yellow]\"electric bike\"[/] → [bold cyan]{label(g, c)}[/] → " + " → ".join(label(g, b) for b in broader_chain(g, c)))
    con.print("  [dim]A taxonomy knows names and is-a. It has no relationships, rules or data.[/]")

# ------------------------------------------------------------------ form 2: ontology
def load_ontology():
    g = Graph(); g.parse(HERE / "ontology" / "bikeshare_ontology.ttl"); return g
def restrictions(g):
    out = []
    for cls, r in g.subject_objects(RDFS.subClassOf):
        if (r, RDF.type, OWL.Restriction) in g:
            out.append((short(cls), short(g.value(r, OWL.onProperty)), int(g.value(r, OWL.qualifiedCardinality)), short(g.value(r, OWL.onClass))))
    return sorted(out)

def cmd_ontology():
    g = load_ontology()
    title("Form 2 · Ontology (OWL): classes, properties, cardinality, rules", "magenta")
    t = Table(box=box.SIMPLE_HEAD, header_style="bold magenta", pad_edge=False)
    for c in ["Class", "Subclass of", "Disjoint with"]: t.add_column(c)
    for c in sorted(g.subjects(RDF.type, OWL.Class), key=short):
        if isinstance(c, type(BS.x)) and str(c).startswith(str(BS)):
            t.add_row(short(c), ", ".join(short(p) for p in g.objects(c, RDFS.subClassOf) if str(p).startswith(str(BS))) or "-",
                      ", ".join(short(d) for d in g.objects(c, OWL.disjointWith)) or "-")
    p = Table(box=box.SIMPLE_HEAD, header_style="bold magenta", pad_edge=False)
    for c in ["Relationship", "From", "To"]: p.add_column(c)
    for prop in sorted(g.subjects(RDF.type, OWL.ObjectProperty), key=short):
        d, r = g.value(prop, RDFS.domain), g.value(prop, RDFS.range)
        if d: p.add_row(short(prop), short(d), short(r))
    grid = Table.grid(padding=(0, 6)); grid.add_row(t, p); con.print(grid)
    for cls, prop, n, on in restrictions(g):
        con.print(f"  [bold]cardinality[/]  every [magenta]{cls}[/] {prop} [bold]exactly {n}[/] [magenta]{on}[/]")
    for cls in (BS.ActiveRider, BS.EmptyRiskStation):
        con.print(f"  [bold]rule[/]         [magenta]{short(cls)}[/]: {g.value(cls, BS.rule)}")
    n = len(set(g.subjects(RDF.type, BS.Trip)))
    con.print(f"  [dim]instances in the ontology: {n} trips, 0 riders, 0 bikes. It defines the world; it holds no data.[/]")

# ------------------------------------------------------------------ form 3: knowledge graph
def instance_graph():
    g = Graph(); g.bind("bs", BS)
    for s in rows("stations.csv"):
        st = BS[s["station_id"]]; g.add((st, RDF.type, BS.DockStation)); g.add((st, BS.name, Literal(s["name"])))
        g.add((st, BS.availableBikes, Literal(int(s["available_bikes"])))); g.add((st, BS.capacity, Literal(int(s["capacity"]))))
    for b in rows("bikes.csv"): g.add((BS[b["bike_id"]], RDF.type, BS.EBike if b["bike_type"] == "ebike" else BS.ClassicBike))
    for m in rows("memberships.csv"):
        g.add((BS[m["rider_id"]], RDF.type, BS.Rider))
        g.add((BS[m["membership_id"]], RDF.type, BS.AnnualMembership if m["membership_type"] == "annual" else BS.CasualMembership))
        g.add((BS[m["rider_id"]], BS.hasMembership, BS[m["membership_id"]]))
    for t in rows("trips.csv"):
        tr = BS[t["trip_id"]]; g.add((tr, RDF.type, BS.Trip)); g.add((tr, BS.takenBy, BS[t["rider_id"]]))
        g.add((tr, BS.usesBike, BS[t["bike_id"]])); g.add((tr, BS.startsAt, BS[t["start_station_id"]])); g.add((tr, BS.endsAt, BS[t["end_station_id"]]))
        g.add((tr, BS.startTime, Literal(t["start_ts"] + ":00", datatype=XSD.dateTime)))
        g.add((tr, BS.fareCAD, Literal(t["fare_cad"], datatype=XSD.decimal))); g.add((tr, BS.status, Literal(t["status"])))
    return g

def run_rules(kg):
    added = {}
    for f in sorted((HERE / "kg" / "rules").glob("*.rq")):
        days = int(kg.value(BS.ActiveRider, BS.windowDays))
        cutoff = Literal((AS_OF - dt.timedelta(days=days)).isoformat(), datatype=XSD.dateTime)
        res = kg.query(f.read_text(), initBindings={"cutoff": cutoff})
        new = [tr for tr in res if tr not in kg]
        for tr in new: kg.add(tr)
        added[f.stem] = len(new)
    return added

def build_kg(verbose=False, inject=False):
    t0 = time.time(); onto = load_ontology(); inst = instance_graph()
    if inject: inst.add((BS["TR-0042"], BS.usesBike, BS["B-007"]))     # a bad record from a dock sync glitch
    kg = onto + inst; n0 = len(kg)
    # RDFS inference with owlrl over the class and relationship triples (literal values are set aside so the
    # reasoner does not add re-typed copies of numbers such as "7"^^integer next to "7.0"^^decimal)
    lits = Graph(); [lits.add(t) for t in kg if isinstance(t[2], Literal)]
    kg = kg - lits
    owlrl.DeductiveClosure(owlrl.RDFS_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(kg)
    kg = kg + lits; n1 = len(kg); added = run_rules(kg); n2 = len(kg)
    if verbose:
        title("Form 3 · Knowledge graph: ontology + instance data + inference", "bright_blue")
        con.print(f"  ontology {len(onto):>6,} triples   +  instance data {len(inst):>6,} triples (8 stations, 42 bikes, 60 riders, 1,200 trips)")
        con.print(f"  RDFS inference (owlrl)   {n0:>6,} → {n1:>6,} triples   e.g. every EBike is now also a [bold]Bike[/]")
        for k, v in added.items(): con.print(f"  rule [bright_blue]{k:<20}[/] +{v} facts")
        con.print(f"  ActiveRider: {len(set(kg.subjects(RDF.type, BS.ActiveRider)))} riders   "
                  f"EmptyRiskStation: " + ", ".join(f"{kg.value(s, BS.name)} ({kg.value(s, BS.availableBikes)} left)" for s in sorted(kg.subjects(RDF.type, BS.EmptyRiskStation))))
    bad = list(kg.query((HERE / "kg" / "queries" / "one_bike_per_trip.rq").read_text()))
    if verbose:
        if bad: [con.print(f"  [bold red]✘ violation[/]  {short(r[0])} uses {r[1]} bikes, but the ontology says exactly 1") for r in bad]
        else: con.print(f"  [bold green]✔ check[/]  every trip uses exactly one bike  [dim](closed-world SPARQL check, our own)[/]")
        kg.serialize(OUT / "knowledge_graph.ttl", format="turtle")
        con.print(f"  saved out/knowledge_graph.ttl  ({len(kg):,} triples, {time.time() - t0:.1f}s)")
    return kg, bad

def q3_kg(kg):
    since = Literal((AS_OF - dt.timedelta(days=7)).isoformat(), datatype=XSD.dateTime)
    q = (HERE / "kg" / "queries" / "q3_annual_ebike_empty_risk.rq").read_text()
    return [(str(r[0]), int(r[1]), str(r[2]).split()) for r in kg.query(q, initBindings={"since": since})]

def cmd_query():
    kg, _ = build_kg()
    title("Knowledge graph · multi-hop SPARQL", "bright_blue")
    q = "\n".join(l for l in (HERE / "kg" / "queries" / "q3_annual_ebike_empty_risk.rq").read_text().splitlines() if not l.startswith("#"))
    con.print(Syntax(q.strip(), "sparql", theme="monokai", background_color="default"))
    res = q3_kg(kg); t = Table(box=box.SIMPLE_HEAD, header_style="bold bright_blue", pad_edge=False)
    for c in ["Empty-risk station", "Annual riders, e-bike, this week", "Rider IDs"]: t.add_column(c)
    for st, n, ids in res: t.add_row(st, str(n), " ".join(sorted(ids)))
    con.print(t)
    con.print(f"  [dim]4 hops: Rider → Membership, Trip → Rider, Trip → Bike, Trip → Station. EBike, AnnualMembership and EmptyRiskStation come from the model.[/]")

# ------------------------------------------------------------------ form 4: semantic layer
def duck(): return duckdb.connect(str(HERE / "bikeshare.duckdb"), read_only=True)
def cmd_semantic():
    m = SC.load(); db = duck()
    title("Form 4 · Semantic layer: governed metric → SQL → DuckDB", "green")
    d = m["metrics"]["avg_trip_revenue"]
    con.print(f"  metric [bold green]avg_trip_revenue[/] = {d['expr']}   [dim]({d['description']} certified)[/]")
    sql = SC.compile_query(m, "avg_trip_revenue", ["station"])
    con.print(Syntax(sql, "sql", theme="monokai", background_color="default", word_wrap=True))
    res = db.execute(sql).fetchall()
    t = Table(box=box.SIMPLE_HEAD, header_style="bold green", pad_edge=False)
    t.add_column("Station"); t.add_column("Avg trip revenue (CAD)", justify="right")
    for st, v in res: t.add_row(st, f"${v:.2f}")
    adhoc = dict(db.execute("SELECT s.name, ROUND(AVG(t.fare_cad), 2) FROM trips t JOIN stations s ON t.start_station_id = s.station_id GROUP BY 1").fetchall())
    a = Table(box=box.SIMPLE_HEAD, header_style="bold green", pad_edge=False)
    for c in ["Asked from", "Market Square", "Same?"]: a.add_column(c)
    gov = dict(res)["Market Square"]
    for who in ["dashboard", "notebook", "AI agent"]:
        v = dict(db.execute(SC.compile_query(m, "avg_trip_revenue", ["station"])).fetchall())["Market Square"]
        a.add_row(f"{who} → metric", f"${v:.2f}", "[bold green]✔ same[/]" if v == gov else "[bold red]✘ different[/]")
    a.add_row("hand-written AVG(fare)", f"${adhoc['Market Square']:.2f}", "[bold red]✘ different[/] [dim](counts cancelled trips)[/]")
    grid = Table.grid(padding=(0, 6)); grid.add_row(t, a); con.print(grid)

# ------------------------------------------------------------------ the same concept, four homes
HOMES = {
 "ebike": ("E-bike", [
   ("Taxonomy", "a skos:Concept", 'tx:EBike  prefLabel "E-bike", altLabel "electric bike", broader tx:Bike'),
   ("Ontology", "an owl:Class", "bs:EBike  subClassOf bs:Bike, disjointWith bs:ClassicBike"),
   ("Knowledge graph", "a class node + typed instances", "bs:B-003 a bs:EBike   (inferred: a bs:Bike) … {n} e-bikes"),
   ("Semantic layer", "a column value", "bikes.bike_type = 'ebike'  → dimension bike_type")]),
 "active-rider": ("Active rider", [
   ("Taxonomy", "a term with a text definition", 'tx:ActiveRider  definition "A rider who rides regularly."'),
   ("Ontology", "a class + its rule", 'bs:ActiveRider subClassOf bs:Rider; rule "completed trip in last 30 days"'),
   ("Knowledge graph", "facts inferred by a rule", "kg/rules/active_rider.rq  CONSTRUCT {{ ?r a bs:ActiveRider }}  → {n} riders"),
   ("Semantic layer", "a governed metric", "active_riders = COUNT(DISTINCT rider_id) FILTER (last 30 days) → {m}")]),
 "empty-risk": ("Empty-risk station", [
   ("Taxonomy", "a narrower term", "tx:EmptyRiskStation  broader tx:DockStation"),
   ("Ontology", "a class + threshold", "bs:EmptyRiskStation subClassOf bs:DockStation; threshold 3"),
   ("Knowledge graph", "facts inferred by a rule", "kg/rules/empty_risk_station.rq  availableBikes < 3  → {n} stations"),
   ("Semantic layer", "not modeled", "only a raw column: stations.available_bikes (no rule, no name)")]),
}
def cmd_homes(keys):
    kg, _ = build_kg()
    for key in keys: _homes(kg, key)
def _homes(kg, key):
    name, items = HOMES[key]
    n = {"ebike": len(set(kg.subjects(RDF.type, BS.EBike))), "active-rider": len(set(kg.subjects(RDF.type, BS.ActiveRider))),
         "empty-risk": len(set(kg.subjects(RDF.type, BS.EmptyRiskStation)))}[key]
    mval = duck().execute(SC.compile_query(SC.load(), "active_riders")).fetchone()[0]
    title(f"One concept, four homes: \"{name}\"", "yellow")
    t = Table(box=box.SIMPLE_HEAD, header_style="bold yellow", pad_edge=False)
    for c in ["Form", "Lives as", "What it looks like"]: t.add_column(c)
    for form, kind, look in items:
        t.add_row(f"[bold {FORM_COL[form]}]{form}[/]", kind, look.format(n=n, m=mval))
    con.print(t)

# ------------------------------------------------------------------ the same questions to every form
QUESTIONS = {1: "Is an e-bike a kind of bike?", 2: "Can one trip use two bikes?",
             3: "Which annual members ended an e-bike trip this week at a station that is now empty-risk?",
             4: "Average trip revenue per station, the same number everywhere?"}

def answers():
    tx, onto = load_taxonomy(), load_ontology(); kg, bad = build_kg(); db = duck(); m = SC.load()
    A = {}
    is_kind = TX.Bike in broader_chain(tx, TX.EBike)
    A[1] = [("Taxonomy", YES if is_kind else NO, "E-bike → broader → Bike → Vehicle (skos:broader)"),
            ("Ontology", YES, "EBike subClassOf Bike, and disjoint with ClassicBike"),
            ("Knowledge graph", YES, f"yes, and all {len(set(kg.subjects(RDF.type, BS.EBike)))} e-bikes are inferred to be Bikes"),
            ("Semantic layer", NO, "only sees bike_type = 'ebike', a value with no hierarchy")]
    card = [r for r in restrictions(onto) if r[1] == "usesBike"][0]
    A[2] = [("Taxonomy", NO, "no relationships or constraints, only terms"),
            ("Ontology", YES, f"no: every Trip usesBike exactly {card[2]} Bike (cardinality)"),
            ("Knowledge graph", YES, "no, and checks the data: " + ("0 violations in 1,200 trips" if not bad else f"{len(bad)} violation(s)")),
            ("Semantic layer", NO, "no rule for it; a join would just return two rows")]
    res = q3_kg(kg); kg_ids = sorted({i for _, _, ids in res for i in ids})
    sql = """SELECT DISTINCT t.rider_id FROM trips t JOIN memberships m USING (rider_id) JOIN bikes b USING (bike_id)
             JOIN stations s ON t.end_station_id = s.station_id
             WHERE m.membership_type = 'annual' AND b.bike_type = 'ebike' AND s.available_bikes < 3
               AND t.start_ts >= TIMESTAMP '2026-06-30 18:00' - INTERVAL 7 DAY ORDER BY 1"""
    sql_ids = [r[0] for r in db.execute(sql).fetchall()]
    A[3] = [("Taxonomy", NO, "knows the words, not riders or trips"),
            ("Ontology", NO, "defines the path, but holds no instance data"),
            ("Knowledge graph", YES, f"{len(kg_ids)} riders: {' '.join(kg_ids[:6])}{' …' if len(kg_ids) > 6 else ''}  (4 hops, 1 rule, kinds inferred)"),
            ("Semantic layer", PART, f"{len(sql_ids)} riders, but only with hand-written joins; kinds and the empty-risk rule hard-coded")]
    gov = dict(db.execute(SC.compile_query(m, "avg_trip_revenue", ["station"])).fetchall())
    sp = """PREFIX bs: <https://example.org/harbourline/ontology#>
            SELECT ?n (AVG(?f) AS ?avg) WHERE { ?t bs:startsAt ?s ; bs:fareCAD ?f . ?s bs:name ?n } GROUP BY ?n"""
    kgv = {str(r[0]): float(r[1]) for r in kg.query(sp)}
    A[4] = [("Taxonomy", NO, "no numbers"), ("Ontology", NO, "no data, no metric definitions"),
            ("Knowledge graph", PART, f"SPARQL AVG says ${kgv['Market Square']:.2f} at Market Square; the definition lives in each query"),
            ("Semantic layer", YES, f"certified avg_trip_revenue: ${gov['Market Square']:.2f} at Market Square, in every tool")]
    return A

def cmd_ask(nums):
    A = answers()
    for q in nums:
        title(f"Q{q}. {QUESTIONS[q]}", "yellow")
        t = Table(box=box.SIMPLE_HEAD, show_header=False, pad_edge=False)
        t.add_column(width=17); t.add_column(width=11); t.add_column()
        for form, v, why in A[q]: t.add_row(f"[bold {FORM_COL[form]}]{form}[/]", v, why)
        con.print(t)

def cmd_scorecard():
    A = answers(); sym = {YES: "[bold green]✔[/]", PART: "[bold yellow]~[/]", NO: "[bold red]✘[/]"}
    title("Scorecard · one business, four forms, the same four questions", "yellow")
    t = Table(box=box.ROUNDED, header_style="bold yellow", border_style="grey50")
    t.add_column("Form"); [t.add_column(f"Q{q}", justify="center") for q in QUESTIONS]; t.add_column("Score", justify="right"); t.add_column("Best at")
    best = {"Taxonomy": "shared words, synonyms, is-a", "Ontology": "structure, constraints, rules",
            "Knowledge graph": "connected facts, inference, multi-hop", "Semantic layer": "governed numbers, consistent everywhere"}
    for i, form in enumerate(FORM_COL):
        vs = [A[q][i][1] for q in QUESTIONS]; score = sum(1 if v == YES else 0.5 if v == PART else 0 for v in vs)
        t.add_row(f"[bold {FORM_COL[form]}]{form}[/]", *[sym[v] for v in vs], f"{score:g}/4", best[form])
    con.print(t)
    for q, text in QUESTIONS.items(): con.print(f"  [dim]Q{q}[/] {text}")
    con.print("  [bold]No single form answers everything.[/] Most teams combine them: words → model → graph → metrics.")

if __name__ == "__main__":
    a = sys.argv[1:] or ["scorecard"]; c = a[0]
    if c == "taxonomy": cmd_taxonomy()
    elif c == "ontology": cmd_ontology()
    elif c == "kg": build_kg(verbose=True, inject="--inject-bad-trip" in a)
    elif c == "query": cmd_query()
    elif c == "semantic": cmd_semantic()
    elif c == "homes": cmd_homes(a[1:] or ["ebike"])
    elif c == "ask": cmd_ask([int(x) for x in a[1:]] or list(QUESTIONS))
    elif c == "scorecard": cmd_scorecard()
    else: print(__doc__)
