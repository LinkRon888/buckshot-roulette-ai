# 恶魔轮盘：Godot mod 读状态（2026-11-08）

## 结论先说

- **对局内可以全自动**：靠 `state.json`。今天实打实赢过两关，出牌判定（实弹/空包）不再看图。
- **开场自动化没做完**：卡在"认屏"。跨机位指纹不稳，同一扇门在不同机位坐标不同。

## mod 怎么做（可复用）

游戏是 **Godot 4.1.1**，PCK 直接嵌在 exe 尾部：

```
PCK @ 57826816   engine=4.1.1  file_base=58282384
3572 个文件 / 703.8 MB，其中 195 个 .gd 是**明文源码**
```

- `tools/pck.py` 读 PCK 目录 / 导出文件
- `tools/pckpack.py` 解包 → 打补丁 → 重打包成独立 `mod.pck`
- 启动：`Buckshot Roulette.exe --main-pack out\br\mod.pck`
  **不动 exe、不动 Steam 文件**，删掉 pck 即恢复
- 补丁文件放在 `out/br/patch/`，覆盖同名路径（今天改了两个）：
  - `scripts/HealthCounter.gd` —— 每 0.12 秒 dump 状态到 `out/br/state.json`
  - `scripts/GlobalVariables.gd` —— autoload 探针，写 `out/br/scene.json`

### 踩过的坑（重要）

1. **DPI**：脚本必须 `SetProcessDPIAware()`。否则坐标被系统按 150% 缩放，
   算的 (1779,538) 实际点到 (2668,807) —— 屏幕外。所有"点错位置"的怪现象都是这个。
2. **Godot 渲染在 SubViewport 里**：`vp_size=[960,540]`，窗口 `win_ds=[2560,1600]`。
   `Camera3D.unproject_position()` 给的是 960×540 坐标系，**不能直接用**。
3. **`get_window()` 在 HealthCounter 里会崩**：加进 dump 会让整个 `_process` 失败、
   状态文件完全停写。用 `DisplayServer.window_get_size()` 代替。
4. **`im.activeItem` / `im.moving` 不可靠**：一直是 true / `<null>`，不能当判据。
5. **浮着的道具不进 `items_player`**，而是被算进 `items_dealer`。
6. **`itemArray_player` 从来没被赋值**（源码里只 append dealer 侧）。
   要读桌上道具得用 `im.items_dynamicInteractionArray`（带 `itemName` + `isPlayerSide`）。
7. 道具阶段的配额：`roundArray[currentRound].numberOfItemsToGrab`。

## state.json 字段

```
socket  phase(shoot/item/placing/other)  can_shoot        ← 最重要的三个
hp_player hp_dealer  live blank left  round batch start_hp using_items
player_cuffed dealer_cuffed sawed  items_player items_dealer
grids_occupied grabbed grabbed_enemy  quota  cigs_player cigs_dealer
targets[[名字,x,y,ok]]  clicks last_click[x,y,命中节点名]
vp_size win_ds  scale(未启用)
```

`can_shoot` 来自 `PermissionManager.interactionBranchArray` 里 `interactionAlias=="shotgun"`
那条的 `interactionAllowed` —— 这是"能不能出牌"的唯一权威开关。

## 实测有效的坐标（2560×1600，窗口在 (0,0)）

| 用途 | 坐标 |
|---|---|
| 菜单开始 | (1314,1041) |
| 浴室门 | (1536,823) |
| 走廊门（左侧那扇） | (255,900) |
| 生死状（推近时） | (1262,1050) |
| 生死状（拉远后） | (1298,494) |
| 键盘 A/I/M/I/Enter | (1531,392) (1644,640) (1644,724) (1644,640) (1779,538) |
| 枪（home 视角） | (1320,400) |
| 我自己 / 庄家 | (1283,1244) / (1219,381) |
| 道具箱口 | (1250,980) |
| 放道具的槽位 | (700,600) (700,450) (1900,800) (1900,400) (700,300) (1900,600) |

**门的可点区域在门板中下部**，不是门框上沿（差 100~200px 就点不动）。

## 出牌策略（已实现于 tools/br-run.py）

- `live==0` → 打自己（全是空包，续回合）
- `blank==0` → 打庄家（全是实弹）
- 我 1 血 → 一律打庄家，绝不冒险
- 空包比例 ≥78% 才敢打自己（实测连续三次 1实2空打自己都撞实弹，1/27 的概率）
- 道具顺序：手铐（保回合）→ 手锯（确认实弹才锯，1 血变 2 血）→ 开枪
- **出牌前先等 0.75 秒**让镜头从道具箱回到 home，否则点在动画中间 = 点空

## 没解决

- **开场认屏不可靠**：走廊/浴室各有多个机位，中心区指纹在同一类屏之间差 10~27，
  跨类只差 ~25，区分不开。结果就是来回点同一扇门。
- `targets` 里的 `shotgun` 坐标换算成屏幕后并不落在枪的可点区域（点上去命中 StaticBody3D）。

## 工具清单

| 文件 | 用途 |
|---|---|
| tools/pck.py / pckpack.py | PCK 读 / 打包 |
| tools/br-st.py | 打印状态摘要 |
| tools/br-act.py | 单步出牌（带 --think） |
| tools/br-run.py | 常驻自动打牌循环 |
| tools/br-click.py | 按 targets 名字点击（查不到就拒绝） |
| tools/br-screen.py | 认屏（中心区 80×50 指纹） |
| tools/br-auto2.py | 认屏状态机（开场，未跑通） |
| tools/br-enter2.py | 固定序列 + 像素差验证（10 步都验证过，但"变了"≠"走对了"） |
| tools/br-hud.ps1 | 左上角浮窗（状态 + 想法） |

## 2026-11-08 追加：点击必须先悬停（这是今天所有反复的根因）

**症状**：同一个坐标，有时能点中，有时完全没反应；我一直以为是坐标不准，改了一整天。

**实测**：横移扫描同一行，光标句柄在门的位置会变：

`
x=1216  cursor=1935083851   ← 箭头
x=1376  cursor=759432095    ← 变成可交互光标（门从这里开始）
x=1696  cursor=759432095
`

说明**坐标本来就是对的**（1536 在门中间）。

**真正的原因**：我的点击是"移动鼠标 → 60 毫秒后按下"。游戏需要先建立起 hover 状态才认这次点击，
60ms 太短。改成**移动后等 0.55 秒再按**，浴室门、走廊门、生死状、键盘全部一次命中。

**结论：所有点击函数默认 settle 必须 ≥0.5 秒。** 已改进 br-scene / br-act / br-click / br-run / br-enter2。

## 2026-11-08 追加：道具阶段的两个正确判据（都从源码读出来的）

1. **配额**：
oundArray[currentRound].numberOfItemsToGrab → 每边抽够就结束。
   抓够 quota 个就不该再点箱口，不用猜"是不是轮到我"。
2. **浮着的道具不进 items_player**，会算进 items_dealer；
   ctiveItem / moving 一直是 true / <null>，**不能当判据**。
   可靠做法：抽完自己记一个 need_place 标记，放下后清掉。

## 2026-11-08 追加：放道具别再试探

以前是"挨个点槽位，哪个 grids_occupied 变大就成"——道具 2 会先点已经被道具 1 占住的格子。
改成维护"道具 ↔ 格子"表，直接放第一个空位，每个道具只点一下。
**注意**：程序重启后表是空的，要按当前 grids_occupied 把前 N 个槽位先标成占用。

## 2026-11-08 追加：格子占用可以直接读（不用试）

`gdscript
@export var gridParentArray : Array[Node3D]    # 我的 4~8 个格子
@export var gridOccupiedArray : Array[bool]    # 每个格子占没占
`

