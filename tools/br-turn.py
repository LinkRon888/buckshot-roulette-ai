# -*- coding: utf-8 -*-
"""我出决策、脚本执行：一个回合一次调用。

用法：
  python tools/br-turn.py show
      紧凑显示盘面（这是我要"看"的全部信息）

  python tools/br-turn.py run [--think 文本] [--next 文本] \
      [--wait 60] [--item 手铐] [--item 小刀] [--shoot 庄家|自己]

run 会：
  1. 等轮到我（can_shoot，最多 --wait 秒）
  2. 把 think/next 写到左上角面板
  3. 依次使用 --item 指定的道具（每个都回读确认真的少了）
  4. --shoot 指定的目标：点枪 → 点目标 → 回读验证弹数变化
  5. 打印一行结果

道具名可以写中文：手铐/小刀/放大镜/啤酒/香烟/过期药
"""
import argparse
import ctypes
import io
import json
import os
import sys
import time

BR = os.path.join('out', 'br')
STATE = os.path.join(BR, 'state.json')
NEXT = os.path.join(BR, 'next.txt')
THINK = os.path.join(BR, 'think.txt')
ACT = os.path.join(BR, 'actlog.txt')
STOP = os.path.join(BR, 'STOP')
GRID_Y_OFFSET = {2: 70, 7: 190}

# ===== 实测网格（tools/br-hovermap.py 扫出来的，2026-11-09）=====
DEALER_CANDS = [(1295, 350), (1240, 350), (1350, 350), (1130, 350), (1460, 350),
                (1295, 400), (1240, 400)]
SELF_CANDS = [(1295, 1200), (1240, 1200), (1350, 1200), (1295, 1300),
              (1130, 1200), (1460, 1200)]
CASE_CANDS = [(1295, 1200), (1020, 1200), (1570, 1200), (1240, 1100), (1350, 1100)]
GUN_CANDS = [(1240, 600), (1240, 700), (1130, 800), (1350, 500), (1350, 300),
             (1130, 700), (1240, 500), (1130, 900)]

GUN = (1240, 600)
TARGETS = {'庄家': (1295, 350), '自己': (1295, 1200),
           'dealer': (1295, 350), 'self': (1295, 1200)}



GUN = (1290, 620)   # 用户实测：枪
TARGETS = {'庄家': (1274, 375), '自己': (1277, 1230),
           'dealer': (1274, 375), 'self': (1277, 1230)}

ALIAS = {
    '手铐': 'handcuffs', '小刀': 'handsaw', '锯': 'handsaw', '手锯': 'handsaw',
    '放大镜': 'magnifying glass', '啤酒': 'beer', '香烟': 'cigarettes', '烟': 'cigarettes',
    '过期药': 'expired medicine', '手机': 'burner phone',
}
CN = {v: k for k, v in ALIAS.items()}

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()


class _PT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class _MI(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('md', ctypes.c_ulong),
                ('fl', ctypes.c_ulong), ('tm', ctypes.c_ulong), ('ex', ctypes.c_void_p)]


class _IN(ctypes.Structure):
    _fields_ = [('t', ctypes.c_ulong), ('mi', _MI)]


def send(flag):
    i = _IN()
    i.t = 0
    i.mi.fl = flag
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(_IN))


def st():
    for _ in range(8):
        try:
            return json.load(open(STATE, encoding='utf-8'))
        except Exception:
            time.sleep(0.08)
    return {}


def find_window():
    res = []

    def cb(h, l):
        n = user32.GetWindowTextLengthW(h)
        if n:
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, b, n + 1)
            if 'Buckshot' in b.value:
                res.append(h)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(cb), 0)
    return res[0] if res else None


SCREEN_W, SCREEN_H = 2560, 1600


def _mi(dx, dy, fl):
    i = _IN()
    i.t = 0
    i.mi.dx = dx
    i.mi.dy = dy
    i.mi.fl = fl
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(_IN))


def smooth_click(x, y, hover=0.5):
    """绝对 SendInput 移动 + 悬停 + 点击。

    关键：不能用 SetCursorPos——游戏收不到 motion 事件，内部光标不会跟过去，
    点了也等于没点。必须用 MOUSEEVENTF_MOVE|MOUSEEVENTF_ABSOLUTE。
    """
    if os.path.exists(STOP):
        return False
    h = find_window()
    if not h or user32.GetForegroundWindow() != h:
        return False
    pt = _PT()
    user32.GetCursorPos(ctypes.byref(pt))
    x0, y0 = pt.x, pt.y
    x, y = float(x), float(y)
    if abs(x0 - x) < 2 and abs(y0 - y) < 2:
        x0, y0 = x0 + 5, y0 + 5
        _mi(int(x0 * 65535 / (SCREEN_W - 1)), int(y0 * 65535 / (SCREEN_H - 1)), 0x8001)
        time.sleep(0.05)
    for i in range(1, 17):
        cx = x0 + (x - x0) * i / 16.0
        cy = y0 + (y - y0) * i / 16.0
        _mi(int(cx * 65535 / (SCREEN_W - 1)), int(cy * 65535 / (SCREEN_H - 1)), 0x8001)
        time.sleep(0.016)
    time.sleep(hover)
    _mi(0, 0, 0x0002)
    time.sleep(0.07)
    _mi(0, 0, 0x0004)
    return True


