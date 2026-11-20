"""Generate the fictional Northlight Cinemas sample data (Data for AI, folder 08).

Writes four CSV files (a small star schema) and one H2 SQL script that
loads them. Everything here is made up: cinemas, films and numbers.
Run:  python3 data/build_data.py
"""
import csv, datetime as dt, os, random

random.seed(8)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_SQL = os.path.join(HERE, "..", "sql", "northlight_h2.sql")

CINEMAS = [  # id, name, city, province, region, screens
    (1, "Northlight Harbourfront", "Halifax", "NS", "East", 6),
    (2, "Northlight Byward", "Ottawa", "ON", "East", 8),
    (3, "Northlight Plateau", "Montreal", "QC", "East", 10),
    (4, "Northlight Old Port", "Montreal", "QC", "East", 7),
    (5, "Northlight Bow River", "Calgary", "AB", "West", 9),
    (6, "Northlight Seawall", "Vancouver", "BC", "West", 12),
    (7, "Northlight Inner Harbour", "Victoria", "BC", "West", 5),
]
FILMS = [  # id, title, genre, rating, release date, pull (popularity)
    (1, "Glacier Run", "Action", "PG-13", "2026-01-09", 1.25),
    (2, "The Last Lantern", "Drama", "PG", "2026-01-23", 0.80),
    (3, "Pixel Paws", "Animation", "G", "2026-02-06", 1.30),
    (4, "Static Hollow", "Horror", "R", "2026-02-27", 0.95),
    (5, "Orbit Nine", "Sci-Fi", "PG-13", "2026-03-13", 1.40),
    (6, "Wedding Weather", "Comedy", "PG-13", "2026-03-27", 0.85),
    (7, "Iron Tide", "Action", "PG-13", "2026-04-10", 1.15),
    (8, "Quiet Harbour", "Drama", "PG", "2026-04-24", 0.70),
    (9, "Moss and Pebble", "Animation", "G", "2026-05-08", 1.20),
    (10, "Night Signal", "Horror", "R", "2026-05-22", 1.00),
    (11, "Second Sun", "Sci-Fi", "PG-13", "2026-06-05", 1.35),
    (12, "Office Party Animals", "Comedy", "14A", "2026-06-12", 0.90),
]
CINEMA_PULL = {1: 0.85, 2: 1.00, 3: 1.15, 4: 0.90, 5: 1.05, 6: 1.25, 7: 0.80}  # local demand
DAYPARTS = [  # name, sort, base price, demand factor
    ("Matinee", 1, 11.00, 0.55), ("Evening", 2, 15.50, 1.00), ("Late Night", 3, 13.00, 0.60)]
START, END = dt.date(2026, 1, 1), dt.date(2026, 6, 30)

