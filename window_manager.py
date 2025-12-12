"""
窗口管理工具 - 识别运行中程序 + 精准切换

功能：
1. 获取所有运行中的窗口列表
2. 按名称/关键词查找窗口
3. 精准切换到指定窗口（不重复打开）
4. 如果没运行才用Win+S搜索打开
"""

import ctypes
from ctypes import wintypes
import time
import pyautogui

# Windows API
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# 常量
SW_RESTORE = 9
SW_SHOW = 5
SW_MINIMIZE = 6
GW_OWNER = 4

# 回调函数类型
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def get_window_text(hwnd: int) -> str:
    """获取窗口标题"""
    length = user32.GetWindowTextLengthW(hwnd) + 1
    buffer = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buffer, length)
    return buffer.value


def get_process_name(hwnd: int) -> str:
    """获取窗口对应的进程名"""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    # 打开进程获取名称
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if handle:
        buffer = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        kernel32.CloseHandle(handle)
        # 只返回exe名称
        return buffer.value.split('\\')[-1] if buffer.value else ""
    return ""


def is_real_window(hwnd: int) -> bool:
    """判断是否是真实可见窗口（排除隐藏窗口、工具窗口等）"""
    if not user32.IsWindowVisible(hwnd):
        return False
    
    # 排除没有标题的窗口
    title = get_window_text(hwnd)
    if not title or len(title.strip()) == 0:
        return False
    
    # 排除一些系统窗口
    skip_titles = ['Program Manager', 'MSCTFIME UI', 'Default IME', 'Windows Input Experience']
    if title in skip_titles:
        return False
    
    # 排除工具窗口（没有owner但有WS_EX_TOOLWINDOW样式）
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex_style & WS_EX_TOOLWINDOW:
        return False
    
    return True


def get_all_windows() -> list:
    """获取所有运行中的窗口"""
    windows = []
    
    def enum_callback(hwnd, lparam):
        if is_real_window(hwnd):
            title = get_window_text(hwnd)
            process = get_process_name(hwnd)
            windows.append({
                'hwnd': hwnd,
                'title': title,
                'process': process,
                'is_minimized': user32.IsIconic(hwnd) != 0
            })
        return True
    
    user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
    return windows


def find_window(keyword: str, windows: list = None) -> dict:
    """按关键词查找窗口（标题或进程名）"""
    if windows is None:
        windows = get_all_windows()
    
    keyword_lower = keyword.lower()
    
    # 精确匹配进程名
    for w in windows:
        if keyword_lower in w['process'].lower():
            return w
    
    # 模糊匹配标题
    for w in windows:
        if keyword_lower in w['title'].lower():
            return w
    
    return None


def switch_to_window(hwnd: int) -> bool:
    """切换到指定窗口"""
    try:
        # 如果窗口最小化，先恢复
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)
        
        # 激活窗口
        user32.SetForegroundWindow(hwnd)
        
        # 确保窗口在最前面
        user32.BringWindowToTop(hwnd)
        
        return True
    except:
        return False


def switch_to_app(name: str) -> dict:
    """
    智能切换到应用程序
    
    Args:
        name: 应用名称或关键词（如 "chrome", "vscode", "微信"）
    
    Returns:
        {'success': bool, 'action': 'switched'|'opened', 'window': dict}
    """
    # 常见应用名称映射
    app_mapping = {
        'chrome': ['chrome.exe', 'Google Chrome'],
        'edge': ['msedge.exe', 'Microsoft Edge'],
        'firefox': ['firefox.exe', 'Mozilla Firefox'],
        'vscode': ['Code.exe', 'Visual Studio Code'],
        'windsurf': ['Windsurf.exe', 'Windsurf'],
        'cursor': ['Cursor.exe', 'Cursor'],
        'notepad': ['notepad.exe', '记事本', 'Notepad'],
        'explorer': ['explorer.exe', '文件资源管理器'],
        'cmd': ['cmd.exe', '命令提示符'],
        'powershell': ['powershell.exe', 'PowerShell'],
        'terminal': ['WindowsTerminal.exe', 'Terminal'],
        '微信': ['WeChat.exe', '微信'],
        'wechat': ['WeChat.exe', '微信'],
        'qq': ['QQ.exe', 'QQ'],
        'blender': ['blender.exe', 'Blender'],
        'freecad': ['FreeCAD.exe', 'FreeCAD'],
        'word': ['WINWORD.EXE', 'Word'],
        'excel': ['EXCEL.EXE', 'Excel'],
        'ppt': ['POWERPNT.EXE', 'PowerPoint'],
    }
    
    # 获取所有窗口
    windows = get_all_windows()
    
    # 查找匹配的窗口
    name_lower = name.lower()
    
    # 先尝试映射
    search_terms = app_mapping.get(name_lower, [name])
    
    found = None
    for term in search_terms:
        found = find_window(term, windows)
        if found:
            break
    
    if found:
        # 找到了，切换过去
        success = switch_to_window(found['hwnd'])
        return {
            'success': success,
            'action': 'switched',
            'window': found,
            'message': f"已切换到: {found['title']}"
        }
    else:
        # 没找到，用Win+S搜索打开
        pyautogui.hotkey('win', 's')
        time.sleep(0.5)
        pyautogui.typewrite(name if name.isascii() else '', interval=0.05)
        if not name.isascii():
            # 中文用剪贴板
            import pyperclip
            pyperclip.copy(name)
            pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        pyautogui.press('enter')
        return {
            'success': True,
            'action': 'opened',
            'window': None,
            'message': f"未找到运行中的 {name}，已搜索打开"
        }


def list_windows():
    """列出所有运行中的窗口（调试用）"""
    windows = get_all_windows()
    print(f"\n=== 运行中的窗口 ({len(windows)}个) ===\n")
    for i, w in enumerate(windows, 1):
        status = "[最小化]" if w['is_minimized'] else ""
        print(f"{i:2}. {w['process']:25} | {w['title'][:50]} {status}")
    return windows


# 命令行测试
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        app_name = sys.argv[1]
        print(f"切换到: {app_name}")
        result = switch_to_app(app_name)
        print(result['message'])
    else:
        list_windows()
