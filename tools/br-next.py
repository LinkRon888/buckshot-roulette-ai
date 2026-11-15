#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写决策 + 等下一个决策点 + 把新局面打出来 —— 一手只花一次模型请求。

为什么要这个脚本
    现在的流程每手是 3 次请求：
        ① read need_decision.txt          → 看局面
        ② pwsh 写 decision.txt            → 出决策
        ③ pwsh 等下一个决策点              → 醒来，但只得到"等到了"
        ④ （还得再 read 一次才看得到新局面）
    第 ③ 步纯属"醒一下"，白白多一次完整请求。
    把 ①②③④ 合成一次调用，成本直接砍到 1/3。

用法
    python tools\\br-next.py "50/50 打庄家" dealer
    python tools\\br-next.py yes                      # 选择题：只写 decision
    python tools\\br-next.py "..." dealer --max 3     # 连着等 3 手

输出（每一手一段）
    k
    === 第 1 手的新局面 ===
    我 2 : 庄 1 | 3 实 2 空 剩 5 发 | 我的: 小刀×1
    --- 你的教训（lessons.md）---
    ...
    --- 回答前 ---
    1) ...

    k 表示"决策已落地"。后面跟的就是下一手要读的内容。

安全设计
    - 先写 decision 再写 think（decision 落地了主循环就不会卡）
    - 每段等待都有超时，超时返回人话而不是 traceback
    - --max 控制最多连等几手（默认 1），避免一个 turn 拖太长
    - 任何异常都打印可读原因，退出码 1，AI 能据此回退到 read + 手动写
"""
import argparse
import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BR = os.path.join(ROOT, 'out', 'br')
NEED = os.path.join(BR, 'need_decision.txt')
DEC = os.path.join(BR, 'decision.txt')
THINK = os.path.join(BR, 'think.txt')
LOG = os.path.join(BR, 'run2.log')


def read_file(p):
    try:
        with io.open(p, encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return None


def write_file(p, text):
    with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def loop_alive():
    """粗判主循环还活着：run2.log 最近 3 分钟内有更新。"""
    try:
        return (time.time() - os.path.getmtime(LOG)) < 180
    except Exception:
        return True


def wait_next(old_text, timeout):
    """等 need_decision.txt 出现和 old_text 不同的内容。

    返回 (新内容, 状态)。状态：'ok' / 'timeout' / 'dead'
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        cur = read_file(NEED)
        if cur and cur.strip() and cur != old_text:
            return cur, 'ok'
        if not loop_alive():
            return None, 'dead'
        time.sleep(0.5)
    return None, 'timeout'


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('think', nargs='?', default='')
    ap.add_argument('decision', nargs='?', default='')
    ap.add_argument('--max', type=int, default=1,
                    help='最多连等几手（默认 1，建议不超过 3）')
    ap.add_argument('--timeout', type=float, default=600.0,
                    help='每次等待的秒数上限（默认 600）')
    a = ap.parse_args(argv[1:])

    # 支持两种写法：
    #   br-next.py yes                 -> think='yes', decision=''
    #   br-next.py "想法" dealer        -> think='想法', decision='dealer'
    if not a.decision:
        think, dec = '', a.think
    else:
        think, dec = a.think, a.decision

    if not dec.strip():
        print('用法: br-next.py "<think，可为空>" <decision>')
        print('  或: br-next.py yes            （选择题只写 decision）')
        return 2

    if not os.path.isdir(BR):
        print('!! 找不到 out/br 目录：%s' % BR)
        print('   是不是工作目录不对？应该在游戏 AI 包的根目录跑。')
        return 1

    # 记下当前决策点内容，之后用它判断"新局面来了"
    old = read_file(NEED) or ''

    # ① 先写 decision —— 它落地了主循环就能往下走，think 失败也不影响
    try:
        write_file(DEC, dec.strip())
    except Exception as e:
        print('!! 写 decision.txt 失败: %s' % e)
        return 1

    # ② 再写 think（只给面板看）
    if think.strip():
        try:
            write_file(THINK, think.strip())
        except Exception:
            pass  # think 写不进去不影响游戏

    print('k')

    # ③ 等新局面
    rounds = 0
    while rounds < max(1, a.max):
        new, why = wait_next(old, a.timeout)
        if why == 'ok':
            rounds += 1
            print()
            print('=== 第 %d 手的新局面 ===' % rounds)
            print(new.strip())
            old = new
            if rounds >= a.max:
                return 0
            # 连等多手时，这里需要 AI 已经写好下一手的 decision
            # 但脚本没法替它判断 —— 所以连等只在 AI 提前给了下一手时才工作。
            # 实际使用建议 --max 1（默认），拿到新局面就走。
            return 0
        if why == 'dead':
            print()
            print('!! 主循环好像停了（run2.log 3 分钟没更新）')
            print('   看 out/br/run2.log 最后 20 行确认。')
            return 1
        print()
        print('!! 等了 %.0f 秒没有新决策点。' % a.timeout)
        print('   可能是：对局还没走到决策点 / 游戏卡住了 / 主循环退出。')
        print('   查 out/br/run2.log 最后 20 行。')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