模组已导出 my_slots = [[格号, 有没有东西, x, y], ...]（**960x540 视口坐标**，要乘 win/vp 才是屏幕坐标）。
实测：放了 2 个道具后，对应两个槽位变 True，其余 False —— 与 grids_occupied=2 一致。

**放道具就该这么放**：查 my_slots，取第一个 occupied==False 的坐标，点下去。不要挨个试。

注意：PermissionManager.interactionBranchArray 里**只有 shotgun 一条**，格子和道具都不在那里，
必须从 ItemManager 取。

## 2026-11-08 追加：道具连点的真正原因

use_item 里写了"3 秒内不重复"，但**忘了在点击后记录时间**，所以锁形同虚设，手铐被连点 9 次。
修法：点完立刻 _item_lock['t'] = time.time()。修好后实测每种道具只触发一次。

## 2026-11-08 追加：可复用流程图

- 人看的：
otes/br-flow.md（流程图 + 每步点哪里 + 对局循环 + 今日教训）
- 机器读的：	ools/br-flow.json（同样的内容，结构化，带 hoverMs / 缩放系数 / 点击坐标）

这份的东西**不依赖某一次对局**，换会话照它就能操作。核心是那两条：
悬停 0.55 秒再点、放道具用 my_slots 不要试。

## 2026-11-08 深夜：道具终于能用（定位问题的完整结论）

**道具能不能点中，卡了一整晚。四种坐标来源全部试过：**

| 来源 | 结果 |
|---|---|
| 硬编码坐标 | 偏 |
| `my_slots`（格子锚点 `gridParentArray` 的 global_position） | 镜头在对方那边时投影成负数，点屏幕外 |
| 截图手量 | 每次布局不同，量一次就失效 |
| `item_points`（道具 branch 往上第一个 Node3D）**+ 区分敌我** | **对了** |

**关键诊断**（把道具节点链倒出来才看清）：

`
0: interaction branch[Node]              ← 交互判定
1: cigarette box_parent[MeshInstance3D]  ← 道具模型本体，就是这一层
2: player grid intake colliders[Node3D]
3: compartments parent[Node3D]
`

所以"从 branch 往上找第一个 Node3D"是对的。**真正的错是没过滤 `isPlayerSide`**：
庄家的道具也在同一个数组里，它在对面的位置投影出来自然跑到视口外（实测有个手锯是 x=1070、y=673，超过 960x540）。

修法：`item_points` 每项加上 `isPlayerSide`，Python 侧只用 `it[3] == true` 的。

**另一个必修的时序问题（用户指出的）：**

1. 看完子弹（放大镜）后游戏还在播动画，立刻点道具必然没反应 → 用道具前统一等 0.3 秒
2. 判断不能复用循环开头的旧快照（模组 0.12 秒才写一次）→ 每次判定前重新读一次
3. **道具用掉后回读确认不能只等 0.35 秒**——游戏更新比这慢，实测会被误判成"没用成"，
   而道具其实已经消失了。改成轮询最多 1.4 秒。

**抽道具的正确点位**：箱口下半部那块大黑区，实测 (1280,880)。
（(1250,980) 是老坐标，镜头一变就落到箱子外面）

**验证道具真用了的独立证据**（不要靠自己说）：
- 小刀 → 模组 `sawed` 变 true
- 放大镜 → 读 `next_shell`
- 手铐 → `dealer_cuffed` 变 true

**还没修的**：`shot-miss`——锯好枪、确认实弹、庄家只剩 1 血，那一枪点出去没生效。
该加"同一坐标重试一次"，但今晚没做。

## 2026-11-09 凌晨：领奖箱怎么开（用户指出，一次成功）

打赢三关之后进入领奖（`socket = "cash briefcase"`），开箱是**三步**，我原先只做了前两步：

`
1. 点左卡扣   (900, 1190)
2. 点右卡扣   (1830, 1190)
3. 点箱盖     (1350, 870)   ← 这一步不能少，少了箱子纹丝不动
`

开箱后满箱钞票 → **按任意键** → 结算画面（发掉的子弹/香烟/踢开的门/啤酒/现金总额 82805 $）
→ 再按任意键 → 回到菜单。

**教训**：卡扣只是解锁，真正的"掀盖子"是第三步。我一直在卡扣位置换来换去，
把"往左一点"理解成坐标要精调，其实流程本身就少一步。
"用户说位置不对"时，先怀疑自己少做了动作，而不是坐标差几个像素。

**顺带记下这局的完整胜利**：三关全胜（2 血 → 4 血 → 6 血），最终 `hp 3:0`。
道具用了放大镜、小刀、手铐、啤酒——"放大镜确认实弹 → 小刀加伤 → 开枪打庄家"
这条链路完整跑通，锯过的枪实弹打出 2 点伤害。

## 2026-11-09 凌晨：道具点击为什么时好时坏——根因确定

**数据**（多局日志统计，成功率与道具形状强相关）：

| 道具 | 形状 | 成功率 |
|---|---|---|
| 香烟 | 实心方盒 | 100% |
| 小刀/手锯 | 长条 | 93% |
| 放大镜 | 镜片+手柄（L 形） | 67% |
| 手铐 | **两个环，中间是空的** | 50% |

**根因**：点击点取的是几何中心（模型原点 / AABB 包围盒中心）。
- 方盒子 → 中心一定在实体上 → 100%
- **手铐是两个环，包围盒中心正好落在两环之间的空洞里** → 点过去是空气 → 必失败

所以"坐标调不准"不是精度问题，是**这个点本身在物理上就是空的**。调多少次都没用。

**已实现的正解（还没验证）**：不猜点，用**游戏自己的射线**验证。
_dsh_hit_point(cam, branch, mesh)：从候选屏幕点发射线，只有打中该道具的碰撞体才算数；
按 17 个偏移依次试（0/±40/±80 的网格）；全都不中就返回 null。
模组输出 item_pts2 = [[名字, x, y, 是否可点]]，不可点的直接跳过、绝不乱点。

**下一次要做的**：重启游戏打一局，看 item_pts2 里手铐的坐标是不是非 -1，
以及成功率有没有从 50% 上去。如果射线也打不中，说明该道具在该视角下真的不可点，
那就该换时机（等镜头回到正面再点），而不是换坐标。

**另外记一条流程错误**：领奖箱是三步（左卡扣 → 右卡扣 → **掀箱盖**），
我原先少最后一步，一直以为是卡扣坐标不对，白白换了七组坐标。
"用户说位置不对"时，先怀疑自己少做了动作。

## 2026-11-09：复活的正确流程（用户纠正，已实现）

**两条路完全不一样，不能混：**

| 死在哪 | 流程 |
|---|---|
| 第 1、2 关 | 约 18 秒 → 回到浴室 → 点门1 → 5 秒 → 点门2 → 9 秒 → 到牌桌 |
| **第 3 关** | 约 13 秒 → **天堂的大铁门** → 点铁门 → 约 18 秒 → 点「重试」→ 约 7 秒 → 回到浴室 → 点门1 → 门2 → 牌桌 |

**复活后只推两次门就到牌桌，不用再签生死状**（还是同一把）。
**只有"重新开始一把"才需要重新签名。**

实现：`br-enter3.py door1` 先读 state 里的 `batch`（0/1 = 前两关，2 = 第三关）决定走哪条；
两条最后都汇合到"门1 → 门2 → 牌桌"，并且跳过签名。

**等待方式也改了**：不再是固定 `sleep(18)`。
对局循环在 `hp_player == 0` 那一刻往 `out/br/death.txt` 写毫秒时间戳，
重生脚本只补 `实测时长 - 已过去时间`，所以启动晚了也不会发呆。

