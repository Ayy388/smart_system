#!/bin/bash
# /usr/local/bin/spi-chromium-kiosk.sh —— 在 SPI 触摸屏上以 kiosk 模式运行 Chromium 显示 Flask 页面
# 由 spi-kiosk.service 在 X 启动成功后调用
set -euo pipefail

export DISPLAY=:0
export HOME=/root
URL="${1:-http://127.0.0.1:5000/}"

# 等待 Flask 服务就绪
for i in $(seq 1 30); do
  if curl -sf "$URL" >/dev/null 2>&1; then break; fi
  sleep 1
done

# 等待 X server 就绪
for i in $(seq 1 20); do
  if [ -S /tmp/.X11-unix/X0 ]; then break; fi
  sleep 0.5
done

exec /usr/bin/chromium \
  --no-sandbox \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-translate \
  --disable-features=TranslateUI \
  --no-first-run \
  --no-default-browser-check \
  --disable-session-crashed-bubble \
  --disable-infobars \
  --hide-scrollbars \
  --start-fullscreen \
  --kiosk \
  --app="$URL" \
  --window-size=480,320 \
  --window-position=0,0 \
  "$URL"
