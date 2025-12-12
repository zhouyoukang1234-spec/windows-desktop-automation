"""
视觉识别辅助工具 - 提供强制刷新和智能点击功能
"""
import json
import time
import pyautogui
import pyperclip
from pathlib import Path
from typing import Optional, Tuple, List

OUTPUT_DIR = Path(__file__).parent / 'output'

def force_refresh(wait_sec: float = 3.0) -> dict:
    """强制触发重新识别
    
    Args:
        wait_sec: 等待识别完成的秒数
    
    Returns:
        最新的识别结果
    """
    signal_file = OUTPUT_DIR / '.force_refresh'
    json_file = OUTPUT_DIR / 'latest_vision.json'
    
    # 记录旧的修改时间
    old_mtime = json_file.stat().st_mtime if json_file.exists() else 0
    
    # 写入信号文件
    signal_file.write_text(str(time.time()))
    print("🔄 强制刷新已触发")
    
    # 等待新结果
    start = time.time()
    while time.time() - start < wait_sec:
        time.sleep(0.3)
        if json_file.exists() and json_file.stat().st_mtime > old_mtime:
            time.sleep(0.2)  # 等待写入完成
            try:
                d = json.load(open(json_file, 'r', encoding='utf-8'))
                print(f"✅ 识别完成: {len(d.get('elements', []))} 个元素")
                return d
            except json.JSONDecodeError:
                continue  # 文件还在写入，继续等待
    
    print("⚠️ 等待超时，返回旧结果")
    try:
        return json.load(open(json_file, 'r', encoding='utf-8')) if json_file.exists() else {}
    except:
        return {}

def get_result() -> dict:
    """获取最新识别结果"""
    json_file = OUTPUT_DIR / 'latest_vision.json'
    if json_file.exists():
        return json.load(open(json_file, 'r', encoding='utf-8'))
    return {}

def find_by_label(label: str, refresh: bool = False) -> Optional[Tuple[int, int]]:
    """通过OCR标签查找元素坐标
    
    Args:
        label: 要查找的文字（支持部分匹配）
        refresh: 是否先强制刷新
    
    Returns:
        (x, y) 坐标，未找到返回 None
    """
    d = force_refresh() if refresh else get_result()
    
    for e in d.get('elements', []):
        if label in e.get('label', ''):
            return tuple(e['center'])
    return None

def find_by_icon(icon_number: int, refresh: bool = False) -> Optional[Tuple[int, int]]:
    """通过图标编号查找坐标
    
    Args:
        icon_number: 青色数字编号
        refresh: 是否先强制刷新
    
    Returns:
        (x, y) 坐标，未找到返回 None
    """
    d = force_refresh() if refresh else get_result()
    idx = d.get('icon_index', {})
    coord = idx.get(str(icon_number))
    return tuple(coord) if coord else None

def click_label(label: str, retry: bool = True) -> bool:
    """点击包含指定文字的元素
    
    Args:
        label: 要点击的文字
        retry: 未找到时是否强制刷新重试
    
    Returns:
        是否点击成功
    """
    coord = find_by_label(label)
    if not coord and retry:
        print(f"⚠️ 未找到 '{label}'，强制刷新重试...")
        coord = find_by_label(label, refresh=True)
    
    if coord:
        pyautogui.click(*coord)
        print(f"✅ 点击 '{label}' @ {coord}")
        return True
    
    print(f"❌ 未找到 '{label}'")
    return False

def click_icon(icon_number: int, retry: bool = True) -> bool:
    """点击指定编号的图标
    
    Args:
        icon_number: 青色数字编号
        retry: 未找到时是否强制刷新重试
    
    Returns:
        是否点击成功
    """
    coord = find_by_icon(icon_number)
    if not coord and retry:
        print(f"⚠️ 未找到图标 {icon_number}，强制刷新重试...")
        coord = find_by_icon(icon_number, refresh=True)
    
    if coord:
        pyautogui.click(*coord)
        print(f"✅ 点击图标 {icon_number} @ {coord}")
        return True
    
    print(f"❌ 未找到图标 {icon_number}")
    return False

def type_text(text: str, use_clipboard: bool = True):
    """输入文字（支持中文）
    
    Args:
        text: 要输入的文字
        use_clipboard: 是否使用剪贴板（推荐，支持中文）
    """
    if use_clipboard:
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
    else:
        pyautogui.typewrite(text, interval=0.05)
    print(f"✅ 输入: {text}")

def list_elements(method: str = None) -> List[dict]:
    """列出所有识别的元素
    
    Args:
        method: 过滤方法 ('ocr', 'yolo', 'florence')
    
    Returns:
        元素列表
    """
    d = get_result()
    elements = d.get('elements', [])
    if method:
        elements = [e for e in elements if e.get('method') == method]
    return elements

def list_icons() -> dict:
    """列出所有图标编号和坐标"""
    d = get_result()
    return d.get('icon_index', {})


# 快捷函数
refresh = force_refresh
click = click_label
icon = click_icon


if __name__ == '__main__':
    # 测试
    print("=== 视觉识别辅助工具 ===")
    d = get_result()
    print(f"元素数量: {len(d.get('elements', []))}")
    print(f"图标编号: {list(d.get('icon_index', {}).keys())}")