**踩到的坑**：`wait_remain` 里写了 `io.open` 但没 `import io`，异常被 `except` 吞掉，
导致"已过去时间"永远算 0、照样等满——这种静默失败最难发现，测试时用模拟时间戳才抓出来。

**待确认**：大铁门坐标 `(1376, 820)` 还没实测；重试按钮 `(1300, 890)` 是之前验证过的。

## 2026-11-09 下午：改成"我决策 + 脚本执行"（C 模式）

**用户确认的观察**：我亲自一手一手打（A 模式）时"比脚本拟人很多，道具也用得出来"，
但**太慢**——每回合要 6~8 次工具往返（读状态→写面板→点道具→回读→点枪→点目标→再读），
十到二十秒，其中我真正思考的时间很短，大部分浪费在往返上。

**解法：一个回合一次调用**（`tools/br-turn.py`）

`
python tools/br-turn.py show                  # 紧凑看盘面（我要的全部信息）
python tools/br-turn.py draw                  # 道具阶段：抽→放→反复，直到阶段结束
python tools/br-turn.py run --think "..." --next "..." \
    --item 手铐 --item 小刀 --shoot 庄家        # 一步做完：等轮到我→用道具→点枪→点目标→验证
`

**实测效果**：道具阶段从手动的近 2 分钟降到 **6.4 秒**；每回合从 ~15 秒降到 ~5 秒。

### 今天学到的三条硬规矩

1. **`socket=briefcase` 就是"道具阶段还没结束"，必须继续抽。**
   不能因为"箱子看着空"就当抽完了——箱子是一次吐一个道具的，看着空只是这一轮没吐。
   我因为它误判过两次，白等了半分钟。

2. **箱口和箱盖不是一个地方。**
   - 抽道具点**上半部开口**（今日视角约 935~1625, 417~786，中心 1280,600）
   - 掀盖点**下半部/箱盖**（1350,870 那一带）
   我一直点 (1280,880) 抽道具，那其实是箱盖位置，所以"抽不动"。

3. **领奖箱三步（用户实测的坐标）**
   `
   左卡扣 (853, 1207) → 右卡扣 (1691, 1213) → 箱盖 (1260, 957)
   `
   · 进领奖台后**先等约 13 秒**再点，太早点不动
   · 开盖后**约 30 秒是过场+结算，不要点**
   · 之后任意键/点击回菜单
   我之前一直在 1720~1840 试右卡扣，实际是 1691——差那几十像素就是不开。

### 还欠的

- `br-turn.py` 的开枪验证仍会**误报"没打出去"**（其实打出去了）。已放宽为
  "弹数减少 / 血量变化 / 回合交出，任一成立即算命中"，但偶尔还会喊错。
  下次可以干脆只看回合是否交出。
- 我的出牌阈值要改：**空包比实弹多就该打自己**（原先写 78% 太保守）。
  今天实测 67% 空包打自己是对的——不伤血还保住回合。

## 2026-11-09 深夜：坐标为什么一直不对（重大发现）

### 根因（三个叠加）

1. **y 比例算错**。真实的视口→屏幕变换是
   `screen = vp × 2.667 + (0, 80)`（游戏上下有 80px 黑边），
   我一直按 1600/540 = 2.963 算，越往下偏得越多。
   模组里可以直接读 `get_viewport().get_screen_transform()` 拿到真值。

2. **`m button_choice dealer` / `you` 的 `mouse_filter = 2`（MOUSE_FILTER_IGNORE）**。
   它们压根不接收鼠标点击，是给手柄/键盘焦点导航用的。
   **所以模组给出的 UI 矩形再准也没用——点不动。**

3. **真正的判定对象是 3D 交互点，不是 UI**。
   画面上"庄家"/"你"只是 Label，可点的是：
   `text dealer` / `text you` / `briefcase intake`。

### 正确解法：用 hover 闭环

`InteractionManager.activeParent` 就是游戏自己射线算出的"鼠标指着谁"。
模组导出成 `hover = [节点名, 路径, 别名]`，工具流程改成：

`
移动鼠标 → 读 hover → 别名对上才点击
`

实测别名：
- 拿枪：`shotgun`（可见位置约 1290,620 一带；1280,760 是桌子，点不到）
- 打庄家：`text dealer`（约 1274,375）
- 打自己：`text you`（约 1277,1230）
- 抽道具：`briefcase intake`（约 1250,1350）

### 其它实测结论

- **`SetCursorPos` 移鼠标无效**：游戏收不到 motion 事件，内部光标不跟。
  必须用 `SendInput` + `MOUSEEVENTF_MOVE|MOUSEEVENTF_ABSOLUTE`。
- **`state.json` 动作后滞后数秒**，回读窗口至少给 6~8 秒，否则会误判"没打出去"。
- `can_aim=True` 时 `can_shoot` 本来就是 False，
  验证开枪不能用"回合是否交出"当判据，只能看 `left`/血量变化。
- `item_pts2` 经常返回 -1，不可靠；`item_descriptions` 是占位符（"HANDSAW DESC"）。
- `gun_pt`（投影 shotgun 交互点）得到 (3933,-876)，在屏幕外，没用。
- 不在对局时也写 `in_match=false`，避免菜单留着上一局的旧数据。
- `managers` 里已剔除 `sequenceArray`/`tempSequence`（那是完整弹序=透视）。

## 2026-11-10 凌晨：待修的 bug 清单（明天做）

### 当前进度（可续打）
游戏停在**第三关**：batch=2、round=1、我 5 : 庄 6、道具阶段。
wins=2（第一关、第二关都赢了），losses=0。

### A. 我自己造成的代码 bug（共 4 次，最该改的）

**症状**：`tools/br-turn.py` 反复报 `NameError: name 'xxx' is not defined`。
被删过的：`snapshot_line`、`shoot`、`parse_expect`、`GUN_CANDS` 等候选点表。

**根因**：我用"字符串定位 → 整段替换"改代码，
替换区间 `def do_items` → `def main` 之间**还夹着别的函数/常量**，一换就一起没了。

**修法**：
1. 所有函数单独成块，块之间不留其它定义；
2. 每次改完自动自检——遍历需要的函数名和常量名，缺了就报警；
3. 常量统一放文件头部（已做：候选点表已挪到 GRID_Y_OFFSET 之后）。

### B. 读取游戏状态的三个坑

1. **滞后**：动作后 `state.json` 要过数秒才反映。2.5 秒回读会误判"没打出去"。
   → 统一轮询 6~8 秒，只认 `left` 减少或血量变化。
2. **半截文件**：写入非原子，JSON 解析随机失败。
   → 所有读取必须 try 重试 3~6 次（部分临时脚本没加）。
3. **菜单/过场不写文件**：留下上一局的旧数据。
   → 已加 `in_match` 标记；工具要**先查 in_match 和 ms 新鲜度**再决策。

### C. 坐标类字段绝大部分是废的（已验证）

| 字段 | 结论 |
|---|---|
| `aim_btns` / `briefcase_btns` | ❌ UI 空间坐标 + 按钮 `mouse_filter=IGNORE`，点了没用 |
| `gun_pt` | ❌ 投影到 (3933,-876)，屏幕外 |
| `item_pts2` | ⚠️ 经常 -1 |
| `item_descriptions` | ⚠️ 占位符 "HANDSAW DESC" |
| **`hover`** | ✅ **唯一可靠的定位手段**（游戏自己的射线结果） |

### D. 位置会漂移

用道具、锯枪之后**镜头会动**，枪和目标的屏幕位置跟着变，候选点全部失效。
→ 已加兜底扫描（粗扫桌面找别名），但慢（一次 20~30 秒）。

