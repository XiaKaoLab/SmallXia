"""持久化强化学习 episode、人工接管、转换样本与视觉成功标签。
Created on 2026-11-02; Updated on 2026-11-02
@author: https://github.com/Linmoqian
"""
import json
import sqlite3
from pathlib import Path


class ReplayStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.config = json.loads((directory / 'session.json').read_text(encoding='utf-8'))
        with self.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS transitions (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL, reward REAL NOT NULL, terminated INTEGER NOT NULL,
                    truncated INTEGER NOT NULL, intervention INTEGER NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS labels (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reward INTEGER NOT NULL, payload TEXT NOT NULL);
            ''')
            connection.execute('INSERT OR IGNORE INTO control VALUES (1, ?)', (json.dumps({
                'episode': 0, 'episode_steps': 0, 'status': 'ready', 'intervention': False,
                'intervention_target': None, 'intervention_expires_ns': 0}),))

    def connect(self):
        connection = sqlite3.connect(self.directory / 'replay.sqlite3', timeout=3)
        connection.execute('PRAGMA journal_mode=WAL')
        return connection

    def control(self):
        with self.connect() as connection:
            return json.loads(connection.execute('SELECT payload FROM control WHERE id=1').fetchone()[0])

    def update_control(self, **changes):
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            state = json.loads(connection.execute('SELECT payload FROM control WHERE id=1').fetchone()[0])
            state.update(changes)
            connection.execute('UPDATE control SET payload=? WHERE id=1', (json.dumps(state),))
            return state

    def append(self, row):
        with self.connect() as connection:
            cursor = connection.execute('INSERT INTO transitions(kind,reward,terminated,truncated,intervention,payload) VALUES (?,?,?,?,?,?)',
                (row['kind'], row['reward'], row['terminated'], row['truncated'], row['intervention'], json.dumps(row, allow_nan=False)))
            return cursor.lastrowid

    def rows(self, after=0, limit=100000):
        with self.connect() as connection:
            values = connection.execute('SELECT id,payload,reward,terminated,truncated FROM transitions WHERE id>? ORDER BY id LIMIT ?', (after, limit)).fetchall()
            return [{**json.loads(payload), 'id': key, 'reward': reward, 'terminated': bool(done), 'truncated': bool(truncated)}
                    for key, payload, reward, done, truncated in values]

    def feedback(self, transition_id, success, *, truncated=False, reward_source='human'):
        with self.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT payload FROM transitions WHERE id=?', (transition_id,)).fetchone()
            if row is None:
                raise FileNotFoundError('转换样本不存在')
            payload = json.loads(row[0])
            payload['reward_source'] = reward_source
            connection.execute('UPDATE transitions SET reward=?,terminated=?,truncated=?,payload=? WHERE id=?',
                               (int(success), int(success or not truncated), int(truncated), json.dumps(payload), transition_id))

    def label(self, observation, reward):
        with self.connect() as connection:
            cursor = connection.execute('INSERT INTO labels(reward,payload) VALUES (?,?)', (reward, json.dumps(observation)))
            return cursor.lastrowid

    def labels(self):
        with self.connect() as connection:
            return [{'reward': reward, 'observation': json.loads(payload)} for reward, payload in connection.execute('SELECT reward,payload FROM labels')]

    def summary(self):
        with self.connect() as connection:
            total, interventions, reward = connection.execute('SELECT count(*),coalesce(sum(intervention),0),coalesce(sum(reward),0) FROM transitions').fetchone()
            labels = dict(connection.execute('SELECT reward,count(*) FROM labels GROUP BY reward'))
        return {**self.config, **self.control(), 'transitions': total, 'interventions': interventions,
                'intervention_rate': interventions / total if total else 0, 'reward_sum': reward,
                'reward_labels': {str(key): value for key, value in labels.items()}}
