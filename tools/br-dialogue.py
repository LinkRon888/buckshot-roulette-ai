#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓「屏幕对话框」上的文字（电话/放大镜/庄家说话都走这个 Label）。

为什么要单独一个脚本：
  PowerShell 控制台会把 UTF-8 中文显示成乱码，用 read 工具读文件才准。
  对话框只显示 3 秒左右，所以要连续采样、把不同内容都记下来。

用法:
    python tools/br-dialogue.py --sec 12          # 采样 12 秒
    python tools/br-dialogue.py --sec 20 --follow # 一直跑，新内容就打印

输出: out/br/dialogue_capture.txt（UTF-8，每行一条，带时间戳）
"""
import argparse
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'out', 'br', 'state.json')
OUT = os.path.join(ROOT, 'out', 'br', 'dialogue_capture.txt')


def read_state():
    for _ in range(20):
        try:
            with open(STATE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            time.sleep(0.06)
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sec', type=float, default=12.0, help='采样多少秒')
    ap.add_argument('--follow', action='store_true', help='一直跑（Ctrl+C 停）')
    ap.add_argument('--minlen', type=int, default=1, help='少于这么多字的不记')
    a = ap.parse_args()

    open(OUT, 'w', encoding='utf-8').close()
    seen = set()
    t0 = time.time()
    try:
        while a.follow or time.time() - t0 < a.sec:
            d = read_state()
            txt = str(d.get('dialogue') or '').strip()
            if len(txt) >= a.minlen and txt not in seen:
                seen.add(txt)
                line = '%s | %s' % (time.strftime('%H:%M:%S'), txt.replace('\n', ' / '))
                with open(OUT, 'a', encoding='utf-8') as f:
                    f.write(line + '\n')
                print(line, flush=True)
            time.sleep(0.12)
    except KeyboardInterrupt:
        pass
    print('抓到 %d 条不同对话 -> %s' % (len(seen), OUT), flush=True)


if __name__ == '__main__':
    main()
