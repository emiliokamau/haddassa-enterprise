"""
Create newsletter_subscribers table and stamp Alembic to the correct revision.
Credentials are read from the .env file via the Flask app config.
Run from backend/ directory:
    ..\.venv\Scripts\python.exe tools\create_newsletter_table.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, NewsletterSubscriber

app = create_app()
with app.app_context():
    # Create any missing tables (safe, won't touch existing ones)
    db.create_all()

    # Check tables via SQLAlchemy
    result = db.session.execute(db.text("SHOW TABLES"))
    tables = [r[0] for r in result]

    if "newsletter_subscribers" in tables:
        print("OK: newsletter_subscribers table exists")
    else:
        print("ERROR: newsletter_subscribers table still missing")
        sys.exit(1)

    # Stamp alembic_version to c8d9e0f1a2b3 so db upgrade is a no-op
    try:
        row = db.session.execute(db.text("SELECT version_num FROM alembic_version")).fetchone()
        current = row[0] if row else None
    except Exception:
        current = None
    print(f"Current Alembic version: {current}")

    if current != "c8d9e0f1a2b3":
        db.session.execute(db.text("DELETE FROM alembic_version"))
        db.session.execute(db.text("INSERT INTO alembic_version (version_num) VALUES ('c8d9e0f1a2b3')"))
        db.session.commit()
        print("Stamped alembic_version to c8d9e0f1a2b3")
    else:
        print("Alembic version already at c8d9e0f1a2b3")

    print("\nAll tables in database:")
    result = db.session.execute(db.text("SHOW TABLES"))
    for r in result:
        print(f"  {r[0]}")
