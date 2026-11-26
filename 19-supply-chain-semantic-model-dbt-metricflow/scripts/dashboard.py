"""Build dashboard/index.html from the MetricFlow saved-query exports (exports/*.csv).
Targets come from the contract schedule in docs/. No number on the page is computed outside MetricFlow,
except comparing it with its target."""
import csv, re, sys, webbrowser
from collections import defaultdict
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "exports"; OUT = ROOT / "dashboard"; OUT.mkdir(exist_ok=True)
def rows(name): return list(csv.DictReader(open(EXP / f"{name}.csv")))
def q(ts): return f"Q{(int(ts[5:7]) - 1) // 3 + 1}"
def f(v): return float(v) if v not in ("", None) else None

# contract targets, read from the SLA schedule table
targets = {}
for line in (ROOT / "docs" / "CTR-SLA-SCHEDULE_2026.md").read_text().splitlines():
    m = re.match(r"\|\s*([A-Z][^|]+?)\s*\|\s*CTR-[^|]+\|\s*(\d+)%\s*\|\s*(\d+)%", line)
    if m: targets[m.group(1)] = (int(m.group(2)) / 100, int(m.group(3)) / 100)
STANDARD = (0.90, 0.97)

sla = rows("supplier_sla_scorecard")
qf = rows("supplier_quality_and_freight")
inv = rows("warehouse_inventory_health")
car = rows("carrier_scorecard")
quarters = ["Q1", "Q2", "Q3"]                 # completed quarters (Q4 2026 is still open)
suppliers = sorted({r["supplier__supplier_name"] for r in sla}, key=lambda s: (s not in targets, s))
otd = {(r["supplier__supplier_name"], q(r["metric_time__quarter"])): f(r["on_time_delivery_rate"]) for r in sla}
fill = {(r["supplier__supplier_name"], q(r["metric_time__quarter"])): f(r["fill_rate"]) for r in sla}
fpu = {(r["purchase_order__supplier__supplier_name"], q(r["metric_time__quarter"])): f(r["freight_cost_per_unit"])
       for r in qf if r["metric_time__quarter"]}

NAVY, CARD, GRID, TX, MUT = "#020617", "#0B1222", "#1E293B", "#F1F5F9", "#94A3B8"
MINT, ROSE, AMBER, CYAN = "#34D399", "#FB7185", "#FBBF24", "#22D3EE"
fig = make_subplots(rows=2, cols=2, vertical_spacing=0.16, horizontal_spacing=0.08,
                    subplot_titles=("On-time delivery vs contract target, completed quarters 2026 (red = SLA missed)",
                                    "Pangrove Polymer: freight cost per unit received",
                                    "Month-end stockout rate by warehouse",
                                    "Northline Freight on-time rate vs its 95% target"))
# 1. heat table: OTD by supplier x quarter, coloured by met / missed
z, txt = [], []
for s in suppliers:
    tgt = targets.get(s, STANDARD)[0]; zr, tr = [], []
    for qq in quarters:
        v = otd.get((s, qq))
        zr.append(None if v is None else (1 if v >= tgt else 0)); tr.append("" if v is None else f"{v:.1%}")
    z.append(zr); txt.append(tr)
labels = [f"{s}  ({targets.get(s, STANDARD)[0]:.0%})" for s in suppliers]
fig.add_trace(go.Heatmap(z=z, x=quarters, y=labels, text=txt, texttemplate="%{text}", textfont=dict(size=15, color=TX),
                         colorscale=[[0, "#7F1D1D"], [1, "#064E3B"]], zmin=0, zmax=1, showscale=False, xgap=3, ygap=3,
                         hovertemplate="%{y} %{x}: %{text}<extra></extra>"), 1, 1)
fig.update_yaxes(autorange="reversed", row=1, col=1)
# 2. Pangrove freight per unit
pv = [fpu.get(("Pangrove Polymer Ltd", qq)) for qq in quarters]
fig.add_trace(go.Bar(x=quarters, y=pv, marker_color=[ROSE if qq == "Q3" else CYAN for qq in quarters], showlegend=False,
                     text=[f"${v:.2f}" if v else "" for v in pv], textposition="outside", textfont=dict(color=TX, size=15)), 1, 2)
fig.update_yaxes(range=[0, max(v for v in pv if v) * 1.25], tickprefix="$", row=1, col=2)
# 3. stockouts by warehouse
byw = defaultdict(list)
for r in sorted(inv, key=lambda r: r["metric_time__month"]):
    byw[r["warehouse__warehouse_name"]].append((r["metric_time__month"][:7], f(r["stockout_rate"])))
