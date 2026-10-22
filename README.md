# Smart System — 智能人流统计与考勤系统

[![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi-5-red)](https://www.raspberrypi.com/products/raspberry-pi-5/)
[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-black)](https://flask.palletsprojects.com/)
[![TensorFlow Lite](https://img.shields.io/badge/TensorFlow%20Lite-2.21-orange)](https://www.tensorflow.org/lite)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

基于 **Raspberry Pi 5** + **CSI 摄像头**（OV5647）的实时人流统计系统。通过 SSD MobileNet 深度学习模型检测进出人群，结合质心跟踪与计数线跨越判定，实现 **进入/离开人数实时统计**，数据存入 SQLite 数据库，通过 **Flask Web 应用**提供终端控制界面和管理后台。

支持 **3.5 英寸 SPI 触摸屏**（MHS-3.5 / ILI9486 + XPT2046），触摸屏和 HDMI 显示器**自动切换**。

---

## 目录结构

```
smart_system/
├── flask_app/
│   ├── app.py                 # Flask 主程序（页面路由 + API + 视频流）
│   ├── config.py              # 配置文件
│   ├── camera_manager.py      # 摄像头管理（Picamera2 / OpenCV / 模拟源）
│   ├── vision_module.py       # 视觉处理（检测 + 跟踪 + 计数线判定）
│   ├── person_detector.py     # 人体检测器（SSD MobileNet TFLite）
│   ├── db_helper.py           # 数据库操作（事件入库 + 统计 + 设置）
│   ├── db_init.py             # 数据库初始化
│   ├── models/
│   │   └── detect.tflite      # SSD MobileNet V1 COCO 人体检测模型
│   ├── templates/
│   │   ├── index.html         # 终端控制界面（480×320 横屏适配）
│   │   └── dashboard.html     # 管理后台（ECharts 图表 + 历史记录）
│   ├── static/
│   │   └── js/echarts.min.js  # ECharts（本地引用，无需 CDN）
│   ├── run.sh                 # 启动脚本
│   └── smart-system.service   # systemd 服务（开机自启）
├── run.sh                     # 项目根目录快捷启动
└── screenshots/               # 演示截图
```

## 功能特性

| 模块 | 说明 |
|------|------|
| 人体检测 | SSD MobileNet V1（COCO，TFLite），约 25 ms/帧，0.55 置信度阈值 |
| 目标跟踪 | 质心跟踪 + 匈牙利匹配，支持跟踪丢失重连 |
| 进出判定 | 黄色计数线跨越检测：上→下 = 进入，下→上 = 离开 |
| 视频流 | MJPEG，含实时检测框与计数标注 |
| 数据持久化 | SQLite，记录每次进入/离开事件及时间戳 |
| Web 前端 | 终端界面（480×320 横屏）+ 管理后台（饼图/柱状图/历史表/设置） |
| 模拟模式 | `SIM=1` 切换模拟画面（无摄像头时演示用） |
| 触摸屏支持 | MHS-3.5 英寸 SPI 屏 + HDMI 自动切换 |
| 系统服务 | systemd 开机自启 Flask + Chromium kiosk |

## 快速开始

### 环境要求

- Raspberry Pi 5（树莓派 5）
- Raspberry Pi OS（Debian Trixie，内核 6.18+）
- CSI 摄像头（OV5647）
- Python 3.13+（推荐使用 venv）

### 安装

```bash
cd ~/smart_system
source venv/bin/activate
pip install flask opencv-python tensorflow picamera2
```

### 运行

```bash
# 真实摄像头（默认）
./run.sh

# 模拟画面演示（无摄像头环境）
./run.sh sim
```

浏览器访问：
- 终端控制界面：`http://<树莓派IP>:5000/`
- 管理后台：`http://<树莓派IP>:5000/dashboard`

### 触摸屏（MHS-3.5）

系统已集成 MHS-3.5 英寸 SPI 触摸屏驱动，支持 HDMI/SPI **自动切换**：
- HDMI 连接显示器时：桌面正常在 HDMI 显示
- HDMI 断开时：自动在 SPI 触摸屏上以 Kiosk 模式显示网页

安装驱动：
```bash
git clone https://github.com/goodtft/LCD-show.git
cd LCD-show && sudo ./MHS35-show
sudo reboot
```

systemd 服务：
```bash
# 开机自启
sudo systemctl enable smart-system.service  # Flask 服务
sudo systemctl enable spi-kiosk.service     # 触摸屏 kiosk
sudo systemctl enable xpt2046-penirq-kick.service  # 触摸修复
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/video_feed` | GET | MJPEG 视频流（含检测框与计数线） |
| `/api/status` | GET | 运行状态（fps、帧数、检测开关、当前人数） |
| `/api/latest` | GET | 最新计数 `{enter, exit, current}` |
| `/api/statistics` | GET | 历史统计 `{total, today, by_label}` |
| `/api/history?limit=20` | GET | 历史进入/离开记录 |
| `/api/start` | POST | 启动人流统计 |
| `/api/stop` | POST | 停止人流统计 |
| `/api/capture` | POST | 重置计数 |
| `/api/settings` | POST | 保存设置 `{threshold, alarm}` |

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | HTML5 / CSS3（Flexbox + 响应式）/ JavaScript（fetch AJAX）/ ECharts 5 |
| 后端 | Flask 3 / Jinja2 / MJPEG 视频流 |
| 视觉 | OpenCV / SSD MobileNet V1（TFLite）/ MOG2 背景差分（模拟模式） |
| 数据库 | SQLite（事件记录 + 系统设置持久化） |
| 硬件 | 树莓派 5 / Pi Camera 2（OV5647）/ MHS-3.5 触摸屏（ILI9486 + XPT2046） |
| 部署 | systemd 服务 / Chromium kiosk / HDMI-SPI 自动切换 |

## 许可证

MIT License