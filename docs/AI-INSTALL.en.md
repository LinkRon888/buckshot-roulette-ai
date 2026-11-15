# AI install manual (you are the AI — execute this)

**The user only said "install it". Don't ask questions; work through the steps below by yourself.**

When you're done the user should be able to play straight away. If you get stuck midway, handle it per that step's "what if it fails".

---

# Step 0: run three self-checks first (don't skip)

## 0.1 Is the permission sufficient — **this is a hard gate; if it fails, don't install**

**Just run this script** (don't hand-roll a `python -c`, the quoting will blow up):

```powershell
python tools\br-permcheck.py
```

**Read the output**:

| Output | Meaning | Next |
|---|---|---|
| `=> 权限够，可以安装。` | ✅ | continue to step 0.2 |
| `=> 权限不够。` | ❌ **stop** | see below |

**If the permission is insufficient, stop and tell the user**:

> This session is workspace-write, so it can't be installed. The game has to write %APPDATA%\Godot (outside the workspace).
> Please change the session permission to **danger-full-access**, then have me rerun.

**Don't try to escalate** (approvals are off in this session, so the request gets auto-rejected and you only waste time).

**And definitely don't "just try installing anyway"** — the install does succeed (`setup.py` only writes inside the workspace),
but **the game won't start**, and the error looks like "the mod is broken", so you debug for ages before realising it was the permission.

## 0.2 Is Python there

```powershell
python --version
```

- A version number → continue
- `不是内部或外部命令` ("not recognized as an internal or external command") → **stop and tell the user to install Python 3**

## 0.3 Where the game is installed

Look for `Buckshot Roulette.exe` in this order:

```powershell
$paths = @(
  "C:\Program Files (x86)\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe",
  "D:\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe",
  "E:\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe"
)
foreach ($p in $paths) { if (Test-Path $p) { "找到: $p" } }
```

**None of them found** → look up the Steam install directory from the registry, or:

```powershell
Get-ChildItem -Path C:,D:,E: -Filter "Buckshot Roulette.exe" -Recurse -ErrorAction SilentlyContinue -Depth 8 | Select-Object -First 3 FullName
```

**Still not found** → **stop and ask the user**: "Where is the game installed? Give me the full path to Buckshot Roulette.exe."

---

# Step 1: confirm the current directory

You need to be at the root of this pack (the level that has `tools\`, `art\`, `patches\`, `README.md`).

```powershell
Get-Location
Test-Path tools\setup.py
```

- `True` → correct, continue
- `False` → you may be one level up; `cd` in, or search:

```powershell
Get-ChildItem -Path . -Filter "setup.py" -Recurse -Depth 3 | Select-Object FullName
```

---

# Step 2: run the install

**This is the one command that has to run** (replace `<EXE>` with the real path you found in step 0.3):

```powershell
python tools\setup.py --exe "<EXE>"
```

## What it does

1. Unpacks the game files into `out\pckall` (**3–5 minutes the first time**, instant after that)
2. Applies `patches\*.patch` to the original `.gd` files
3. **Rewrites the paths inside the files to this machine's real paths**
4. **Copies the portrait** `art\char-200.png` → `out\br\char-200.png`
5. Repacks into `out\br\mod.pck` (about 700 MB)

## Expected output

`setup.py` prints its progress lines in Chinese, so the block below is the literal output:

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

## What if it fails

| Error | Cause | What to do |
|---|---|---|
| `FileNotFoundError` + a very long path | Windows 260-character limit | move the whole pack to a short path (e.g. `D:\bs\`) and start over |
| `找不到 patches 目录` (can't find the patches directory) | wrong directory layout | go back to step 1 and confirm the location |
| `PermissionError` | not enough permission | go back to step 0.1 |
| exits with no output at all | Python too old | check `python --version`; you need 3.6+ |

**A slow first run is normal** — the first unpack takes 3–5 minutes; don't interrupt it just because it's slow.

---

# Step 3: verify the install

Run these three; **all three passing is what counts as installed**.

## ⚠️ But the 4th check below matters more than these — don't skip it

The path substitution is **the step most likely to fail silently**: if the patch didn't swap the placeholder for this machine's path,
the mod writes its state to **someone else's path** (which doesn't exist), and the game just looks like it's "not responding".
**It never raises an error**, so you have to check it yourself.

```powershell
Select-String -Path out\br\patch\scripts\HealthCounter.gd -Pattern 'KOROOT'
```

**Expected**: that line's path should be **the directory you're in now**, e.g.

```gdscript
920  const _DSH_KOROOT := "D:/buckshot/out/br/"
```

## ❌ If you see someone else's path

```
920  const _DSH_KOROOT := "C:/Users/someone-else/..."     ← looks like this = broken
```

That means `setup.py` didn't substitute it. **Go back and check whether the "applying patches" section printed**:

```
·路径自动替换 -> <your dir>/out/br/
```

**No print = the patch has no placeholder in it** (you may have downloaded an old build). Unzip the pack again and reinstall.

---

The three checks below are the basic ones:


Run these three; **all three passing is what counts as installed**:

```powershell
# ① mod.pck 存在且够大（约 700 MB）
(Get-Item out\br\mod.pck).Length / 1MB

# ② 补丁产物存在
Get-ChildItem out\br\patch\scripts\*.gd | Select-Object Name

# ③ 立绘到位
Test-Path out\br\char-200.png
```

**Expected**:

- ① `≈ 704`
- ② 4 files: `HealthCounter.gd` / `GlobalVariables.gd` / `ItemManager.gd` / `IntroManager.gd`
- ③ `True`

**If any one is off** → go back to step 2 and rerun (`setup.py` is safe to rerun, it can't break anything).

---

# Step 4: launch

```powershell
python tools\br-launch.py
```

## What it does

1. Kills the old processes, clears the leftovers
2. Launches the game (with `--main-pack out\br\mod.pck`)
3. **Snaps the game window to (0,0)** (the game drifts off on every launch)
4. Checks the Godot log for script errors
5. `menu_start` + starts the decision loop + starts the status HUD

## Expected output

`br-launch.py` also prints in Chinese; the block is the literal output:

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

## Critical check

**If you see `!! 有脚本错误，mod 可能没生效`** ("there are script errors, the mod may not have taken effect") → the `.gd` has a syntax error:
1. Look at exactly which line its `Parse Error` names
2. **Nine times out of ten it's an indentation problem** (mixed tabs and spaces)
3. Go back to step 2 and rerun

---

# Step 5: confirm it's playable

```powershell
# 等一个决策点（最多 2 分钟）
python tools\br-turn.py wait-decision --wait 120
```

**Expected**: something like

```
=== 决策点 ===
我 4 : 庄 4 | 2实2空 剩4发 | 我的: 啤酒×1、电话×1 | 庄家: ...

回答 out/br/decision.txt，写以下之一：
  self                        打自己
  dealer                      打庄家
  use:啤酒;shoot:dealer       先喝啤酒再打庄家
```

**Getting that means everything works end to end.**

Note: the hint lines above are printed by `br-turn.py` in Chinese, but the parser accepts English item names just as well —
`use:Beer;shoot:dealer` means the same as `use:啤酒;shoot:dealer`, and `self` / `dealer` are already English.

## Then

**Read `docs/PLAYBOOK.md`** and start playing according to its decision loop. **Every decision is yours.**

---

# FAQ (after installing)

| Symptom | What to check |
|---|---|
| no portrait in the HUD's bottom-right | `Test-Path out\br\char-200.png`; if it's missing, `copy art\char-200.png out\br\` |
| HUD doesn't show up | start it by hand with `powershell -File tools\br-hud.ps1` and read the error |
| black screen / no response | `Parse Error` in the Godot log |
| decision point never arrives | `Get-Content out\br\run2.log -Tail 30` |
| HUD twitches and flickers | shouldn't happen any more; if it still does, report it |

---

# Three rules you must follow

1. **Always read item lists with the `read` tool from `out/br/need_decision.txt`**
   The console turns Chinese into `����̡�1`; guessing items from it goes wrong.

2. **Write `think.txt` at every decision point**
   The HUD shows it to the human. The decision-point file reminds you at the end too.

3. **Every decision is yours**
   The loop won't decide for you, and it shouldn't. Just write into `out/br/decision.txt`.

---

# What to tell the user when you're done

One sentence is enough:

> Installed. The game is already running, and I've started playing.

---

## How the HUD size is decided (by resolution)

**The HUD scales itself by screen width**, based on 2560 wide (scale = 1.0).

| Screen width | Automatic scale | HUD width | Font size |
|---|---|---|---|
| 1366 / 1600 | 0.65 (floor) | ~455 | smaller |
| 1920 | 0.75 | ~525 | medium |
| 2560 | 1.00 | 700 | standard |
| 3440 (ultrawide) | 1.34 | ~940 | large |
| 3840 (4K) | 1.50 | 1050 | large |

**In theory you never touch this** — it adapts at startup.

### To adjust it by hand

Write a number in `out\br\hud_scale.txt`:

```
1.2
```

**Range 0.65 ~ 1.6**; anything outside gets clamped. Delete the file to go back to automatic.

### Common cases

| Symptom | What to do |
|---|---|
| HUD too big, covers the game | write `0.8` |
| HUD too small to read | write `1.3` |
| still small on a 4K screen | write `1.6` (the ceiling) |

### You can also pass the flag directly

```powershell
powershell -File tools\br-hud.ps1 -Width 900
```

**Priority**: the `-Width` flag > `hud_scale.txt` > automatic.
