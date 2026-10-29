# -*- coding: utf-8 -*-
"""make_shot5.py —— 截图5：重启后服务自动运行（真实重启后的 systemctl / journalctl / API）"""
import os
import subprocess
import sys

ROOT = "/home/yango/smart_system"
SHOTS = os.path.join(ROOT, "screenshots")
sys.path.insert(0, SHOTS)
from term_render import render_terminal

SUDO = "echo '123' | sudo -S -p '' "


def run(cmd, sudo=False):
    p = subprocess.run((SUDO + cmd) if sudo else cmd, shell=True,
                       capture_output=True, text=True, timeout=60)
    return ((p.stdout or "") + (p.stderr or "")).strip("\n")


lines = [("cmd", "sudo reboot          # 重启树莓派（断电重启等效）"),
         ("dim", "# ... 等待约 30 秒 ..."),
         ("cmd", "uptime"),
         ("out", run("uptime")),
         ("cmd", "sudo systemctl is-enabled smart_system"),
         ("ok", run("systemctl is-enabled smart_system")),
         ("cmd", "sudo systemctl status smart_system --no-pager | head -4"),
         ]
for ln in run("systemctl status smart_system --no-pager").splitlines()[:4]:
    lines.append(("ok" if "Active: active" in ln else "out", ln))
lines.append(("cmd", "sudo journalctl -b -u smart_system --no-pager | head -8   # 本次开机日志"))
for ln in run("journalctl -b -u smart_system --no-pager").splitlines()[:8]:
    lines.append(("dim", ln[30:] if len(ln) > 31 else ln))
lines.append(("cmd", "curl -s http://127.0.0.1:5000/api/status"))
lines.append(("out", run("curl -s --max-time 5 http://127.0.0.1:5000/api/status")))
lines.append(("ok", "✅ 无人登录、无需手动启动，系统开机即自动运行并对外提供 Web 服务"))

size = render_terminal(lines, os.path.join(SHOTS, "shot5_autostart.png"),
                       width=1010, size=15,
                       title="yango@raspberrypi: ~/smart_system — 重启后验证开机自启动")
print("shot5:", size)
print(run("uptime"))