r"""一键安装：解包 -> 应用补丁 -> 重新打包。

用法：
    python tools\setup.py --exe "<游戏exe完整路径>"

它做三件事：
  1. 把你的游戏文件解包到 out\pckall
  2. 把 patches\*.patch 应用到解出来的原始 .gd 上（产物在 out\br\patch\scripts）
  3. 重新打包成 out\br\mod.pck（约 700 MB）

如果你已经解过包，加 --skip-extract 可跳过第 1 步。
"""
import argparse
import shutil
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from pckpack import find_pack, read_dir, extract, collect, write_pack  # noqa: E402

PATCH_DIR = os.path.join(ROOT, 'patches')
WORK = os.path.join(ROOT, 'out', 'pckall')
OUT_PATCH = os.path.join(ROOT, 'out', 'br', 'patch', 'scripts')
OUT_PCK = os.path.join(ROOT, 'out', 'br', 'mod.pck')


def apply_unified(orig_lines, patch_text):
    """把 unified diff 应用到 orig_lines（保留换行符的列表），返回新列表。"""
    lines = patch_text.splitlines(keepends=True)
    out = []
    pos = 0
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.startswith('@@'):
            i += 1
            continue
        # 解析 @@ -a,b +c,d @@
        head = ln.split('@@')[1].strip()
        old_rng = head.split()[0]
        start = int(old_rng[1:].split(',')[0])
        if start > 0:
            start -= 1
        # 复制到 hunk 之前的原始行
        while pos < start:
            out.append(orig_lines[pos])
            pos += 1
        i += 1
        # 应用 hunk 内的行
        while i < len(lines) and not lines[i].startswith('@@'):
            h = lines[i]
            if h.startswith(' '):
                out.append(orig_lines[pos])
                pos += 1
            elif h.startswith('-'):
                pos += 1
            elif h.startswith('+'):
                out.append(h[1:])
            i += 1
    while pos < len(orig_lines):
        out.append(orig_lines[pos])
        pos += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True, help='Buckshot Roulette.exe 的完整路径')
    ap.add_argument('--skip-extract', action='store_true', help='跳过解包（已经解过时用）')
    ap.add_argument('--keep-pckall', action='store_true',
                    help='装完保留 out/pckall（默认会删，省 2GB 磁盘）')
    a = ap.parse_args()

    if not os.path.isdir(PATCH_DIR):
        print('!! 找不到 patches 目录：' + PATCH_DIR)
        return 1

    # ---- 第 1 步：解包 ----
    info = find_pack(a.exe)
    files = read_dir(a.exe, info)
    _pckall_existed = os.path.isdir(WORK)
    print('[1/3] 游戏包: %d 个文件, engine=%s' % (len(files), info['engine']))
    if a.skip_extract and os.path.isdir(WORK):
        print('      跳过解包（--skip-extract）')
    else:
        extract(a.exe, info, files, WORK)

    # ---- 第 2 步：应用补丁 ----
    os.makedirs(OUT_PATCH, exist_ok=True)

    # 立绘：HUD 从 out/br/char-200.png 读，包里的在 art/char-200.png，要挪过去
    src_art = os.path.join(ROOT, "art", "char-200.png")
    dst_art = os.path.join(ROOT, "out", "br", "char-200.png")
    if os.path.isfile(src_art):
        os.makedirs(os.path.dirname(dst_art), exist_ok=True)
        shutil.copy2(src_art, dst_art)
        print("      |  立绘已复制 -> out/br/char-200.png")
    else:
        print("      |  提醒：找不到 art/char-200.png，面板右下角会是空的")

    # 训练资产：lessons（经验）/ style（风格）/ lang（语言）。
    # 不装这些，别人装完就是"裸奔"——AI 从零开始，会重演所有踩过的坑。
    import shutil as _shutil
    for _name in ("lessons.md", "style.txt", "lang.txt"):
        _src = os.path.join(ROOT, _name)
        _dst = os.path.join(ROOT, "out", "br", _name)
        if not os.path.exists(_src):
            continue
        try:
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            _shutil.copy2(_src, _dst)
            print("      |  %s -> out/br/" % _name)
        except Exception as _e:
            print("      |  %s 复制失败: %s" % (_name, _e))

    print('[2/3] 应用补丁:')
    ok = 0
    for name in sorted(os.listdir(PATCH_DIR)):
        if not name.endswith('.patch'):
            continue
        target = name[:-len('.patch')]          # 例如 HealthCounter.gd
        orig = os.path.join(WORK, 'scripts', target)
        if not os.path.isfile(orig):
            print('      !! 找不到原始文件: scripts/%s' % target)
            continue
        with open(orig, 'r', encoding='utf-8', errors='replace') as f:
            orig_lines = f.readlines()
        with open(os.path.join(PATCH_DIR, name), 'r', encoding='utf-8') as f:
            ptxt = f.read()
        new_lines = apply_unified(orig_lines, ptxt)
        text = ''.join(new_lines)
        # 自动把占位路径换成这台机器的真实路径（用户不用手动改）
        placeholder = 'C:/Users/<YOUR_USER>/Documents/deepseek-harness/default-workspace/out/br/'
        actual = os.path.join(ROOT, 'out', 'br').replace(os.sep, '/') + '/'
        if placeholder in text:
            text = text.replace(placeholder, actual)
            print('      路径自动替换 -> ' + actual)
        with open(os.path.join(OUT_PATCH, target), 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print('      %-22s %d 行 -> %d 行' % (target, len(orig_lines), len(new_lines)))
        ok += 1
    if ok == 0:
        print('!! 一个补丁都没应用成功')
        return 1

    # ---- 第 3 步：打包 ----
    print('[3/3] 重新打包...')
    entries = collect(WORK, os.path.join(ROOT, 'out', 'br', 'patch'))
    os.makedirs(os.path.dirname(OUT_PCK), exist_ok=True)
    write_pack(entries, OUT_PCK)
    print()
    print('完成！')
    print('  产物: ' + OUT_PCK)
    print('  下一步: python tools\\br-launch.py')

    # 清理：把解包目录删掉（占 2~3GB，装完就没用了）。
    # 只在「本次是全新解包」时删 —— 如果之前就有（比如用 --skip-extract 复用），
    # 那是别人要重复构建用的，别动。
    if not a.keep_pckall and not _pckall_existed and os.path.isdir(WORK):
        _ok = False
        # rmtree 直接删长路径文件会 FileNotFoundError（游戏里有 270 字符的路径），
        # 先试 \\?\ 前缀。
        for _w in (WORK, '\\\\?\\' + os.path.abspath(WORK)):
            try:
                shutil.rmtree(_w)
                _ok = True
                break
            except Exception as _e:
                _last = _e
        if _ok:
            print("      └ 已清理临时解包目录 out/pckall（省下 2~3GB）")
        else:
            print("      └ 清理失败（不影响使用）: %s" % _last)
            print("         可以手动删: " + WORK)
    return 0


if __name__ == '__main__':
    sys.exit(main())
