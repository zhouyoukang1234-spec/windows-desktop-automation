#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉识别监控系统 V2.0
用于UIA无法识别的软件（微信、Blender等）

三层识别：
1. YOLO - 图标位置检测
2. RapidOCR - 文字标签识别
3. Florence-2 - 图标语义识别

特性：
- 增量识别：只识别变化区域，稳定元素复用
- 持续刷新：与UIA系统相同的刷新机制
- 前台窗口：只识别当前激活窗口

输出：
- output/latest_vision.json（视觉识别结果）
- output/latest_vision.png（标注后的截图）
"""

import os
import sys
import json
import time
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import win32gui
import win32api
import ctypes
from mss import mss

# 启用DPI感知，确保坐标正确
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

# 尝试导入识别模块
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️ YOLO未安装，视觉检测不可用")

try:
    from rapidocr_onnxruntime import RapidOCR
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ RapidOCR未安装，文字识别不可用")


class VisionMonitor:
    """视觉识别监控系统"""
    
    def __init__(self, 
                 interval: float = 1.0,
                 weights_dir: str = None,
                 enable_florence: bool = False):
        """
        初始化
        
        Args:
            interval: 刷新间隔（秒），默认1.0（视觉识别较慢）
            weights_dir: 模型权重目录
            enable_florence: 是否启用Florence-2（较慢但更准确）
        """
        self.interval = interval
        self.enable_florence = enable_florence
        self.running = False
        
        # 输出目录（与UIA系统同级）
        self.output_dir = Path(__file__).parent / 'output'
        self.output_dir.mkdir(exist_ok=True)
        
        # 模型路径
        if weights_dir is None:
            # 默认路径
            project_root = Path(__file__).parent.parent
            weights_dir = project_root / 'weights' / 'omniparser_v2'
        self.weights_dir = Path(weights_dir)
        
        # 初始化识别器
        self.detector = None
        self.ocr = None
        self.florence_model = None
        self.florence_processor = None
        
        # 增量识别状态
        self.last_image = None
        self.last_image_hash = None
        self.stable_elements = {}  # {位置签名: 元素信息}
        self.element_index = 0  # 全局元素编号
        
        # 图标编号稳定性（参考canvas系统）
        self.last_icon_elements = []  # 上次的红色图标元素列表 [{id, center_x, center_y}, ...]
        
        # OCR独立文字稳定性（避免每次识别都变化）
        self.stable_ocr_texts = {}  # {label: {bbox, center, last_seen}}
        self.ocr_stable_threshold = 30  # 位置匹配阈值（像素）
        self.icon_match_threshold = 15  # 位置匹配阈值（像素）
        
        # 变化检测参数
        self.change_threshold = 30
        self.min_change_area = 100
        self.cache_similarity = 0.98  # 98%相似度才使用缓存（更敏感，更新更快）
        
        # 异步写入
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        # 统计
        self.scan_count = 0
        self.cache_count = 0
        
        print("=" * 60)
        print("🔍 视觉识别监控系统 V2.0")
        print("=" * 60)
        print(f"📁 输出目录: {self.output_dir.absolute()}")
        print(f"⏱️  刷新间隔: {interval}秒")
        print(f"🎯 Florence-2: {'启用' if enable_florence else '禁用'}")
        print("=" * 60)
        
        self._load_models()
    
    def _load_models(self):
        """加载识别模型"""
        # 1. YOLO检测器
        if YOLO_AVAILABLE:
            model_path = self.weights_dir / 'icon_detect' / 'model.pt'
            if model_path.exists():
                self.detector = YOLO(str(model_path))
                print(f"✅ YOLO检测器已加载")
            else:
                print(f"⚠️ YOLO模型不存在: {model_path}")
        
        # 2. OCR识别器
        if OCR_AVAILABLE:
            self.ocr = RapidOCR()
            print(f"✅ RapidOCR已加载")
        
        # 3. Florence-2（可选）
        if self.enable_florence:
            try:
                from transformers import AutoProcessor, AutoModelForCausalLM
                import torch
                
                florence_path = self.weights_dir / 'icon_caption_florence'
                if not florence_path.exists():
                    florence_path = self.weights_dir / 'icon_caption'
                
                if florence_path.exists():
                    self.florence_processor = AutoProcessor.from_pretrained(
                        str(florence_path),
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    # 添加attn_implementation参数避免SDPA兼容性问题
                    self.florence_model = AutoModelForCausalLM.from_pretrained(
                        str(florence_path),
                        trust_remote_code=True,
                        local_files_only=True,
                        attn_implementation="eager"  # 避免SDPA兼容问题
                    )
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    self.florence_model.to(device)
                    self.florence_model.eval()
                    print(f"✅ Florence-2已加载 ({device})")
            except Exception as e:
                print(f"⚠️ Florence-2加载失败: {e}")
    
    def _get_foreground_window(self) -> Tuple[Optional[int], str, Tuple, Tuple]:
        """获取前台窗口（返回窗口rect和客户区偏移）"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or not win32gui.IsWindow(hwnd):
            return None, "", (0, 0, 0, 0), (0, 0)
        
        title = win32gui.GetWindowText(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        
        # 计算客户区偏移（标题栏+边框）
        try:
            client_rect = win32gui.GetClientRect(hwnd)
            # 客户区左上角在屏幕上的位置
            client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
            # 偏移量 = 客户区位置 - 窗口位置
            offset_x = client_left - rect[0]
            offset_y = client_top - rect[1]
        except:
            offset_x, offset_y = 0, 0
        
        return hwnd, title, rect, (offset_x, offset_y)
    
    def _capture_window(self, rect: Tuple) -> Optional[np.ndarray]:
        """截取窗口"""
        try:
            x1, y1, x2, y2 = rect
            with mss() as sct:
                monitor = {"left": x1, "top": y1, "width": x2-x1, "height": y2-y1}
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                return img
        except:
            return None
    
    def _calc_image_hash(self, image: np.ndarray) -> str:
        """计算图像感知哈希"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (16, 16))
        dct = cv2.dct(np.float32(resized))
        dct_low = dct[:8, :8]
        avg = dct_low.mean()
        hash_bits = (dct_low > avg).flatten()
        hash_array = np.packbits(hash_bits)
        return ''.join(format(x, '02x') for x in hash_array[:8])
    
    def _hash_similarity(self, hash1: str, hash2: str) -> float:
        """计算哈希相似度"""
        if not hash1 or not hash2:
            return 0.0
        hamming = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        return 1.0 - (hamming / (len(hash1) * 4))
    
    def _detect_changed_regions(self, current: np.ndarray, last: np.ndarray) -> List[Tuple]:
        """检测变化区域"""
        if last is None:
            h, w = current.shape[:2]
            return [(0, 0, w, h)]
        
        if current.shape != last.shape:
            h, w = current.shape[:2]
            return [(0, 0, w, h)]
        
        # 计算差异
        diff = cv2.absdiff(current, last)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, self.change_threshold, 255, cv2.THRESH_BINARY)
        
        # 形态学处理
        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        regions = []
        for contour in contours:
            if cv2.contourArea(contour) > self.min_change_area:
                x, y, w, h = cv2.boundingRect(contour)
                margin = 20
                regions.append((
                    max(0, x - margin),
                    max(0, y - margin),
                    min(current.shape[1], x + w + margin),
                    min(current.shape[0], y + h + margin)
                ))
        
        return regions if regions else []
    
    def _get_element_signature(self, bbox: List[int]) -> str:
        """生成元素位置签名（用于增量识别）"""
        x1, y1, x2, y2 = bbox
        # 10像素容差
        return f"{x1//10}_{y1//10}_{x2//10}_{y2//10}"
    
    def _is_in_changed_region(self, bbox: List[int], regions: List[Tuple]) -> bool:
        """判断元素是否在变化区域内"""
        if not regions:
            return False
        
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        
        for rx1, ry1, rx2, ry2 in regions:
            if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                return True
        return False
    
    def _ocr_find_label(self, bbox: List[int], ocr_results: List) -> str:
        """OCR查找图标对应的文字标签（支持文字在框内或框下方）"""
        if not ocr_results:
            return ""
        
        x1, y1, x2, y2 = bbox
        icon_center_x = (x1 + x2) / 2
        icon_center_y = (y1 + y2) / 2
        icon_width = x2 - x1
        icon_height = y2 - y1
        
        candidates = []
        for item in ocr_results:
            box, text, confidence = item
            text = text.strip()
            
            # 过滤
            if len(text) < 1 or confidence < 0.5:
                continue
            if text[0] in '×·…@#$%^&*':
                continue
            
            # 计算文字中心位置
            text_cx = sum(p[0] for p in box) / 4
            text_cy = sum(p[1] for p in box) / 4
            text_left = min(p[0] for p in box)
            text_right = max(p[0] for p in box)
            text_top = min(p[1] for p in box)
            text_bottom = max(p[1] for p in box)
            
            # 方式1：文字在框内部（菜单/按钮）
            overlap_x = max(0, min(x2, text_right) - max(x1, text_left))
            overlap_y = max(0, min(y2, text_bottom) - max(y1, text_top))
            text_width = text_right - text_left
            text_height = text_bottom - text_top
            
            if text_width > 0 and text_height > 0:
                overlap_ratio = (overlap_x * overlap_y) / (text_width * text_height)
                if overlap_ratio > 0.5:  # 文字50%以上在框内
                    candidates.append({
                        'text': text,
                        'confidence': confidence,
                        'distance': 0,  # 内部匹配优先
                        'type': 'inside'
                    })
                    continue
            
            # 方式2：文字在框下方（桌面图标）
            v_dist = text_top - y2  # 文字顶部 - 框底部
            h_dist = abs(text_cx - icon_center_x)
            
            if -20 <= v_dist <= 50 and h_dist < icon_width * 1.5:
                candidates.append({
                    'text': text,
                    'confidence': confidence,
                    'distance': abs(v_dist) + h_dist * 0.5 + 10,  # +10让下方匹配优先级低于内部
                    'type': 'below'
                })
        
        if candidates:
            best = min(candidates, key=lambda x: x['distance'])
            return best['text']
        return ""
    
    def _florence_caption(self, icon_img: Image.Image) -> str:
        """Florence-2识别图标"""
        if not self.florence_model or not self.florence_processor:
            return ""
        
        try:
            import torch
            device = next(self.florence_model.parameters()).device
            
            if icon_img.mode != 'RGB':
                icon_img = icon_img.convert('RGB')
            
            prompt = "<CAPTION>"
            inputs = self.florence_processor(
                text=prompt,
                images=icon_img,
                return_tensors="pt"
            ).to(device)
            
            with torch.no_grad():
                generated_ids = self.florence_model.generate(
                    input_ids=inputs["input_ids"],
                    pixel_values=inputs["pixel_values"],
                    max_new_tokens=50,
                    num_beams=2
                )
            
            text = self.florence_processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]
            
            return text.strip()
        except:
            return ""
    
    def _recognize(self, image: np.ndarray, changed_regions: List[Tuple]) -> List[Dict]:
        """执行识别"""
        if not self.detector:
            return []
        
        # 保存临时文件供YOLO使用
        temp_path = self.output_dir / 'temp_capture.png'
        cv2.imwrite(str(temp_path), image)
        
        # YOLO检测
        results = self.detector.predict(
            source=str(temp_path),
            conf=0.35,
            verbose=False
        )
        
        if not results or len(results[0].boxes) == 0:
            return list(self.stable_elements.values())
        
        # OCR识别（大图缩放加速，提速2.3倍）
        ocr_results = None
        if self.ocr:
            h, w = image.shape[:2]
            if w > 1920:
                ocr_scale = 1920 / w
                ocr_img = cv2.resize(image, None, fx=ocr_scale, fy=ocr_scale)
                raw_ocr, _ = self.ocr(ocr_img)
                # 坐标还原到原图
                if raw_ocr:
                    ocr_results = []
                    for item in raw_ocr:
                        box, text, conf = item
                        # box是4个点的坐标，需要放大回原图
                        scaled_box = [[p[0]/ocr_scale, p[1]/ocr_scale] for p in box]
                        ocr_results.append((scaled_box, text, conf))
            else:
                ocr_results, _ = self.ocr(str(temp_path))
        
        # 处理每个检测结果
        pil_img = Image.open(temp_path)
        elements = []
        new_stable = {}
        
        for box in results[0].boxes:
            xyxy = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0])
            bbox = [int(x) for x in xyxy]
            
            sig = self._get_element_signature(bbox)
            
            # 检查是否在变化区域
            in_changed = self._is_in_changed_region(bbox, changed_regions)
            
            # 如果不在变化区域且之前已识别，复用
            if not in_changed and sig in self.stable_elements:
                elem = self.stable_elements[sig].copy()
                new_stable[sig] = elem
                elements.append(elem)
                continue
            
            # 需要重新识别
            label = ""
            method = "yolo"
            
            # 1. 尝试OCR
            if ocr_results:
                label = self._ocr_find_label(bbox, ocr_results)
                if label:
                    method = "ocr"
            
            # 2. 尝试Florence-2
            if not label and self.enable_florence:
                icon_img = pil_img.crop(tuple(bbox))
                label = self._florence_caption(icon_img)
                if label:
                    method = "florence"
            
            # 3. 生成编号
            if not label:
                self.element_index += 1
                label = f"Icon_{self.element_index}"
            
            elem = {
                'index': self.element_index if 'Icon_' in label else None,
                'bbox': bbox,
                'center': [(bbox[0]+bbox[2])//2, (bbox[1]+bbox[3])//2],
                'label': label,
                'method': method,
                'confidence': conf
            }
            
            if 'Icon_' not in label:
                # 有意义的标签，记录稳定元素
                new_stable[sig] = elem
            
            elements.append(elem)
        
        # 更新稳定元素
        self.stable_elements = new_stable
        
        # 添加OCR独立文字（没有匹配到YOLO框的文字，如菜单栏File/Edit等）
        # 用黄色标注，区分YOLO框内的绿色OCR
        # 使用稳定缓存，避免每次识别都变化
        if ocr_results:
            matched_texts = {e['label'] for e in elements if e.get('method') == 'ocr'}
            # 收集所有已识别元素的边界框（包括YOLO和绿色OCR）
            existing_boxes = [e['bbox'] for e in elements]
            
            new_ocr_texts = {}  # 本次识别的OCR文字
            
            for item in ocr_results:
                box, text, conf = item
                text = text.strip()
                if len(text) < 2 or conf < 0.7:
                    continue
                if text in matched_texts:
                    continue
                # 过滤纯数字和特殊字符
                if text.isdigit() or text[0] in '×·…@#$%^&*()[]{}|<>/\\-+':
                    continue
                # 过滤太长的文本（放宽到20字符）
                if len(text) > 20:
                    continue
                # 过滤纯符号组合
                if all(c in '.-_+=[]{}()0123456789' for c in text):
                    continue
                
                # 计算边界框
                x_coords = [p[0] for p in box]
                y_coords = [p[1] for p in box]
                bbox = [int(min(x_coords)), int(min(y_coords)), 
                        int(max(x_coords)), int(max(y_coords))]
                
                # 检查是否与已有元素重叠（避免重复识别）
                ocr_cx, ocr_cy = (bbox[0]+bbox[2])//2, (bbox[1]+bbox[3])//2
                overlapped = False
                for ebox in existing_boxes:
                    # 检查中心点是否在已有框内，或框大面积重叠
                    if ebox[0]-5 <= ocr_cx <= ebox[2]+5 and ebox[1]-5 <= ocr_cy <= ebox[3]+5:
                        overlapped = True
                        break
                    # 检查边界框重叠
                    ox = max(0, min(bbox[2], ebox[2]) - max(bbox[0], ebox[0]))
                    oy = max(0, min(bbox[3], ebox[3]) - max(bbox[1], ebox[1]))
                    if ox > 0 and oy > 0:
                        overlap_area = ox * oy
                        bbox_area = (bbox[2]-bbox[0]) * (bbox[3]-bbox[1])
                        if bbox_area > 0 and overlap_area / bbox_area > 0.3:
                            overlapped = True
                            break
                if overlapped:
                    continue
                
                # 分词处理（按空格或大写字母分割，如"FileEditSelection"）
                words = text.split()
                if len(words) == 1 and len(text) > 6:
                    import re
                    words = re.findall(r'[A-Z][a-z]*|[a-z]+|[\u4e00-\u9fff]+', text)
                    words = [w for w in words if len(w) >= 2]
                
                if len(words) > 1:
                    total_len = sum(len(w) for w in words)
                    bbox_width = bbox[2] - bbox[0]
                    x_start = bbox[0]
                    for word in words:
                        if len(word) < 2:
                            continue
                        word_width = int(bbox_width * len(word) / total_len)
                        word_bbox = [x_start, bbox[1], x_start + word_width, bbox[3]]
                        word_cx = (word_bbox[0]+word_bbox[2])//2
                        word_cy = (word_bbox[1]+word_bbox[3])//2
                        new_ocr_texts[word] = {'bbox': word_bbox, 'center': [word_cx, word_cy], 'conf': conf}
                        x_start += word_width
                else:
                    new_ocr_texts[text] = {'bbox': bbox, 'center': [ocr_cx, ocr_cy], 'conf': conf}
            
            # 稳定性处理 + 去重：避免OCR独立文字之间重叠
            added_ocr_boxes = []  # 已添加的OCR框，用于检查重叠
            for label, data in new_ocr_texts.items():
                # 使用缓存位置（如果有且位置相近）
                if label in self.stable_ocr_texts:
                    cached = self.stable_ocr_texts[label]
                    dx = abs(data['center'][0] - cached['center'][0])
                    dy = abs(data['center'][1] - cached['center'][1])
                    if dx < self.ocr_stable_threshold and dy < self.ocr_stable_threshold:
                        data = cached
                
                # 检查是否与已添加的OCR框重叠
                bbox = data['bbox']
                cx, cy = data['center']
                skip = False
                for added_box in added_ocr_boxes:
                    # 检查中心点是否在已有框内
                    if added_box[0] <= cx <= added_box[2] and added_box[1] <= cy <= added_box[3]:
                        skip = True
                        break
                    # 检查边界框重叠面积
                    ox = max(0, min(bbox[2], added_box[2]) - max(bbox[0], added_box[0]))
                    oy = max(0, min(bbox[3], added_box[3]) - max(bbox[1], added_box[1]))
                    if ox > 0 and oy > 0:
                        overlap = ox * oy
                        area = (bbox[2]-bbox[0]) * (bbox[3]-bbox[1])
                        if area > 0 and overlap / area > 0.3:
                            skip = True
                            break
                
                if skip:
                    continue
                
                added_ocr_boxes.append(bbox)
                elements.append({
                    'index': None,
                    'bbox': bbox,
                    'center': [cx, cy],
                    'label': label,
                    'method': 'ocr',
                    'confidence': data['conf'],
                    'standalone_ocr': True
                })
            
            # 更新稳定缓存
            self.stable_ocr_texts = new_ocr_texts
        
        # 清理临时文件
        try:
            temp_path.unlink()
        except:
            pass
        
        return elements
    
    def _draw_annotations(self, image: np.ndarray, elements: List[Dict]) -> np.ndarray:
        """绘制标注（支持中文，红色图标显示稳定数字编号）
        
        ID稳定性机制（参考canvas系统）：
        1. 位置匹配：中心点距离<阈值视为同一元素，保持原ID
        2. ID回收：消失的元素ID被新元素复用
        3. 紧凑编号：确保ID从1开始连续
        """
        # 转换为PIL图像以支持中文
        img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # 加载中文字体
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
            font_large = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 14)
                font_large = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 18)
            except:
                font = ImageFont.load_default()
                font_large = font
        
        # 第一步：收集所有红色图标元素
        current_icons = []
        for elem in elements:
            label = elem['label']
            method = elem.get('method', 'unknown')
            if 'Icon_' in label or method == 'yolo':
                bbox = elem.get('bbox_relative') or elem.get('bbox')
                cx, cy = (bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2
                current_icons.append({
                    'elem': elem,
                    'cx': cx, 'cy': cy,
                    'bbox': bbox
                })
        
        # 第二步：按位置排序（从上到下，从左到右）
        current_icons.sort(key=lambda e: (int(e['cy'] / 50) * 10000 + e['cx']))
        
        # 第三步：ID稳定性匹配
        used_ids = set()
        new_icon_list = []
        
        if self.last_icon_elements:
            # 匹配阶段：找位置相近的旧元素
            unmatched = []
            for icon in current_icons:
                best_match = None
                best_dist = self.icon_match_threshold
                
                for old in self.last_icon_elements:
                    if old['id'] in used_ids:
                        continue
                    dx = icon['cx'] - old['cx']
                    dy = icon['cy'] - old['cy']
                    dist = (dx*dx + dy*dy) ** 0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_match = old
                
                if best_match:
                    icon['id'] = best_match['id']
                    used_ids.add(icon['id'])
                    new_icon_list.append({'id': icon['id'], 'cx': icon['cx'], 'cy': icon['cy']})
                else:
                    unmatched.append(icon)
            
            # 回收阶段：消失的ID给新元素
            old_ids = set(e['id'] for e in self.last_icon_elements)
            recycled = sorted(old_ids - used_ids)
            
            for icon in unmatched:
                if recycled:
                    icon['id'] = recycled.pop(0)
                else:
                    all_used = used_ids | set(e['id'] for e in new_icon_list)
                    nid = 1
                    while nid in all_used:
                        nid += 1
                    icon['id'] = nid
                used_ids.add(icon['id'])
                new_icon_list.append({'id': icon['id'], 'cx': icon['cx'], 'cy': icon['cy']})
        else:
            # 首次识别
            for i, icon in enumerate(current_icons, 1):
                icon['id'] = i
                new_icon_list.append({'id': i, 'cx': icon['cx'], 'cy': icon['cy']})
        
        # 更新状态
        self.last_icon_elements = new_icon_list
        
        # 第四步：绘制所有元素
        for elem in elements:
            bbox = elem.get('bbox_relative') or elem.get('bbox')
            label = elem['label']
            method = elem.get('method', 'unknown')
            is_standalone_ocr = elem.get('standalone_ocr', False)  # OCR独立文字标记
            
            # 颜色：OCR独立文字用黄色，YOLO框内OCR用绿色
            if is_standalone_ocr:
                color = (255, 255, 0)  # 黄色：OCR独立文字
            elif method == 'ocr':
                color = (0, 255, 0)    # 绿色：YOLO框内OCR
            elif method == 'florence':
                color = (0, 0, 255)    # 蓝色：Florence
            else:
                color = (255, 0, 0)    # 红色：YOLO图标
            
            # 画框
            draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], outline=color, width=2)
            
            # 红色图标：显示稳定编号（放在框左上角外侧，避免遮挡）
            if 'Icon_' in label or method == 'yolo':
                cx, cy = (bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2
                icon_id = None
                for icon in current_icons:
                    if icon['cx'] == cx and icon['cy'] == cy:
                        icon_id = icon.get('id')
                        break
                
                if icon_id:
                    num_str = str(icon_id)
                    # 编号放在框左上角外侧（上方偏左）
                    x, y = bbox[0] - 2, bbox[1] - 20
                    # 确保不超出图像边界
                    if y < 2:
                        y = bbox[1] + 2  # 如果上方空间不够，放在框内顶部
                    if x < 2:
                        x = 2
                    # 黑色描边（加粗）
                    for dx, dy in [(-2,0), (2,0), (0,-2), (0,2), (-1,-1), (-1,1), (1,-1), (1,1), (-2,-1), (-2,1), (2,-1), (2,1), (-2,-2), (2,-2), (-2,2), (2,2)]:
                        draw.text((x+dx, y+dy), num_str, font=font_large, fill=(0, 0, 0))
                    # 青色文字（各种背景都清晰）
                    draw.text((x, y), num_str, font=font_large, fill=(0, 255, 255))
                    elem['icon_number'] = icon_id
            else:
                # OCR/Florence：显示文字标签
                label_short = label[:15] if len(label) > 15 else label
                text_bbox = draw.textbbox((bbox[0], bbox[1]-18), label_short, font=font)
                draw.rectangle(text_bbox, fill=(0, 0, 0))
                draw.text((bbox[0], bbox[1]-18), label_short, font=font, fill=color)
        
        # 转回OpenCV格式
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    def _save_results(self, elements: List[Dict], image: np.ndarray, title: str, window_rect: Tuple, client_offset: Tuple = (0, 0)):
        """保存结果"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        
        # 获取DPI缩放比例（仅用于记录）
        dpi_scale = get_dpi_scale()
        
        # 窗口左上角位置
        # 注意：启用DPI感知后，GetWindowRect已经返回物理像素坐标
        win_x, win_y = window_rect[0], window_rect[1]
        # 客户区偏移（标题栏+边框）
        offset_x, offset_y = client_offset
        
        for elem in elements:
            # 保留原始相对坐标（截图内的相对坐标）
            elem['bbox_relative'] = elem['bbox'].copy()
            
            # bbox转换为屏幕绝对坐标
            # 截图是从window_rect开始的（包含标题栏+边框）
            # 所以直接用window_rect的左上角坐标，不需要额外加client_offset
            # 因为截图内的坐标已经是相对于整个窗口（包括标题栏）的
            elem['bbox_screen'] = [
                elem['bbox'][0] + win_x,
                elem['bbox'][1] + win_y,
                elem['bbox'][2] + win_x,
                elem['bbox'][3] + win_y
            ]
            # center转换（这是点击用的坐标）
            elem['center'] = [
                elem['bbox_screen'][0] + (elem['bbox_screen'][2] - elem['bbox_screen'][0]) // 2,
                elem['bbox_screen'][1] + (elem['bbox_screen'][3] - elem['bbox_screen'][1]) // 2
            ]
        
        # 分类元素：YOLO图标、YOLO框内OCR、OCR独立文字（黄色）
        yolo_icons = []      # 红色框+青色编号
        yolo_ocr = []        # 绿色框
        standalone_ocr = []  # 黄色框（排后面）
        
        for e in elements:
            if e.get('standalone_ocr'):
                standalone_ocr.append(e)
            elif 'Icon_' in e.get('label', '') or e.get('method') == 'yolo':
                yolo_icons.append(e)
            else:
                yolo_ocr.append(e)
        
        # 排序：YOLO图标 → YOLO框内OCR → OCR独立文字（黄色排后面）
        sorted_elements = yolo_icons + yolo_ocr + standalone_ocr
        
        # JSON数据
        json_data = {
            'timestamp': timestamp,
            'window': title,
            'window_rect': list(window_rect),
            'dpi_scale': dpi_scale,
            'client_offset': list(client_offset),
            'element_count': len(sorted_elements),
            'note': '坐标说明: center和bbox_screen是物理像素坐标(可直接用于pyautogui点击), bbox_relative是截图内相对坐标',
            # 分类索引（方便查询）
            'index': {
                'by_label': {e['label']: e['center'] for e in sorted_elements if e.get('label')},
                'yolo_icons': {e['label']: e['center'] for e in yolo_icons},
                'yolo_ocr': {e['label']: e['center'] for e in yolo_ocr if e.get('label')},
                'standalone_ocr': {e['label']: e['center'] for e in standalone_ocr if e.get('label')}
            },
            # 分类统计
            'category_count': {
                'yolo_icons': len(yolo_icons),
                'yolo_ocr': len(yolo_ocr),
                'standalone_ocr': len(standalone_ocr)
            },
            'elements': sorted_elements
        }
        
        # 先绘制标注（会给元素添加icon_number）
        annotated = self._draw_annotations(image, elements)
        
        # 添加编号索引到JSON
        icon_index = {e['icon_number']: e['center'] for e in elements if e.get('icon_number')}
        json_data['icon_index'] = icon_index
        
        # 异步写入
        def write_files():
            # JSON
            json_path = self.output_dir / 'latest_vision.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            # 标注图片
            img_path = self.output_dir / 'latest_vision.png'
            cv2.imwrite(str(img_path), annotated)
        
        self._executor.submit(write_files)
    
    def _scan_once(self):
        """单次扫描"""
        hwnd, title, rect, client_offset = self._get_foreground_window()
        if not hwnd:
            return
        
        # 截图
        image = self._capture_window(rect)
        if image is None:
            return
        
        self.scan_count += 1
        
        # 计算哈希
        current_hash = self._calc_image_hash(image)
        
        # 检查是否有强制刷新信号
        force_refresh = False
        signal_file = self.output_dir / '.force_refresh'
        if signal_file.exists():
            force_refresh = True
            signal_file.unlink()  # 删除信号文件
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 强制刷新触发")
        
        # 检查是否需要重新识别
        if self.last_image_hash and not force_refresh:
            similarity = self._hash_similarity(current_hash, self.last_image_hash)
            if similarity > self.cache_similarity:
                # 几乎没变化，使用缓存但保存带标注的截图
                self.cache_count += 1
                # 如果有上次的识别结果，重新绘制标注
                if hasattr(self, 'last_elements') and self.last_elements:
                    annotated = self._draw_annotations(image, self.last_elements)
                    img_path = self.output_dir / 'latest_vision.png'
                    self._executor.submit(lambda img=annotated: cv2.imwrite(str(img_path), img))
                return
        
        # 检测变化区域
        changed_regions = self._detect_changed_regions(image, self.last_image)
        
        # 识别
        elements = self._recognize(image, changed_regions)
        
        # 保存（传递窗口rect和客户区偏移用于精确坐标转换）
        self._save_results(elements, image, title, rect, client_offset)
        
        # 更新状态
        self.last_image = image.copy()
        self.last_image_hash = current_hash
        self.last_elements = elements  # 保存识别结果用于缓存时重绘标注
        
        # 输出统计
        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"扫描{self.scan_count} | 缓存{self.cache_count} | "
              f"元素{len(elements)} | 变化区{len(changed_regions)}")
    
    def run(self):
        """运行监控"""
        self.running = True
        
        print(f"\n{'─'*60}")
        print(f"🎯 开始视觉监控")
        print(f"📁 输出: {self.output_dir}/latest_vision.json")
        print(f"📸 截图: {self.output_dir}/latest_vision.png")
        print(f"按 Ctrl+C 停止")
        print(f"{'─'*60}\n")
        
        try:
            while self.running:
                self._scan_once()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print(f"\n✅ 已停止")
            self.running = False
            print(f"📊 统计: 扫描{self.scan_count}次，缓存命中{self.cache_count}次")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='视觉识别监控系统')
    parser.add_argument('--interval', type=float, default=1.0, help='刷新间隔（秒）')
    parser.add_argument('--florence', action='store_true', help='启用Florence-2')
    parser.add_argument('--weights', type=str, default=None, help='模型权重目录')
    
    args = parser.parse_args()
    
    monitor = VisionMonitor(
        interval=args.interval,
        weights_dir=args.weights,
        enable_florence=args.florence
    )
    monitor.run()


if __name__ == '__main__':
    main()
