# -*- coding: utf-8 -*-
# main.py —— 智能系统统一主程序（实验六：系统集成与发布）
# 课题C 统计组：智能人流统计与考勤系统
# 整合：摄像头采集线程 + 视觉处理（检测/跟踪/计数线判定）+ 数据库 + Flask Web服务
import signal
import sys
import time

import config
from app import app, start_capture_thread, load_settings

# ============================================================
# 主程序入口
# ============================================================
running = True


def signal_handler(sig, frame):
    """处理 Ctrl+C / systemctl stop 信号，优雅退出"""
    global running
    print("\n[系统] 收到退出信号，正在关闭...")
    running = False
    time.sleep(1)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 1) 视觉处理模块（检测 + 质心跟踪 + 计数线跨越判定）
    print("[系统] 视觉处理模块已加载（人体检测 → 质心跟踪 → 计数线判定）")

    # 2) AI 推理模块：统计组无需额外 AI 模块（保持注释状态）
    # 【农业组】from ai_module_leaf import LeafAI ; ai_module = LeafAI()
    # 【安防组】from ai_module_face import FaceAI ; ai_module = FaceAI()
    print("[系统] 统计组无需额外 AI 模块，跳过")

    # 3) 数据库与设置
    load_settings()
    print(f"[系统] 数据库就绪：{config.DB_PATH}")

    # 4) 启动摄像头采集线程（生产者，帧放入缓冲）
    start_capture_thread()
    time.sleep(3)
    print("[摄像头] 采集线程已启动")

    # 5) 主线程运行 Web 服务（消费者）：生产用 waitress，缺失时退回 Flask 内置服务器
    from app import counter
    info = counter.detector_info
    print(f"[系统] 检测器：{info.get('type')} / {info.get('model') or '-'} "
          f"/ 运行时 {info.get('runtime') or '-'}")
    print(f"[系统] Web服务启动，访问 http://树莓派IP:5000")
    print(f"[系统] 终端控制界面: http://<树莓派IP>:5000/")
    print(f"[系统] 管理后台:     http://<树莓派IP>:5000/dashboard")
    try:
        from waitress import serve
        print("[系统] 使用 waitress 生产级 WSGI 服务器（8 线程）")
        serve(app, host="0.0.0.0", port=5000, threads=8)
    except ImportError:
        print("[系统] 未安装 waitress，回退 Flask 开发服务器（仅调试用）")
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True,
                use_reloader=False)


if __name__ == "__main__":
    main()