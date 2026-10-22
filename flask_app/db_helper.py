# db_helper.py —— 数据库操作（统计组：智能人流统计与考勤系统）
# 记录一次“进入/离开”事件，result_label = enter / exit，confidence = 本次人数
import sqlite3
import json
import os

# 默认数据库路径：优先使用 flask_app 同级的 detections.db（与顶层实验共用）
DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "detections.db")


class DBHelper:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                result_label TEXT NOT NULL,
                confidence REAL,
                detail_info TEXT,
                source TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def insert_detection(self, image_path, result_label, confidence=1.0,
                         detail_info=None, source="live"):
        """插入一条人流事件（进入/离开）记录"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO detections (image_path, result_label, confidence, detail_info, source)
            VALUES (?, ?, ?, ?, ?)
        ''', (image_path, result_label, float(confidence),
              json.dumps(detail_info) if detail_info else None, source))
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    def get_history(self, limit=100):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('''
            SELECT id, timestamp, image_path, result_label, confidence
            FROM detections ORDER BY id DESC LIMIT ?
        ''', (limit,))
        rows = cur.fetchall()
        conn.close()
        return rows

    def get_statistics(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM detections')
        total = cur.fetchone()[0]
        cur.execute('SELECT result_label, COUNT(*) FROM detections GROUP BY result_label')
        by_label = dict(cur.fetchall())
        cur.execute("SELECT COUNT(*) FROM detections WHERE DATE(timestamp)=DATE('now', 'localtime')")
        today = cur.fetchone()[0]
        conn.close()
        return {"total": total, "by_label": by_label, "today": today}

    def get_setting(self, key, default=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('SELECT value FROM system_settings WHERE key=?', (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else default

    def set_setting(self, key, value):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)',
                    (key, str(value)))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    db = DBHelper()
    print("数据库:", db.db_path)
    print("统计:", db.get_statistics())
    print("计数线位置:", db.get_setting("count_line_y", 240))
