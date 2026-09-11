"""SQLite repository boundary; short transactions, foreign keys, WAL, versioned schema."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@contextmanager
def connect():
    path = Path(os.environ.get("BLUEZONE_DB", str(ROOT / "data/bluezone.db")))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise RuntimeError("Database schema is newer than this application")
        if version == 0:
            db.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
              name TEXT NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'learner' CHECK(role IN ('learner','admin')),
              active INTEGER NOT NULL DEFAULT 1, created INTEGER NOT NULL);
            CREATE TABLE sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              csrf TEXT NOT NULL, expires INTEGER NOT NULL);
            CREATE INDEX sessions_user ON sessions(user_id);
            CREATE TABLE paths(id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
              level TEXT NOT NULL, position INTEGER NOT NULL UNIQUE);
            CREATE TABLE units(id TEXT PRIMARY KEY, path_id TEXT NOT NULL REFERENCES paths(id),
              title TEXT NOT NULL, summary TEXT NOT NULL, kind TEXT NOT NULL, minutes INTEGER NOT NULL,
              xp INTEGER NOT NULL, position INTEGER NOT NULL UNIQUE, published INTEGER NOT NULL DEFAULT 1,
              content TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE completions(user_id INTEGER NOT NULL REFERENCES users(id), unit_id TEXT NOT NULL REFERENCES units(id),
              completed INTEGER NOT NULL, xp INTEGER NOT NULL, PRIMARY KEY(user_id,unit_id));
            CREATE TABLE attempts(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
              unit_id TEXT NOT NULL REFERENCES units(id), correct INTEGER NOT NULL, created INTEGER NOT NULL);
            CREATE INDEX attempts_user ON attempts(user_id,created);
            CREATE TABLE chats(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
              unit_id TEXT NOT NULL REFERENCES units(id), role TEXT NOT NULL, message TEXT NOT NULL, mode TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE TABLE audit(id INTEGER PRIMARY KEY, actor INTEGER REFERENCES users(id), action TEXT NOT NULL,
              target TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE TABLE limits(key TEXT PRIMARY KEY, start INTEGER NOT NULL, count INTEGER NOT NULL);
            PRAGMA user_version=1;
            ''')

def audit(db, actor, action, target):
    import time
    db.execute("INSERT INTO audit(actor,action,target,created) VALUES(?,?,?,?)", (actor, action, str(target), int(time.time())))
