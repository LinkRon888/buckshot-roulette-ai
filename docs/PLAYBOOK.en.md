> ## ⚠️ First, what this playbook is
>
> **It's a "how to think" reference, not a "copy this" template.**
>
> The strategies, cases and probability tables inside are there so you **know how to compute** — not so you
> mechanically apply them when a similar board shows up. You are a language model, not a state-machine script —
> **when you hit a board this playbook doesn't cover, work it out yourself.**
>
> **Three kinds of content, keep them apart**:
>
> | Type | Example | Can you overrule it |
> |---|---|---|
> | **Mechanics** (how the game works) | shooting yourself with a blank keeps the turn; Handcuffs make them skip | ❌ no, that's fact |
> | **Rules of thumb** (true in most cases) | shoot yourself when blanks dominate; don't take Pills at 1 HP | ⚠️ **yes**, but you must say why this time is different |
> | **Cases** (one worked example of the thinking) | "1 HP vs 4 HP, use Beer to eject a shell and flip it" | ❌ don't copy it; learn the reasoning |
>
> **Generalizing beats copying.** If you compute that some "rule of thumb" doesn't hold on the current board,
> go with your computation — but **write the reason into think.txt**.
>
> Every concrete number here (HP, shells, items) is an **example**, not your actual board.

---

# Buckshot Roulette · automated playbook (for a fresh session)

> ## ⚡ One line: use this single command per decision point
>
> ```powershell
> python tools\br-next.py "<one-line judgement>" <decision>
> python tools\br-next.py yes                # choice questions
> ```
>
> **It writes the decision + waits for the next turn + prints the new board — one request per turn.**
> **Don't use read on the decision point, don't write your own script, don't use the write tool.**
>
> Both real attempts at rolling our own failed: it missed the board, or returned only `ok` so you still had to read
> again — and not a cent was saved.
>
> ⚠️ **Don't reinvent this wheel. The script already handles it**: decision before think (so nothing deadlocks),
> the loop dying gets explained in plain words, timeouts don't hang, and the new board comes back with it.

> **This file is self-contained.** A fresh session can take over after reading this one file;
> it doesn't need to know anything about earlier conversations.
> Workspace: `<your workspace>`
> Last updated: 2026-11-13

---

## 0. The whole setup in one sentence

The game runs a mod (a patched PCK) that writes the game's internal state to `out/br/state.json` every 0.12 seconds,
and reads `out/br/cmd.txt` every 0.12 seconds to execute commands.
So: **I read state.json to see the board, and I write cmd.txt to make the game act**.

The main loop `tools/br-run2.py` wraps those two things: when it's "my turn to decide" it pauses,
writes the board into `out/br/need_decision.txt`, and then **waits for me to write the answer into `out/br/decision.txt`**.

---

## ⚠️ 0. Before you start: the session permission must be danger-full-access

**This comes first; without it everything downstream is wasted.**

The game has to write `%APPDATA%\Godot\...` (outside the workspace) and run processes outside the sandbox.
If the session permission is `workspace-write` (the default), launching the game will **request escalation to danger-full-access**;
and if approvals are off, that request is **auto-rejected**, and then you sit there unable to move.

**Symptom**: after running `br-launch.py` the game doesn't come up, or you see an approval request saying `escalate sandbox to danger-full-access`.

**So**: set the permission tier to `danger-full-access` when you open the session; don't stay on the default `workspace-write`.

---

## 1. Launch (one command)

```powershell
cd <your workspace>
python tools\br-launch.py
```

It does five things in order, **every one of them necessary**:

