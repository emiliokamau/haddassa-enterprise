"""
Phase D helper: create audit_logs table via db.create_all() and report results.
Run from backend/ directory:
    ..\.venv\Scripts\python.exe tools\phase_d_setup.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, AuditLog
import pymysql

app = create_app()
with app.app_context():
    # Create any missing tables (safe for existing tables)
    db.create_all()

    conn = pymysql.connect(
        host="localhost", port=3760, user="root",
        password="42125811Kamau", db="hadassah_enterprises"
    )
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()

print("Tables in hadassah_enterprises:")
for t in tables:
    print(f"  {t}")

if "audit_logs" in tables:
    print("\nOK: audit_logs table exists")
else:
    print("\nERROR: audit_logs table missing")
    sys.exit(1)
