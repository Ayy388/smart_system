# test_counter.py —— 离线验证计数去抖逻辑（不接摄像头）
import sys
sys.path.insert(0, "/home/yango/smart_system/flask_app")

import numpy as np
import config
from vision_module import PeopleCounter

config.COUNT_HYSTERESIS = 28
config.COUNT_COOLDOWN = 3.0
config.COUNT_CONFIRM_FRAMES = 3
LINE = 240
BOX_W, BOX_H = 60, 150


def run_case(name, ys, expect, dt=1 / 8.0):
    c = PeopleCounter(line_y=LINE, simulation=True, axis="y")
    c.hysteresis, c.cooldown, c.min_hits = 28, 3.0, 2
    c.enter_count = c.exit_count = 0
    t = 1000.0
    events = []
    for i, y in enumerate(ys):
        x = 320 - BOX_W // 2
        det = [(x, int(y - BOX_H / 2), BOX_W, BOX_H, 0.9)]
        frame = np.zeros((480, 640, 3), np.uint8)
        ev = c.update(det, frame=frame, now=t)
        events += [(k, i) for k, _, _ in ev]
        t += dt
    got = (c.enter_count, c.exit_count)
    ok = "PASS" if got == expect else "FAIL"
    print(f"[{ok}] {name}: enter={got[0]} exit={got[1]} (期望 {expect[0]}/{expect[1]}) 事件={events}")
    return got == expect


def walk(start, end, n):
    return [start + (end - start) * i / (n - 1) for i in range(n)]


ok = True
# 1) 正常穿过一次：上 → 下
ok &= run_case("正常进入一次", walk(120, 380, 40), (1, 0))
# 2) 下 → 上 离开一次
ok &= run_case("正常离开一次", walk(380, 120, 40), (0, 1))
# 3) 站在计数线上抖动 ±4 px（旧版会疯狂计数）
ok &= run_case("线上抖动±4px", [LINE + 4 * np.sin(i / 2) for i in range(80)], (0, 0))
# 4) 抖动 ±18 px（越过迟滞带边界）
ok &= run_case("线上抖动±18px", [LINE + 18 * np.sin(i / 2) for i in range(80)], (0, 0))
# 5) 快速通过（3 帧穿过，旧版容易漏计）
ok &= run_case("快速通过(3帧)", [120, 240, 380] + [380] * 6, (1, 0))
# 6) 走进过渡带又退回（没有真正过线）
ok &= run_case("进带后退回", walk(120, 236, 20) + walk(236, 120, 20), (0, 0))
# 7) 来回各一次（间隔足够长）
ys = walk(120, 380, 30) + walk(380, 380, 30) + walk(380, 120, 30)
ok &= run_case("进入→停留→离开", ys, (1, 1))
# 8) 同一人 1 秒内快速折返（冷却应挡住第二次）
ys = walk(120, 380, 8) + walk(380, 120, 8)
ok &= run_case("1秒内折返(冷却)", ys, (1, 0))
# 9) 两人同时同向通过
c = PeopleCounter(line_y=LINE, simulation=True, axis="y")
c.hysteresis, c.cooldown, c.min_hits = 28, 3.0, 2
t, events = 1000.0, 0
for i in range(40):
    y = 120 + (380 - 120) * i / 39
    dets = [(100, y - 75, 60, 150, 0.9), (480, y - 75, 60, 150, 0.9)]
    frame = np.zeros((480, 640, 3), np.uint8)
    events += len(c.update(dets, frame=frame, now=t))
    t += 1 / 8.0
print(f"[{'PASS' if c.enter_count == 2 else 'FAIL'}] 两人同时进入: enter={c.enter_count} (期望 2)")
ok &= c.enter_count == 2

# 10) 同一人同时给出两个框（衣服/手臂被单独检出）→ 合并成一条轨迹，只算一次
c = PeopleCounter(line_y=LINE, simulation=True, axis="y")
c.hysteresis, c.cooldown, c.min_hits = 28, 3.0, 2
t = 2000.0
for i in range(40):
    y = 20 + i * 10
    dets = [(240, y, 160, 200, 0.62), (280, y + 80, 70, 90, 0.52)]
    frame = np.zeros((480, 640, 3), np.uint8)
    c.update(dets, frame=frame, now=t)
    t += 0.25
p1 = c.enter_count == 1 and c.exit_count == 0
p2 = len(c.tracks) == 1
print(f"[{'PASS' if p1 else 'FAIL'}] 衣服/手臂重复框只算一人: enter={c.enter_count} exit={c.exit_count} (期望 1/0)")
print(f"[{'PASS' if p2 else 'FAIL'}] 重复框合并为一条轨迹: 轨迹数={len(c.tracks)} (期望 1)")
ok &= p1 and p2

# 10.5) 轨迹丢失后，同外观的目标出现在线另一侧 → 不能靠“复活”凭空计一次
c = PeopleCounter(line_y=LINE, simulation=True, axis="y")
c.hysteresis, c.cooldown, c.min_hits = 28, 3.0, 2
frame = np.dstack([np.full((480, 640), 90, np.uint8)] * 3)
t = 2000.0
for _ in range(3):                       # 在线下方建立轨迹
    c.update([(290, 45, 60, 150, 0.9)], frame=frame, now=t)
    t += 0.1
for _ in range(2):                       # 丢失 2 帧
    c.update([], frame=frame, now=t)
    t += 0.1
for _ in range(12):                      # 同外观目标突然出现在线上方
    c.update([(290, 305, 60, 150, 0.9)], frame=frame, now=t)
    t += 0.1
p_rev = (c.enter_count, c.exit_count) == (0, 0)
print(f"[{'PASS' if p_rev else 'FAIL'}] 复活不跨线凭空计数: enter={c.enter_count} exit={c.exit_count} (期望 0/0)")
ok &= p_rev

# 11) 竖线模式：从左到右记一次进入，再从右到左记一次离开
c = PeopleCounter(line_y=320, simulation=True, axis="x")
c.hysteresis, c.cooldown, c.min_hits = 28, 3.0, 2
t = 3000.0
for i in range(40):                      # 左 → 右
    x = 120 + i * 12
    c.update([(x, 150, 160, 200, 0.6)], frame=None, now=t)
    t += 0.2
p1 = (c.enter_count, c.exit_count) == (1, 0)
t += 5.0
for i in range(40):                      # 右 → 左
    x = 600 - i * 12
    c.update([(x, 150, 160, 200, 0.6)], frame=None, now=t)
    t += 0.2
p2 = (c.enter_count, c.exit_count) == (1, 1)
print(f"[{'PASS' if p1 else 'FAIL'}] 竖线 左→右 记一次进入: {c.enter_count}/{c.exit_count} (期望 1/1 中的进入)")
print(f"[{'PASS' if p2 else 'FAIL'}] 竖线 右→左 记一次离开: {c.enter_count}/{c.exit_count} (期望 1/1)")
ok &= p1 and p2

print("\n总体:", "全部通过" if ok else "存在失败用例")
sys.exit(0 if ok else 1)