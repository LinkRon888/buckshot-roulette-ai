# 恶魔轮盘浮窗 · 完全自绘版（修闪烁）
#
# 为什么全自绘：用 Label 子控件时，只要有一个带 Transparent 背景的标签需要重绘，
# 父窗体就得重画它背后的区域，叠上 Opacity（分层窗口）就会闪。改成只有一次 Paint
# 之后，整块内容在一帧里画完，不存在"先擦掉再画"的中间态。
#
# 其它：想法 45 秒过期 / 胜率面板级累计 / 立绘贴右下角 / 游戏退出就退出
#
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File tools\br-hud.ps1 [-Action run|stop|clear]
param(
  [ValidateSet('run','stop','clear')][string]$Action = 'run',
  [int]$Width = 0,
  [int]$X = 10,
  [int]$Y = 10,
  [int]$ThinkMaxAge = 75,
  [int]$ImgW = 0
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$brDir = Join-Path $root 'out\br'
$stateFile = Join-Path $brDir 'state.json'
$thinkFile = Join-Path $brDir 'think.txt'
$charFile  = Join-Path $brDir 'char-200.png'
$pidFile   = Join-Path $brDir 'hud.pid'
$utf8 = New-Object System.Text.UTF8Encoding($false)

if ($Action -eq 'stop') {
  if (Test-Path $pidFile) {
    $p = Get-Process -Id ([int](Get-Content $pidFile -Raw)) -ErrorAction SilentlyContinue
    if ($p) { Stop-Process -Id $p.Id -Force }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  }
  Write-Output 'hud stopped'
  exit 0
}
if ($Action -eq 'run' -and (Test-Path $pidFile)) {
  $oldPid = 0
  try { $oldPid = [int](Get-Content $pidFile -Raw) } catch { $oldPid = 0 }
  if ($oldPid -gt 0) {
    $op = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $oldPid) -ErrorAction SilentlyContinue
    if ($op -and $op.CommandLine -like '*br-hud.ps1*') { Write-Output 'already running'; exit 0 }
  }
}
try { if (Test-Path $thinkFile) { [System.IO.File]::WriteAllText($thinkFile, '', $utf8) } } catch { }
if ($Action -eq 'clear') { Write-Output 'cleared'; exit 0 }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# 自绘 + 双缓冲 + 圆角窗体的 C# 子类
$cs0 = @'
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

