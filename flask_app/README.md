# 智能人流统计与考勤系统 —— Flask 后端与 Web 前端

统计组 · 实验五（Web 前端）+ 实验六（系统集成与发布测试）

## 一、结构

```
flask_app/
├── main.py                 # 统一主程序（集成入口：采集线程 + Web 服务）
├── app.py                  # Flask 路由 + API + 采集线程/检测线程
├── config.py               # 配置（摄像头、计数线、去抖参数、检测频率、令牌）
├── camera_manager.py       # 摄像头管理（Picamera2 / OpenCV / 模拟画面）
├── person_detector.py      # 人体检测（SSD TFLite / 背景差分回退）
├── vision_module.py        # 跟踪 + 计数线状态机 + 标注
├── db_helper.py            # 数据库（事件入库、统计、日报、导出、清理）
├── models/                 # detect.tflite + labelmap.txt
├── tests/test_counter.py   # 计数去抖单元测试（9 个用例）
├── templates/              # index.html（3.5寸屏） / dashboard.html（后台）
└── static/js/echarts.min.js
```

## 二、运行

```bash
cd ~/smart_system
./venv/bin/python flask_app/main.py        # 生产运行（waitress）
# 或
sudo systemctl start smart_system           # 作为系统服务运行

SIM=1 ./venv/bin/python flask_app/main.py   # 模拟画面（无人也不依赖摄像头）
```

依赖（venv 内）：`flask`、`opencv-python`、`numpy`、`picamera2`（系统包）、
`ai-edge-litert`（TFLite 运行时）、`waitress`（生产 WSGI）。

## 三、线程模型

```
┌──────────────┐  最新原始帧  ┌──────────────┐
│ 采集线程      │ ──────────▶ │ 检测线程      │
│ Picamera2    │             │ SSD 推理       │
│ 标注+JPEG编码 │ ◀────────── │ 跟踪/计数/入库 │
└──────┬───────┘   轨迹状态   └──────────────┘
       │ MJPEG
       ▼
  浏览器 / 3.5 寸屏
```

- 采集线程：稳定 14 fps 输出视频，**不做推理**；无浏览器观看时自动跳过标注与 JPEG 编码；
- 检测线程：按 `DETECT_FPS`（默认 8）限频推理（2 线程，45 ms/帧），与视频互不阻塞；
- Web 线程：waitress 8 线程，读写共享状态均加锁。

实测（Pi 5 4GB，640×480）：视频 14 fps、检测 8 fps、整机单核占用 81%（含 2 路观众）、SoC 50 ℃。

## 四、计数算法（第七次课现场实测后重写）

1. **检测**：SSD MobileNet（int8，300×300）只取 person 类，阈值 0.5；再做三层去重
   （同一人的衣服/手臂常被单独检出一个框）：
   - 框级：小框含在大框里（交集/小框面积 > 0.5 或中心落入）+ 面积差明显 → 丢弃小框；
   - 框级：IoU > 0.45 视为同一框；
   - 轨迹级：两条轨迹的框互相包含/几乎重合 → 合并为一条（保留命中多的）。
2. **跟踪**：速度预测 + 距离/尺寸门限做一对一匹配；丢失后用 HSV 直方图相似度重识别，
   避免同一人被切成多个 ID（实测旧版 8 分钟产生 50 个 ID）。
3. **计数线**：默认是**竖线**，位于屏幕正中（`COUNT_AXIS="x"`、`COUNT_LINE_X=320`），
   左→右 记“进入”、右→左 记“离开”；后台可切换成横线（`COUNT_AXIS="y"`，位置 `COUNT_LINE_Y=220`）。
   竖线与横线共用同一套去抖状态机，只是判定坐标从 y 换成 x。
4. **跨线判定**（状态机）：
   - 计数线两侧各 `COUNT_HYSTERESIS=28 px` 为过渡带，带内抖动不计数；
   - 越过带后还需连续 `COUNT_CONFIRM_FRAMES=3` 帧停在另一侧才确认；
   - 同一轨迹两次计数至少间隔 `COUNT_COOLDOWN=3 s`；
   - 跨越后 1.5 s 内没被确认（又晃回去）本次作废。
5. 事件写入 `detections` 表：`result_label = enter / exit`，`detail_info` 记录 track_id、score。

> 旧版只比较“上一帧在哪一侧”，人在线上抖动会反复 enter/exit（实测 2 秒 6 条记录），
> 上述四道闸门即为修复。

## 五、API

写操作需带 `X-API-Token`（默认 `smart2026`，见 `config.API_TOKEN`），可用 `?token=` 代替。

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/video_feed` | GET | MJPEG 视频流（含计数带/检测框标注） |
| `/api/status` | GET | 运行状态：fps、detect_fps、帧数、检测器类型、轨迹数、计数 |
| `/api/latest` | GET | 会话计数 `{enter, exit, current, tracks}` |
| `/api/statistics` | GET | 全量统计：total、by_label、today、today_enter/exit、current、24 小时分时 |
| `/api/history?limit=20` | GET | 历史记录（时间已转本地时区） |
| `/api/report?date=YYYY-MM-DD` | GET | 考勤/人流日报：分时进出、首末时间、高峰时段 |
| `/api/export.csv` | GET | 导出历史 CSV |
| `/api/settings` | GET/POST | 计数线方向 `count_axis`（x 竖线 / y 横线）、位置、匹配距离（POST 需令牌，含参数校验） |
| `/api/start` `/api/stop` | POST | 启动 / 停止统计 |
| `/api/reset` | POST | 重置会话计数（历史保留）；`/api/capture` 为兼容别名 |
| `/api/prune?days=90` | POST | 清理过期历史 |

## 六、数据与时区

- 数据库 `timestamp` 统一存 **UTC**（`CURRENT_TIMESTAMP`），查询时用
  `datetime(timestamp,'localtime')` 转本地，避免“今日统计”在 0~8 点算错、后台时间差 8 小时；
- 表上建有 `timestamp`、`result_label` 索引；
- 清理：`/api/prune` 或 `python db_helper.py`。

## 七、测试

```bash
cd flask_app && ../venv/bin/python tests/test_counter.py   # 计数逻辑 9 个用例
python3 ../screenshots/functest2.py                        # 接口自测（13 项）
```