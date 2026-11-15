"""把 Godot PCK 解出来、打补丁、再重新打包成一个独立 .pck。
配合 Godot 的 `--main-pack` 用：不动原 exe、不动 Steam 文件。

用法:
  python tools/pckpack.py --exe <exe> --work out/pckall --out out/br/mod.pck --patch out/br/patch
patch 目录里的文件按相对路径覆盖（如 patch/scripts/HealthCounter.gd）。
"""
import argparse
import os
import struct
import sys

VLONG = '\\\\?\\'
MAGIC = b'GDPC'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pck import find_pack, read_dir  # noqa: E402


def longpath(p):
    r"""Windows 的 260 字符路径限制。

    游戏里有很深的资源路径（multiplayer/models/tabletops/... 那种），
    解压目录稍微深一点就会超 260，open() 直接 FileNotFoundError。
    加 "\\?\\" 前缀能绕开这个限制（要求绝对路径、且用反斜杠）。
    """
    if os.name != 'nt':
        return p
    p = os.path.abspath(p)
    if p.startswith('\\\\?\\'):
        return p
    return '\\\\?\\' + p


def extract(exe, info, files, work):
    os.makedirs(work, exist_ok=True)
    with open(exe, 'rb') as f:
        for i, x in enumerate(files):
            rel = x['path'].replace('res://', '')
            dst = os.path.join(work, rel)
            try:
                os.makedirs(os.path.dirname(longpath(dst)), exist_ok=True)
            except OSError:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
            f.seek(info['file_base'] + x['offset'])
            try:
                with open(longpath(dst), 'wb') as g:
                    g.write(f.read(x['size']))
            except (FileNotFoundError, OSError):
                # 长路径前缀也不行的话，至少给一句人话，别抛一坨 traceback
                raise SystemExit(
                    '\n!! 解包失败：路径太长（Windows 260 字符限制）\n'
                    '   出错文件: %s\n'
                    '   解决办法：把整个文件夹解压到更短的位置，比如 D:\\buckshot\\\n'
                    % rel)
            if (i + 1) % 500 == 0:
                print('  extracted %d/%d' % (i + 1, len(files)))
    print('extracted %d files -> %s' % (len(files), work))


def collect(work, patch):
    """遍历 work 目录，patch 里有同名文件就用 patch 的。"""
    out = []
    for root, _dirs, names in os.walk(longpath(work)):
        root = root.replace(VLONG, "") if root.startswith(VLONG) else root
        for n in names:
            full = os.path.join(root, n)
            rel = os.path.relpath(full, work).replace('\\', '/')
            src = os.path.join(patch, rel) if patch else None
            if src and os.path.isfile(src):
                out.append((rel, src))
            else:
                out.append((rel, full))
    out.sort(key=lambda t: t[0])
    return out


def write_pack(entries, out_path):
    blobs = []
    total = 0
    for rel, src in entries:
        with open(longpath(src), 'rb') as f:
            data = f.read()
        blobs.append((rel, data))
        total += len(data)

    dir_size = 0
    for rel, data in blobs:
        path = ('res://' + rel).encode('utf-8')
        plen = (len(path) + 3) // 4 * 4
        dir_size += 4 + plen + 16 + 16 + 4

    file_base = 96 + 4 + dir_size + 4
    file_base = (file_base + 15) // 16 * 16

    hdr = bytearray()
    hdr += MAGIC
    hdr += struct.pack('<I', 2)          # pack_version
    hdr += struct.pack('<I', 4)          # ver_major
    hdr += struct.pack('<I', 1)          # ver_minor
    hdr += struct.pack('<I', 1)          # ver_patch
    hdr += struct.pack('<I', 0)          # pack_flags
    hdr += struct.pack('<Q', file_base)
    hdr += b'\x00' * 64                  # reserved
    hdr += struct.pack('<I', len(blobs))

    import hashlib
    off = 0
    dirbytes = bytearray()
    for rel, data in blobs:
        path = ('res://' + rel).encode('utf-8')
        plen = (len(path) + 3) // 4 * 4
        dirbytes += struct.pack('<I', plen)
        dirbytes += path + b'\x00' * (plen - len(path))
        dirbytes += struct.pack('<QQ', off, len(data))
        dirbytes += hashlib.md5(data).digest()
        dirbytes += struct.pack('<I', 0)
        off += len(data)
    dirbytes += struct.pack('<I', 0)

    pad = file_base - (96 + 4 + len(dirbytes))
    with open(out_path, 'wb') as f:
        f.write(hdr)
        f.write(dirbytes)
        f.write(b'\x00' * pad)
        for rel, data in blobs:
            f.write(data)
    size = os.path.getsize(out_path)
    print('wrote %s  files=%d  file_base=%d  size=%.1f MB'
          % (out_path, len(blobs), file_base, size / 1048576.0))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--work', default='out/pckall')
    ap.add_argument('--patch', default='')
    ap.add_argument('--out', default='out/br/mod.pck')
    ap.add_argument('--skip-extract', action='store_true')
    ap.add_argument('--list-patched', action='store_true')
    a = ap.parse_args()

    info = find_pack(a.exe)
    files = read_dir(a.exe, info)
    print('pack @ %d engine=%s files=%d' % (info['offset'], info['engine'], len(files)))
    if not a.skip_extract:
        extract(a.exe, info, files, a.work)
    entries = collect(a.work, a.patch)
    print('collected %d files' % len(entries))
    if a.list_patched:
        for rel, src in entries:
            if a.patch and os.path.abspath(src).startswith(os.path.abspath(a.patch)):
                print('  PATCHED:', rel)
    write_pack(entries, a.out)
