# -*- coding: utf-8 -*-
"""make_shot1.py —— 截图1：main.py 启动日志 + /video_feed 实时视频流"""
import os

from PIL import Image, ImageDraw, ImageFont

from term_render import render_log

ROOT = "/home/yango/smart_system"
SHOTS = os.path.join(ROOT, "screenshots")
LOG = "/tmp/main_real.log"
CJK = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

# ---- 1) 日志渲染（过滤 libcamera 的 INFO/WARN 噪声）----
keep = []
for ln in open(LOG, encoding="utf-8", errors="replace").read().splitlines():
    s = ln.rstrip()
    if not s:
        continue
    if " INFO " in s or " WARN " in s or "v4l2_pixelformat" in s:
        continue
    if s.startswith(" * ") or s.startswith("\x1b"):
        s = s.replace("\x1b[31m", "").replace("\x1b[0m", "").replace("\x1b[1m", "")
        s = s.replace("\x1b[33m", "")
    keep.append(s)

log_txt = "\n".join(keep)
term_png = os.path.join(SHOTS, "_shot1_term.png")
render_log("\n".join(["$ source venv/bin/activate", "$ python main.py", ""] + keep),
           term_png, width=880, size=15,
           title="yango@raspberrypi: ~/smart_system/flask_app — main.py")
left = Image.open(term_png)

# ---- 2) 实时画面 ----
frame = Image.open(os.path.join(SHOTS, "live_frame.jpg"))
fw = 640
frame = frame.resize((fw, int(frame.height * fw / frame.width)), Image.LANCZOS)

# ---- 3) 横向拼接 ----
pad = 12
label_h = 30
W = left.width + pad * 3 + fw
H = max(left.height, frame.height + label_h) + pad * 2 + label_h
canvas = Image.new("RGB", (W, H), (10, 10, 12))
d = ImageDraw.Draw(canvas)
f = ImageFont.truetype(CJK, 15)

d.rectangle([0, 0, W, label_h + 6], fill=(40, 42, 46))
d.text((12, 6), "① python main.py 启动日志（多线程：采集线程 + Flask 主线程）", font=f, fill=(210, 215, 220))
d.text((left.width + pad * 2, 6), "② http://<树莓派IP>:5000/video_feed 实时视频流（黄线=计数线）",
       font=f, fill=(210, 215, 220))

canvas.paste(left, (pad, label_h + 6 + pad))
canvas.paste(frame, (left.width + pad * 2, label_h + 6 + pad))

out = os.path.join(SHOTS, "shot1_main_startup.png")
canvas.save(out)
print("saved", out, canvas.size, "log lines:", len(keep))