#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令写 think.txt + decision.txt —— 给 AI 省 token 用。

为什么要这个脚本：
  AI 每个决策点要写两个文件。如果用 `python -c "..."` 直接写，
  中文 + 嵌套引号在 PowerShell 里非常容易撑破，失败了还得重试一次
  （重试 = 多一次完整请求 = 多花一份钱）。

  用这个脚本只有一层引号。两种用法：

      python tools\\br-set.py dealer                  # 只写 decision
      python tools\\br-set.py "50/50 打庄家" dealer    # think + decision

  选择题（药瓶/菜单/加倍）用第一种：
      python tools\\br-set.py yes

  输出只有一个字符 k（既确认成功，又不占 token）。

顺序：**先写 decision.txt，再写 think.txt**。
  反过来的话，万一 think 那半出错，decision 没落地，主循环会一直等。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BR = os.path.join(ROOT, 'out', 'br')


def main(argv):
    args = [a for a in argv[1:]]
    if not args:
        print('用法: br-set.py <decision>   或   br-set.py "<think>" <decision>')
        return 2

    if len(args) == 1:
        think, dec = '', args[0]
    else:
        think, dec = args[0], args[1]

    if not dec.strip():
        print('decision 不能为空')
        return 2

    # 先 decision —— 它落地了主循环就能往下走
    with io.open(os.path.join(BR, 'decision.txt'), 'w', encoding='utf-8') as f:
        f.write(dec.strip())

    # 再 think —— 只给面板看，写到哪步都不影响游戏
    if think.strip():
        with io.open(os.path.join(BR, 'think.txt'), 'w', encoding='utf-8') as f:
            f.write(think.strip())

    print('k')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
