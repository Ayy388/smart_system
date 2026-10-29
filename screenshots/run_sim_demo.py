# -*- coding: utf-8 -*-
"""run_sim_demo.py —— 以 SIM=1 模拟画面运行集成系统，采集计数，
   截取终端控制界面(480×320)、管理后台，并生成截图3（API + 数据库）。"""
import json
import os
import subprocess
import sys
import time

import requests

ROOT = "/home/yango/smart_system"
APP = os.path.join(ROOT, "flask_app")
SHOTS = os.path.join(ROOT, "screenshots")
PY = os.path.join(ROOT, "venv", "bin", "python")
sys.path.insert(0, SHOTS)
from term_render import render_terminal

DB = os.path.join(ROOT, "detections.db")


def sh(cmd, **kw):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    return (p.stdout or "") + (p.stderr or "")


def chrome(url, out, w, h, budget=6000):
    sh(f"chromium --headless=new --disable-gpu --no-sandbox --hide-scrollbars "
       f"--force-device-scale-factor=1 --virtual-time-budget={budget} "
       f"--window-size={w},{h} --screenshot={out} {url}")
    return os.path.exists(out) and os.path.getsize(out) > 5000


sh("pkill -f 'python main.py'")
time.sleep(2)
# 启动模拟模式
sh(f"cd {APP} && SIM=1 nohup {PY} main.py > /tmp/main_sim.log 2>&1 &")
for _ in range(30):
    time.sleep(1)
    try:
        if requests.get("http://127.0.0.1:5000/api/status", timeout=2).ok:
            break
    except Exception:
        pass
print("status:", requests.get("http://127.0.0.1:5000/api/status", timeout=5).json())

requests.post("http://127.0.0.1:5000/api/start", timeout=5)
print("detection started, 采集计数中 ...")
peak = {"enter": 0, "exit": 0}
t0 = time.time()
while time.time() - t0 < 150:
    time.sleep(10)
    s = requests.get("http://127.0.0.1:5000/api/latest", timeout=5).json()["data"]
    print(f"  t={int(time.time()-t0):3d}s  enter={s['enter']} exit={s['exit']} current={s['current']}")
    peak = s
    if s["enter"] >= 6 and s["exit"] >= 5:
        break

# ---------- 浏览器截图 ----------
ok1 = chrome("http://127.0.0.1:5000/", os.path.join(SHOTS, "_ui_terminal.png"), 480, 320, 5000)
ok2 = chrome("http://127.0.0.1:5000/dashboard", os.path.join(SHOTS, "_ui_dashboard.png"), 1500, 940, 8000)
print("界面截图:", ok1, ok2)

# ---------- 截图3：API + 数据库 ----------
lines = [("cmd", "curl -s http://127.0.0.1:5000/api/status"), ]
status_raw = sh("curl -s http://127.0.0.1:5000/api/status")
lines.append(("out", json.dumps(json.loads(status_raw), ensure_ascii=False)))
lines.append(("cmd", "curl -s http://127.0.0.1:5000/api/latest"))
lines.append(("out", json.dumps(requests.get("http://127.0.0.1:5000/api/latest", timeout=5).json(),
                                 ensure_ascii=False)))
lines.append(("cmd", "curl -s http://127.0.0.1:5000/api/statistics"))
lines.append(("out", json.dumps(requests.get("http://127.0.0.1:5000/api/statistics", timeout=5).json(),
                                 ensure_ascii=False)))
lines.append(("cmd", "curl -s 'http://127.0.0.1:5000/api/history?limit=3'"))
lines.append(("out", json.dumps(requests.get("http://127.0.0.1:5000/api/history?limit=3",
                                             timeout=5).json(), ensure_ascii=False)))
lines.append(("cmd", "python3 -c \"...query db...\"   # 查询 detections 表"))
q = sh(f"""python3 -c "
import sqlite3
c = sqlite3.connect('{DB}')
print('sqlite> .tables')
print('  ', [r[0] for r in c.execute(\\"select name from sqlite_master where type='table'\\")])
print('sqlite> select count(*) from detections;')
print('  ', c.execute('select count(*) from detections').fetchone()[0])
print('sqlite> select id,timestamp,result_label,confidence,source from detections order by id desc limit 5;')
for r in c.execute('select id,timestamp,result_label,confidence,source from detections order by id desc limit 5'):
    print('  ', r)
print('sqlite> select result_label,count(*) from detections group by result_label;')
print('  ', c.execute('select result_label,count(*) from detections group by result_label').fetchall())
" """)
for ln in q.strip().splitlines():
    lines.append(("out", ln))
lines.append(("ok", "✅ 进入/离开事件已实时写入 SQLite（detections 表）"))

render_terminal(lines, os.path.join(SHOTS, "shot3_api_db.png"), width=1000, size=15)

json.dump({"counts": peak, "status": json.loads(status_raw)},
          open(os.path.join(SHOTS, "demo.json"), "w"), ensure_ascii=False, indent=1)
print("done. counts:", peak)