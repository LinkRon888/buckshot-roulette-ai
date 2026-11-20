# -*- coding: utf-8 -*-
"""主循环：把"机械动作"全部自动做完，只在**决策点**停下来等我。

解决的问题：每换一个阶段（门→生死状→签名→道具→领奖）我都要重新读一次状态再手动调一次，
中间就是发呆。这个脚本一直盯着 can_do 和 phase，出现什么就立刻做什么。

它自己不决定打谁。到了"枪在我手上"那一刻，它：
  1. 把实时盘面写到 out/br/need_decision.txt
  2. 等 out/br/decision.txt 出现（内容 dealer 或 self）
  3. 执行，删掉 decision.txt，继续循环

停止：创建 out/br/STOP 文件。
"""
import json
import os
import sys
import time

ROOT = os.path.join('out', 'br')
STATE = os.path.join(ROOT, 'state.json')
SCENE = os.path.join(ROOT, 'scene.json')
CMD = os.path.join(ROOT, 'cmd.txt')
RES = os.path.join(ROOT, 'cmd_result.txt')
STOP = os.path.join(ROOT, 'STOP')
NEED = os.path.join(ROOT, 'need_decision.txt')
DEC = os.path.join(ROOT, 'decision.txt')
LOG = os.path.join(ROOT, 'run2.log')

NOISE = {'text you', 'text dealer', 'crt'}
# 偷道具优先级（我的决定）：手铐窗口只有 7 秒，来不及逐个问，所以预先定好
# 小刀(伤害翻倍) > 放大镜(信息) > 电话(信息) > 手铐(夺回合) > 逆转器 > 啤酒 > 香烟 > 药片
STEAL_PRIORITY = ['handsaw', 'magnifying glass', 'burner phone', 'handcuffs',
                  'inverter', 'beer', 'cigarettes', 'expired medicine']
# 签名名字：从 out/br/player_name.txt 读，读不到就用默认值。
# 改名字只要改那个文件，不用动代码。
SIG_NAME_DEFAULT = 'player'   # 用户没指定名字时用这个（正好 6 格，是签名机上限）
SIG_NAME_MAX = 6    # 游戏签名机只有 6 个格子（SignatureManager: markerIndex != 6），多的打不进去


def load_player_name():
    """读名字文件；没有就返回默认值。带截断，防止超长打不进去。"""
    path = os.path.join('out', 'br', 'player_name.txt')
    try:
        if os.path.exists(path):
            s = open(path, encoding='utf-8').read().strip()
            if s:
                if len(s) > SIG_NAME_MAX:
                    log('  名字 %r 超长，截断到 %d 个字符' % (s, SIG_NAME_MAX))
                    s = s[:SIG_NAME_MAX]
                return s
    except Exception as e:
        log('  读名字文件失败: %s' % e)
    return SIG_NAME_DEFAULT


SIG_NAME = load_player_name()


# ==================== 多语言 ====================
# 语言从 out/br/lang.txt 读（zh / en）——跟面板 tools/br-hud.ps1 共用同一个文件，
# 改一处两边一起变。想加第三种语言：在 LANG 里加一个键（比如 de = {...}）补全字段就行。
#
# 注意：格式字符串（ammoFmt / itemFmt / hpFmt…）也放进字典里。
# 别把某一种语言的格式硬编码进拼接代码——那样一换语言就会输出 "0B 0L" 这种混合体。
ITEMS_ZH = {
    'beer': '啤酒', 'cigarettes': '香烟', 'handsaw': '小刀', 'handcuffs': '手铐',
    'magnifying glass': '放大镜', 'expired medicine': '药片',
    'burner phone': '电话', 'adrenaline': '肾上腺素', 'inverter': '逆转器',
}
ITEMS_EN = {
    'beer': 'Beer', 'cigarettes': 'Cigarettes', 'handsaw': 'Handsaw',
    'handcuffs': 'Handcuffs', 'magnifying glass': 'Magnifying Glass',
    'expired medicine': 'Pills', 'burner phone': 'Burner Phone',
    'adrenaline': 'Adrenaline', 'inverter': 'Inverter',
}

LANG = {
    'zh': {
        'hpFmt': '我 {p} : 庄 {d}',
        'ammoFmt': '{live} 实 {blank} 空 剩 {left} 发',
        'sawed': '已锯枪', 'dealerCuffed': '庄被铐',
        'magSee': '放大镜看的: {what}', 'liveShell': '实弹', 'blankShell': '空包',
        'mine': '我的: {items}', 'dealerItems': '庄家: {items}',
        'none': '无', 'itemFmt': '{name}×{n}', 'itemSep': '、',
        'aimLocked': '【枪已在手，不能再使用道具】',
        'needHint': ('\n--- 回答前 ---\n'
                     '1) 先写 out/br/think.txt（你的判断，面板会显示给人看）\n'
                     '2) 再写 out/br/decision.txt（self / dealer / use:X;shoot:Y）\n'),
        'askEnd': '一局结束了，要继续吗？',
        'askEndYes': '再开一局（menu_start）', 'askEndNo': '停在这里',
        'askPill': '药瓶：普通还是无尽？（当前 endless={e}）',
        'askPillYes': '嗑药：进无尽模式（每轮3小关，打完可翻倍）',
        'askPillNo': '普通：三大关，死亡回原关卡',
        'askPill2': '药瓶选择框已开着：普通还是无尽？',
        'askPillYes2': '嗑药：进无尽模式', 'askPillNo2': '普通：三大关',
        'askDbl': '翻倍：分数 {score}（上一轮 {prev}，已过 {rounds} 轮）',
        'askDblYes': '加倍（赢了翻倍，输了清零）', 'askDblNo': '见好就收（直接结算）',
        'dpPoint': '[决策点] {txt}',
        'dpChose': '[决策] {title} -> {k}',
        'dpBad': '[决策] 不认识的回答: {raw}（可选 {keys}）',
        'items': ITEMS_ZH,
    },
    'en': {
        'hpFmt': 'Me {p} : Dealer {d}',
        'ammoFmt': '{live} live / {blank} blank · {left} left',
        'sawed': 'SAWED', 'dealerCuffed': 'DEALER CUFFED',
        'magSee': 'magnifier: next is {what}', 'liveShell': 'LIVE', 'blankShell': 'BLANK',
        'mine': 'Mine: {items}', 'dealerItems': 'Dealer: {items}',
        'none': 'none', 'itemFmt': '{name} x{n}', 'itemSep': ', ',
        'aimLocked': '[gun in hand · no items]',
        'needHint': ('\n--- before you answer ---\n'
                     '1) write out/br/think.txt first (your reasoning; the HUD shows it)\n'
                     '2) then write out/br/decision.txt (self / dealer / use:X;shoot:Y)\n'),
        'askEnd': 'Round over. Play again?',
        'askEndYes': 'Play again (menu_start)', 'askEndNo': 'Stop here',
        'askPill': 'Pill: normal or endless? (endless now = {e})',
        'askPillYes': 'Take it: endless mode (3 stages a round, can double up after)',
        'askPillNo': 'Normal: 3 stages, death returns you to the same stage',
        'askPill2': 'Pill dialog already open: normal or endless?',
        'askPillYes2': 'Take it: endless mode', 'askPillNo2': 'Normal: 3 stages',
        'askDbl': 'Double up: score {score} (last {prev}, {rounds} rounds cleared)',
        'askDblYes': 'Double (win = x2, lose = 0)', 'askDblNo': 'Bank it (settle now)',
        'dpPoint': '[Decision] {txt}',
        'dpChose': '[Decision] {title} -> {k}',
        'dpBad': '[Decision] unknown answer: {raw} (want one of {keys})',
        'items': ITEMS_EN,
    },
}


