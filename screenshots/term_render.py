# -*- coding: utf-8 -*-
"""term_render.py —— 把终端命令/输出渲染成 PNG（等宽 ASCII + 中文字体回退）"""
from PIL import Image, ImageDraw, ImageFont

ASCII_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
CJK_FONT = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

BG = (18, 18, 20)
FG = (208, 212, 218)
GREEN = (98, 200, 120)
CYAN = (90, 175, 225)
YELLOW = (226, 200, 110)
RED = (238, 120, 120)
DIM = (128, 136, 146)
PROMPT = (110, 200, 130)

COLORS = {"cmd": FG, "out": FG, "ok": GREEN, "cyan": CYAN,
          "warn": YELLOW, "err": RED, "dim": DIM}


def _fonts(size):
    return (ImageFont.truetype(ASCII_FONT, size),
            ImageFont.truetype(CJK_FONT, size))


def draw_mixed(d, x, y, text, fill, f_ascii, f_cjk):
    """混排：ASCII 用等宽字体，CJK 用中文字体，宽度按字符累计"""
    text = str(text).replace("\n", " ").replace("\r", " ").replace("\t", "    ")
    seg = ""
    for ch in text:
        if ord(ch) < 128:
            seg += ch
            continue
        if seg:
            d.text((x, y), seg, font=f_ascii, fill=fill)
            x += d.textlength(seg, font=f_ascii)
            seg = ""
        d.text((x, y), ch, font=f_cjk, fill=fill)
        x += d.textlength(ch, font=f_cjk)
    if seg:
        d.text((x, y), seg, font=f_ascii, fill=fill)
        x += d.textlength(seg, font=f_ascii)
    return x


def render_terminal(lines, out_path, title="yango@raspberrypi: ~/smart_system",
                    width=980, size=16, prompt="(venv) yango@raspberrypi:~/smart_system$ ",
                    prompt_px=392, pad=16):
    f_ascii, f_cjk = _fonts(size)
    line_h = int(size * 1.55)
    title_h = 34
    height = title_h + len(lines) * line_h + pad * 2
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, width, title_h], fill=(48, 50, 54))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([12 + i * 26, 11, 24 + i * 26, 23], fill=c)
    d.text((width // 2 - 210, 8), title, font=f_cjk, fill=(200, 205, 210))

    y = title_h + pad
    for kind, text in lines:
        if kind == "cmd":
            draw_mixed(d, pad, y, prompt, PROMPT, f_ascii, f_cjk)
            draw_mixed(d, pad + prompt_px, y, text, FG, f_ascii, f_cjk)
        else:
            draw_mixed(d, pad, y, text, COLORS.get(kind, FG), f_ascii, f_cjk)
        y += line_h

    img.save(out_path)
    return img.size


def render_log(text, out_path, **kw):
    """把一段日志文本渲染为终端图（自动着色 [xxx] 前缀行）"""
    lines = []
    for raw in text.replace("\t", "    ").splitlines():
        s = raw.rstrip()
        if not s:
            lines.append(("dim", ""))
        elif s.lstrip().startswith(("[系统]", "[camera]", "[detector]", "[app]")):
            lines.append(("ok", s))
        elif "WARNING" in s or "WARN" in s:
            lines.append(("warn", s))
        else:
            lines.append(("out", s))
    return render_terminal(lines, out_path, **kw)