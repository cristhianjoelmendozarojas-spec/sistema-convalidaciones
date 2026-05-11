import os
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

class PgCursor:
    def __init__(self, cursor, conn):
        self._cur = cursor
        self._conn = conn
        self.lastrowid = None
        self.rowcount = None
        self.description = None

    def execute(self, query, params=None):
        self._cur.execute(query, params)
        self.rowcount = self._cur.rowcount
        self.description = self._cur.description
        q = query.strip().upper()
        if q.startswith('INSERT') and not q.startswith('INSERT OVERRIDING'):
            try:
                self._cur.execute("SELECT LASTVAL()")
                self.lastrowid = self._cur.fetchone()[0]
            except Exception:
                self.lastrowid = None
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def close(self):
        self._cur.close()


class PgConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, dictionary=True):
        factory = RealDictCursor if dictionary else None
        cur = self._conn.cursor(cursor_factory=factory)
        return PgCursor(cur, self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_connection():
    raw = psycopg2.connect(**DB_CONFIG)
    return PgConnection(raw)


class Database:
    def __init__(self, dictionary=True):
        self.conn = None
        self.cur = None
        self.dictionary = dictionary

    def __enter__(self):
        raw = psycopg2.connect(**DB_CONFIG)
        self.conn = PgConnection(raw)
        self.cur = self.conn.cursor(dictionary=self.dictionary)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        return False

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn:
            self.conn.rollback()


def db_query(dictionary=True):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            with Database(dictionary=dictionary) as db:
                kwargs['db'] = db
                result = f(*args, **kwargs)
                db.commit()
                return result
        return wrapper
    return decorator


def db_transaction(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with Database(dictionary=True) as db:
            kwargs['db'] = db
            try:
                result = f(*args, **kwargs)
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise
    return wrapper


def fetch_one(query, params=None):
    with Database(dictionary=True) as db:
        db.cur.execute(query, params or ())
        return db.cur.fetchone()


def fetch_all(query, params=None):
    with Database(dictionary=True) as db:
        db.cur.execute(query, params or ())
        return db.cur.fetchall()


def execute(query, params=None, commit=True):
    with Database(dictionary=False) as db:
        db.cur.execute(query, params or ())
        if commit:
            db.commit()
        return db.cur.rowcount, db.cur.lastrowid
