"""
程序监控系统 - 实时识别三类程序

1. taskbar_apps: 任务栏运行的程序（有窗口）
2. background_apps: 后台运行的程序（托盘/无窗口，如QQ、百度网盘）
3. installed_apps: 已安装但未运行的程序

输出: output/apps.json
"""

import ctypes
from ctypes import wintypes
import json
import time
import subprocess
import os
from pathlib import Path
from datetime import datetime
import threading
import winreg

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class AppMonitor:
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = Path(__file__).parent / 'output'
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.output_file = self.output_dir / 'apps.json'
        
        # 缓存已安装程序（不常变，启动时扫描一次）
        self.installed_cache = None
        self.installed_cache_time = 0
        
        # 确认能快速打开的程序（已验证的命令）
        self.quick_launch = {
            # 系统工具
            'notepad': {'cmd': 'notepad', 'name': '记事本'},
            'calc': {'cmd': 'calc', 'name': '计算器'},
            'explorer': {'cmd': 'explorer', 'name': '文件资源管理器'},
            'cmd': {'cmd': 'cmd', 'name': '命令提示符'},
            'powershell': {'cmd': 'powershell', 'name': 'PowerShell'},
            'terminal': {'cmd': 'wt', 'name': 'Windows Terminal'},
            'mspaint': {'cmd': 'mspaint', 'name': '画图'},
            'taskmgr': {'cmd': 'taskmgr', 'name': '任务管理器'},
            'control': {'cmd': 'control', 'name': '控制面板'},
            'settings': {'cmd': 'start ms-settings:', 'name': '设置'},
            # 浏览器
            'chrome': {'cmd': 'start chrome', 'name': 'Google Chrome'},
            'edge': {'cmd': 'start msedge', 'name': 'Microsoft Edge'},
            'firefox': {'cmd': 'start firefox', 'name': 'Firefox'},
            # 开发工具
            'vscode': {'cmd': 'code', 'name': 'VS Code'},
            'windsurf': {'cmd': 'start "" "C:\\Users\\%USERNAME%\\AppData\\Local\\Programs\\Windsurf\\Windsurf.exe"', 'name': 'Windsurf'},
            # Office
            'word': {'cmd': 'start winword', 'name': 'Word'},
            'excel': {'cmd': 'start excel', 'name': 'Excel'},
            'ppt': {'cmd': 'start powerpnt', 'name': 'PowerPoint'},
            'outlook': {'cmd': 'start outlook', 'name': 'Outlook'},
        }
        
        self.running = False
    
    def get_window_text(self, hwnd: int) -> str:
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buffer = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buffer, length)
        return buffer.value
    
    def get_process_name(self, hwnd: int) -> tuple:
        """返回 (进程名, PID)"""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if handle:
            buffer = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(260)
            kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
            kernel32.CloseHandle(handle)
            return buffer.value.split('\\')[-1] if buffer.value else "", pid.value
        return "", pid.value
    
    def get_taskbar_apps(self) -> list:
        """获取任务栏运行的程序（有窗口）"""
        apps = []
        seen_pids = set()
        
        def enum_callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            
            title = self.get_window_text(hwnd)
            if not title or len(title.strip()) == 0:
                return True
            
            # 排除系统窗口
            skip = ['Program Manager', 'MSCTFIME UI', 'Default IME', 'Windows Input Experience']
            if title in skip:
                return True
            
            # 排除工具窗口
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex_style & WS_EX_TOOLWINDOW:
                return True
            
            process, pid = self.get_process_name(hwnd)
            if pid in seen_pids:
                return True
            seen_pids.add(pid)
            
            apps.append({
                'name': process.replace('.exe', ''),
                'process': process,
                'title': title[:100],
                'pid': pid,
                'hwnd': hwnd,
                'minimized': user32.IsIconic(hwnd) != 0
            })
            return True
        
        user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
        return apps
    
    def get_background_apps(self) -> list:
        """获取后台运行的程序（无窗口，如托盘程序）"""
        # 获取所有进程
        all_processes = {}
        
        # 使用tasklist获取所有进程
        try:
            result = subprocess.run(
                ['tasklist', '/fo', 'csv', '/nh'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.replace('"', '').split(',')
                    if len(parts) >= 2:
                        name = parts[0]
                        pid = int(parts[1]) if parts[1].isdigit() else 0
                        all_processes[pid] = name
        except:
            pass
        
        # 获取有窗口的进程PID
        window_pids = set()
        def enum_callback(hwnd, lparam):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            window_pids.add(pid.value)
            return True
        user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
        
        # 常见后台程序（托盘程序）
        background_keywords = [
            'qq', 'wechat', 'weixin', 'telegram', 'discord', 'slack',
            'baidunetdisk', 'baiduyunguanjia', 'onedrive', 'dropbox',
            'steam', 'epic', 'nvidia', 'amd', 'intel',
            'clash', 'v2ray', 'shadowsocks',
            'everything', 'listary', 'snipaste',
            'potplayer', 'foobar', 'spotify',
            'teamviewer', 'anydesk', 'sunlogin',
        ]
        
        apps = []
        seen = set()
        for pid, name in all_processes.items():
            if pid in window_pids:
                continue
            
            name_lower = name.lower().replace('.exe', '')
            if any(kw in name_lower for kw in background_keywords):
                if name not in seen:
                    seen.add(name)
                    apps.append({
                        'name': name.replace('.exe', ''),
                        'process': name,
                        'pid': pid
                    })
        
        return apps
    
    def get_installed_apps(self, force_refresh: bool = False) -> list:
        """获取已安装的程序（从注册表和开始菜单）"""
        # 缓存10分钟
        if not force_refresh and self.installed_cache and time.time() - self.installed_cache_time < 600:
            return self.installed_cache
        
        apps = {}
        
        # 从注册表读取
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for hkey, path in reg_paths:
            try:
                key = winreg.OpenKey(hkey, path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            if name and len(name) > 1:
                                exe_path = ""
                                try:
                                    exe_path = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                except:
                                    pass
                                if name not in apps:
                                    apps[name] = {'name': name, 'path': exe_path}
                        except:
                            pass
                        winreg.CloseKey(subkey)
                    except:
                        pass
                winreg.CloseKey(key)
            except:
                pass
        
        # 从开始菜单读取快捷方式
        start_paths = [
            Path(os.environ.get('PROGRAMDATA', '')) / 'Microsoft/Windows/Start Menu/Programs',
            Path(os.environ.get('APPDATA', '')) / 'Microsoft/Windows/Start Menu/Programs',
        ]
        
        for start_path in start_paths:
            if start_path.exists():
                for lnk in start_path.rglob('*.lnk'):
                    name = lnk.stem
                    if name and len(name) > 1 and name not in apps:
                        apps[name] = {'name': name, 'path': str(lnk)}
        
        result = list(apps.values())
        self.installed_cache = result
        self.installed_cache_time = time.time()
        
        return result
    
    def scan_once(self) -> dict:
        """单次扫描"""
        taskbar = self.get_taskbar_apps()
        background = self.get_background_apps()
        installed = self.get_installed_apps()
        
        # 获取正在运行的进程名
        running_names = set()
        for app in taskbar + background:
            running_names.add(app['process'].lower())
            running_names.add(app['name'].lower())
        
        # 过滤已安装列表，只保留未运行的
        not_running = []
        for app in installed:
            name_lower = app['name'].lower()
            # 简单匹配
            is_running = any(r in name_lower or name_lower in r for r in running_names)
            if not is_running:
                not_running.append(app)
        
        # 为每个程序添加具体打开方式
        for app in taskbar:
            app['open_method'] = 'hwnd'  # 用窗口句柄切换
            app['open_code'] = f"user32.ShowWindow({app['hwnd']}, 9); user32.SetForegroundWindow({app['hwnd']})"
        
        for app in background:
            name_lower = app['name'].lower()
            if 'qq' in name_lower:
                app['open_method'] = 'hotkey'
                app['open_hotkey'] = 'ctrl+alt+z'
                app['open_code'] = "pyautogui.hotkey('ctrl', 'alt', 'z')"
            elif 'wechat' in name_lower or 'weixin' in name_lower:
                app['open_method'] = 'hotkey'
                app['open_hotkey'] = 'ctrl+alt+w'
                app['open_code'] = "pyautogui.hotkey('ctrl', 'alt', 'w')"
            else:
                app['open_method'] = 'tray'
                app['open_code'] = '需手动点击托盘图标'
        
        data = {
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'note': '三种打开方式: taskbar用hwnd切换, background用hotkey激活, quick_launch用cmd启动',
            # 任务栏程序（有窗口，用hwnd切换）
            'taskbar_apps': taskbar,
            'taskbar_count': len(taskbar),
            # 后台程序（托盘运行，用快捷键激活）
            'background_apps': background,
            'background_count': len(background),
            # 快捷启动（确认能快速打开的，用cmd启动）
            'quick_launch': self.quick_launch,
            'quick_launch_count': len(self.quick_launch),
            # 索引（方便查询）
            'index': {
                'taskbar': {app['name']: {'hwnd': app['hwnd'], 'title': app['title'][:50], 'method': 'hwnd'} for app in taskbar},
                'background': {app['name']: {'pid': app['pid'], 'method': app.get('open_method', 'tray'), 'hotkey': app.get('open_hotkey', '')} for app in background},
                'quick': {k: {'cmd': v['cmd'], 'name': v['name']} for k, v in self.quick_launch.items()},
            },
            # 使用说明
            'usage': {
                'taskbar': 'from ctypes import windll; windll.user32.SetForegroundWindow(hwnd)',
                'background_qq': "import pyautogui; pyautogui.hotkey('ctrl', 'alt', 'z')",
                'background_wechat': "import pyautogui; pyautogui.hotkey('ctrl', 'alt', 'w')",
                'quick_launch': "import os; os.system(cmd)"
            }
        }
        
        return data
    
    def save(self, data: dict):
        """保存到JSON"""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def run(self, interval: float = 2.0):
        """持续运行"""
        print(f"程序监控已启动，输出: {self.output_file}")
        print(f"刷新间隔: {interval}秒")
        self.running = True
        
        while self.running:
            try:
                data = self.scan_once()
                self.save(data)
                print(f"\r[{data['timestamp']}] 任务栏:{data['taskbar_count']} 后台:{data['background_count']} 已安装:{data['installed_count']}", end='', flush=True)
            except Exception as e:
                print(f"\n错误: {e}")
            
            time.sleep(interval)
    
    def stop(self):
        self.running = False


def switch_to_app(name: str) -> dict:
    """智能切换/打开应用"""
    monitor = AppMonitor()
    data = monitor.scan_once()
    
    name_lower = name.lower()
    
    # 1. 先查任务栏（有窗口的程序）
    for app in data['taskbar_apps']:
        if name_lower in app['name'].lower() or name_lower in app['title'].lower():
            hwnd = app['hwnd']
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            return {'success': True, 'action': 'switched', 'app': app, 'message': f"已切换到: {app['title'][:50]}"}
    
    # 2. 查后台程序（如QQ、微信）- 查找隐藏窗口并激活
    for app in data['background_apps']:
        if name_lower in app['name'].lower():
            # 方法1：查找该进程的所有窗口（包括隐藏的）
            found_hwnd = None
            def find_process_window(hwnd, lparam):
                nonlocal found_hwnd
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == app['pid']:
                    # 找到该进程的窗口
                    title = monitor.get_window_text(hwnd)
                    if title and len(title) > 0:
                        found_hwnd = hwnd
                        return False  # 停止枚举
                return True
            
            user32.EnumWindows(EnumWindowsProc(find_process_window), 0)
            
            if found_hwnd:
                # 激活找到的窗口
                user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(found_hwnd)
                user32.BringWindowToTop(found_hwnd)
                return {'success': True, 'action': 'activated', 'app': app, 'hwnd': found_hwnd, 'message': f"已激活后台程序窗口: {app['name']}"}
            
            # 方法2：用快捷键激活常见托盘程序
            import pyautogui
            if 'qq' in name_lower:
                # QQ默认快捷键 Ctrl+Alt+Z
                pyautogui.hotkey('ctrl', 'alt', 'z')
                time.sleep(0.3)
                return {'success': True, 'action': 'hotkey', 'app': app, 'message': f"已用快捷键Ctrl+Alt+Z激活QQ"}
            elif 'wechat' in name_lower or 'weixin' in name_lower:
                # 微信默认快捷键 Ctrl+Alt+W
                pyautogui.hotkey('ctrl', 'alt', 'w')
                time.sleep(0.3)
                return {'success': True, 'action': 'hotkey', 'app': app, 'message': f"已用快捷键Ctrl+Alt+W激活微信"}
            
            return {'success': False, 'action': 'background', 'app': app, 'message': f"后台程序 {app['name']} 无可见窗口，请手动点击托盘图标"}
    
    # 3. 查快捷启动（确认能快速打开的程序）
    if name_lower in monitor.quick_launch:
        info = monitor.quick_launch[name_lower]
        cmd = info['cmd']
        os.system(cmd)
        return {'success': True, 'action': 'launched', 'command': cmd, 'message': f"已快速启动: {info['name']}"}
    
    # 4. 其他程序用Win+S搜索
    import pyautogui
    pyautogui.hotkey('win', 's')
    time.sleep(0.5)
    if name.isascii():
        pyautogui.typewrite(name, interval=0.05)
    else:
        import pyperclip
        pyperclip.copy(name)
        pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.3)
    pyautogui.press('enter')
    return {'success': True, 'action': 'searched', 'message': f"未找到快速启动方式，已用Win+S搜索: {name}"}


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--daemon':
            # 后台运行
            monitor = AppMonitor()
            monitor.run(interval=2.0)
        else:
            # 切换应用
            result = switch_to_app(sys.argv[1])
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 单次扫描
        monitor = AppMonitor()
        data = monitor.scan_once()
        monitor.save(data)
        print(f"已保存到: {monitor.output_file}")
        print(f"\n任务栏程序 ({data['taskbar_count']}个):")
        for app in data['taskbar_apps'][:10]:
            print(f"  {app['name']:20} | {app['title'][:40]}")
        print(f"\n后台程序 ({data['background_count']}个):")
        for app in data['background_apps'][:10]:
            print(f"  {app['name']}")
