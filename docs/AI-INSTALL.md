# AI 安装手册（你是 AI，照这个执行）

**用户只说了「装好它」，你不要问问题，按下面顺序自己做完。**

做完之后用户应该能直接玩。中途卡住就按每一步的「失败怎么办」处理。

---

# 第 0 步：先自检三件事（不要跳过）

## 0.1 权限够不够 —— **这是硬闸，不过就别装**

**直接跑这个脚本**（不要自己拼 `python -c`，引号会炸）：

```powershell
python tools\br-permcheck.py
```

**看返回**：

| 输出 | 含义 | 下一步 |
|---|---|---|
| `=> 权限够，可以安装。` | ✅ | 继续第 0.2 步 |
| `=> 权限不够。` | ❌ **停** | 见下面 |

**权限不够时，停下来告诉用户**：

> 这个会话是 workspace-write，装不了。游戏要写 %APPDATA%\Godot（工作区外面）。
> 请把会话权限改成 **danger-full-access**，然后让我重跑。

**不要尝试提权**（本会话审批是关的，申请会被自动拒绝，浪费时间）。

**更不要"先装着试试"** —— 装是能装成功的（`setup.py` 只写工作区内），
但**游戏起不来**，而且报错长得像"mod 坏了"，排查很久才发现是权限。

## 0.2 Python 在不在

```powershell
python --version
```

- 有版本号 → 继续
- `不是内部或外部命令` → **停下来告诉用户装 Python 3**

## 0.3 游戏装在哪

按这个顺序找 `Buckshot Roulette.exe`：

```powershell
$paths = @(
  "C:\Program Files (x86)\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe",
  "D:\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe",
  "E:\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe"
)
foreach ($p in $paths) { if (Test-Path $p) { "找到: $p" } }
```

**都找不到** → 从注册表查 Steam 安装目录，或者：

```powershell
Get-ChildItem -Path C:,D:,E: -Filter "Buckshot Roulette.exe" -Recurse -ErrorAction SilentlyContinue -Depth 8 | Select-Object -First 3 FullName
```

**还是找不到** → **停下来问用户**：「游戏装在哪？把 Buckshot Roulette.exe 的完整路径给我。」

---

# 第 1 步：确认当前目录

你需要在这个包的根目录（有 `tools\`、`art\`、`patches\`、`README.md` 那一层）。

```powershell
Get-Location
Test-Path tools\setup.py
```

- `True` → 对，继续
- `False` → 你可能在上一级，`cd` 进去，或者搜索：

```powershell
Get-ChildItem -Path . -Filter "setup.py" -Recurse -Depth 3 | Select-Object FullName
```

---

# 第 2 步：跑安装

**这是唯一一条必须跑的命令**（把 `<EXE>` 换成第 0.3 步找到的真实路径）：

```powershell
python tools\setup.py --exe "<EXE>"
```

## 它会做什么

1. 解包游戏文件到 `out\pckall`（**首次 3~5 分钟**，之后秒过）
2. 应用 `patches\*.patch` 到原始 `.gd`
3. **自动把文件里的路径换成这台机器的真实路径**
4. **复制立绘** `art\char-200.png` → `out\br\char-200.png`
5. 重新打包成 `out\br\mod.pck`（约 700 MB）

## 预期输出

```
[1/3] 游戏包: 3572 个文件, engine=4.1.1
      extracted 3572 files -> ...
[2/3] 应用补丁:
      HealthCounter.gd      212 行 -> 1446 行
      GlobalVariables.gd    314 行 -> 510 行
      IntroManager.gd       327 行 -> 327 行
      ItemManager.gd        589 行 -> 592 行
      ＜路径自动替换 -> C:/.../out/br/＞
      立绘已复制 -> out/br/char-200.png
[3/3] 重新打包...
wrote out/br/mod.pck  files=3572  ...  size=704.3 MB

完成！
  产物: .../out/br/mod.pck
  下一步: python tools\br-launch.py
```

## 失败怎么办

| 报错 | 原因 | 处理 |
|---|---|---|
| `FileNotFoundError` + 很长的路径 | Windows 260 字符限制 | 把整个包移到短路径（如 `D:\bs\`）重来 |
| `找不到 patches 目录` | 目录结构不对 | 回到第 1 步确认位置 |
| `PermissionError` | 权限不够 | 回到第 0.1 步 |
| 没有任何输出就退出 | Python 版本太老 | `python --version` 看看，要 3.6+ |

**超时也正常** —— 首次解包 3~5 分钟，别因为慢就打断。

---

# 第 3 步：验证安装

下面这三条，**三条都过了才算装好**。

## ⚠️ 但对比下面这第 4 条更重要 —— 别跳过

路径替换是**最容易静默失败**的一步：patch 里如果没把占位符换成本机路径，
mod 会把状态写到**别人的路径**（不存在），游戏看起来就是"没反应"。
**它不会报错**，所以必须自己查。

```powershell
Select-String -Path out\br\patch\scripts\HealthCounter.gd -Pattern 'KOROOT'
```

**预期**：那行的路径应该是**你现在这个目录**，例如

```gdscript
920  const _DSH_KOROOT := "D:/buckshot/out/br/"
```

## ❌ 如果看到的是别人的路径

```
920  const _DSH_KOROOT := "C:/Users/someone-else/..."     ← 长这样就是坏了
```

说明 `setup.py` 没替换成功。**回去看「应用补丁」那节有没有打印**：

```
·路径自动替换 -> <你的目录>/out/br/
```

**没打印 = patch 里没有占位符**（可能下载到的是老版本）。重新解压包再装。

---

下面这三条是基础检查：


跑这三条，**三条都过了才算装好**：

```powershell
# ① mod.pck 存在且够大（约 700 MB）
(Get-Item out\br\mod.pck).Length / 1MB

