# -*- coding: utf-8 -*-
"""compose_docs.py —— 截图9：部署手册 / 操作指南 文档预览（Markdown 渲染后截图拼接）"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SHOTS = "/home/yango/smart_system/screenshots"
CJK = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"


def crop_content(path, view_h=None):
    im = Image.open(path).convert("RGB")
    a = np.array(im)
    bg = a[-1, -1].astype(int)
    rows = np.where((np.abs(a.astype(int) - bg).sum(axis=2) > 12).any(axis=1))[0]
    bottom = int(rows.max()) + 20 if len(rows) else im.height
    im = im.crop((0, 0, im.width, min(bottom, im.height)))
    if view_h:
        im = im.crop((0, 0, im.width, min(view_h, im.height)))
    return im


def panel(img, title, width=650):
    im = img.resize((width, int(img.height * width / img.width)), Image.LANCZOS)
    bar = 30
    out = Image.new("RGB", (width, im.height + bar), (40, 42, 48))
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, width, bar], fill=(46, 48, 54))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([10 + i * 22, 9, 20 + i * 22, 19], fill=c)
    d.text((88, 7), title, font=ImageFont.truetype(CJK, 15), fill=(210, 214, 220))
    out.paste(im, (0, bar))
    return out


deploy = crop_content("/tmp/doc_deploy.png", view_h=1500)
guide = crop_content("/tmp/doc_guide.png", view_h=1500)
p1 = panel(deploy, "docs/部署手册.md  —  智能人流统计与考勤系统部署手册")
p2 = panel(guide, "docs/操作指南.md  —  用户操作指南")

pad, top = 10, 40
H = max(p1.height, p2.height)
W = p1.width + p2.width + pad * 3
canvas = Image.new("RGB", (W, H + top + pad), (16, 16, 18))
d = ImageDraw.Draw(canvas)
d.rectangle([0, 0, W, top], fill=(34, 36, 42))
d.text((12, 10), "截图9  部署文档：docs/部署手册.md 与 docs/操作指南.md（已完成）",
       font=ImageFont.truetype(CJK, 17), fill=(226, 229, 234))
canvas.paste(p1, (pad, top + pad))
canvas.paste(p2, (pad * 2 + p1.width, top + pad))
out = os.path.join(SHOTS, "shot9_docs.png")
canvas.save(out)
print("shot9:", canvas.size, p1.size, p2.size)