def write_csv(name, header, rows):
    with open(os.path.join(HERE, name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

dates, d = [], START
while d <= END:
    q = (d.month - 1) // 3 + 1
    dates.append((int(d.strftime("%Y%m%d")), d.isoformat(), d.year, q, f"Q{q}", d.month,
                  d.strftime("%B"), d.strftime("%A"), "Weekend" if d.weekday() >= 4 else "Weekday"))
    d += dt.timedelta(days=1)

facts, sid = [], 1
for (dk, iso, *_rest) in dates:
    day = dt.date.fromisoformat(iso)
    weekend = 1.35 if day.weekday() >= 4 else 1.0
    showing = [f for f in FILMS if 0 <= (day - dt.date.fromisoformat(f[4])).days < 56]
    for c in CINEMAS:
        cid, screens, west = c[0], c[5], c[4] == "West"
        for dp, _s, price, demand in DAYPARTS:
            for film in random.sample(showing, min(3 if screens >= 9 else 2, len(showing))):
                age_weeks = (day - dt.date.fromisoformat(film[4])).days // 7
                decay = 0.86 ** age_weeks
                seats = random.choice([120, 150, 180, 220, 260])
                fill = 0.62 * CINEMA_PULL[cid] * demand * weekend * film[5] * decay * random.uniform(0.75, 1.2)
                if film[2] == "Animation" and dp == "Late Night": fill *= 0.25
                if film[2] == "Horror" and dp == "Late Night": fill *= 1.6
                tickets = max(0, min(seats, round(seats * fill)))
                p = price + (1.0 if west else 0.0) + (2.0 if film[2] in ("Sci-Fi", "Action") else 0.0)
                rev = round(tickets * p * random.uniform(0.93, 0.99), 2)  # discounts and passes
                per_head = random.uniform(6.0, 8.5) * (1.25 if film[2] == "Animation" else 1.0)
                conc = round(tickets * per_head, 2)
                facts.append((sid, dk, cid, film[0], _s, seats, tickets, rev, conc)); sid += 1

write_csv("cinemas.csv", ["cinema_id", "cinema_name", "city", "province", "region", "screens"], CINEMAS)
write_csv("films.csv", ["film_id", "title", "genre", "rating", "release_date", "popularity"], FILMS)
write_csv("dates.csv", ["date_key", "the_date", "year", "quarter", "quarter_name", "month_num", "month_name", "day_name", "day_type"], dates)
write_csv("dayparts.csv", ["daypart_id", "daypart", "base_price"], [(s, n, p) for n, s, p, _ in DAYPARTS])
write_csv("screenings.csv", ["screening_id", "date_key", "cinema_id", "film_id", "daypart_id", "seats_available", "tickets_sold", "ticket_revenue", "concession_revenue"], facts)

def lit(v): return str(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'"
def inserts(table, rows):
    out = []
    for i in range(0, len(rows), 500):
        out.append(f'INSERT INTO "{table}" VALUES'+"\n" + ",\n".join("(" + ",".join(lit(v) for v in r) + ")" for r in rows[i:i+500]) + ";")
    return "\n".join(out)

DDL = {
    "dim_cinema": [("cinema_id", "INT PRIMARY KEY"), ("cinema_name", "VARCHAR(60)"), ("city", "VARCHAR(40)"),
                   ("province", "VARCHAR(4)"), ("region", "VARCHAR(10)"), ("screens", "INT")],
    "dim_film": [("film_id", "INT PRIMARY KEY"), ("title", "VARCHAR(60)"), ("genre", "VARCHAR(20)"),
                 ("rating", "VARCHAR(8)"), ("release_date", "DATE"), ("popularity", "DECIMAL(4,2)")],
    "dim_date": [("date_key", "INT PRIMARY KEY"), ("the_date", "DATE"), ("the_year", "INT"), ("quarter", "INT"),
                 ("quarter_name", "VARCHAR(2)"), ("month_num", "INT"), ("month_name", "VARCHAR(12)"),
                 ("day_name", "VARCHAR(10)"), ("day_type", "VARCHAR(8)")],
    "dim_daypart": [("daypart_id", "INT PRIMARY KEY"), ("daypart", "VARCHAR(12)"), ("base_price", "DECIMAL(6,2)")],
    "fact_screening": [("screening_id", "INT PRIMARY KEY"), ("date_key", "INT"), ("cinema_id", "INT"), ("film_id", "INT"),
                       ("daypart_id", "INT"), ("seats_available", "INT"), ("tickets_sold", "INT"),
                       ("ticket_revenue", "DECIMAL(10,2)"), ("concession_revenue", "DECIMAL(10,2)")],
}

os.makedirs(os.path.dirname(OUT_SQL), exist_ok=True)
with open(OUT_SQL, "w") as f:
    f.write("-- Northlight Cinemas (fictional) star schema for H2. Generated by data/build_data.py.\n"
            "-- Identifiers are quoted lowercase because Mondrian quotes the names it reads from the schema.\n")
    for t in ["fact_screening", "dim_cinema", "dim_film", "dim_date", "dim_daypart"]:
        f.write(f'DROP TABLE IF EXISTS "{t}";\n')
    for t, cols in DDL.items():
        f.write(f'CREATE TABLE "{t}" (' + ", ".join(f'"{c}" {ty}' for c, ty in cols) + ");\n")
    f.write(inserts("dim_cinema", CINEMAS) + "\n")
    f.write(inserts("dim_film", [(a, b, c, r, d, p) for a, b, c, r, d, p in FILMS]).replace("'2026-", "DATE '2026-") + "\n")
    f.write(inserts("dim_date", [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for r in dates]).replace(", '2026-", ", DATE '2026-") + "\n")
    f.write(inserts("dim_daypart", [(s, n, p) for n, s, p, _ in DAYPARTS]) + "\n")
    f.write(inserts("fact_screening", facts) + "\n")

print(f"cinemas={len(CINEMAS)} films={len(FILMS)} dates={len(dates)} screenings={len(facts)}")
print(f"tickets={sum(r[6] for r in facts):,} ticket_revenue=${sum(r[7] for r in facts):,.2f}")
