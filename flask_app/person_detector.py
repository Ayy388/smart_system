# person_detector.py —— 人体检测器（统计组：人流统计与考勤系统）
# 方案一（真实摄像头）：SSD MobileNet V1 COCO TFLite 模型，只保留 person 类别，
#                       不再依赖背景差分，从根本上解决暗光/噪点导致的“满屏误标”问题。
# 方案二（模拟画面）：模拟小人只是色块，深度学习模型无法识别，改用背景差分。
#
# 运行时优先级：
#   ai_edge_litert（LiteRT，tflite-runtime 的后继，Python 3.13 有 aarch64 轮子）
#   → tflite_runtime → tensorflow.lite
# 三者都没有时才回退背景差分。
import os
import time

import cv2
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "detect.tflite")
LABEL_PATH = os.path.join(MODEL_DIR, "labelmap.txt")

# 该量化模型输出的类别号：0 = person（COCO 0-based），其余为背景/其他物体
PERSON_CLASS_ID = 0


def _load_interpreter_class():
    """按可用性返回 (Interpreter, 运行时名称)"""
    try:
        from ai_edge_litert.interpreter import Interpreter
        return Interpreter, "LiteRT"
    except Exception:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter, "tflite-runtime"
    except Exception:
        pass
    try:
        from tensorflow.lite import Interpreter
        return Interpreter, "tensorflow.lite"
    except Exception:
        return None, None


class PersonDetectorSSD:
    """基于 TensorFlow Lite 的 SSD MobileNet 人体检测器"""

    def __init__(self, model_path=MODEL_PATH, score_thresh=0.5, num_threads=4):
        Interpreter, self.runtime = _load_interpreter_class()
        if Interpreter is None:
            raise RuntimeError("未安装 ai-edge-litert / tflite_runtime / tensorflow")
        self.score_thresh = score_thresh
        self.interpreter = Interpreter(model_path=model_path, num_threads=num_threads)
        self.interpreter.allocate_tensors()
        self.in_detail = self.interpreter.get_input_details()[0]
        self.in_shape = self.in_detail["shape"]           # [1, 300, 300, 3]
        self.in_h, self.in_w = int(self.in_shape[1]), int(self.in_shape[2])
        self.in_uint8 = self.in_detail["dtype"] == np.uint8
        self.out_details = self._sort_outputs(self.interpreter.get_output_details())
        self.class_names = self._load_labels()

    @staticmethod
    def _sort_outputs(details):
        """按名字/形状识别 SSD 的 4 个输出，兼容 TF1/TF2 两种命名

        TF 的 Detection_PostProcess 输出顺序固定为：boxes, classes, scores, num。
        名字在不同导出版本里可能都叫 TFLite_Detection_PostProcess，因此主要靠形状判断。
        """
        boxes = classes = scores = num = None
        twos = []
        for d in details:
            name = d["name"].lower()
            shape = [int(v) for v in d["shape"]]
            prod = 1
            for v in shape:
                prod *= v
            if len(shape) == 3 and shape[-1] == 4:
                boxes = d
            elif prod == 1:                      # num_detections: [1]
                num = d
            elif len(shape) >= 2:
                if "class" in name:
                    classes = d
                elif "score" in name:
                    scores = d
                else:
                    twos.append(d)
        # 名字不可靠时按输出顺序兜底：classes 在前，scores 在后
        if classes is None and twos:
            classes = twos[0]
        if scores is None and len(twos) >= 2:
            scores = twos[-1]
        if None in (boxes, classes, scores, num):
            raise RuntimeError(f"无法识别模型输出张量: {[d['name'] for d in details]}")
        return {"boxes": boxes, "classes": classes, "scores": scores, "num": num}

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
        inp = cv2.resize(rgb, (self.in_w, self.in_h))
        if self.in_uint8:
            # 量化模型：直接把 0~255 的像素灌进去，归一化在模型内部完成
            inp = np.expand_dims(inp, axis=0).astype(np.uint8)
        else:
            inp = np.expand_dims(inp, axis=0).astype(np.float32) / 127.5 - 1.0

        self.interpreter.set_tensor(self.in_detail["index"], inp)
        self.interpreter.invoke()

        boxes = self.interpreter.get_tensor(self.out_details["boxes"]["index"])[0]
        classes = self.interpreter.get_tensor(self.out_details["classes"]["index"])[0]
        scores = self.interpreter.get_tensor(self.out_details["scores"]["index"])[0]
        count = int(self.interpreter.get_tensor(self.out_details["num"]["index"])[0])

        cands = []
        for i in range(count):
            if int(classes[i]) != PERSON_CLASS_ID:
                continue
            score = float(scores[i])
            if score < self.score_thresh:
                continue
            ymin, xmin, ymax, xmax = [float(v) for v in boxes[i]]
            x1, y1 = max(0.0, xmin), max(0.0, ymin)
            x2, y2 = min(1.0, xmax), min(1.0, ymax)
            x, y = int(x1 * w0), int(y1 * h0)
            w, hh = int((x2 - x1) * w0), int((y2 - y1) * h0)
            if w < 20 or hh < 45:
                continue
            if hh < 0.55 * w:                 # 人形框高应大于宽的一半，横向长条多为手臂/椅子
                continue
            cands.append((x, y, w, hh, score))

        cands.sort(key=lambda b: -(b[2] * b[3]))   # 先大后小：完整人体框优先保留
        results = []
        for b in cands:
            if not any(_is_duplicate(b, r) for r in results):
                results.append(b)
        # 输出按分数排序，便于上层展示
        results.sort(key=lambda b: -b[4])
        return results


