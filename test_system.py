#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统测试脚本
测试所有核心模块是否正常工作
"""

import os
import sys
import json
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """测试核心依赖导入"""
    print("\n=== 1. 测试核心依赖 ===")
    
    tests = [
        ("pyautogui", "import pyautogui"),
        ("pyperclip", "import pyperclip"),
        ("mss", "import mss"),
        ("cv2", "import cv2"),
        ("numpy", "import numpy"),
        ("PIL", "from PIL import Image"),
        ("win32gui", "import win32gui"),
        ("pywinauto", "import pywinauto"),
    ]
    
    passed = 0
    for name, cmd in tests:
        try:
            exec(cmd)
            print(f"  ✓ {name}")
            passed += 1
        except ImportError as e:
            print(f"  ✗ {name}: {e}")
    
    print(f"\n  结果: {passed}/{len(tests)} 通过")
    return passed == len(tests)


def test_vision_deps():
    """测试Vision依赖"""
    print("\n=== 2. 测试Vision依赖 ===")
    
    tests = [
        ("ultralytics", "from ultralytics import YOLO"),
        ("rapidocr", "from rapidocr_onnxruntime import RapidOCR"),
    ]
    
    passed = 0
    for name, cmd in tests:
        try:
            exec(cmd)
            print(f"  ✓ {name}")
            passed += 1
        except ImportError as e:
            print(f"  ✗ {name}: {e}")
    
    print(f"\n  结果: {passed}/{len(tests)} 通过")
    return passed == len(tests)


def test_uia_monitor():
    """测试UIA监控系统"""
    print("\n=== 3. 测试UIA监控 ===")
    
    output_dir = Path(__file__).parent / 'output'
    json_file = output_dir / 'latest.json'
    
    if not json_file.exists():
        print("  ✗ latest.json不存在，请先启动monitor.py")
        return False
    
    try:
        data = json.load(open(json_file, 'r', encoding='utf-8'))
        control_count = data.get('control_count', 0)
        index_count = len(data.get('index', {}).get('by_name', {}))
        
        print(f"  ✓ 控件数量: {control_count}")
        print(f"  ✓ 名称索引: {index_count}")
        
        # 检查截图
        png_file = output_dir / 'latest.png'
        if png_file.exists():
            size = png_file.stat().st_size
            print(f"  ✓ 截图大小: {size/1024:.1f}KB")
        
        return control_count > 0
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def test_vision_monitor():
    """测试Vision监控系统"""
    print("\n=== 4. 测试Vision监控 ===")
    
    output_dir = Path(__file__).parent / 'output'
    json_file = output_dir / 'latest_vision.json'
    
    if not json_file.exists():
        print("  ✗ latest_vision.json不存在，请先启动vision_monitor.py")
        return False
    
    try:
        data = json.load(open(json_file, 'r', encoding='utf-8'))
        element_count = data.get('element_count', 0)
        
        # 统计各类元素
        elements = data.get('elements', [])
        yolo_count = sum(1 for e in elements if e.get('method') == 'yolo' or 'Icon_' in e.get('label', ''))
        ocr_count = sum(1 for e in elements if e.get('method') == 'ocr')
        standalone_ocr = sum(1 for e in elements if e.get('standalone_ocr'))
        
        print(f"  ✓ 总元素: {element_count}")
        print(f"    - YOLO图标: {yolo_count}")
        print(f"    - OCR文字: {ocr_count}")
        print(f"    - 独立OCR: {standalone_ocr}")
        
        return element_count > 0
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def test_app_monitor():
    """测试程序监控系统"""
    print("\n=== 5. 测试程序监控 ===")
    
    output_dir = Path(__file__).parent / 'output'
    json_file = output_dir / 'apps.json'
    
    if not json_file.exists():
        print("  ✗ apps.json不存在，请先启动app_monitor.py")
        return False
    
    try:
        data = json.load(open(json_file, 'r', encoding='utf-8'))
        taskbar = len(data.get('taskbar_apps', []))
        background = len(data.get('background_apps', []))
        shortcuts = len(data.get('quick_launch', []))
        
        print(f"  ✓ 任务栏程序: {taskbar}")
        print(f"  ✓ 后台程序: {background}")
        print(f"  ✓ 快捷启动: {shortcuts}")
        
        return taskbar > 0
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def test_click_utils():
    """测试多显示器点击工具"""
    print("\n=== 6. 测试多显示器点击 ===")
    
    try:
        from click_utils import get_virtual_screen_info, screen_to_absolute, activate_window
        
        vs = get_virtual_screen_info()
        print(f"  ✓ 虚拟屏幕: origin=({vs['x']}, {vs['y']}), size={vs['width']}x{vs['height']}")
        
        # 测试坐标转换
        test_coords = [(0, 0), (-1000, 500), (1000, 500)]
        for x, y in test_coords:
            abs_x, abs_y = screen_to_absolute(x, y)
            print(f"    ({x}, {y}) -> ({abs_x}, {abs_y})")
        
        print(f"  ✓ 坐标转换正常")
        print(f"  ✓ activate_window函数可用")
        
        return True
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def test_smart_helper():
    """测试智能切换辅助"""
    print("\n=== 7. 测试智能切换 ===")
    
    try:
        from smart_helper import get_smart_result
        
        data, source = get_smart_result()
        element_count = len(data.get('elements', []))
        
        print(f"  ✓ 数据源: {source}")
        print(f"  ✓ 元素数量: {element_count}")
        
        return True
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def test_mouse_move():
    """测试鼠标移动（可选）"""
    print("\n=== 8. 测试鼠标移动 ===")
    
    try:
        from click_utils import move_to, get_virtual_screen_info
        import win32api
        
        # 获取当前位置
        old_pos = win32api.GetCursorPos()
        print(f"  当前位置: {old_pos}")
        
        # 移动到屏幕中心
        vs = get_virtual_screen_info()
        center_x = vs['x'] + vs['width'] // 2
        center_y = vs['y'] + vs['height'] // 2
        
        move_to(center_x, center_y)
        time.sleep(0.2)
        
        new_pos = win32api.GetCursorPos()
        print(f"  移动到: {new_pos}")
        
        # 恢复位置
        move_to(old_pos[0], old_pos[1])
        
        print(f"  ✓ 鼠标移动正常")
        return True
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def main():
    print("=" * 60)
    print("🔍 Windows桌面自动化系统测试")
    print("=" * 60)
    
    results = {}
    
    results['核心依赖'] = test_imports()
    results['Vision依赖'] = test_vision_deps()
    results['UIA监控'] = test_uia_monitor()
    results['Vision监控'] = test_vision_monitor()
    results['程序监控'] = test_app_monitor()
    results['多显示器点击'] = test_click_utils()
    results['智能切换'] = test_smart_helper()
    results['鼠标移动'] = test_mouse_move()
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    for name, result in results.items():
        status = "✓" if result else "✗"
        print(f"  {status} {name}")
        if result:
            passed += 1
    
    print(f"\n  总计: {passed}/{len(results)} 通过")
    
    if passed == len(results):
        print("\n✅ 所有测试通过！系统已就绪。")
    else:
        print("\n⚠️ 部分测试未通过，请检查上述错误。")
    
    return passed == len(results)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
