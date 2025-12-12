#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多显示器点击工具
================
支持任意屏幕配置（多显示器、负坐标、竖屏、横屏、不同DPI）的精确点击

核心原理：
- 使用SendInput API的VIRTUALDESK标志
- 自动获取虚拟屏幕范围并转换坐标
- 支持负坐标（第二屏幕在左侧或上方）
"""

import ctypes
from ctypes import wintypes
import time

# 启用DPI感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))
    ]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('mi', MOUSEINPUT)]


# 鼠标事件标志
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000


def get_virtual_screen_info():
    """获取虚拟屏幕信息（所有显示器组成的总区域）"""
    sm_x = ctypes.windll.user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    sm_y = ctypes.windll.user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
    sm_w = ctypes.windll.user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    sm_h = ctypes.windll.user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
    return {
        'x': sm_x,
        'y': sm_y,
        'width': sm_w,
        'height': sm_h,
        'right': sm_x + sm_w,
        'bottom': sm_y + sm_h
    }


def screen_to_absolute(x, y):
    """
    将屏幕坐标转换为SendInput的绝对坐标（0-65535范围）
    
    Args:
        x: 屏幕X坐标（可以是负数）
        y: 屏幕Y坐标（可以是负数）
    
    Returns:
        (abs_x, abs_y): 转换后的绝对坐标
    """
    vs = get_virtual_screen_info()
    abs_x = int((x - vs['x']) * 65535 / vs['width'])
    abs_y = int((y - vs['y']) * 65535 / vs['height'])
    return abs_x, abs_y


def _send_input(flags, x=0, y=0):
    """发送鼠标输入事件"""
    extra = ctypes.pointer(ctypes.c_ulong(0))
    mi = MOUSEINPUT(x, y, 0, flags, 0, extra)
    inp = INPUT(0, mi)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def move_to(x, y):
    """
    移动鼠标到指定位置（支持负坐标）
    
    使用SetCursorPos，比SendInput更可靠，支持负坐标。
    
    Args:
        x: 屏幕X坐标（支持负数）
        y: 屏幕Y坐标（支持负数）
    """
    # SetCursorPos直接支持负坐标，无需转换，更精确
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def click(x, y, button='left', clicks=1, interval=0.1):
    """
    在指定位置点击（支持负坐标，多显示器）
    
    Args:
        x: 屏幕X坐标（支持负数）
        y: 屏幕Y坐标（支持负数）
        button: 鼠标按钮 ('left', 'right', 'middle')
        clicks: 点击次数
        interval: 多次点击的间隔（秒）
    """
    # 移动到目标位置
    move_to(x, y)
    time.sleep(0.05)
    
    # 确定按钮事件
    if button == 'left':
        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP
    elif button == 'right':
        down_flag = MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP
    elif button == 'middle':
        down_flag = MOUSEEVENTF_MIDDLEDOWN
        up_flag = MOUSEEVENTF_MIDDLEUP
    else:
        down_flag = MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_LEFTUP
    
    # 执行点击
    for i in range(clicks):
        _send_input(down_flag)
        time.sleep(0.02)
        _send_input(up_flag)
        if i < clicks - 1:
            time.sleep(interval)


def double_click(x, y, button='left'):
    """双击"""
    click(x, y, button=button, clicks=2, interval=0.1)


def right_click(x, y):
    """右键点击"""
    click(x, y, button='right')


def activate_window(hwnd):
    """
    可靠地激活窗口（绕过Windows前台窗口限制）
    
    Windows限制非前台进程调用SetForegroundWindow，
    使用Alt键技巧可以绕过此限制。
    
    Args:
        hwnd: 窗口句柄
    Returns:
        bool: 是否成功激活
    """
    user32 = ctypes.windll.user32
    
    # 1. 如果窗口最小化，先恢复
    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.1)
    
    # 2. 使用Alt键技巧绕过前台窗口限制
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    VK_MENU = 0x12  # Alt键
    
    # 按下Alt
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
    # 激活窗口
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    # 释放Alt
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
    
    time.sleep(0.1)
    return user32.GetForegroundWindow() == hwnd


def activate_and_click(hwnd, x, y, button='left', delay=0.3):
    """
    激活窗口并点击
    
    Args:
        hwnd: 窗口句柄
        x: 屏幕X坐标
        y: 屏幕Y坐标
        button: 鼠标按钮
        delay: 激活后等待时间
    """
    activate_window(hwnd)
    time.sleep(delay)
    click(x, y, button=button)


def click_element(element, hwnd=None):
    """
    点击Vision识别的元素
    
    Args:
        element: 包含'center'键的字典，或者直接是[x, y]坐标
        hwnd: 可选，窗口句柄（会先激活窗口）
    """
    if isinstance(element, dict):
        x, y = element.get('center', element.get('center_screen', [0, 0]))
    else:
        x, y = element
    
    if hwnd:
        activate_and_click(hwnd, x, y)
    else:
        click(x, y)


if __name__ == '__main__':
    # 测试
    import json
    
    print("=== 多显示器点击工具测试 ===")
    
    vs = get_virtual_screen_info()
    print(f"虚拟屏幕: origin=({vs['x']}, {vs['y']}), size={vs['width']}x{vs['height']}")
    
    # 测试坐标转换
    test_coords = [(0, 0), (-1000, -500), (1000, 500)]
    for x, y in test_coords:
        abs_x, abs_y = screen_to_absolute(x, y)
        print(f"  ({x}, {y}) -> absolute ({abs_x}, {abs_y})")
    
    print("\n使用方法:")
    print("  from click_utils import click, activate_and_click")
    print("  click(-1802, -79)  # 点击负坐标位置")
    print("  activate_and_click(hwnd, x, y)  # 激活窗口后点击")
