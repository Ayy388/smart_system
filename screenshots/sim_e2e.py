# -*- coding: utf-8 -*-
"""sim_e2e.py —— 用模拟摄像头跑通“检测→跟踪→计数”全链路，验证一次通过只记一次"""
import os
import sys
import time

os.environ["SIM"] = "1"
sys.path.insert(0, "/home/yango/smart_system/flask_app")

import numpy as np                                    # noqa: E402
import config                                         # noqa: E402
from camera_manager import CameraManager              # noqa: E402
from vision_module import PeopleCounter               # noqa: E402

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 40
cam = CameraManager()
counter = PeopleCounter(line_y=240, simulation=True, axis="y")
print("检测器:", counter.detector_info)

events = []
t0 = time.time()
frames = 0
while time.time() - t0 < SECONDS:
    frame = cam.read_frame()
    if frame is None:
        time.sleep(0.05)
        continue
    dets = counter.detect_people(frame)
    ev = counter.update(dets, frame=frame)
    for kind, tid, info in ev:
        events.append((round(time.time() - t0, 1), kind, tid, info["score"]))
        print(f"  [{time.time()-t0:5.1f}s] {kind:<5} track={tid} score={info['score']}")
    frames += 1
    time.sleep(0.10)          # 10 fps

print(f"\n运行 {SECONDS:.0f}s，{frames} 帧，检测器 {counter.detector_info['type']}")
print(f"事件 {len(events)} 条：进入 {counter.enter_count}，离开 {counter.exit_count}")
per_track = {}
for _, kind, tid, _ in events:
    per_track.setdefault(tid, []).append(kind)
print("每条轨迹的事件:", per_track)
dup = {k: v for k, v in per_track.items() if len(v) > 2}
print("重复计数轨迹(>2 次):", dup if dup else "无")