**另外**：游戏不在前台时 `hover` 读不到——起 HUD 面板会抢一次焦点，
所以每轮开打前必须**先把游戏切回前台**再动作。

### E. 我对游戏机制理解错的

- `can_shoot`（枪在桌上）和 `can_aim`（枪已在手、等选目标）是两种不同的"能动手"，
  等回合必须两个都认。
- 空包打自己之后**枪不撒手**，直接进 can_aim，不用重新点枪。
- 画面上的"庄家/你"是 3D 标签（`text dealer`/`text you`），不是 UI 按钮。

### F. 明天要做的五件事

1. 给 `br-turn.py` 加自检：函数/常量缺一个就拒绝运行并报出来。
2. 删掉所有对 `aim_btns`/`gun_pt`/`item_pts2` 的依赖，只留 `hover`。
3. 加 `ensure_match_state()`：先验 `in_match` + `ms` 新鲜度，再决策。
4. 校验开枪只认 `left` 减少或血量变化，不再用 `can_shoot`。
5. 记住每个动作点最后一次成功的坐标，失败才扫描；扫描结果缓存。

## 2026-11-10 晚：无人值守自动化的进展与待修清单

### 已经跑通的部分（实测，不是推测）

**1. 命令通道（mod 端）**：`out/br/cmd.txt` → 校验 → 调游戏函数 → `cmd_result.txt`
已验证的命令：
- `grab_gun` / `shoot|dealer|self`（走 `InteractionManager.InteractWith`）
- `door_bathroom` / `door_backroom` / `waiver`
- `sign|字母` / `sign_enter`（带按键动画 Press()）
- `grab_item` / `place|格号`（守 quota）
- `use|道具名`（走 `PickupItemFromTable`，会删格子节点）
- `latch|L|R` / `lid` / `heaven`

**2. 菜单也能自动**：autoload `GlobalVariables` 里加了 `cmd_menu.txt` → `MenuManager.Start()`

**3. 阶段判据**：`can_do`（所有 InteractionBranch 的 allowed 别名）——
浴室门、走廊门、生死状、签名、领奖卡扣、天堂门都在里面。
**注意**：`text dealer`/`text you`/`pill bottle`/`crt` 是常驻别名，判阶段要过滤。

**4. 主循环** `tools/br-run2.py`：
- 看到 can_do 里的别名就执行对应命令（全自动开场/道具/领奖）
- 轮到我自动拿枪
- 到"枪在我手上"就停下，把盘面写到 `need_decision.txt`，等我写 `decision.txt`
- 死亡后自动重走浴室→走廊

### 关键教训（绕了很久换来的）

1. **`Shoot()` 不能直接调** —— 必须走 `InteractionManager.InteractWith("text dealer")`，
   否则 ①"庄家/你"标签不消失 ②`fs_dec` 锁不上，能重复开枪。
2. **`InteractWith` 会返回成功但什么都不做**（`fs_dec` 已锁时）。
   所以**开枪后必须验证弹数/血量变了**，否则就是空操作。已加验证+重试。
3. **道具效果只能走 `PickupItemFromTable`**，只调 `InteractWith` 会留下桌面模型。
4. **`can_do` 会滞后/残留**：庄家回合时仍可能显示 shotgun/item，所以每条命令
   还要叠加 `socket=='home'`、`can_aim`、`dealerHoldingShotgun==false` 等二次校验。
5. **`itemDescription` 是占位符**（"HANDSAW DESC"），道具效果文本只能看代码。
6. **`aim_btns` / `briefcase_btns` / `gun_pt` / `item_pts2` 都不可用**：
   前者是 UI 空间且按钮 `mouse_filter=IGNORE`，后者投影到屏幕外/返回 -1。
7. **鼠标点击三条硬要求**：SendInput 绝对移动（不能 SetCursorPos）、悬停 0.5 秒、
   游戏必须真前台（`GetFocus` 是线程局部的，查别的进程要用 `GetGUIThreadInfo`）。
8. **键盘也能进控制器模式**：`ControllerManager._input` 里
   `InputEventKey` + 导航键 → `controller_active=true`；鼠标一动就退出。
   这条是"真实输入"的可行路径，**还没用起来**。

### 待修的问题（下次集中处理）

1. **`br-run2.py` 反复改坏**：我多次用"字符串定位整段替换"，把入口 `if __name__`、
   夹在中间的 `act()`、`can_do` 过滤条件一起删掉。改完必须跑一次
   `ast.parse` + 函数清单自检。
2. **`NOISE` 过滤把决策点判据也过滤了**（已修，但说明过滤要分两套：判断阶段用过滤后，
   判断能不能开枪用原始的）。
3. **决策点会出现 `剩 0 发`**（已修：要求 `left > 0`）。
4. **道具阶段开头会刷很多"can_do 里没有 briefcase intake"**：箱子还没准备好，
   逻辑是对的但日志吵，可以加个安静期。
5. **`use` 之后血量/道具数有 1~2 秒滞后**，回读要等。
6. **还没做**：用键盘导航（方向键+回车）替代 `shoot` 命令。
   这条能彻底避开 `fs_dec` 和视觉残留问题，代价是慢一点。

### 文件清单

- `tools/br-run2.py`  主循环（事件驱动 + 决策点暂停）
- `tools/br-turn.py`  grab / wait / shoot / draw 单步工具
- `tools/br-chain.py` 开场链（已被主循环取代）
- `tools/br-pick.py`  鼠标坐标拾取器（量未知按钮用）
- `tools/br-hovermap.py`  hover 网格扫描（画交互区域地图）
- `tools/br-focus.py`  强制前台/焦点
- `docs/DESIGN.md`    所有工程细节（这个文件）

---

## 2026-11-12 晚（23:20）：普通模式完整跑通 + 七个 bug 的根因

### 结论先说

**普通模式从菜单到通关全自动跑通了一整局**，没有一次人工操作。
备份在 `out/br/backup/normal-20261112-2318/`（含 mod.pck + patch 源码 + tools + 还原说明）。

### 实测的一整局（日志时间戳）

```
23:12:13 现在 我4:庄0              ← 第三关赢下
23:12:29 领奖阶段：开始等结尾动画
23:12:29 latch|L -> OK
23:12:31 latch|R -> OK
23:12:33 lid -> OK
23:12:55 ending_exit -> OK         ← 等结尾动画 22 秒
23:12:59 回到菜单成功
23:13:11 在菜单待机                ← 之后一直安静，不亂按
```

### 七个 bug（都是实测挖出来的，别再踩）

**① `_dsh_cmd` 里不能用 `d[...]`**
`d` 是 `_dsh_dump()` 的局部变量，`_dsh_cmd()` 里没有。
写 `d["xxx"] = ...` → GDScript 未定义标识符 → **整个 HealthCounter.gd 编译失败 → mod 全挂**（状态不更新、命令无响应）。
修：用成员变量 `_dsh_dump_items`，在 `_dsh_dump` 里再拷进 `d`。

**② `var x := obj.get("name")` 会解析失败**
`get()` 返回 Variant，`:=` 无法推断类型：
```
Parse Error: Cannot infer the type of "bv" variable
USER ERROR: Script does not inherit from Node: res://scripts/GlobalVariables.gd
```
**GlobalVariables 是 autoload，它挂了游戏就黑屏起不来。**
修：去掉 `:=`，写成 `var x = obj.get(...)`。
**教训：改完 .gd 先看 Godot 日志有没有 `SCRIPT ERROR` / `Parse Error`，再谈功能。**

