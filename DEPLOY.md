# 快速部署指南

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 |
| Python | 3.8+ |
| 内存 | 8GB+ (Vision需要16GB+) |
| GPU | 可选 (Vision加速) |

## 快速部署

### 方式一：一键安装

```powershell
# 1. 克隆项目
git clone https://github.com/your-repo/ai浏览器自动化.git
cd ai浏览器自动化/v2_simplified

# 2. 运行安装脚本
powershell -ExecutionPolicy Bypass -File setup.ps1

# 3. 启动系统
.\start.ps1 -All
```

### 方式二：手动安装

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建输出目录
mkdir output

# 3. 启动监控
Start-Process python -ArgumentList "monitor.py" -WindowStyle Hidden
Start-Process python -ArgumentList "vision_monitor.py","--interval","0.5" -WindowStyle Hidden
Start-Process python -ArgumentList "app_monitor.py","--daemon" -WindowStyle Hidden
```

## 依赖说明

### 核心依赖（必需）

```
pyautogui        # 鼠标键盘自动化
pyperclip        # 剪贴板操作
mss              # 快速截图
Pillow           # 图像处理
opencv-python    # 计算机视觉
numpy            # 数组操作
pywin32          # Windows API
pywinauto        # Windows UI Automation
```

### Vision依赖（vision_monitor.py需要）

```powershell
# OmniParser V2 依赖
pip install ultralytics==8.3.70 supervision==0.18.0

# OCR文字识别
pip install rapidocr-onnxruntime onnxruntime
```

### 模型文件下载 ⚠️重要

Vision系统使用 **OmniParser V2** 模型：

**下载地址：** https://huggingface.co/microsoft/OmniParser-v2

```
weights/omniparser_v2/
├── icon_detect/
│   └── model.pt          # 40MB - YOLO图标检测 (必需)
└── icon_caption/
    └── model.safetensors # 1GB - Florence-2 (可选)
```

**下载方式：**

```powershell
# 方式1: 使用huggingface-cli
pip install huggingface_hub
huggingface-cli download microsoft/OmniParser-v2 --local-dir weights/omniparser_v2

# 方式2: 手动下载
# 访问 https://huggingface.co/microsoft/OmniParser-v2
# 下载 icon_detect/model.pt 放到对应目录
```

**文件说明：**

| 文件 | 大小 | 必需 | 说明 |
|------|------|------|------|
| `icon_detect/model.pt` | 40MB | ✅ | YOLO图标检测 |
| `icon_caption/*` | 1GB | ❌ | Florence-2 (可选) |

**快速测试（不需要模型）：**
- 只运行 `monitor.py` (UIA系统) 不需要任何模型
- `vision_monitor.py` 没有YOLO模型时只用OCR识别文字

### Florence-2 (可选)

只有启动时加 `--enable-florence` 才需要：

```powershell
# 安装PyTorch
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# 安装Florence-2依赖
pip install transformers einops==0.8.0 timm

# 启动时启用
python vision_monitor.py --enable-florence
```

## 验证安装

```powershell
# 测试核心依赖
python -c "import pyautogui, pyperclip, mss, cv2, numpy, win32gui; print('OK')"

# 运行完整测试
python test_system.py
```

## 常见问题

### Q1: 窗口切换无效
**原因：** Windows前台窗口限制
**解决：** 使用`click_utils.activate_window()`替代直接调用`SetForegroundWindow`

```python
from click_utils import activate_window
activate_window(hwnd)  # 使用Alt键技巧绕过限制
```

### Q2: 最小化窗口无法激活
**解决：** `activate_window()`会自动先恢复窗口再激活

### Q3: 网络无法连接Hugging Face
**解决：** 使用镜像站点
```powershell
$env:HF_ENDPOINT = 'https://hf-mirror.com'
```

### Q4: Vision识别结果为0个元素
**原因：** YOLO模型未下载
**解决：** 下载模型后重启vision_monitor.py

## 启动命令

```powershell
# 只启动UIA监控（大多数应用）
.\start.ps1

# 启动UIA + Vision（支持更多应用）
.\start.ps1 -Vision

# 启动全部监控
.\start.ps1 -All

# 停止所有监控
.\start.ps1 -Stop
```

## 输出文件

启动后，系统会在 `output/` 目录生成：

| 文件 | 更新频率 | 说明 |
|------|----------|------|
| `latest.json` | 0.5秒 | UIA控件数据 |
| `latest.png` | 0.5秒 | 窗口截图 |
| `latest_vision.json` | 变化时 | Vision识别数据 |
| `latest_vision.png` | 变化时 | 带标注截图 |
| `apps.json` | 2秒 | 运行程序列表 |

## 多显示器支持

系统完全支持多显示器配置：

```python
from click_utils import click, activate_and_click

# 支持负坐标（副屏幕）
click(-1802, -79)

# 激活窗口后点击
activate_and_click(hwnd, x, y)
```

支持场景：
- ✅ 左侧/上方副屏幕（负坐标）
- ✅ 竖屏显示器
- ✅ 不同DPI缩放
- ✅ 跨屏窗口

## 常见问题

### 1. pywin32安装失败

```powershell
pip install pywin32 --force-reinstall
python -c "import win32gui"  # 测试
```

### 2. mss截图黑屏

确保以管理员权限运行，或检查屏幕缩放设置。

### 3. Vision识别慢

- 检查GPU是否可用：`python -c "import torch; print(torch.cuda.is_available())"`
- 安装flash-attention加速：`pip install flash-attn`

### 4. 负坐标点击无效

使用 `click_utils.py` 而不是 `pyautogui`：

```python
from click_utils import click
click(-1000, 500)  # 正确
```

## 目录结构

```
v2_simplified/
├── monitor.py          # UIA监控
├── vision_monitor.py   # Vision监控
├── app_monitor.py      # 程序监控
├── click_utils.py      # 多显示器点击
├── requirements.txt    # 依赖列表
├── setup.ps1           # 安装脚本
├── start.ps1           # 启动脚本
└── output/             # 输出目录
```

## 联系支持

如有问题，请查看：
- `OPERATION_MANUAL.md` - 完整操作手册
- `RESEARCH_SUMMARY.md` - 技术细节
- `docs/铁律规则.md` - 必须遵守的规则
