#!/bin/bash
# /usr/local/bin/spi-kiosk.sh —— 在 SPI 触摸屏上以 kiosk 模式显示 Flask 网页
# 前提：Flask 服务已在 :5000 运行（由 smart-system.service 提供）
# 当 HDMI 接显示器时，本脚本由 spi-kiosk.service 的 ExecCondition 阻止执行。
set -euo pipefail

# 1. 找到 SPI framebuffer（fb_ili9486），可能是 fb0 或 fb1
fbnum=$(awk '/fb_ili9486/ {print $1}' /proc/fb)
if [ -z "$fbnum" ]; then
  echo "spi-kiosk: no fb_ili9486 framebuffer found in /proc/fb" >&2
  exit 1
fi

# 2. 生成 X 配置，指向 SPI framebuffer
cat > /etc/X11/xorg-spi.conf <<CONF
Section "ServerFlags"
    Option "AutoAddGPU" "false"
    Option "DontZap" "true"
EndSection

Section "ServerLayout"
    Identifier "SPILayout"
    Screen "SPIScreen"
EndSection

Section "Device"
    Identifier "SPIDevice"
    Driver "fbdev"
    Option "fbdev" "/dev/fb${fbnum}"
EndSection

Section "Screen"
    Identifier "SPIScreen"
    Device "SPIDevice"
    SubSection "Display"
        Virtual 480 320
    EndSubSection
EndSection
CONF
echo "spi-kiosk: using /dev/fb${fbnum}"

# 3. 切到 tty2 并启动 X（与原仓库一致，避免与 HDMI 上的 :0 冲突）
chvt 2
export HOME=/root
export XDG_VTNR=2
export DISPLAY=:0

# 启动 X server
exec /usr/bin/Xorg :0 vt2 -config /etc/X11/xorg-spi.conf -nocursor
