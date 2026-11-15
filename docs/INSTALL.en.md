# Buckshot Roulette · AI full-auto play kit

**One line to an AI and it plays**: drop the whole pack into a workspace, tell the AI to read `docs/PLAYBOOK.md`, and it opens the game and plays it by itself.

> This is not a cheat. It doesn't change game logic, doesn't change numbers, doesn't grant invincibility —
> it just reads the game's internal state and then **presses the keys you would have pressed anyway**.

---

# Part 1: three things to check before installing

## ① You must own a legit copy of the game

Buckshot Roulette on Steam (Godot 4.1.1). **The game itself is not in this pack** (copyright);
the files in `patches/` are **diffs** (not whole `.gd` files) — you apply them to your own game files and rebuild a `mod.pck`.

## ② The AI session permission must be `danger-full-access`

The game needs to write `%APPDATA%\Godot\...\logs` (**outside the workspace**).
Under `workspace-write` the game fails to launch, and **the error looks exactly like a broken mod**:

```
Failed to open user://logs/godot.log
USER SCRIPT ERROR: Parse Error: ...
```

**On an error like this, check the permission first — don't go digging in the mod.**

## ③ You need Python 3

Both the packer and the main loop are Python scripts.

---

# Part 2: installing (four steps, about 5 minutes)

## Step 1: unzip to a short path