def screen_of(vx, vy, s):
    win = s.get('win_ds') or [2560, 1600]
    vp = s.get('vp_size') or [960, 540]
    return (int(vx * win[0] / float(vp[0])), int(vy * win[1] / float(vp[1])))


def item_pos(s, name):
    gi = None
    for it in (s.get('item_slots') or []):
        if len(it) >= 3 and str(it[0]) == name and bool(it[2]):
            gi = int(it[1])
            break
    if gi is None:
        return None
    for g in (s.get('my_slots') or []):
        if int(g[0]) == gi:
            return screen_of(g[2], g[3] + GRID_Y_OFFSET.get(gi, 0), s)
    return None


def count_item(s, name):
    return sum(1 for x in (s.get('items_player') or []) if x == name)


def panel(think_txt='', next_txt=''):
    try:
        if think_txt:
            open(THINK, 'w', encoding='utf-8').write(think_txt)
        if next_txt:
            open(NEXT, 'w', encoding='utf-8').write(next_txt)
        if next_txt:
            old = []
            if os.path.exists(ACT):
                old = open(ACT, encoding='utf-8').read().splitlines()
            old = ([time.strftime('%H:%M:%S') + ' ' + next_txt] + old)[:5]
            open(ACT, 'w', encoding='utf-8').write('\n'.join(old))
    except Exception:
        pass


def show():
    d = st()
    if not d:
        print('读不到 state.json（游戏是否用 --main-pack 启动？）')
        return
    print('socket=%s  can_shoot=%s  round=%s batch=%s' % (
        d.get('socket'), d.get('can_shoot'), d.get('round'), d.get('batch')))
    print('血 我%d : 庄%d   |   %d实 %d空 剩%d发' % (
        int(d.get('hp_player') or 0), int(d.get('hp_dealer') or 0),
        int(d.get('live') or 0), int(d.get('blank') or 0), int(d.get('left') or 0)))
    flags = []
    if d.get('sawed'):
        flags.append('已锯枪')
    if d.get('player_cuffed'):
        flags.append('我被铐')
    if d.get('dealer_cuffed'):
        flags.append('庄被铐')
    print('状态: %s' % (' '.join(flags) if flags else '无'))
    mine = {}
    for it in (d.get('item_slots') or []):
        if len(it) >= 3 and bool(it[2]):
            nm = str(it[0])
            mine[nm] = mine.get(nm, 0) + 1
    print('我的道具: %s' % ('  '.join('%s×%d' % (CN.get(k, k), v) for k, v in mine.items()) or '无'))
    hold = [str(it[0]) for it in (d.get('item_slots') or []) if len(it) >= 3 and not bool(it[2])]
    print('手上拿着: %s' % (CN.get(hold[0], hold[0]) if hold else '无'))
    print('空格: %s' % (' '.join(str(int(g[0])) for g in (d.get('my_slots') or []) if not bool(g[1])) or '无'))
    print('抽道具: %s/%s' % (d.get('grabbed'), d.get('quota')))


