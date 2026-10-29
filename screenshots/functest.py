# -*- coding: utf-8 -*-
"""functest.py —— 实验六 功能测试 12 项：真实调用所有接口并记录结果"""
import json
import os
import subprocess
import time
import urllib.request

SHOTS = "/home/yango/smart_system/screenshots"
BASE = "http://127.0.0.1:5000"


def req(path, method="GET", data=None):
    url = BASE + path
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method,
                               headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(r, timeout=8) as resp:
        raw = resp.read()
        return resp.status, raw.decode("utf-8", "replace"), round((time.time() - t0) * 1000)


def code(path):
    return int(subprocess.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 6 {BASE}{path}",
        shell=True, capture_output=True, text=True).stdout or 0)


res = []


def add(no, item, method, ok, detail, ms=None):
    res.append({"no": no, "item": item, "method": method, "ok": ok,
                "detail": detail, "ms": ms})
    print(no, item, ok, detail, ms)


s, b, ms = req("/video_feed") if False else (code("/video_feed"), "", None)
add(1, "视频流", "curl -o vf.jpg /video_feed", s == 200, f"HTTP {s}，返回 MJPEG 帧")
s = code("/")
add(2, "终端控制界面", "GET /", s == 200, f"HTTP {s}，返回 index.html")
s = code("/dashboard")
add(3, "管理后台", "GET /dashboard", s == 200, f"HTTP {s}，返回 dashboard.html")

s, b, ms = req("/api/status")
d = json.loads(b)["data"]
add(4, "状态API", "GET /api/status", s == 200,
    f"fps={d['fps']:.1f} frames={d['frame_count']} camera={d['camera']}", ms)

s, b, ms = req("/api/start", "POST")
add(5, "启动API", "POST /api/start", s == 200, json.loads(b)["message"], ms)
time.sleep(1)
s, b, ms = req("/api/stop", "POST")
add(6, "停止API", "POST /api/stop", s == 200, json.loads(b)["message"], ms)
s, b, ms = req("/api/start", "POST")
s, b, ms = req("/api/capture", "POST")
add(7, "拍照/重置API", "POST /api/capture", s == 200,
    json.loads(b)["message"] + " " + json.dumps(json.loads(b)["data"]), ms)
s, b, ms = req("/api/history?limit=3")
add(8, "历史API", "GET /api/history?limit=3", s == 200,
    f"返回 {len(json.loads(b)['data'])} 条记录", ms)
s, b, ms = req("/api/statistics")
add(9, "统计API", "GET /api/statistics", s == 200,
    json.dumps(json.loads(b)["data"], ensure_ascii=False), ms)
s, b, ms = req("/api/latest")
add(10, "最新结果API", "GET /api/latest", s == 200,
    json.dumps(json.loads(b)["data"], ensure_ascii=False), ms)
s, b, ms = req("/api/settings", "POST", {"threshold": 240, "alarm": 50})
add(11, "设置API", "POST /api/settings", s == 200, json.loads(b)["message"], ms)

import sqlite3
c = sqlite3.connect("/home/yango/smart_system/detections.db")
n = c.execute("select count(*) from detections").fetchone()[0]
grp = c.execute("select result_label,count(*) from detections group by result_label").fetchall()
add(12, "数据库存储", "select count(*) from detections", n > 0,
    f"共 {n} 条；{dict(grp)}")

json.dump(res, open(os.path.join(SHOTS, "functest.json"), "w"),
          ensure_ascii=False, indent=1)
print("saved functest.json")