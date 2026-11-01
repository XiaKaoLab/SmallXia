"""持久化采集命令、处理回执与设备工作进程状态。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from time import time_ns


class CaptureQueue:
    def __init__(self, directory):
        self.directory = directory
        self.config = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
        with self.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS commands(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL, result TEXT);
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.directory / 'queue.sqlite3', timeout=3)
        connection.execute('PRAGMA journal_mode=WAL')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def set(self, **values):
        with self.connect() as connection:
            for key, value in values.items():
                connection.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', (key, json.dumps(value)))

    def state(self):
        with self.connect() as connection:
            return {key: json.loads(value) for key, value in connection.execute('SELECT key,value FROM metadata')}

    def enqueue(self, kind, body):
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if connection.execute("SELECT count(*) FROM commands WHERE status IN ('queued','running')").fetchone()[0] >= 100:
                raise ValueError('待处理命令超过 100，请等待采集回执')
            cursor = connection.execute("INSERT INTO commands(kind,body,status) VALUES (?,?,'queued')", (kind, json.dumps(body)))
            return {'command_id': cursor.lastrowid, 'status': 'queued', 'session_id': self.config['id']}

    def next(self):
        with self.connect() as connection:
            row = connection.execute("SELECT id,kind,body FROM commands WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            if row:
                connection.execute("UPDATE commands SET status='running' WHERE id=?", (row[0],))
                return row[0], row[1], json.loads(row[2])

    def complete(self, command_id, status, result):
        with self.connect() as connection:
            connection.execute('UPDATE commands SET status=?,result=? WHERE id=?', (status, json.dumps(result), command_id))

    def command(self, command_id):
        with self.connect() as connection:
            row = connection.execute('SELECT status,result FROM commands WHERE id=?', (command_id,)).fetchone()
        if row is None:
            raise FileNotFoundError('采集命令不存在')
        return {'command_id': command_id, 'status': row[0], 'result': json.loads(row[1]) if row[1] else None}
