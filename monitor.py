#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版实时监控系统 V2.0
========================
设计理念：系统只做数据采集，AI做所有决策

核心原则：
1. 极简设计 - 只做UIA扫描和截图
2. 持续更新 - 0.5秒固定间隔，不做变化检测
3. 快速输出 - JSON带索引，AI直接读取无需grep
4. 前台聚焦 - 只识别当前前台窗口

输出文件：
- output/latest.json（控件信息+快速索引）
- output/latest.png（实时截图）
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

import win32gui
import win32con
from PIL import ImageGrab

try:
    from pywinauto import Application
    UIA_AVAILABLE = True
except ImportError:
    UIA_AVAILABLE = False
    print("❌ pywinauto未安装，请运行: pip install pywinauto")
    sys.exit(1)


class SimplifiedMonitor:
    """简化版实时监控系统"""
    
    def __init__(self, interval: float = 0.5):
        """
        初始化
        
        Args:
            interval: 更新间隔（秒），默认0.5
        """
        self.interval = interval
        self.running = False
        
        # 输出目录
        self.output_dir = Path(__file__).parent / 'output'
        self.output_dir.mkdir(exist_ok=True)
        
        # Application缓存（复用，减少开销）
        self._app_cache: Dict[int, Application] = {}
        self._last_hwnd: Optional[int] = None
        
        # 异步写入线程池
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        # 统计
        self.scan_count = 0
        self.success_count = 0
        self._screenshot_count = 0
        self.start_time = None
        
        # 窗口切换检测
        self._last_window_hwnd = None
        self._last_window_title = None
        
        # 跳过的控件类型（无用类型）
        self.SKIP_TYPES = {'Separator', 'ScrollBar', 'Thumb', 'Grip', 'TitleBar'}
        
        print("=" * 60)
        print("🚀 简化版实时监控系统 V2.0")
        print("=" * 60)
        print(f"📁 输出目录: {self.output_dir.absolute()}")
        print(f"⏱️  更新间隔: {interval}秒")
        print("=" * 60)
    
    def _get_foreground_window(self) -> tuple:
        """获取前台窗口信息"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or not win32gui.IsWindow(hwnd):
            return None, None, None
        
        title = win32gui.GetWindowText(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        return hwnd, title, rect
    
    def _get_app(self, hwnd: int) -> Optional[Application]:
        """获取或创建Application对象（带缓存）"""
        # 窗口切换时清理缓存
        if self._last_hwnd != hwnd:
            self._app_cache.clear()
            self._last_hwnd = hwnd
        
        if hwnd not in self._app_cache:
            try:
                app = Application(backend='uia').connect(handle=hwnd, timeout=2.0)
                self._app_cache[hwnd] = app
            except Exception:
                return None
        
        return self._app_cache.get(hwnd)
    
    def _scan_controls(self, hwnd: int, title: str) -> Dict:
        """扫描窗口控件"""
        app = self._get_app(hwnd)
        if not app:
            return {}
        
        controls = {}
        index_by_name = {}
        index_by_type = {}
        
        try:
            window = app.window(handle=hwnd)
            
            # 检测是否是浏览器（需要深度遍历）
            is_browser = any(x in title.lower() for x in ['chrome', 'edge', 'firefox', '豆包', 'browser'])
            
            # 获取后代控件
            descendants = list(window.descendants())
            
            # 浏览器深度遍历Document
            if is_browser:
                extra_controls = []
                for desc in descendants[:50]:
                    try:
                        if desc.element_info.control_type == 'Document':
                            doc_children = list(desc.descendants())
                            extra_controls.extend(doc_children[:200])
                    except:
                        pass
                descendants.extend(extra_controls)
            
            # 控件数量限制
            max_controls = 400 if is_browser else 200
            
            for i, ctrl in enumerate(descendants[:max_controls]):
                try:
                    ctrl_type = ctrl.element_info.control_type
                    
                    # 跳过无用类型
                    if ctrl_type in self.SKIP_TYPES:
                        continue
                    
                    # 获取矩形
                    rect = ctrl.rectangle()
                    
                    # 检查有效性（有尺寸且在屏幕内）
                    width = rect.right - rect.left
                    height = rect.bottom - rect.top
                    if width < 5 or height < 5:
                        continue
                    if rect.left < -1000 or rect.top < -1000:
                        continue
                    
                    # 计算中心坐标
                    cx = (rect.left + rect.right) // 2
                    cy = (rect.top + rect.bottom) // 2
                    
                    # 获取名称
                    try:
                        name = ctrl.element_info.name or ''
                    except:
                        name = ''
                    
                    # 获取启用状态
                    try:
                        enabled = ctrl.is_enabled()
                    except:
                        enabled = True
                    
                    # 生成控件ID
                    ctrl_id = f"{ctrl_type}_{cx}_{cy}"
                    
                    # 存储控件信息
                    ctrl_info = {
                        'type': ctrl_type,
                        'name': name,
                        'center': [cx, cy],
                        'rect': [rect.left, rect.top, rect.right, rect.bottom],
                        'enabled': enabled
                    }
                    controls[ctrl_id] = ctrl_info
                    
                    # 建立名称索引（非空名称）
                    if name and len(name) > 0:
                        # 取名称前30个字符作为key
                        name_key = name[:30]
                        index_by_name[name_key] = [cx, cy]
                    
                    # 建立类型索引
                    if ctrl_type not in index_by_type:
                        index_by_type[ctrl_type] = []
                    index_by_type[ctrl_type].append([cx, cy])
                    
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"⚠️ 扫描异常: {e}")
        
        return {
            'controls': controls,
            'index_by_name': index_by_name,
            'index_by_type': index_by_type
        }
    
    def _screenshot_loop(self):
        """截图线程：独立运行，0.5秒持续截图，支持多显示器"""
        while self.running:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd and win32gui.IsWindow(hwnd):
                    rect = win32gui.GetWindowRect(hwnd)
                    # 确保rect有效
                    if rect[2] > rect[0] and rect[3] > rect[1]:
                        # all_screens=True 支持多显示器（包括负坐标的第二屏幕）
                        screenshot = ImageGrab.grab(bbox=rect, all_screens=True)
                        if screenshot and screenshot.size[0] > 0:
                            img_path = self.output_dir / 'latest.png'
                            screenshot.save(str(img_path), 'PNG')
                            self._screenshot_count += 1
            except Exception as e:
                print(f"截图异常: {e}")
            time.sleep(0.5)
    
    def _save_json(self, data: Dict):
        """保存JSON"""
        try:
            json_path = self.output_dir / 'latest.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def _do_scan(self):
        """执行一次UIA扫描（截图由独立线程处理）"""
        self.scan_count += 1
        
        # 获取前台窗口
        hwnd, title, rect = self._get_foreground_window()
        if not hwnd:
            return
        
        # 扫描控件
        scan_result = self._scan_controls(hwnd, title)
        
        # 组装数据
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        data = {
            'timestamp': timestamp,
            'window': {
                'hwnd': hwnd,
                'title': title,
                'rect': list(rect) if rect else []
            },
            'control_count': len(scan_result.get('controls', {})),
            'controls': list(scan_result.get('controls', {}).values()),
            'index': {
                'by_name': scan_result.get('index_by_name', {}),
                'by_type': scan_result.get('index_by_type', {})
            }
        }
        
        # 保存JSON
        self._save_json(data)
        self.success_count += 1
        
        # 输出状态（每10次输出一次）
        if self.scan_count % 10 == 0:
            elapsed = time.time() - self.start_time
            rate = self.success_count / elapsed if elapsed > 0 else 0
            print(f"📊 扫描{self.scan_count}次 | 截图{self._screenshot_count}次 | 窗口: {title[:30]}")
    
    def _check_window_change(self) -> bool:
        """快速检测窗口是否切换（50ms级别）"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
        
        title = win32gui.GetWindowText(hwnd)
        
        # 检测窗口是否切换
        if hwnd != self._last_window_hwnd or title != self._last_window_title:
            self._last_window_hwnd = hwnd
            self._last_window_title = title
            return True
        
        return False
    
    def run(self):
        """运行监控（截图线程独立 + UIA扫描）"""
        self.running = True
        self.start_time = time.time()
        
        print(f"\n🎯 开始监控")
        print(f"   📸 截图线程: 0.5秒/次（独立运行）")
        print(f"   🔍 UIA扫描: {self.interval}秒/次")
        print(f"📁 输出: {self.output_dir / 'latest.json'}")
        print(f"📁 截图: {self.output_dir / 'latest.png'}")
        print(f"\n按 Ctrl+C 停止\n")
        print("-" * 60)
        
        # 启动截图线程（独立运行）
        screenshot_thread = threading.Thread(target=self._screenshot_loop, daemon=True)
        screenshot_thread.start()
        print("✅ 截图线程已启动")
        
        try:
            while self.running:
                # UIA扫描
                self._do_scan()
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print("⏹️  用户停止")
            print("=" * 60)
            self.running = False
            
            # 最终统计
            elapsed = time.time() - self.start_time
            print(f"\n📊 最终统计:")
            print(f"   运行时间: {elapsed:.1f}秒")
            print(f"   扫描次数: {self.scan_count}")
            print(f"   成功次数: {self.success_count}")
            print(f"   成功率: {self.success_count/max(self.scan_count,1)*100:.1f}%")
            print(f"\n✅ 系统已停止")
        
        finally:
            self._executor.shutdown(wait=False)
    
    def stop(self):
        """停止监控"""
        self.running = False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='简化版实时监控系统 V2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python monitor.py              # 默认0.5秒间隔
  python monitor.py --interval 0.3   # 0.3秒间隔
        """
    )
    parser.add_argument('--interval', type=float, default=0.5,
                        help='更新间隔（秒），默认0.5')
    
    args = parser.parse_args()
    
    try:
        monitor = SimplifiedMonitor(interval=args.interval)
        monitor.run()
    except Exception as e:
        print(f"\n❌ 系统异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