1. Kills leftover game processes and the old loop, clears stale command files
2. Launches the game with `--main-pack out\br\mod.pck` (without that flag it's the vanilla game, mod entirely absent)
3. **Snaps the window to (0,0) and verifies the conversion** — on every launch the game lands at (789,485) with its bottom-right corner cut off
4. Checks the Godot log for script errors (one wrong character in a `.gd` and the whole mod dies)
5. `menu_start` + starts the main loop + starts the status HUD

**Note**: `python` here means
`python`

---

## 2. The decision loop (core; follow it exactly)

```
① wait for a decision point
   python tools\br-turn.py wait-decision --wait 120

② read the real board (⚠️ must use the read tool on the file, never console output)
   read out\br\need_decision.txt

③ write the thinking (the HUD displays it)
   write out\br\think.txt

④ write the decision
   write out\br\decision.txt
```

### ⚠️ Iron rule number one: items must be read with the `read` tool

The PowerShell console renders Chinese as `�������` mojibake. **Guessing item names from mojibake goes wrong** —
it's happened twice already: reading "Handcuffs" as "Adrenaline", and believing I had a Magnifier when I didn't.

The output of `wait-decision` only tells you "the moment has arrived"; **the actual item list must be `read` from the file**.

### How to write the decision file

| What you write | Meaning |
|---|---|
| `self` | shoot yourself |
| `dealer` | shoot the dealer |
| `use:Beer;shoot:dealer` | use Beer, then shoot the dealer |
| `use:Handsaw;use:Handcuffs;shoot:dealer` | several items in sequence |
| `use:Adrenaline;steal:Magnifier` | Adrenaline steals their Magnifier (**a step of its own; can't be combined with shoot**) |
| `use:Adrenaline;steal:Inverter;shoot:dealer` | steal first, then shoot |

Chinese item names parse too — `use:手铐;shoot:dealer` resolves exactly like `use:Handcuffs;shoot:dealer`,
and the parser also tolerates lowercase and a stray count like `use:Beer x1`.

### What to put in the thinking (think.txt)

The HUD displays it, and **the human reading it needs to be able to follow your reasoning**:

```
3 live / 4 blank = 43% live, blanks dominate.
I only have Pills, and at max HP 4/4 they're unusable (50% loses a point).
Shoot myself: 57% keeps the turn, and worst case I eat 1 and still have 3 HP.
```

**When you use an item, write the result in too**:
- `Magnifier says: next is BLANK`
- `Phone says: shell #4 is LIVE`
- `Beer ejected: a BLANK`
- `Pills: heal 2 / lose 1`

The HUD expires it after 75 seconds; past that it shows `agent is deepsleeping`.

---

## 3. Rules (the hand-written version's errors are fixed here)

> ⚠️ **Check your style first**: `out/br/style.txt` (safe / balanced / aggressive).
> Hard rules (no Pills at 1 HP, etc.) are the same in every style; **ambiguous boards follow the style**.
> The strategy tables later in this playbook are written from the "default" viewpoint — if your style is aggressive, some spots should be played riskier.

### Turn mechanics

- **After every reload, the player goes first.** So "shoot myself with the last blank to keep first move" is **pointless** — the next round is yours anyway.
- **Shoot yourself + blank** → the turn stays yours (free)
- **Shoot yourself + live** → you take the damage, the turn goes to the other side
- **Shoot the other side (blank or live)** → the turn goes to the other side

### The nine items

| Item | Effect | Key point |
|---|---|---|
| **Handsaw** | +1 damage on the next shell (1→2) | does nothing on a blank — wasted |
| **Beer** | ejects the shell currently in the chamber | for changing the ratio / skipping a known trap |
| **Cigarettes** | heals 1 | **don't use at full HP**; check `start_hp` before healing |
| **Handcuffs** | the other side skips their next turn | ⚠️ **after cuffing you must shoot them**; shooting yourself throws it away |
| **Magnifier** | see what the next shell is | the HUD shows a `Magnifier` line |
| **Adrenaline** | steal one of their items | **stolen items are used immediately**, not put into your slots; only a 7-second window |
| **Burner Phone** | tells you whether shell N is blank/live | read it from the dialog box, see below |
| **Pills** | 50% heal 2 / 50% lose 1 | ⚠️ **never at 1 HP** (lose 1 = dead) |
| **Inverter** | flips the next shell | see the probability table below |

### The right mindset for items (important)

**The default action is: use it.**

- Changing stage wipes them; you can't carry them out
- Not using it = a guaranteed waste
- Using it wrong = at least you learn how to use it next time
- **Hoarding = a guaranteed loss**

**So don't ask "should I use it", ask "what does the board look like after I use it".**

| Item | Ask yourself before using |
|---|---|
| Magnifier | Once I see it, what will I do? If it's live, do I have a Handsaw to pair with it? |
| Beer | Eject this shell — is what's left better or worse? |
| Handcuffs | If I cuff him, who do I shoot this shell? How many shells are left? (see the trap below) |
| Cigarettes | Do I need that 1 HP? Or does this turn need tempo more? |
| Pills | Is gambling my life worth it? Or is my HP high enough that I don't have to? |
| Inverter | Are blanks or live shells dominating now? Does flipping favour me? |
| Burner Phone | Knowing what shell N is — does that actually help me decide? |
| Handsaw | Is the next shell **definitely** live? If not, it's wasted |
| Adrenaline | Steal which one? Can what I steal produce an effect **immediately**? |

**If you've gone two turns in a row without touching any item, go back and look — you're probably hoarding too much.**

---

### Before using / stealing an item, ask: what do I lack most right now?

| I lack | Prioritise taking / using |
|---|---|
| **Life** (1~2 HP, could die any moment) | Cigarettes, Pills (if there's no better option) |
| **Information** (I don't know the next shell) | Magnifier, Burner Phone |
| **Damage** (they're nearly dead) | Handsaw, Inverter |
| **Tempo** (I want to keep this turn) | Handcuffs, shooting myself (if it's a blank) |

**Ask this especially when Adrenaline is stealing something.**

**Typical mistake**: you're at 1 HP, and the dealer holds Cigarettes and a Handsaw.
You go steal the Handsaw to deal damage — **but if your next shell is live, you die first and the Handsaw did nothing.**

**Damage only matters if you live to use it.**

---

### Three specific traps that are easy to fall into

**① With only 1 shell left, cuffing the dealer is a waste**

```
1 shell left → cuff him → shoot → chamber empty → reload → the cuff expires
```

Handcuffs are worth "skipping one full turn of theirs". Fire the last shell and fresh ammo is loaded; that "skip" lands on nothing.

**Correct use**: cuff while there are still ≥2 shells left.

**② The system won't tell you what Beer ejected**

Compare it yourself afterwards:

```
before: note the live / blank numbers
after: look again
whichever number dropped is the kind you ejected
```

No visible change = the state hasn't refreshed yet; wait 0.5 s and read again.

**③ For the Burner Phone's result, read `out\br\dialogue_capture.txt` — not `state.json`**

The dialog text only stays on screen for ~3 seconds. By the time you finish
deciding and go read `state.json`, it's already cleared.

**The capture tool is already running** — `br-launch.py` starts a resident
`br-dialogue.py --follow` on boot. It scans the `dialogue` field every 0.12 s
and appends whatever appears to that file.

**So after using the phone, just read the last line of the file.**

**Do not**: go digging in `state.json` for `dialogue` — it will almost
certainly be empty by then.

---

### Inverter: watch the direction, don't memorize dogma

| Current ratio | Using the Inverter | Verdict |
|---|---|---|
| 1 live, 2 blank (33% live) | blank→live, so the live chance becomes 67% | **positive** |
| 3 live, 2 blank (60% live) | live→blank, so the live chance becomes 40% | **negative, don't use it** |
| 1 live, 1 blank (50%) | still 50% | **neutral, don't waste it** |
| known that the next shell is blank | it becomes live | **guaranteed hit** (with Handsaw = a guaranteed 2) |

### How to read the Burner Phone

The Phone speaks in **"the Nth shell from now"** — N=1 is the very next shell, not a fixed position in this round's reload.

- Example: 4 left, 2 live 2 blank, Phone says "shell #4 is live" → that last shell is live, and the first 3 are 1 live 2 blank.
- **Every shell you fire shifts every number down by one**: what was "shell #4" becomes "shell #3" on the next shot.
- **After Beer ejects the current shell, everything shifts down too**: a known shell #N becomes shell #N-1 after the eject.
- So renumber on every change of the board; you can't carry last turn's numbering into this turn.
- The good news: if the Phone says "shell #1", you know the next shell outright — that's a free Magnifier.

**A trap stepped into on 2026-11-14 (the user called it out on the spot)**: I treated "shell #4" as a fixed position in the round,
assumed that after Beer ejected one shell the known live shell would slide up, and fired `shoot:dealer`.
In reality the shell that got ejected was itself live, and the one that slid up was a **blank** — I shot air, handed over the turn for free,
and the dealer took that live shell and shot me back. **"What's the next shell after Beer" must be recomputed from the shifted numbering.**

Grab the dialog box with `tools\br-dialogue.py` (the game's dialog is in Chinese in this build):
```powershell
python tools\br-dialogue.py --sec 22    # 先起它，再用电话
```
The result is written to `out\br\dialogue_capture.txt`, as:
```
14:31:06 | 第四发子弹 / ...  实弹。
```

**Inference method (computed as "the Nth shell from now")**: 8 left = 4 live 4 blank, Phone says shell #4 is live
→ shell #4 is locked as live, so the first 3 shells are 4 live 4 blank minus that one = 3 live 4 blank
→ **the current shell (#1) sits in 3 live 4 blank = 43%**. (Same conclusion as the old wording, but the old model was wrong,
and it computes incorrectly the moment you use Beer mid-round — see the trap above.)

### Common item combos

1. **Handcuffs + Handsaw + shoot them**: lands 2, and if you whiff they skip their turn and the next shell is still yours.
   **This combo absorbs the cost of a whiff**, one of the best in the game.
2. **Magnifier + Inverter + Handsaw**: see it → flip a blank into live → **saw the barrel** → **guaranteed 2**.
3. **Adrenaline steals their Inverter**: when they hold an Inverter, steal it to flip a known blank → a guaranteed 1.
4. **Beer + Phone for a guaranteed hit**: Phone says shell #7 is live → infer that the first 6 hold one fewer live → use Beer to eject down to that shell.

### Three hard rules that are easy to miss (added by the user 2026-11-13)

**① Handcuffs work only once per round**
You can't cuff the dealer while he's cuffed; and once he breaks free it's his turn, so you can't cuff him then either.
So: **when you see `Dealer cuffed`, stop thinking about cuffing** — that play is wasted. (The loop already has a guard: it skips it and logs the skip.)

**② When items disappear (verified against the game source)**

| Situation | Result |
|---|---|
| **normal mode stage 1** | **there are no items at all** (`numberOfItemsToGrab = 0`) |
| **normal mode stage 2 → stage 3** | **cleared** (the only stage switch in normal mode that has items to clear) |
| **between rounds inside the same stage** | **kept** (e.g. what's left in stage 2 round 1 carries into round 2) |
| **endless mode, between stages** | **cleared** (1→2 and 2→3 both clear) |
| **endless mode, after picking double up** | what's left from the **last stage** of the previous big round **carries into stage 1 of the next big round**; cleared at stage 2 |

**Source evidence**:
- `RestartBatch()` (the restart after doubling) only sets `currentBatchIndex = 0` and then calls `MainBatchSetup(false)`,
  **and there is no item-clearing call in there** → so items carry over
- normal stage progression takes a different path, which does clear them

**What it means**: **items never leave a stage.** "Hoard them for the next stage" isn't a thing. So the default action is **use them up**.

**③ Normal mode stage 3: at ≤ 2 HP the healing channel is cut off**
Cigarettes don't heal either (**smoking one is pure waste**). So in stage 3 the moment you drop to 2 HP or below, stop counting on healing — you live on Handcuffs/Beer/Inverter.
(Endless mode does **not** have this restriction.)

### Two hard rules about HP

**① Don't take Pills at 1 HP by default** — but this is a **rule of thumb, not an iron law**

50% lose 1 = dead on the spot. **Don't gamble by default.**

**But some boards are worth the gamble**: if "the chance the dealer kills me this round" is **clearly above 50%**,
then taking Pills is actually positive EV:

```
Scenario: I'm at 1 HP, the dealer's next shot is 70% live.
  Don't take: 70% chance I get killed
  Take:       50% heal 2 (I live) + 50% lose 1 (I die)
       → survival goes from 30% up to 50%
```

**How to judge**: ask yourself "if I do nothing right now, what's the chance I die next round?"
- **< 50%** → don't take them (gambling into death isn't worth it)
- **> 50%** → you can consider taking them (you'd probably die anyway, so take the shot)
- **can't tell** → don't take them

**Same principle**: every other "rule of thumb" works the same way — compute first, then decide whether to apply it.

**② Check `start_hp` before healing**
`start_hp` in `state.json` is **the HP of this big round's first stage**, and that's the healing ceiling.
Endless mode rolls 2–4 per stage, so "I'm at 4 HP" doesn't mean full — the ceiling may be 2.

---

## 4. The two modes

### Normal mode (three stages)

- Stage one has **no items**; they start in stage two
- Die in the first two stages → bathroom revive → click door 1, door 2 → back to **the stage you died in**
- Die in stage three → **heaven**: wait 12 seconds for the camera to pan down → click the iron door → 15.6 seconds of flight → wait for the "restart" text → wait 2 more seconds → click retry
- Beat stage three → open the box for the cash (left latch, right latch, lid) → ending animation → back to the menu

### Endless mode (taking the pill)

**How to enter**: in the bathroom click **the pill bottle** → pick ✔

**⚠️ In normal mode don't touch the pill bottle** — just open the doors in the bathroom (door 1, door 2).
Only click the pill bottle when you actually mean to go endless; once it's open, picking ✘ to go back to normal is pointless and interrupts the bathroom flow.

(`br-run2.py`'s pill branch already implements this: picking "normal" **does nothing** and goes straight to opening the doors.)

- 3 stages per big round, and **death is real**: back to the bathroom, restart from **stage 1 of this big round** (no save, so the stage index resets to 0)
- After dying the pill bottle appears again, and you have to **pick ✔ again** to get back into endless
- Beat 3 stages → score → choose **✔ double up** or **✘ bank it**
  - ✔ → back to stage 1, and winning the next round doubles the score
  - ✘ → cash-out box → ending → back to the menu
- **Score formula (time-based, not item-based)**:
  ```
  score = 70000 − (seconds from signing to beating stage 3 / 600) × 40000
  minimum 10 (play absurdly long and it floors at 10)
  ```
  So **speed** is the lever on a high score.

---

## 5. The status HUD (optional, but very useful)

`tools\br-hud.ps1` is the floating window in the top-left; **started automatically by br-launch.py**, and it exits itself when the game closes.

What it shows:
```
Buckshot Roulette  Live 0s                In game
Stage 2 · Round 0 · 3W 1L · 75%
HP (dealer : me)   3 : 3    max 3
Shells   4 blank / 4 live · #1 · 8 left
Magnifier: next is BLANK
My items   Handcuffs  Inverter  Handsaw
Dealer items   Magnifier x2  Beer
My turn
Thinking · 12s ago
(what I wrote as my reasoning)
```

- mouse click-through, no flicker
- **the win rate is HUD-level**: the baseline is recorded when the HUD starts, dying doesn't reset it
- the reasoning expires after 75 seconds; past that it shows `agent is deepsleeping`

---

## 6. Troubleshooting

| Symptom | Cause | What to do |
|---|---|---|
| black screen / mod does nothing | `.gd` has a syntax error → autoload died | check the Godot log for `Parse Error`; step 4 of `br-launch.py` checks it |
| decision point never arrives | it's not my turn, or the loop died | look at the last lines of `out/br/run2.log`; check whether the loop process is alive |
| HUD stuck on `Waiting for match…` | the game really is in its menu | normal; send `menu_start` to begin |
| HUD twitches and flickers | state-detection threshold too tight (fixed) | current builds have an 8-second grace period; it shouldn't recur |
| item counts doubled | the mod counted twice (fixed) | the two sides now read from different sources |
| window's bottom-right is cut off | the window drifted | step 3 of `br-launch.py` snaps it back automatically |

### Common commands

```powershell
# 手动发命令（绕过循环）
echo grab_gun > out\br\cmd.txt
Get-Content out\br\cmd_result.txt

# 看游戏状态
Get-Content out\br\state.json -Raw

# 看循环日志
Get-Content out\br\run2.log -Tail 20

# 重打包 mod（改过 .gd 之后必须做，约 20 秒）
python tools\pckpack.py --exe "<游戏exe>" --work out\pckall --patch out\br\patch --out out\br\mod.pck --skip-extract
```

---

## 7. Traps hit in this session (don't step in them again)

1. **`var x := obj.get(...)` makes the whole autoload fail to parse** — `get()` returns Variant and `:=` can't infer the type. Use `var x =`.
2. **You can't use `d[...]` inside `_dsh_cmd()`** — `d` is a local of `_dsh_dump()`; using it there fails compilation of the whole script.
3. **`Add-Type -TypeDefinition` needs `-ReferencedAssemblies` when compiling C#** — `-AssemblyName` only loads, it doesn't hand the compiler a reference.
4. **`$pid` is a read-only PowerShell automatic variable** — you can't use it as your own variable name.
5. **Killing processes by fuzzy command-line match kills yourself** — the shell that invoked it has that same string on its command line. Always kill by the pid file.
6. **`.Replace(a, b, 1)` is Python syntax** — PowerShell's String.Replace only has the two-argument form.
7. **`WS_EX_LAYERED` on its own doesn't flicker, `Opacity < 1` does** — click-through uses `LAYERED | TRANSPARENT`, and flicker is avoided by "never setting Opacity". Verify those two separately.

---

## 8. File list

| Path | Purpose |
|---|---|
| `out/br/mod.pck` | the packed mod (704 MB) |
| `out/br/patch/scripts/*.gd` | the patch sources (repack after editing) |
| `out/br/state.json` | game state (the mod writes it every 0.12 s) |
| `out/br/scene.json` | scene info (the autoload writes it every 0.25 s) |
| `out/br/cmd.txt` | command input (I write, the mod reads) |
| `out/br/cmd_result.txt` | command result (the mod writes) |
| `out/br/need_decision.txt` | decision point (the loop writes, I read) |
| `out/br/decision.txt` | my decision (I write, the loop reads) |
| `out/br/think.txt` | my reasoning (I write, the HUD displays) |
| `tools/br-launch.py` | **the standard launch flow** |
| `tools/br-run2.py` | the main loop |
| `tools/br-turn.py` | single-step tools such as `wait-decision` |
| `tools/br-dialogue.py` | captures the on-screen dialog text (Burner Phone results) |
| `tools/br-hud.ps1` | the status HUD |
| `tools/pckpack.py` | repacks the mod |
| `工程笔记.md` | the complete engineering notes (1066 lines, every detail) |
| `out/br/backup/` | backups of the usable builds at each stage |

---

## 9. What to do when you start

1. Read sections 1 and 2; get launching and the decision loop straight
2. Run `python tools\br-launch.py`
3. Wait for `wait-decision`
4. **Read `need_decision.txt` with the `read` tool**, then decide per the rules in section 3
5. Write `think.txt` at every decision (the HUD shows it)

**Every decision is yours**; the loop won't decide for you, and it shouldn't.

---

## 10. Name and signature (finalized 2026-11-13 evening)

**Name file**: `out/br/player_name.txt`
- whatever is in it is what you sign in-game
- **6 characters max** (the signature machine has only 6 slots; extras are silently dropped)
- **letters a-z only**
- displayed in caps (`dsh` → `DSH`)
- restart the game after changing it

**Signing flow** (the loop does it automatically, don't touch it):
```
open the bathroom doors → pick up the waiver → signature screen → letter by letter sign|d sign|s sign|h
→ find the ENTER key, play the press animation → wait 0.3 s → Input_Enter() submits → the match starts
```

**Note**: `waiver` (pick up the waiver) is **a normal step the loop sends itself**; don't send it by hand.
And `PickUpWaiver()` clears the name already typed — once you've signed, never send waiver again.

---

## 11. After an endless-mode death you must pick the pill again

**Fixed**: as soon as a match is detected (socket is `home`/`enemy`/`shell compartment`/`health counter`),
the "pill already asked" flag is cleared. So dying back to the bathroom **asks again** whether to take the pill.

An older build had a bug: after dying back to the bathroom the pill bottle stayed on screen forever, so the
"absent for 12 rounds straight" reset never fired, so it stopped asking → opened the doors directly → **fell back into normal mode**.

---

## 12. Three questions you must pass before every decision (added 2026-11-13, because the AI keeps forgetting to use items)

**At every decision point, recite these; don't skip:**

### ① Do I know what the next shell is right now?

| In hand / on the board | How to find out |
|---|---|
| Magnifier (mine) | `use:magnifying glass` → the HUD shows a `Magnifier` line |
| Magnifier (theirs) + Adrenaline (mine) | `use:adrenaline;steal:magnifying glass` |
| Burner Phone | `use:burner phone` → read `out/br/dialogue_capture.txt` |
| Beer + a known shell #N | use Beer to eject the shells in front of it |
| none of the above | you can only play the ratio (look at "how many blank, how many live") |

**When you know it's live and the dealer is down to 1–2 HP, that's a must-kill window — don't waste it.**

### ② How much damage can I guarantee?

**The damage-scaling chain when you know it's live**:

```
known live + I have Handsaw                     → use:handsaw;shoot:dealer = 2
known live + I have Inverter (not needed)
known blank + I have Inverter                   → use:inverter;shoot:dealer = 1
known blank + Inverter + Handsaw                → use:inverter;use:handsaw;shoot:dealer = 2
known live + dealer has Handsaw + I have Adrenaline → use:adrenaline;steal:handsaw;shoot:dealer = 2
known live + I have Handsaw + Handcuffs         → use:handsaw;use:handcuffs;shoot:dealer = 2 and they don't hit back
```

**The one most often forgotten**: **when the dealer holds a Handsaw / Inverter, steal it with Adrenaline and it's 2 or 1 damage immediately**.
(stolen items are used at once, they don't go into your slots, 7-second window)

### ③ Is there a cheaper play?

| Board | Cheaper play |
|---|---|
| they're at 1 HP, 50/50 | Handcuffs + shoot them: a hit wins, a miss still makes them skip |
| they're at 1 HP, I know it's live | just shoot; 1 damage is enough |
| blanks dominate (>55%) | shoot yourself to keep the turn, don't burn items |

### How to play a 50/50 — depends on your style (there is no absolute right)

At `1 live 1 blank` the two lines have **similar win rates**; the difference is **variance**, not expected value:

| | Shoot yourself (gambling on blank) | Shoot the dealer (gambling on live) |
|---|---|---|
| good branch (50%) | blank → turn kept → the live shell after it is still yours | live → straight 1 damage on him |
| bad branch (50%) | live → **you lose 1 HP**, and the turn changes | blank → **only the turn changes, no HP lost** |

**Both readings hold**:
- "I can't gamble my own HP" → shoot the dealer
- "if I win the gamble I get an extra move" → shoot yourself

**This is a preference question, not a theorem.**

---

### Pick a style first (read `out/br/style.txt`, defaults to safe)

| Style | 50/50 target | Items | Pills | Overall |
|---|---|---|---|---|
| **safe** | shoot the dealer | **use them, but pick spots with clear payoff** (saw the barrel only when the shell is known live) | only at ≥3 HP | avoid risk, grind it out |
| **balanced** | shoot the dealer | as needed | at ≥2 HP | read the board and judge on the spot |
| **aggressive** | shoot yourself (gamble the turn) | use early, use often | take them at ≥2 HP | chase tempo and comebacks |

**Style only tilts "ambiguous boards", it never touches hard rules** (no Pills at 1 HP is the same in every style).

**Where the play actually differs**:
- who you shoot on a 50/50
- whether you dare shoot yourself at just over 50%
- whether to stockpile items or spend them now
- when low on HP, play safe or chase tempo

**To lock in a style**: write `safe` / `balanced` / `aggressive` in `out/br/style.txt`.
Leave it out and it defaults to `safe`.

---

# Self-review (learn items, not luck)

**The playbook is only the starting point. What actually makes you better is your own games.**

---

## ⚠️ First, remember: this game is mostly luck

**Don't learn rules from a single outcome.** The shell order is random; one result proves nothing.

### ❌ Don't learn like this (that's mistaking noise for signal)

```
Last time it was 1 live 1 blank, I shot myself and died — so this time shoot the dealer
Last time shooting myself hit three in a row, so shooting myself is right
Last time stealing the Handsaw won, so stealing the Handsaw while low is fine too
```

**A "rule" from a sample size of 1 is no rule at all.** Learning this way just makes you more superstitious.

### ✅ The right way to review

**Don't ask "was this outcome good", ask "given what I knew at the time, was this decision's expected value positive".**

| Ask this | Not this |
|---|---|
| Low HP, I stole the Handsaw, but at the time I **knew** the next shell could be live — shouldn't I have considered surviving first? | Stealing the Handsaw won that game, keep doing it |
| With 1 shell left I cuffed him — I **knew** a reload follows the shot, so did that cuff do anything? | The cuff won it this time, so it's a good cuff |
| I had a Burner Phone but fired without using it — was that throwing information away? | I won without using it this time |

---

## Only learn "the controllable things": items

**You can't control luck; you can control item choices. So review only items.**

### ✅ What to learn

| Category | Example |
|---|---|
| **item choice** | low HP, the dealer holds Cigarettes and a Handsaw → steal the Cigarettes (survival), not the Handsaw |
| **item timing** | with 1 shell left, cuffing is useless (a reload follows the shot) |
| **item combos** | known live + Handsaw = 2; stealing the dealer's saw counts the same |
| **using information** | firing while holding an unused Burner Phone / Magnifier = throwing intelligence away |
| **failing to use** | two turns in a row without touching any item = hoarding too much |
| **paying too dearly** | spending Adrenaline (a big cost) to steal an item you can't use |

### ❌ What not to learn

- "I shot myself and died last time, so shoot the dealer next time" — luck
- "that decision won last time, so keep it up" — luck
- "mechanical numbers: what to do with N shells left" — compute it, don't memorise it

---

## Stay compact (important)

**lessons.md only ever grows, and then it slows everything down. It has to be compressed.**

### Hard limits

| Limit | Value |
|---|---|
| total entries | **no more than 12** |
| each entry | **no more than 3 lines** |
| when it's full | **merge similar ones / delete stale ones / fold two into one** |

### How to write it

✅ Good (it can change your next judgement):
```markdown
## Low HP: survival first
- At 1~2 HP, Cigarettes in the dealer's hand are worth more than the Handsaw
- Before using/stealing an item, ask: what do I lack most right now
```

❌ Bad (a running diary):
```markdown
## 2026-11-14 17:02 endless stage 2
- board: I'm at 1 HP, the dealer holds Cigarettes and a Handsaw
- I stole the Handsaw
- the next shell was live, I died
- should have stolen the Cigarettes
```

**The difference**: good ones are "rules", bad ones are "diaries". **Record rules, not diaries.**

---

## The user will train you

The user may:
- edit `lessons.md` directly
- tell you "that move was wrong"
- have you switch `style.txt`

**That's training, not an order.** Understand why first, then adjust your judgement.

**Different people training their AI will end up with different AIs** — that's the design intent.

---

## How to write think.txt

**Write only: the decision + the reason. One sentence. Written for a human, not for a log.**

### ✅ Good

```
1 live 1 blank = 50%, I'm at 1 HP. Shoot the dealer: a loss only hands over the turn, a win ends it.
```
```
Magnifier says live, dealer at 2 HP and I have a Handsaw — saw the barrel and shoot, 2 ends it.
```

### ❌ Bad

```
According to playbook line 406, shoot yourself when blanks dominate.
Now I need to read state.json immediately to confirm the shell counts...
```
(**don't mention the playbook**, **don't write the operational steps**)

```
Let me analyse the current board first. On HP, we have 2 and they have 1...
```
(**don't restate what the HUD already shows**)

### The one-sentence principle

> **Write "why I'm playing it this way", not "what process I'm following".**

---

---

## Decision speed (important; don't drag it out)

**Do only two tool round-trips per decision point:**

1. `read out/br/need_decision.txt` — **the decision point already has everything**
   (the board + your lessons), **so no need to also read state.json**
2. **in the same message**, `write think.txt` and `write decision.txt` together

**Don't do this**:
```
write think.txt first → think for a while → then write decision.txt
```
Two round-trips = 10~20 extra seconds. Across dozens of turns that's ten-plus minutes.

**Why it's slow**: every tool call is a complete model request.
The longer the context, the slower each request. **Round-trip count hurts more than context length.**

---

## About context (for the user to read)

After a long session the context grows and decisions get slower — **that's normal**.

**DSH compresses automatically**, but that itself takes time.

**Suggestions**:

| Situation | What to do |
|---|---|
| dozens of turns in and clearly slower | **start a new session** (a fresh one picks up from the playbook + lessons.md) |
| lessons.md is too long | it slows down every decision point; **keep it under 12 entries** |
| everything feels slow | first check whether there are too many tool round-trips (see above) |

**Switching sessions loses nothing**: `lessons.md` lives in a file, so a new session reads it once and inherits your training.

---

## Item naming (don't change it yourself)

In the game it's a **Magnifier** (the English name is **magnifying glass**) — **not a "mirror"**.

A mirror reflects; a magnifier is a lens — completely different things.
Use the full name when writing a decision: `use:magnifying glass`.

**The English name is `magnifying glass`; don't write `mirror`.**

> Defence: even if you write "mirror", the system treats it as a Magnifier,
> but **don't rely on that fallback** — writing it correctly is less work.

---

## After writing a decision, do one last self-check (against inventing items)

**Every `use:X` and `steal:X` you're about to write, X must actually be in your hand / on their side.**

Typical mistake (this actually happened): thinking "stealing the dealer's saw is a great play",
I also wrote `use:adrenaline` — **but I had no Adrenaline at all**.

**The system now rejects the whole line and asks again. Two rejects in a row and it executes only the shot, dropping all items.**

So after writing, glance at the `Mine:` line and confirm the names are all in there.

---

# How to write a decision (the key to saving tokens)

**Do only 2 tool calls per decision point.** This is not a suggestion, it's mandatory — one extra request per turn,
and the cost of a whole game doubles.

## The standard move: use `tools\br-set.py`, one command does it

**Don't hand-roll `python -c "..."`** — Chinese text plus quotes blows up easily in PowerShell,
and a failed write means a retry (a retry = one more full request = another slice of money).

**Use the ready-made script:**

```powershell
# 对局决策：think + decision 一起写
python tools\br-set.py "50/50 safe 打庄家" dealer

# 选择题（药瓶/菜单/加倍）：只写 decision
python tools\br-set.py yes
```

**Its output is a single `k`** — it confirms success without eating any tokens.

**Inside it writes decision first, then think**, so even if the think half fails, the main loop won't hang.

## Don't do these

| Don't | Why |
|---|---|
| **Don't use the `write` tool** | the loop constantly deletes and recreates these two files, so `write` reports `file changed since it was read` — and that failed attempt was still a full request |
| **Don't split it across two pwsh calls** | what one call can finish, two calls turns into double the requests |
| **Don't let the command print anything** | stdout goes into the context. If you want confirmation, `print('k')` |
| don't write think, then "think about it", then write decision | that's two round-trips |

## Exception: choice decision points (pill / menu / double up)

Those **don't need think.txt** — write the decision with a single command:

```powershell
python -c "open('out/br/decision.txt','w',encoding='utf-8').write('yes'); print('k')"
```

## How many calls in total?

| Kind | Calls |
|---|---|
| a game decision point | **2**: read + one pwsh |
| a choice question | **2**: read + one pwsh |
| plus the once-per-turn **wait for wake** | +1 (unavoidable) |

**3 in total. More than 3 means you're burning money.**

## Reading a decision point must use the `read` tool — never pwsh

**This one is hard.**

Reading `need_decision.txt` with `pwsh` (`Get-Content`, `type`, `cat`) turns the Chinese into mojibake:

```
鎴?2 : 搴?2 | 1 瀹?2 绌?鍓?3 鍙?| 鎴戠殑: 鏃?
```

(UTF-8 read as GBK)

**Then you start guessing from the shape of the characters** — guess wrong and you write items that don't exist.
It has actually happened: reading "Handcuffs" as "Adrenaline", then writing `use:adrenaline`,
and the whole decision got rejected.

**Because: console output encoding is a fixed bet; reading the file is accurate.**

| What you need to read | With what |
|---|---|
| `need_decision.txt` | **the `read` tool** |
| `state.json` | **the `read` tool** |
| `lessons.md` | **the `read` tool** |
| confirming a file got written | `pwsh` (only whether it exists, not what's in it) |

## Chain them — don't end the turn after every move

**If everything is normal you can handle several decision points in one turn** — that saves one "wake" request per move.

```
read the decision point → br-set.py writes → (sleep and poll) → read the next one → ...
```

**But note**:
- you need a sleep in between (otherwise you busy-spin)
- watch the **mojibake risk and the very long waits** on each move
- if anything looks off, stop; don't force it through

---

## Before every decision, look at your HP first (important)

**HP is the only resource in this game you can spend and get back.**
Below 2 HP, one more hit kills you — and then no amount of items in hand helps.

So for every decision, walk through this order:

### Step 1: how much HP do I have?

**Cigarettes: smoke them whenever you're not at full HP.**

Not "only when you're about to die" — **patch up a bit the moment you lose a bit**. Why:
they can put out **2 or more damage in one move** (Inverter + Handsaw = even a blank becomes 2,
known live + saw the barrel = 2). **3 HP looks safe, but one turn can take it away.**

**Holding a Cigarette = holding insurance you won't spend. It gets wiped when the stage changes; you can't carry it.**

| HP | What to do |
|---|---|
| **full HP** | don't smoke (a smoke would do nothing) |
| **down 1 or more** | **smoke if you have Cigarettes** — heal back up before shooting |
| **≤2 HP** | healing comes first, unless this move can finish them outright |

**Exceptions (you may hold off)**:
- this move **definitely** kills them (known live + Handsaw + them at ≤2 HP)
- they're cuffed + you're sure this shell hits

### Step 2: do I have any healing items?

| Have | What to do |
|---|---|
| **Cigarettes** (heal 1) | **smoke first, then look at the board**. That 1 HP can be the difference between surviving the next hit or not |
| **Pills** (50% heal 2 / 50% lose 1) | weigh the gamble. At 1 HP, lose 1 = dead, but if you die next turn anyway, gambling is rational |
| **neither** | you're down to play and luck |

### Step 3: the exceptions — when not to heal first

**Only these cases let you skip healing and shoot straight away:**

- this move **definitely** kills them (known live + Handsaw, them at ≤2 HP)
- they're already cuffed + you're sure this shell hits
- healing would **waste the only window** (e.g. they're at 1 HP and your Phone told you the next shell is live)

**Apart from these, heal first when low.**

---

### A real mistake, as it happened

```
我 2 : 庄 3 | 3实2空 剩5发 | 我的: 小刀×1、啤酒×2、香烟×2
→ 直接打庄家，什么都没用
```

**What went wrong**: 2 HP, holding 2 Cigarettes (worth 2 HP of healing), and 3 live 2 blank = 60% live.
**This move should have smoked first to heal**, instead of gambling 2 HP on a 60%.

**It optimised "this shell", not "staying alive".**

---

## ⚠️ Playing a second game: **do not** rerun br-launch.py

**One exception**: the **first** time after `br-launch.py` starts, it does NOT ask
"Play again?" — it sends `menu_start` directly so the game doesn't sit idle in the
bathroom (a new user would otherwise see "game launched but nothing happens").
**Every round after that does ask.**

**The main loop doesn't die.** When a game ends and you're back at the menu, the loop asks you itself:

```
[决策点] 一局结束了，要继续吗？
  yes   再开一局（menu_start）
  no    停在这里
```

**Write `yes` and the next game starts** — keep playing inside the same session; nothing needs restarting.

### When you actually should rerun

| Situation | Restart? |
|---|---|
| a game ended and you want another | **no**, answer yes |
| you want to switch normal / endless | **no**, just answer at the pill prompt |
| you changed code under `tools/` | yes (the loop doesn't hot-reload) |
| the loop really died (`run2.log` has `主循环结束` and stops updating) | yes |
| the game window is gone / black screen | yes |

**How to tell**: check whether `out/br/run2.log` is still being written. Still writing = alive, leave it alone.

**Note**: `br-launch.py` clears `run2.log` and starts it fresh, so "I restarted it" throws away the previous game's log.
**Don't treat it as a routine step.**

---

# ⚡ Recommended: use `br-next.py` — one request per turn

**The "read + br-set.py" flow above costs 3 requests per turn. This script squeezes it down to 1.**

## Usage

```powershell
python tools\br-next.py "50/50 safe 打庄家" dealer
python tools\br-next.py yes                      # 选择题
```

**It does four things**:

1. writes `decision.txt` (first, so the main loop can move on)
2. writes `think.txt` (the HUD shows it)
3. waits for the next decision point to appear
4. **prints the new board straight out**

## What it prints

```
k
=== 第 1 手的新局面 ===
我 2 : 庄 1 | 3 实 2 空 剩 5 发 | 我的: 小刀×1
--- 你的教训（lessons.md）---
## 香烟不满血就抽，别等到快死
...
--- 回答前 ---
1) ...
```

**Whatever comes after `=== 第 N 手的新局面 ===` is exactly what you need to read for the next turn.**

**No need to `read` again — it's already in front of you.**

## Why it saves

| Approach | Requests per turn |
|---|---|
| read + br-set.py + wait | **3** |
| **br-next.py** | **1** |

**76% of the time goes into "waiting for the board + relaying it", not into thinking.**

## When not to use it

- **you want to look at the board before deciding** (entering a new stage, say) → use the old way, `read` once
- **the script errors** (timeout / loop stopped) → it explains in plain words; check `run2.log` as it says
- **you're not sure it's reliable** → fall back to `read` + `br-set.py` at any time

## Don't drag a turn out too long

**By default it waits for just 1 turn and returns.** Chaining many turns makes a single turn absurdly long,
and any single failure in the middle is very hard to clean up.

**To chain**: `--max 3`, but **look back at `run2.log` once right afterwards**.

---

# The three ways compared (by cost)

| Approach | Requests per turn | When to use |
|---|---|---|
| **`br-next.py`** | **1** | use this by default |
| `read` + `br-set.py` | 3 | you want to see the board first / the script errors |
| `read` + the `write` tool | 4+ | **don't** (the file policy rejects it, wasting the request) |

