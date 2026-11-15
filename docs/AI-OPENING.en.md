# Opening prompt for the AI

Copy **the whole block** below and send it to a fresh session, then let it start on its own.

---

```
read docs/PLAYBOOK.md, then launch and start playing as it describes.

A few hard requirements (they're in the playbook too, stressed again here):

1. The permission must be danger-full-access. **Run python tools\br-permcheck.py first**
   (only continue if it returns 0 / says the permission is fine). The game writes %APPDATA%\Godot (outside the workspace);
   under workspace-write the install can succeed, but the game won't start, and the error looks like a broken mod.

2. Reading a decision point must use the "read file" tool (read) on out/br/need_decision.txt.
   Never read it with pwsh / Get-Content / type — PowerShell turns the Chinese into
   mojibake like 「鎴?2 : 搴?2」, and guessing item names from that goes wrong (the original session read
   "Handcuffs" as "Adrenaline" and wrote a use:adrenaline that didn't exist).

3. **Use only this one command per decision point**:

   python tools\br-next.py "<one-line judgement>" <decision>
   python tools\br-next.py yes                (choice questions: pill / menu / double up)

   It writes the decision + waits for the next turn + **prints the new board** — one request per turn.

   **Don't** read the decision point again (the board is already in its output).
   **Don't** write your own helper script — two sessions have tried, both failed
   (it returns `ok` without the board, so you have to read again, and not a cent was saved).
   **Don't** use the write tool for think.txt / decision.txt (the file policy rejects it).

4. Every decision is yours; the loop won't decide for you.

5. out/br/lessons.md already holds 6 lessons (see section 4 below), shown at every decision point.
   They aren't orders, they're "holes earlier players fell into". Follow them first; add your own when you lose.

6. In normal mode don't click the pill bottle; just open the two bathroom doors. Only endless mode
   clicks the pill bottle and then picks yes.
```

---

## What it should do

1. read the playbook
2. run `python tools\br-launch.py` (it starts the game + HUD + main loop + dialog capture automatically)
3. repeat "read the decision point → br-set.py writes the decision"
4. when it loses, add a lesson to `out/br/lessons.md`

## How you can tell it got it right

| What you see | Notes |
|---|---|
| it reads `need_decision.txt` with `read` | reading with pwsh → mojibake → wrong item |
| it makes only 2 tool calls per decision | more than 3 means it's burning tokens |
| it writes into `think.txt` | if it doesn't, the HUD keeps showing `deepsleeping` |
| the decision point shows "your lessons" | that means `lessons.md` was loaded correctly |
| the game really does move | if it's stuck, look at `out/br/run2.log` |

## If it gets stuck

Have it run:

```powershell
Get-Content out\br\run2.log -Tail 20
```

Or check playbook section 6 / the troubleshooting table in `docs/INSTALL.en.md`.

---

# 📖 About the bundled lessons.md (important)

**The `out/br/lessons.md` in this pack isn't empty — 6 entries in it were distilled from dozens of our games.**

They cover the mistakes the AI makes most:

| Lesson | What it fixes |
|---|---|
| survival first when low | gambling at 2 HP instead of healing |
| when the dealer holds Inverter + Handsaw, a blank also equals 2 | not understanding the threat their items pose |
| check the item bar before writing use:X | inventing items you don't hold |
| don't hand over a high-live-density round while low | giving turns away carelessly at low HP |
| read the Phone / Magnifier first, don't gamble on 50% | holding information and not using it |
| with tolerance items, first ask "can this turn one shell into two" | not knowing how to play Handcuffs |

## Three ways to use it

| What you want | How |
|---|---|
| **least effort** (recommended) | **do nothing** — start with these 6 and the AI is far ahead of training it from zero |
| **train it yourself** | have the AI empty `out/br/lessons.md` (keep only the format notes), then **start from zero** — it will summarise on its own, but that takes a lot of games |
| **mix** | keep the ones you agree with, delete the ones you want it to work out for itself |

**Say this to the AI to wipe it and start over**:

```
Delete every lesson in out/br/lessons.md, keep only the format notes at the top.
After that I'll play it myself and write lessons in when I lose.
```

**Note**: once it's wiped, the AI will **repeat those traps** — not using items, gambling at low HP, inventing items.
That's the price of "training from zero"; keep the file if you'd rather not pay it.
