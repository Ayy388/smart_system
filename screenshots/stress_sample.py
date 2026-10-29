# -*- coding: utf-8 -*-
"""stress_sample.py —— 连续运行（压力）测试采样：每分钟记录温度/内存/FPS/记录数
   用法：python3 stress_sample.py [采样次数]  → 输出 screenshots/stress.csv"""
import csv
import os
import subprocess
import sys
import time
import urllib.request

ROOT = "/home/yango/smart_system"
SHOTS = os.path.join(ROOT, "screenshots")
DB = os.path.join(ROOT, "detections.db")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 45


def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return ""


def temp():
    t = sh("vcgencmd measure_temp")
    return t.replace("temp=", "").replace("'C", "") if t else ""


def mem_used():
    info = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])          # kB
    used_kb = info["MemTotal"] - info["MemAvailable"]
    return round(used_kb / 1024)


def load1():
    return open("/proc/loadavg").read().split()[0]


def api(path):
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000" + path, timeout=5) as r:
            import json
            return json.loads(r.read().decode())["data"]
    except Exception:
        return {}


def db_count():
    import sqlite3
    try:
        c = sqlite3.connect(DB)
        n = c.execute("select count(*) from detections").fetchone()[0]
        c.close()
        return n
    except Exception:
        return -1


rows = []
t0 = time.time()
for i in range(N + 1):
    st = api("/api/status")
    rows.append({
        "分钟": round((time.time() - t0) / 60, 1),
        "时间": time.strftime("%H:%M:%S"),
        "CPU温度": temp(),
        "内存占用MB": mem_used(),
        "FPS": round(float(st.get("fps", 0)), 1) if st else 0,
        "数据库记录数": db_count(),
        "负载": load1(),
    })
    with open(os.path.join(SHOTS, "stress.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(rows[-1], flush=True)
    if i < N:
        time.sleep(60)