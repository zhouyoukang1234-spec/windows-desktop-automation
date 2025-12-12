# Windows 桌面自动化操作手册

## 目录
1. [系统概述](#1-系统概述)
2. [启动流程](#2-启动流程)
3. [数据文件说明](#3-数据文件说明)
4. [完整操作流程](#4-完整操作流程)
5. [验证方法详解](#5-验证方法详解)
6. [常见错误与解决方案](#6-常见错误与解决方案)
7. [特殊情况处理](#7-特殊情况处理)
8. [程序管理](#8-程序管理)
9. [界面操作命令](#9-界面操作命令)
10. [铁律总结](#10-铁律总结)

---

## 1. 系统概述

### 系统架构
```
┌────────────────────────────────────────────────────────────┐
│                    监控系统 (后台运行)                       │
├────────────────────────────────────────────────────────────┤
│  monitor.py        → latest.json + latest.png (UIA数据)    │
│  vision_monitor.py → latest_vision.json (OCR视觉识别)      │
│  app_monitor.py    → apps.json (程序状态)                  │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│                    AI操作流程                               │
├────────────────────────────────────────────────────────────┤
│  读取JSON → 获取坐标 → 执行操作 → 验证结果 → 下一步         │
└────────────────────────────────────────────────────────────┘
```

### 核心原则
- **UIA优先**：大多数Windows程序都支持UIA，优先使用latest.json
- **单步操作**：每次只执行一个动作，然后验证
- **必须验证**：每个操作后都要查看截图确认效果
- **坐标来源**：所有坐标必须从JSON获取，禁止猜测

---

## 2. 启动流程

### 第一步：启动监控系统

**在操作任何桌面内容之前，必须先启动监控系统：**

```powershell
# 启动UIA监控（生成latest.json和latest.png）
Start-Process python -ArgumentList "v2_simplified\monitor.py" -WindowStyle Hidden

# 启动视觉监控（生成latest_vision.json，作为备用）
Start-Process python -ArgumentList "v2_simplified\vision_monitor.py","--interval","0.5" -WindowStyle Hidden

# 启动程序监控（生成apps.json，用于程序切换）
Start-Process python -ArgumentList "v2_simplified\app_monitor.py","--daemon" -WindowStyle Hidden
```

### 第二步：验证系统初始化

验证监控系统是否完成初始化。

### 第三步：验证监控系统是否正常

```
read_file v2_simplified/output/latest.json
```

**检查要点：**
- 文件是否能正常读取？
- `control_count` 是否 >= 5？
- `timestamp` 是否是最近的时间？

### 如果JSON无法读取

**问题1：gitignore阻止**
```
# 检查.gitignore文件，确保有以下例外：
!v2_simplified/output/*.json
!v2_simplified/output/*.png
```

**问题2：监控未运行**
```powershell
# 检查python进程
Get-Process python

# 如果没有，重新启动监控系统
```

**问题3：权限问题**
```powershell
# 以管理员身份运行PowerShell
```

---

## 3. 数据文件说明

### 文件列表

| 文件 | 内容 | 更新频率 | 用途 |
|------|------|----------|------|
| `latest.json` | UIA控件数据 | 0.5秒 | **主要数据源** |
| `latest.png` | 当前截图 | 0.5秒 | **验证操作结果** |
| `latest_vision.json` | Vision OCR数据 | 0.5秒 | UIA失效时的备用 |
| `apps.json` | 运行中的程序 | 2秒 | 程序切换/启动 |

### latest.json 结构详解

```json
{
  "timestamp": "2025-12-12 01:32:08",  // 更新时间
  "window": {
    "hwnd": 4660272,                   // 窗口句柄
    "title": "FreeCAD 1.0.2",          // 窗口标题
    "rect": [-9, 0, 1630, 1378]        // 窗口位置
  },
  "control_count": 169,                // 控件总数（>=5表示UIA可用）
  "controls": [                        // 控件列表
    {
      "type": "Button",                // 控件类型
      "name": "保存",                  // 控件名称
      "center": [137, 104],            // 点击坐标（重要！）
      "rect": [100, 90, 174, 118],     // 控件边界
      "enabled": true                  // 是否可用
    }
  ],
  "index": {
    "by_name": {                       // 按名称索引（快速查找）
      "保存": [137, 104],
      "新建": [41, 104]
    }
  }
}
```

### 何时使用哪个文件

```
┌─────────────────────────────────────────────────────────┐
│  开始操作                                                │
│     ↓                                                   │
│  读取 latest.json                                       │
│     ↓                                                   │
│  control_count >= 5?                                    │
│     ├─ YES → 使用 UIA 数据 (latest.json)                │
│     └─ NO  → 使用 Vision 数据 (latest_vision.json)      │
│                                                         │
│  需要切换程序？ → 使用 apps.json                         │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 完整操作流程

### 黄金法则：一个操作 → 一次验证

**绝对不要**连续执行多个操作而不验证！

### 标准流程图

```
┌──────────────────────────────────────────────────────────────┐
│  Step 1: 读取数据                                            │
│  ─────────────────                                           │
│  read_file v2_simplified/output/latest.json                  │
│  • 确认 control_count >= 5                                   │
│  • 找到目标控件                                              │
│  • 记录坐标 [X, Y]                                           │
├──────────────────────────────────────────────────────────────┤
│  Step 2: 执行操作                                            │
│  ─────────────────                                           │
│  python -c "import pyautogui; pyautogui.click(X, Y)"         │
│  • 只执行一个操作                                            │
│  • 不要连续多次点击                                          │
├──────────────────────────────────────────────────────────────┤
│  Step 3: 验证结果                                            │
│  ─────────────────                                           │
│  read_file v2_simplified/output/latest.png                   │
│  • 检查界面是否变化                                          │
│  • 确认操作是否成功                                          │
├──────────────────────────────────────────────────────────────┤
│  Step 4: 决定下一步                                          │
│  ─────────────────                                           │
│  • 成功 → 继续下一个操作                                     │
│  • 失败 → 换方法（不要重复同样的操作）                       │
└──────────────────────────────────────────────────────────────┘
```

### 实际操作示例

**目标：点击FreeCAD的"创建矩形"按钮**

```
# Step 1: 读取JSON获取坐标
read_file v2_simplified/output/latest.json

# 从JSON中找到：
# "创建矩形": [493, 215]

# Step 2: 执行点击
python -c "import pyautogui; pyautogui.click(493, 215)"

# Step 3: 验证结果
read_file v2_simplified/output/latest.png

# Step 4: 检查截图
# - 如果看到矩形工具被激活 → 成功，继续下一步
# - 如果没有变化 → 换方法
```

---

## 5. 验证方法详解

### 方法1：read_file 查看截图（最常用）

```
read_file v2_simplified/output/latest.png
```

**适用场景：**
- 检查界面是否变化
- 确认菜单是否打开
- 查看是否有错误提示

### 方法2：read_file 查看JSON

```
read_file v2_simplified/output/latest.json
```

**适用场景：**
- 检查新控件是否出现
- 获取新出现元素的坐标
- 确认窗口是否切换

### 方法3：grep_search 搜索特定元素

```
grep_search "按钮名称" "v2_simplified/output/latest.json" MatchPerLine=True
```

**适用场景：**
- 快速查找特定控件
- 确认某个元素是否存在

**注意：** grep只能看到部分内容，如果找不到，要用read_file看完整JSON

### 验证时检查什么

| 检查项 | 说明 |
|--------|------|
| 界面是否变化 | 对比操作前后的截图 |
| 菜单是否打开 | 有些按钮会弹出菜单 |
| 对话框是否出现 | 有些操作会弹出对话框 |
| 焦点是否正确 | 输入框是否被选中 |
| 是否有错误提示 | 红色警告、弹窗等 |
| 控件数量变化 | control_count是否改变 |

---

## 6. 常见错误与解决方案

### 错误1：批量操作

**❌ 错误做法：**
```python
# 一条命令里执行多个操作
pyautogui.click(100,100); time.sleep(0.3); pyautogui.click(200,200)
```

**问题：** 操作太快，界面来不及响应

**✅ 正确做法：**
```python
# 第一次点击
python -c "import pyautogui; pyautogui.click(100, 100)"

# 验证
read_file v2_simplified/output/latest.png

# 确认成功后，第二次点击
python -c "import pyautogui; pyautogui.click(200, 200)"

# 再次验证
read_file v2_simplified/output/latest.png
```

---

### 错误2：猜测坐标

**❌ 错误做法：**
```
"我觉得按钮应该在(500, 300)附近"
```

**问题：** 猜测的坐标几乎肯定是错的

**✅ 正确做法：**
```
# 先读取JSON
read_file v2_simplified/output/latest.json

# 找到准确坐标
# "保存(S)": [137, 104]

# 使用准确坐标
python -c "import pyautogui; pyautogui.click(137, 104)"
```

---

### 错误3：不验证操作结果

**❌ 错误做法：**
```
点击 → 点击 → 点击 → 点击（完全不检查）
```

**问题：** 不知道哪一步出错，最后一团糟

**✅ 正确做法：**
```
点击 → 验证 → 点击 → 验证 → 点击 → 验证
```

---

### 错误4：重复失败的操作

**❌ 错误做法：**
```
# 同样的点击执行5次，希望能成功
python -c "import pyautogui; pyautogui.click(300, 200)"  # 失败
python -c "import pyautogui; pyautogui.click(300, 200)"  # 还是失败
python -c "import pyautogui; pyautogui.click(300, 200)"  # 继续失败
...
```

**✅ 正确做法：**
```
# 第一次失败后
python -c "import pyautogui; pyautogui.click(300, 200)"
read_file latest.png  # 检查：没效果

# 换方法！可能的原因：
# 1. 坐标不对 → 重新从JSON获取坐标
# 2. 需要先打开菜单 → 先点击菜单
# 3. 元素被遮挡 → 关闭遮挡的窗口
# 4. 用快捷键代替 → pyautogui.hotkey('ctrl', 's')
```

---

### 错误5：只用grep不读完整JSON

**❌ 错误做法：**
```
grep_search "保存" latest.json
# 结果只显示部分内容，看不到完整上下文
```

**✅ 正确做法：**
```
# 先用grep快速确认元素存在
grep_search "保存" latest.json

# 然后读取完整JSON获取详细信息
read_file v2_simplified/output/latest.json
```

---

### 错误6：UIA可用时用Vision

**❌ 错误做法：**
```
# latest.json有169个控件，却去用latest_vision.json
read_file latest_vision.json  # 不应该
```

**✅ 正确做法：**
```
# 先检查UIA
read_file latest.json
# 看到 control_count: 169 → UIA可用

# 使用UIA数据（更准确）
# 只有control_count < 5时才用Vision
```

---

### 错误7：gitignore阻止读取JSON

**症状：** read_file latest.json 报错或返回空

**解决方案：**
```
# 检查.gitignore
read_file .gitignore

# 添加例外
!v2_simplified/output/*.json
!v2_simplified/output/*.png
```

---

### 错误8：使用MCP点击工具

**❌ 错误做法：**
```
mcp3_click_screen(500, 300)
mcp0_click(500, 300)
```

**问题：** MCP工具的坐标系与pyautogui不一致

**✅ 正确做法：**
```python
python -c "import pyautogui; pyautogui.click(500, 300)"
```

---

## 7. 特殊情况处理

### 情况1：UIA无法识别（control_count < 5）

**场景：** 某些程序（如游戏、特殊软件）不支持UIA

**解决方案：使用Vision识别**

```
# Step 1: 检查Vision数据
read_file v2_simplified/output/latest_vision.json

# Step 2: 找到目标元素
# Vision数据结构：
# {
#   "elements": [
#     {
#       "label": "按钮文字",
#       "center": [X, Y],
#       "type": "yolo_icon" / "yolo_ocr" / "standalone_ocr"
#     }
#   ]
# }

# Step 3: 使用Vision坐标点击
python -c "import pyautogui; pyautogui.click(X, Y)"
```

---

### 情况2：找不到目标元素

**可能原因和解决方案：**

| 原因 | 解决方案 |
|------|----------|
| 元素被遮挡 | 关闭遮挡的窗口/对话框 |
| 需要滚动 | `pyautogui.scroll(-3)` 向下滚动 |
| 需要展开菜单 | 先点击父菜单 |
| 窗口最小化 | 用SetForegroundWindow激活 |
| 名称不完全匹配 | 用grep模糊搜索 |

**示例：元素在滚动区域外**
```
# 先滚动
python -c "import pyautogui; pyautogui.scroll(-3)"

# 验证更新

# 重新读取JSON
read_file v2_simplified/output/latest.json

# 找到元素后点击
python -c "import pyautogui; pyautogui.click(X, Y)"
```

---

### 情况3：菜单/下拉框操作

**步骤：**
```
# Step 1: 点击菜单按钮
python -c "import pyautogui; pyautogui.click(菜单坐标)"

# Step 2: 验证菜单是否打开
read_file v2_simplified/output/latest.png

# Step 3: 重新读取JSON获取菜单项坐标
read_file v2_simplified/output/latest.json

# Step 4: 点击菜单项
python -c "import pyautogui; pyautogui.click(菜单项坐标)"

# Step 5: 验证
read_file v2_simplified/output/latest.png
```

---

### 情况4：输入框操作

**完整流程：**
```
# Step 1: 点击输入框
python -c "import pyautogui; pyautogui.click(输入框坐标)"

# Step 2: 验证焦点
read_file v2_simplified/output/latest.png

# Step 3: 清空现有内容（如需要）
python -c "import pyautogui; pyautogui.hotkey('ctrl', 'a')"

# Step 4: 输入内容（中文必须用剪贴板）
python -c "import pyperclip; pyperclip.copy('内容'); import pyautogui; pyautogui.hotkey('ctrl', 'v')"

# Step 5: 验证输入
read_file v2_simplified/output/latest.png

# Step 6: 按Enter确认（如需要）
python -c "import pyautogui; pyautogui.press('enter')"
```

---

### 情况5：等待加载

**场景：** 点击后需要等待程序响应

```
# 点击操作
python -c "import pyautogui; pyautogui.click(X, Y)"

# 验证操作结果

# 然后验证
read_file v2_simplified/output/latest.png
```

---

## 8. 程序管理

### 查看当前运行的程序

```
read_file v2_simplified/output/apps.json
```

**apps.json 结构：**
```json
{
  "taskbar_apps": [           // 任务栏程序（可直接切换）
    {
      "name": "freecad",
      "hwnd": 4660272,        // 窗口句柄
      "title": "FreeCAD 1.0.2"
    }
  ],
  "background_apps": [        // 后台程序（托盘区）
    {
      "name": "QQ",
      "open_hotkey": "ctrl+alt+z"
    }
  ],
  "quick_launch": {           // 快速启动命令
    "chrome": {"cmd": "start chrome"},
    "notepad": {"cmd": "notepad"}
  }
}
```

### 切换到任务栏程序

```python
# 从apps.json获取hwnd
# 假设FreeCAD的hwnd是4660272

python -c "from ctypes import windll; windll.user32.SetForegroundWindow(4660272)"
```

### 激活后台程序（托盘区）

```python
# QQ
python -c "import pyautogui; pyautogui.hotkey('ctrl', 'alt', 'z')"

# 微信
python -c "import pyautogui; pyautogui.hotkey('ctrl', 'alt', 'w')"
```

### 启动新程序

```python
# 方法1: 使用quick_launch中的命令
python -c "import os; os.system('start chrome')"

# 方法2: Win+S搜索
python -c "import pyautogui; pyautogui.hotkey('win', 's')"
python -c "import pyperclip; pyperclip.copy('程序名'); import pyautogui; pyautogui.hotkey('ctrl', 'v')"
python -c "import pyautogui; pyautogui.press('enter')"
# 验证程序是否启动
```

---

## 9. 界面操作命令

### 点击操作

```python
# 单击
python -c "import pyautogui; pyautogui.click(X, Y)"

# 双击
python -c "import pyautogui; pyautogui.doubleClick(X, Y)"

# 右键
python -c "import pyautogui; pyautogui.rightClick(X, Y)"
```

### 拖拽操作

```python
# 从(X1,Y1)拖到(X2,Y2)
python -c "import pyautogui; pyautogui.moveTo(X1, Y1); pyautogui.drag(X2-X1, Y2-Y1, duration=0.5)"
```

### 滚动操作

```python
# 向下滚动
python -c "import pyautogui; pyautogui.scroll(-3)"

# 向上滚动
python -c "import pyautogui; pyautogui.scroll(3)"
```

### 文字输入

```python
# 中文（必须用剪贴板）
python -c "import pyperclip; pyperclip.copy('中文内容'); import pyautogui; pyautogui.hotkey('ctrl', 'v')"

# 英文/数字
python -c "import pyautogui; pyautogui.typewrite('english123', interval=0.05)"
```

### 按键操作

```python
# 单个按键
python -c "import pyautogui; pyautogui.press('enter')"
python -c "import pyautogui; pyautogui.press('tab')"
python -c "import pyautogui; pyautogui.press('escape')"
python -c "import pyautogui; pyautogui.press('delete')"

# 组合键
python -c "import pyautogui; pyautogui.hotkey('ctrl', 'a')"    # 全选
python -c "import pyautogui; pyautogui.hotkey('ctrl', 'c')"    # 复制
python -c "import pyautogui; pyautogui.hotkey('ctrl', 'v')"    # 粘贴
python -c "import pyautogui; pyautogui.hotkey('ctrl', 's')"    # 保存
python -c "import pyautogui; pyautogui.hotkey('ctrl', 'z')"    # 撤销
python -c "import pyautogui; pyautogui.hotkey('alt', 'f4')"    # 关闭窗口
```

---

## 10. 铁律总结

### 7条必须遵守的规则

| # | 规则 | 说明 |
|---|------|------|
| 1 | **读取完整JSON** | 用 `read_file`，不要只用 grep |
| 2 | **坐标从JSON获取** | 绝对不要猜测坐标 |
| 3 | **单步操作** | 每次只执行一个动作 |
| 4 | **每步必验证** | 操作后必须查看截图 |
| 5 | **失败换方法** | 不要重复失败的操作 |
| 6 | **中文用剪贴板** | pyperclip.copy + Ctrl+V |
| 7 | **禁用MCP点击** | 只用pyautogui |

### 操作前检查清单

- [ ] 监控系统是否运行？
- [ ] latest.json是否可读？
- [ ] control_count >= 5？
- [ ] 找到目标元素了吗？
- [ ] 获取到准确坐标了吗？
- [ ] 准备好验证了吗？

**任何一项为否，先解决再操作！**

### 禁止操作列表

| 禁止操作 | 原因 |
|----------|------|
| 猜测坐标 | 会点错位置 |
| 使用mcp3_click/mcp0_click | 坐标系不一致 |
| 一条命令多个操作 | 太快，界面来不及响应 |
| 重复失败操作超过2次 | 浪费时间，需要换方法 |
| 跳过验证 | 不知道操作是否成功 |
| 用typewrite输入中文 | 会产生乱码 |
| 假设界面状态 | 界面可能已经变化 |

---

## 附录：快速参考卡片

### 标准点击流程
```
read_file v2_simplified/output/latest.json  # 获取坐标
python -c "import pyautogui; pyautogui.click(X, Y)"  # 点击
read_file v2_simplified/output/latest.png  # 验证
```

### 多显示器点击（推荐）
```python
# 支持负坐标、跨屏窗口
from v2_simplified.click_utils import click, activate_and_click

click(-1802, -79)  # 支持任意屏幕坐标
activate_and_click(hwnd, x, y)  # 激活窗口后点击
```

### 标准输入流程
```
python -c "import pyautogui; pyautogui.click(X, Y)"  # 点击输入框
read_file v2_simplified/output/latest.png  # 验证焦点
python -c "import pyperclip; pyperclip.copy('内容'); import pyautogui; pyautogui.hotkey('ctrl', 'v')"  # 输入
read_file v2_simplified/output/latest.png  # 验证输入
```

### 程序切换流程
```
read_file v2_simplified/output/apps.json  # 获取hwnd
python -c "from ctypes import windll; windll.user32.SetForegroundWindow(HWND)"  # 切换
read_file v2_simplified/output/latest.png  # 验证
```
