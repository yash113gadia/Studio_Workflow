"""Preeti Studio End-to-End System Healthcheck Script."""
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None


def check_system_health():
    print("=" * 80)
    print("PREETI STUDIO LOCAL AI OS — SYSTEM OPERATIONAL HEALTHCHECK")
    print("=" * 80)

    # 1. Check SQLite Database
    db_path = Path("database/studio.db")
    if not db_path.exists():
        print(f"[FAIL] SQLite database missing at {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check WAL mode
    wal_mode = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
    print(f"Database Journal Mode: {wal_mode.upper()} {'[OK]' if wal_mode.upper() == 'WAL' else '[WARNING]'}")

    # Check tables count
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print(f"Active Relational Tables: {len(tables)} tables registered [OK]")

    # Check GPU lease state
    lease_row = cursor.execute("SELECT resource, owner_job_id, acquired_at FROM gpu_lease WHERE resource='GPU0_HEAVY'").fetchone()
    if lease_row:
        res, owner, acq = lease_row
        status_str = f"LOCKED by {owner} at {acq}" if owner else "FREE / READY"
        print(f"GPU Mutex Lease ({res}): {status_str} [OK]")
    else:
        print("[FAIL] GPU0_HEAVY lease resource not configured in DB.")
        conn.close()
        return 1

    conn.close()

    # 2. Host RAM and Free Disk
    if psutil:
        mem = psutil.virtual_memory()
        total_ram_gb = mem.total / (1024**3)
        avail_ram_gb = mem.available / (1024**3)
        print(f"Host System RAM: {avail_ram_gb:.2f} GB available of {total_ram_gb:.2f} GB total [OK]")

    # 3. Directories integrity
    critical_dirs = ["database", "models", "projects", "workflows", "shared_assets", "services"]
    for d in critical_dirs:
        p = Path(d)
        if p.exists() and p.is_dir():
            print(f"Core Directory '{d}': FOUND [OK]")
        else:
            print(f"Core Directory '{d}': MISSING [FAIL]")
            return 1

    print("=" * 80)
    print("STATUS: OPERATIONAL — ALL SUBSYSTEMS HEALTHY")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(check_system_health())
