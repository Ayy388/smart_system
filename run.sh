#!/bin/bash
# 项目根目录启动脚本（自动进入 flask_app 运行）
# 用法：./run.sh          —— 真实摄像头模式
#       ./run.sh sim     —— 模拟画面模式（演示人流走动计数）
cd "$(dirname "$0")/flask_app"
exec ./run.sh "$@"
