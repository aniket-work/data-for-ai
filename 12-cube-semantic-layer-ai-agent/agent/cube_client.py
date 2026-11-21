"""Tiny client for a local Cube Core: mints a JWT per role and calls REST, GraphQL and the SQL API."""
import json
import os
import time
from pathlib import Path

import httpx
import jwt

ROOT = Path(__file__).resolve().parent.parent
CUBE_URL = os.environ.get("CUBE_URL", "http://localhost:4000")
ROLES = json.loads((ROOT / "cube" / "roles.json").read_text())


def _env(name: str) -> str:
    if name in os.environ:
        return os.environ[name]
    for line in (ROOT / "cube" / ".env").read_text().splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1]
    raise KeyError(name)


def token(role: str) -> str:
    """A short-lived JWT whose payload is the role's security context."""
    ctx = dict(ROLES[role])
    ctx["exp"] = int(time.time()) + 3600
    return jwt.encode(ctx, _env("CUBEJS_API_SECRET"), algorithm="HS256")


def _headers(role):
    return {"Authorization": token(role), "Content-Type": "application/json"}


def load(query: dict, role: str = "exec") -> dict:
    """POST /cubejs-api/v1/load. Retries while Cube answers 'Continue wait'."""
    for _ in range(60):
        r = httpx.post(f"{CUBE_URL}/cubejs-api/v1/load", json={"query": query},
                       headers=_headers(role), timeout=60)
        body = r.json()
        if body.get("error") == "Continue wait":
            time.sleep(0.5)
            continue
        if r.status_code >= 400 or "error" in body:
            raise RuntimeError(body.get("error", r.text))
        return body
    raise TimeoutError("Cube kept saying 'Continue wait'")


def meta(role: str = "exec") -> dict:
    r = httpx.get(f"{CUBE_URL}/cubejs-api/v1/meta", headers=_headers(role), timeout=30)
    r.raise_for_status()
    return r.json()


def graphql(gql: str, role: str = "exec") -> dict:
    r = httpx.post(f"{CUBE_URL}/cubejs-api/graphql", json={"query": gql},
                   headers=_headers(role), timeout=60)
    return r.json()


def sql_api(sql: str, user: str = "exec"):
    """Cube's SQL API speaks the Postgres wire protocol on port 15432."""
    import psycopg
    conn = psycopg.connect(host=os.environ.get("CUBE_SQL_HOST", "localhost"),
                           port=int(os.environ.get("CUBE_SQL_PORT", "15432")),
                           user=user, password=_env("CUBEJS_SQL_PASSWORD"), dbname="cube")
    with conn, conn.cursor() as cur:
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        return cols, cur.fetchall()