Unzip to a **short path** such as `D:\buckshot-ai\`. You should end up with:

```
<your workspace>/
├── README.md                 ← you're reading it
├── docs/
│   ├── INSTALL.md            ← detailed install & troubleshooting (this file)
│   ├── INSTALL.en.md         ← English (you're reading it)
│   ├── AI-INSTALL.md         ← hand this to the AI and let it install
│   ├── AI-OPENING.md         ← the opening prompt once installed
│   ├── PLAYBOOK.md           ← the AI's full playbook (it reads this)
│   ├── PLAYBOOK.en.md
│   ├── DESIGN.md             ← engineering notes (look here when something breaks)
│   └── screenshots/          ← HUD screenshots
├── tools/                    ← 11 files: install / pack / main loop / HUD
├── patches/                  ← 4 .patch files (not full .gd files)
├── art/char-200.png          ← the portrait in the HUD's corner
├── lessons.md  style.txt  lang.txt   ← the AI's training assets (setup.py copies them to out\br\)
└── out\br\mod.pck            ← produced by the install, ~704 MB
```

> ⚠️ **Don't unzip into a deep, long path** — the game contains 270-character resource paths, and a
> deeply nested location hits Windows' 260-character limit. `D:\buckshot-ai\` is the safe choice.

## Step 2: check permissions first (30 seconds, don't skip)

```powershell
python tools\br-permcheck.py
```

| Output | Meaning | Next |
|---|---|---|
| `=> 权限够，可以安装。` | ✅ | continue to step 3 |
| `=> 权限不够。` | ❌ | switch the AI session to `danger-full-access`, rerun |

With too little permission the install still "succeeds" (`setup.py` only writes inside the workspace),
but **the game won't launch**, and the error looks exactly like a broken mod (see part 1 ②) — a dead end we've been down.

## Step 3: one command installs it

```powershell
python tools\setup.py --exe "<full path to your exe>"
```

It does five things automatically — **no manual path editing**:

1. unpacks your game files into `out\pckall` (3–5 minutes the first time, instant afterwards)
2. applies `patches\*.patch` to the extracted `.gd` files
3. **rewrites the placeholder paths to this machine's real paths** (`<YOUR_USER>` and friends are handled)
4. copies the portrait `art\char-200.png` → `out\br\char-200.png`
5. repacks into `out\br\mod.pck` (~704 MB)

**Time**: 3–5 minutes the first run; ~20 seconds once unpacked (pass `--skip-extract` to skip unpacking).
When you see `完成！` it's done.

## Step 4: launch

```powershell
python tools\br-launch.py
```

It does five things in order — **every step matters**:

1. kills the old game process and old loop, clears leftover command files
2. starts the game with `--main-pack out\br\mod.pck` (without it you get the vanilla game, no mod)
3. **snaps the window to (0,0) and verifies the math** — the game always opens at (789,485) and clips the bottom-right
4. checks the Godot log for script errors (one wrong character in a `.gd` and the whole mod dies)
5. `menu_start` + starts the loop + starts the HUD

---

# Part 3: how to let the AI play

## The opening prompt for the AI

Copy the contents of `docs/AI-OPENING.md` and send them, or just say:

```
read docs/PLAYBOOK.md, then launch per section 1 and start playing per section 2.
```

## The AI's work loop (the long version is in playbook section 2)

```
① python tools\br-turn.py wait-decision --wait 120     wait for a decision point
② read out\br\need_decision.txt with the read tool     see the board (⚠️ never from console output)
③ write out\br\think.txt                               my reasoning (the HUD shows it)
④ write out\br\decision.txt                            my decision
```

## ⚠️ The easiest mistake: guessing items from console mojibake

PowerShell renders Chinese as:

```
我 3 : 庄 1 | 3 实 3 空 剩 6 发 | 我的: ����̡�1��������1
```

**Guessing item names from that goes wrong.** The original session guessed wrong three times, and one of those times it "used an item it didn't actually have".

**Rule**: always read the item list with the `read` tool from `out/br/need_decision.txt`.

---

# Part 4: the status HUD

## What it is

A floating window in the top-left corner that shows the game state plus what the AI is thinking, live. **Started automatically by `br-launch.py`**, and it exits by itself when the game closes.

It looks like this:

```
Buckshot Roulette  Live 0s                In game
Endless R1 · Stage 1 · Round 1 · 3W 1L · 75%
HP (dealer : me)   4 : 4    max 4
Shells   2 blank / 2 live · #1 · 4 left
Magnifier: next is BLANK
My items   Beer  Phone  Pills  Handcuffs  Handsaw
Dealer items   Handcuffs  Pills  Handsaw  Magnifier  Cigarettes
My turn                                  ← red
Thinking · 3s ago
2 live / 2 blank = 50%, I have Handcuffs — cuff first, then look
                                      [portrait]
                                       thought for 1s
                                       · hell, I'm not thinking anymore.
```

## What it shows

| Line | Meaning |
|---|---|
| `Live Xs` | how fresh `state.json` is (past 3.5 seconds the HUD holds the previous frame) |
| `Stage N` / `Endless RN · Stage M` | normal mode and endless mode use two different spellings |
| `Round K` | which "shoot the shells empty → reload" cycle within this stage |
| `NW ML · X%` | **HUD-level** tally: the baseline is recorded when the HUD starts, and dying doesn't reset it |
| `HP (dealer : me)` | **note the dealer is on the left, me on the right** |
| `max N` | the heal ceiling (endless mode rolls 2–4 per stage) |
| `Shells` | how many blank, how many live · which shell · how many left (the "which shell" part is for the Burner Phone) |
| `Magnifier: next is …` | only appears after a Magnifier has been used (gone after 15 seconds) |
| `Thinking · Ns ago` | what the AI wrote into `think.txt`, expires after 75 seconds |
| `agent is deepsleeping` | the placeholder when no AI is thinking |

## Features (every one of them paid for in blood)

- **Mouse click-through**: clicking the HUD clicks the game behind it
- **No flicker**: fully owner-drawn + `WS_EX_COMPOSITED`, content is repainted only after a signature comparison
- **Lives and dies with the game**: it exits when the game exits (it doesn't hide, so it can't sit in the background eating resources)
- **Rounded corners + thin border + translucent background**

## Driving the HUD on its own

```powershell
# 停
powershell -NoProfile -ExecutionPolicy Bypass -File tools\br-hud.ps1 -Action stop

# 自己起（一般不用，launch 会起）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\br-hud.ps1
```

## Want to change how it looks

Edit the color block at the top of `tools/br-hud.ps1`:

```powershell
$cBg      = [System.Drawing.Color]::FromArgb(255, 34, 41, 58)    # 背景
$cStat    = [System.Drawing.Color]::FromArgb(255, 255, 214, 70) # 关数那行（黄）
$cHealth  = [System.Drawing.Color]::FromArgb(255, 150, 250, 185) # 血量（绿）
$cThink   = [System.Drawing.Color]::FromArgb(255, 255, 228, 140) # 想法（黄）
```

**You must save it as UTF-8 with BOM**, otherwise PowerShell 5.1 reads it as ANSI, every Chinese character turns to garbage and the syntax crashes outright.

## Portrait

`art/char-200.png` goes to `out/br/char-200.png`. To use your own image:
- **200px wide**, transparent PNG recommended
- the HUD pins it to the bottom-right corner and it follows the HUD's height

---

# Part 5: changing the name

```
out\br\player_name.txt
```

| Rule | Notes |
|---|---|
| **6 characters max** | the signature machine has only 6 slots |
| **letters a-z only** | the keyboard has no digits or symbols |
| displayed in caps | `dsh` → `DSH` |
| restart the game after | the script reads it once at launch |

---

# Part 6: gameplay quick reference

## Turn mechanics

- **After every reload, the player goes first**
- Shoot yourself + blank → the turn stays yours (free)
- Shoot yourself + live → you take damage, the turn goes to the other side
- Shoot the other side (blank or live) → the turn goes to the other side

## The nine items

| Item | Effect | Key point |
|---|---|---|
| Handsaw | +1 damage on the next shell | does nothing on a blank — wasted |
| Beer | ejects the shell currently in the chamber | changes the ratio / skips a known trap |
| Cigarettes | heals 1 | don't use at full HP; check `start_hp` |
| Handcuffs | the other side skips a turn | **only one cuff per round**; after cuffing you must shoot them |
| Magnifier | see the next shell | the HUD displays it |
| Adrenaline | steal one of their items | **stolen items are used immediately**, a 7-second window |
| Burner Phone | tells you whether shell N is blank/live | read it from the dialog box |
| Pills | 50% heal 2 / 50% lose 1 | **never at 1 HP** |
| Inverter | flips the next shell | positive when blanks dominate, negative when live dominate |

## Hard rules (all of them learned the hard way)

- **Never take Pills at 1 HP** (50% lose 1 = suicide)
- **Check the max HP before healing**
- **Normal mode, stage 3: once either side is at ≤2 HP, healing is cut off** (game source: the line really is cut)
- **Don't use the Inverter on a 50/50** (waste)
- **Handcuffs + shoot them** is the most reliable combo
- **In normal mode don't touch the pill bottle**, just open the two doors in the bathroom

## Score (endless mode)

```
score = 70000 − (seconds from signing to beating stage 3 / 600) × 40000
minimum 10
```

**It's time-based, not item-based.** Speed is the whole game.

---

# Part 7: troubleshooting

| Symptom | Cause | What to do |
|---|---|---|
| Black screen / mod does nothing | `.gd` has a syntax error → autoload died | look for `Parse Error` in the Godot log |
| Game won't start, reports `Failed to open user://logs` | **not enough permission** (not a mod problem) | set the session permission to `danger-full-access` |
| Decision point never arrives | loop died / it's not my turn | `Get-Content out\br\run2.log -Tail 20` |
| HUD stuck on `Waiting for match…` | the game really is in its menu | normal; send `menu_start` |
| HUD twitches and flickers | state-detection threshold too tight (fixed) | it now has an 8-second grace period |
| Item counts doubled | the mod counted twice (fixed) | the two sides now read from different sources |
| Name won't type in | more than 6 characters / non-letters | edit `player_name.txt` |
| Endless turns normal after death | "pill already asked" never reset (fixed) | see the notes |

## Common commands

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

# Part 8: known limitations

- The guard for "normal mode stage 3, ≤2 HP, no healing" is in place, but **never exercised live** (HP never dropped to 2)
- The HUD can't do "translucent background, fully opaque portrait" (WinForms' Opacity applies to the whole window)
- Only verified on Windows
- Window snapping is only verified at 2560×1600 fullscreen (re-check on another resolution); the HUD itself auto-scales to screen width (0.65–1.6)

---

# Copyright

This pack contains **no game code** — only `patches/*.patch` (the diffs I wrote) and build scripts.

**The artifacts you generate locally** — `out/br/patch/scripts/*.gd` and `out/br/mod.pck` —
are patched game code. **Don't redistribute those.**
