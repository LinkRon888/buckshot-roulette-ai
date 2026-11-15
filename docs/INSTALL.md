# 恶魔轮盘 · AI 全自动游玩套件

**给 AI 一句话就能玩**：把整个包丢进工作区，让 AI 读 `docs/PLAYBOOK.md`，它就会自己开游戏、自己打。

> 这不是外挂。它不改游戏逻辑、不改数值、不开无敌 ——
> 只是把游戏内部状态读出来，然后**替你按你本来会按的键**。

---

# 第一部分：装之前先看这三条

## ① 必须有正版游戏

Steam 上的 **Buckshot Roulette**（Godot 4.1.1）。**游戏本体不在这个包里**（版权），
包里的 `patches/*.patch` 是**补丁**（不是完整 `.gd`），要拿你自己的游戏文件打上补丁，重新打出一个 `mod.pck`。

## ② AI 会话权限必须是 `danger-full-access`

游戏要写 `%APPDATA%\Godot\...\logs`（**工作区之外**）。
权限是 `workspace-write` 时，游戏启动会失败，而且**报错长得像 mod 坏了**：

```
Failed to open user://logs/godot.log
USER SCRIPT ERROR: Parse Error: ...
```

**看到这种错先查权限，别去查 mod。**

## ③ 需要 Python 3

打包和主循环都是 Python 脚本。

---

# 第二部分：安装（四步，约 5 分钟）

## 步骤 1：解压到短路径

解压到一个**短路径**，比如 `D:\buckshot-ai\`。解出来的目录长这样：

```
<你的工作区>/
├── README.md                 ← 你正在看的
├── docs/
│   ├── INSTALL.md            ← 详细安装与排错（就是这份）
│   ├── INSTALL.en.md         ← 英文版
│   ├── AI-INSTALL.md         ← 丢给 AI，让它自己装
│   ├── AI-OPENING.md         ← 装好后发给 AI 的开场白
│   ├── PLAYBOOK.md           ← AI 的完整操作手册（它要读这个）
│   ├── PLAYBOOK.en.md
│   ├── DESIGN.md             ← 工程笔记（出问题查这里）
│   └── screenshots/          ← 面板截图
├── tools/                    ← 11 个文件：安装 / 打包 / 主循环 / 面板
├── patches/                  ← 4 个 .patch（不是完整 .gd）
├── art/char-200.png          ← 面板右下角的立绘
├── lessons.md  style.txt  lang.txt   ← AI 的训练资产（setup.py 复制到 out\br\）
└── out\br\mod.pck            ← 装出来的，约 704 MB
```

> ⚠️ **别解压到很深很长的路径里** —— 游戏里有 270 字符的资源路径，
> 太深的位置会撞 Windows 的 260 字符限制。`D:\buckshot-ai\` 这种短路径最安全。

## 步骤 2：先自检权限（30 秒，别跳）

```powershell
python tools\br-permcheck.py
```

| 输出 | 含义 | 下一步 |
|---|---|---|
| `=> 权限够，可以安装。` | ✅ | 继续步骤 3 |
| `=> 权限不够。` | ❌ | 把 AI 会话权限改成 `danger-full-access`，重跑 |

权限不够时装也能装成功（`setup.py` 只写工作区内），但**游戏起不来**，
而且报错长得像"mod 坏了"（见第一部分②）—— 那条死路我们走过。

## 步骤 3：一条命令装好

```powershell
python tools\setup.py --exe "<游戏exe完整路径>"
```

它会自动做五件事，**不用手动改任何路径**：

1. 解包你的游戏文件到 `out\pckall`（首次 3~5 分钟，之后秒过）
2. 把 `patches\*.patch` 应用到解出来的原始 `.gd` 上
3. **自动把脚本里的占位路径换成你这台机器的真实路径**（`<YOUR_USER>` 这类不用管）
4. 复制立绘 `art\char-200.png` → `out\br\char-200.png`
5. 重新打包成 `out\br\mod.pck`（约 704 MB）

**耗时**：首次约 3~5 分钟；已经解过包的话约 20 秒（加 `--skip-extract` 跳过解包）。
看到 `完成！` 就成了。

## 步骤 4：跑起来

```powershell
python tools\br-launch.py
```

它会依次做五件事，**每一步都必要**：

1. 杀掉旧游戏进程和旧循环，清掉残留命令文件
2. 用 `--main-pack out\br\mod.pck` 启动游戏（不带这个参数就是原版，mod 全无）
3. **窗口归位到 (0,0) 并验证换算** —— 游戏每次启动都会跑到 (789,485)，右下角被裁
4. 检查 Godot 日志有没有脚本错误（`.gd` 改错一个字符整个 mod 就挂）
5. `menu_start` + 起主循环 + 起状态面板

---

# 第三部分：怎么让 AI 玩

## 给 AI 的开场白

复制 `docs/AI-OPENING.md` 的内容发给它，或者直接说：

```
读 docs/PLAYBOOK.md，然后按第 1 节启动、第 2 节开始打。
```

## AI 的工作循环（手册第 2 节有详细版）

```
① python tools\br-turn.py wait-decision --wait 120     等决策点
② 用 read 工具读 out\br\need_decision.txt              看局面（⚠️ 不能用控制台输出）
③ 写 out\br\think.txt                                  我的思考（面板会显示）
④ 写 out\br\decision.txt                               我的决策
```

## ⚠️ 最容易犯的错：看控制台乱码猜道具

PowerShell 把中文输出成：

```
我 3 : 庄 1 | 3 实 3 空 剩 6 发 | 我的: ����̡�1��������1
```

**靠这个猜道具名会出错。** 原会话里猜错过三次，其中一次「用了个根本没有的道具」。

**规矩**：道具清单一律用 `read` 工具读 `out/br/need_decision.txt`。

---

# 第四部分：状态面板（HUD）

## 它是什么

左上角一个浮窗，实时显示游戏状态 + AI 在想什么。**由 `br-launch.py` 自动启动**，游戏关掉它会自己退出。

看起来是这样：

```
恶魔轮盘  实时 0s                      对战中
无尽 第1大轮 · 第1小关 · 第1回合 · 3胜1负 · 胜率：75%
血量（庄家：我）   4 : 4    满血为 4
弹药情况   2空2实 · 第1发 · 剩余 4 发
放大镜看到：下一发是空包
我的道具   啤酒  电话  药片  手铐  小刀
庄家的道具   手铐  药片  小刀  放大镜  香烟
轮到我                                  ← 红色
想法 · 3 秒前
2实2空 = 50%，我有手铐，先铐再看
                                      [立绘]
                                       已思考（用时1秒）
                                       · 我操，我不思考了。
