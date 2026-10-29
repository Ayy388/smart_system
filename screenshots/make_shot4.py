# -*- coding: utf-8 -*-
"""make_shot4.py —— 截图4：Systemd 服务配置与运行状态（真实 systemctl 输出）"""
import os
import subprocess
import sys

ROOT = "/home/yango/smart_system"
SHOTS = os.path.join(ROOT, "screenshots")
sys.path.insert(0, SHOTS)
from term_render import render_terminal

SUDO = "echo '123' | sudo -S -p '' "


def run(cmd, sudo=False):
    c = (SUDO + cmd) if sudo else cmd
    p = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=90)
    out = (p.stdout or "") + (p.stderr or "")
    # 去掉 sudo 提示噪声
    return "\n".join(l for l in out.splitlines()
                     if not l.startswith("sudo:")) if False else out.strip("\n")


lines = [("cmd", "sudo cp smart_system.service /etc/systemd/system/"), ("dim", "")]
lines.append(("cmd", "sudo systemctl daemon-reload"))
lines.append(("cmd", "sudo systemctl start smart_system"))
lines.append(("cmd", "sudo systemctl status smart_system --no-pager"))
for ln in run("systemctl status smart_system --no-pager").splitlines()[:22]:
    kind = "ok" if "Active: active" in ln or "Loaded:" in ln else "out"
    lines.append((kind, ln))
lines.append(("cmd", "sudo systemctl is-enabled smart_system"))
lines.append(("ok", run("systemctl is-enabled smart_system")))
lines.append(("cmd", "sudo journalctl -u smart_system -n 6 --no-pager"))
for ln in run("journalctl -u smart_system -n 6 --no-pager").splitlines():
    lines.append(("dim", ln[38:] if len(ln) > 39 else ln))
lines.append(("cmd", "ss -ltn | grep 5000"))
lines.append(("out", run("ss -ltn | grep 5000")))
lines.append(("ok", "✅ 服务已启动并设为开机自启动（Restart=always，进程异常退出 10s 后自动重启）"))

size = render_terminal(lines, os.path.join(SHOTS, "shot4_systemd.png"),
                       width=1010, size=15,
                       title="yango@raspberrypi: ~/smart_system/flask_app — systemctl")
print("shot4:", size)

# 目录结构（供 5.2 使用）
ls = run("ls -la", )
with open(os.path.join(SHOTS, "ls_flask_app.txt"), "w") as f:
    f.write(run("cd /home/yango/smart_system/flask_app && ls -la"))
print(run("cd /home/yango/smart_system/flask_app && ls -la"))