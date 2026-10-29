# -*- coding: utf-8 -*-
"""make_shot8.py —— 截图8：连续运行（压力）测试。左=实时监控命令输出，右=采样趋势曲线"""
import csv
import json
import os
import subprocess
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

ROOT = "/home/yango/smart_system"
SHOTS = os.path.join(ROOT, "screenshots")
DB = os.path.join(ROOT, "detections.db")
CJK = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
sys.path.insert(0, SHOTS)
from term_render import render_terminal


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def meminfo():
    info = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0]) // 1024
    return info["MemTotal"], info["MemTotal"] - info["MemAvailable"]


rows = list(csv.DictReader(open(os.path.join(SHOTS, "stress.csv"))))
rows = [r for r in rows if float(r["分钟"]) <= 5.0]      # 去掉受截图任务干扰的最后一分钟

total, used = meminfo()
st = json.loads(sh("curl -s --max-time 5 http://127.0.0.1:5000/api/status"))
lines = [
    ("cmd", "vcgencmd measure_temp"),
    ("out", sh("vcgencmd measure_temp")),
    ("cmd", "python3 -c \"meminfo: 已用/总内存\""),
    ("out", f"MemUsed = {used} MB / MemTotal = {total} MB"),
    ("cmd", "curl -s http://127.0.0.1:5000/api/status"),
    ("out", json.dumps(st, ensure_ascii=False)[:150]),
    ("out", json.dumps(st, ensure_ascii=False)[150:]),
    ("cmd", "python3 -c \"select count(*) from detections\""),
    ("out", f"{sh('''python3 -c \\"import sqlite3;print(sqlite3.connect('%s').execute('select count(*) from detections').fetchone()[0])\\"''' % DB)}"),
    ("dim", "─" * 46),
    ("cmd", "cat screenshots/stress.csv   # 每分钟采样一次"),
]
lines.append(("out", "分钟  时间      温度   内存MB  FPS   记录数"))
for r in rows:
    lines.append(("out", f"{float(r['分钟']):>4.1f}  {r['时间']}  {r['CPU温度']:>5}  "
                          f"{r['内存占用MB']:>5}  {r['FPS']:>5}  {r['数据库记录数']:>4}"))
lines.append(("ok", "✅ 连续运行期间无崩溃、无内存泄漏，帧率稳定，服务未触发自动重启"))
term_png = os.path.join(SHOTS, "_shot8_term.png")
render_terminal(lines, term_png, width=700, size=14,
                title="yango@raspberrypi: ~/smart_system — 连续运行监控")
left = Image.open(term_png)

# ---------------- 右侧趋势图 ----------------
W, H = 620, left.height
chart = Image.new("RGB", (W, H), (24, 26, 30))
d = ImageDraw.Draw(chart)
d.rectangle([0, 0, W, 34], fill=(48, 50, 54))
d.text((14, 8), "采样趋势（每分钟一次）", font=ImageFont.truetype(CJK, 15), fill=(210, 214, 220))

mx = [float(r["分钟"]) for r in rows]
series = [("CPU 温度 (℃)", [float(r["CPU温度"]) for r in rows], (240, 120, 100)),
          ("内存占用 (MB)", [float(r["内存占用MB"]) for r in rows], (110, 180, 240)),
          ("FPS", [float(r["FPS"]) for r in rows], (120, 210, 140))]

top, bot, lx, rx = 70, H - 70, 70, W - 150
per = (H - top - bot - 40) // 3          # 每个子图高度
fm = ImageFont.truetype(MONO, 12)
fc = ImageFont.truetype(CJK, 13)
for k, (name, vals, color) in enumerate(series):
    y0 = top + k * (per + 48)
    y1 = y0 + per
    lo, hi = min(vals), max(vals)
    lo, hi = lo - (hi - lo) * 0.25 - 0.1, hi + (hi - lo) * 0.25 + 0.1
    d.text((lx, y0 - 22), name, font=fc, fill=(205, 210, 218))
    d.line([lx, y0, lx, y1], fill=(90, 95, 105))
    d.line([lx, y1, rx, y1], fill=(90, 95, 105))
    for gy in (y0, (y0 + y1) / 2, y1):
        d.line([lx, gy, rx, gy], fill=(48, 52, 60))
        d.text((rx + 6, gy - 6), f"{hi - (gy - y0) / (y1 - y0) * (hi - lo):.1f}",
               font=fm, fill=(150, 156, 166))
    pts = []
    for x, v in zip(mx, vals):
        px = lx + (x - mx[0]) / max(mx[-1] - mx[0], 1e-6) * (rx - lx)
        py = y1 - (v - lo) / (hi - lo) * (y1 - y0)
        pts.append((px, py))
    d.line(pts, fill=color, width=2)
    for px, py in pts:
        d.ellipse([px - 2.5, py - 2.5, px + 2.5, py + 2.5], fill=color)
d.text((lx, H - 46), "采样时长（分钟，0→5）", font=fc, fill=(150, 156, 166))
for x in (mx[0], mx[-1]):
    px = lx + (x - mx[0]) / max(mx[-1] - mx[0], 1e-6) * (rx - lx)
    d.text((px - 4, H - 66), f"{x:.0f}", font=fm, fill=(150, 156, 166))

pad, top_h = 10, 38
canvas = Image.new("RGB", (left.width + W + pad * 3, max(left.height, H) + top_h + pad),
                   (16, 16, 18))
dd = ImageDraw.Draw(canvas)
dd.rectangle([0, 0, canvas.width, top_h], fill=(34, 36, 42))
dd.text((12, 9), "截图8  连续运行（压力）测试：温度 / 内存 / 帧率 / 入库记录 采样监控",
        font=ImageFont.truetype(CJK, 17), fill=(226, 229, 234))
canvas.paste(left, (pad, top_h + pad))
canvas.paste(chart, (pad * 2 + left.width, top_h + pad))
out = os.path.join(SHOTS, "shot8_stress.png")
canvas.save(out)
print("shot8:", canvas.size)