**③ 抽到道具后立刻放置 → 道具被没收（幽灵格的真正原因）**
```gdscript
func GrabItem():
    items_dynamicInteractionArray.append(...)   ← 这里就登记了，我立刻看到"抽到了"
    moving = true
    await get_tree().create_timer(lerpDuration - .2)   ← 还要 0.25 秒
    if (numberOfOccupiedGrids != 8): ...        ← 之后才检查空间
    else:
        activeItem.queue_free()                 ← 我抢先放好 → 计数变 8 → 它把刚放的道具删了
```
修：`grab_item` 之后 **sleep 0.65 秒**再做放置。

**④ 放完道具要等飞行动画结束**
```gdscript
func LerpItem():                    # ItemManager._process 每帧跑
    activeItem.transform.origin = lerp(pos_current, pos_next, c)   ← 只有这一个 activeItem
```
抓下一个道具会把 `activeItem` 换掉，上一个还在飞的就冻住/消失。
修：放完等 `lerp_duration + 0.45` 秒（`lerp_duration` 实测 0.45）。
我把 `lerp_duration` 从 mod 导出了（字段 `lerp_duration`）。

**⑤ 格子满 + 配额没满 → 道具阶段永远卡住**
`EndItemGrabbing()` 只在 `numberOfItemsGrabbed == numberOfItemsToGrab` 时被调用。
我格子满就停手 → 配额永远不够 → 卡死。
游戏的正确路径：再抽一次 → `GrabItem` 走 `NO SPACE` 分支 → `EndItemGrabbing()` 收尾。
修：格子满但 `grabbed < quota` 时**补发一次 `grab_item`**，等 3 秒。
实测：满格进入道具阶段 → 14 秒收尾，不卡。

**⑥ 放完道具后 intake 权限有 0.45 秒延迟**
`PlaceDownItem` 的 else 分支：
```gdscript
await get_tree().create_timer(lerpDuration).timeout
interaction_intake.interactionAllowed = true    ← 0.45 秒后才恢复
```
我立刻检查 `can_do` 里没有 `briefcase intake` → 误判成"不让抽" → 直接 return。
修：先 `wait_until('briefcase intake' in can_do)`（最多 4 秒），再判断要不要补 grab。

**⑦ 天堂计时器没重置 → 下次进天堂抢跑**
`heaven_seen_at` 只在 `is_death` 分支重置，离开天堂的正常路径没重置。
下次进天堂时 `waited` 很大 → 跳过 12 秒等待，直接点门 → 画面被跳过，看着像"没点门就重启"。
修：不在天堂的分支里把 `heaven_seen_at / heaven_text_at / heaven_door_at` 全清掉。

### 第三关死亡 → 天堂的完整时序（实测）

```
[HEAVEN] scene appeared, wait for camera pan (~12s)
（等 12 秒）                    ← BeginLoop: 1s + 音乐 + camera pan down + 11.1s
[HEAVEN] door ready -> Fly()
heaven_door -> OK               ← InteractionManager "heaven door" → Heaven.Fly()
（等 15.6 秒飞行）
[HEAVEN] 文字已显示(alpha=1.00)  ← Fly 里 await 15.6 后 buttonArray[*].isActive = true
（等 2 秒）
[HEAVEN] 等满 2 秒 -> 选「重试」
heaven_retry -> OK              ← HeavenManager.Button_Retry() → death.tscn
door_bathroom / door_backroom   ← 回到游戏
```

**关键**：`isActive = true` 只是允许交互，"重启"字样要等它之后；`btn_retry.visible` 从场景加载就是 true，**不能拿它当判据**。
判据用 `buttonArray[0].isActive`（字段 `heaven_buttons`）+ 再等 2 秒。

### 新加的命令和字段

**HealthCounter（main 场景）**
- `fix_grids` —— 用真实道具重建 `gridOccupiedArray` / `numberOfOccupiedGrids`，修幽灵格
- `dump_items` —— 把 `items_dynamicInteractionArray` 每条摊开（名字/玩家侧/格号/实例id/在树里），排障用
- `set_batch|N` —— 调试跳关（0/1/2），验证用
- `ending_exit` —— `EndingManager.ExitGame()`，通关后回菜单

**GlobalVariables（autoload，跨场景）**
- `heaven_door` —— `Heaven.Fly()`
- `heaven_retry` —— `Heaven.Button_Retry()`
- 新字段：`is_heaven` / `is_death` / `heaven_door_ok` / `heaven_buttons` / `heaven_btn_vis` / `heaven_btn_alpha`

**HealthCounter 新字段**
- `spawn_children` / `dyn_inter` / `dyn_ind` —— 桌面节点数 / 登记的道具数 / 登记的指示器数
- `num_occupied` / `occupied_true` —— 游戏记账 / 数组里 true 的个数（这两个同源，**不能单独用来判漂移**，要看 `dyn_inter` 里有没有 null）
- `lerp_duration` —— 道具飞行动画时长（0.45）
- `fs_dec` —— 开枪锁（false=这枪会生效）

### 排障方法（这次很管用）

1. **先看三个数**：`num_occupied` / `dyn_inter` / 真实道具数。不一致就是有幽灵或丢件。
2. **`dump_items`** 看数组里是不是有 null —— null 表示对象被 queue_free 但没从数组删。
3. **state.json 不更新 = HealthCounter 挂了**，先查 Godot 日志的 `Parse Error`。
4. **菜单/天堂状态下 state.json 是旧快照**，判场景要用 `scene.json` 的 `scene` 字段。

### 还没做的

- 嗑药加倍模式（endless + 分数翻倍选择），规则不同，要重新摸
- 道具拾起/放置的视觉指针高光没验证过

---

## 2026-11-12 深夜（00:50）：无尽模式（嗑药）打通 + 决策作弊问题

### 无尽模式完整流程（代码级，已实测）

**入口**：洗手间 → 点药瓶 → 选 ✔

```gdscript
# IntroManager.gd
func SelectedPill(selected : bool):
    if (selected):
        pill_unlock.IncrementAmount()
        endlessmode.SetupEndless()          # ← 只有选 ✔ 才进无尽

# EndlessMode.gd
func SetupEndless():
    roundManager.endless = true
    playerData.hasReadIntroduction = true   # 跳过所有新手对话
    amounts[*].amount_active = amount_don     # 9 种道具全开
```

**药瓶出现条件**（`IntroManager._ready`）：
- 不是死亡复活（`!playerEnteringFromDeath && !enteringFromTrueDeath`）
- 且 `user://buckshotroulette_pills.shell` 存在（选过一次 ✔ 就会生成）

**结构**：每大轮 3 小关，`playerData.currentBatchIndex` 0→1→2

**死亡**（`DeathManager.MainDeathRoutine`）：
```gdscript
if (roundManager.endless):
    change_scene_to_file("res://scenes/death.tscn")
    return                          # ← 在 SaveGame() 之前 return，所以不存档
```
→ `TempDeathScreen._ready()` → `change_scene_to_file("res://scenes/main.tscn")`
→ 因为没存档（`MenuManager.Start()` 会 ClearSave），`currentBatchIndex` 读回 0
→ **从这一大轮第 1 小关重来**，药瓶会再次出现，要重新选 ✔

**打赢第三小关**（`RoundManager.EndMainBatch`）：
```gdscript
playerData.currentBatchIndex += 1
if (playerData.currentBatchIndex == 3):
    if (endless):
        counting = false
        BeginScoreLerp()            # 进翻倍结算
        return
    # 普通：进领奖箱
```

**分数公式（重要：是按时间，不是按道具）**：
```gdscript
# RoundManager.gd  BeginScoreLerp
startscore = prevscore
if (!doubling):
    score_deduction = initial_time / 600 * 40000
    endscore = 70000 - int(score_deduction)
    if (endscore < 10): endscore = 10
    prevscore = endscore
else:
    endscore = prevscore * 2         # 之后每次直接翻倍
    prevscore = endscore
```
`initial_time` 从 **签完名那一刻** 开始累加（`SignatureManager.gd:132: roundManager.counting = true`），
到打赢第三小关停止。