for (w, pts), c in zip(sorted(byw.items()), [CYAN, AMBER, ROSE, MINT]):
    fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], name=w.replace(" Distribution Center", " DC").replace(" Fulfilment Center", " FC"),
                             mode="lines+markers", line=dict(color=c, width=3 if "Toronto" in w else 1.6)), 2, 1)
fig.update_yaxes(tickformat=".0%", row=2, col=1)
# 4. Northline vs target
nl = sorted((r["metric_time__month"][:7], f(r["carrier_on_time_rate"]), int(r["carrier__contracted_otd_target_pct"]))
            for r in car if r["carrier__carrier_name"] == "Northline Freight")
fig.add_trace(go.Bar(x=[p[0] for p in nl], y=[p[1] for p in nl], marker_color=[ROSE if p[1] < p[2] / 100 else MINT for p in nl],
                     showlegend=False), 2, 2)
fig.add_trace(go.Scatter(x=[p[0] for p in nl], y=[p[2] / 100 for p in nl], mode="lines", line=dict(color=AMBER, dash="dash"),
                         name="contract target", showlegend=False), 2, 2)
fig.update_yaxes(tickformat=".0%", range=[0.5, 1.05], row=2, col=2)
fig.update_layout(template="plotly_dark", paper_bgcolor=NAVY, plot_bgcolor=CARD, height=790, width=1840,
                  font=dict(family="Inter, Arial", color=TX, size=14), margin=dict(l=40, r=30, t=60, b=40),
                  showlegend=True, legend=dict(orientation="h", x=0.0, y=-0.06, bgcolor="rgba(0,0,0,0)"),
                  bargap=0.35)
for a in fig.layout.annotations: a.font = dict(size=17, color=TX)
fig.update_xaxes(gridcolor=GRID); fig.update_yaxes(gridcolor=GRID)

p_q3 = otd[("Pangrove Polymer Ltd", "Q3")]; f_q3 = fill[("Pangrove Polymer Ltd", "Q3")]
tor = dict(byw["Toronto Distribution Center"])
tgt_p = targets["Pangrove Polymer Ltd"]
tiles = [("Pangrove OTD, Q3", f"{p_q3:.1%}", f"target {tgt_p[0]:.0%}", p_q3 < tgt_p[0]),
         ("Pangrove fill rate, Q3", f"{f_q3:.1%}", f"target {tgt_p[1]:.0%}", f_q3 < tgt_p[1]),
         ("Pangrove freight / unit, Q3", f"${fpu[('Pangrove Polymer Ltd','Q3')]:.2f}", f"Q2 ${fpu[('Pangrove Polymer Ltd','Q2')]:.2f}", True),
         ("Toronto DC stockouts, Sep", f"{tor['2026-09']:.1%}", f"Jun {tor['2026-06']:.1%}", True)]
tile_html = "".join(f'<div class="tile {"bad" if bad else "ok"}"><div class="k">{k}</div><div class="v">{v}</div><div class="s">{s}</div></div>'
                    for k, v, s, bad in tiles)
html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Ostrawind supply chain dashboard</title>
<style>body{{margin:0;background:{NAVY};color:{TX};font-family:Inter,Arial,sans-serif}}
header{{padding:22px 40px 6px}} h1{{margin:0;font-size:30px}} .sub{{color:{MUT};font-size:16px;margin-top:6px}}
.tiles{{display:flex;gap:18px;padding:14px 40px 0}} .tile{{flex:1;background:{CARD};border:1px solid {GRID};border-top:4px solid {MINT};border-radius:14px;padding:14px 22px}}
.tile.bad{{border-top-color:{ROSE}}} .k{{color:{MUT};font-size:15px;font-weight:600}} .v{{font-size:40px;font-weight:800;margin:4px 0}} .s{{color:{MUT};font-size:15px}}</style></head>
<body><header><h1>Ostrawind Supply Co. &middot; supplier and inventory dashboard</h1>
<div class="sub">Every number comes from a MetricFlow saved query on the Ossie supply chain model (exports/*.csv). Targets from the 2026 SLA schedule.</div></header>
<div class="tiles">{tile_html}</div>
{fig.to_html(full_html=False, include_plotlyjs=True, config={"displayModeBar": False})}</body></html>"""
(OUT / "index.html").write_text(html)
print(f"dashboard/index.html written: {len(suppliers)} suppliers, {len(byw)} warehouses, targets for {len(targets)} contracts")
if "--open" in sys.argv: webbrowser.open((OUT / "index.html").as_uri())
