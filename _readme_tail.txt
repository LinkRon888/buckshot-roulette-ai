ut\br\player_name.txt
```

- **最多 6 个字符**（签名机只有 6 个格子）
- **只能字母 a-z**
- 改完**重启游戏**生效

## 想让它打无尽模式？

跟 AI 说：
```
这一把打无尽模式（嗑药），选 ✔
```

## 想换面板的立绘？

替换 `out\br\char-200.png`（建议 200px 宽、透明背景）。

---

# 六、版权 ✅

这个包**不含游戏代码**：

- ❌ 没有游戏本体
- ❌ 没有完整的 `.gd` 文件
- ✅ 只有**补丁**（我改动的差异）

你用自己的正版游戏文件打补丁得到结果 —— 这是标准做法。

**但注意**：打完补丁的 `out\br\mod.pck` 和 `out\br\patch\scripts\*.gd`
**是你自己机器上生成的**，别把那些再发给别人（那才是含游戏代码的东西）。

---

## 立绘（面板右下角那个角色）

`setup.py` 会**自动**把 `art/char-200.png` 复制到 `out/br/char-200.png`。

**如果你没跑 setup.py，或者面板右下角是空的**，手动复制一次：

```powershell
mkdir out\br -Force
copy art\char-200.png out\br\char-200.png
```

然后重启面板：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\br-hud.ps1 -Action stop
powershell -NoProfile -ExecutionPolicy Bypass -File tools\br-hud.ps1
```

**想换自己的图**：尺寸建议 200px 宽、透明背景 PNG。

---

## 界面语言（中/英）

面板支持中英双语。改 `out\br\lang.txt`：

```
zh     中文（默认）
en     English
```

**改完重启面板生效**（不用重装、不用重打包）。

想在游戏里看到英文道具名？面板会显示英文，但**决策文件里中英文都接受**，不影响 AI 工作。

---

## 面板大小可以调

面板会**自动按屏幕宽度缩放**，一般不用管。

嫌大嫌小就在 `out\br\hud_scale.txt` 里写个数字（`0.8` 变小，`1.3` 变大），范围 0.65~