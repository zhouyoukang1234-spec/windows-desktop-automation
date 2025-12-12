"""
智能切换辅助工具
================
两个系统同时运行，但智能选择数据源：
- 优先使用UIA数据（latest.json）
- UIA元素<阈值时，切换到视觉数据（latest_vision.json）

输出文件：
- latest.json / latest.png (UIA系统)
- latest_vision.json / latest_vision.png (视觉系统)
"""

import json
import time
import pyautogui
import pyperclip
from pathlib import Path
from typing import Optional, Tuple, List, Dict

OUTPUT_DIR = Path(__file__).parent / 'output'
UIA_THRESHOLD = 5  # UIA元素少于此数时切换到视觉


def get_uia_result() -> dict:
    """获取UIA识别结果（转换为统一格式）"""
    json_file = OUTPUT_DIR / 'latest.json'
    try:
        if json_file.exists():
            d = json.load(open(json_file, 'r', encoding='utf-8'))
            # 转换为统一格式：controls -> elements, window -> window_title
            return {
                'window_title': d.get('window', ''),
                'elements': d.get('controls', []),
                'index': d.get('index', {}),
                'raw': d
            }
    except:
        pass
    return {}


def get_vision_result() -> dict:
    """获取视觉识别结果"""
    json_file = OUTPUT_DIR / 'latest_vision.json'
    try:
        if json_file.exists():
            return json.load(open(json_file, 'r', encoding='utf-8'))
    except:
        pass
    return {}


def get_smart_result(threshold: int = UIA_THRESHOLD) -> Tuple[dict, str]:
    """智能获取数据：UIA优先，无效时用视觉
    
    Returns:
        (数据dict, 来源'uia'或'vision')
    """
    uia = get_uia_result()
    uia_count = len(uia.get('elements', []))
    
    if uia_count >= threshold:
        return uia, 'uia'
    
    # UIA无效，使用视觉
    vision = get_vision_result()
    return vision, 'vision'


def force_refresh_vision(wait_sec: float = 3.0) -> dict:
    """强制刷新视觉识别"""
    signal_file = OUTPUT_DIR / '.force_refresh'
    json_file = OUTPUT_DIR / 'latest_vision.json'
    
    old_mtime = json_file.stat().st_mtime if json_file.exists() else 0
    signal_file.write_text(str(time.time()))
    
    start = time.time()
    while time.time() - start < wait_sec:
        time.sleep(0.3)
        if json_file.exists() and json_file.stat().st_mtime > old_mtime:
            time.sleep(0.2)
            try:
                return json.load(open(json_file, 'r', encoding='utf-8'))
            except:
                continue
    return get_vision_result()


def find_element(name: str, use_vision: bool = False) -> Optional[Tuple[int, int]]:
    """查找元素坐标
    
    Args:
        name: 元素名称（部分匹配）
        use_vision: 强制使用视觉数据
    """
    if use_vision:
        d = get_vision_result()
    else:
        d, source = get_smart_result()
    
    for e in d.get('elements', []):
        label = e.get('name') or e.get('label') or ''
        if name in label:
            return tuple(e['center'])
    return None


def find_by_icon(icon_number: int) -> Optional[Tuple[int, int]]:
    """通过图标编号查找坐标（仅视觉系统）"""
    d = get_vision_result()
    idx = d.get('icon_index', {})
    coord = idx.get(str(icon_number))
    return tuple(coord) if coord else None


def click_element(name: str, retry_vision: bool = True) -> bool:
    """点击元素（智能切换）
    
    Args:
        name: 元素名称
        retry_vision: UIA找不到时是否尝试视觉
    """
    # 先用UIA
    coord = find_element(name, use_vision=False)
    
    if not coord and retry_vision:
        print(f"⚠️ UIA未找到'{name}'，尝试视觉识别...")
        coord = find_element(name, use_vision=True)
    
    if coord:
        pyautogui.click(*coord)
        print(f"✅ 点击 '{name}' @ {coord}")
        return True
    
    print(f"❌ 未找到 '{name}'")
    return False


def click_icon(icon_number: int) -> bool:
    """点击图标编号（视觉系统）"""
    coord = find_by_icon(icon_number)
    if coord:
        pyautogui.click(*coord)
        print(f"✅ 点击图标 {icon_number} @ {coord}")
        return True
    print(f"❌ 未找到图标 {icon_number}")
    return False


def type_text(text: str):
    """输入文字"""
    pyperclip.copy(text)
    pyautogui.hotkey('ctrl', 'v')
    print(f"✅ 输入: {text}")


def get_status() -> dict:
    """获取当前状态"""
    uia = get_uia_result()
    vision = get_vision_result()
    
    uia_count = len(uia.get('elements', []))
    vision_count = len(vision.get('elements', []))
    icon_count = len(vision.get('icon_index', {}))
    
    d, source = get_smart_result()
    
    return {
        'uia_elements': uia_count,
        'vision_elements': vision_count,
        'vision_icons': icon_count,
        'active_source': source,
        'uia_window': uia.get('window_title', ''),
        'vision_window': vision.get('window_title', '')
    }


def print_status():
    """打印当前状态"""
    s = get_status()
    print(f"\n=== 系统状态 ===")
    print(f"UIA系统: {s['uia_elements']}个元素 | 窗口: {s['uia_window']}")
    print(f"视觉系统: {s['vision_elements']}个元素, {s['vision_icons']}个图标 | 窗口: {s['vision_window']}")
    print(f"当前数据源: {s['active_source'].upper()}")
    print(f"切换阈值: UIA < {UIA_THRESHOLD} 时使用视觉")


# 快捷别名
click = click_element
icon = click_icon
status = print_status
refresh = force_refresh_vision


if __name__ == '__main__':
    print_status()
