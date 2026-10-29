# -*- coding: utf-8 -*-
"""live_recorder.py —— 轻量记录器：只轮询 API + 每 5 秒抓一帧，几乎不占 CPU"""
import csv
import json
import os
import time
import urllib.request

DUR = int(os.environ.get("DUR", "600"))
OUT = os.environ.get("OUT", "/tmp/live_eval.csv")
FRAME_DIR = os.environ.get("FRAMES", "/tmp/evalframes")
os.makedirs(FRAME_DIR, exist_ok=True)


def get_json(path):
    with urllib.request.urlopen("http://127.0.0.1:5000" + path, timeout=5) as r:
        return json.loads(r.read().decode())["data"]


def grab_frame(path):
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/video_feed", timeout=6) as r:
            buf = b""
            while True:
                chunk = r.read(8192)
                if not chunk:
                    return False
                buf += chunk
                a = buf.find(b"\xff\xd8")
                b = buf.find(b"\xff\xd9")
                if a != -1 and b > a:
                    with open(path, "wb") as f:
                        f.write(buf[a:b + 2])
                    return True
    except Exception:
        return False


rows, t0, last_frame, prev = [], time.time(), 0, None
with open(OUT, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["t", "enter", "exit", "current", "tracks", "fps", "detect_fps", "event"])
    while time.time() - t0 < DUR:
        try:
            st = get_json("/api/status")
        except Exception:
            time.sleep(1)
            continue
        ev = ""
        if prev:
            if st["enter"] != prev["enter"]:
                ev += "ENTER "
            if st["exit"] != prev["exit"]:
                ev += "EXIT "
        row = [round(time.time() - t0, 1), st["enter"], st["exit"], st["current"],
               st["tracks"], st["fps"], st["detect_fps"], ev.strip()]
        rows.append(row)
        w.writerow(row)
        fh.flush()
        prev = st
        now = time.time() - t0
        if now - last_frame >= 5:
            grab_frame(os.path.join(FRAME_DIR, f"f_{int(now):04d}.jpg"))
            last_frame = now
        time.sleep(0.5)

print("recorded", len(rows), "samples in", int(time.time() - t0), "s")
enters = sum(1 for r in rows if "ENTER" in r[7])
exits = sum(1 for r in rows if "EXIT" in r[7])
print(f"期间计数变化: ENTER {enters} 次, EXIT {exits} 次, 最终 {rows[-1][1]}/{rows[-1][2]}")
if rows:
    fps = [r[5] for r in rows if r[5]]
    print(f"视频帧率 平均 {sum(fps)/len(fps):.1f}, 最小 {min(fps)}")