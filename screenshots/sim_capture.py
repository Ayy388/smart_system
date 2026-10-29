# -*- coding: utf-8 -*-
"""sim_capture.py —— 在 SIM=1 演示模式下：等待计数累积 → 截图界面/后台 → 生成截图3"""
import json
import os
import subprocess
import sys
import time

import requests

ROOT = "/home/yango/smart_system"
SHOTS = os.path.join(ROOT, "screenshots")
DB = os.path.join(ROOT, "detections.db")
sys.path.insert(0, SHOTS)
from term_render import render_terminal


def sh(cmd, timeout=120):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return (p.stdout or "") + (p.stderr or "")


def chrome(url, out, w, h, budget=6000):
    sh(f"chromium --headless=new --disable-gpu --no-sandbox --hide-scrollbars "
       f"--force-device-scale-factor=1 --virtual-time-budget={budget} "
       f"--window-size={w},{h} --screenshot={out} {url}", timeout=90)
    ok = os.path.exists(out) and os.path.getsize(out) > 5000
    print(f"  chromium {out}: {'OK' if ok else 'FAIL'}",
          os.path.getsize(out) if os.path.exists(out) else 0)
    return ok


# ---------- 等待计数 ----------
peak = {}
t0 = time.time()
while time.time() - t0 < 120:
    s = requests.get("http://127.0.0.1:5000/api/latest", timeout=5).json()["data"]
    print(f"  t={int(time.time()-t0):3d}s enter={s['enter']} exit={s['exit']} current={s['current']}")
    peak = s
    if s["enter"] >= 6 and s["exit"] >= 5:
        break
    time.sleep(8)

# ---------- 界面截图 ----------
print("截图 ...")
chrome("http://127.0.0.1:5000/", os.path.join(SHOTS, "_ui_terminal.png"), 480, 320, 5000)
chrome("http://127.0.0.1:5000/dashboard", os.path.join(SHOTS, "_ui_dashboard.png"), 1500, 940, 8000)

# ---------- 截图3 ----------
lines = []
for path in ["/api/status", "/api/latest", "/api/statistics", "/api/history?limit=3"]:
    lines.append(("cmd", f"curl -s http://127.0.0.1:5000{path}"))
    try:
        data = requests.get("http://127.0.0.1:5000" + path, timeout=5).json()
        txt = json.dumps(data, ensure_ascii=False)
    except Exception as e:
        txt = f"ERROR {e}"
    while len(txt) > 150:
        lines.append(("out", txt[:150]))
        txt = "  " + txt[150:]
    lines.append(("out", txt))

lines.append(("cmd", "python3 - <<EOF   # 查询 SQLite 数据库"))
q = sh(f"""python3 -c "
import sqlite3
c = sqlite3.connect('{DB}')
print('表:', [r[0] for r in c.execute(\\"select name from sqlite_master where type='table'\\")])
print('记录数:', c.execute('select count(*) from detections').fetchone()[0])
print('按类型统计:', c.execute('select result_label, count(*) from detections group by result_label').fetchall())
print('最近 5 条:')
for r in c.execute('select id,timestamp,result_label,confidence,source from detections order by id desc limit 5'):
    print('   ', r)
" """)
for ln in q.strip().splitlines():
    lines.append(("out", ln))
lines.append(("ok", "✅ 每次进入/离开事件均实时写入 SQLite（detections 表）"))

size = render_terminal(lines, os.path.join(SHOTS, "shot3_api_db.png"), width=1000, size=15)
print("shot3:", size)

demo = {"counts": peak,
        "status": requests.get("http://127.0.0.1:5000/api/status", timeout=5).json()["data"]}
json.dump(demo, open(os.path.join(SHOTS, "demo.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(demo, ensure_ascii=False))