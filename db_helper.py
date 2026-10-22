# db_helper.py
import sqlite3
import json

class DBHelper:
    def __init__(self, db_path="detections.db"):
        self.db_path = db_path

    def insert_detection(self, image_path, result_label, confidence=0.0, detail_info=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO detections (image_path, result_label, confidence, detail_info, source)
            VALUES (?, ?, ?, ?, ?)
        ''', (image_path, result_label, confidence,
              json.dumps(detail_info) if detail_info else None,
              "live"))
        conn.commit()
        detection_id = cursor.lastrowid
        conn.close()
        return detection_id

    def get_history(self, limit=100):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, timestamp, image_path, result_label, confidence
            FROM detections ORDER BY id DESC LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_statistics(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM detections')
        total = cursor.fetchone()[0]
        cursor.execute('SELECT result_label, COUNT(*) FROM detections GROUP BY result_label')
        by_label = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM detections WHERE DATE(timestamp)=DATE('now')")
        today = cursor.fetchone()[0]
        conn.close()
        return {"total": total, "by_label": dict(by_label), "today": today}
