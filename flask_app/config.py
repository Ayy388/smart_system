# config.py —— 智能人流统计与考勤系统 配置文件
# 统计组（第七次课：系统集成与发布测试）

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "detections.db")
DB_PATH = os.path.normpath(DB_PATH)          # 复用顶层数据库文件

# ---- 摄像头配置 ----
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 20

# ---- 计数线（图像坐标系中的 y 像素坐标）----
# 按现场画面定标：计数线落在 y=220（画面 46% 高度处），
# 上侧 46% 为“离开 OUT”区，下侧 54% 为“进入 IN”区（可由后台“计数线位置”微调）
# 计数线方向："x" = 竖线（人左右过线，按 x 坐标判定）；"y" = 横线（人上下过线）
COUNT_AXIS = "x"
COUNT_LINE_X = CAMERA_WIDTH // 2                # 竖线默认在屏幕正中（640/2 = 320）
COUNT_LINE_Y = 220                              # 横线位置（切回 "y" 时使用）
COUNT_OUT_RATIO = round(COUNT_LINE_Y / CAMERA_HEIGHT, 3)

# ---- 计数去抖参数（第七次课现场调优后新增）----
# 迟滞带：计数线两侧各 H 像素为“过渡带”，质心在带内抖动不计数
COUNT_HYSTERESIS = 28
# 确认帧：越过计数带后，还要连续多少帧仍在另一侧才算真正跨线
COUNT_CONFIRM_FRAMES = 3
# 挂起重置：跨越后若 1.5 秒内没被确认（又晃回去 / 被冷却挡住），本次作废
COUNT_PENDING_TIMEOUT = 1.5
# 冷却时间：同一轨迹两次计数的最小间隔（秒），防止一人反复计数
COUNT_COOLDOWN = 3.0

# ---- 目标匹配 ----
MATCH_DISTANCE = 60         # 最近邻匹配距离（像素），对应前台设置“匹配距离”
TRACK_MAX_LOST = 40         # 轨迹丢失多少帧后删除（按检测帧率计，约 3.5 s）
TRACK_MIN_HITS = 2          # 轨迹命中多少帧才允许计数（4fps 下 4 帧=1 秒，太快的人会漏计）

# ---- 检测频率（与视频帧率解耦，降低 CPU 占用）----
DETECT_FPS = 8              # 每秒执行多少次模型推理（8fps ≈ 单核 81%，视频仍按 FEED_FPS 输出）
DETECT_THREADS = 2          # 推理线程数：2 线程 45ms/帧（8fps 下 CPU 约 81%），1 线程 88ms 但更省电

# ---- 视频流 ----
JPEG_QUALITY = 68
FEED_FPS = 14               # MJPEG 视频流帧率（SSH 隧道/WiFi 下 18fps 会堆积延迟）

# ---- 开机自动开始统计（kiosk/壁挂场景需要，重启后不用再点“启动”）----
AUTO_START_DETECTION = True

# ---- 接口鉴权（写操作）----
# 留空表示不鉴权（仅限调试）；生产请在环境变量或此处设置令牌
API_TOKEN = os.getenv("API_TOKEN", "smart2026")

# ---- 数据库 ----
DB_RETAIN_DAYS = 90         # 超过多少天的历史记录可清理（调用 /api/prune 手动执行）

# ---- 无摄像头时自动启用模拟画面（便于无摄像头环境联调）----
# 1 = 强制模拟；0 = 强制真实摄像头；auto = 摄像头不可用时自动切换
SIMULATION = os.getenv("SIM", "auto")

# ---- 调试 ----
DEBUG = False