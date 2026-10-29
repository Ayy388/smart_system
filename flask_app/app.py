# app.py —— Flask 主程序（统计组：智能人流统计与考勤系统）
# 实验五：Web 前端开发 —— 终端控制界面 + 管理后台 + 前后端联调
# 第七次课：系统集成与发布 —— 检测/视频解耦、FPS 真实统计、接口鉴权、日报与导出
import collections
import functools
import json
import threading
import time

import cv2
import numpy as np
from flask import (Flask, Response, jsonify, render_template, request,
                   send_file)

import config
from camera_manager import CameraManager
from vision_module import PeopleCounter, process_frame
from db_helper import DBHelper

cv2.setNumThreads(2)          # 降低 OpenCV 多线程对 CPU 的争抢

app = Flask(__name__)

# ---------------- 全局状态 ----------------
camera = CameraManager()
_line_default = (config.COUNT_LINE_X if getattr(config, "COUNT_AXIS", "y") == "x"
                 else config.COUNT_LINE_Y)
counter = PeopleCounter(line_y=_line_default,
                        match_distance=config.MATCH_DISTANCE,
                        simulation=camera.simulation,
                        axis=getattr(config, "COUNT_AXIS", "y"))
db = DBHelper()

state = {
    "running": False,            # 视频采集线程是否运行
    "detection_enabled": bool(getattr(config, "AUTO_START_DETECTION", True)),  # 是否启用检测/计数
    "fps": 0.0,                  # 视频帧率（滑动窗口）
    "detect_fps": 0.0,           # 检测帧率
    "frame_count": 0,
    "started_at": time.time(),
}
state_lock = threading.Lock()

latest_jpeg = None               # 最近一帧标注后的 JPEG 字节
jpeg_lock = threading.Lock()
viewers = 0                      # 正在看视频流的连接数：没人看时跳过标注与 JPEG 编码
viewers_lock = threading.Lock()

stop_event = threading.Event()
capture_thread = None
detect_thread = None

latest_raw = None                 # 最新原始帧（供检测线程使用）
raw_lock = threading.Lock()
raw_ts = [0.0]

frame_ts = collections.deque(maxlen=40)      # 视频帧时间戳
detect_ts = collections.deque(maxlen=40)     # 检测时间戳


def _rate(ts):
    """根据时间戳队列计算真实帧率"""
    if len(ts) < 2:
        return 0.0
    span = ts[-1] - ts[0]
    return round((len(ts) - 1) / span, 1) if span > 0 else 0.0