def wait_can_shoot(timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = st()
        # can_shoot = 枪在桌上能拿；can_aim = 枪已在手、该选目标了。
        # 空包打自己之后枪不撒手，游戏直接进 can_aim，必须也能算"轮到我"
        if d.get('can_shoot') or d.get('can_aim'):
            return d
        if os.path.exists(STOP):
            return {}
        time.sleep(0.25)
    return {}


def use_one(name_en):
    s = st()
    pos = item_pos(s, name_en)
    if not pos:
        print('  [X] %s 拿不到格子坐标' % CN.get(name_en, name_en))
        return False
    before = count_item(s, name_en)
    if before <= 0:
        print('  [X] 没有 %s' % CN.get(name_en, name_en))
        return False
    if not smooth_click(pos[0], pos[1]):
        print('  [X] %s 点击被拒（游戏不在前台？）' % CN.get(name_en, name_en))
        return False
    for _ in range(8):
        time.sleep(0.18)
        a = st()
        if count_item(a, name_en) < before:
            print('  [OK] 用了 %s' % CN.get(name_en, name_en))
            return True
    print('  [X] %s 点了但道具没少' % CN.get(name_en, name_en))
    return False



def move_only(x, y, wait=0.35):
    """只移动不点击（SendInput 绝对移动，游戏才收得到）"""
    if os.path.exists(STOP):
        return False
    h = find_window()
    if not h or user32.GetForegroundWindow() != h:
        return False
    pt = _PT()
    user32.GetCursorPos(ctypes.byref(pt))
    x0, y0 = pt.x, pt.y
    x, y = float(x), float(y)
    for i in range(1, 13):
        cx = x0 + (x - x0) * i / 12.0
        cy = y0 + (y - y0) * i / 12.0
        _mi(int(cx * 65535 / (SCREEN_W - 1)), int(cy * 65535 / (SCREEN_H - 1)), 0x8001)
        time.sleep(0.012)
    time.sleep(wait)
    return True


def hover_alias():
    d = st()
    h = d.get('hover') or []
    return (h[2] if len(h) > 2 else '') or ''


def scan_for_alias(want):
    """候选点都失败时，粗扫桌面区域找目标（慢，但只在需要时用）"""
    for y in range(250, 1150, 110):
        for x in range(950, 1701, 110):
            if os.path.exists(STOP):
                return None
            if not move_only(x, y, 0.22):
                return None
            if hover_alias() == want:
                return (x, y)
    return None


def click_alias(want, cands, label=''):
    """在候选点里找 alias == want 的位置并点击。返回 (成功, 用的点)"""
    for (x, y) in cands:
        if os.path.exists(STOP):
            return False, None
        if not move_only(x, y):
            return False, None
        got = hover_alias()
        if got == want:
            if smooth_click(x, y, 0.25):
                return True, (x, y)
            return False, None
    # 候选点都不行 → 粗扫一遍
    print('  候选点没命中 %s，开始扫描...' % want)
    pt = scan_for_alias(want)
    if pt and smooth_click(pt[0], pt[1], 0.25):
        print('  扫描找到 %s 在 %s' % (want, pt))
        return True, pt
    return False, None


# 候选点：以常见位置为中心铺开


def shoot_click(target_cn):
    before = st()
    if not before.get('can_aim'):
        ok, pt = click_alias('shotgun', GUN_CANDS)
        if not ok:
            print('  [X] 找不到枪（hover 里没有 shotgun）')
            return False
        print('  拿到枪（点 %s）' % (pt,))
        for _ in range(20):
            time.sleep(0.15)
            if st().get('can_aim'):
                break
    want = 'text dealer' if target_cn in ('庄家', 'dealer') else 'text you'
    cands = DEALER_CANDS if want == 'text dealer' else SELF_CANDS
    ok, pt = click_alias(want, cands)
    if not ok:
        print('  [X] 找不到目标 %s' % want)
        return False
    print('  点了 %s（位置 %s）' % (want, pt))
    after = st()
    for _ in range(40):
        time.sleep(0.2)
        after = st()
        if int(after.get('left') or 0) < int(before.get('left') or 0) or \
           int(after.get('hp_dealer') or 0) != int(before.get('hp_dealer') or 0) or \
           int(after.get('hp_player') or 0) != int(before.get('hp_player') or 0):
            break
    d_l = int(before.get('left') or 0) - int(after.get('left') or 0)
    d_d = int(before.get('hp_dealer') or 0) - int(after.get('hp_dealer') or 0)
    d_p = int(before.get('hp_player') or 0) - int(after.get('hp_player') or 0)
    if d_l <= 0 and d_d == 0 and d_p == 0:
        print('  [X] 点了但弹数、血量都没变')
        return False
    verdict = 'LIVE' if (d_d > 0 or d_p > 0) else 'BLANK'
    print('  [OK] 打%s -> %s  庄-%d 我-%d 弹-%d' % (target_cn, verdict, d_d, d_p, max(d_l, 0)))
    print('  现在 我%d : 庄%d' % (int(after.get('hp_player') or 0), int(after.get('hp_dealer') or 0)))
    return True




# ===== 命令通道（mod 里 cmd.txt -> 直接调游戏函数，不用鼠标）=====
CMD_FILE = os.path.join('out', 'br', 'cmd.txt')
RES_FILE = os.path.join('out', 'br', 'cmd_result.txt')


def send_cmd(line, timeout=1.2):
    """写一条命令给 mod，等它返回结果。返回 (成功, 原始结果文本)"""
    try:
        if os.path.exists(RES_FILE):
            os.remove(RES_FILE)
    except Exception:
        pass
    try:
        with open(CMD_FILE, 'w', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        return False, 'write failed: %s' % e
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(RES_FILE):
            time.sleep(0.03)
            try:
                txt = io.open(RES_FILE, encoding='utf-8').read().strip()
            except Exception:
                txt = ''
            return txt.startswith('OK'), txt
        time.sleep(0.04)
    return False, 'no result'


def cmd_available():
    """命令通道能不能用：看 state.json 里有没有 actions 字段"""
    d = st()
    return 'actions' in d or 'allowed' in d


def grab_gun_cmd():
    ok, txt = send_cmd('grab_gun')
    return ok, txt


def use_cmd(name_en):
    ok, txt = send_cmd('use|' + name_en)
    return ok, txt


def grab_item_cmd():
    return send_cmd('grab_item')


def place_cmd(gi):
    return send_cmd('place|%d' % gi)


def shoot(target_cn):
    """先走命令通道；不通就退回像素点击（旧路径原样保留）"""
    before = st()
    who = 'dealer' if target_cn in ('庄家', 'dealer') else 'self'
    if cmd_available():
        # 枪必须已经在手上——不自动补拿，保证"先拿枪再决定打谁"是看得见的两个动作
        if not before.get('can_aim'):
            print('  [X] 枪不在手上，先执行 grab')
            return False
        alias_t = 'text dealer' if who == 'dealer' else 'text you'
        ok, txt = send_visual(alias_t, 'shoot|' + who)
        print('  [cmd] shoot|%s -> %s' % (who, txt))
        if ok:
            after = st()
            for _ in range(40):
                time.sleep(0.2)
                after = st()
                if int(after.get('left') or 0) < int(before.get('left') or 0) or \
                   int(after.get('hp_dealer') or 0) != int(before.get('hp_dealer') or 0) or \
                   int(after.get('hp_player') or 0) != int(before.get('hp_player') or 0):
                    break
            d_l = int(before.get('left') or 0) - int(after.get('left') or 0)
            d_d = int(before.get('hp_dealer') or 0) - int(after.get('hp_dealer') or 0)
            d_p = int(before.get('hp_player') or 0) - int(after.get('hp_player') or 0)
            if d_l > 0 or d_d or d_p:
                verdict = 'LIVE' if (d_d > 0 or d_p > 0) else 'BLANK'
                print('  [OK] 打%s -> %s  庄-%d 我-%d 弹-%d' % (target_cn, verdict, d_d, d_p, max(d_l, 0)))
                print('  现在 我%d : 庄%d' % (int(after.get('hp_player') or 0), int(after.get('hp_dealer') or 0)))
                return True
            print('  [cmd] 命令成功但盘面没变，等一下再判')
        print('  [cmd] 通道不成，退回点击')
    return shoot_click(target_cn)



SCENE_FILE = os.path.join('out', 'br', 'scene.json')


def scene_st():
    for _ in range(20):
        try:
            return json.load(open(SCENE_FILE, encoding='utf-8'))
        except Exception:
            time.sleep(0.08)
    return {}


def phase():
    """根据 mod 给的字段判断当前处于哪个阶段。返回 (阶段名, 说明)"""
    s = scene_st()
    d = st()
    scn = s.get('scene') or ''
    sk = d.get('socket') or s.get('socket') or ''
    hpp = int(d.get('hp_player') or 0)
    hpd = int(d.get('hp_dealer') or 0)
    allowed = d.get('allowed') or []
    if not d.get('in_match'):
        if scn == 'menu':
            return ('menu', '在主菜单')
        return ('loading', '不在对局中（scene=%s）' % scn)
    if scn == 'heaven':
        return ('death_heaven', '死亡过场（天堂）')
    if sk == '' and hpp == 0 and hpd == 0:
        return ('cutscene', '过场/死亡动画：镜头无 socket、血量归零')
    if sk == 'briefcase':
        return ('item_phase', '道具阶段（可以抽道具）')
    if sk == 'shell compartment':
        return ('reload', '正在装弹')
    if sk == 'cash briefcase':
        return ('prize', '领奖阶段')
    if d.get('can_aim'):
        return ('aiming', '枪在手，该选打谁')
    if d.get('can_shoot') or 'shotgun' in allowed:
        return ('battle_my_turn', '对局中，轮到我了')
    if sk == 'enemy':
        return ('battle_enemy_turn', '对局中，庄家回合')
    if sk:
        return ('other', '镜头=%s' % sk)
    return ('unknown', '认不出来（socket 空、血量非 0）')


def wait_phase(targets, timeout=120, label=''):
    """等到阶段进入 targets 之一，或出现可执行动作"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(STOP):
            return None
        ph, why = phase()
        if ph in targets:
            return ph, why
        # 有任何允许的交互也可以视为可行动
        d = st()
        if d.get('allowed'):
            return 'actable', '出现的可交互: %s' % d.get('allowed')
        time.sleep(0.4)
    return None




def dealer_holding_gun(d=None):
    d = d or st()
    di = (d.get('managers') or {}).get('dealer intelligence') or {}
    return bool(di.get('dealerHoldingShotgun'))


def my_aim_ready(d=None):
    """我拿着枪、可以进行决策的那一刻"""
    d = d or st()
    return (str(d.get('socket')) == 'home'
            and bool(d.get('can_aim'))
            and not dealer_holding_gun(d))


def wait_my_aim(timeout=90):
    """等"枪在我手上"这一刻；期间绝不做决策。返回那一刻的状态"""
    t0 = time.time()
    last = ''
    while time.time() - t0 < timeout:
        if os.path.exists(STOP):
            return None
        d = st()
        if my_aim_ready(d):
            return d
        # 记录为什么还没到
        why = []
        if str(d.get('socket')) != 'home':
            why.append('socket=%s' % d.get('socket'))
        if not d.get('can_aim'):
            why.append('can_aim=false')
        if dealer_holding_gun(d):
            why.append('庄家拿着枪')
        s = ','.join(why)
        if s != last:
            last = s
        time.sleep(0.3)
    return None


def decide_shot(d):
    """在"枪在我手"的实时数据上做决策。返回 (dealer|self, 理由)"""
    hp_p = int(d.get('hp_player') or 0)
    hp_d = int(d.get('hp_dealer') or 0)
    live = int(d.get('live') or 0)
    blank = int(d.get('blank') or 0)
    left = int(d.get('left') or 0)
    nxt = d.get('next_shell') or ''
    if left <= 0:
        return None, '没有子弹了'
    # 1 血时绝不能打自己
    if hp_p <= 1 and live > 0:
        return 'dealer', '我只有%d血，打自己可能立刻结束（%d实%d空）' % (hp_p, live, blank)
    # 全是空包：打自己没风险，还能保回合
    if live == 0 and blank > 0:
        return 'self', '全是空包（0实%d空），打自己不掉血还保住回合' % blank
    # 空包占多数：打自己
    if blank > live:
        return 'self', '空包占多数（%d实%d空），打自己%s概率不掉血还保回合' % (live, blank, blank * 100 // left)
    # 其余：进攻
    return 'dealer', '实弹不少于空包（%d实%d空），打庄家他只剩%d血' % (live, blank, hp_d)


def auto_turn(timeout=90):
    """完整自动回合：等我拿枪 → 现场决策 → 开枪"""
    d = wait_my_aim(timeout)
    if not d:
        print('[auto] 没等到"枪在我手上"')
        return False
    target, why = decide_shot(d)
    if not target:
        print('[auto] 不决策：%s' % why)
        return False
    print('[auto] 现场盘面: %s实%s空 剩%s发  我%d:庄%d' % (
        d.get('live'), d.get('blank'), d.get('left'), d.get('hp_player'), d.get('hp_dealer')))
    print('[auto] 决策: 打%s —— %s' % ('庄家' if target == 'dealer' else '自己', why))
    panel(why, '打%s' % ('庄家' if target == 'dealer' else '自己'))
    return shoot('庄家' if target == 'dealer' else '自己')







# 伪点击用的候选点（实测网格）
_ALIAS_PTS = {
    'shotgun': [(1240, 600), (1240, 700), (1130, 800), (1350, 500), (1240, 500), (1130, 700)],
    'text dealer': [(1295, 350), (1240, 350), (1350, 350), (1130, 350), (1460, 350)],
    'text you': [(1295, 1200), (1240, 1200), (1350, 1200), (1295, 1300), (1130, 1200)],
    'briefcase intake': [(1295, 1200), (1020, 1200), (1570, 1200), (1240, 1100), (1295, 1300)],
}
_ALIAS_CACHE = {}




kernel32 = ctypes.windll.kernel32


def ensure_foreground():
    """把游戏切到前台并拿到焦点。伪点击必须在前台才看得见。"""
    h = find_window()
    if not h:
        return False
    if user32.GetForegroundWindow() == h:
        return True
    user32.ShowWindow(h, 9)
    user32.SetForegroundWindow(h)
    time.sleep(0.15)
    if user32.GetForegroundWindow() == h:
        return True
    # 用 AttachThreadInput 硬抢
    cur = kernel32.GetCurrentThreadId()
    tid = user32.GetWindowThreadProcessId(h, None)
    try:
        if tid and tid != cur:
            user32.AttachThreadInput(cur, tid, True)
        user32.BringWindowToTop(h)
        user32.SetForegroundWindow(h)
        user32.SetFocus(h)
    finally:
        if tid and tid != cur:
            user32.AttachThreadInput(cur, tid, False)
    time.sleep(0.2)
    return user32.GetForegroundWindow() == h

def move_to_alias(alias, verify=True):
    """把鼠标移到别名对应的对象上。返回是否成功。

    先试缓存点，再试预设点，最后粗扫。全程用 hover 确认。
    """
    if os.path.exists(STOP):
        return False
    if not ensure_foreground():
        print('  （切不到前台，不动鼠标）')
        return False
    cands = []
    if alias in _ALIAS_CACHE:
        cands.append(_ALIAS_CACHE[alias])
    cands += _ALIAS_PTS.get(alias, [])
    for (x, y) in cands:
        if not move_only(x, y, 0.3):
            return False
        if not verify or hover_alias() == alias:
            _ALIAS_CACHE[alias] = (x, y)
            return True
    # 粗扫
    for y in range(250, 1450, 110):
        for x in range(950, 1701, 110):
            if os.path.exists(STOP):
                return False
            if not move_only(x, y, 0.2):
                return False
            if hover_alias() == alias:
                _ALIAS_CACHE[alias] = (x, y)
                print('  （扫描找到 %s 在 (%d,%d)）' % (alias, x, y))
                return True
    return False


def send_visual(alias, line, timeout=1.2):
    """伪点击：先移鼠标到对象上，再发命令。没有对应别名就直接发。"""
    if alias:
        ok = move_to_alias(alias)
        if ok:
            print('  鼠标停在 %s 上' % alias)
        else:
            print('  没找到 %s 的位置，直接发命令' % alias)
    return send_cmd(line, timeout)




NEED_FILE = os.path.join('out', 'br', 'need_decision.txt')


def cmd_wait_decision(timeout=600):
    """等决策点。

    先看现在有没有"正在等我"的决策点：
        need_decision.txt 存在 且 decision.txt 不存在
    有就立刻返回（这是之前最费时间的地方：已经挂起了却去等下一轮）。
    没有才进入等待。
    """
    dec_file = os.path.join('out', 'br', 'decision.txt')

    # 我上一次"看到"决策点的时刻。need_decision.txt 比它旧 = 已经被我回答过、
    # 但循环还没清掉的陈旧文件，不能当成新决策点。
    MARK = os.path.join('out', 'br', '_last_seen_need.txt')

    def pending():
        try:
            if not os.path.exists(NEED_FILE):
                return None
            if os.path.exists(dec_file):
                return None
            nm = os.path.getmtime(NEED_FILE)
            if time.time() - nm > 300:
                return None
            if os.path.exists(MARK):
                try:
                    if nm <= os.path.getmtime(MARK):
                        return None
                except Exception:
                    pass
            return io.open(NEED_FILE, encoding='utf-8').read().strip()
        except Exception:
            return None

    def mark_seen():
        try:
            with open(MARK, 'w', encoding='utf-8') as f:
                f.write(str(time.time()))
        except Exception:
            pass

    def show(txt):
        print('=== 决策点 ===')
        print(txt)
        print()
        print('请在 out/br/decision.txt 里写：')
        print('  self                        打自己')
        print('  dealer                      打庄家')
        print('  use:手铐;shoot:dealer       先用手铐再打庄家')

    cur = pending()
    if cur:
        mark_seen()
        print('[立即]（决策点已经挂着，没等）')
        show(cur)
        return

    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(STOP):
            print('（收到 STOP，退出等待）')
            return
        cur = pending()
        if cur:
            mark_seen()
            print('[等待 %.1f 秒后到达]' % (time.time() - t0))
            show(cur)
            return
        time.sleep(0.05)
    print('（等了 %d 秒没有决策点）' % timeout)

def cmd_grab(timeout=30):
    """只做一件事：拿枪。等动画播完、can_aim 变 true 才返回。"""
    d = st()
    if str(d.get('socket')) != 'home':
        print('现在不是我的回合（socket=%s），不拿枪' % d.get('socket'))
        return False
    if dealer_holding_gun(d):
        print('庄家拿着枪，不拿')
        return False
    if d.get('can_aim'):
        print('枪已经在我手上')
        return True
    ok, txt = send_visual('shotgun', 'grab_gun')
    print('grab_gun -> %s' % txt)
    if not ok:
        return False
    t0 = time.time()
    while time.time() - t0 < timeout:
        if st().get('can_aim'):
            print('枪到手（等了 %.1f 秒，动画播完）' % (time.time() - t0))
            return True
        time.sleep(0.15)
    print('命令成功但 can_aim 没变 true')
    return False

def cmd_wait(timeout=120):
    """等到"我拿着枪"的那一刻，把实时盘面打出来给决策者看。不做任何决策。

    枪还在桌上（can_shoot=true / can_aim=false）时先拿枪再等。
    """
    t0 = time.time()
    grabbed = False
    while time.time() - t0 < timeout:
        if os.path.exists(STOP):
            return
        x = st()
        if str(x.get('socket')) == 'home' and not dealer_holding_gun(x):
            if x.get('can_aim'):
                break
            if x.get('can_shoot') and not grabbed:
                r = send_cmd('grab_gun')
                print('  拿枪: %s' % r[1])
                grabbed = True
        time.sleep(0.3)
    print('等"枪在我手上"（socket=home + can_aim + 庄家没拿枪）...')
    d = wait_my_aim(max(5, timeout))
    if not d:
        print('没等到。当前:')
        x = st()
        print('  socket=%s can_aim=%s 庄家拿枪=%s 我%d:庄%d %d实%d空 剩%d' % (
            x.get('socket'), x.get('can_aim'), dealer_holding_gun(x),
            int(x.get('hp_player') or 0), int(x.get('hp_dealer') or 0),
            int(x.get('live') or 0), int(x.get('blank') or 0), int(x.get('left') or 0)))
        return
    print()
    print('=== 轮到我、枪在手，实时盘面 ===')
    print('  我 %d : 庄 %d' % (int(d.get('hp_player') or 0), int(d.get('hp_dealer') or 0)))
    print('  %d 实弹 / %d 空包 / 剩 %d 发' % (
        int(d.get('live') or 0), int(d.get('blank') or 0), int(d.get('left') or 0)))
    flags = []
    if d.get('sawed'): flags.append('已锯枪')
    if d.get('dealer_cuffed'): flags.append('庄家被铐')
    if d.get('player_cuffed'): flags.append('我被铐')
    print('  状态: %s' % (' '.join(flags) if flags else '无'))
    mine = {}
    for it in (d.get('item_slots') or []):
        if len(it) >= 3 and bool(it[2]):
            mine[str(it[0])] = mine.get(str(it[0]), 0) + 1
    print('  道具: %s' % ('、'.join('%s×%d' % (CN.get(k, k), v) for k, v in mine.items()) or '无'))
    print()
    print('  —— 请决策：shoot dealer 还是 shoot self ——')

def parse_expect(txt):
    out = {}
    for part in (txt or '').split():
        if '=' in part:
            k, v = part.split('=', 1)
            out[k.strip()] = v.strip()
    return out


def check_expect(spec, s):
    diffs = []
    real = {
        'live': str(int(s.get('live') or 0)),
        'blank': str(int(s.get('blank') or 0)),
        'left': str(int(s.get('left') or 0)),
        'hp': '%d:%d' % (int(s.get('hp_player') or 0), int(s.get('hp_dealer') or 0)),
        'sawed': 'true' if s.get('sawed') else 'false',
        'dealer_cuffed': 'true' if s.get('dealer_cuffed') else 'false',
        'player_cuffed': 'true' if s.get('player_cuffed') else 'false',
    }
    for k, want in spec.items():
        got = real.get(k)
        if got is None:
            continue
        if got != want:
            diffs.append('%s 我以为是 %s，实际是 %s' % (k, want, got))
    return (len(diffs) == 0), '；'.join(diffs)


def snapshot_line(s):
    return ('%d实%d空 剩%d发  我%d:庄%d  %s%s%s' % (
        int(s.get('live') or 0), int(s.get('blank') or 0), int(s.get('left') or 0),
        int(s.get('hp_player') or 0), int(s.get('hp_dealer') or 0),
        '已锯枪 ' if s.get('sawed') else '',
        '庄被铐 ' if s.get('dealer_cuffed') else '',
        '我被铐' if s.get('player_cuffed') else '')).strip()


_CASE_PT = [None]      # 记住找到的箱口位置


def find_case_pt():
    """用 hover 找到箱口那一个点（只找一次，之后复用）"""
    if _CASE_PT[0]:
        return _CASE_PT[0]
    for (x, y) in CASE_CANDS:
        if os.path.exists(STOP):
            return None
        if not move_only(x, y):
            return None
        if hover_alias() == 'briefcase intake':
            _CASE_PT[0] = (x, y)
            print('  箱口位置确定: (%d, %d)' % (x, y))
            return _CASE_PT[0]
    return None


def draw_once():
    """抽一次：先去箱口，确认 hover 还是箱口，再点"""
    pt = find_case_pt()
    if not pt:
        return False
    before_n = len((st().get('item_slots') or []))
    # 每次抽之前确认一次位置（判定可能随镜头微移）
    if not move_only(pt[0], pt[1]):
        return False
    if hover_alias() != 'briefcase intake':
        _CASE_PT[0] = None          # 位置失效了，重新找
        pt = find_case_pt()
        if not pt:
            return False
    if not smooth_click(pt[0], pt[1], 0.3):
        return False
    for _ in range(12):
        time.sleep(0.2)
        a = st()
        if len(a.get('item_slots') or []) != before_n:
            return True
        if any(len(it) >= 3 and not bool(it[2]) for it in (a.get('item_slots') or [])):
            return True
    return False


def do_items(s):
    """道具阶段：优先用命令（grab_item / place），命令不行再退回点击"""
    t0 = time.time()
    placed = 0
    drew = 0
    use_cmd = cmd_available()
    while time.time() - t0 < 120:
        if os.path.exists(STOP):
            break
        s = st()
        if s.get('socket') != 'briefcase':
            print('  道具阶段结束（socket=%s）' % s.get('socket'))
            break
        # 限额：grabbed >= quota 就不能再抽了
        quota = int(s.get('quota') or 0)
        grabbed = int(s.get('grabbed') or 0)
        hold = [str(it[0]) for it in (s.get('item_slots') or []) if len(it) >= 3 and not bool(it[2])]
        if quota > 0 and grabbed >= quota and not hold:
            print('  抽满了（%d/%d），不再抽' % (grabbed, quota))
            break
        if hold:
            free = [int(g[0]) for g in (s.get('my_slots') or []) if not bool(g[1])]
            if not free:
                print('  格子满了')
                break
            gi = free[0]
            if use_cmd:
                ok, txt = send_cmd('place|%d' % gi)
                print('  place|%d -> %s' % (gi, txt))
                if ok:
                    placed += 1
                    time.sleep(0.45)
                    continue
            # 兜底：点击
            for g in (s.get('my_slots') or []):
                if int(g[0]) == gi:
                    pos = screen_of(g[2], g[3] + GRID_Y_OFFSET.get(gi, 0), s)
                    if smooth_click(pos[0], pos[1], 0.35):
                        time.sleep(0.4)
                        placed += 1
                    break
            continue
        # 没拿着东西 → 抽
        if use_cmd:
            ok, txt = send_cmd('grab_item')
            if ok:
                drew += 1
                time.sleep(0.5)
                continue
            print('  grab_item 失败，退回点击: %s' % txt)
            use_cmd = False
        pt = find_case_pt()
        if not pt:
            print('  找不到箱口')
            break
        before_n = len(s.get('item_slots') or [])
        if smooth_click(pt[0], pt[1], 0.35):
            time.sleep(0.5)
            a = st()
            if len(a.get('item_slots') or []) != before_n or any(
                    len(it) >= 3 and not bool(it[2]) for it in (a.get('item_slots') or [])):
                drew += 1
    print('  道具阶段：抽了 %d 次，放下 %d 个，用时 %.1f 秒' % (drew, placed, time.time() - t0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['show', 'run', 'draw', 'wait', 'shoot', 'grab', 'wait-decision'])
    ap.add_argument('target', nargs='?', default='')
    ap.add_argument('--think', default='')
    ap.add_argument('--next', default='')
    ap.add_argument('--wait', type=float, default=60.0)
    ap.add_argument('--item', action='append', default=[])
    ap.add_argument('--shoot', default='')
    ap.add_argument('--expect', default='')

    a = ap.parse_args()

    if a.cmd == 'show':
        show()
        return

    if a.cmd == 'wait-decision':
        cmd_wait_decision(int(a.wait) if a.wait else 600)
        return

    if a.cmd == 'grab':
        cmd_grab()
        return

    if a.cmd == 'wait':
        cmd_wait(a.wait)
        return

    if a.cmd == 'shoot':
        tgt = a.target or a.shoot
        if tgt not in ('dealer', 'self', '庄家', '自己'):
            print('shoot 后面要给 dealer 或 self')
            return
        ok = shoot(tgt)
        print('完成' if ok else '没打成')
        return

    if a.cmd == 'draw':
        panel('道具阶段：抽→放，抽到箱子空为止', '自动抽放道具')
        do_items(st())
        show()
        return

    t0 = time.time()
    panel(a.think, a.next or '等待轮到我')
    if a.item or a.shoot:
        d = wait_can_shoot(a.wait)
        if not d:
            print('没等到轮到我（%.0f 秒）' % a.wait)
            return
    # 动手前再读一次真实盘面，和"我以为的"对比
    now = st()
    print('  动手前盘面: %s' % snapshot_line(now))
    spec = parse_expect(a.expect)
    if spec:
        ok, why = check_expect(spec, now)
        if not ok:
            print('  !! 盘面和我做决策时不一样，中止不动手')
            print('     %s' % why)
            print('     请按当前盘面重新决策')
            return
        print('  盘面核对：一致（%s）' % a.expect)

    for name in a.item:
        en = ALIAS.get(name, name)
        if not use_one(en):
            print('道具中断，这一回合到此为止')
            return
    if a.shoot:
        # 道具可能改变了盘面（比如锯枪），打之前再看一眼
        if a.item:
            print('  用完道具后: %s' % snapshot_line(st()))
        shoot(a.shoot)
    print('用时 %.1f 秒' % (time.time() - t0))


if __name__ == '__main__':
    main()
