import hashlib
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import HTTPException
from .db import connect

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def answer_digest(value):
    return digest(" ".join(value.strip().casefold().split()))

def verify(password, hashed):
    try:
        return hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def rate_limit(key, maximum, seconds):
    now = int(time.time())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM limits WHERE start < ?", (now - 86400,))
        row = db.execute("SELECT * FROM limits WHERE key=?", (key,)).fetchone()
        if row and now - row['start'] < seconds:
            if row['count'] >= maximum:
                raise HTTPException(429, "Too many requests. Please try again later.", headers={"Retry-After": str(seconds - (now-row['start']))})
            db.execute("UPDATE limits SET count=count+1 WHERE key=?", (key,))
        else:
            db.execute("INSERT OR REPLACE INTO limits VALUES(?,?,1)", (key,now))
