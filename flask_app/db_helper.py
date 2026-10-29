# db_helper.py —— 数据库操作（统计组：智能人流统计与考勤系统）
# 记录一次“进入/离开”事件，result_label = enter / exit
#
# 时区约定：timestamp 一律用 UTC 存储（CURRENT_TIMESTAMP），
#           查询/展示时统一用 datetime(timestamp,'localtime') 转成本地时间，
#           避免“今日统计”在凌晨 0~8 点算错、后台显示时间差 8 小时。
import json
import os
import sqlite3

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "detections.db")

LOCAL_TS = "datetime(timestamp, 'localtime')"          # 统一的本地时间表达式


class DBHelper:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB
        self.init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self._conn()
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
        cur.execute('CREATE INDEX IF NOT EXISTS idx_detections_ts ON detections(timestamp)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_detections_label ON detections(result_label)')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()
        conn.close()

    # ---------------- 写入 ----------------
    def insert_detection(self, image_path, result_label, confidence=1.0,
                         detail_info=None, source="live"):
        """插入一条人流事件（进入/离开）记录"""
        conn = self._conn()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO detections (image_path, result_label, confidence, detail_info, source)
            VALUES (?, ?, ?, ?, ?)
        ''', (image_path, result_label, float(confidence),
              json.dumps(detail_info, ensure_ascii=False) if detail_info else None, source))
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    # ---------------- 查询 ----------------
    def get_history(self, limit=100):
        """返回最近记录（时间为本地时间字符串）"""
        conn = self._conn()
        rows = conn.execute(f'''
            SELECT id, {LOCAL_TS} AS ts, image_path, result_label, confidence, detail_info, source
            FROM detections ORDER BY id DESC LIMIT ?
        ''', (int(limit),)).fetchall()
        conn.close()
        return rows

    def get_statistics(self, hours=24):
        conn = self._conn()
        cur = conn.cursor()
        total = cur.execute('SELECT COUNT(*) FROM detections').fetchone()[0]
        by_label = dict(cur.execute(
            'SELECT result_label, COUNT(*) FROM detections GROUP BY result_label').fetchall())
        today = cur.execute(
            f"SELECT COUNT(*) FROM detections WHERE DATE({LOCAL_TS})=DATE('now','localtime')"
        ).fetchone()[0]
        today_enter = cur.execute(
            f"SELECT COUNT(*) FROM detections WHERE result_label='enter' "
            f"AND DATE({LOCAL_TS})=DATE('now','localtime')").fetchone()[0]
        today_exit = cur.execute(
            f"SELECT COUNT(*) FROM detections WHERE result_label='exit' "
            f"AND DATE({LOCAL_TS})=DATE('now','localtime')").fetchone()[0]
        # 近 N 小时分时统计（本地时间）
        rows = cur.execute(
            f"SELECT strftime('%H', {LOCAL_TS}) AS h, result_label, COUNT(*) "
            f"FROM detections WHERE {LOCAL_TS} >= datetime('now','localtime', ?) "
            f"GROUP BY h, result_label", (f'-{int(hours)} hours',)).fetchall()
        hourly = {f"{h:02d}": {"enter": 0, "exit": 0} for h in range(24)}
        for r in rows:
            if r["h"] in hourly:
                hourly[r["h"]][r["result_label"]] = r["COUNT(*)"]
        conn.close()
        enter_total = int(by_label.get("enter", 0))
        exit_total = int(by_label.get("exit", 0))
        return {"total": total, "by_label": by_label,
                "today": today, "today_enter": today_enter, "today_exit": today_exit,
                "current": max(0, enter_total - exit_total),
                "hourly": hourly}

    def get_daily_report(self, date=None):
        """某天的考勤/人流日报：分时进出 + 首末时间 + 高峰小时"""
        conn = self._conn()
        cur = conn.cursor()
        day = date or cur.execute("SELECT DATE('now','localtime')").fetchone()[0]
        rows = cur.execute(
            f"""SELECT strftime('%H', {LOCAL_TS}) AS h, result_label, COUNT(*) AS c
                FROM detections WHERE DATE({LOCAL_TS}) = ?
                GROUP BY h, result_label ORDER BY h""", (day,)).fetchall()
        hourly = [{"hour": f"{h:02d}", "enter": 0, "exit": 0} for h in range(24)]
        for r in rows:
            idx = int(r["h"])
            hourly[idx][r["result_label"]] = r["c"]
        enter = sum(x["enter"] for x in hourly)
        exit_ = sum(x["exit"] for x in hourly)
        first = cur.execute(
            f"SELECT MIN({LOCAL_TS}) FROM detections WHERE result_label='enter' "
            f"AND DATE({LOCAL_TS})=?", (day,)).fetchone()[0]
        last = cur.execute(
            f"SELECT MAX({LOCAL_TS}) FROM detections WHERE DATE({LOCAL_TS})=?", (day,)
        ).fetchone()[0]
        peak = max(hourly, key=lambda x: x["enter"], default=None)
        conn.close()
        return {"date": day, "enter": enter, "exit": exit_,
                "net": max(0, enter - exit_), "hourly": hourly,
                "first_enter": first, "last_event": last,
                "peak_hour": peak["hour"] if peak and peak["enter"] else None,
                "peak_enter": peak["enter"] if peak else 0}

    def history_csv(self, limit=5000):
        """导出 CSV 文本（本地时间）"""
        conn = self._conn()
        rows = conn.execute(
            f"SELECT id, {LOCAL_TS} AS ts, result_label, detail_info, source "
            f"FROM detections ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        conn.close()
        lines = ["id,时间,类型,详情,来源"]
        for r in rows:
            lbl = "进入" if r["result_label"] == "enter" else "离开"
            detail = (r["detail_info"] or "").replace('"', "'").replace(",", ";")
            lines.append(f'{r["id"]},{r["ts"]},{lbl},"{detail}",{r["source"] or ""}')
        return "\n".join(lines)

    def prune(self, days=None):
        """清理超过 days 天的历史记录，返回删除条数"""
        import config
        days = int(days or getattr(config, "DB_RETAIN_DAYS", 90))
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM detections WHERE {LOCAL_TS} < "
                    f"datetime('now','localtime', ?)", (f'-{days} days',))
        n = cur.rowcount
        conn.commit()
        conn.close()
        return n

    # ---------------- 设置 ----------------
    def get_setting(self, key, default=None):
        conn = self._conn()
        row = conn.execute('SELECT value FROM system_settings WHERE key=?', (key,)).fetchone()
        conn.close()
        return row["value"] if row else default

    def set_setting(self, key, value):
        conn = self._conn()
        conn.execute('INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)',
                     (key, str(value)))
        conn.commit()
        conn.close()


if __name__ == "__main__":
    db = DBHelper()
    print("数据库:", db.db_path)
    print("统计:", db.get_statistics())
    print("日报:", db.get_daily_report())
    print("计数线位置:", db.get_setting("count_line_y", 240))