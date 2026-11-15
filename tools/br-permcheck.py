#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权限自检：这个会话能不能写工作区外的文件？

为什么要有这个脚本（而不是在文档里写 python -c）：
  文档里原来写的是
      python -c "open('$env:APPDATA\\_dsh_perm_test.txt','w')..."
  PowerShell 的引号 + $env: 展开 + 反斜杠，四层嵌套，实测会炸成
  Python 语法错误。AI 看到 SyntaxError 就分不清"权限不够"还是"命令写错了"，
  于是选择继续装 —— 后面游戏起来然后静默失败，排查半天。
  （2026-11-14 在真实新工作区里实测踩到）

用法：
    python tools\\br-permcheck.py

返回码：
    0 = 可写，权限够
    1 = 不可写，权限不够（会话要改成 danger-full-access）
"""
import os
import sys

TARGETS = [
    ('%APPDATA%\\Godot', '游戏要写这里（存档、日志）'),
    ('%TEMP%', '临时目录'),
]


def expand(p):
    return os.path.expandvars(p) if '%' in p else p


def check(path, desc):
    """在 path 下建一个临时文件，看能不能写。"""
    real = expand(path)
    if not os.path.isdir(real):
        # 目录不存在也算失败：游戏需要它存在或能创建
        try:
            os.makedirs(real, exist_ok=True)
        except Exception as e:
            print('  x  %-28s 建不了目录: %s' % (desc, e))
            return False
    probe = os.path.join(real, '_dsh_perm_test.txt')
    try:
        with open(probe, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(probe)
        print('  v  %-28s 可写' % desc)
        return True
    except Exception as e:
        print('  x  %-28s 不可写: %s' % (desc, type(e).__name__))
        return False


def main():
    print('权限自检')
    ok = True
    for path, desc in TARGETS:
        if not check(path, desc):
            ok = False

    print()
    if ok:
        print('=> 权限够，可以安装。')
        return 0

    print('=> 权限不够。')
    print()
    print('   游戏要写 %APPDATA%\\Godot（工作区外面），workspace-write 下起不来。')
    print('   而且报错会长得像"mod 坏了"，不是"权限不够"，白排查半天。')
    print()
    print('   请让用户把这个会话的权限改成 danger-full-access，然后重跑。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