def token_required(fn):
    """写接口鉴权：校验 X-API-Token 头 / token 参数；未配置令牌时放行"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if config.API_TOKEN:
            tok = (request.headers.get("X-API-Token")
                   or request.args.get("token"))
            if not tok:
                body = request.get_json(silent=True) or request.form
                tok = (body or {}).get("token")
            if tok != config.API_TOKEN:
                return jsonify({"code": 401, "message": "未授权：缺少或错误的访问令牌"}), 401
        return fn(*args, **kwargs)
    return wrapper


def load_settings():
    """从数据库读取设置并应用到计数器"""
    try:
        axis = str(db.get_setting("count_axis", getattr(config, "COUNT_AXIS", "y"))).lower()
        counter.set_axis(axis)
        default_line = (getattr(config, "COUNT_LINE_X", config.CAMERA_WIDTH // 2)
                        if axis == "x" else config.COUNT_LINE_Y)
        line = db.get_setting("count_line_y", default_line)
        dist = db.get_setting("match_distance", config.MATCH_DISTANCE)
        counter.set_line(int(line))
        counter.set_match_distance(int(dist))
        print(f"[app] 已加载设置：计数线方向={'竖线(左右)' if axis == 'x' else '横线(上下)'} "
              f"位置={line} 匹配距离={dist}")
    except Exception as e:
        print(f"[app] 加载设置失败: {e}")


# ---------------- 视频处理线程 ----------------
def capture_loop():
    """采集线程：只负责取帧、标注和编码（不再做推理），保证视频流帧率稳定"""
    global latest_raw
    frame_interval = 1.0 / max(config.FEED_FPS, 1)
    while not stop_event.is_set():
        t0 = time.time()
        frame = camera.read_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        with state_lock:
            enabled = state["detection_enabled"]

        # 交给检测线程一张原图（检测在独立线程里做，不阻塞视频）
        with raw_lock:
            latest_raw = frame.copy()
            raw_ts[0] = t0

        # 没人看视频流时不需要标注和 JPEG 编码，直接省掉这部分 CPU
        with viewers_lock:
            has_viewer = viewers > 0
        if has_viewer:
            # 用最近一次检测结果标注（框最多滞后一个检测周期）
            frame = counter.annotate(frame, draw_tracks=enabled)
            ok, buf = cv2.imencode(".jpg", frame,
                                   [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])
            if ok:
                global latest_jpeg
                with jpeg_lock:
                    latest_jpeg = buf.tobytes()

        now = time.time()
        frame_ts.append(now)
        with state_lock:
            state["frame_count"] += 1
            state["fps"] = _rate(frame_ts)

        dt = now - t0
        if dt < frame_interval:
            time.sleep(frame_interval - dt)


def detect_loop():
    """检测线程：按 DETECT_FPS 限频做推理/跟踪/计数，与视频线程解耦"""
    detect_interval = 1.0 / max(config.DETECT_FPS, 1)
    while not stop_event.is_set():
        t0 = time.time()
        with state_lock:
            enabled = state["detection_enabled"]
        with raw_lock:
            frame = latest_raw

        if enabled and frame is not None:
            events = []
            try:
                detections = counter.detect_people(frame)
                events = counter.update(detections, frame=frame)
            except Exception as e:
                print(f"[app] 处理帧异常: {e}")

            for kind, tid, info in events:
                db.insert_detection(image_path=None, result_label=kind,
                                    confidence=float(info.get("score", 1.0) or 1.0),
                                    detail_info=info, source="live")

            detect_ts.append(time.time())
            with state_lock:
                state["detect_fps"] = _rate(detect_ts)

        dt = time.time() - t0
        if dt < detect_interval:
            time.sleep(detect_interval - dt)
        else:
            time.sleep(0.01)


def start_capture_thread():
    global capture_thread, detect_thread
    if capture_thread is not None and capture_thread.is_alive():
        return
    stop_event.clear()
    capture_thread = threading.Thread(target=capture_loop, daemon=True,
                                      name="capture")
    capture_thread.start()
    detect_thread = threading.Thread(target=detect_loop, daemon=True,
                                     name="detect")
    detect_thread.start()


def process_frame_safe(frame):
    """运行检测并捕获异常，避免单帧异常导致线程退出"""
    try:
        return process_frame(frame, counter)
    except Exception as e:
        print(f"[app] 处理帧异常: {e}")
        return frame, []


def jpeg_placeholder():
    """尚无可用帧时发送的占位图（深色背景 + 提示文字）"""
    img = np.zeros((config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3), np.uint8)
    cv2.putText(img, "Waiting for camera...", (120, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 217, 255), 2)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])[1].tobytes()


def gen_video(fps_arg=None):
    """MJPEG 视频流生成器

    - 带观众计数：无人观看时采集线程跳过标注/编码；
    - 支持 ?fps= 降频（弱网/隧道场景），默认 config.FEED_FPS；
    - 画面没变化时不重复发送同一帧，空闲时几乎不占带宽；
    - 慢客户端靠“只发最新帧”自动丢帧，不会无限堆积（但 SSH 隧道仍会缓冲，建议直连局域网 IP）。
    """
    global viewers
    try:
        fps = float(fps_arg) if fps_arg is not None else float(config.FEED_FPS)
    except (TypeError, ValueError):
        fps = config.FEED_FPS
    fps = max(2.0, min(float(config.FEED_FPS), fps))
    interval = 1.0 / fps

    with viewers_lock:
        viewers += 1
    last_sent = None
    try:
        while True:
            with jpeg_lock:
                jpeg = latest_jpeg
            if jpeg is None:
                jpeg = jpeg_placeholder()
            if jpeg is not last_sent:          # 画面没变就不重发（省带宽）
                last_sent = jpeg
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + jpeg + b"\r\n")
            time.sleep(interval)
    finally:
        with viewers_lock:
            viewers = max(0, viewers - 1)


# ---------------- 页面路由 ----------------
@app.route("/")
def index():
    """终端控制界面（3.5英寸横屏）"""
    return render_template("index.html", api_token=config.API_TOKEN)


@app.route("/dashboard")
def dashboard():
    """管理后台"""
    return render_template("dashboard.html", api_token=config.API_TOKEN)


# ---------------- 视频流 ----------------
@app.route("/video_feed")
def video_feed():
    # 参数在这里取，生成器里不再访问 request（Flask 流式响应上下文已弹出）
    return Response(gen_video(request.args.get("fps")),
                    mimetype="multipart/x-mixed-replace; boundary=frame",
                    headers={"Cache-Control": "no-store"})


# ---------------- API ----------------
@app.route("/api/status")
def api_status():
    with state_lock:
        s = dict(state)
    s["running"] = capture_thread is not None and capture_thread.is_alive()
    s["detect_thread"] = detect_thread is not None and detect_thread.is_alive()
    s["simulation"] = camera.simulation
    s["camera"] = "simulation" if camera.simulation else "real"
    snap = counter.snapshot()
    s.update({k: snap[k] for k in ("enter", "exit", "current")})
    s["tracks"] = snap["tracks"]
    s["detector"] = counter.detector_info
    s["viewers"] = viewers
    s["uptime"] = int(time.time() - state["started_at"])
    return jsonify({"code": 0, "data": s})


@app.route("/api/latest")
def api_latest():
    return jsonify({"code": 0, "data": counter.snapshot()})


@app.route("/api/statistics")
def api_statistics():
    """全量统计（历史来自数据库，current 为入库累计的在场人数）"""
    stats = db.get_statistics()
    stats["session"] = counter.snapshot()
    stats["detector"] = counter.detector_info
    return jsonify({"code": 0, "data": stats})


@app.route("/api/history")
def api_history():
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20
    rows = db.get_history(limit=limit)
    data = [{"id": r["id"], "timestamp": r["ts"], "result_label": r["result_label"],
             "confidence": r["confidence"], "source": r["source"]} for r in rows]
    return jsonify({"code": 0, "data": data})


@app.route("/api/report")
def api_report():
    """考勤/人流日报：?date=YYYY-MM-DD（默认今天，本地时间）"""
    return jsonify({"code": 0, "data": db.get_daily_report(request.args.get("date"))})


@app.route("/api/export.csv")
def api_export():
    """导出历史记录 CSV"""
    csv_text = db.history_csv(limit=int(request.args.get("limit", 5000)))
    resp = Response(csv_text, mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = 'attachment; filename="people_history.csv"'
    return resp


@app.route("/api/start", methods=["POST"])
@token_required
def api_start():
    with state_lock:
        state["detection_enabled"] = True
    start_capture_thread()
    return jsonify({"code": 0, "message": "已启动人流统计",
                    "data": {"detection_enabled": True}})


@app.route("/api/stop", methods=["POST"])
@token_required
def api_stop():
    with state_lock:
        state["detection_enabled"] = False
    return jsonify({"code": 0, "message": "已停止人流统计",
                    "data": {"detection_enabled": False}})


@app.route("/api/reset", methods=["POST"])
@token_required
def api_reset():
    """重置会话计数（历史记录保留）"""
    counter.reset()
    return jsonify({"code": 0, "message": "计数已重置", "data": counter.snapshot()})


@app.route("/api/capture", methods=["POST"])
@token_required
def api_capture():
    """兼容旧接口：等价于 /api/reset（历史版本名为 capture）"""
    counter.reset()
    return jsonify({"code": 0, "message": "计数已重置（兼容接口 /api/capture）",
                    "data": counter.snapshot()})


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify({"code": 0, "data": {
        "count_axis": counter.axis,
        "count_line_y": counter.line_y,
        "match_distance": counter.match_distance,
        "hysteresis": counter.hysteresis,
        "cooldown": counter.cooldown,
    }})


@app.route("/api/settings", methods=["POST"])
@token_required
def api_settings():
    try:
        body = request.get_json(silent=True) or request.form
        # 兼容旧字段名 threshold / alarm
        axis = str(body.get("count_axis", counter.axis)).lower()
        if axis not in ("x", "y"):
            return jsonify({"code": 1, "message": "计数线方向只能是 x（竖线）或 y（横线）"}), 400
        counter.set_axis(axis)
        limit = config.CAMERA_WIDTH if axis == "x" else config.CAMERA_HEIGHT
        line = int(body.get("count_line_y", body.get("threshold", counter.line_y)))
        dist = int(body.get("match_distance", body.get("alarm", counter.match_distance)))
        if not (0 < line < limit):
            return jsonify({"code": 1, "message": f"计数线位置需在 1~{limit - 1}"}), 400
        if not (5 <= dist <= 300):
            return jsonify({"code": 1, "message": "匹配距离需在 5~300 之间"}), 400
        counter.set_line(line)
        counter.set_match_distance(dist)
        db.set_setting("count_axis", axis)
        db.set_setting("count_line_y", line)
        db.set_setting("match_distance", dist)
        return jsonify({"code": 0, "message": "设置已保存",
                        "data": {"count_axis": axis, "count_line_y": line,
                                 "match_distance": dist}})
    except Exception as e:
        return jsonify({"code": 1, "message": f"保存失败: {e}"}), 400


@app.route("/api/prune", methods=["POST"])
@token_required
def api_prune():
    """清理过期历史（默认 DB_RETAIN_DAYS 天）"""
    days = request.args.get("days", config.DB_RETAIN_DAYS)
    return jsonify({"code": 0, "message": "清理完成",
                    "data": {"deleted": db.prune(days), "days": int(days)}})


if __name__ == "__main__":
    load_settings()
    start_capture_thread()
    print("* 智能人流统计与考勤系统 已启动")
    print("* 终端控制界面:  http://<树莓派IP>:5000/")
    print("* 管理后台:      http://<树莓派IP>:5000/dashboard")
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=5000, threads=8)
    except Exception:
        app.run(host="0.0.0.0", port=5000, debug=config.DEBUG, threaded=True,
                use_reloader=False)