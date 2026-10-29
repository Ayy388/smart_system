# -*- coding: utf-8 -*-
"""boundary_test.py —— 实验六 边界测试：强光/暗光（真实摄像头，软件固定曝光）
   与 快速移动/遮挡（模拟画面构造），输出 shot6 / shot7 拼图与测试数据。"""
import json
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/home/yango/smart_system"
APP = os.path.join(ROOT, "flask_app")
SHOTS = os.path.join(ROOT, "screenshots")
CJK = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

sys.path.insert(0, APP)
os.chdir(APP)
import config
from person_detector import MotionDetector
from vision_module import PeopleCounter, process_frame

result = {}


def to_bgr(arr):
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR) if arr.shape[2] == 3 else arr


def label(img, text, sub=""):
    """左上角贴标题条"""
    out = img.copy()
    h, w = out.shape[:2]
    cv2.rectangle(out, (0, 0), (w, 46), (30, 30, 34), -1)
    cv2.putText(out, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    if sub:
        cv2.putText(out, sub, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 217, 255), 1)
    return out


# ==========================================================
# 一、强光 / 暗光（真实摄像头）
# ==========================================================
def real_extremes():
    from picamera2 import Picamera2
    picam = Picamera2()
    cfg = picam.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
    picam.configure(cfg)
    picam.start()
    time.sleep(2.5)

    conds = [
        ("normal", "正常光照（自动曝光）", {"Brightness": 0.0}),
        ("bright", "强光/过曝（ISP 亮度 +0.4）", {"Brightness": 0.4}),
        ("dark", "暗光/欠曝（ISP 亮度 -0.5）", {"Brightness": -0.5}),
    ]
    frames, stats = {}, {}
    for key, desc, ctl in conds:
        try:
            picam.set_controls(ctl)
        except Exception as e:
            print("set_controls:", e)
        time.sleep(1.6)
        seq = [to_bgr(picam.capture_array()) for _ in range(10)]
        det = MotionDetector(min_area=3000, var_threshold=45)
        dets = [len(det.detect(f)) for f in seq]
        # 前 3 帧用于建立背景，统计后 7 帧
        frames[key] = seq[-1]
        g = cv2.cvtColor(seq[-1], cv2.COLOR_BGR2GRAY)
        stats[key] = {"desc": desc, "mean": round(float(seq[-1].mean()), 1),
                      "sat": round(float((g >= 245).mean() * 100), 1),
                      "dark": round(float((g <= 15).mean() * 100), 1),
                      "det_avg": round(float(np.mean(dets[3:])), 2)}
        print(key, stats[key])
    picam.stop()
    return frames, stats


frames, stats = real_extremes()
result["real"] = stats

counter = PeopleCounter(simulation=False)
panels = []
for key, ttl in [("normal", "① 正常光照"), ("bright", "② 强光直射/过曝"),
                 ("dark", "③ 暗光/欠曝")]:
    f = counter.annotate(frames[key].copy(), draw_tracks=False)
    s = stats[key]
    panels.append(label(f, ttl, f"画面平均亮度 {s['mean']}   过曝像素 {s['sat']}%   暗部像素 {s['dark']}%"))


def grid(panels, cols, out, title=""):
    h, w = panels[0].shape[:2]
    pad = 8
    rows = (len(panels) + cols - 1) // cols
    canvas = np.full((rows * h + (rows - 1) * pad, cols * w + (cols - 1) * pad, 3),
                     22, np.uint8)
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        canvas[r * (h + pad):r * (h + pad) + h, c * (w + pad):c * (w + pad) + w] = p
    if title:
        # 顶部中文标题（PIL 绘制，避免 OpenCV 不支持中文）
        pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        t = Image.new("RGB", (pil.width, 38), (30, 30, 34))
        d = ImageDraw.Draw(t)
        d.text((12, 8), title, font=ImageFont.truetype(CJK, 17), fill=(230, 232, 236))
        out_img = Image.new("RGB", (pil.width, pil.height + 38))
        out_img.paste(t, (0, 0))
        out_img.paste(pil, (0, 38))
        out_img.save(out)
        return out_img.size
    Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)).save(out)
    return (canvas.shape[1], canvas.shape[0])


print(grid(panels, 3, os.path.join(SHOTS, "shot6_light.png"),
           "截图6  边界测试①：正常 / 强光过曝 / 暗光欠曝（真实摄像头 OV5647，ISP 亮度参数模拟极端光照）"))

# ==========================================================
# 二、快速移动 / 遮挡（模拟画面构造）
# ==========================================================
from camera_manager import SimulatedCamera

sim = SimulatedCamera(640, 480)
for p in sim.people:
    p["vy"] *= 5.0
    p["vx"] *= 5.0
counter = PeopleCounter(simulation=True)
events_fast, fast_frames = [], []
for i in range(160):
    f = sim.read_frame()
    f2, ev = process_frame(f, counter)
    events_fast += ev
    if i in (40, 80, 120):
        fast_frames.append(f2.copy())
result["fast_move"] = {"events": len(events_fast),
                       "enter": counter.enter_count, "exit": counter.exit_count,
                       "detail": events_fast[:12]}

# 遮挡：模拟画面中在目标前方立一块“柱子”，遮住目标的 60%
class OccludedSim(SimulatedCamera):
    def read_frame(self):
        f = super().read_frame()
        cv2.rectangle(f, (250, 120), (330, 460), (70, 70, 78), -1)   # 遮挡物
        cv2.putText(f, "OCCLUDER", (248, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (200, 200, 210), 1)
        return f

sim2 = OccludedSim(640, 480)
counter2 = PeopleCounter(simulation=True)
events_occ, occ_frames = [], []
for i in range(160):
    f = sim2.read_frame()
    f2, ev = process_frame(f, counter2)
    events_occ += ev
    if i in (40, 80, 120):
        occ_frames.append(f2.copy())
result["occlusion"] = {"events": len(events_occ),
                       "enter": counter2.enter_count, "exit": counter2.exit_count}

p_fast = label(fast_frames[1], "① 快速移动（模拟目标速度 × 5）",
               f"跟踪保持，跨线事件 {result['fast_move']['events']} 次  计数 IN {counter.enter_count} / OUT {counter.exit_count}")
p_occ = label(occ_frames[1], "② 部分遮挡（遮挡物遮住目标约 60%）",
              f"遮挡期间轨迹短暂丢失，跨线事件 {result['occlusion']['events']} 次  计数 IN {counter2.enter_count} / OUT {counter2.exit_count}")
print(grid([p_fast, p_occ], 2, os.path.join(SHOTS, "shot7_move_occlusion.png"),
           "截图7  边界测试②：快速移动 / 部分遮挡（SIM 模拟画面构造极端条件）"))

json.dump(result, open(os.path.join(SHOTS, "boundary.json"), "w"),
          ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False, indent=1))