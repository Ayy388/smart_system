# -*- coding: utf-8 -*-
"""live_monitor.py —— 现场评估：从 /video_feed 连续取帧，量化检测与计数表现
   - 运动量（帧间差分，排除标注框像素）
   - 标注框像素数（app 画出的检测框/跟踪框）
   - 计数变化事件、时延
   - 每 5 秒存一帧到 /tmp/liveframes/"""
import csv
import json
import os
import time
import urllib.request

import cv2
import numpy as np

OUT_DIR = "/tmp/liveframes"
CSV = "/tmp/live_monitor.csv"
DURATION = int(os.environ.get("DUR", "300"))
os.makedirs(OUT_DIR, exist_ok=True)


def status():
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/api/status", timeout=3) as r:
            return json.loads(r.read().decode())["data"]
    except Exception:
        return {}


stream = urllib.request.urlopen("http://127.0.0.1:5000/video_feed", timeout=20)
buf = b""
prev = None
prev_st = status()
rows = []
t0 = time.time()
last_save = 0
boxes_present_since = None


def read_frame():
    global buf
    while True:
        chunk = stream.read(4096)
        if not chunk:
            return None
        buf += chunk
        a = buf.find(b"\xff\xd8")
        b = buf.find(b"\xff\xd9")
        if a != -1 and b != -1 and b > a:
            jpg = buf[a:b + 2]
            buf = buf[b + 2:]
            f = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if f is not None:
                return f


with open(CSV, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["t", "enter", "exit", "current", "fps", "box_px", "motion", "bright", "event"])
    while time.time() - t0 < DURATION:
        f = read_frame()
        if f is None:
            break
        # 标注框颜色 BGR(B=255,G=217,R=0)
        B, G, R = f[:, :, 0].astype(int), f[:, :, 1].astype(int), f[:, :, 2].astype(int)
        boxmask = (B > 190) & (G > 150) & (R < 90)
        box_px = int(boxmask.sum())
        # 运动量：去掉标注区域后与上一帧的差分
        if prev is not None:
            keep = ~(boxmask | prevbox)
            motion = float(np.abs(f.astype(int) - prev.astype(int))[keep].mean())
        else:
            motion = 0.0
        st = status()
        ev = ""
        if st and prev_st:
            if st.get("enter", 0) != prev_st.get("enter", 0):
                ev += "ENTER+%d " % (st["enter"] - prev_st["enter"])
            if st.get("exit", 0) != prev_st.get("exit", 0):
                ev += "EXIT+%d " % (st["exit"] - prev_st["exit"])
        rows.append([round(time.time() - t0, 2), st.get("enter"), st.get("exit"),
                     st.get("current"), round(float(st.get("fps", 0)), 1),
                     box_px, round(motion, 2), round(float(f.mean()), 1), ev.strip()])
        w.writerow(rows[-1])
        fh.flush()
        if len(rows) % 25 == 0:
            w.writerow([])
            fh.flush()
        prev, prevbox = f, boxmask
        prev_st = st
        # 每 5 秒存帧（框出现时加密到 1 秒）
        now = time.time() - t0
        if box_px > 30 and (now - last_save >= 1.0):
            cv2.imwrite(os.path.join(OUT_DIR, f"box_{int(now):03d}.jpg"), f)
            last_save = now
        elif now - last_save >= 5.0:
            cv2.imwrite(os.path.join(OUT_DIR, f"idle_{int(now):03d}.jpg"), f)
            last_save = now
        time.sleep(0.2)

print("done rows:", len(rows))