```

## 它显示什么

| 行 | 含义 |
|---|---|
| `实时 Xs` | `state.json` 有多新（超过 3.5 秒面板会保持上一帧不动） |
| `第N关` / `无尽 第N大轮 · 第M小关` | 普通模式是无尽模式是两种不同写法 |
| `第K回合` | 本关内第几次「打空子弹→重装」 |
| `N胜M负 · 胜率：X%` | **面板级**累计：开面板时记基准，死了不重置 |
| `血量（庄家：我）` | **注意是庄家在左、我在右** |
| `满血为 N` | 回血上限（无尽模式每关随机 2~4） |
| `弹药情况` | 几空几实 · 第几发 · 剩余几发（「第几发」是给电话用的） |
| `放大镜看到` | 只有用过放大镜才出现（15 秒后消失） |
| `想法 · N 秒前` | AI 写进 `think.txt` 的内容，75 秒过期 |
| `您的 agent 正在 deepsleeping` | 没有 AI 在想事时的占位 |

## 特性（都是踩坑踩出来的）

- **鼠标能穿透**：点面板等于点它后面的游戏
- **不闪**：全自绘 + `WS_EX_COMPOSITED`，内容是签名比对后才重绘
- **跟游戏同生共死**：游戏退出它就退出（不隐藏，免得后台占资源）
- **圆角 + 细边框 + 半透明底**

## 单独控制面板

```powershell
# 停
powershell -NoProfile -ExecutionPolicy Bypass -File tools\br-hud.ps1 -Action stop