| 用时 | 初始金额 |
|---|---|
| 3 分钟 | 58000 |
| 5 分钟 | 50000 |
| 10 分钟 | 30000 |
| 12 分钟 | ≈20800（实测 20836） |

**用户文档里写的是「与道具使用挂钩、越少则越多」——这是错的，真实杠杆是时间。**
（道具用得少会打得快，所以看起来像因果，其实是相关。）

**翻倍选择**：
```gdscript
"double yes": shotgun.roundManager.Response(true)    # ✔ 继续
"double no":  shotgun.roundManager.Response(false)   # ✘ 结算
```
- ✔ → `RestartBatch()` → `currentBatchIndex = 0` → 新一大轮（实测 batch 回到 0）
- ✘ → `brief.ending.endless_score = endscore; brief.MainRoutine()` → 领奖结算

### 反作弊：`next_shell` 的门禁（今天最重要的修正）

**问题**：mod 一直导出 `roundManager.shellSpawner.sequenceArray[0]`，那是子弹队列里**真实的下一发**。
等于免费放大镜。我一度靠它做决策，还编出过「放大镜看到实弹」而当时我身上根本没有放大镜
（日志 `跳过 magnifying glass（场上确实没有）` 证明循环拦住了动作，但我的结论已经编出来了）。

**用户的规则**：只有真的用了放大镜之后才能读下一发；偷到对方的放大镜也算（偷到即使用）。

**实现**（`HealthCounter.gd`）：
```gdscript
var _dsh_mag_until := 0

# use 命令成功且道具是放大镜时：
_dsh_mag_until = Time.get_ticks_msec() + 15000
# steal 命令偷到放大镜时：同样开 15 秒

# 导出时：
var nxt := "unknown"
if Time.get_ticks_msec() < _dsh_mag_until:
    nxt = str(roundManager.shellSpawner.sequenceArray[0])
d["next_shell"] = nxt
```
平时一律 `unknown`。决策面板会显示 `放大镜看的: 实弹/空包`。

**注意**：15 秒窗口很紧，我事后读 `state.json` 常常已经过期——
**应该从决策面板（need_decision.txt）读**，那是放大镜用完 0.1 秒内生成的。

### 屏幕文字的合法读法

**原则**：画面上显出来的字可以读；隐藏状态不能读。

| 信息 | 显示机制 | 合法读法 |
|---|---|---|
| 电话「第 N 发」 | `BurnerPhone.gd` → `dia.ShowText_Forever(fulldia)` → `Dialogue.dialogueUI : Label` | 读 `Label.text`（mod 导出 `d["dialogue"]`） |
| 放大镜 | 纯动画/视觉，没有文字节点 | 按用户允许：直接用 `next_shell`（等价效果） |
| 实/空数量 | 游戏本来就显示 | `d["live"]` / `d["blank"]` / `d["left"]` |

**电话的关键细节**（`BurnerPhone.gd`）：
```gdscript
randindex = randi_range(1, len - 1)     # 随机第 1..len-1 发，不是第 0 发
if (sequence[randindex] == "blank"): secondpart = tr("BLANKROUND")
else: secondpart = tr("LIVEROUND")
fulldia = tr(firstpart) + "\n... " + tr(secondpart)
dia.ShowText_Forever(fulldia)           # 显示 3 秒后 HideText
```
**对话框只显示 3 秒**，所以要边用边采样 → `tools/br-dialogue.py`

**`DialogueManager` 必须加进 `_DSH_WANTED`**（原来没有），否则 `_dsh_mgr_get("DialogueManager")` 返回 null。

### 肾上腺素：偷取是交互式的，且窗口只有 7 秒

```gdscript
"adrenaline":
    animator_playerHands.play("player use adrenaline")
    await get_tree().create_timer(5.3 + .2, false).timeout   # 5.5 秒
    items.SetupItemSteal()
    #EnablePermissions()      # ← 故意不恢复权限，等玩家选
```

`ItemManager.SetupItemSteal()`：
- 把 `items_dynamicInteractionArray` 换成**双方所有道具**
- `interaction.stealing = true`
- `Counter(true)` 启动 **`timer_steal_max = 7.0`** 计时
- 超时 → `RevertItemSteal_Timeout()` 偷取取消

**偷到的道具是「当场使用」，不是放进自己格子**（用户指出的关键区别）。
所以「偷什么」等于「现在立刻用什么」——必须由我在决策点判断，
面板会显示庄家有哪些道具。

**踩过的坑**：
- **肾上腺素不恢复权限**，我的旧代码在 `use` 之后等 `can_shoot` 恢复，
  白等 14 秒超时，把 7 秒窗口耗光了 → 修法：`adrenaline` 跳过权限等待
- 肾上腺素**不能和其它 `use:` 混在一次决策里**——后面的道具要等权限，
  会把偷取窗口耗没。必须单独一步：`use:adrenaline;steal:X`

**mod 命令**：`steal|道具名`（在 `items_dynamicInteractionArray` 里找 `!isPlayerSide` 且名字匹配的）

### 决策速度：药瓶 / 翻倍要和开枪一样快

原来的流程是「先点药瓶 → 等动画 → 才问我」，很慢。
改成**先问我 → 再点药瓶 → 再选**，决策点 0.3 秒就出来。
主循环轮询从 0.6 秒改到 0.2 秒。

### 新工具

| 工具 | 作用 |
|---|---|
| `tools/br-launch.py` | **标准启动流程**：清进程 → 启动 → **窗口归位(0,0)** → 查脚本错误 → menu_start → 起循环。一步都不能跳 |
| `tools/br-dialogue.py` | 采样屏幕对话框文字，写到 `out/br/dialogue_capture.txt`（PowerShell 控制台会乱码，必须走文件） |

**启动脚本的意义**：游戏每次启动窗口都会跑到 `(789,485)`，右下角被裁。
以前靠我记着跑 `br-screencheck.py`，现在写死在第 3 步，失败就退出。
PowerShell 执行策略禁止跑 `.ps1`，所以做成 `.py`。

### 回血上限（用户纠正）

```gdscript
# HealthCounter.gd UpdateDisplayRoutineCigarette_Player
var maxHealth = roundManager.roundArray[0].startingHealth     # 本批第 1 轮的血量
roundManager.health_player += 1
if (roundManager.health_player > maxHealth):
    roundManager.health_player = maxHealth
```
**上限是 `roundArray[0].startingHealth`（本大轮第 1 小关的血量），不是当前小关的。**
无尽模式每小关血量随机 2~4（`GenerateRandomBatches`: `randi_range(2, 4)`），
所以「满血」要先看 `start_hp` 再决定要不要吸烟/吃药。

### 决策套路（实战总结，都是用户文档里的思路）

1. **手铐 + 打庄家**：打空也不亏——他跳过回合，下一发还是我的。
   **绝对不能 手铐 + 打自己**（手铐白给）。
2. **逆转器看方向，别看死理**：
   - 空包多（如 1实2空 → 33%实）→ 逆转 = 正收益（33% → 67%）
   - 实弹多（如 3实2空 → 60%实）→ 逆转 = **负收益**（60% → 40%）
   - **1实1空这种 50/50 时，逆转是中性，别浪费**
3. **啤酒 + 电话做「确定打击」**：
   电话说第 7 发实弹 → 推出现在这发是空包 → 啤酒退掉 → 用已知实弹收人头。
