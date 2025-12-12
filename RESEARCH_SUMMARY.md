# 多显示器自动化研究成果总结

## 研究背景

解决Windows桌面自动化中的多显示器坐标定位问题，特别是：
- 副屏幕负坐标点击
- 竖屏显示器支持
- 不同DPI缩放适配
- 跨屏窗口操作

## 核心发现

### 问题根源

1. **pyautogui.click()** 在负坐标时可能失效
2. **win32api.mouse_event()** 同样存在问题
3. 根本原因：这些API未正确处理虚拟桌面坐标系

### 解决方案

使用 **SendInput API + VIRTUALDESK 标志**：

```python
# 关键标志
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000  # 关键！

# 坐标转换：屏幕坐标 → 虚拟桌面绝对坐标 (0-65535)
abs_x = (screen_x - virtual_screen_left) * 65535 / virtual_screen_width
abs_y = (screen_y - virtual_screen_top) * 65535 / virtual_screen_height
```

## 测试结果

| 场景 | 窗口位置 | 测试结果 |
|------|----------|----------|
| 副屏上方 | `(-2000, -1000)` | ✅ Sculpting切换成功 |
| 副屏下方 | `(-2000, 800)` | ✅ Shading切换成功 |
| 主屏幕 | `(200, 100)` | ✅ Layout/File菜单成功 |
| 副屏中间 | `(-1680, 387)` | ✅ Animation切换成功 |
| **跨屏窗口** | `(-1303, 11)→(1314, 1670)` | ✅ 两边都能准确点击 |

## 兼容性

| 配置 | 支持状态 |
|------|----------|
| 负X坐标（左侧屏幕） | ✅ |
| 负Y坐标（上方屏幕） | ✅ |
| 竖屏显示器（3840高度） | ✅ |
| DPI 1.5x缩放 | ✅ |
| 窗口跨越两个屏幕 | ✅ |
| 窗口移动后重新识别 | ✅ |

## 核心代码

### click_utils.py

```python
from v2_simplified.click_utils import click, activate_and_click

# 支持任意屏幕坐标（包括负数）
click(-1802, -79)

# 激活窗口后点击
activate_and_click(hwnd, x, y)

# 双击/右键
double_click(x, y)
right_click(x, y)
```

### 使用流程

```python
import json
from v2_simplified.click_utils import activate_and_click

# 1. 读取识别结果
d = json.load(open('v2_simplified/output/latest_vision.json', encoding='utf-8'))

# 2. 获取元素坐标
coord = d['index']['by_label']['Modeling']

# 3. 激活窗口并点击
activate_and_click(hwnd, coord[0], coord[1])
```

## 项目结构

```
v2_simplified/
├── 核心监控
│   ├── monitor.py          # UIA监控（主要）
│   ├── vision_monitor.py   # Vision OCR监控（备用）
│   └── app_monitor.py      # 程序状态监控
│
├── 辅助工具
│   ├── click_utils.py      # 多显示器点击工具 ⭐新增
│   ├── click_helper.py     # 标签点击辅助
│   ├── smart_helper.py     # UIA/Vision智能切换
│   ├── vision_helper.py    # 视觉识别辅助
│   └── window_manager.py   # 窗口管理
│
├── 输出目录
│   └── output/
│       ├── latest.json         # UIA识别结果
│       ├── latest.png          # UIA截图
│       ├── latest_vision.json  # Vision识别结果
│       ├── latest_vision.png   # Vision截图
│       └── apps.json           # 程序状态
│
└── 文档
    ├── README.md
    ├── OPERATION_MANUAL.md
    ├── SYSTEM_PROMPT.md
    └── docs/
        ├── 快速开始.md
        ├── 操作知识库.md
        └── 铁律规则.md
```

## 启动命令

```powershell
# 启动三个监控系统
Start-Process python -ArgumentList "v2_simplified\monitor.py" -WindowStyle Hidden
Start-Process python -ArgumentList "v2_simplified\vision_monitor.py","--interval","0.5" -WindowStyle Hidden
Start-Process python -ArgumentList "v2_simplified\app_monitor.py","--daemon" -WindowStyle Hidden
```

## 技术要点

1. **DPI感知**：必须调用 `SetProcessDpiAwareness(2)` 确保坐标准确
2. **虚拟屏幕**：使用 `GetSystemMetrics(76-79)` 获取完整虚拟屏幕范围
3. **坐标转换**：屏幕坐标需要转换为0-65535范围的绝对坐标
4. **VIRTUALDESK标志**：确保SendInput覆盖所有显示器

## 总结

通过使用SendInput API配合VIRTUALDESK标志，成功实现了：
- 任意屏幕配置下的精确点击
- 负坐标完全支持
- 跨屏窗口操作
- DPI缩放自动适配

**多显示器桌面自动化问题已完全解决！**