# ② 补丁产物存在
Get-ChildItem out\br\patch\scripts\*.gd | Select-Object Name

# ③ 立绘到位
Test-Path out\br\char-200.png
```

**预期**：

- ① `≈ 704`
- ② 4 个文件：`HealthCounter.gd` / `GlobalVariables.gd` / `ItemManager.gd` / `IntroManager.gd`
- ③ `True`

**任何一条不对** → 回第 2 步重跑（`setup.py` 可以重复跑，不会坏）。

---

# 第 4 步：启动

```powershell
python tools\br-launch.py
```

## 它会做

1. 杀旧进程、清残留
2. 启动游戏（带 `--main-pack out\br\mod.pck`）
3. **把游戏窗口归位到 (0,0)**（游戏每次启动都会跑偏）
4. 检查 Godot 日志有没有脚本错误
5. `menu_start` + 起决策循环 + 起状态面板

## 预期输出

```
[4/5] 检查 Godot 日志
   日志干净，没有脚本错误
[5/5] menu_start + 主循环
   scene = menu
   menu_start -> OK|menu_start|ms=...
[HUD] 面板已启动（无控制台窗口）
   HUD PID: 12345（游戏关掉它会自己退出）
   循环 PID: 67890
完成。决策点写到 out\br\need_decision.txt
```

## 关键检查

**看到 `!! 有脚本错误，mod 可能没生效`** → 说明 `.gd` 有语法错误：
1. 看它打印的 `Parse Error` 具体是哪一行
2. **九成是缩进问题**（tab/空格混用）
3. 回第 2 步重跑

---

# 第 5 步：确认能玩

```powershell
# 等一个决策点（最多 2 分钟）
python tools\br-turn.py wait-decision --wait 120
```

**预期**：打印出类似

```
=== 决策点 ===
我 4 : 庄 4 | 2实2空 剩4发 | 我的: 啤酒×1、电话×1 | 庄家: ...

回答 out/br/decision.txt，写以下之一：
  self                        打自己
  dealer                      打庄家
  use:啤酒;shoot:dealer       先喝啤酒再打庄家
```

**有了就说明全通了。**

## 然后

**读 `docs/PLAYBOOK.md`**，按它的决策循环开始打。**决策全权在你。**

---

# 常见问题（装完之后）

| 症状 | 查什么 |
|---|---|
| 面板右下角没立绘 | `Test-Path out\br\char-200.png`，没有就 `copy art\char-200.png out\br\` |
| 面板不显示 | `powershell -File tools\br-hud.ps1` 手动起，看报错 |
| 游戏黑屏 / 无反应 | Godot 日志的 `Parse Error` |
| 决策点一直不来 | `Get-Content out\br\run2.log -Tail 30` |
| 面板抽搐闪 | 不该有了；还闪就报告 |

---

# 你要遵守的三条

1. **读道具必须用 `read` 工具读 `out/br/need_decision.txt`**
   控制台会把中文变成 `����̡�1`，靠它猜道具会出错。

2. **每个决策点写 `think.txt`**
   面板会显示给人看。决策点文件末尾也提醒了。

3. **决策全权在你**
   循环不会替你做决定，也不该做。写进 `out/br/decision.txt` 就行。

---

# 装完之后告诉用户什么

一句话就够：

> 装好了，游戏已经在跑，我开始打了。

---

## 面板大小怎么定（按分辨率）

**面板会自己按屏幕宽度缩放**，基准是 2560 宽（scale = 1.0）。

| 屏幕宽 | 自动 scale | 面板宽 | 字号 |
|---|---|---|---|
| 1366 / 1600 | 0.65（下限） | ~455 | 较小 |
| 1920 | 0.75 | ~525 | 中 |
| 2560 | 1.00 | 700 | 标准 |
| 3440（带鱼屏） | 1.34 | ~940 | 大 |
| 3840（4K） | 1.50 | 1050 | 大 |

**理论上不用管**，启动就自适应了。

### 想手动调

在 `out\br\hud_scale.txt` 里写一个数字：

```
1.2
```

**范围 0.65 ~ 1.6**，超出会被夹住。删掉这个文件就回到自动判断。

### 常见情况

| 现象 | 怎么办 |
|---|---|
| 面板太大挡住游戏 | 写 `0.8` |
| 面板太小看不清 | 写 `1.3` |
| 4K 屏上还是偏小 | 写 `1.6`（上限） |

### 你也可以直接传参数

```powershell
powershell -File tools\br-hud.ps1 -Width 900
```

**优先级**：`-Width` 参数 > `hud_scale.txt` > 自动判断。
