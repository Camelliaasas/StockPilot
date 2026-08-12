"""数据库层：SQLite 海量存储——日线/指数/期货/新闻"""
import sqlite3, os

from paths import data_path
DB = data_path()

SCHEMA = '''
CREATE TABLE IF NOT EXISTS daily_prices (
    code TEXT, name TEXT, date TEXT,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL, turnover REAL,
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_code ON daily_prices(code, date);

CREATE TABLE IF NOT EXISTS index_daily (
    code TEXT, date TEXT,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_index ON index_daily(code, date);

CREATE TABLE IF NOT EXISTS futures_daily (
    code TEXT, name TEXT, date TEXT,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_futures ON futures_daily(code, date);

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, title TEXT, content TEXT, source TEXT, code TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, code TEXT, direction TEXT, confidence REAL,
    reason TEXT, actual_direction TEXT, correct INTEGER,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    code TEXT PRIMARY KEY, name TEXT,
    added_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS positions (
    code TEXT PRIMARY KEY, name TEXT,
    shares REAL, cost REAL,
    added_at TEXT DEFAULT (datetime('now','localtime'))
);
'''

def get_conn():
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

def upsert_prices(code, name, rows):
    """批量写入日线——按 (code,date) 去重"""
    conn = get_conn()
    conn.executemany(
        'INSERT OR REPLACE INTO daily_prices (code, name, date, open, high, low, close, volume, amount, turnover) VALUES (?,?,?,?,?,?,?,?,?,?)',
        [(code, name, r['date'].strftime('%Y-%m-%d') if hasattr(r['date'],'strftime') else str(r['date']),
          r['open'], r['high'], r['low'], r['close'], r.get('volume'), r.get('amount'), r.get('turnover'))
         for r in rows]
    )
    conn.commit()
    conn.close()

def upsert_index(code, rows):
    conn = get_conn()
    conn.executemany(
        'INSERT OR REPLACE INTO index_daily (code, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)',
        [(code, r['date'].strftime('%Y-%m-%d') if hasattr(r['date'],'strftime') else str(r['date']),
          r['open'], r['high'], r['low'], r['close'], r.get('volume'))
         for r in rows]
    )
    conn.commit()
    conn.close()

def upsert_futures(code, name, rows):
    conn = get_conn()
    conn.executemany(
        'INSERT OR REPLACE INTO futures_daily (code, name, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?,?)',
        [(code, name, r['date'].strftime('%Y-%m-%d') if hasattr(r['date'],'strftime') else str(r['date']),
          r['open'], r['high'], r['low'], r['close'], r.get('volume'))
         for r in rows]
    )
    conn.commit()
    conn.close()

def count_rows():
    conn = get_conn()
    n = conn.execute('SELECT COUNT(*) FROM daily_prices').fetchone()[0]
    ni = conn.execute('SELECT COUNT(*) FROM index_daily').fetchone()[0]
    nf = conn.execute('SELECT COUNT(*) FROM futures_daily').fetchone()[0]
    conn.close()
    return n, ni, nf

if __name__ == '__main__':
    init_db()
    print('✅ 数据库初始化完成')
