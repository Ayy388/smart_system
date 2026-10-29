# -*- coding: utf-8 -*-
"""functest2.py —— 改进后功能自测（真实请求，不依赖浏览器）"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5000"
TOKEN = "smart2026"
results = []


def req(path, method="GET", body=None, token=None, timeout=8):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("X-API-Token", token)
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read(30000) if "/video_feed" in url else resp.read()
            return resp.status, raw, (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, e.read(), (time.time() - t0) * 1000


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


# 1 页面
for p in ("/", "/dashboard"):
    st, raw, ms = req(p)
    record(f"页面 {p}", st == 200 and len(raw) > 1000, f"HTTP {st}, {len(raw)}B, {ms:.0f}ms")

# 2 视频流
st, raw, ms = req("/video_feed", timeout=6)
record("视频流 /video_feed", st == 200 and len(raw) > 5000, f"HTTP {st}, {len(raw)}B")

# 3 状态
st, raw, _ = req("/api/status")
d = json.loads(raw)["data"]
record("状态接口", st == 200 and d["fps"] > 5 and d["detector"]["type"] == "ssd",
       f"fps={d['fps']} detect={d['detect_fps']} 检测器={d['detector']['model']}")

# 4 统计
st, raw, _ = req("/api/statistics")
d = json.loads(raw)["data"]
record("统计接口（含今日进/出与分时）",
       st == 200 and "today_enter" in d and "hourly" in d and len(d["hourly"]) == 24,
       f"total={d['total']} 今日进/出={d['today_enter']}/{d['today_exit']} current={d['current']}")

# 5 历史（本地时间）
st, raw, _ = req("/api/history?limit=3")
rows = json.loads(raw)["data"]
h_now = time.localtime().tm_hour
h_ts = int(rows[0]["timestamp"][11:13]) if rows else -1
local_ok = (not rows) or h_ts in (h_now, h_now - 1, h_now + 1)   # 空库也算通过（无记录可校验）
record("历史接口时间已转本地", st == 200 and local_ok,
       f"最新时间={rows[0]['timestamp'] if rows else '-'} 当前小时={time.localtime().tm_hour}")

# 6 日报
st, raw, _ = req("/api/report")
d = json.loads(raw)["data"]
record("考勤/人流日报", st == 200 and d["date"] and len(d["hourly"]) == 24,
       f"日期={d['date']} 进/出={d['enter']}/{d['exit']} 高峰={d['peak_hour']}")

# 7 CSV 导出
st, raw, _ = req("/api/export.csv?limit=5")
record("CSV 导出", st == 200 and raw.decode("utf-8").startswith("id,时间"), f"{len(raw)}B")

# 8 无令牌写入应被拒绝
st, raw, _ = req("/api/reset", "POST")
record("无令牌写入被拒绝", st == 401, f"HTTP {st}")

# 9 带令牌重置
st, raw, _ = req("/api/reset", "POST", token=TOKEN)
record("带令牌重置计数", st == 200, json.loads(raw)["message"])

# 10 兼容接口
st, raw, _ = req("/api/capture", "POST", token=TOKEN)
record("兼容接口 /api/capture", st == 200, json.loads(raw)["message"])

# 11 设置读写（先记住原值，测完还原，避免污染现场配置）
_, raw0, _ = req("/api/settings")
orig = json.loads(raw0)["data"]
st, raw, _ = req("/api/settings", "POST", {"count_line_y": 245, "match_distance": 60}, token=TOKEN)
ok1 = st == 200
st2, raw2, _ = req("/api/settings")
d2 = json.loads(raw2)["data"]
record("设置保存并回读", ok1 and d2["count_line_y"] == 245, f"line={d2['count_line_y']} dist={d2['match_distance']}")

# 12 非法值
st, raw, _ = req("/api/settings", "POST", {"count_line_y": 9999}, token=TOKEN)
record("非法设置被拒绝", st == 400, f"HTTP {st}")

# 13 还原测试前的设置
req("/api/settings", "POST", {"count_line_y": orig["count_line_y"],
                              "match_distance": orig["match_distance"]}, token=TOKEN)

print("\n通过 %d/%d" % (sum(1 for _, ok, _ in results if ok), len(results)))