public class HudForm4 : Form {
  public HudForm4() {
    SetStyle(ControlStyles.UserPaint |
             ControlStyles.AllPaintingInWmPaint |
             ControlStyles.OptimizedDoubleBuffer |
             ControlStyles.ResizeRedraw, true);
    UpdateStyles();
  }
  protected override void OnPaintBackground(PaintEventArgs e) { }
  protected override void WndProc(ref Message m) {
    if (m.Msg == 0x0084) { m.Result = (IntPtr)(-1); return; }
    base.WndProc(ref m);
  }
  // WS_EX_COMPOSITED：让系统在窗口层做合成，彻底消掉"擦掉再画"的中间态
  protected override CreateParams CreateParams {
    get {
      CreateParams cp = base.CreateParams;
      cp.ExStyle |= 0x02000000;
      return cp;
    }
  }
}
public class HudDpi7 { [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
if (-not ('HudForm4' -as [type])) {
  Add-Type -TypeDefinition $cs0 -ReferencedAssemblies 'System.Windows.Forms','System.Drawing'
}
try { [void][HudDpi7]::SetProcessDPIAware() } catch { }

# ---------------- 配色 ----------------
# ==================== 多语言 ====================
# 语言从 out/br/lang.txt 读（zh / en），默认 zh。
# 想加第三种语言：在 $L 里加一个键（比如 de = @{...}），补全所有字段就行。
function Get-Lang {
  try {
    $f = Join-Path $brDir 'lang.txt'
    if (Test-Path $f) {
      $v = ([System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)).Trim().ToLower()
      if ($L.ContainsKey($v)) { return $v }
    }
  } catch { }
  return 'zh'
}

$L = @{
  zh = @{
    title='恶魔轮盘'; live='实时'; stage='第{0}关'; round='第{0}回合'
    endless='无尽 第{0}大轮 · 第{1}小关'; winrate='{0}胜{1}负 · 胜率：{2}%'; winrateNA='0胜0负 · 胜率：—'
    hp='血量（庄家：我）'; hpCap='满血为'; ammo='弹药情况'; ammoFmt='{0}空{1}实 · 第{2}发 · 剩余{3}发'
    magSee='放大镜看到：下一发是{0}'; liveShell='实弹'; blankShell='空包'
    myItems='我的道具'; dealerItems='庄家的道具'; none='无'
    itemCountFmt='{0}×{1}'
    turnMine='轮到我'; dealerCuffed='庄被铐'; meCuffed='我被铐'; sawed='已锯枪'
    think='想法'; secondsAgo='秒前'; noThink='您的 agent 正在 deepsleeping'
    fighting='对战中'; idle='待机'; waiting='等待对局…'; noGame='游戏未启动'
    items=@{ beer='啤酒'; cigarettes='香烟'; handsaw='小刀'; handcuffs='手铐';
             'magnifying glass'='放大镜'; 'expired medicine'='药片';
             'burner phone'='电话'; adrenaline='肾上腺素'; inverter='逆转器' }
  }
  en = @{
    title='Buckshot Roulette'; live='Live'; stage='Stage {0}'; round='Round {0}'
    endless='Endless R{0} · Stage {1}'; winrate='{0}W {1}L · {2}%'; winrateNA='0W 0L · —'
    hp='HP (dealer : me)'; hpCap='max'; ammo='Shells'; ammoFmt='{0} blank / {1} live · #{2} · {3} left'
    magSee='Magnifier: next is {0}'; liveShell='LIVE'; blankShell='BLANK'
    myItems='My items'; dealerItems='Dealer items'; none='none'
    itemCountFmt='{0} x{1}'
    turnMine='My turn'; dealerCuffed='Dealer cuffed'; meCuffed='I am cuffed'; sawed='Sawed'
    think='Thinking'; secondsAgo='s ago'; noThink='agent is deepsleeping'
    fighting='In game'; idle='Idle'; waiting='Waiting for match…'; noGame='Game not running'
    items=@{ beer='Beer'; cigarettes='Cigarettes'; handsaw='Handsaw'; handcuffs='Handcuffs';
             'magnifying glass'='Magnifier'; 'expired medicine'='Pills';
             'burner phone'='Phone'; adrenaline='Adrenaline'; inverter='Inverter' }
  }
}
$LANGSET = Get-Lang
$T = $L[$LANGSET]

# 道具名（按语言取，取不到就原样）
function ItemName($raw) {
  $k = [string]$raw
  if ($T.items.ContainsKey($k)) { return $T.items[$k] }
  return $k
}

# ==================== 自动缩放 ====================
# 按屏幕宽度自动决定面板尺寸和字号。基准是 2560 宽（scale=1.0）。
# 想手动覆盖：在 out/br/hud_scale.txt 里写一个数字（如 1.2），或传 -Width。
$script:scale = 1.0
try {
  $ovr = Join-Path $brDir "hud_scale.txt"
  if (Test-Path $ovr) {
    $v = 0.0
    if ([double]::TryParse(([System.IO.File]::ReadAllText($ovr, [System.Text.Encoding]::UTF8)).Trim(), [ref]$v) -and $v -gt 0.3) {
      $script:scale = $v
    }
  } else {
    $scrW = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
    $script:scale = $scrW / 2560.0
  }
} catch { $script:scale = 1.0 }
# 夹在 0.65 ~ 1.6，防止极端分辨率下面板太小或太大
if ($script:scale -lt 0.65) { $script:scale = 0.65 }
if ($script:scale -gt 1.6)  { $script:scale = 1.6 }
function S([double]$v) { return [int][math]::Round($v * $script:scale) }

$cBg      = [System.Drawing.Color]::FromArgb(255, 34, 41, 58)
$cBorder  = [System.Drawing.Color]::FromArgb(255, 104, 138, 192)
$cTitle   = [System.Drawing.Color]::FromArgb(255, 130, 200, 255)
$cHealth  = [System.Drawing.Color]::FromArgb(255, 150, 250, 185)
$cWait    = [System.Drawing.Color]::FromArgb(255, 170, 190, 220)
$cThink   = [System.Drawing.Color]::FromArgb(255, 255, 228, 140)
$cStat    = [System.Drawing.Color]::FromArgb(255, 255, 214, 70)      # 关数/胜负：黄色
$cBadge   = [System.Drawing.Color]::FromArgb(255, 120, 180, 255)
$cDim     = [System.Drawing.Color]::FromArgb(255, 160, 175, 200)
$cWinHi   = [System.Drawing.Color]::FromArgb(255, 255, 214, 70)
$cWinLo   = [System.Drawing.Color]::FromArgb(255, 255, 150, 80)

$fTitle   = New-Object System.Drawing.Font('Microsoft YaHei UI', (S 11), [System.Drawing.FontStyle]::Bold)
$fSmall   = New-Object System.Drawing.Font('Microsoft YaHei UI', (S 8.5))
$fStat    = New-Object System.Drawing.Font('Microsoft YaHei UI', (S 13), [System.Drawing.FontStyle]::Bold)
$fHealth  = New-Object System.Drawing.Font('Microsoft YaHei UI', (S 11), [System.Drawing.FontStyle]::Bold)
$fThink   = New-Object System.Drawing.Font('Microsoft YaHei UI', (S 12))
$fFlags   = New-Object System.Drawing.Font('Microsoft YaHei UI', (S 11), [System.Drawing.FontStyle]::Bold)

function ReadTxt($path) {
  try { if (Test-Path $path) { return ([System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)).Trim() } } catch { }
  return ''
}
function FreshText($path, $maxAge) {
  try {
    if (-not (Test-Path $path)) { return @('', -1) }
    $age = ((Get-Date) - (Get-Item $path).LastWriteTime).TotalSeconds
    if ($age -gt $maxAge) { return @('', $age) }
    return @(([System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)).Trim(), $age)
  } catch { return @('', -1) }
}
$nameMap = @{
  'cigarettes'='香烟'; 'beer'='啤酒'; 'handsaw'='小刀'; 'handcuffs'='手铐';
  'magnifying glass'='放大镜'; 'expired medicine'='药片';
  'burner phone'='电话'; 'adrenaline'='肾上腺素'; 'inverter'='逆转器'
}
function FmtItems($arr) {
  if (-not $arr -or @($arr).Count -eq 0) { return $T.none }
  $g = [ordered]@{}
  foreach ($it in @($arr)) {
    $k = ItemName([string]$it)
    if ($g.Contains($k)) { $g[$k] = $g[$k] + 1 } else { $g[$k] = 1 }
  }
  $out = @()
  foreach ($k in $g.Keys) { if ($g[$k] -gt 1) { $out += ($T.itemCountFmt -f $k, $g[$k]) } else { $out += $k } }
  return ($out -join '  ')
}

# 尺寸默认值必须在创建窗体之前算好
if ($Width -le 0) { $Width = (S 880) }
if ($ImgW -le 0) { $ImgW = (S 200) }

$form = New-Object HudForm4
$form.Text = 'DSH HUD'
$form.FormBorderStyle = 'None'
$form.StartPosition = 'Manual'
$form.Location = New-Object System.Drawing.Point($X, $Y)
$form.Size = New-Object System.Drawing.Size($Width, (S 300))
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.BackColor = $cBg
$form.Opacity = 0.85   # 0.85 = 半透明；配 LAYERED 才能生效，但可能带回闪烁
# （不设 Opacity：分层窗口会引入重绘闪烁，默认就是不透明）
$img = $null
if (Test-Path $charFile) {
  try { $img = [System.Drawing.Image]::FromFile($charFile) } catch { $img = $null }
}

$left = (S 16)
$imgPad = (S 10)
$textW = $Width - $ImgW - $left - $imgPad - 10

# 渲染状态（timer 只改这个，改了才 Invalidate）
$script:S = @{
  badge = ''; clock = ''; stat = ''; statColor = $cStat
  health = ''; healthColor = $cHealth; think = ''; flags = ''
  height = 200
}
$script:lastSig = ''
$script:startedAt = Get-Date
$script:noGameTicks = 0
$script:sessionW = 0        # 面板级：我赢了几次
$script:sessionL = 0        # 面板级：我输了几次
$script:prevHpD = -1        # 上一帧庄家血量（用来检测「从 >0 变 0」）
$script:prevHpP = -1        # 上一帧我的血量
$script:lastLiveAt = [DateTime]::MinValue
$script:baseL = -1

function Get-RoundPath($w, $h, $r) {
  $p = New-Object System.Drawing.Drawing2D.GraphicsPath
  $d = $r * 2
  $p.AddArc(0, 0, $d, $d, 180, 90)
  $p.AddArc($w - $d - 1, 0, $d, $d, 270, 90)
  $p.AddArc($w - $d - 1, $h - $d - 1, $d, $d, 0, 90)
  $p.AddArc(0, $h - $d - 1, $d, $d, 90, 90)
  $p.CloseAllFigures()
  return $p
}
function Apply-Clip() {
  try {
    $pp = Get-RoundPath $form.Width $form.Height 12
    $form.Region = New-Object System.Drawing.Region($pp)
    $pp.Dispose()
  } catch { }
}

$form.Add_Paint({
  param($sender, $e)
  $g = $e.Graphics
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
  $W = $form.Width
  $H = $form.Height

  # 背景
  $bgBrush = New-Object System.Drawing.SolidBrush($cBg)
  $g.FillRectangle($bgBrush, 0, 0, $W, $H)
  $bgBrush.Dispose()

  # 边框（圆角）
  $path = Get-RoundPath $W $H 12
  $pen = New-Object System.Drawing.Pen($cBorder, 1)
  $g.DrawPath($pen, $path)
  $pen.Dispose(); $path.Dispose()

  $sf = [System.Drawing.StringFormat]::GenericTypographic

  # 标题 + 实时（同一行，实时是小字跟在后面）
  $tb = New-Object System.Drawing.SolidBrush($cTitle)
  $g.DrawString($T.title, $fTitle, $tb, [float]$left, [float]9, $sf)
  $titleW = $g.MeasureString($T.title, $fTitle, 1000, $sf).Width
  $sb = New-Object System.Drawing.SolidBrush($cDim)
  if ($script:S.clock) {
    $g.DrawString($script:S.clock, $fSmall, $sb, [float]($left + $titleW + 8), [float]15, $sf)
  }
  # 右上徽标
  if ($script:S.badge) {
    $bb = New-Object System.Drawing.SolidBrush($cBadge)
    $bw = $g.MeasureString($script:S.badge, $fSmall, 1000, $sf).Width
    $g.DrawString($script:S.badge, $fSmall, $bb, [float]($W - $left - $bw), [float]14, $sf)
    $bb.Dispose()
  }

  # 关数 / 回合 / 胜负（黄色大字）
  $yNow = 36
  if ($script:S.stat) {
    $stb = New-Object System.Drawing.SolidBrush($script:S.statColor)
    # 胜率随胜负数变长（17胜11负 · 胜率：61%），放不下就自动缩字号
    $statFont = $fStat
    $statW = $g.MeasureString($script:S.stat, $fStat, 10000, $sf).Width
    $statRoom = $W - $left - 24
    if ($statW -gt $statRoom -and $statW -gt 0) {
      $kk = [Math]::Max(0.55, $statRoom / $statW)
      $statFont = New-Object System.Drawing.Font($fStat.FontFamily, [float]([Math]::Max(7.0, $fStat.Size * $kk)), $fStat.Style)
    }
    $g.DrawString($script:S.stat, $statFont, $stb, [float]$left, [float]$yNow, $sf)
    if ($statFont -ne $fStat) { $statFont.Dispose() }
    $yNow += $g.MeasureString($script:S.stat, $statFont, 10000, $sf).Height + 2
    $stb.Dispose()
  }

  # 分隔线
  $lp = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(90, 104, 138, 192), 1)
  $g.DrawLine($lp, $left, [float]$yNow, ($W - $left), [float]$yNow)
  $lp.Dispose()
  $yNow += 8

  # 血量/弹/道具
  if ($script:S.health) {
    $hb = New-Object System.Drawing.SolidBrush($script:S.healthColor)
    $rect = New-Object System.Drawing.RectangleF([float]$left, [float]$yNow, [float]$textW, 400)
    $g.DrawString($script:S.health, $fHealth, $hb, $rect, $sf)
    $hH = $g.MeasureString($script:S.health, $fHealth, (New-Object System.Drawing.SizeF([float]$textW, 400)), $sf).Height
    $yNow += $hH + 8
    $hb.Dispose()
  }

  # 状态标记（轮到我 / 被铐 / 已锯枪）—— 红色，单独一行
  if ($script:S.flags) {
    $yNow += 6
    $fb = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 255, 90, 90))
    $g.DrawString($script:S.flags, $fFlags, $fb, [float]$left, [float]$yNow, $sf)
    $yNow += $g.MeasureString($script:S.flags, $fFlags, 1000, $sf).Height + 12
    $fb.Dispose()
  }

