import functools
import sqlite3
import threading

connections = {}
_db_filename = None


def _connect():
    connections[threading.get_ident()] = sqlite3.connect(_db_filename)
    return connections[threading.get_ident()]


def _get_connection():
    return connections.get(threading.get_ident()) or _connect()


def init(db_filename):
    global _db_filename
    _db_filename = db_filename
    conn = _connect()
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (type INTEGER, uid TEXT, PRIMARY KEY (type, uid))')
    conn.commit()


TYPES = {
    'banned': 1,
    'ignored': 2,
    'bots': 3,
    'nodel': 4,
}


def auto_reconnect(f):
    @functools.wraps(f)
    def wrapped(*args):
        try:
            return f(*args)
        except sqlite3.DatabaseError:
            _connect()
            return f(*args)
    return wrapped


@auto_reconnect
def add(type, uid):
    type = TYPES[type]
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO users VALUES (?, ?) ON CONFLICT DO NOTHING', (type, str(uid)))
    conn.commit()
    return cur.rowcount


@auto_reconnect
def addmany(type, uids):
    type = TYPES[type]
    conn = _get_connection()
    cur = conn.cursor()
    cur.executemany('INSERT INTO users VALUES (?, ?) ON CONFLICT DO NOTHING', [(type, str(i)) for i in uids])
    conn.commit()
    return cur.rowcount


@auto_reconnect
def delete(type, uid):
    type = TYPES[type]
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM users WHERE type=? AND uid=?', (type, str(uid)))
    conn.commit()
    return cur.rowcount

@auto_reconnect
def deletemany(type, uids):
    type = TYPES[type]
    conn = _get_connection()
    cur = conn.cursor()
    cur.executemany('DELETE FROM users WHERE type=? AND uid=?', [(type, str(i)) for i in uids])
    conn.commit()
    return cur.rowcount

@auto_reconnect
def contains(type, uid):
    type = TYPES[type]
    cur = _get_connection().cursor()
    cur.execute('SELECT COUNT(*) FROM users WHERE type=? AND uid=?', (type, str(uid)))
    return bool(cur.fetchone()[0])

@auto_reconnect
def all(type):
    type = TYPES[type]
    cur = _get_connection().cursor()
    cur.execute('SELECT uid FROM users WHERE type=?', (type,))
    return [u[0] for u in cur.fetchall()]