def load_lang():
    """读 out/br/lang.txt；读不到或不认识就 zh。容忍 BOM、空白、大小写。"""
    try:
        p = os.path.join(ROOT, 'lang.txt')
        if os.path.exists(p):
            v = open(p, encoding='utf-8-sig').read().strip().lower()
            if v in LANG:
                return v
    except Exception:
        pass
    return 'zh'


LANGSET = load_lang()
T = LANG[LANGSET]


def item_label(name):
    """游戏里的英文道具名 -> 当前语言的显示名（取不到就原样返回）"""
    k = str(name)
    return (T.get('items') or {}).get(k, k)


def fmt_items(counts):
    """{英文道具名: 数量} -> 当前语言的一行道具清单"""
    if not counts:
        return T['none']
    out = [T['itemFmt'].format(name=item_label(k), n=v) for k, v in counts.items()]
    return T['itemSep'].join(out)


def rd(path):
    for _ in range(20):
        try:
            return json.load(open(path, encoding='utf-8'))
        except Exception:
            time.sleep(0.06)
    return {}


# 英文 Windows 上控制台编码可能不认中文（诊断日志是中文写的），
# 别让一次 print 抛 UnicodeEncodeError 把整局带崩。
# 顺便把重定向出去的日志统一成 UTF-8（管到文件里以前是 ANSI，换台机器就乱码）。
for _st in (sys.stdout, sys.stderr):
    try:
        _st.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def log(msg):
    line = time.strftime('%H:%M:%S ') + msg
    print(line)
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def send(line, timeout=6):
    try:
        if os.path.exists(RES):
            os.remove(RES)
    except Exception:
        pass
    try:
        with open(CMD, 'w', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        return False, 'write fail %s' % e
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(RES):
            time.sleep(0.03)
            txt = open(RES, encoding='utf-8').read().strip()
            return txt.startswith('OK'), txt
        time.sleep(0.05)
    return False, 'no result'


def send_menu(line, timeout=10):
    """走 autoload 的命令通道（跨场景可用，比如天堂界面的重试）"""
    res = os.path.join('out', 'br', 'cmd_menu_result.txt')
    cmd = os.path.join('out', 'br', 'cmd_menu.txt')
    try:
        if os.path.exists(res):
            os.remove(res)
    except Exception:
        pass
    with open(cmd, 'w', encoding='utf-8') as f:
        f.write(line)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(res):
            time.sleep(0.03)
            txt = open(res, encoding='utf-8').read().strip()
            return txt.startswith('OK'), txt
        time.sleep(0.05)
    return False, 'no result'


def can_do():
    d = rd(STATE)
    return [a for a in (d.get('can_do') or []) if a not in NOISE]


def dealer_holding(d):
    return bool(((d.get('managers') or {}).get('dealer intelligence') or {}).get('dealerHoldingShotgun'))


def my_turn_ready(d):
    """决策点：我的回合。枪在桌上（can_shoot）最理想——还能先用道具；
    枪已在手（can_aim）也算，但此时不能再用道具。"""
    if int(d.get('left') or 0) <= 0:
        return False
    if dealer_holding(d):
        return False
    if str(d.get('socket')) != 'home':
        return False
    return bool(d.get('can_shoot')) or bool(d.get('can_aim'))


def my_aim_ready(d):
    """执行用：枪已在我手上，可以开枪。"""
    if int(d.get('left') or 0) <= 0:
        return False
    return (str(d.get('socket')) == 'home' and bool(d.get('can_aim')) and not dealer_holding(d))


# 中文道具名：表已经在上面的多语言块里（ITEMS_ZH）。
# 这个名字留着，因为偷取日志/别名表还在用它。
CN_NAME = ITEMS_ZH


def my_items(d):
    got = {}
    for it in (d.get('item_slots') or []):
        if len(it) >= 3 and bool(it[2]):
            nm = str(it[0])
            got[nm] = got.get(nm, 0) + 1
    return got


def lessons_brief(max_chars=420):
    """把 lessons.md 压成一小段，塞进决策点。
    只取「## 标题 + - 要点」的行，丢掉注释和说明。"""
    path = os.path.join(ROOT, 'lessons.md')
    try:
        if not os.path.exists(path):
            return ''
        raw = open(path, encoding='utf-8').read()
    except Exception:
        return ''
    lines = []
    in_comment = False
    for ln in raw.splitlines():
        s = ln.strip()
        if '<!--' in s:
            in_comment = True
        if in_comment:
            if '-->' in s:
                in_comment = False
            continue
        if not s or s.startswith('# ') or s.startswith('>'):
            continue
        if s.startswith('## ') or s.startswith('- '):
            lines.append(s)
    if not lines:
        return ''
    # 从前往后取 —— 越靠前的越基础（"残血先保命"这种），
    # 以前从后往前取，结果最关键的早期教训永远被挤掉（2026-11-14 踩到）
    picked = []
    total = 0
    for s in lines:
        if total + len(s) + 1 > max_chars and picked:
            break
        picked.append(s)
        total += len(s) + 1
    return '\n'.join(picked)


def board_text(d):
    """决策点盘面文字。

    整段都走 T，中英各一套（连格式串也在字典里）：
        我 4 : 庄 4 | 2 实 2 空 剩 4 发 | 我的: 啤酒×1 | 庄家: 无
        Me 4 : Dealer 4 | 2 live / 2 blank · 4 left | Mine: Beer x1 | Dealer: none
    """
    items = my_items(d)
    parts = [
        T['hpFmt'].format(p=int(d.get('hp_player') or 0), d=int(d.get('hp_dealer') or 0)),
        T['ammoFmt'].format(live=int(d.get('live') or 0), blank=int(d.get('blank') or 0),
                            left=int(d.get('left') or 0)),
    ]
    if d.get('sawed'):
        parts.append(T['sawed'])
    if d.get('dealer_cuffed'):
        parts.append(T['dealerCuffed'])
    nsh = str(d.get('next_shell') or '')
    if nsh in ('live', 'blank'):
        parts.append(T['magSee'].format(
            what=T['liveShell'] if nsh == 'live' else T['blankShell']))
    parts.append(T['mine'].format(items=fmt_items(items)))
    dl = {}
    for nm in (d.get('items_dealer') or []):
        nm = str(nm)
        dl[nm] = dl.get(nm, 0) + 1
    parts.append(T['dealerItems'].format(items=fmt_items(dl)))
    s = ' | '.join(parts)
    if d.get('can_aim'):
        s += '  ' + T['aimLocked']
    return s




def wait_until(pred, timeout=4.0, step=0.12):
    """等 pred(state) 为真。返回 (是否等到, 最后状态)"""
    t0 = time.time()
    d = rd(STATE)
    while time.time() - t0 < timeout:
        d = rd(STATE)
        try:
            if pred(d):
                return True, d
        except Exception:
            pass
        time.sleep(step)
    return False, d


def settle(sec=0.3):
    time.sleep(sec)

def fix_drift(quiet=False):
    """检查并修复格子占用漂移：游戏记账 vs 桌上真实道具。"""
    d = rd(STATE)
    no = int(d.get('num_occupied') or 0)
    act = len([it for it in (d.get('item_slots') or [])
               if len(it) >= 3 and bool(it[2])])
    if no == act:
        return False
    ok, r = send('fix_grids')
    if not quiet or not ok:
        log('  修正格子漂移（记账 %d / 实际 %d）-> fix_grids %s'
            % (no, act, 'OK' if ok else r))
    time.sleep(0.35)
    return True


def STEAL_CN(name):
    """偷取日志里显示的道具名（跟着当前语言走）"""
    return item_label(str(name))


# 决策文件里可以写中文道具名（手册就是这么教的），发命令前统一换成游戏认的英文
ITEM_ALIAS = {}
for _en, _cn in CN_NAME.items():
    ITEM_ALIAS[_en] = _en
    ITEM_ALIAS[_cn] = _en
ITEM_ALIAS.update({'手铐': 'handcuffs', '小刀': 'handsaw', '啤酒': 'beer',
                   '香烟': 'cigarettes', '放大镜': 'magnifying glass',
                   '药片': 'expired medicine', '电话': 'burner phone',
                   '肾上腺素': 'adrenaline', '逆转器': 'inverter',
                   # 常见误称兜底（AI 老把放大镜叫"镜子"，英文可能叫 mirror/glass）
                   '镜子': 'magnifying glass', '透镜': 'magnifying glass',
                   '镜': 'magnifying glass',
                   'mirror': 'magnifying glass', 'magnifier': 'magnifying glass',
                   'glass': 'magnifying glass', 'lens': 'magnifying glass'})
# 决策点文字里出现的是"显示名"（英文档里就是 Beer / Magnifying Glass），
# 也要能解析回来 —— 两种语言的显示名都收进别名表。setdefault：不覆盖已有的。
for _lg in LANG.values():
    for _k, _shown in (_lg.get('items') or {}).items():
        ITEM_ALIAS.setdefault(_shown, _k)


def item_en(name):
    """中文/英文道具名（含两种语言的显示名）-> 游戏命令用的英文名

    现在中英都能解析，而且容忍大小写和误带的数量尾巴：
        use:啤酒 / use:beer / use:Beer / use:Beer x1  ->  都是 beer
    """
    s = str(name).strip()
    for cand in (s, s.lower(), s.split('×')[0].strip(), s.lower().split(' x')[0].strip()):
        if cand in ITEM_ALIAS:
            return ITEM_ALIAS[cand]
    return s


def ask(title, options, timeout=600):
    """通用决策点：写 need_decision.txt，等 decision.txt，返回我选的那个字符串。

    options: [(key, 说明), ...]  例如 [('yes','无尽模式'), ('no','普通模式')]
    """
    lines = [title, '']
    for k, desc in options:
        lines.append('  %-8s %s' % (k, desc))
    txt = '\n'.join(lines)
    # 选择题也要告诉它写到哪个文件 —— 以前只有对局决策点有提示，
    # 结果 AI 停在药瓶/菜单选择题上不知道怎么办（19:43 实际卡住过）
    keys = [k for k, _ in options]
    hint = ('\n--- 回答方式 ---\n把下面某一个词写进 out/br/decision.txt：%s\n'
            % ' / '.join(keys)) if 'zh' == LANGSET else (
            '\n--- how to answer ---\nwrite one of these into out/br/decision.txt: %s\n'
            % ' / '.join(keys))
    with open(NEED, 'w', encoding='utf-8') as f:
        f.write(txt + '\n' + hint)
    log(T['dpPoint'].format(txt=title))
    t0 = time.time()
    keys = [k for k, _ in options]
    while time.time() - t0 < timeout and not os.path.exists(STOP):
        if os.path.exists(DEC):
            raw = open(DEC, encoding='utf-8').read().strip().lower()
            try:
                os.remove(DEC)
            except Exception:
                pass
            for k in keys:
                if raw == k or raw.endswith(k) or (':' in raw and raw.split(':')[-1] == k):
                    try:
                        os.remove(NEED)
                    except Exception:
                        pass
                    log(T['dpChose'].format(title=title, k=k))
                    return k
            log(T['dpBad'].format(raw=repr(raw), keys=keys))
        time.sleep(0.15)
    try:
        os.remove(NEED)
    except Exception:
        pass
    return None


def do_items(s):
    """道具阶段：每轮先数空格子和手上道具，再决定抽还是放。"""
    quota = int(s.get('quota') or 0)
    grab_fail = 0
    finish_tries = 0      # 「补抓一件逼收尾」最多试 2 次，防止无限补抓
    while True:
        if os.path.exists(STOP):
            return
        s = rd(STATE)
        if s.get('socket') != 'briefcase':
            log('道具阶段结束')
            return

        slots = s.get('my_slots') or []

        # 幽灵格检测：游戏记的占用数 vs 桌上真实道具数
        num_occ = int(s.get('num_occupied') or 0)
        actual = len([it for it in (s.get('item_slots') or [])
                      if len(it) >= 3 and bool(it[2])])
        if num_occ != actual:
            okf, rf = send('fix_grids')
            log('  !! 格子占用表漂移（记账 %d / 实际 %d）-> fix_grids %s'
                % (num_occ, actual, 'OK' if okf else rf))
            time.sleep(0.4)
            s = rd(STATE)
            slots = s.get('my_slots') or []

        # 空格子必须用"真实道具"来算！gridOccupiedArray 会在新一轮道具阶段被重置，
        # 但桌面上的旧道具还在 —— 信它就会把新道具覆盖到已有道具的格子上。
        occ_by_item = set()
        for it in (s.get('item_slots') or []):
            if len(it) >= 3 and bool(it[2]):
                occ_by_item.add(int(it[1]))
        all_idx = [int(g[0]) for g in slots]
        if not all_idx:
            all_idx = list(range(8))
        free = [i for i in all_idx if i not in occ_by_item]
        used = len(occ_by_item)
        hold = [str(it[0]) for it in (s.get('item_slots') or [])
                if len(it) >= 3 and not bool(it[2])]

        # ① 没有空格子 → 不管手上有没有，立刻结束（之前漏的就是这一条）
        if not free:
            # 先修漂移：如果只是幽灵格，修完可能还有空位
            if fix_drift():
                s = rd(STATE)
                slots = s.get('my_slots') or []
                occ2 = set()
                for it2 in (s.get('item_slots') or []):
                    if len(it2) >= 3 and bool(it2[2]):
                        occ2.add(int(it2[1]))
                free = [int(g[0]) for g in slots if int(g[0]) not in occ2]
                if free:
                    continue
            # 格子满了 —— 不管配额抽没抽够，都必须发一次 grab。
            # 游戏只有走 NO SPACE 分支才会调 EndItemGrabbing() 收尾。
            # （之前这里错写成 g_now < quota 才发，配额满了就永远卡住）
            g_now = int(s.get('grabbed') or 0)
            # 放置完最后一个道具后游戏要过 0.45 秒才恢复 intake 权限，先等它
            if 'briefcase intake' not in can_do():
                wait_until(lambda x: 'briefcase intake' in [
                    a for a in (x.get('can_do') or []) if a not in NOISE], 4.0)
            if 'briefcase intake' in can_do():
                log('  格子满（%d/%d）-> 发 grab 走 NO SPACE 收尾' % (g_now, quota))
                send('grab_item')
                time.sleep(3.0)
                s2 = rd(STATE)
                if str(s2.get('socket')) != 'briefcase':
                    log('  道具阶段已结束')
                    return
            return 'full'

        # ② 手上有道具 → 放下
        if hold:
            gi = free[0]
            ok, txt = send('place|%d' % gi)
            if not ok:
                log('  放下 %s 到格%d 失败: %s' % (hold[0], gi, txt))
                time.sleep(0.8)
                continue

            def landed(d, gi=gi, nm=hold[0]):
                for it in (d.get('item_slots') or []):
                    if len(it) >= 3 and str(it[0]) == nm and bool(it[2]) and int(it[1]) == gi:
                        return True
                return False

            got, _ = wait_until(landed, 5.0)
            if got:
                # 必须等飞行动画真正走完！LerpItem 动的是共享的 activeItem，
                # 抓下一个道具会把它换掉，上一个还没飞到的道具就会冻住/消失。
                lt = float(s.get('lerp_duration') or 0.5)
                time.sleep(lt + 0.45)
                ok2, _ = wait_until(landed, 1.0)
                log('  放下 %s 到格%d %s（等飞行 %.2fs）' % (
                    hold[0], gi, '（已落定）' if ok2 else '（!! 放完又不见了）', lt))
                if not ok2:
                    fix_drift(quiet=True)
            else:
                log('  !! 放下 %s 到格%d 没落定' % (hold[0], gi))
                fix_drift(quiet=True)
            continue

        # ③ 抽够了 -> 游戏还不会自己收尾！
        # 实测：配额抽满后 socket 仍是 briefcase；再抓一件（超配额）+ 把它放下，
        # 游戏才走 EndItemGrabbing() 结束阶段。所以要 continue 回循环，让路径②去放。
        grabbed = int(s.get('grabbed') or 0)
        if quota > 0 and grabbed >= quota:
            fix_drift(quiet=True)
            if finish_tries < 2 and 'briefcase intake' in can_do():
                finish_tries += 1
                log('  抽满 %d/%d -> 补抓一件并放下，逼游戏收尾' % (grabbed, quota))
                send('grab_item')
                time.sleep(1.6)
                continue
            log('  抽满 %d/%d，结束' % (grabbed, quota))
            return

        # ④ 抽一个
        if 'briefcase intake' not in can_do():
            time.sleep(0.2)
            continue
        n_before = len([it for it in (s.get('item_slots') or [])
                        if len(it) >= 3 and not bool(it[2])])
        ok, txt = send('grab_item')
        if not ok:
            log('  grab_item 失败: %s' % txt)
            grab_fail += 1
            if grab_fail >= 3:
                log('  !! 连续 3 次抽失败，强制结束道具阶段')
            time.sleep(0.8)
            continue
        got, _ = wait_until(
            lambda d: int(d.get('grabbed') or 0) > grabbed
            or len([it for it in (d.get('item_slots') or [])
                    if len(it) >= 3 and not bool(it[2])]) > n_before,
            4.0)
        if got:
            grab_fail = 0
            # 关键：GrabItem 内部还有 lerpDuration-0.2 秒的 await，之后才检查空间。
            # 如果在那之前就 PlaceDownItem，GrabItem 醒来会看到"格子已满"，
            # 走 NO SPACE 分支把 activeItem（我刚放好的那个）queue_free 掉 —— 幽灵格就是这么来的。
            time.sleep(0.65)
        else:
            grab_fail += 1
            log('  !! 抽了但没等到道具出现（连续 %d 次）' % grab_fail)
            if grab_fail >= 3:
                log('  !! 连续 3 次抽不到东西，强制结束道具阶段')
            time.sleep(1.0)


def sign_name():
    """把名字打进去（带按键动画）"""
    for ch in SIG_NAME:
        ok, txt = send('sign|' + ch)
        log('  签名 %s -> %s' % (ch, 'OK' if ok else txt))
        time.sleep(0.5)
    ok, txt = send('sign_enter')
    log('  签名提交 -> %s' % ('OK' if ok else txt))
    time.sleep(1.0)


def main():
    log('=== 主循环启动 ===')
    signed = False
    idle = 0
    cash_seen = None
    item_done = False
    heaven_waiting = False
    heaven_seen_at = None
    heaven_door_done = False
    heaven_text_at = None
    heaven_door_at = None
    last_socket = None
    ask_next_game = False   # 菜单的"要不要再来一局"是否已问过
    # 刚启动时的第一次「菜单」不应该问"要继续吗" —— 直接开一局。
    # 否则新用户/新会话第一眼看到的就是「游戏开了但停在浴室不动」。
    # 注意：只有"还没见过任何非菜单场景"时才自动开，中途重启循环不会误判。
    _first_boot = True
    # ---------- 局数控制（2026-11-20 加）----------
    # 用户没说要打几局时：每局结束都问「要继续吗」（原有行为）。
    # 把想打的局数写进 out/br/target_games.txt（一个数字），循环会自动连打那么多局，
    # 打完就停并清掉这个文件 —— 这样「说打一局」就真的只打一局。
    _TARGET = os.path.join("out", "br", "target_games.txt")
    _DONE = os.path.join("out", "br", "games_done.txt")
    MENU_CMD = os.path.join("out", "br", "cmd_menu.txt")
    MENU_RES = os.path.join("out", "br", "cmd_menu_result.txt")

    def _read_target_games():
        """读目标局数；没有文件或读不出来就返回 None（= 每局都问）。"""
        try:
            if not os.path.exists(_TARGET):
                return None
            n = int(open(_TARGET, encoding="utf-8").read().strip())
            return n if n > 0 else None
        except Exception:
            return None

    def _read_games_done():
        try:
            if not os.path.exists(_DONE):
                return 0
            return int(open(_DONE, encoding="utf-8").read().strip())
        except Exception:
            return 0

    def _write_games_done(n):
        try:
            with open(_DONE, "w", encoding="utf-8") as f:
                f.write(str(int(n)))
        except Exception:
            pass

    def _menu_start():
        """让 mod 回菜单开一局。"""
        try:
            if os.path.exists(MENU_RES):
                os.remove(MENU_RES)
        except Exception:
            pass
        with open(MENU_CMD, "w", encoding="utf-8") as f:
            f.write("menu_start")

    menu_since = time.time()   # 进入菜单的时刻（用于「menu_start 没生效」的解锁判断）
    menu_silent = False        # 用户答过 no 之后为 True：安静待着，不再自动追问
    item_retry = 0           # 道具阶段重跑次数（<3）
    item_done_at = 0          # 道具阶段"做完"的时间戳（用来判断是不是真卡住）
    pill_answered = False   # 同一次洗手间里问过药瓶就不再问（选 ✘ 后药瓶仍可点，会无限追问）
    pill_absent = 0         # 药瓶连续缺席的轮数（点它的瞬间会短暂消失，不能一缺就重置）
    while not os.path.exists(STOP):
        s = rd(SCENE)
        scn = str(s.get('scene') or '')
        if scn and scn != "menu":
            _first_boot = False
        # 天堂界面：要选「重试」还是「退出」—— 我选重试
        if bool(s.get('is_heaven')):
            if heaven_seen_at is None:
                heaven_seen_at = time.time()
                log('[HEAVEN] scene appeared, wait for camera pan (~12s)')
            waited = time.time() - heaven_seen_at
            if not heaven_door_done:
                # 如果按钮已经激活，说明门早已点过（比如循环中途重启），直接进下一阶段
                if bool(s.get('heaven_buttons')):
                    log('[HEAVEN] buttons already active -> skip door step')
                    heaven_door_done = True
                    continue
                if waited < 12.0:
                    idle += 1
                    if idle % 15 == 0:
                        log('  waiting camera pan (%.0f / 12s)' % waited)
                elif bool(s.get('heaven_door_ok')):
                    log('[HEAVEN] door ready -> Fly()')
                    ok, r = send_menu('heaven_door')
                    log('  heaven_door -> %s' % ('OK' if ok else r))
                    heaven_door_done = True
                else:
                    idle += 1
                    if idle % 15 == 0:
                        log('  waiting door (%.0f s)' % waited)
            elif not heaven_waiting:
                # isActive 只是允许交互；"重启"字样是 Fly 的动画之后才显示出来的。
                # 要等文字真的出现（visible 且 alpha 够高）再等 2 秒，才按重试。
                vis = bool(s.get('heaven_btn_vis'))
                alpha = float(s.get('heaven_btn_alpha') or 0.0)
                if bool(s.get('heaven_buttons')) and vis and alpha >= 0.9:
                    if heaven_text_at is None:
                        heaven_text_at = time.time()
                        log('[HEAVEN] 文字已显示(alpha=%.2f) -> 再等 2 秒' % alpha)
                    elif time.time() - heaven_text_at >= 2.0:
                        log('[HEAVEN] 等满 2 秒 -> 选「重试」')
                        ok, r = send_menu('heaven_retry')
                        log('  heaven_retry -> %s' % ('OK' if ok else r))
                        heaven_waiting = True
                else:
                    idle += 1
                    if idle % 15 == 0:
                        log('  flying/waiting text (active=%s vis=%s alpha=%.2f)'
                            % (s.get('heaven_buttons'), vis, alpha))
            time.sleep(0.2)
            continue

        # 死亡场景：纯自动动画，什么都不做
        if bool(s.get('is_death')):
            heaven_waiting = False
            heaven_seen_at = None
            heaven_door_done = False
            heaven_text_at = None
            idle += 1
            if idle % 25 == 0:
                log('死亡场景动画中（scene=%r）' % scn)
            time.sleep(0.2)
            continue
        # 不在天堂：把天堂相关的计时全部清掉，否则下一次进天堂会沿用旧时间戳（抢跑）
        heaven_waiting = False
        heaven_door_done = False
        heaven_seen_at = None
        heaven_text_at = None
        heaven_door_at = None
        # 菜单状态下 state.json 是旧的（HealthCounter 不存在），不能拿它做判断
        if scn == 'menu':
            cash_seen = None
            idle += 1
            if idle % 20 == 0:
                log('在菜单待机')
            # 打完一局回到菜单后，问一次要不要继续
            if not ask_next_game and _first_boot:
                # 本次启动第一次见菜单：直接开一局，不打扰用户
                _first_boot = False
                _menu_start()
                log("  首次启动 -> 直接开一局（不问）")
                menu_since = time.time()
                time.sleep(1.5)
                continue
            # ---------- 局数控制（2026-11-20 加）----------
            # target_games.txt 里有数字 N：自动连打到 N 局，打完清掉文件再正常提问。
            # 先处理「答过 yes 但 menu_start 没生效」：60 秒后解锁重问。
            # 答过 no 则 menu_silent=True，安静待着 —— 想继续就手动写
            # out/br/cmd_menu.txt = menu_start（mod 会去开一局）。
            if ask_next_game and not menu_silent and (time.time() - menu_since) > 60:
                ask_next_game = False
                log('  menu_start 好像没生效（菜单待机 >60s）-> 解锁重问')
            if not ask_next_game:
                _tg = _read_target_games()
                if _tg is not None:
                    _done = _read_games_done() + 1
                    _write_games_done(_done)
                    if _done < _tg:
                        _menu_start()
                        log('  局数 %d/%d -> 自动开下一局' % (_done, _tg))
                        ask_next_game = True
                        menu_since = time.time()
                        time.sleep(1.5)
                        continue
                    else:
                        log('  已打满 %d 局（目标 %d）-> 停下来问' % (_done, _tg))
                        _write_games_done(0)
                        try:
                            os.remove(_TARGET)
                        except Exception:
                            pass
                        # 不 continue：往下走正常提问，让用户决定还要不要
            if not ask_next_game:
                dec = ask(T['askEnd'],
                          [('yes', T['askEndYes']),
                           ('no', T['askEndNo'])])
                if dec:
                    ask_next_game = True
                    menu_since = time.time()
                    if dec == 'yes':
                        _menu_start()
                        menu_silent = False
                        log('  再来一局 -> menu_start')
                        time.sleep(1.5)
                    else:
                        menu_silent = True
                        log('  停在菜单（你说停）—— 想继续就写 out/br/cmd_menu.txt = menu_start')
                continue
            time.sleep(0.2)
            continue
        # 已经离开菜单（scene 变了）才允许下次再问 ——
        # 之前在这里立刻重置，导致 menu_start 生效前的 17 秒里重复弹同一个决策点
        ask_next_game = False
        menu_silent = False
        menu_since = time.time()
        d = rd(STATE)
        if str(d.get('socket')) != 'briefcase':
            item_retry = 0        # 离开道具阶段就清零
            item_done = False
        cd = can_do()

        # 药瓶真正离开画面（连续约 3 秒不在 can_do）才允许下次进洗手间再问一次
        if 'pill bottle' in cd:
            pill_absent = 0
        else:
            pill_absent += 1
            # 一旦进了对局（离开浴室），就把"问过药瓶"清掉 —— 死亡回浴室时要能重新选 ✔
            if str(d.get("socket") or "") in ("home", "enemy", "shell compartment", "health counter"):
                pill_answered = False
            if pill_absent >= 12 and pill_answered:
                pill_answered = False

        def allowed(alias):
            return alias in cd

        def act(alias, cmd, note=''):
            """只有游戏允许（alias 在 can_do 里）才执行，执行后等别名消失，避免重复"""
            if not allowed(alias):
                return False, 'can_do 里没有 %s' % alias
            ok, r = send(cmd)
            log('%s%s -> %s' % (cmd, ('（' + note + '）') if note else '', 'OK' if ok else r))
            if ok:
                # 等这个别名从 can_do 消失，证明动作真的生效了
                t1 = time.time()
                while time.time() - t1 < 3.0:
                    if alias not in can_do():
                        break
                    time.sleep(0.15)
            return ok, r

        # ---------- 1) 决策点：轮到我、枪还在桌上（还能用道具）----------
        if my_turn_ready(d):
            txt = board_text(d)
            _retry_note = ""
            # 【2026-11-15 重构】把「写决策点 -> 等回答 -> 解析 -> 校验」包进 while True：
            # 决策里写了手上没有的道具时，**在同一个循环里重写决策点并等它重写**，
            # 而不是删文件 + continue（那样主循环不会重新判定，实测死锁 2 分钟）。
            while True:
                with open(NEED, "w", encoding="utf-8") as f:
                    _lb = lessons_brief()
                    _rm = T["needHint"]
                    if _lb:
                        _hdr = "\n--- 你的教训（lessons.md）---\n" if LANGSET == "zh" else "\n--- your lessons ---\n"
                        f.write(txt + _retry_note + _hdr + _lb + "\n" + _rm)
                    else:
                        f.write(txt + _retry_note + "\n" + _rm)
                if _retry_note:
                    log("  [重问] 已把「道具不存在」写回决策点，等它重写")
                else:
                    log(T["dpPoint"].format(txt=txt))
                dec = None
                t0 = time.time()
                while time.time() - t0 < 600 and not os.path.exists(STOP):
                    if os.path.exists(DEC):
                        dec = open(DEC, encoding="utf-8").read().strip().lower()
                        try:
                            os.remove(DEC)
                        except Exception:
                            pass
                        break
                    time.sleep(0.05)
                try:
                    os.remove(NEED)
                except Exception:
                    pass
                if not dec:
                    log("[决策] 没等到 decision.txt，跳过")
                    break
                uses = []
                shot = None
                steal_target = None
                for part in dec.replace(",", ";").split(";"):
                    part = part.strip()
                    if part.startswith("use:"):
                        uses.append(item_en(part[4:].strip()))
                    elif part.startswith("steal:"):
                        steal_target = item_en(part[6:].strip())
                    elif part.startswith("shoot:"):
                        shot = part[6:].strip()
                    elif part in ("dealer", "self"):
                        shot = part
                log("[决策] 收到: uses=%s shot=%s" % (uses, shot))
                _inv = [str(x) for x in (d.get("items_player") or [])]
                _bad = [u for u in uses if u not in _inv]
                if _bad:
                    log("  !! 你写了 %s，但手上只有 %s -> 退回让它重写"
                        % (", ".join(_bad), "、".join(_inv) or "无"))
                    _retry_note = ("\n!! 你刚才写了 use:%s，但你手上没有\n"
                                   "!! 你现在实际只有：%s\n"
                                   "!! 别写手上没有的道具，重新写一遍 decision.txt\n"
                                   % (", use:".join(_bad), "、".join(_inv) or "无"))
                    continue
                if not uses and shot is None and steal_target is None:
                    log("[决策] !! 无法解析 %r —— 应该写 self / dealer / use:X;shoot:Y" % dec)
                    _retry_note = "\n!! 你刚才写的内容看不懂：%s\n!! 请写 self / dealer / use:X;shoot:Y\n" % dec
                    continue
                break

            # ① 先用道具（必须在拿枪之前）
            for it in uses:
                s0 = rd(STATE)
                # 规则守卫（2026-11-13 用户补充）：
                #   手铐一轮只能铐一次 —— 庄家带着铐时铐不了；他挣脱后就轮到他，也铐不了
                if it == 'handcuffs' and bool(s0.get('dealer_cuffed')):
                    log('  跳过 handcuffs：庄家已经被铐住，一轮只能铐一次')
                    continue
                # 偷手铐同样：庄家已被铐住时偷来当场用也是浪费（17:48 实际踩到）
                if steal_target == 'handcuffs' and bool(s0.get('dealer_cuffed')):
                    log('  跳过 steal:handcuffs —— 庄家已经被铐住，偷来也用不上')
                    steal_target = None
                    if it == 'adrenaline':
                        continue      # 没目标了，肾上腺素也别用（省下来）
                #   普通模式第三关：血量 <= 2 时回血通道被切断，香烟没用
                if it == 'cigarettes':
                    is_s3 = (int(s0.get('batch') or 0) == 2) and (not bool(s0.get('endless')))
                    if is_s3 and int(s0.get('hp_player') or 0) <= 2:
                        log('  跳过 cigarettes：普通第三关 2 血及以下无法回血（游戏规则）')
                        continue
                # 场上没有就跳过，但别跳过两次以上（可能只是状态滞后）
                if it not in [str(x) for x in s0.get('items_player') or []]:
                    time.sleep(0.2)
                    s0 = rd(STATE)
                if it not in [str(x) for x in s0.get('items_player') or []]:
                    log('  跳过 %s（场上确实没有）' % it)
                    continue
                cnt_before = sum(1 for y in (s0.get('items_player') or []) if str(y) == it)
                ok, r = send('use|' + it)
                # ① 数量真的减少（按数量判断，同名道具不会误报）
                gone, _ = wait_until(
                    lambda x, nm=it, c0=cnt_before: sum(
                        1 for y in (x.get('items_player') or []) if str(y) == nm) < c0, 6.0)
                # ② 等这个道具演完。
                # 注意：肾上腺素故意不恢复权限（它要进偷取模式），不能等 can_shoot，
                # 否则会白等 14 秒，把 7 秒的偷取窗口耗光。
                if it == 'adrenaline':
                    back = gone
                    log('  use %s -> %s%s' % (
                        it, 'OK' if ok else r,
                        '（已生效，接下来进偷取模式）' if gone else '（! 数量没变）'))
                else:
                    back, _ = wait_until(lambda x: bool(x.get('can_shoot')), 14.0)
                    log('  use %s -> %s %s' % (
                        it, 'OK' if ok else r,
                        '（已生效，权限已恢复）' if (gone and back) else
                        ('（! 权限没恢复）' if gone else '（! 数量没变）')))

            # 偷取：dec 里写了 steal:X 就等窗口开，偷 X（偷到即用，不进格子）
            if steal_target:
                okw, _ = wait_until(lambda x: bool(x.get('stealing')), 16.0)
                if okw:
                    ok2, r2 = send('steal|' + steal_target)
                    log('[偷取] 偷 %s -> %s（偷到当场使用）'
                        % (STEAL_CN(steal_target), 'OK' if ok2 else r2))
                    time.sleep(2.0)
                else:
                    log('[偷取] !! 没等到偷取窗口（肾上腺素可能没生效）')

            if not shot:
                log('[决策] 没有 shoot 部分，跳过')
                continue


            # ③ 拿枪（落定）
            if not my_aim_ready(rd(STATE)):
                ok_g, r_g = send('grab_gun')
                log('  grab_gun -> %s' % ('OK' if ok_g else r_g))
                got, dd = wait_until(lambda x: bool(x.get('can_aim')) and not x.get('can_shoot'), 6.0)
                log('  拿枪%s' % ('已落定' if got else '!! 没落定（can_aim=%s can_shoot=%s）'
                                 % (dd.get('can_aim'), dd.get('can_shoot'))))
                settle(0.35)

            # ③ fs_dec 锁着的话这条命令是空操作，先重新拿枪解锁
            cur = rd(STATE)
            if cur.get('fs_dec'):
                log('  fs_dec=true（会变空操作），重新拿枪解锁')
                send('grab_gun')
                wait_until(lambda x: not x.get('fs_dec'), 5.0)
                cur = rd(STATE)

            # ④ 开枪 + 验证
            before = rd(STATE)
            ok, r = send('shoot|' + shot)
            log('[决策] 打%s -> %s' % (shot, 'OK' if ok else r))
            fired = False
            t2 = time.time()
            while time.time() - t2 < 8:
                a = rd(STATE)
                if (int(a.get('left') or 0) != int(before.get('left') or 0)
                        or int(a.get('hp_player') or 0) != int(before.get('hp_player') or 0)
                        or int(a.get('hp_dealer') or 0) != int(before.get('hp_dealer') or 0)):
                    fired = True
                    break
                time.sleep(0.2)
            if fired:
                log('[决策] 已确认开枪生效  现在 我%s:庄%s' % (
                    rd(STATE).get('hp_player'), rd(STATE).get('hp_dealer')))
            else:
                log('[决策] !! 这枪没打出去，重试一次')
                send('grab_gun')
                time.sleep(1.0)
                before2 = rd(STATE)
                ok2, r2 = send('shoot|' + shot)
                log('[决策] 重试 打%s -> %s' % (shot, 'OK' if ok2 else r2))
                t3 = time.time()
                while time.time() - t3 < 6:
                    a2 = rd(STATE)
                    if (int(a2.get('left') or 0) != int(before2.get('left') or 0)
                            or int(a2.get('hp_dealer') or 0) != int(before2.get('hp_dealer') or 0)
                            or int(a2.get('hp_player') or 0) != int(before2.get('hp_player') or 0)):
                        log('[决策] 重试成功')
                        break
                    time.sleep(0.2)
                else:
                    log('[决策] !! 重试也没打出去')
            settle(0.6)
            continue

        # ---------- 2.4) 偷道具窗口：不该乱偷，只等它超时 ----------
        # 偷什么由我在决策点决定（decision.txt 里写 use:adrenaline;steal:X）
        if bool(d.get('stealing')):
            idle += 1
            if idle % 10 == 0:
                log('  偷取窗口开着（剩 %.1f 秒），等它自己关（没指定目标）'
                    % float(d.get('steal_left') or 0))
            time.sleep(0.5)
            continue

        # ---------- 2.5) 药瓶：先问我，再点（不要点了才问，那样太慢）----------
        if allowed('pill bottle') and not pill_answered:
            dec = ask(T['askPill'].format(e=bool(d.get('endless'))),
                      [('yes', T['askPillYes']),
                       ('no', T['askPillNo'])])
            if dec:
                pill_answered = True
                if dec == 'no':
                    # 普通模式：**不碰药瓶**，直接去开浴室门
                    log('  普通模式：不点药瓶，直接开浴室门')
                else:
                    # 无尽模式：点药瓶 -> 选「是」
                    ok, r = send('interact|pill bottle')
                    log('  interact|pill bottle -> %s' % ('OK' if ok else r))
                    wait_until(lambda x: 'pill choice yes' in [
                        a for a in (x.get('can_do') or []) if a not in NOISE], 10.0)
                    ok2, r2 = send('interact|pill choice yes')
                    log('  interact|pill choice yes -> %s' % ('OK' if ok2 else r2))
                    log('=== 进入无尽模式（嗑药）===')
                    wait_until(lambda x: 'pill choice yes' not in [
                        a for a in (x.get('can_do') or []) if a not in NOISE], 10.0)
                    time.sleep(1.5)
            continue

        # 兜底：如果选择框已经开着（比如循环中途重启），直接问
        if allowed('pill choice yes') or allowed('pill choice no'):
            dec = ask(T['askPill2'],
                      [('yes', T['askPillYes2']), ('no', T['askPillNo2'])])
            if dec:
                ok, r = send('interact|pill choice ' + dec)
                log('  interact|pill choice %s -> %s' % (dec, 'OK' if ok else r))
                if dec == 'yes':
                    log('=== 进入无尽模式（嗑药）===')
                wait_until(lambda x: 'pill choice yes' not in [
                    a for a in (x.get('can_do') or []) if a not in NOISE], 10.0)
                time.sleep(1.5)
            continue

        # ---------- 2.6) 翻倍选择 —— 决策点 ----------
        if allowed('double yes') or allowed('double no'):
            dec = ask(T['askDbl'].format(score=d.get('double_score'),
                                         prev=d.get('double_prev'),
                                         rounds=d.get('rounds_beat')),
                      [('yes', T['askDblYes']),
                       ('no', T['askDblNo'])])
            if dec:
                ok, r = send('interact|double ' + dec)
                log('  interact|double %s -> %s' % (dec, 'OK' if ok else r))
                wait_until(lambda x: 'double yes' not in [
                    a for a in (x.get('can_do') or []) if a not in NOISE], 8.0)
                time.sleep(1.5)
            continue

        # ---------- 3) 机械动作：都过 can_do 闸 ----------
        acted = False
        # 新一轮开始（浴室门可点）就重置签名标志 —— 死亡重开也要重新签名
        if allowed('bathroom door'):
            signed = False
        if allowed('bathroom door'):
            act('bathroom door', 'door_bathroom'); acted = True
        elif allowed('backroom door'):
            act('backroom door', 'door_backroom'); acted = True
        elif allowed('release form on table'):
            act('release form on table', 'waiver'); acted = True
        elif allowed('signature machine button') and not signed:
            log('签名界面（走命令 + 按键动画）')
            # 顺手把签名机上所有按钮的 alias 记下来（用来找 ENTER 按钮）
            try:
                sb_list = d.get('sign_buttons') or []
                log('  签名机按钮: %s' % ([str(x) for x in sb_list][:30] if sb_list else '（空）'))
            except Exception as _e:
                log('  按钮列表读取失败: %s' % _e)
            sign_name()
            signed = True
            acted = True
        elif allowed('latch left'):
            act('latch left', 'latch|L'); acted = True
        elif allowed('latch right'):
            act('latch right', 'latch|R'); acted = True
        elif allowed('briefcase lid'):
            act('briefcase lid', 'lid'); acted = True
        elif allowed('heaven door'):
            act('heaven door', 'heaven'); acted = True
        elif str(d.get('socket')) == 'cash briefcase':
            # 领奖阶段：EndingManager.BeginEnding 大约要演 25~28 秒才把
            # waitingForInput 设成 true（也就是画面出现"按任意键"）。
            # 等它 true 之后再等 5 秒，让人把结算看清楚。
            if cash_seen is None:
                cash_seen = time.time()
                ending_at = None
                log('领奖阶段：等结算画面展开')
            elif ending_at is None:
                if bool(d.get('ending_ready')):
                    ending_at = time.time()
                    log('结算画面已就绪（可以按任意键）-> 再等 5 秒')
                else:
                    idle += 1
                    if idle % 25 == 0:
                        log('  结算画面还在演（已等 %.0f 秒）' % (time.time() - cash_seen))
            elif time.time() - ending_at >= 5.0:
                ok, r = send('ending_exit')
                log('ending_exit -> %s' % ('OK' if ok else r))
                cash_seen = None
                ending_at = None
                settled = False
                t3 = time.time()
                while time.time() - t3 < 30:
                    sc = rd(SCENE)
                    if str(sc.get('scene')) == 'menu':
                        settled = True
                        break
                    time.sleep(0.3)
                log('回到菜单%s' % ('成功' if settled else '!! 没等到 menu'))
            acted = True
        elif str(d.get('socket')) == 'briefcase':
            if not item_done:
                reason = do_items(d)
                fix_drift()
                if reason == 'full':
                    log('道具阶段：格子已满，不抽了')
                item_done = True
                item_done_at = time.time()
            else:
                # 只有真卡住才重跑：do_items 返回后通常 1~2 秒游戏就自己收尾了，
                # 等 3 秒还在道具阶段才算真的没结束。
                if time.time() - item_done_at > 3.0:
                    s_now = rd(STATE)
                    if str(s_now.get('socket')) == 'briefcase' and item_retry < 3:
                        item_retry += 1
                        log('  卡在道具阶段 3 秒 -> 重跑 do_items（第 %d 次）' % item_retry)
                        item_done = False
                    else:
                        item_done_at = time.time()   # 已经不在道具阶段了，别重复检查
            acted = True

        if acted:
            idle = 0
            time.sleep(0.7)
        else:
            idle += 1
            if idle % 25 == 0:
                log('待机中（socket=%r can_do=%s）' % (d.get('socket'), cd))
            time.sleep(0.4)

    log('=== 主循环结束 ===')


if __name__ == '__main__':
    main()
