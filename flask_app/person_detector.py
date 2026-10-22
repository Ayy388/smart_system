# person_detector.py —— 人体检测器（统计组：人流统计与考勤系统）
# 方案一（真实摄像头）：SSD MobileNet V1 COCO TFLite 模型，只保留 person 类别，
#                       不再依赖背景差分，从根本上解决暗光/噪点导致的“满屏误标”问题。
# 方案二（模拟画面）：模拟小人只是色块，深度学习模型无法识别，改用背景差分。
import os
import time
import cv2
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "detect.tflite")
LABEL_PATH = os.path.join(MODEL_DIR, "labelmap.txt")

PERSON_CLASS_ID = 0          # 该模型 person = class 0（背景类别，labelmap 中为“???”，但语义上即 person）


class PersonDetectorSSD:
    """基于 TensorFlow Lite 的 SSD MobileNet 人体检测器"""

    def __init__(self, model_path=MODEL_PATH, score_thresh=0.55, input_size=(300, 300)):
        import tensorflow as tf
        self.score_thresh = score_thresh
        self.input_size = input_size
        self.interpreter = tf.lite.Interpreter(model_path=model_path, num_threads=4)
        self.interpreter.allocate_tensors()
        self.in_detail = self.interpreter.get_input_details()[0]
        self.out_details = self.interpreter.get_output_details()
        self.class_names = self._load_labels()

    @staticmethod
    def _load_labels():
        names = []
        if os.path.exists(LABEL_PATH):
            with open(LABEL_PATH, "r", encoding="utf-8") as f:
                names = [line.strip() for line in f.readlines()]
        return names

    def name_of(self, cid):
        try:
            return self.class_names[int(cid)]
        except Exception:
            return str(cid)

    def detect(self, frame):
        """返回 [(x, y, w, h, score), ...]（仅 person 类别，原图坐标）"""
        h0, w0 = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        inp = cv2.resize(rgb, self.input_size)
        inp = np.expand_dims(inp, axis=0).astype(self.in_detail["dtype"])

        self.interpreter.set_tensor(self.in_detail["index"], inp)
        self.interpreter.invoke()

        boxes = self.interpreter.get_tensor(self.out_details[0]["index"])[0]
        classes = self.interpreter.get_tensor(self.out_details[1]["index"])[0]
        scores = self.interpreter.get_tensor(self.out_details[2]["index"])[0]
        count = int(self.interpreter.get_tensor(self.out_details[3]["index"])[0])

        results = []
        for i in range(count):
            if int(classes[i]) != PERSON_CLASS_ID:
                continue
            score = float(scores[i])
            if score < self.score_thresh:
                continue
            # 归一化坐标 ymin, xmin, ymax, xmax
            ymin, xmin, ymax, xmax = boxes[i]
            x = int(max(0.0, xmin) * w0)
            y = int(max(0.0, ymin) * h0)
            w = int((min(1.0, xmax) - max(0.0, xmin)) * w0)
            hh = int((min(1.0, ymax) - max(0.0, ymin)) * h0)
            if w < 15 or hh < 30:
                continue
            results.append((x, y, w, hh, score))
        return results


class MotionDetector:
    """背景差分检测器（仅用于模拟画面：模拟小人为纯色块，深度学习模型无法识别）"""

    def __init__(self, min_area=200, var_threshold=25):
        self.min_area = min_area
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=var_threshold, detectShadows=False)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.frame_w = 640
        self.frame_h = 480

    def reset(self):
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=25, detectShadows=False)

    def detect(self, frame):
        h0, w0 = frame.shape[:2]
        self.frame_w, self.frame_h = w0, h0
        fg = self.bg_sub.apply(frame)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, self._kernel)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if h < 15 or w < 12 or w > w0 * 0.6:
                continue
            results.append((x, y, w, h, 1.0))
        return results


def create_detector(simulation=False, score_thresh=0.55):
    """按运行模式创建检测器"""
    if simulation:
        print("[detector] 模拟画面模式 → 使用背景差分检测器")
        return MotionDetector()
    if os.path.exists(MODEL_PATH):
        try:
            det = PersonDetectorSSD(score_thresh=score_thresh)
            # 预热一次，避免首帧慢
            det.detect(np.zeros((480, 640, 3), np.uint8))
            print(f"[detector] 已加载 SSD MobileNet 人体检测模型（阈值 {score_thresh}）")
            return det
        except Exception as e:
            print(f"[detector] 模型加载失败，回退背景差分: {e}")
    else:
        print(f"[detector] 未找到模型 {MODEL_PATH}，回退背景差分")
    return MotionDetector(min_area=3000, var_threshold=45)


if __name__ == "__main__":
    import sys
    det = create_detector()
    img = cv2.imread(sys.argv[1] if len(sys.argv) > 1 else "/tmp/frame_fixed_exp.jpg")
    t0 = time.time()
    res = det.detect(img)
    dt = (time.time() - t0) * 1000
    print(f"检测耗时 {dt:.1f} ms, 人数 {len(res)}")
    for r in res:
        print("  ", r)
