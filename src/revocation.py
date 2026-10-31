"""Persistent revocation shared by web, CLI and MCP authentication."""
from contextlib import contextmanager
import hashlib
import sqlite3
import time
from src.config import workspace_path


@contextmanager
def connect():
    path=workspace_path('keys/revocations.sqlite3')
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path)
    db.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, cutoff INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS tokens (digest TEXT PRIMARY KEY, expires INTEGER NOT NULL)')
    try:
        with db:
            yield db
    finally:
        db.close()


def cutoff(user_id):
    with connect() as db:
        row=db.execute('SELECT cutoff FROM users WHERE id=?',(user_id,)).fetchone()
        return row[0] if row else -1


def revoke_user(user_id):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO users VALUES (?,?)',(user_id,int(time.time())))


def revoke_token(token):
    if not token:return
    with connect() as db:
        db.execute('DELETE FROM tokens WHERE expires < ?', (int(time.time()),))
        db.execute('INSERT OR REPLACE INTO tokens VALUES (?,?)',(hashlib.sha256(token.encode()).hexdigest(),int(time.time())+3600))


def revoked(token,user_id,issued_at):
    with connect() as db:
        row=db.execute('SELECT cutoff FROM users WHERE id=?',(user_id,)).fetchone()
        return bool((row and issued_at<=row[0]) or db.execute('SELECT 1 FROM tokens WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone())