def _is_duplicate(small, keep):
    """判断 small 是否只是 keep 的一部分（同一人的衣服/手臂被单独检出）

    三种情况视为重复：
      1) 小框大部分落在大框里（交集 / 小框面积 > 0.55）且面积明显更小；
      2) 两框几乎重合（IoU > 0.45）；
      3) 小框中心落在大框内且两者中心很近。
    """
    ax, ay, aw, ah = small[:4]
    bx, by, bw, bh = keep[:4]
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        # 框不相交：仍判断中心是否被包住
        cx, cy = ax + aw / 2.0, ay + ah / 2.0
        inside = bx <= cx <= bx + bw and by <= cy <= by + bh
        return bool(inside and aw * ah < 0.5 * bw * bh)
    inter = (x2 - x1) * (y2 - y1)
    small_area = float(aw * ah)
    keep_area = float(bw * bh)
    iou = inter / (small_area + keep_area - inter)
    contained = inter / max(small_area, 1.0)
    if iou > 0.45:
        return True
    c1 = (ax + aw / 2.0, ay + ah / 2.0)
    c2 = (bx + bw / 2.0, by + bh / 2.0)
    center_inside = (bx <= c1[0] <= bx + bw) and (by <= c1[1] <= by + bh)
    # 小框明显小于大框，且大部分被包含 / 中心落在大框里 → 认定是同一人的局部
    if small_area < 0.45 * keep_area and (contained > 0.5 or center_inside):
        return True
    if contained > 0.7:
        return True
    dist = ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5
    return bool(contained > 0.4 and dist < 0.3 * min(aw, bw))


def _iou(a, b):
    ax, ay, aw, ah = a[:4]
    bx, by, bw, bh = b[:4]
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / float(aw * ah + bw * bh - inter)


class MotionDetector:
    """背景差分检测器（仅用于模拟画面：模拟小人为纯色块，深度学习模型无法识别）"""

    def __init__(self, min_area=200, var_threshold=25, learning_rate=0.002):
        self.min_area = min_area
        self.var_threshold = var_threshold
        # 学习率调小，避免“走得慢/站着不动”的目标被背景模型吸收（实测默认学习率下
        # 模拟画面里 4 个人只剩 0.1 个框/帧，改成 0.002 后可稳定检出 4 个）
        self.learning_rate = learning_rate
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.reset()

    def reset(self):
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=self.var_threshold, detectShadows=False)

    def detect(self, frame):
        h0, w0 = frame.shape[:2]
        fg = self.bg_sub.apply(frame, learningRate=self.learning_rate)
        fg[fg == 127] = 0                        # 去掉阴影标记（如开阴影检测）
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, self._kernel)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for c in contours:
            if cv2.contourArea(c) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if h < 30 or w < 14 or w > w0 * 0.6 or h > h0 * 0.98:
                continue
            results.append((x, y, w, h, 1.0))
        return results


def create_detector(simulation=False, score_thresh=0.5, num_threads=2):
    """按运行模式创建检测器，返回 (detector, 描述信息 dict)"""
    info = {"type": "motion", "runtime": None, "model": None, "input": None}
    if simulation:
        print("[detector] 模拟画面模式 → 使用背景差分检测器")
        info["type"] = "motion"
        return MotionDetector(), info
    if os.path.exists(MODEL_PATH):
        try:
            det = PersonDetectorSSD(score_thresh=score_thresh, num_threads=num_threads)
            det.detect(np.zeros((480, 640, 3), np.uint8))       # 预热
            t0 = time.time()
            det.detect(np.zeros((480, 640, 3), np.uint8))
            ms = (time.time() - t0) * 1000
            info.update(type="ssd", runtime=det.runtime, model="SSD MobileNet COCO (int8)",
                        input=f"{det.in_w}x{det.in_h}", latency_ms=round(ms, 1))
            print(f"[detector] 已加载 {info['model']}，运行时 {det.runtime}，"
                  f"单帧 {ms:.0f} ms，阈值 {score_thresh}")
            return det, info
        except Exception as e:
            print(f"[detector] 模型加载失败，回退背景差分: {e}")
    else:
        print(f"[detector] 未找到模型 {MODEL_PATH}，回退背景差分")
    return MotionDetector(min_area=3000, var_threshold=45), info


if __name__ == "__main__":
    import sys
    det, meta = create_detector()
    img = cv2.imread(sys.argv[1] if len(sys.argv) > 1 else "/tmp/frame_fixed_exp.jpg")
    t0 = time.time()
    res = det.detect(img)
    dt = (time.time() - t0) * 1000
    print(f"检测耗时 {dt:.1f} ms, 人数 {len(res)}, 信息 {meta}")
    for r in res:
        print("  ", r)