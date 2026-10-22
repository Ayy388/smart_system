# vision_module.py —— 视觉处理（统计组：人流统计与考勤系统）
# 人体检测（SSD 深度学习模型 / 模拟画面用背景差分）→ 质心跟踪 → 计数线跨越判定
import cv2
import numpy as np
import config
from person_detector import create_detector


class PeopleCounter:
    def __init__(self, line_y=None, match_distance=None, simulation=False):
        self.frame_w = config.CAMERA_WIDTH
        self.frame_h = config.CAMERA_HEIGHT
        self.line_y = line_y if line_y is not None else config.COUNT_LINE_Y
        self.match_distance = match_distance if match_distance is not None else config.MATCH_DISTANCE

        # 检测器：真实摄像头用 SSD 人体检测，模拟画面用背景差分
        self.detector = create_detector(simulation=simulation)

        # 轨迹：{id: {"centroid":(x,y), "prev":(x,y), "side":0/1, "lost":int,
        #              "hits":int, "box":(x,y,w,h), "score":float}}
        self.tracks = {}
        self.next_id = 1
        self.max_lost = 12          # 连续丢失多少帧后删除轨迹
        self.min_hits = 3           # 轨迹连续命中多少帧才允许计数（抑制偶发误检）

        # 会话计数
        self.enter_count = 0
        self.exit_count = 0

    # ---------------- 检测 ----------------
    def detect_people(self, frame):
        """返回 [(x, y, w, h, score), ...]"""
        return self.detector.detect(frame)

    # ---------------- 跟踪 ----------------
    def _nearest_track(self, centroid):
        best_id, best_d = None, self.match_distance
        for tid, t in self.tracks.items():
            d = np.hypot(t["centroid"][0] - centroid[0],
                         t["centroid"][1] - centroid[1])
            if d < best_d:
                best_d, best_id = d, tid
        return best_id

    def update(self, detections):
        """用当前帧检测结果更新跟踪器，返回本帧发生的 [(事件类型, id), ...]"""
        events = []

        # 1) 标记所有轨迹为“本帧未命中”
        for t in self.tracks.values():
            t["_matched"] = False

        # 2) 关联检测框与已有轨迹
        for (x, y, w, h, score) in detections:
            centroid = (int(x + w / 2), int(y + h / 2))
            tid = self._nearest_track(centroid)
            if tid is not None and not self.tracks[tid]["_matched"]:
                t = self.tracks[tid]
                t["prev"] = t["centroid"]
                t["centroid"] = centroid
                t["box"] = (x, y, w, h)
                t["score"] = score
                t["hits"] += 1
                t["lost"] = 0
                t["_matched"] = True
            else:
                self.tracks[self.next_id] = {
                    "centroid": centroid, "prev": centroid,
                    "side": 1 if centroid[1] >= self.line_y else 0,
                    "lost": 0, "hits": 1, "box": (x, y, w, h),
                    "score": score, "_matched": True}
                self.next_id += 1

        # 3) 处理未命中轨迹
        for tid in list(self.tracks):
            t = self.tracks[tid]
            if not t["_matched"]:
                t["lost"] += 1
                if t["lost"] > self.max_lost:
                    del self.tracks[tid]

        # 4) 计数线跨越判定（只对已稳定跟踪的轨迹计数）
        for tid, t in self.tracks.items():
            if t["hits"] < self.min_hits:
                continue
            py, cy = t["prev"][1], t["centroid"][1]
            side = 1 if cy >= self.line_y else 0       # 1=线下方  0=线上方
            prev_side = 1 if py >= self.line_y else 0
            if prev_side == t["side"] and side != t["side"]:
                if side == 1:                          # 上 → 下：进入
                    self.enter_count += 1
                    events.append(("enter", tid))
                else:                                  # 下 → 上：离开
                    self.exit_count += 1
                    events.append(("exit", tid))
                t["side"] = side
            elif prev_side != t["side"] and side == t["side"]:
                pass
            else:
                t["side"] = side
        return events

    # ---------------- 绘制 ----------------
    def annotate(self, frame, draw_tracks=True):
        h, w = frame.shape[:2]
        # 计数线（青色）
        ly = max(1, min(int(self.line_y), h - 2))
        cv2.line(frame, (0, ly), (w, ly), (255, 216, 0), 2)
        cv2.putText(frame, "COUNT LINE", (w - 145, ly - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 216, 0), 1)
        if draw_tracks:
            for tid, t in self.tracks.items():
                if t["hits"] < self.min_hits:
                    continue                      # 未确认的轨迹不画，避免闪烁误标
                x, y, bw, bh = t["box"]
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (255, 217, 0), 2)
                cx, cy = t["centroid"]
                cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)
                cv2.putText(frame, f"P#{tid} {t['score']:.2f}", (x, max(12, y - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 217, 0), 1)
            txt = (f"IN:{self.enter_count}  OUT:{self.exit_count}  "
                   f"NOW:{max(0, self.enter_count - self.exit_count)}")
            cv2.putText(frame, txt, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
        return frame

    # ---------------- 其它 ----------------
    def reset(self):
        """重置会话计数（对应前台“重置计数”按钮）"""
        self.enter_count = 0
        self.exit_count = 0
        self.tracks.clear()
        if hasattr(self.detector, "reset"):
            self.detector.reset()

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
    detections = counter.detect_people(frame)
    events = counter.update(detections)
    frame = counter.annotate(frame)
    return frame, events
