# vision_module.py —— 视觉处理（统计组：人流统计与考勤系统）
# 人体检测（SSD 深度学习模型 / 模拟画面用背景差分）→ 多目标跟踪 → 计数线跨越判定
#
# 第七次课发布测试后的改进点（现场实测发现的问题）：
#   1. 计数线附近抖动静止目标会被反复计数  → 迟滞带 + 每轨迹冷却
#   2. 背景差分丢框导致同一人被切成多个 ID → 速度预测 + 颜色直方图重识别
#   3. 计数判定依赖“上一帧”，快速移动会漏计 → 用“所在侧/过渡带”状态机
import threading
import time

import cv2
import numpy as np

import config
from person_detector import create_detector


class PeopleCounter:
    """检测 → 跟踪 → 跨线计数"""

    # 轨迹颜色（BGR）
    COL_BELOW = (140, 255, 120)      # 线下方（进入侧）
    COL_ABOVE = (0, 190, 255)        # 线上方（离开侧）
    COL_COUNTED = (60, 60, 255)      # 刚刚计过数的轨迹
    COL_LINE = (255, 216, 0)
    COL_BAND = (40, 60, 80)

    def __init__(self, line_y=None, match_distance=None, simulation=False, axis=None):
        self.frame_w = config.CAMERA_WIDTH
        self.frame_h = config.CAMERA_HEIGHT
        # 计数线方向："x" = 竖线（左右过线），"y" = 横线（上下过线）
        self.axis = (axis or getattr(config, "COUNT_AXIS", "y")).lower()
        default_pos = (getattr(config, "COUNT_LINE_X", self.frame_w // 2)
                       if self.axis == "x" else config.COUNT_LINE_Y)
        self.line_y = int(line_y if line_y is not None else default_pos)
        self.match_distance = int(match_distance if match_distance is not None
                                  else config.MATCH_DISTANCE)

        # 去抖参数
        self.hysteresis = int(getattr(config, "COUNT_HYSTERESIS", 14))
        self.cooldown = float(getattr(config, "COUNT_COOLDOWN", 3.0))
        self.max_lost = int(getattr(config, "TRACK_MAX_LOST", 30))
        self.min_hits = int(getattr(config, "TRACK_MIN_HITS", 4))
        self.confirm_frames = int(getattr(config, "COUNT_CONFIRM_FRAMES", 3))
        self.pending_timeout = float(getattr(config, "COUNT_PENDING_TIMEOUT", 1.5))

        # 检测器：真实摄像头用 SSD 人体检测，模拟画面用背景差分
        self.detector, self.detector_info = create_detector(
            simulation=simulation, num_threads=int(getattr(config, "DETECT_THREADS", 2)))

        # 轨迹：{id: {"centroid", "prev", "velocity", "zone", "from_zone",
        #              "lost", "hits", "box", "score", "hist", "last_count"}}
        self.tracks = {}
        self.next_id = 1
        self.lock = threading.RLock()

        # 会话计数
        self.enter_count = 0
        self.exit_count = 0
        self.last_event_time = 0.0

    # ---------------- 检测 ----------------
    def detect_people(self, frame):
        """返回 [(x, y, w, h, score), ...]"""
        return self.detector.detect(frame)

    # ---------------- 辅助 ----------------
    @staticmethod
    def _centroid(box):
        x, y, w, h = box
        return (int(x + w / 2), int(y + h / 2))

    def _coord(self, centroid):
        """取质心沿计数线法向的坐标：竖线看 x，横线看 y"""
        return centroid[0] if self.axis == "x" else centroid[1]

    def _zone_of(self, cy):
        """-1 = 线上侧, 0 = 过渡带内, 1 = 线下侧"""
        if cy < self.line_y - self.hysteresis:
            return -1
        if cy > self.line_y + self.hysteresis:
            return 1
        return 0

    @staticmethod
    def _hist(frame, box):
        """目标区域 HSV 直方图（用于丢失后重识别）"""
        x, y, w, h = [int(v) for v in box]
        h0, w0 = frame.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w0, x + w), min(h0, y + h)
        if x2 - x1 < 8 or y2 - y1 < 16:
            return None
        roi = frame[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten()

    @staticmethod
    def _hist_sim(a, b):
        if a is None or b is None:
            return 0.0
        return float(cv2.compareHist(a.astype(np.float32), b.astype(np.float32),
                                     cv2.HISTCMP_CORREL))

    # ---------------- 跟踪 + 计数 ----------------
    def update(self, detections, frame=None, now=None):
        """用当前帧检测结果更新跟踪器，返回本帧发生的 [(事件类型, id, 信息), ...]"""
        now = time.time() if now is None else now
        events = []
        with self.lock:
            for t in self.tracks.values():
                t["_matched"] = False

            # 1) 位置/外观匹配：距离候选排序后贪心一对一
            cands = []
            for di, det in enumerate(detections):
                cx, cy = self._centroid(det[:4])
                gate = max(self.match_distance, 0.55 * max(det[2], det[3]))
                for tid, t in self.tracks.items():
                    px, py = t["centroid"][0] + t["velocity"][0], t["centroid"][1] + t["velocity"][1]
                    vx, vy = t["velocity"]
                    # 门限随框尺寸和当前速度自适应：快走/快速通过时不掉 ID
                    speed = float(np.hypot(vx, vy))
                    g = max(gate, min(0.9 * max(det[2], det[3]), 160.0), 1.5 * speed)
                    d = float(np.hypot(px - cx, py - cy))
                    if d <= g:
                        # 距离越小越优先，外观相似再加权
                        cands.append((d, tid, di))
            cands.sort(key=lambda c: c[0])

            used_t, used_d = set(), set()
            for d, tid, di in cands:
                if tid in used_t or di in used_d:
                    continue
                det = detections[di]
                t = self.tracks[tid]
                cx, cy = self._centroid(det[:4])
                pvx = cx - t["centroid"][0]
                pvy = cy - t["centroid"][1]
                t["velocity"] = (0.6 * t["velocity"][0] + 0.4 * pvx,
                                 0.6 * t["velocity"][1] + 0.4 * pvy)
                t["prev"] = t["centroid"]
                t["centroid"] = (cx, cy)
                t["box"] = tuple(det[:4])
                t["score"] = float(det[4])
                t["hits"] += 1
                t["lost"] = 0
                t["_matched"] = True
                used_t.add(tid)
                used_d.add(di)

            # 2) 未匹配检测：先按外观尝试“复活”刚丢失的轨迹，否则新建
            for di, det in enumerate(detections):
                if di in used_d:
                    continue
                bx, cy = self._centroid(det[:4])
                hist = self._hist(frame, det[:4]) if frame is not None else None
                revived = None
                if hist is not None:
                    # 复活的三道门：外观相似 + 位置对得上 + 只允许刚丢几帧的轨迹
                    best, best_sim = None, 0.65
                    for tid, t in self.tracks.items():
                        if t["_matched"] or t["lost"] == 0:
                            continue
                        if t["lost"] > 6:
                            continue
                        px = t["centroid"][0] + t["velocity"][0]
                        py = t["centroid"][1] + t["velocity"][1]
                        if float(np.hypot(px - bx, py - cy)) > 1.6 * self.match_distance:
                            continue
                        sim = self._hist_sim(hist, t.get("hist"))
                        if sim > best_sim:
                            best_sim, best = sim, tid
                    revived = best
                if revived is not None:
                    t = self.tracks[revived]
                    # 复活点若已在线另一侧，说明身份接错了：按新轨迹处理，不产生跨线事件
                    zr = self._zone_of(self._coord((bx, cy)))
                    if zr != 0 and zr != t["from_zone"]:
                        t["from_zone"] = zr
                        t["pending"] = None
                    t["zone"] = zr
                    t["prev"] = t["centroid"]
                    t["centroid"] = (bx, cy)
                    t["box"] = tuple(det[:4])
                    t["score"] = float(det[4])
                    t["hist"] = hist
                    t["velocity"] = (0.0, 0.0)
                    t["hits"] += 1
                    t["lost"] = 0
                    t["_matched"] = True
                    used_d.add(di)
                else:
                    cx, cy = bx, cy
                    z = self._zone_of(cy if self.axis != "x" else cx)
                    self.tracks[self.next_id] = {
                        "centroid": (cx, cy), "prev": (cx, cy), "velocity": (0.0, 0.0),
                        "zone": z, "from_zone": z,
                        "lost": 0, "hits": 1, "box": tuple(det[:4]),
                        "score": float(det[4]), "hist": hist,
                        "last_count": -1e9, "pending": None, "_matched": True}
                    self.next_id += 1
                    used_d.add(di)

            # 2.5) 同一目标的多余轨迹合并（衣服/手臂被当成第二个人时，会出现两条几乎重合的轨迹）
            self._merge_duplicate_tracks()

            # 3) 未命中轨迹老化
            for tid in list(self.tracks):
                t = self.tracks[tid]
                if not t["_matched"]:
                    t["lost"] += 1
                    if t["lost"] > self.max_lost:
                        del self.tracks[tid]

            # 4) 跨线判定：状态机（上侧 -1 ⇄ 过渡带 0 ⇄ 下侧 +1）
            #    + 确认帧（越过计数带后连续 N 帧仍在另一侧才算）
            #    + 冷却时间（同一轨迹两次计数的最小间隔）
            for tid, t in self.tracks.items():
                cy = self._coord(t["centroid"])
                z = self._zone_of(cy)
                t["zone"] = z
                if z == 0:
                    t["pending"] = None
                    continue

                pend = t.get("pending")
                if pend is not None:
                    if z != pend["zone"] or (now - pend["t0"]) > self.pending_timeout:
                        # 又晃回原侧 / 挂起时间过长：本次跨越作废
                        t["pending"] = None
                        t["from_zone"] = z
                        continue
                    pend["frames"] += 1
                    if (pend["frames"] >= self.confirm_frames
                            and t["hits"] >= self.min_hits
                            and (now - t["last_count"]) >= self.cooldown):
                        if z > 0:                      # 上 → 下：进入
                            self.enter_count += 1
                            kind = "enter"
                        else:                          # 下 → 上：离开
                            self.exit_count += 1
                            kind = "exit"
                        t["last_count"] = now
                        t["pending"] = None
                        self.last_event_time = now
                        events.append((kind, tid, {"track_id": tid, "line_y": self.line_y,
                                                   "score": round(float(t["score"]), 2)}))
                    continue

                if t["from_zone"] != 0 and z != t["from_zone"]:
                    t["pending"] = {"zone": z, "frames": 0, "t0": now}
                t["from_zone"] = z
        return events

    def _merge_duplicate_tracks(self):
        """合并同一目标的多余轨迹：小框被大框包含、或两者几乎重合时，保留命中多的那条"""
        items = sorted(self.tracks.items(), key=lambda kv: (-kv[1]["hits"], kv[0]))
        kept = []
        for tid, t in items:
            x, y, w, h = [float(v) for v in t["box"]]
            cx, cy = t["centroid"]
            dup = None
            for kid in kept:
                k = self.tracks[kid]
                kx, ky = k["centroid"]
                kbox = [float(v) for v in k["box"]]
                kw, kh = kbox[2], kbox[3]
                ix1, iy1 = max(x, kbox[0]), max(y, kbox[1])
                ix2, iy2 = min(x + w, kbox[0] + kw), min(y + h, kbox[1] + kh)
                if ix2 <= ix1 or iy2 <= iy1:
                    continue
                inter = (ix2 - ix1) * (iy2 - iy1)
                small = min(w * h, kw * kh)
                big = max(w * h, kw * kh)
                contained = inter / max(small, 1.0)
                dist = ((cx - kx) ** 2 + (cy - ky) ** 2) ** 0.5
                center_inside = (kbox[0] <= cx <= kbox[0] + kw
                                 and kbox[1] <= cy <= kbox[1] + kh)
                if small < 0.45 * big and (contained > 0.5 or center_inside):
                    dup = kid
                    break
                if contained > 0.7 or (contained > 0.45 and dist < 0.25 * min(w, kw)):
                    dup = kid
                    break
            if dup is None:
                kept.append(tid)
            else:
                # 把丢失计数与冷却并给保留轨迹，避免刚合并就重新计数
                keep = self.tracks[dup]
                keep["last_count"] = max(keep["last_count"], t.get("last_count", -1e9))
                del self.tracks[tid]

    # ---------------- 绘制 ----------------
    def annotate(self, frame, draw_tracks=True):
        h, w = frame.shape[:2]
        H = self.hysteresis

        if self.axis == "x":
            # ---------- 竖线：左右过线 ----------
            lx = max(1, min(int(self.line_y), w - 2))
            x1, x2 = max(0, lx - H), min(w, lx + H)
            if x2 > x1:
                band = frame[:, x1:x2].copy()
                cv2.rectangle(band, (0, 0), (x2 - x1, h), self.COL_BAND, -1)
                cv2.addWeighted(band, 0.28, frame[:, x1:x2], 0.72, 0, frame[:, x1:x2])
            for x in (x1, x2):
                for y in range(0, h, 24):
                    cv2.line(frame, (x, y), (x, min(y + 12, h)), self.COL_LINE, 1)
            cv2.line(frame, (lx, 0), (lx, h), self.COL_LINE, 2)
            cv2.putText(frame, "COUNT LINE", (lx + 6, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COL_LINE, 1)
            cv2.putText(frame, "OUT <", (max(4, lx - 78), h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COL_ABOVE, 1)
            cv2.putText(frame, "IN >", (min(w - 52, lx + 8), h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COL_BELOW, 1)
        else:
            # ---------- 横线：上下过线 ----------
            ly = max(1, min(int(self.line_y), h - 2))
            y1, y2 = max(0, ly - H), min(h, ly + H)
            if y2 > y1:
                band = frame[y1:y2, :].copy()
                cv2.rectangle(band, (0, 0), (w, y2 - y1), self.COL_BAND, -1)
                cv2.addWeighted(band, 0.28, frame[y1:y2, :], 0.72, 0, frame[y1:y2, :])

            for y in (y1, y2):
                for x in range(0, w, 24):
                    cv2.line(frame, (x, y), (min(x + 12, w), y), self.COL_LINE, 1)
            cv2.line(frame, (0, ly), (w, ly), self.COL_LINE, 2)
            cv2.putText(frame, "COUNT LINE", (w - 150, ly - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COL_LINE, 1)
            cv2.putText(frame, "IN v", (6, ly + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        self.COL_BELOW, 1)
            cv2.putText(frame, "OUT ^", (6, ly - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        self.COL_ABOVE, 1)

        if draw_tracks:
            now = time.time()
            with self.lock:
                tracks = list(self.tracks.items())
            for tid, t in tracks:
                if t["hits"] < self.min_hits:
                    continue
                x, y, bw, bh = [int(v) for v in t["box"]]
                fresh = (now - t["last_count"]) < 1.2
                col = self.COL_COUNTED if fresh else (
                    self.COL_BELOW if t["zone"] > 0 else self.COL_ABOVE)
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), col, 3 if fresh else 2)
                cx, cy = t["centroid"]
                cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)
                cv2.putText(frame, f"P#{tid} {t['score']:.2f}", (x, max(12, y - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)

            txt = (f"IN:{self.enter_count}  OUT:{self.exit_count}  "
                   f"NOW:{max(0, self.enter_count - self.exit_count)}")
            cv2.putText(frame, txt, (10, 25), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
        return frame

    # ---------------- 其它 ----------------
    def reset(self):
        """重置会话计数（对应前台“重置计数”按钮）"""
        with self.lock:
            self.enter_count = 0
            self.exit_count = 0
            self.tracks.clear()
            self.next_id = 1
            if hasattr(self.detector, "reset"):
                self.detector.reset()

    def set_line(self, pos):
        with self.lock:
            self.line_y = int(pos)
            if self.axis == "x":
                config.COUNT_LINE_X = int(pos)
            else:
                config.COUNT_LINE_Y = int(pos)

    def set_axis(self, axis):
        """切换计数线方向；切换后重置轨迹，避免旧轨迹带着旧坐标跨线"""
        axis = str(axis).lower()
        if axis not in ("x", "y") or axis == self.axis:
            return
        with self.lock:
            self.axis = axis
            self.tracks.clear()
            self.next_id = 1
            self.line_y = (getattr(config, "COUNT_LINE_X", self.frame_w // 2)
                           if axis == "x" else config.COUNT_LINE_Y)

    def set_match_distance(self, d):
        with self.lock:
            self.match_distance = int(d)
            config.MATCH_DISTANCE = int(d)

    def snapshot(self):
        with self.lock:
            return {
                "enter": self.enter_count,
                "exit": self.exit_count,
                "current": max(0, self.enter_count - self.exit_count),
                "tracks": len(self.tracks),
            }

    def info(self):
        return dict(self.detector_info,
                    line_y=self.line_y, hysteresis=self.hysteresis,
                    cooldown=self.cooldown, match_distance=self.match_distance)


def process_frame(frame, counter):
    """检测 → 跟踪 → 计数 → 标注，返回 (标注帧, 事件列表)"""
    detections = counter.detect_people(frame)
    events = counter.update(detections, frame=frame)
    frame = counter.annotate(frame)
    return frame, events