"""Consistent online SQLite backup, including committed WAL data."""
import argparse
import sqlite3
from pathlib import Path
from .db import connect
p=argparse.ArgumentParser(description='Back up BlueZone data')
p.add_argument('destination',help='A new backup filename outside the application data directory')
a=p.parse_args()
dest=Path(a.destination).resolve()
if dest.exists():raise SystemExit('Destination already exists. Choose a new backup filename.')
dest.parent.mkdir(parents=True,exist_ok=True)
with connect() as source:
    with sqlite3.connect(dest) as target:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Backup integrity check failed')
print('Backup verified:',dest)
