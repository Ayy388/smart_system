#!/bin/bash
# 启动智能人流统计与考勤系统
# 用法：./run.sh          —— 真实摄像头模式
#       ./run.sh sim     —— 模拟画面模式（演示人流走动计数）
cd "$(dirname "$0")"
if [ "$1" = "sim" ]; then
  echo ">> 模拟画面模式"
  SIM=1 ../venv/bin/python app.py
else
  echo ">> 真实摄像头模式"
  ../venv/bin/python app.py
fi