4. **1 血绝不吃药片**（50% 扣 1 = 自杀）。
5. **回血前必须看 `start_hp`**，满血就留着。
6. **50/50 打庄家，空包占优才打自己**：
   - 打自己：保回合但伤害可能落在自己身上
   - 打庄家：伤害落在对方身上，但丢回合
   - 空包率 > 50% 才值得赌「保回合」
7. **手铐把「50/50 打空」变成必胜**：
   `1实1空` + 庄家 1 血 + 有手铐 → 手铐+打庄家，
   实弹直接赢，空包他也跳过回合、下一发还是实弹、再打 → **100% 赢**

### 今天新修的两个 bug

**① 签名标志不重置**
`br-run2.py` 的 `signed` 标志设成 True 后从不重置，死亡重开后在签名机前卡死
（`can_do=['signature machine button']` 但不动）。
修：`allowed('bathroom door')` 时 `signed = False`。

**② `steal` 分支的缩进**
第一次打补丁用 2 个 tab 匹配，实际是 3 个，没打上还报了「没匹配」——
**改 `.gd` 前一定要把真实片段打出来看缩进**。

### 还没验证的

- 无尽模式选 ✘（见好就收）→ 领奖结算 → 回菜单
- 连续翻倍第二次（分数应该变成 2 倍）

### 备份

`out/br/backup/normal-20261112-2318/` 是**普通模式**跑通那版（含 mod.pck + 源码 + 工具 + 还原说明）。
无尽模式的改动是在它之后加的，还没单独备份。

---

## 2026-11-13 下午：状态面板重做（六个坑）+ 无尽模式全链路验收

### 面板的六个坑（按发现的顺序）

**① `WS_EX_LAYERED` 是闪烁元凶**
做鼠标穿透时我设了 `0x20 | 0x80000`（TRANSPARENT | LAYERED）。**LAYERED 只有在需要半透明/色键时才必需**，
而分层窗口的绘制模型就是「先擦成透明再往上画」—— 双缓冲在它面前完全无效。
只留 `WS_EX_TRANSPARENT (0x20)` + 加 `WS_EX_COMPOSITED (0x02000000)` 之后才不闪。

**② 「等待对局」抽搐**
判断对局是否活着的阈值只有 2 秒：`ageS < 2.0 → live`。游戏换场景/播大动画时 `state.json` 会慢过 2 秒，
于是 `live` 反复真假跳动，面板就在「内容 ↔ 等待对局」之间闪。
修法：**迟滞 + 宽限期** —— 记 `lastLiveAt`，掉线不足 8 秒且游戏进程还在就**整帧 return**（保留上一帧，一个像素不动）。

**③ 双缓冲在 PowerShell 里是静默失败的**
`$form.DoubleBuffered = $true` 改的是 protected 属性，**赋了也没用也不报错**。
必须继承一个 C# 子类在构造函数里 `SetStyle(...)`。
而且 `Add-Type -TypeDefinition` 编译 C# 时**必须 `-ReferencedAssemblies 'System.Windows.Forms','System.Drawing'`** ——
`Add-Type -AssemblyName` 只是加载程序集，不等于给编译器加引用（否则报「找不到 Forms 命名空间」）。

**④ 每帧无条件写控件 = 每帧重绘**
原来每 150ms 都写 `Text` / `Visible`，即使内容没变也会触发重绘。
改成**内容签名比对**，只有变了才 `Invalidate()`。
另外「实时 0.1s」这种每 100ms 变一次的数字**不能进签名**，否则等于每帧重绘 —— 改成整秒。

**⑤ 子控件的 Transparent 背景会逼父窗体重绘**
只要有一个 `BackColor = Transparent` 的 Label 要重绘，父窗体就得重画它背后那片。
最终方案：**全自绘**（`UserPaint | AllPaintingInWmPaint | OptimizedDoubleBuffer`，重写 `OnPaintBackground` 为空），
一个子控件都不留，所有文字和立绘在**一次 Paint** 里画完。

**⑥ 圆角 Region 只在 Resize 时设，启动那次不触发**
`Add_Resize` 里设 Region，但初始尺寸不触发 Resize → 开局四个角是黑的（看着像"大黑框"）。
修法：`Add_Shown` 里也设一次。

### 面板功能定稿

- **和游戏同生共死**：游戏进程没了就**退出**（不隐藏，免得后台占资源）；由 `br-launch.py` 启动
- **启动无控制台窗口**：`subprocess.CREATE_NO_WINDOW`
- **单实例**：只按 `hud.pid` 里记的 PID 判断（按命令行模糊匹配会把调用它的 shell 一起杀掉，**这个坑踩了两次**）
- **想法过期 75 秒**（45 太短：庄家回合可能一两分钟）；启动时清空 think.txt
- **没想法时显示**「您的 agent 正在 deepsleeping」
- **胜率是面板级的**：开面板时记基准，死了不重置；检测到 mod 计数归零就重取基准
- **立绘** `out/br/char-200.png`：四角泛洪去白底（只去和边缘连通的白，保住衣服和气泡内部的白）→
  `MinFilter` 向内收 1px 去白边 → 轻微羽化 → 贴右下角，跟随面板高度
- 布局：`恶魔轮盘 实时Xs` / `第N关·回合N·N胜N负·N%`（13pt 黄色）/ 血量（庄家：我）/ 弹药情况（几空几实·第几发·剩余几发）/
  我的道具 / 庄家的道具 / **轮到我（红色单独一行）** / 想法

### 道具清单的重复统计（mod 侧）

```gdscript
for it in im.itemArray_player: ip.append(str(it))     # ①
for it in im.itemArray_dealer: idl.append(str(it))
for br in im.items_dynamicInteractionArray:            # ② 又来一遍 → 数量翻倍
    if bool(br.isPlayerSide): ip.append(nm) else: idl.append(nm)
```

**两个症状同源**：数量翻倍；刚抓到手的那件 `isPlayerSide` 还没置位，被算成庄家的。
**正确做法是两边用不同来源**：
- 我的：从 `items_dynamicInteractionArray` 取 `isPlayerSide == true`（`itemArray_player` 可能是空的！）
- 庄家的：只信 `itemArray_dealer`

**第一次修过头了** —— 把动态数组整段删掉，结果 `items_player` 直接变空。教训：改列表来源前先确认那个字段真的有人填。

### 决策流程的两个坑

**① `wait-decision` 会返回「已经回答过」的旧决策点**
循环还没清掉 `need_decision.txt` 时它就把旧内容返回了（实测 0.2 秒返回）。
修法：返回时写 `_last_seen_need.txt` 时间戳，比它旧的 `need_decision.txt` 一律不认。

**② 控制台乱码害我读错道具**
PowerShell 把中文输出成 `�������`，我靠上下文猜道具名，猜错过两次（"有放大镜"实际没有、"有肾上腺素"实际是手铐），
**等于凭空用了个没有的道具**（循环挡住了，但判断已经错了）。
**改用 `read` 工具读 `need_decision.txt`** —— 它按 UTF-8 读，不会乱码。

### 无尽模式验收结论

✔ 加倍 / ✘ 收手 / 死亡回第 1 关 / 偷取 / 放大镜门禁 / 5 秒结算延迟 —— 全部实测通过，**游戏侧无 bug**。

---

## 2026-11-13 15:00 前后：普通模式 3-0 通关 + 两个循环 bug（GUI 会话）

### 战果
普通模式三大关一把过：wins=3 losses=0，领到 **66920**。
14:59 签名 → 15:21 领奖箱，约 22 分钟（正常模式分数与时间无关，只记录）。