  # 想法
  if ($script:S.think) {
    $thb = New-Object System.Drawing.SolidBrush($cThink)
    $rect2 = New-Object System.Drawing.RectangleF([float]$left, [float]$yNow, [float]$textW, 600)
    $g.DrawString($script:S.think, $fThink, $thb, $rect2, $sf)
    $tH = $g.MeasureString($script:S.think, $fThink, (New-Object System.Drawing.SizeF([float]$textW, 600)), $sf).Height
    $yNow += $tH + 6
    $thb.Dispose()
  }
  $tb.Dispose(); $sb.Dispose()

  # 立绘（右下角）
  if ($img -ne $null) {
    $ih = [int]($img.Height * $ImgW / $img.Width)
    $g.DrawImage($img, ($W - $ImgW - $imgPad), ($H - $ih - 8), $ImgW, $ih)
  }
})

$form.Add_Resize({ Apply-Clip })

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 400
$timer.Add_Tick({
  # ---- 游戏进程 ----
  $gp = @(Get-Process -Name 'Buckshot*' -ErrorAction SilentlyContinue)
  if ($gp.Count -eq 0) {
    $script:noGameTicks++
    $alive = ((Get-Date) - $script:startedAt).TotalSeconds
    if ($alive -gt 20 -and $script:noGameTicks -ge 20) {
      try { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue } catch { }
      try { [System.IO.File]::WriteAllText((Join-Path $brDir "hud_exit.txt"), (Get-Date -Format "HH:mm:ss") + " ticks=" + $script:noGameTicks) } catch { }
      $form.Close(); return
    }
  } else { $script:noGameTicks = 0 }

  $newBadge = ''; $newClock = ''; $newStat = ''; $newHealth = ''; $newThink = ''
  $statColor = $cStat

  $live = $false
  if (Test-Path $stateFile) {
    $ageS = ((Get-Date) - (Get-Item $stateFile).LastWriteTime).TotalSeconds
    if ($ageS -lt 3.5) {
      try {
        $j = [System.IO.File]::ReadAllText($stateFile, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
        $live = $true
        $script:lastLiveAt = Get-Date
        $newBadge = $T.fighting
        $newClock = ($T.live + ' ' + [int]$ageS + 's')

        # 关数/回合/胜负（面板级胜率）
        # 胜败自己数：mod 的 wins/losses 在游戏重启（=死亡）时归零，
        # 用它算胜率的话「输」永远记不到，胜率虚高。
        $hpP = [int]$j.hp_player
        $hpD = [int]$j.hp_dealer
        if ($script:prevHpD -gt 0 -and $hpD -le 0 -and $hpP -gt 0) { $script:sessionW = $script:sessionW + 1 }
        if ($script:prevHpP -gt 0 -and $hpP -le 0 -and $hpD -gt 0) { $script:sessionL = $script:sessionL + 1 }
        $script:prevHpD = $hpD
        $script:prevHpP = $hpP
        $sw = [int]$script:sessionW
        $sl = [int]$script:sessionL
        $tot = $sw + $sl
        if ($tot -gt 0) {
          $rate = [int][math]::Round(100.0 * $sw / $tot)
          $stageTxt = ($T.stage -f ([int]$j.batch + 1))
          if ($j.endless) {
            $stageTxt = ($T.endless -f ([int]$j.rounds_beat + 1), ([int]$j.batch + 1))
          }
          $newStat = ($stageTxt + ' · ' + ($T.round -f ([int]$j.round + 1)) + ' · ' + ($T.winrate -f $sw, $sl, $rate))
          if ($rate -lt 50) { $statColor = $cWinLo }
        } else {
          $stageTxt2 = ($T.stage -f ([int]$j.batch + 1))
            if ($j.endless) {
              $stageTxt2 = ($T.endless -f ([int]$j.rounds_beat + 1), ([int]$j.batch + 1))
            }
            $newStat = ($stageTxt2 + ' · ' + ($T.round -f ([int]$j.round + 1)) + ' · ' + $T.winrateNA)
        }

        $nxt = ''
        if ($j.next_shell -eq 'live')      { $nxt = $T.liveShell }
        elseif ($j.next_shell -eq 'blank') { $nxt = $T.blankShell }
        # 本轮总弹数（用于算"第几发"）：left 变大就说明换新轮了
        $leftNow = [int]$j.left
        if ($leftNow -gt $script:roundTotal) { $script:roundTotal = $leftNow }
        if ($leftNow -eq 0) { $script:roundTotal = 0 }
        $shotNo = 0
        if ($script:roundTotal -gt 0) { $shotNo = $script:roundTotal - $leftNow + 1 }

        $hl = @()
        $capHp = [int]$j.start_hp
        if ($capHp -le 0) { $capHp = [Math]::Max([int]$j.hp_player, [int]$j.hp_dealer) }
        $hl += ($T.hp + '   ' + $j.hp_dealer + ' : ' + $j.hp_player + '    ' + $T.hpCap + ' ' + $capHp)
        $hl += ($T.ammo + '   ' + ($T.ammoFmt -f $j.blank, $j.live, $shotNo, $leftNow))
        if ($nxt -ne '') { $hl += ($T.magSee -f $nxt) }
        $hl += ($T.myItems + '   ' + (FmtItems $j.items_player))
        $hl += ($T.dealerItems + '   ' + (FmtItems $j.items_dealer))
        $fl = @()
        if ($j.can_shoot) { $fl += $T.turnMine }
        if ($j.dealer_cuffed) { $fl += $T.dealerCuffed }
        if ($j.player_cuffed) { $fl += $T.meCuffed }
        if ($j.sawed) { $fl += $T.sawed }
        $newFlags = ''
        if ($fl.Count -gt 0) { $newFlags = ($fl -join ' · ') }
        $newHealth = ($hl -join "`r`n")
      } catch { $live = $false }
    }
  }
  if (-not $live) {
    $staleFor = 99999.0
    if ($script:lastLiveAt -ne [DateTime]::MinValue) {
      $staleFor = ((Get-Date) - $script:lastLiveAt).TotalSeconds
    }
    if ($staleFor -lt 8.0 -and $gp.Count -gt 0) {
      # 宽限期内：游戏还在，只是这一帧没读到新状态 —— 保持上一帧的画面，什么都不做
      return
    }
    if ($gp.Count -gt 0) { $newBadge = $T.idle; $newHealth = $T.waiting; $newClock = '' }
    # 不在对局里也要显示累计胜负，否则一回菜单那一行就空了
    $sumW = [int]$script:sessionW
    $sumL = [int]$script:sessionL
    if (($sumW + $sumL) -gt 0) {
      $sumRate = [int][math]::Round(100.0 * $sumW / ($sumW + $sumL))
      $newStat = ($T.winrate -f $sumW, $sumL, $sumRate)
    } else {
      $newStat = $T.winrateNA
    }
    if ($gp.Count -eq 0) { $newHealth = $T.noGame }
  }

  $th, $thAge = FreshText $thinkFile $ThinkMaxAge
  if ($th) {
    $newThink = ($T.think + ' · ' + [int]$thAge + $T.secondsAgo) + "`r`n" + $th
  } else {
    # 没有 AI 在场（或想法已过期）时的占位，别留一块空白让人以为坏了
    $newThink = $T.think + "`r`n" + $T.noThink
  }

  # 只有内容变了才重绘（这是不闪的关键）
  $sig = "$newBadge|$newClock|$newStat|$newHealth|$newThink|$statColor|$newFlags"
  if ($sig -ne $script:lastSig) {
    $script:lastSig = $sig
    $script:S.badge = $newBadge
    $script:S.clock = $newClock
    $script:S.stat = $newStat
    $script:S.statColor = $statColor
    $script:S.health = $newHealth
    $script:S.think = $newThink
    $script:S.flags = $newFlags

    # 估高度：标题36 + 状态行 + 分隔 + 血量块 + 想法 + 立绘
    $g2 = $form.CreateGraphics()
    $sf2 = [System.Drawing.StringFormat]::GenericTypographic
    $hH = 0; $tH = 0
    if ($newHealth) { $hH = $g2.MeasureString($newHealth, $fHealth, (New-Object System.Drawing.SizeF([float]$textW, 400)), $sf2).Height }
    if ($newThink)  { $tH = $g2.MeasureString($newThink, $fThink, (New-Object System.Drawing.SizeF([float]$textW, 600)), $sf2).Height }
    $g2.Dispose()
    $statH = 0
    if ($newStat) { $statH = 26 }

    $flagH = 0
    if ($newFlags) { $flagH = 28 }
    $textBottom = 36 + $statH + 10 + $hH + 14 + $flagH + $tH + 26
    $imgH = 0
    if ($img -ne $null) { $imgH = [int]($img.Height * $ImgW / $img.Width) + 14 }
    $needH = $textBottom
    if ($imgH -gt $needH) { $needH = $imgH }
    if ($needH -lt 150) { $needH = 150 }
    if ($form.Height -ne $needH) {
      $form.Height = $needH
      Apply-Clip
    }
    $form.Invalidate()
  }
})

$cs2 = @(
  'using System;',
  'using System.Runtime.InteropServices;',
  'public class HudClick9 {',
  '  [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int idx);',
  '  [DllImport("user32.dll")] public static extern int SetWindowLong(IntPtr h, int idx, int val);',
  '  public static void Make(IntPtr h) {',
  '    int ex = GetWindowLong(h, -20);',
  '    SetWindowLong(h, -20, ex | 0x20 | 0x80000);   // LAYERED|TRANSPARENT：真正能穿透的组合（不设 Opacity 就不会闪）',
  '  }',
  '}'
) -join "`n"
if (-not ('HudClick9' -as [type])) { Add-Type -TypeDefinition $cs2 }
$form.Add_Shown({
  [HudClick9]::Make($form.Handle)
  Apply-Clip
})

$timer.Start()
Set-Content -Path $pidFile -Value $PID -NoNewline
[void]$form.ShowDialog()
try { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue } catch { }
