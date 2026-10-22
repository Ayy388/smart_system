# vision_module.py —— 视觉处理（统计组：人流统计与考勤系统）
# 功能：人体检测（背景差分 + 轮廓筛选）、目标跟踪、计数线跨越判定（进入/离开）
import cv2
import numpy as np
import time
import config


class PeopleCounter:
    def __init__(self, line_y=None, match_distance=None, min_area=200):
        self.frame_w = config.CAMERA_WIDTH
        self.frame_h = config.CAMERA_HEIGHT
        self.line_y = line_y if line_y is not None else config.COUNT_LINE_Y
        self.match_distance = match_distance if match_distance is not None else config.MATCH_DISTANCE
        self.min_area = min_area
        # 跟踪对象：{id: {"centroid": (x,y), "prev": (x,y), "side": int|None, "lost": int}}
        self.tracks = {}
        self.next_id = 1
        # 会话计数（本次运行/重置后）
        self.enter_count = 0
        self.exit_count = 0
        # 背景差分器（用于人体/运动目标检测）
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=25, detectShadows=False)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        # 可选 HOG 检测器（若当前 OpenCV 支持，可增强检测精度）
        self.hog = None
        if hasattr(cv2, "HOGDescriptor"):
            try:
                self.hog = cv2.HOGDescriptor()
                self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            except Exception:
                self.hog = None

    # ---------------- 检测 ----------------
    def detect_people(self, frame):
        """返回人体包围盒列表 [(x, y, w, h), ...]"""
        boxes = []
        # 1) 背景差分运动目标
        fg = self.bg_sub.apply(frame)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, self._kernel)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            # 过滤不合理的形状（运动目标大致竖向/近似方形）
            if h > 15 and w > 15 and w < self.frame_w * 0.6 and 0.25 < h / max(w, 1) < 6:
                boxes.append((x, y, w, h))

        # 2) HOG 行人检测（如果可用，用于复核）
        if self.hog is not None and len(boxes) == 0:
            rects, _ = self.hog.detectMultiScale(
                cv2.resize(frame, (480, 360)), winStride=(8, 8), padding=(8, 8), scale=1.05)
            scale = frame.shape[1] / 480.0
            for (x, y, w, h) in rects:
                boxes.append((int(x * scale), int(y * scale),
                              int(w * scale), int(h * scale)))
        return boxes

    # ---------------- 跟踪与计数 ----------------
    def _nearest_track(self, centroid):
        best_id, best_d = None, self.match_distance
        for tid, t in self.tracks.items():
            d = np.hypot(t["centroid"][0] - centroid[0], t["centroid"][1] - centroid[1])
            if d < best_d:
                best_d, best_id = d, tid
        return best_id

    def update(self, boxes):
        """用当前帧检测结果更新跟踪器，返回本帧发生的 [进入/离开] 事件列表"""
        events = []
        if not boxes:
            for tid in list(self.tracks):
                self.tracks[tid]["lost"] += 1
                if self.tracks[tid]["lost"] > 10:
                    del self.tracks[tid]
            return events

        used = set()
        # 1) 关联已有轨迹
        for (x, y, w, h) in boxes:
            centroid = (int(x + w / 2), int(y + h / 2))
            tid = self._nearest_track(centroid)
            if tid is not None and tid not in used:
                used.add(tid)
                t = self.tracks[tid]
                t["prev"] = t["centroid"]
                t["centroid"] = centroid
                t["lost"] = 0
            else:
                # 2) 新建轨迹
                self.tracks[self.next_id] = {
                    "centroid": centroid, "prev": centroid,
                    "side": None, "lost": 0, "box": (x, y, w, h)}
                self.next_id += 1

        # 3) 计数线跨越判定
        for tid, t in list(self.tracks.items()):
            py = t["prev"][1]
            cy = t["centroid"][1]
            side = 1 if cy >= self.line_y else 0      # 1=线下方, 0=线上方
            if t["side"] is None:
                t["side"] = side
            elif t["side"] == 0 and side == 1:        # 上 → 下：进入
                self.enter_count += 1
                t["side"] = side
                events.append(("enter", tid))
            elif t["side"] == 1 and side == 0:        # 下 → 上：离开
                self.exit_count += 1
                t["side"] = side
                events.append(("exit", tid))
        return events

    # ---------------- 绘制 ----------------
    def annotate(self, frame, draw_tracks=True):
        h, w = frame.shape[:2]
        # 计数线（始终显示，便于调整计数线位置）
        ly = min(int(self.line_y), h - 2)
        cv2.line(frame, (0, ly), (w, ly), (255, 216, 0), 2)
        cv2.putText(frame, "COUNT LINE", (w - 150, ly - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 216, 0), 1)
        # 轨迹与人数
        if draw_tracks:
            for tid, t in self.tracks.items():
                x, y, bw, bh = t.get("box", (0, 0, 0, 0))
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 217, 255), 2)
                cx, cy = t["centroid"]
                cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)
                cv2.putText(frame, f"#{tid}", (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 217, 255), 1)
            txt = f"IN:{self.enter_count}  OUT:{self.exit_count}  NOW:{max(0, self.enter_count - self.exit_count)}"
            cv2.putText(frame, txt, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
        return frame

    def reset(self):
        """重置会话计数（对应前台“重置计数”按钮）"""
        self.enter_count = 0
        self.exit_count = 0
        self.tracks.clear()
        self.bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=25, detectShadows=False)

    def set_line(self, y):
        self.line_y = int(y)
        config.COUNT_LINE_Y = int(y)

    def set_match_distance(self, d):
        self.match_distance = int(d)
        config.MATCH_DISTANCE = int(d)

    def snapshot(self):
        return {
            "enter": self.enter_count,
            "exit": self.exit_count,
            "current": max(0, self.enter_count - self.exit_count),
        }


def process_frame(frame, counter):
    """检测 → 跟踪 → 计数 → 标注，返回 (标注帧, 事件列表)"""
    boxes = counter.detect_people(frame)
    events = counter.update(boxes)
    frame = counter.annotate(frame)
    return frame, events
