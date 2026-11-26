# SPDX-License-Identifier: MIT
"""Minimal Superset config for the banking Cube demo."""

from __future__ import annotations

import os

SECRET_KEY = os.environ.get(
    "SUPERSET_SECRET_KEY",
    "banking_cube_superset_dev_secret_change_me",
)
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://superset:superset@superset_db:5432/superset",
)
WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = False
ROW_LIMIT = 50000
SUPERSET_WEBSERVER_PORT = 8088
# Allow embedding Cube SQL results without extra feature flags for the demo.
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
}
