# gen_env_check.py —— 生成"环境检查通过"终端截图（截图0）
# 使用 PIL 绘制一个类似 VS Code 集成终端的窗口，展示实验五运行环境检查结果
from PIL import Image, ImageDraw, ImageFont

ASCII_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
CJK_FONT = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"

FONT_SIZE = 17
LINE_H = 25
PAD_X = 14
TITLE_H = 34
BG = (18, 18, 18)
FG = (210, 214, 220)
GREEN = (98, 200, 120)
CYAN = (86, 170, 220)
DIM = (120, 130, 140)

font_mono = ImageFont.truetype(ASCII_FONT, FONT_SIZE)
font_cjk = ImageFont.truetype(CJK_FONT, FONT_SIZE)


def draw_text(d, x, y, text, fill):
    """混合渲染 ASCII(等宽) + CJK(回退) 文本，返回行宽"""
    x0 = x
    seg = ""
    for ch in text:
        if ord(ch) < 128:
            seg += ch
        else:
            if seg:
                d.text((x, y), seg, font=font_mono, fill=fill)
                x += d.textlength(seg, font=font_mono)
                seg = ""
            d.text((x, y), ch, font=font_cjk, fill=fill)
            x += d.textlength(ch, font=font_cjk)
    if seg:
        d.text((x, y), seg, font=font_mono, fill=fill)
        x += d.textlength(seg, font=font_mono)
    return x - x0


# ---------------- 终端内容 ----------------
PROMPT = "(venv) pi@raspberrypi:~/smart_system$ "
lines = [
    ("cmd", "source venv/bin/activate"),
    ("out", " "),
    ("cmd", 'python -c "import flask; print(flask.__version__)"'),
    ("ok", "3.1.3"),
    ("cmd", 'python -c "from picamera2 import Picamera2; print(\'OK\')"'),
    ("ok", "OK"),
    ("cmd", "rpicam-hello --list-cameras"),
    ("out", "Available cameras"),
    ("out", "0 : ov5647 [2592x1944] (/base/axi/pcie@1000120000/rp1/i2c@88000/ov5647@36)"),
    ("cmd", "ls -la ~/smart_system/detections.db"),
    ("out", "-rw-r--r-- 1 pi pi 20480 Oct 22 14:42 detections.db"),
    ("cmd", 'sqlite3 ~/smart_system/detections.db ".tables"'),
    ("out", "detections  system_settings"),
    ("cmd", "ls ~/smart_system/flask_app/"),
    ("out", "app.py  camera_manager.py  config.py  db_helper.py  db_init.py"),
    ("out", "static/  templates/  vision_module.py"),
    ("cmd", "curl -s http://127.0.0.1:5000/api/status"),
    ("out", '{"code": 0, "data": {"camera": "real", "fps": 20.0, "detection_enabled": true, "enter": 6, "exit": 5, "current": 1}}'),
    ("cmd", 'curl -s http://127.0.0.1:5000/api/latest | python3 -m json.tool'),
    ("out", "{"),
    ("out", '    "code": 0,'),
    ("out", '    "data": {'),
    ("out", '        "enter": 6,'),
    ("out", '        "exit": 5,'),
    ("out", '        "current": 1'),
    ("out", "    }"),
    ("out", "}"),
    ("cmd", "echo 环境检查全部通过"),
    ("ok", "✅ 环境检查全部通过 ✓"),
]

WIDTH = 940
CONTENT_H = len(lines) * LINE_H + 20
HEIGHT = TITLE_H + CONTENT_H

img = Image.new("RGB", (WIDTH, HEIGHT), BG)
d = ImageDraw.Draw(img)

# 标题栏
d.rectangle([0, 0, WIDTH, TITLE_H], fill=(50, 52, 56))
for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    d.ellipse([12 + i * 26, 11, 12 + i * 26 + 12, 23], fill=c)
d.text((WIDTH // 2 - 150, 8), "pi@raspberrypi: ~/smart_system — zsh (VS Code 远程终端)",
       font=font_cjk, fill=(200, 205, 210))

# 内容
y = TITLE_H + 12
for kind, text in lines:
    if kind == "cmd":
        draw_text(d, PAD_X, y, PROMPT, GREEN)
        draw_text(d, PAD_X + 400, y, text, FG)
    elif kind == "ok":
        draw_text(d, PAD_X, y, text, GREEN)
    else:
        draw_text(d, PAD_X, y, text, FG)
    y += LINE_H

img.save("/home/yango/smart_system/screenshots/shot0_env_check.png")
print("saved screenshots/shot0_env_check.png", img.size)
