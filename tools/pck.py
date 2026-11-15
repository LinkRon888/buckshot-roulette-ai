"""读 Godot 4 的 PCK（含嵌在 exe 里的那种），列出/导出文件。

用法:
  python tools/pck.py list  --exe <exe> [--limit 40]
  python tools/pck.py ext   --exe <exe> --outdir out/pck [--match .gd,.gdc]
  python tools/pck.py cat   --exe <exe> --path res://foo.txt

Godot 4 PCK v2 结构（小端）:
  header: magic 'GDPC' | pack_version u32 | ver_major u32 | ver_minor u32 |
          ver_patch u32 | pack_flags u32 | file_base u64 | 16*u32 保留
  entry:  path_len u32 | path[path_len] | offset u64 | size u64 | md5[16] | flags u32
  entry 以 path_len==0 结束；offset 相对 file_base
"""
import argparse
import os
import struct
import sys

MAGIC = b'GDPC'


def find_pack(exe):
    """在 exe 里找合法的 PCK 头（pack_version 1..3）。"""
    cands = []
    prev = b''
    off = 0
    CH = 8 << 20
    with open(exe, 'rb') as f:
        while True:
            buf = f.read(CH)
            if not buf:
                break
            data = prev + buf
            base = off - len(prev)
            i = data.find(MAGIC)
            while i >= 0:
                pos = base + i
                cands.append(pos)
                i = data.find(MAGIC, i + 1)
            prev = data[-8:]
            off += len(buf)
    for c in cands:
        with open(exe, 'rb') as f:
            f.seek(c)
            h = f.read(96)
            if len(h) < 96 or h[:4] != MAGIC:
                continue
            packver = struct.unpack('<I', h[4:8])[0]
            vmaj = struct.unpack('<I', h[8:12])[0]
            vmin = struct.unpack('<I', h[12:16])[0]
            vpat = struct.unpack('<I', h[16:20])[0]
            flags = struct.unpack('<I', h[20:24])[0]
            file_base = struct.unpack('<Q', h[24:32])[0]
            if 1 <= packver <= 3 and vmaj == 4:
                return {'offset': c, 'pack_version': packver,
                        'engine': '%d.%d.%d' % (vmaj, vmin, vpat),
                        'flags': flags, 'file_base': file_base}
    raise SystemExit('没找到合法的 PCK 头')


def read_dir(exe, info):
    files = []
    with open(exe, 'rb') as f:
        f.seek(info['offset'] + 96)
        # 实测（4.1.1 导出）：头后面先有一个 u32 文件数，然后才是条目
        head4 = f.read(4)
        count = struct.unpack('<I', head4)[0]
        if not (0 < count < 200000):
            f.seek(info['offset'] + 96)   # 没有计数字段，退回老格式
            count = -1
        while True:
            raw = f.read(4)
            if len(raw) < 4:
                break
            plen = struct.unpack('<I', raw)[0]
            if plen == 0 or plen > 4096:
                break
            path = f.read(plen).rstrip(b'\x00').decode('utf-8', 'replace')
            rest = f.read(16)
            if len(rest) < 16:
                break
            off, size = struct.unpack('<QQ', rest)
            md5 = f.read(16)
            flags = struct.unpack('<I', f.read(4))[0]
            files.append({'path': path, 'offset': off, 'size': size, 'flags': flags})
            if count > 0 and len(files) >= count:
                break
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['list', 'ext', 'cat', 'info'])
    ap.add_argument('--exe', required=True)
    ap.add_argument('--outdir', default='out/pck')
    ap.add_argument('--match', default='')
    ap.add_argument('--path', default='')
    ap.add_argument('--limit', type=int, default=40)
    a = ap.parse_args()

    info = find_pack(a.exe)
    print('PCK @ %d  engine=%s pack_version=%d file_base=%d' %
          (info['offset'], info['engine'], info['pack_version'], info['file_base']))
    files = read_dir(a.exe, info)
    total = sum(x['size'] for x in files)
    print('files=%d total=%.1f MB' % (len(files), total / 1048576.0))

    if a.cmd == 'info':
        exts = {}
        for x in files:
            e = os.path.splitext(x['path'])[1].lower() or '(none)'
            exts[e] = exts.get(e, 0) + 1
        for e, n in sorted(exts.items(), key=lambda kv: -kv[1])[:20]:
            print('  %-12s %d' % (e, n))
        return

    if a.cmd == 'list':
        for x in files[:a.limit]:
            print('  %10d  %s' % (x['size'], x['path']))
        return

    if a.cmd == 'cat':
        target = [x for x in files if x['path'] == a.path]
        if not target:
            raise SystemExit('没有这个文件')
        t = target[0]
        with open(a.exe, 'rb') as f:
            f.seek(info['file_base'] + t['offset'])
            data = f.read(t['size'])
        sys.stdout.buffer.write(data)
        return

    matches = [m.strip().lower() for m in a.match.split(',') if m.strip()]
    picked = [x for x in files if not matches or any(x['path'].lower().endswith(m) for m in matches)]
    print('导出 %d 个文件 -> %s' % (len(picked), a.outdir))
    os.makedirs(a.outdir, exist_ok=True)
    with open(a.exe, 'rb') as f:
        for x in picked:
            rel = x['path'].replace('res://', '')
            dst = os.path.join(a.outdir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            f.seek(info['file_base'] + x['offset'])
            with open(dst, 'wb') as g:
                g.write(f.read(x['size']))
    print('done')


if __name__ == '__main__':
    main()
