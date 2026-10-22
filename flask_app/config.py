# config.py —— 智能人流统计与考勤系统 配置文件
# 统计组（实验五：Web前端开发）

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "detections.db")
DB_PATH = os.path.normpath(DB_PATH)          # 复用顶层数据库文件
# 若希望使用独立的数据库，可改为：
# DB_PATH = os.path.join(BASE_DIR, "detections.db")

# ---- 摄像头配置 ----
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 20

# ---- 计数线（图像坐标系中的 y 像素坐标）----
COUNT_LINE_Y = 240          # 默认计数线位置（对应前台设置“计数线位置”）

# ---- 目标匹配距离（像素），对应前台设置“匹配距离” ----
MATCH_DISTANCE = 50

# ---- 视频流 ----
JPEG_QUALITY = 80
FEED_FPS = 20               # MJPEG 视频流帧率

# ---- 无摄像头时自动启用模拟画面（便于无摄像头环境联调）----
# 1 = 强制模拟；0 = 强制真实摄像头；auto = 摄像头不可用时自动切换
# 也可通过环境变量 SIM 覆盖，例如：SIM=1 python app.py
SIMULATION = os.getenv("SIM", "auto")

# ---- 调试 ----
DEBUG = True
