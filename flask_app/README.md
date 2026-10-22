# 智能人流统计与考勤系统 —— Flask 后端与 Web 前端

统计组 · 实验五：Web 前端开发（终端控制界面 + 管理后台 + 前后端联调）

## 目录结构

```
flask_app/
├── app.py                  # Flask 主程序（页面路由 + API + 视频处理线程）
├── config.py               # 配置文件（摄像头/计数线/匹配距离等）
├── camera_manager.py       # 摄像头管理（Picamera2 / OpenCV / 模拟画面）
├── vision_module.py        # 视觉处理（人体检测 + 目标跟踪 + 计数线跨越判定）
├── db_helper.py            # 数据库操作（进入/离开事件入库、统计、设置）
├── templates/
│   ├── index.html          # 终端控制界面（3.5英寸横屏 480×320 适配）
│   └── dashboard.html      # 管理后台（统计卡片 + ECharts 图表 + 历史表格）
└── static/
    ├── css/
    └── js/echarts.min.js   # 本地 ECharts 库（CDN 不可达时使用）
```

## 运行方法

```bash
cd ~/smart_system/flask_app
source ../venv/bin/activate

# ① 真实摄像头（Raspberry Pi 5 + OV5647，Picamera2 自动识别）
python app.py

# ② 模拟画面模式（无摄像头或希望演示“人流走动计数”效果）
SIM=1 python app.py
```

浏览器访问：

| 地址 | 页面 |
| --- | --- |
| `http://<树莓派IP>:5000/` | 终端控制界面（3.5寸横屏） |
| `http://<树莓派IP>:5000/dashboard` | 管理后台 |

## API 一览

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/video_feed` | GET | MJPEG 视频流（含计数线/检测框标注） |
| `/api/status` | GET | 运行状态（fps、帧数、检测开关、当前人数等） |
| `/api/latest` | GET | 最新计数 `{enter, exit, current}` |
| `/api/statistics` | GET | 历史统计 `{total, today, by_label:{enter,exit}}` |
| `/api/history?limit=20` | GET | 历史进入/离开记录 |
| `/api/start` | POST | 启动人流统计 |
| `/api/stop` | POST | 停止人流统计 |
| `/api/capture` | POST | 重置计数 |
| `/api/settings` | POST | 保存设置（计数线位置 threshold / 匹配距离 alarm） |

## 说明

- 计数原理：背景差分（MOG2）检测运动目标 → 质心跟踪（匹配距离内关联）
  → 质心跨越计数线时，上→下记“进入”，下→上记“离开”，事件写入数据库。
- 计数线位置与匹配距离可在管理后台“系统设置”中调整，保存后写入数据库，
  下次启动自动加载。
- 前端 ECharts 使用本地 `static/js/echarts.min.js`，不依赖外网 CDN。
