import os
from functools import wraps
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

# ── Connection Pool ───────────────────────────────────────────
# Thread-safe pool reuses connections instead of opening a new
# TCP socket per request (~20-50ms saved each time on Render).
_pool = None
_POOL_MIN = 1
_POOL_MAX = 10


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(_POOL_MIN, _POOL_MAX, **DB_CONFIG)
    return _pool


def close_pool():
    """Call on app shutdown to release all pooled connections."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


class PgCursor:
    def __init__(self, cursor, conn, dictionary=False):
        self._cur = cursor
        self._conn = conn
        self._is_dict = dictionary
        self.lastrowid = None
        self.rowcount = None
        self.description = None

    def execute(self, query, params=None):
        q = query.strip().upper()
        if q.startswith('INSERT') and not q.startswith('INSERT OVERRIDING') and ' RETURNING ' not in q:
            query = query.rstrip(';') + ' RETURNING id'
            self._cur.execute(query, params)
            self.description = self._cur.description
            self.rowcount = self._cur.rowcount
            self.lastrowid = self._get_insert_id()
        else:
            self._cur.execute(query, params)
            self.rowcount = self._cur.rowcount
            self.description = self._cur.description
            if q.startswith('INSERT') and not q.startswith('INSERT OVERRIDING'):
                try:
                    self._cur.execute("SELECT LASTVAL()")
                    row_lv = self._cur.fetchone()
                    self.lastrowid = self._get_id_from_row(row_lv)
                except Exception:
                    self.lastrowid = None
        return self

    def _get_id_from_row(self, row):
        if row is None:
            return None
        if self._is_dict:
            return row['id']
        return row[0]

    def _get_insert_id(self):
        try:
            return self._get_id_from_row(self._cur.fetchone())
        except Exception:
            return None

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
        return PgCursor(cur, self._conn, dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        """Return connection to pool instead of destroying it."""
        try:
            self._conn.rollback()
        except Exception:
            pass
        try:
            _get_pool().putconn(self._conn)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass


def _set_timezone(raw):
    try:
        with raw.cursor() as cur:
            cur.execute("SET TIMEZONE TO 'America/Lima'")
    except Exception:
        pass


def get_connection():
    raw = _get_pool().getconn()
    _set_timezone(raw)
    return PgConnection(raw)


class Database:
    def __init__(self, dictionary=True):
        self.conn = None
        self.cur = None
        self.dictionary = dictionary

    def __enter__(self):
        raw = _get_pool().getconn()
        _set_timezone(raw)
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
