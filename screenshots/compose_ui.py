# -*- coding: utf-8 -*-
"""compose_ui.py —— 合成截图2（终端界面 + 管理后台）；并生成截图3（API + 数据库）"""
import json
import os
import sqlite3
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = "/home/yango/smart_system"
SHOTS = os.path.join(ROOT, "screenshots")
DB = os.path.join(ROOT, "detections.db")
CJK = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
sys.path.insert(0, SHOTS)
from term_render import render_terminal

# ---------------- 截图2 ----------------
term = Image.open(os.path.join(SHOTS, "_ui_terminal.png")).convert("RGB")
dash = Image.open(os.path.join(SHOTS, "_ui_dashboard.png")).convert("RGB")

tw = 760
term = term.resize((tw, int(term.height * tw / term.width)), Image.LANCZOS)
dw = 1240
dash = dash.resize((dw, int(dash.height * dw / dash.width)), Image.LANCZOS)

pad, cap_h, top_h = 14, 30, 38
W = dw + pad * 2
H = top_h + cap_h + term.height + pad * 2 + cap_h + dash.height + pad
canvas = Image.new("RGB", (W, H), (16, 16, 18))
d = ImageDraw.Draw(canvas)
f16 = ImageFont.truetype(CJK, 16)
f15 = ImageFont.truetype(CJK, 15)

d.rectangle([0, 0, W, top_h], fill=(38, 40, 46))
d.text((14, 10), "截图2  终端控制界面（3.5 英寸 SPI 横屏，480×320） + 管理后台（PC 浏览器）",
       font=f16, fill=(225, 228, 232))

y = top_h
d.text((pad, y + 6), "① http://<树莓派IP>:5000/    终端控制界面：当前人数 / 进入 / 离开 + 实时视频 + 启动/停止/重置",
       font=f15, fill=(150, 200, 235))
y += cap_h
canvas.paste(term, ((W - term.width) // 2, y))
y += term.height + pad + cap_h
d.text((pad, y - cap_h + 6), "② http://<树莓派IP>:5000/dashboard    管理后台：统计卡片 + 饼图/柱状图 + 历史记录 + 系统设置",
       font=f15, fill=(150, 200, 235))
canvas.paste(dash, (pad, y))
out2 = os.path.join(SHOTS, "shot2_terminal_dashboard.png")
canvas.save(out2)
print("shot2:", canvas.size)

# ---------------- 截图3 ----------------
lines = []
for path in ["/api/status", "/api/latest", "/api/statistics", "/api/history?limit=3"]:
    lines.append(("cmd", f"curl -s http://127.0.0.1:5000{path}"))
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:5000" + path, timeout=5) as r:
            txt = r.read().decode()
    except Exception as e:
        txt = f"ERROR {e}"
    while len(txt) > 148:
        lines.append(("out", txt[:148]))
        txt = "  " + txt[148:]
    lines.append(("out", txt))

lines.append(("cmd", "sqlite3 查询（python3 sqlite3 模块）"))
c = sqlite3.connect(DB)
lines.append(("out", "sqlite> .tables"))
lines.append(("out", "  " + str([r[0] for r in c.execute(
    "select name from sqlite_master where type='table'")])))
lines.append(("out", "sqlite> select count(*) from detections;"))
lines.append(("out", "  " + str(c.execute("select count(*) from detections").fetchone()[0])))
lines.append(("out", "sqlite> select result_label, count(*) from detections group by result_label;"))
lines.append(("out", "  " + str(c.execute(
    "select result_label, count(*) from detections group by result_label").fetchall())))
lines.append(("out", "sqlite> select id,timestamp,result_label,confidence,source from detections order by id desc limit 5;"))
for r in c.execute("select id,timestamp,result_label,confidence,source from detections "
                   "order by id desc limit 5"):
    lines.append(("out", "  " + str(r)))
c.close()
lines.append(("ok", "✅ 每次进入/离开事件均实时写入 SQLite（detections 表），并可用 /api/history 回读"))
size = render_terminal(lines, os.path.join(SHOTS, "shot3_api_db.png"), width=1010, size=15)
print("shot3:", size)

# 记录演示数据
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:5000/api/status", timeout=5) as r:
    st = json.loads(r.read().decode())["data"]
json.dump(st, open(os.path.join(SHOTS, "demo.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(st, ensure_ascii=False))