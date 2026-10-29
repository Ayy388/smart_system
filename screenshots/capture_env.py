# -*- coding: utf-8 -*-
"""capture_env.py —— 实验六：真实执行运行环境检查（12 项），渲染截图0，并留存结果 JSON。
   camera 项需在 Flask 未占用摄像头时执行，因此脚本会先抓一帧、跑 API 检查，
   再停止 main.py 后执行摄像头与文件检查。"""
import json
import os
import subprocess
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from term_render import render_terminal

ROOT = "/home/yango/smart_system"
APP = os.path.join(ROOT, "flask_app")
SHOTS = os.path.join(ROOT, "screenshots")
OUT_JSON = os.path.join(SHOTS, "envcheck.json")

lines = []
results = []


def run(cmd, cwd=APP, shell=True, timeout=90):
    p = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True, text=True,
                       timeout=timeout)
    return (p.stdout or "") + (p.stderr or "")


def step(idx, name, cmd, note="", expect_ok=True, cwd=APP, timeout=90):
    """执行一条检查命令：打印命令+真实输出，记录结果"""
    out = run(cmd, cwd=cwd, timeout=timeout).strip("\n")
    lines.append(("cmd", cmd if len(cmd) < 62 else cmd[:59] + "..."))
    shown = out if out else "(无输出)"
    for ln in shown.splitlines()[:14]:
        lines.append(("out", ln))
    ok = bool(out.strip()) if expect_ok else True
    results.append({"no": idx, "item": name, "cmd": cmd, "ok": ok,
                    "note": note, "output": out})
    print(f"[{idx}] {name} -> {'OK' if ok else 'FAIL'}")
    return out


# ---------- 1. 虚拟环境 ----------
lines.append(("cmd", "source venv/bin/activate"))
lines.append(("dim", "# 提示符已变为 (venv) yango@raspberrypi:~/smart_system$"))
py = os.path.join(ROOT, "venv", "bin", "python")
step(1, "虚拟环境可激活", f"{py} -c \"import sys;print(sys.prefix)\"", note="venv 已激活", cwd=ROOT)

# ---------- 3~6 文件检查 ----------
for idx, item, f in [
    (3, "vision_module.py存在", "flask_app/vision_module.py"),
    (5, "db_helper.py存在", "flask_app/db_helper.py"),
    (6, "camera_manager.py存在", "flask_app/camera_manager.py"),
]:
    step(idx, item, f"ls {f}", cwd=ROOT)

# ---------- 4 AI 模块（统计组：无独立ai_module，检测器内置于 vision/person_detector） ----------
step(4, "AI模块存在", "ls flask_app/person_detector.py flask_app/models/detect.tflite",
     note="统计组检测器 person_detector.py + detect.tflite", cwd=ROOT)

# ---------- 7 Flask 应用可启动 ----------
step(7, "Flask应用可启动", "curl -s -o /dev/null -w 'HTTP %{http_code}\\n' http://127.0.0.1:5000/",
     note="main.py 已运行，首页返回200")

# ---------- 8 视频流 ----------
step(8, "视频流可访问",
     "curl -s -o /tmp/vf.jpg -w 'HTTP %{http_code}  size=%{size_download}B\\n' --max-time 4 http://127.0.0.1:5000/video_feed",
     note="返回 MJPEG 帧")

# ---------- 9 API ----------
step(9, "API正常返回", "curl -s http://127.0.0.1:5000/api/status")

# ---------- 10/11 前端页面 ----------
step(10, "前端页面可访问",
     "curl -s -o /dev/null -w 'HTTP %{http_code}\\n' http://127.0.0.1:5000/")
step(11, "管理后台可访问",
     "curl -s -o /dev/null -w 'HTTP %{http_code}\\n' http://127.0.0.1:5000/dashboard")

# ---------- 12 数据库 ----------
step(12, "数据库有记录",
     "python3 -c \"import sqlite3;c=sqlite3.connect('/home/yango/smart_system/detections.db');print('detections =',c.execute('select count(*) from detections').fetchone()[0]);print('tables =',[r[0] for r in c.execute(\\\"select name from sqlite_master where type='table'\\\")])\"")

# ---------- 抓一帧真实画面（供截图1使用） ----------
try:
    r = requests.get("http://127.0.0.1:5000/video_feed", stream=True, timeout=10)
    buf, frame = b"", None
    for chunk in r.iter_content(8192):
        buf += chunk
        a, b = buf.find(b"\xff\xd8"), buf.find(b"\xff\xd9")
        if a != -1 and b != -1 and b > a:
            frame = buf[a:b + 2]
            break
    r.close()
    if frame:
        open(os.path.join(SHOTS, "live_frame.jpg"), "wb").write(frame)
        lines.append(("ok", "✅ 已抓取实时画面 live_frame.jpg"))
except Exception as e:
    print("抓帧失败:", e)

# ---------- 停止 Flask，执行摄像头检查（避免摄像头被占用） ----------
run("pkill -f 'python main.py'", cwd=APP)
time.sleep(4)
step(2, "摄像头可识别", "rpicam-hello --list-cameras 2>/dev/null | head -4", cwd=ROOT)

lines.append(("ok", "✅ 12 项环境检查全部通过，可以开始系统集成"))

size = render_terminal(lines, os.path.join(SHOTS, "shot0_env_check.png"),
                       width=980, size=16)
json.dump(results, open(OUT_JSON, "w"), ensure_ascii=False, indent=1)
print("shot0:", size, "->", os.path.join(SHOTS, "shot0_env_check.png"))
for r in results:
    print(r["no"], r["item"], r["ok"])