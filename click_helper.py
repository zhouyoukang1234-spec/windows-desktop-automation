#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉识别点击辅助工具
解决窗口移动后坐标失效的问题

用法：
    python click_helper.py "标签名"
    python click_helper.py Add
    python click_helper.py 腾讯新闻
    
    # 作为模块导入
    from click_helper import click, get_coord
    click("Add")
    x, y = get_coord("腾讯新闻")
"""

import json
import sys
from pathlib import Path
import win32gui
import pyautogui
import ctypes

# 启用DPI感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass


def get_dpi_scale() -> float:
    """获取当前屏幕DPI缩放比例"""
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return dpi / 96.0
    except:
        return 1.0


def get_real_time_coord(label: str, verbose: bool = True) -> tuple:
    """
    获取元素的实时屏幕坐标（支持DPI缩放和窗口移动）
    
    原理：
    1. 读取识别结果中的相对坐标(bbox_relative) - 截图内物理像素
    2. 获取当前窗口的实时位置（逻辑坐标）
    3. 将逻辑坐标转换为物理像素坐标
    4. 计算实时绝对坐标 = 当前窗口物理位置 + 相对坐标
    """
    json_path = Path(__file__).parent / 'output' / 'latest_vision.json'
    
    if not json_path.exists():
        print(f"❌ 找不到识别结果: {json_path}")
        return None
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 查找目标元素
    target = None
    for elem in data['elements']:
        if elem['label'] == label or label.lower() in elem['label'].lower():
            target = elem
            break
    
    if not target:
        print(f"❌ 找不到元素: {label}")
        print(f"可用标签: {[e['label'] for e in data['elements'] if 'Icon_' not in e['label']][:10]}")
        return None
    
    # 获取相对坐标（截图内的物理像素坐标）
    bbox_rel = target.get('bbox_relative') or target.get('bbox')
    if not bbox_rel:
        print(f"❌ 元素没有相对坐标")
        return None
    
    # 获取识别时的窗口位置（逻辑坐标）和DPI缩放
    old_rect = data.get('window_rect', [0, 0, 0, 0])
    saved_dpi_scale = data.get('dpi_scale', 1.0)
    window_title = data.get('window', '')
    
    # 获取当前DPI缩放
    current_dpi_scale = get_dpi_scale()
    
    # 获取当前窗口位置（逻辑坐标）
    hwnd = win32gui.FindWindow(None, window_title)
    if not hwnd:
        # 尝试模糊匹配
        def find_window(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if window_title in title or title in window_title:
                    results.append(hwnd)
        results = []
        win32gui.EnumWindows(find_window, results)
        hwnd = results[0] if results else 0
    
    if not hwnd:
        if verbose:
            print(f"⚠️ 找不到窗口: {window_title}，使用识别时的坐标")
        # 使用识别时的坐标（已经是物理像素）
        center = target['center']
        return (center[0], center[1])
    
    # 获取当前窗口坐标
    # 注意：启用DPI感知后，GetWindowRect已经返回物理像素坐标
    current_rect = win32gui.GetWindowRect(hwnd)
    
    # 计算相对坐标的中心点
    rel_cx = (bbox_rel[0] + bbox_rel[2]) // 2
    rel_cy = (bbox_rel[1] + bbox_rel[3]) // 2
    
    # 最终坐标 = 当前窗口位置 + 相对坐标
    real_x = current_rect[0] + rel_cx
    real_y = current_rect[1] + rel_cy
    
    if verbose:
        print(f"📍 {label}")
        print(f"   DPI缩放: {current_dpi_scale*100:.0f}%")
        print(f"   当前窗口坐标: {current_rect[:2]}")
        print(f"   元素相对坐标: ({rel_cx}, {rel_cy})")
        print(f"   最终点击坐标: ({real_x}, {real_y})")
    
    return (real_x, real_y)


def get_coord(label: str) -> tuple:
    """获取坐标（静默模式）"""
    return get_real_time_coord(label, verbose=False)


def click(label: str):
    """点击指定标签的元素"""
    coord = get_real_time_coord(label)
    if coord:
        pyautogui.click(coord[0], coord[1])
        print(f"✅ 已点击 ({coord[0]}, {coord[1]})")
        return True
    return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python click_helper.py <标签名>")
        print("示例: python click_helper.py Add")
        sys.exit(1)
    
    label = sys.argv[1]
    click(label)
