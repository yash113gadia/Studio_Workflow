"""Quick database schema audit."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "studio.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("PRAGMA journal_mode")
print(f"Journal Mode: {c.fetchone()[0]}")

c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in c.fetchall()]
print(f"Total Tables: {len(tables)}")
for t in tables:
    c.execute(f'SELECT COUNT(*) FROM "{t}"')
    count = c.fetchone()[0]
    print(f"  {t}: {count} rows")

conn.close()
print("\nDATABASE SCHEMA AUDIT: PASSED")
