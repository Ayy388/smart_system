import cv2
import time
from picamera2 import Picamera2

def create_camera(width=640, height=480):
    """初始化Picamera2摄像头，返回picam2对象"""
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (width, height)})
    picam2.configure(config)
    picam2.set_controls({
        "AwbEnable": False,
        "AeEnable": False,
        "ColourGains": (1.8, 1.5),
        "ExposureTime": 15000,
        "AnalogueGain": 2.0
    })
    picam2.start()
    time.sleep(2)
    print("摄像头已启动")
    return picam2

def capture_frame(picam2):
    """从摄像头捕获一帧，返回BGR格式图像"""
    frame_rgb = picam2.capture_array()
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    return frame_bgr
