#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恶魔轮盘：标准启动流程（固定顺序，别跳步）

顺序不能改，每一步都有踩过的坑在背后：
  1) 关旧进程 + 清命令文件        —— 上一局的 need_decision/decision 会干扰新局
  2) 带 mod.pck 启动              —— 不用 --main-pack 就是原版，mod 全无
  3) 窗口归位到 (0,0) 并验证换算   —— 每次启动游戏都会自己跑回 (789,485)，导致右下角被裁
  4) 检查 Godot 日志有没有脚本错误 —— .gd 改错一个字符就整个 autoload 挂掉、黑屏
  5) menu_start + 起主循环

用法:
    python tools/br-launch.py            完整启动
    python tools/br-launch.py --nomenu   只启动到菜单，不点开始
    python tools/br-launch.py --wait 20  启动后多等几秒
"""
import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

EXE = r'C:\Program Files (x86)\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe'
PACK = os.path.join(ROOT, 'out', 'br', 'mod.pck')
LOGDIR = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'Godot',
                      'app_userdata', 'Buckshot Roulette', 'logs')

BR = os.path.join(ROOT, 'out', 'br')
NEED = os.path.join(BR, 'need_decision.txt')
DEC = os.path.join(BR, 'decision.txt')
STOP = os.path.join(BR, 'STOP')
SCENE = os.path.join(BR, 'scene.json')
CLEAN = ['need_decision.txt', 'decision.txt', 'STOP', 'cmd_menu.txt', 'cmd_menu_result.txt',
         'cmd.txt', 'cmd_result.txt']


def say(msg):
    print(msg, flush=True)


def ps(cmd, timeout=30):
    """跑一段 PowerShell，返回 stdout。"""
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd],
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout or '') + (r.stderr or '')
    except Exception as e:
        return 'ERR %s' % e




def kill_loops():
    """杀掉所有 br-run2 循环。防止两个循环抢着写 need_decision.txt
    （踩过：br-launch 起一个，用户手动又起一个，结果看到的是旧进程写的）。"""
    ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
       "Where-Object { $_.CommandLine -match 'br-run2|br-dialogue' } | "
       "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    time.sleep(0.5)


def stop_hud():
    """关掉正在跑的面板。只按 hud.pid 里记的 PID 杀 —— 按命令行模糊匹配会连
    调用它的这个 shell 一起杀掉（命令行里也有 br-hud.ps1 字样，踩过两次）。"""
    pidf = os.path.join(ROOT, 'out', 'br', 'hud.pid')
    if os.path.exists(pidf):
        try:
            old = int(open(pidf, encoding='utf-8').read().strip())
        except Exception:
            old = 0
        if old > 0:
            ps('Stop-Process -Id %d -Force -ErrorAction SilentlyContinue' % old)
        try:
            os.remove(pidf)
        except Exception:
            pass
    time.sleep(0.6)


def start_hud():
    """起浮窗。必须用 CREATE_NO_WINDOW，否则会多一个可见的 PowerShell 控制台窗口
    （2026-11-13 踩过：关掉面板后那个控制台还留在桌面上）。"""
    say('[HUD] 启动浮窗（无控制台窗口）')
    hud = os.path.join(ROOT, 'tools', 'br-hud.ps1')
    if not os.path.exists(hud):
        say('   !! 找不到 %s' % hud)
        return None
    flags = 0
    if hasattr(subprocess, 'CREATE_NO_WINDOW'):
        flags = subprocess.CREATE_NO_WINDOW
    try:
        pr = subprocess.Popen(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', hud],
            cwd=ROOT, creationflags=flags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        say('   HUD PID: %d（游戏关掉它自己会退出）' % pr.pid)
        return pr
    except Exception as e:
        say('   !! 启动失败: %s' % e)
        return None


def step1_clean():
    say('[1/5] 关闭旧进程、清理命令文件')
    stop_hud()
    kill_loops()
    ps('Get-Process -Name "Buckshot*" -ErrorAction SilentlyContinue | '
       'ForEach-Object { Stop-Process -Id $_.Id -Force }')
    ps('Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | '
       'Where-Object { $_.CommandLine -match \'br-run2\' } | '
       'ForEach-Object { Stop-Process -Id $_.ProcessId -Force }')
    time.sleep(2)
    for n in CLEAN:
        p = os.path.join(BR, n)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    log = os.path.join(BR, 'run2.log')
    if os.path.exists(log):
        try:
            open(log, 'w', encoding='utf-8').close()
        except Exception:
            pass
    say('   已清理')


def step2_launch(wait):
    say('[2/5] 启动游戏（--main-pack out\\br\\mod.pck）')
    if not os.path.exists(PACK):
        raise SystemExit('找不到 mod 包: %s' % PACK)
    if not os.path.exists(EXE):
        raise SystemExit('找不到游戏: %s' % EXE)
    subprocess.Popen([EXE, '--main-pack', PACK], cwd=os.path.dirname(EXE))
    time.sleep(wait)


def step3_normalize():
    say('[3/5] 窗口归位检查')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'br-screencheck.py')],
                       capture_output=True, text=True)
    out = (r.stdout or '') + (r.stderr or '')
    for ln in out.splitlines():
        say('   ' + ln)
    # 关键判据：窗口必须在 (0,0)
    if '(0,0)' not in out:
        say('   !! 窗口归位结果里没看到 (0,0)，别继续')
        return False
    return True


def step4_logcheck():
    say('[4/5] 检查 Godot 日志')
    if not os.path.isdir(LOGDIR):
        say('   !! 没找到日志目录: %s' % LOGDIR)
        return True
    logs = [os.path.join(LOGDIR, f) for f in os.listdir(LOGDIR) if f.endswith('.log')]
    if not logs:
        say('   !! 没有 .log 文件')
        return True
    latest = max(logs, key=os.path.getmtime)
    bad = []
    try:
        with open(latest, encoding='utf-8', errors='replace') as f:
            for ln in f:
                if any(k in ln for k in ('SCRIPT ERROR', 'Parse Error', 'does not inherit')):
                    bad.append(ln.rstrip())
    except Exception as e:
        say('   读日志失败: %s' % e)
        return True
    if bad:
        say('   !! 有脚本错误（mod 可能没生效）：')
        for ln in bad[:6]:
            say('      ' + ln)
        return False
    say('   日志干净，没有脚本错误')
    return True


def step5_start(nomenu):
    if nomenu:
        say('[5/5] 跳过（--nomenu）')
        return
    say('[5/5] menu_start + 起主循环')
    import json
    for _ in range(30):
        try:
            with open(SCENE, encoding='utf-8') as f:
                sc = json.load(f).get('scene')
            say('   scene = %s' % sc)
            break
        except Exception:
            time.sleep(0.2)

    res = os.path.join(BR, 'cmd_menu_result.txt')
    if os.path.exists(res):
        os.remove(res)
    with open(os.path.join(BR, 'cmd_menu.txt'), 'w', encoding='utf-8') as f:
        f.write('menu_start')
    t0 = time.time()
    while time.time() - t0 < 10:
        if os.path.exists(res):
            say('   menu_start -> ' + open(res, encoding='utf-8').read().strip())
            break
        time.sleep(0.2)
    else:
        say('   menu_start -> 超时')

    time.sleep(4)
    start_hud()
    # 对话框抓取器常驻后台：电话/庄家说的话只显示 3 秒，
    # 让 AI 自己去起它不可靠（踩过：它忘了起，回头读 state.json 已经空了）。
    dlg = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, 'tools', 'br-dialogue.py'), '--follow'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0),
        cwd=ROOT)
    say('   对话框抓取 PID: %d（常驻，电话结果写到 out\\br\\dialogue_capture.txt）' % dlg.pid)
    p = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, 'tools', 'br-run2.py')],
        stdout=open(os.path.join(BR, 'loop_out.txt'), 'w', encoding='utf-8'),
        stderr=open(os.path.join(BR, 'loop_err.txt'), 'w', encoding='utf-8'),
        cwd=ROOT)
    say('   循环 PID: %d' % p.pid)
    say('完成。决策点会写到 out\\br\\need_decision.txt')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nomenu', action='store_true', help='只启动到菜单，不点开始')
    ap.add_argument('--wait', type=int, default=14, help='启动后等几秒（默认 14）')
    a = ap.parse_args()

    step1_clean()
    step2_launch(a.wait)
    if not step3_normalize():
        raise SystemExit(1)
    if not step4_logcheck():
        raise SystemExit(1)
    step5_start(a.nomenu)


if __name__ == '__main__':
    main()
