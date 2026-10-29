# -*- coding: utf-8 -*-
"""analyze_frames.py —— 分析 live_monitor 保存的标注帧：检测框数量、尺寸、抖动(IoU)、漏检"""
import csv
import glob
import os
import re

import cv2
import numpy as np

FR = sorted(glob.glob("/tmp/liveframes/*.jpg"))
print("frames:", len(FR))


def boxes_of(img):
    B, G, R = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    m = ((B > 190) & (G > 150) & (R < 90)).astype(np.uint8)
    m[228:252, :] = 0                     # 去掉计数线(y=240)及"COUNT LINE"文字
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < 400 or w < 12 or h < 18:
            continue                      # 过滤文字/噪点
        out.append((x, y, w, h))
    return out


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / (aw * ah + bw * bh - inter)


rec = []
prev = None
for f in FR:
    img = cv2.imread(f)
    if img is None:
        continue
    t = int(re.search(r"_(\d+)\.jpg", f).group(1))
    bs = boxes_of(img)
    best_iou = max([iou(prev[0], b) for b in bs], default=0.0) if prev and bs else 0.0
    rec.append({"t": t, "n": len(bs), "boxes": bs, "iou": round(best_iou, 3),
                "bright": round(float(img.mean()), 1)})
    prev = bs

n_with = sum(1 for r in rec if r["n"] > 0)
n_multi = sum(1 for r in rec if r["n"] > 1)
sizes = [b[2] * b[3] for r in rec for b in r["boxes"]]
hs = [b[3] for r in rec for b in r["boxes"]]
print(f"有检测框的帧: {n_with}/{len(rec)} = {n_with/max(len(rec),1)*100:.0f}%")
print(f"多框帧(可能误检): {n_multi}")
print(f"框面积 min/median/max: {min(sizes) if sizes else 0} / "
      f"{int(np.median(sizes)) if sizes else 0} / {max(sizes) if sizes else 0}")
print(f"框高 min/median/max: {min(hs) if hs else 0} / "
      f"{int(np.median(hs)) if hs else 0} / {max(hs) if hs else 0}")
ious = [r["iou"] for r in rec if r["n"] > 0]
print(f"相邻帧框 IoU: 均值 {np.mean(ious):.2f}, <0.5 的帧 {sum(1 for i in ious if i < 0.5)}/{len(ious)}")

print("\n逐帧（每第 4 帧）:")
for i, r in enumerate(rec):
    if i % 4:
        continue
    print(f"  t={r['t']:>3}s n={r['n']} iou={r['iou']:>4} bright={r['bright']} "
          f"boxes={r['boxes'][:3]}")

# 统计 CSV 事件
rows = []
with open("/tmp/live_monitor.csv") as fh:
    for row in csv.reader(fh):
        if row and row[0] and row[0][0].isdigit():
            rows.append(row)
ev = [r for r in rows if len(r) > 8 and r[8]]
print(f"\n采样 {len(rows)} 帧 span={float(rows[-1][0]):.0f}s")
print(f"计数事件 {len(ev)} 次:")
for r in ev:
    print("  t=%ss %s -> enter=%s exit=%s" % (r[0], r[8], r[1], r[2]))
fps = [float(r[4]) for r in rows]
print(f"上报 FPS: 均值 {np.mean(fps):.1f} min {min(fps)} max {max(fps)}")