### 坑一：workspace-write 权限下游戏启动即崩（0xC0000005）
症状：`br-launch.py` 第 3 步「找不到游戏窗口」，进程已退出，**不写日志**。
查证：vanilla（不带 mod）**崩在同一偏移 0x20b18d6** → 和 mod 无关。
真因：会话在 `workspace-write` 时，**游戏子进程继承文件限制**，写不了
`%APPDATA%\Godot\app_userdata\Buckshot Roulette\logs`；抓 stderr 能看到
`ERROR: Failed to open user://logs/godot....log`。
解法：会话权限设 `danger-full-access`（手册第 0 节已写）。

### 坑二：药瓶选 ✘ 后无限追问
选完 `pill choice no` 后药瓶**仍在 can_do 里**（浴室门也可点），循环先判药瓶 → 每 3 秒重问一次，卡死。
修（`br-run2.py`）：
- `pill_answered` 标记：同一次洗手间只问一次
- 重置条件不能是「药瓶一离开 can_do」——**点它的瞬间会短暂消失**，一缺就重置等于没修（我第一次就这么错的）。
  改成 `pill_absent >= 12` 轮（约 2.4 秒连续缺席）才重置
- 选「普通」时**不点药瓶**，直接落到浴室门分支

### 坑三：决策文件写中文道具名，循环不认
手册教的是 `use:手铐;shoot:dealer`，但循环用 `items_player`（英文 `handcuffs`）比对，
于是日志出现 `跳过 手铐（场上确实没有）` → **没铐就开了枪**，庄家随后小刀锯枪反打 2 点。
修：加 `ITEM_ALIAS` / `item_en()`，`use:` 和 `steal:` 都先过一遍映射（中文/英文都收）。

### 战术笔记（实战有效的两条）
1. **1 血时的拖弹仓打法**：`放大镜`看清 → 空包就打自己（白赚）、实弹就`啤酒`退掉，
   一枪不放、一个回合都不给庄家，把弹仓走空换新仓。实测靠这个从「1血对4血、对方5把小刀」活了下来。
2. **锯子别在 50% 上赌两次**：4实3空 连开两发都是空包，锯子连白用两次；真正吃到伤害的是后面。
   锯子更适合配`手铐`（确定能再打一发）或配已知实弹。

---

## 2026-11-13 16:00 前后：签名界面 / ENTER 按钮（未完成，交接）

### 已完成

**名字可配置**
`tools/br-run2.py` 不再写死 `SIG_NAME = 'dsh'`，改成：
- 读 `out/br/player_name.txt`，没有就用默认 `dsh`
- 超过 `SIG_NAME_MAX = 12` 个字符会截断并记日志

**修掉两个循环致命 bug**
- 签名前的 `waiver` 是循环自己发的（`allowed('release form on table')` → `waiver`），这是正常流程，不是多余步骤
- 我在签名那段插入日志后留下了一行重复的 `log(... % _e)`，`_e` 在 try 外面 → **NameError → 主循环直接死**，表现为「记了签名界面但没输字母」

### 没做成：让 ENTER 有按下动画

**目标**：打完名字 → 先播 ENTER 按钮的按下动画 → 再提交。

**卡点**：`_dsh_sign_buttons` 一直是空的，日志里稳定输出 `签名机按钮: （空）`。

扫描代码（`HealthCounter.gd` 约 320 行）：
```gdscript
var sc4 = n4.get_script()
if sc4 != null and str(sc4.resource_path).get_file() == "SignatureButtonBranch.gd":
    sbs.append(n4)
```
已经放宽成「路径含 SignatureButton 或 `n4.has_method("Press")`」，**还是空**。

**下一步该查的**：
1. `while stack4.size() > 0 and g4 < 30000` —— **30000 次可能不够**，场景树大就扫不到后面的节点。先把这个上限调到 200000 试试。
2. 确认签名键节点的父节点是不是在 `get_tree().root` 可达范围内（`SignatureButtonBranch.gd` 里 `parent = get_parent()`，`intbranch = parent.get_child(1)`）。

**已知事实**（不用再查）：
- `SignatureButtonBranch.Press()` **只播动画，不输入任何东西**
- 真正提交是 `SignatureManager.Input_Enter()`
- 真正输入是 `SignatureManager.Input_Letter(alias)` → `letterArray[markerIndex].text = alias`
- `PickUpWaiver()` 会 `for letter in letterArray: letter.text = ""` —— **清空已输入的名字**，所以不能在签名后发 waiver
- 现在的字母输入走的是兜底路径（`_dsh_sign_one` 找不到按钮就 `Input_Letter`），**能用、但没有动画**

### 两个坑（今天在同一个地方栽了三次）

**① `str.replace(裸子串)` 会匹配到带缩进的行内部**
`t.replace('d["start_hp"] = 0', 'd["sign_buttons"] = ...\nd["start_hp"] = 0')`
匹配到了 `\t\td["start_hp"] = 0` 里面的子串，换行插在中间，**第二行的两个 tab 丢了** → 语法错误。
**改 .gd 一律用整行匹配**（`ln == '...'` 或 `ln.strip() == '...'`），别用裸子串。

**② `:=` 配 `[]` 其实没问题**
文件里本来就有 30 处 `var x := []` 在正常工作。今天误判成它的问题，白改了两次。
真正会炸的是缩进。

**③ 插入代码后必须检查有没有重复行**
我用「跳过 N 行」的方式撤销插入，结果留下了半截，造成 `_e` 未定义。撤代码后要 `Select-String` 确认目标行只剩一处。

### 签名 ENTER 键的按下动画（已解决）

**结论**：`sign_enter` 现在会**先播放 ENTER 键的按下动画，再提交**。

**关键结构**（这是找了半天才搞明白的）：
```
button_enter                      ← 交互分支的父节点，自身没有 Press()
├── signature button branch       ← 带 Press() 的就是它（4 个子节点之一）
└── interaction branch_enter      ← 节点名就是 "interaction branch_enter"
```

`SignatureButtonBranch.gd`：
```gdscript
func _ready():
    parent = get_parent()
    intbranch = parent.get_child(1)   # 交互分支是父节点的第 2 个子节点
```
→ 带 `Press()` 的脚本节点和交互分支是**兄弟**，都在 `button_enter` 下面。

**实现**（`HealthCounter.gd` 的 `sign_enter`）：
1. 从 `_dsh_branch_nodes`（分支扫描时收集的节点引用）里找名字含 `branch_enter` 的
2. 取它的父节点，在**父节点的子节点里**找带 `has_method("Press")` 的 → 找到 `signature button branch`
3. `prt.call("Press")` 播动画
4. `await 0.3 秒`
5. `sg2.call("Input_Enter")` 提交

**踩过的三个坑**：
- 自己从 `get_tree().root` 扫树**扫不到**签名键（只到 1801 个节点），但**分支扫描能扫到** → 必须复用 `_dsh_branch_nodes`，不能再自己扫一遍
- 一开始搜 `par_e.get_parent().get_children()`（高了一层），`has_method("Press")` 永远是 false → 应该搜 `par_e.get_children()`
- 调试时 `FileAccess.WRITE` 每次覆盖，看不到所有输出 → 要用 `READ_WRITE + seek_end()` 追加

**调试手法**：`print()` 看不到（`br-launch.py` 把游戏 stdout 丢进 DEVNULL），所以调试信息要**写文件**（`_dsh_dbg()` 写到 `out/br/sign_debug.txt`）。收尾时清掉。

### 名字可配置

`out/br/player_name.txt` 里写名字，默认 `dsh`，超过 12 字符截断。

### 本次会话只改了 HealthCounter.gd

`GlobalVariables.gd` / `ItemManager.gd` / `IntroManager.gd` **各 0 行改动** —— 游戏原本逻辑一行没动。
