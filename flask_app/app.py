# app.py —— Flask 主程序（统计组：智能人流统计与考勤系统）
# 实验五：Web 前端开发 —— 终端控制界面 + 管理后台 + 前后端联调
import json
import threading
import time
import cv2
import numpy as np
from flask import Flask, render_template, Response, request, jsonify

import config
from camera_manager import CameraManager
from vision_module import PeopleCounter, process_frame
from db_helper import DBHelper

app = Flask(__name__)

# ---------------- 全局状态 ----------------
camera = CameraManager()
counter = PeopleCounter(line_y=config.COUNT_LINE_Y,
                        match_distance=config.MATCH_DISTANCE,
                        simulation=camera.simulation)
db = DBHelper()

state = {
    "running": False,            # 视频采集线程是否运行
    "detection_enabled": False,  # 是否启用检测/计数
    "fps": 0.0,
    "frame_count": 0,
}
state_lock = threading.Lock()

latest_jpeg = None               # 最近一帧标注后的 JPEG 字节
jpeg_lock = threading.Lock()

stop_event = threading.Event()
capture_thread = None


def load_settings():
    """从数据库读取设置并应用到计数器"""
    try:
        line = db.get_setting("count_line_y", config.COUNT_LINE_Y)
        dist = db.get_setting("match_distance", config.MATCH_DISTANCE)
        counter.set_line(int(line))
        counter.set_match_distance(int(dist))
        print(f"[app] 已加载设置：计数线位置={line} 匹配距离={dist}")
    except Exception as e:
        print(f"[app] 加载设置失败: {e}")


# ---------------- 视频处理线程 ----------------
def capture_loop():
    """持续采集帧；当检测启用时执行人体检测与计数，并维护 MJPEG 帧缓冲"""
    frame_interval = 1.0 / max(config.FEED_FPS, 1)
    while not stop_event.is_set():
        t0 = time.time()
        frame = camera.read_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        with state_lock:
            enabled = state["detection_enabled"]

        events = []
        if enabled:
            frame, events = process_frame_safe(frame)
        else:
            # 未启用检测时仍绘制计数线，便于调整位置
            frame = counter.annotate(frame, draw_tracks=False)

        ok, buf = cv2.imencode(".jpg", frame,
                               [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])
        if ok:
            global latest_jpeg
            with jpeg_lock:
                latest_jpeg = buf.tobytes()

        # 事件入库（进入/离开）
        for kind, tid in events:
            db.insert_detection(
                image_path=None,
                result_label=kind,
                confidence=1.0,
                detail_info={"track_id": tid, "line_y": counter.line_y},
                source="live")

        with state_lock:
            state["frame_count"] += 1
            elapsed = time.time() - t0
            state["fps"] = 1.0 / elapsed if elapsed > 0 else 0.0

        # 控制帧率
        dt = time.time() - t0
        if dt < frame_interval:
            time.sleep(frame_interval - dt)


def process_frame_safe(frame):
    """运行检测并捕获异常，避免单帧异常导致线程退出"""
    try:
        return process_frame(frame, counter)
    except Exception as e:
        print(f"[app] 处理帧异常: {e}")
        return frame, []


def start_capture_thread():
    global capture_thread
    if capture_thread is not None and capture_thread.is_alive():
        return
    stop_event.clear()
    capture_thread = threading.Thread(target=capture_loop, daemon=True)
    capture_thread.start()


def jpeg_placeholder():
    """尚无可用帧时发送的占位图（深色背景 + 提示文字）"""
    img = np.zeros((config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3), np.uint8)
    cv2.putText(img, "Waiting for camera...", (120, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 217, 255), 2)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])[1].tobytes()


def gen_video():
    """MJPEG 视频流生成器"""
    while True:
        with jpeg_lock:
            jpeg = latest_jpeg
        if jpeg is None:
            jpeg = jpeg_placeholder()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
               jpeg + b"\r\n")
        time.sleep(1.0 / max(config.FEED_FPS, 1))


# ---------------- 页面路由 ----------------
@app.route("/")
def index():
    """终端控制界面（3.5英寸横屏）"""
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    """管理后台"""
    return render_template("dashboard.html")


# ---------------- 视频流 ----------------
@app.route("/video_feed")
def video_feed():
    return Response(gen_video(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------- API ----------------
@app.route("/api/status")
def api_status():
    with state_lock:
        s = dict(state)
    s["running"] = capture_thread is not None and capture_thread.is_alive()
    s["simulation"] = camera.simulation
    s["camera"] = "simulation" if camera.simulation else "real"
    s["enter"] = counter.enter_count
    s["exit"] = counter.exit_count
    s["current"] = max(0, counter.enter_count - counter.exit_count)
    return jsonify({"code": 0, "data": s})


@app.route("/api/latest")
def api_latest():
    snap = counter.snapshot()
    return jsonify({"code": 0, "data": snap})


@app.route("/api/statistics")
def api_statistics():
    stats = db.get_statistics()
    stats["current"] = counter.snapshot()["current"]
    return jsonify({"code": 0, "data": stats})


@app.route("/api/history")
def api_history():
    limit = request.args.get("limit", 20)
    try:
        limit = int(limit)
    except ValueError:
        limit = 20
    rows = db.get_history(limit=limit)
    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "timestamp": r[1],
            "image_path": r[2],
            "result_label": r[3],
            "confidence": r[4],
        })
    return jsonify({"code": 0, "data": data})


@app.route("/api/start", methods=["POST"])
def api_start():
    with state_lock:
        state["detection_enabled"] = True
    start_capture_thread()
    return jsonify({"code": 0, "message": "已启动人流统计", "data": {"detection_enabled": True}})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    with state_lock:
        state["detection_enabled"] = False
    return jsonify({"code": 0, "message": "已停止人流统计", "data": {"detection_enabled": False}})


@app.route("/api/capture", methods=["POST"])
def api_capture():
    """统计组：此接口用于重置计数"""
    counter.reset()
    return jsonify({"code": 0, "message": "计数已重置",
                    "data": counter.snapshot()})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    try:
        body = request.get_json(silent=True) or request.form
        line = int(body.get("threshold", config.COUNT_LINE_Y))
        dist = int(body.get("alarm", config.MATCH_DISTANCE))
        counter.set_line(line)
        counter.set_match_distance(dist)
        db.set_setting("count_line_y", line)
        db.set_setting("match_distance", dist)
        return jsonify({"code": 0, "message": "设置已保存",
                        "data": {"count_line_y": line, "match_distance": dist}})
    except Exception as e:
        return jsonify({"code": 1, "message": f"保存失败: {e}"}), 400


if __name__ == "__main__":
    load_settings()
    start_capture_thread()
    print("* 智能人流统计与考勤系统 已启动")
    print("* 终端控制界面:  http://<树莓派IP>:5000/")
    print("* 管理后台:      http://<树莓派IP>:5000/dashboard")
    app.run(host="0.0.0.0", port=5000, debug=config.DEBUG, threaded=True,
            use_reloader=False)