# 自己起（一般不用，launch 会起）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\br-hud.ps1
```

## 想改样子

改 `tools/br-hud.ps1` 顶部的配色块：

```powershell
$cBg      = [System.Drawing.Color]::FromArgb(255, 34, 41, 58)    # 背景
$cStat    = [System.Drawing.Color]::FromArgb(255, 255, 214, 70) # 关数那行（黄）
$cHealth  = [System.Drawing.Color]::FromArgb(255, 150, 250, 185) # 血量（绿）
$cThink   = [System.Drawing.Color]::FromArgb(255, 255, 228, 140) # 想法（黄）
```

**改完必须存成 UTF-8 带 BOM**，否则 PowerShell 5.1 按 ANSI 读，中文全乱、语法直接崩。

## 立绘

`art/char-200.png` 放在 `out/br/char-200.png`。想换自己的图：
- 建议 **200px 宽**、透明背景 PNG
- 面板会按右下角贴，跟随面板高度

---

# 第五部分：改名字

```
out\br\player_name.txt
```

| 规则 | 说明 |
|---|---|
| 最多 **6 个字符** | 签名机只有 6 个格子 |
| 只能**字母 a-z** | 键盘上没有数字和符号 |
| 显示转大写 | `dsh` → `DSH` |
| 改完重启游戏 | 脚本启动时读一次 |

---

# 第六部分：玩法速查

## 回合机制

- **每次装完子弹，玩家先手**
- 打自己 + 空包 → 回合还是你的（白赚）
- 打自己 + 实弹 → 自己受伤，回合交给对方
- 打对方（无论空实）→ 回合交给对方

## 九种道具

| 道具 | 效果 | 关键点 |
|---|---|---|
| 小刀 | 下一发伤害 +1 | 空包不生效，白用 |
| 啤酒 | 退出膛内一发 | 改变比例 / 跳过已知的坑 |
| 香烟 | 回 1 血 | 满血别用；看 `start_hp` |
| 手铐 | 对方跳过一回合 | **一轮只能铐一次**；铐住后必须打对方 |
| 放大镜 | 看下一发 | 面板会显示 |
| 肾上腺素 | 偷对方一件道具 | **偷到即用**，只有 7 秒窗口 |
| 电话 | 告诉你第 N 发是空/实 | 从对话框读 |
| 药片 | 50% 回 2 血 / 50% 扣 1 血 | **1 血绝对不能用** |
| 逆转器 | 翻转下一发 | 空包占优时正收益，实弹占优时负收益 |

## 硬规矩（都是踩过坑的）

- **1 血绝不吃药片**（50% 扣 1 = 自杀）
- **回血前先看满血值**
- **普通模式第三关，任一方 ≤2 血时回血被切断**（游戏源码：剪线真死）
- **逆转器别在 50/50 用**（浪费）
- **手铐 + 打对方** 是最稳的组合
- **普通模式不要碰药瓶**，直接在洗手间开两道门

## 分数（无尽模式）

```
分数 = 70000 − (签名到打赢第三关的秒数 / 600) × 40000
最低 10 分
```

**按时间算，不是按道具。** 打得快才是关键。

---

# 第七部分：故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| 黑屏 / mod 无反应 | `.gd` 有语法错误 → autoload 挂了 | 看 Godot 日志的 `Parse Error` |
| 装完游戏起不来、AI 完全没反应 | 会话权限不够（不是 mod 坏） | 先跑 `python tools\br-permcheck.py` 看一眼 |
| 游戏起不来，报 `Failed to open user://logs` | **权限不够**（不是 mod 问题） | 会话权限改成 `danger-full-access` |
| 决策点一直不来 | 循环挂了 / 不在我的回合 | `Get-Content out\br\run2.log -Tail 20` |
| 面板显示「等待对局」不动 | 游戏真的在菜单 | 正常，发 `menu_start` |
| 面板抽搐闪 | 状态判定阈值太紧（已修） | 现在有 8 秒宽限期 |
| 道具数量翻倍 | mod 重复统计（已修） | 已改成两边用不同来源 |
| 名字打不进去 | 超过 6 个字符 / 用了非字母 | 改 `player_name.txt` |
| 无尽死亡后变普通 | 「问过药瓶」没重置（已修） | 见笔记 |

## 常用命令

```powershell
# 看游戏状态
Get-Content out\br\state.json -Raw

# 看循环日志
Get-Content out\br\run2.log -Tail 20

# 手动发命令（绕过循环）
# ⚠️ 必须用 Python 写，不能用 echo（echo 会写成 UTF-16，mod 读成乱码）
python -c "open('out/br/cmd.txt','w',encoding='utf-8').write('grab_gun')"
Get-Content out\br\cmd_result.txt

# 重新打包 mod（改过 .gd 之后必须做）
python tools\pckpack.py --exe "<游戏exe>" --work out\pckall --patch out\br\patch --out out\br\mod.pck --skip-extract
```

---

# 第八部分：已知限制

- 「普通模式第三关 ≤2 血不能回血」的守卫代码就位，但**没有实测到**（一直没掉到 2 血）
- 面板「背景半透明、立绘全不透明」做不到（WinForms 的 Opacity 是全窗生效）
- 只在 Windows 上验证过
- 窗口归位只在 2560×1600 全屏下验证过（换分辨率要复核一次）；面板本身按屏幕宽度自动缩放 0.65~1.6

---

# 版权

本包**不含游戏代码**：只有 `patches/*.patch`（我改动的差异）和构建脚本。

**你自己机器上生成的产物** —— `out/br/patch/scripts/*.gd` 和 `out/br/mod.pck` ——
那是打了补丁的游戏代码，**别再分发**。
