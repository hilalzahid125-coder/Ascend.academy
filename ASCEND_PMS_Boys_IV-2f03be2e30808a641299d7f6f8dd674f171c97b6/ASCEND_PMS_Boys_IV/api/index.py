"""Vercel ASGI entry point.

Vercel's Python runtime may not invoke FastAPI lifespan hooks. Bootstrap the
schema and optional initial admin at cold start; the initialization is idempotent.
"""
import os
# The application loads its route fragments dynamically. Explicit imports let
# Vercel's dependency tracer discover packages referenced in those fragments.
import fastapi, jinja2, multipart, openpyxl, PIL, psycopg, psycopg_binary  # noqa: F401
from app import app
from db import init_db, ensure_admin, connect

init_db()
admin_password = os.getenv('PMS_ADMIN_PASSWORD')
if admin_password:
    if len(admin_password) < 12:
        raise RuntimeError('PMS_ADMIN_PASSWORD must be at least 12 characters.')
    ensure_admin(os.getenv('PMS_ADMIN_ID', 'ADMIN-0001'), os.getenv('PMS_ADMIN_NAME', 'School Administrator'), admin_password)
with connect() as conn:
    if not conn.execute("SELECT 1 FROM users WHERE role='admin' AND admin_level='super' AND status='active' LIMIT 1").fetchone():
        raise RuntimeError('No active Super Admin exists. Configure PMS_ADMIN_PASSWORD to initialize one.')
