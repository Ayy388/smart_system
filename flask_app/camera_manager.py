# camera_manager.py —— 摄像头管理（统计组）
# 优先使用真实摄像头（Raspberry Pi 使用 Picamera2，否则使用 OpenCV 打开 USB/CSI 摄像头）；
# 当摄像头不可用或 config.SIMULATION 开启时，自动切换到“模拟画面”源，便于无摄像头环境联调。
import time
import cv2
import numpy as np
import config


class SimulatedCamera:
    """模拟摄像头：在静态背景上绘制若干个来回运动的人形色块，
    用于在无摄像头/摄像头不可用的环境下演示“人流统计”全流程。"""

    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        # 背景：浅色室内走廊场景
        self.background = np.full((height, width, 3), 150, np.uint8)
        self._paint_room()
        # 模拟行人：每人有位置、速度、颜色、尺寸
        self.people = [
            {"x": 120.0, "y": 60.0,  "vx": 0.7, "vy": 1.1,  "r": 16, "c": (40, 120, 220)},
            {"x": 300.0, "y": 430.0, "vx": 0.5, "vy": -1.0, "r": 14, "c": (60, 180, 80)},
            {"x": 480.0, "y": 90.0,  "vx": -0.6, "vy": 1.2, "r": 15, "c": (200, 90, 60)},
            {"x": 520.0, "y": 400.0, "vx": 0.4, "vy": -0.9, "r": 13, "c": (180, 80, 200)},
        ]
        self.t = 0.0

    def _paint_room(self):
        h, w = self.background.shape[:2]
        # 地面
        cv2.rectangle(self.background, (0, h // 2), (w, h), (110, 110, 130), -1)
        # 门框（计数线左右各一扇门）
        cv2.rectangle(self.background, (30, 80), (180, h // 2), (90, 90, 120), -1)
        cv2.rectangle(self.background, (w - 180, 80), (w - 30, h // 2), (90, 90, 120), -1)
        # 窗户
        cv2.rectangle(self.background, (220, 40), (420, 140), (190, 200, 220), -1)
        cv2.line(self.background, (220, 90), (420, 90), (150, 160, 180), 2)
        # 简单线条装饰
        for x in range(60, w, 60):
            cv2.line(self.background, (x, h // 2), (x + 30, h), (120, 120, 140), 2)

    def read_frame(self):
        frame = self.background.copy()
        self.t += 0.3
        for p in self.people:
            # 更新位置，碰到上下边界反弹（模拟人员在门口来回走动）
            p["y"] += p["vy"]
            p["x"] += p["vx"] * np.sin(self.t / 20 + p["x"] / 100)
            if p["y"] < 60 or p["y"] > self.height - 60:
                p["vy"] *= -1
            if p["x"] < 40 or p["x"] > self.width - 40:
                p["vx"] *= -1
            # 绘制人形（头 + 身）
            cx, cy, r = int(p["x"]), int(p["y"]), p["r"]
            cv2.circle(frame, (cx, cy - r), int(r * 0.5), p["c"], -1)
            cv2.rectangle(frame, (cx - r, cy - int(r * 0.4)),
                          (cx + r, cy + r), p["c"], -1)
        return frame

    def release(self):
        pass


class CameraManager:
    def __init__(self):
        self.width = config.CAMERA_WIDTH
        self.height = config.CAMERA_HEIGHT
        self.simulation = False
        self.picam2 = None
        self.cap = None
        self._sim = None
        self._open()

    def _open(self):
        mode = config.SIMULATION
        if mode == "1":
            self._use_simulation()
            return

        # 1) Raspberry Pi: Picamera2
        try:
            from picamera2 import Picamera2
            picam2 = Picamera2()
            cfg = picam2.create_preview_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"})
            picam2.configure(cfg)
            # 固定白平衡，避免色温漂移；曝光交给自动曝光（固定 15ms 在室内会严重欠曝）
            try:
                picam2.set_controls({
                    "AwbEnable": False,
                    "ColourGains": (1.8, 1.5),
                    "AeEnable": True,
                })
            except Exception as e:
                print(f"[camera] 控制参数设置失败(忽略): {e}")
            picam2.start()
            time.sleep(1.5)
            self.picam2 = picam2
            print("[camera] 已启动 Picamera2（自动曝光 + 固定白平衡）")
            return
        except Exception as e:
            print(f"[camera] Picamera2 不可用: {e}")

        # 2) OpenCV 打开摄像头
        for idx in range(3):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                ok, frame = cap.read()
                if ok and frame is not None:
                    self.cap = cap
                    print(f"[camera] 已打开 OpenCV 摄像头 #{idx}")
                    return
                cap.release()
            else:
                print(f"[camera] OpenCV 摄像头 #{idx} 打开失败")

        # 3) 模拟画面
        if mode != "0":
            self._use_simulation()
        else:
            raise RuntimeError("config.SIMULATION=0 且未找到可用摄像头")

    def _use_simulation(self):
        self.simulation = True
        self._sim = SimulatedCamera(self.width, self.height)
        print("[camera] 未找到可用摄像头，已切换到【模拟画面】模式")

    def read_frame(self):
        """返回一帧 BGR 图像；失败返回 None"""
        if self.simulation:
            return self._sim.read_frame()
        if self.picam2 is not None:
            try:
                arr = self.picam2.capture_array()
                if arr.shape[2] == 3:  # RGB
                    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                return arr
            except Exception:
                return None
        if self.cap is not None:
            ok, frame = self.cap.read()
            if ok and frame is not None:
                return frame
        return None

    def release(self):
        if self.picam2 is not None:
            try:
                self.picam2.stop()
            except Exception:
                pass
        if self.cap is not None:
            self.cap.release()
        if self._sim is not None:
            self._sim.release()


if __name__ == "__main__":
    cam = CameraManager()
    print("模拟模式:", cam.simulation)
    for i in range(5):
        f = cam.read_frame()
        print(i, None if f is None else f.shape)
        time.sleep(0.2)
    cam.release()
