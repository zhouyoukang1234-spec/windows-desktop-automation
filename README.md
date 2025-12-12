# 🎯 V2 简化版实时监控系统

## 设计理念

**系统只做数据采集，AI做所有决策。**

基于实际操作经验的核心发现：
1. 复杂的"智能处理"反而增加延迟
2. AI本身就能理解和决策
3. 系统应该尽可能简单、快速

---

## 核心特点

| 特点 | 说明 |
|------|------|
| **极简设计** | 只做UIA扫描+截图，无额外处理 |
| **持续更新** | 0.5秒固定间隔，不做变化检测 |
| **索引输出** | JSON带by_name索引，AI直接读取 |
| **异步写入** | 文件写入不阻塞扫描 |
| **App缓存** | 复用Application对象减少开销 |

---

## 文件结构

```
v2_simplified/
├── 核心监控
│   ├── monitor.py          # UIA监控系统
│   ├── vision_monitor.py   # Vision OCR监控
│   └── app_monitor.py      # 程序状态监控
│
├── 辅助工具
│   ├── click_utils.py      # 多显示器点击工具 ⭐
│   ├── click_helper.py     # 标签点击辅助
│   ├── smart_helper.py     # UIA/Vision智能切换
│   ├── vision_helper.py    # 视觉识别辅助
│   └── window_manager.py   # 窗口管理
│
├── output/
│   ├── latest.json         # UIA识别结果
│   ├── latest.png          # UIA截图
│   ├── latest_vision.json  # Vision识别结果
│   ├── latest_vision.png   # Vision截图
│   └── apps.json           # 程序状态
│
├── docs/
│   ├── 快速开始.md
│   ├── 铁律规则.md
│   └── 操作知识库.md
│
├── OPERATION_MANUAL.md     # 完整操作手册
├── RESEARCH_SUMMARY.md     # 研究成果总结
└── README.md
```

---

## 双系统架构

**双系统架构**：UIA + 视觉识别，智能互补

---

## 核心文件

| 文件 | 功能 |
|------|------|
| `monitor.py` | UIA监控系统（有UIA支持的应用） |
| `vision_monitor.py` | 视觉识别系统（无UIA支持的应用） |
| `app_monitor.py` | 程序状态监控 |
| `click_utils.py` | **多显示器点击工具** ⭐ |
| `click_helper.py` | 标签点击辅助 |
| `smart_helper.py` | UIA/Vision智能切换 |

## 多显示器支持 ⭐

支持任意屏幕配置的精确点击：

```python
from v2_simplified.click_utils import click, activate_and_click

# 支持负坐标（副屏幕）
click(-1802, -79)

# 激活窗口后点击
activate_and_click(hwnd, x, y)
```

| 场景 | 支持状态 |
|------|----------|
| 负X坐标（左侧屏幕） | ✅ |
| 负Y坐标（上方屏幕） | ✅ |
| 竖屏显示器 | ✅ |
| DPI缩放 | ✅ |
| 跨屏窗口 | ✅ |

## 输出文件（4个）

| 文件 | 系统 | 用途 |
|------|------|------|
| `output/latest.json` | UIA | 控件数据 |
| `output/latest.png` | UIA | 截图 |
| `output/latest_vision.json` | Vision | 识别数据+图标索引 |
| `output/latest_vision.png` | Vision | 带标注截图 |

---

## 快速启动

```bash
# 同时启动两个系统
python monitor.py &
python vision_monitor.py --interval 0.5 &
```

---

## 使用逻辑

```python
import json

# 1. 先查UIA数据
uia = json.load(open('output/latest.json'))
if len(uia.get('controls', [])) >= 5:
    # UIA有效，用UIA
    elements = uia['controls']
else:
    # UIA无效，用Vision
    vision = json.load(open('output/latest_vision.json'))
    elements = vision['elements']
    icons = vision['icon_index']  # 图标编号坐标
```

---

## 应用支持

| 应用 | UIA | Vision | 推荐 |
|------|-----|--------|------|
| FreeCAD | ✅ 161元素 | ✅ | UIA |
| Blender | ❌ 5元素 | ✅ 160+64 | Vision |
| 微信 | ✅ | ✅ | UIA |
| 浏览器 | ✅ | ✅ | UIA |

---

## 视觉系统特性

- **青色数字编号**：高对比度，各种背景清晰
- **ID稳定性**：位置匹配保持编号
- **强制刷新**：`force_refresh.py` 触发重新识别

### 铁律（必须遵守）
1. **坐标从JSON获取** - 不要猜测
2. **中文用剪贴板** - pyperclip.copy() + Ctrl+V
3. **命令写单行** - 分号分隔

### 标准流程
```
grep/read获取坐标 → run_command点击 → 等待0.5秒 → 验证结果
```

---

## 与原系统对比

| 方面 | 原系统 | V2简化版 |
|------|--------|----------|
| 变化检测 | 50ms轮询 | 无 |
| 增量识别 | Tree Diff | 无 |
| 代码量 | 600行 | 300行 |
| 复杂度 | 高 | 低 |
| 维护性 | 困难 | 简单 |

---

## 文档导航

- 📖 [快速开始](docs/快速开始.md) - 5分钟上手
- 🔒 [铁律规则](docs/铁律规则.md) - 必须遵守的规则
- 📚 [操作知识库](docs/操作知识库.md) - 各软件操作经验
