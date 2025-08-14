"""
UI Style Management Module
Manages all styles and themes for the application
"""

import streamlit as st
import base64
import pandas as pd
from io import StringIO, BytesIO
from PIL import Image
import json
import tempfile
import os
from pathlib import Path

class FilePreviewGenerator:
    """File Preview Generator - Generates real content previews based on file types"""
    
    @staticmethod
    def generate_preview_html(uploaded_file, max_preview_size=50):
        """
        Generate preview HTML content for files
        
        Args:
            uploaded_file: Streamlit uploaded file object
            max_preview_size: Maximum number of lines/characters for preview
            
        Returns:
            str: HTML string of preview content
        """
        try:
            filename = uploaded_file.name
            file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
            file_size = uploaded_file.size
            
            # 重置文件指针到开始位置
            uploaded_file.seek(0)
            
            # 根据文件类型生成不同的预览
            if file_ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg']:
                return FilePreviewGenerator._generate_image_preview(uploaded_file)
            elif file_ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv']:
                return FilePreviewGenerator._generate_video_preview(uploaded_file)
            elif file_ext in ['mp3', 'wav', 'aac', 'ogg', 'flac']:
                return FilePreviewGenerator._generate_audio_preview(uploaded_file)
            elif file_ext in ['csv']:
                return FilePreviewGenerator._generate_csv_preview(uploaded_file, max_preview_size)
            elif file_ext in ['xlsx', 'xls']:
                return FilePreviewGenerator._generate_excel_preview(uploaded_file, max_preview_size)
            elif file_ext in ['json']:
                return FilePreviewGenerator._generate_json_preview(uploaded_file, max_preview_size)
            elif file_ext in ['txt', 'md', 'markdown']:
                return FilePreviewGenerator._generate_text_preview(uploaded_file, max_preview_size)
            elif file_ext in ['pdf']:
                return FilePreviewGenerator._generate_pdf_preview(uploaded_file)
            elif file_ext in ['doc', 'docx']:
                return FilePreviewGenerator._generate_doc_preview(uploaded_file)
            elif file_ext in ['ppt', 'pptx']:
                return FilePreviewGenerator._generate_ppt_preview(uploaded_file)
            else:
                return FilePreviewGenerator._generate_generic_preview(uploaded_file, max_preview_size)
                
        except Exception as e:
            # 如果预览生成失败，返回默认图标
            return FilePreviewGenerator._get_fallback_icon(file_ext)
        finally:
            # 确保文件指针重置
            try:
                uploaded_file.seek(0)
            except:
                pass
    
    @staticmethod
    def _generate_image_preview(uploaded_file):
        """生成图片预览"""
        try:
            # 读取图片数据
            image_data = uploaded_file.read()
            
            # 使用PIL处理图片
            image = Image.open(BytesIO(image_data))
            
            # 创建固定尺寸的缩略图 - 与容器高度匹配
            container_size = (80, 80)
            
            # 计算保持宽高比的缩放尺寸
            image.thumbnail(container_size, Image.Resampling.LANCZOS)
            
            # 创建一个固定尺寸的画布，居中放置缩略图
            canvas = Image.new('RGBA', container_size, (255, 255, 255, 0))  # 透明背景
            
            # 计算居中位置
            x = (container_size[0] - image.width) // 2
            y = (container_size[1] - image.height) // 2
            
            # 将图片粘贴到画布中央
            canvas.paste(image, (x, y))
            
            # 转换为base64
            buffer = BytesIO()
            canvas.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # 返回优化的HTML，确保图片完美适配容器
            return f'''<img src="data:image/png;base64,{img_str}" 
                style="width: 80px; height: 80px; object-fit: contain; border-radius: 0.5rem; display: block; margin: 0 auto;">'''
            
        except Exception:
            return '🖼️'
    
    @staticmethod
    def _generate_csv_preview(uploaded_file, max_rows=4):
        """生成CSV文件预览"""
        try:
            # 读取CSV文件
            content = uploaded_file.read().decode('utf-8')
            df = pd.read_csv(StringIO(content))
            
            # 获取前几行数据
            preview_df = df.head(max_rows)
            
            # 限制列数，避免过宽
            if len(preview_df.columns) > 3:
                preview_df = preview_df.iloc[:, :3]
                cols_truncated = len(df.columns) - 3
            else:
                cols_truncated = 0
            
            # 生成HTML表格 - 优化容器适配
            html = '<div style="width: 100%; height: 100%; font-size: 0.6rem; padding: 0.25rem; overflow: hidden; display: flex; flex-direction: column; justify-content: center;">'
            html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.5rem;">'
            
            # 表头
            html += '<tr>'
            for col in preview_df.columns:
                col_name = col[:6] + '..' if len(str(col)) > 6 else str(col)
                html += f'<th style="background: #f1f5f9; padding: 0.1rem; border: 1px solid #e2e8f0; font-size: 0.45rem; line-height: 1;">{col_name}</th>'
            html += '</tr>'
            
            # 数据行 - 限制显示行数以适应容器
            display_rows = min(len(preview_df), 3)
            for _, row in preview_df.head(display_rows).iterrows():
                html += '<tr>'
                for val in row:
                    val_str = str(val)[:4] + '..' if len(str(val)) > 4 else str(val)
                    html += f'<td style="padding: 0.1rem; border: 1px solid #e2e8f0; font-size: 0.4rem; line-height: 1; text-align: center;">{val_str}</td>'
                html += '</tr>'
            
            html += '</table>'
            
            # 显示数据统计 - 简化版本
            if len(df) > display_rows or cols_truncated > 0:
                html += f'<div style="text-align: center; margin-top: 0.2rem; font-size: 0.35rem; color: #64748b; line-height: 1;">'
                html += f'{len(df)}×{len(df.columns)}'
                html += '</div>'
            
            html += '</div>'
            return html
            
        except Exception:
            return '📊'
    
    @staticmethod
    def _generate_excel_preview(uploaded_file, max_rows=4):
        """生成Excel文件预览"""
        try:
            # 读取Excel文件的第一个工作表
            df = pd.read_excel(uploaded_file, nrows=max_rows)
            
            # 限制列数
            if len(df.columns) > 3:
                df = df.iloc[:, :3]
            
            # 生成类似CSV的预览 - 优化容器适配
            html = '<div style="width: 100%; height: 100%; font-size: 0.6rem; padding: 0.25rem; overflow: hidden; display: flex; flex-direction: column; justify-content: center;">'
            html += '<div style="background: #10b981; color: white; padding: 0.1rem; text-align: center; font-size: 0.4rem; margin-bottom: 0.2rem; border-radius: 0.2rem;">Excel</div>'
            html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.5rem;">'
            
            # 表头
            html += '<tr>'
            for col in df.columns:
                col_name = col[:6] + '..' if len(str(col)) > 6 else str(col)
                html += f'<th style="background: #f1f5f9; padding: 0.1rem; border: 1px solid #e2e8f0; font-size: 0.45rem; line-height: 1;">{col_name}</th>'
            html += '</tr>'
            
            # 数据行 - 限制显示行数
            display_rows = min(len(df), 2)
            for _, row in df.head(display_rows).iterrows():
                html += '<tr>'
                for val in row:
                    val_str = str(val)[:4] + '..' if len(str(val)) > 4 else str(val)
                    html += f'<td style="padding: 0.1rem; border: 1px solid #e2e8f0; font-size: 0.4rem; line-height: 1; text-align: center;">{val_str}</td>'
                html += '</tr>'
            
            html += '</table></div>'
            return html
            
        except Exception:
            return '📈'
    
    @staticmethod
    def _generate_json_preview(uploaded_file, max_items=6):
        """生成JSON文件预览"""
        try:
            content = uploaded_file.read().decode('utf-8')
            data = json.loads(content)
            
            html = '<div style="width: 100%; height: 100%; font-size: 0.55rem; padding: 0.25rem; font-family: monospace; background: #f8fafc; border-radius: 0.25rem; overflow: hidden; display: flex; align-items: center; justify-content: center;">'
            
            # 递归显示JSON结构（简化版，更紧凑）
            def format_json_preview(obj, level=0, max_level=1):
                if level > max_level:
                    return "..."
                
                if isinstance(obj, dict):
                    items = list(obj.items())[:2]  # 只显示前2个键值对
                    result = "{"
                    for i, (k, v) in enumerate(items):
                        if i > 0:
                            result += ","
                        result += f'<br>{"&nbsp;" * (level * 1)}<span style="color: #dc2626;">"{k[:6]}"</span>: {format_json_preview(v, level + 1, max_level)}'
                    if len(obj) > 2:
                        result += f'<br>{"&nbsp;" * (level * 1)}<span style="color: #64748b;">...{len(obj) - 2}</span>'
                    result += f'<br>{"&nbsp;" * ((level - 1) * 1 if level > 0 else 0)}}}'
                    return result
                elif isinstance(obj, list):
                    if len(obj) == 0:
                        return "[]"
                    items = obj[:1]  # 只显示第1个元素
                    result = "["
                    for i, item in enumerate(items):
                        if i > 0:
                            result += ","
                        result += f'<br>{"&nbsp;" * (level * 1)}{format_json_preview(item, level + 1, max_level)}'
                    if len(obj) > 1:
                        result += f'<br>{"&nbsp;" * (level * 1)}<span style="color: #64748b;">...{len(obj) - 1}</span>'
                    result += f'<br>{"&nbsp;" * ((level - 1) * 1 if level > 0 else 0)}]'
                    return result
                elif isinstance(obj, str):
                    if len(obj) > 6:
                        return f'<span style="color: #059669;">"{obj[:6]}..."</span>'
                    return f'<span style="color: #059669;">"{obj}"</span>'
                else:
                    return f'<span style="color: #0369a1;">{str(obj)[:6]}</span>'
            
            html += format_json_preview(data)
            html += '</div>'
            return html
            
        except Exception:
            return '📋'
    
    @staticmethod
    def _generate_text_preview(uploaded_file, max_lines=4):
        """生成文本文件预览"""
        try:
            content = uploaded_file.read().decode('utf-8')
            lines = content.split('\n')[:max_lines]
            
            html = '<div style="width: 100%; height: 100%; font-size: 0.55rem; padding: 0.25rem; font-family: monospace; background: #f8fafc; border-radius: 0.25rem; overflow: hidden; display: flex; flex-direction: column; justify-content: center; line-height: 1.1;">'
            
            for i, line in enumerate(lines):
                # 限制每行长度以适应小容器
                if len(line) > 15:
                    line = line[:15] + '..'
                
                # 简单的Markdown高亮
                if line.startswith('#'):
                    html += f'<div style="color: #dc2626; font-weight: bold; font-size: 0.5rem;">{line}</div>'
                elif line.startswith('*') or line.startswith('-'):
                    html += f'<div style="color: #059669; font-size: 0.5rem;">• {line[1:].strip()}</div>'
                else:
                    html += f'<div style="color: #334155; font-size: 0.5rem;">{line}</div>'
            
            # 修复f-string中的反斜杠问题
            total_lines = len(content.split('\n'))
            if total_lines > max_lines:
                remaining_lines = total_lines - max_lines
                html += f'<div style="color: #64748b; text-align: center; margin-top: 0.2rem; font-size: 0.4rem;">+{remaining_lines}</div>'
            
            html += '</div>'
            return html
            
        except Exception:
            return '📄'
    
    @staticmethod
    def _generate_pdf_preview(uploaded_file):
        """生成PDF文件预览"""
        try:
            # PDF预览比较复杂，这里显示文件信息
            file_size = uploaded_file.size
            
            html = '<div style="width: 100%; height: 100%; font-size: 0.6rem; padding: 0.25rem; text-align: center; background: #fef2f2; border-radius: 0.25rem; display: flex; flex-direction: column; justify-content: center; align-items: center;">'
            html += '<div style="color: #dc2626; font-size: 1.8rem; margin-bottom: 0.2rem;">📕</div>'
            html += '<div style="color: #7f1d1d; font-size: 0.5rem; font-weight: bold;">PDF</div>'
            
            if file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.0f}K"
            else:
                size_str = f"{file_size / (1024 * 1024):.1f}M"
            
            html += f'<div style="color: #991b1b; font-size: 0.4rem; margin-top: 0.1rem;">{size_str}</div>'
            html += '</div>'
            return html
            
        except Exception:
            return '📕'
    
    @staticmethod
    def _generate_doc_preview(uploaded_file):
        """生成Word文档预览"""
        html = '<div style="width: 100%; height: 100%; font-size: 0.6rem; padding: 0.25rem; text-align: center; background: #eff6ff; border-radius: 0.25rem; display: flex; flex-direction: column; justify-content: center; align-items: center;">'
        html += '<div style="color: #2563eb; font-size: 1.8rem; margin-bottom: 0.2rem;">📄</div>'
        html += '<div style="color: #1e40af; font-size: 0.5rem; font-weight: bold;">Word</div>'
        html += '</div>'
        return html
    
    @staticmethod
    def _generate_ppt_preview(uploaded_file):
        """生成PowerPoint文档预览"""
        html = '<div style="width: 100%; height: 100%; font-size: 0.6rem; padding: 0.25rem; text-align: center; background: #fefce8; border-radius: 0.25rem; display: flex; flex-direction: column; justify-content: center; align-items: center;">'
        html += '<div style="color: #ca8a04; font-size: 1.8rem; margin-bottom: 0.2rem;">📊</div>'
        html += '<div style="color: #92400e; font-size: 0.5rem; font-weight: bold;">PowerPoint</div>'
        html += '</div>'
        return html
    
    @staticmethod
    def _generate_generic_preview(uploaded_file, max_chars=60):
        """生成通用文件预览"""
        try:
            # 尝试以文本方式读取
            content = uploaded_file.read().decode('utf-8', errors='ignore')
            if content.strip():
                preview_text = content[:max_chars]
                if len(content) > max_chars:
                    preview_text += '..'
                
                html = '<div style="width: 100%; height: 100%; font-size: 0.5rem; padding: 0.25rem; font-family: monospace; background: #f8fafc; border-radius: 0.25rem; overflow: hidden; display: flex; align-items: center; justify-content: center; text-align: center; line-height: 1.1;">'
                html += f'<div style="color: #334155;">{preview_text}</div>'
                html += '</div>'
                return html
            else:
                return '📁'
                
        except Exception:
            return '📁'
    
    @staticmethod
    def _generate_video_preview(uploaded_file):
        """生成视频文件预览"""
        try:
            # 对于视频文件，返回简单的emoji预览，避免HTML嵌套问题
            return '🎬'
            
        except Exception:
            return '🎬'
    
    @staticmethod
    def _generate_audio_preview(uploaded_file):
        """生成音频文件预览"""
        try:
            # 对于音频文件，返回简单的emoji预览，避免HTML嵌套问题
            return '🎵'
            
        except Exception:
            return '🎵'
    
    @staticmethod
    def _get_fallback_icon(file_ext):
        """获取备用图标"""
        icons = {
            "csv": "📊", "xlsx": "📈", "xls": "📈",
            "json": "📋", "txt": "📄", "pdf": "📕",
            "html": "🌐", "doc": "📄", "docx": "📄",
            "ppt": "📊", "pptx": "📊", "md": "📝", "markdown": "📝",
            "png": "🖼️", "jpg": "🖼️", "jpeg": "🖼️", 
            "gif": "🖼️", "bmp": "🖼️", "svg": "🖼️",
            "mp4": "🎬", "avi": "🎬", "mov": "🎬", "wmv": "🎬", 
            "flv": "🎬", "webm": "🎬", "mkv": "🎬",
            "mp3": "🎵", "wav": "🎵", "aac": "🎵", "ogg": "🎵", "flac": "🎵"
        }
        return icons.get(file_ext, "📁")

class UIStyleManager:
    """UI样式管理器"""
    
    def __init__(self):
        self.current_theme = "dark"
    
    @staticmethod
    def get_main_styles():
        """获取主要样式"""
        return """
        <style>
        /* 导入现代字体 */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* CSS变量定义 */
        :root {
            --primary-color: #6366f1;
            --primary-dark: #4f46e5;
            --secondary-color: #10b981;
            --background-primary: #ffffff;
            --background-secondary: #f1f5f9;
            --background-tertiary: #e2e8f0;
            --text-primary: #1e293b;
            --text-secondary: #334155;
            --text-muted: #64748b;
            --border-color: #cbd5e1;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --error-color: #ef4444;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        
        /* 全局样式重置 */
        .stApp {
            background: linear-gradient(135deg, var(--background-primary) 0%, var(--background-secondary) 100%);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        
        /* 隐藏Streamlit默认元素 */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* 主容器样式 */
        .main-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0;
        }
        
        /* 顶部导航栏样式 */
        .top-navigation {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border-color);
            padding: 1rem 2rem;
            margin: -1rem -1rem 2rem -1rem;
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .nav-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        /* 侧边栏样式优化 */
        .css-1d391kg {
            background: var(--background-secondary);
            border-right: 1px solid var(--border-color);
        }
        
        .sidebar-content {
            padding: 1rem;
        }
        
        /* 新建对话按钮 */
        .new-chat-button {
            width: 100%;
            background: linear-gradient(135deg, var(--primary-color), var(--primary-dark)) !important;
            color: white !important;
            border: none !important;
            border-radius: 1rem !important;
            padding: 1rem !important;
            font-weight: 600 !important;
            margin-bottom: 1.5rem !important;
            transition: all 0.3s ease !important;
            box-shadow: var(--shadow) !important;
        }
        
        .new-chat-button:hover {
            transform: translateY(-2px) !important;
            box-shadow: var(--shadow-lg) !important;
        }
        
        /* 聊天历史样式 */
        .chat-history-section {
            margin-bottom: 2rem;
        }
        
        .section-title {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .chat-history-item {
            background: var(--background-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1rem;
            margin-bottom: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }
        
        .chat-history-item:hover {
            background: var(--background-primary);
            border-color: var(--primary-color);
            transform: translateX(4px);
        }
        
        .chat-history-item.active {
            background: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .chat-preview {
            font-size: 0.875rem;
            color: var(--text-secondary);
            line-height: 1.4;
            margin-bottom: 0.5rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        
        .chat-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75rem;
            color: var(--text-muted);
        }
        
        /* 删除按钮样式 */
        .delete-chat-button {
            background: transparent !important;
            color: var(--text-muted) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 0.5rem !important;
            padding: 0.4rem !important;
            font-size: 0.8rem !important;
            transition: all 0.2s ease !important;
            min-height: 32px !important;
            width: 100% !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        
        .delete-chat-button:hover {
            background: var(--error-color) !important;
            color: white !important;
            border-color: var(--error-color) !important;
            transform: scale(1.05) !important;
        }
        
        .delete-chat-button:active {
            transform: scale(0.95) !important;
        }
        
        /* 聊天项布局优化 */
        .chat-item-container {
            display: flex;
            gap: 0.5rem;
            align-items: stretch;
            margin-bottom: 0.75rem;
        }
        
        .chat-button-container {
            flex: 1;
        }
        
        .delete-button-container {
            width: 40px;
            display: flex;
            align-items: center;
        }
        
        /* 聊天消息样式 */
        .chat-message {
            margin-bottom: 1.5rem;
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message-container {
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            max-width: 80%;
        }
        
        .user-message .message-container {
            margin-left: auto;
            flex-direction: row-reverse;
        }
        
        .message-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            font-size: 1.2rem;
        }
        
        .user-avatar {
            background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
        }
        
        .ai-avatar {
            background: linear-gradient(135deg, var(--secondary-color), #059669);
        }
        
        .message-bubble {
            background: var(--background-secondary);
            border: 1px solid var(--border-color);
            border-radius: 1.25rem;
            padding: 1.25rem;
            position: relative;
        }
        
        .user-message .message-bubble {
            background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
            color: white;
        }
        
        .ai-message .message-bubble {
            background: var(--background-secondary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
        }
        
        .message-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
            font-size: 0.875rem;
            font-weight: 600;
        }
        
        .message-time {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-left: auto;
        }
        
        /* 工具执行样式 */
        .tool-execution {
            background: var(--background-tertiary);
            border: 1px solid var(--warning-color);
            border-radius: 0.75rem;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        .tool-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--warning-color);
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .loading-dots {
            display: inline-flex;
            gap: 0.25rem;
        }
        
        .loading-dots span {
            width: 6px;
            height: 6px;
            background: var(--primary-color);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }
        
        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        
        /* 文件预览样式 */
        .file-preview {
            background: var(--background-primary);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        .file-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
            color: var(--secondary-color);
            font-weight: 600;
        }
        
        /* 输入区域样式 */
        .stChatInput {
            background: var(--background-secondary);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
        }
        
        .stChatInput > div > div > textarea {
            background: transparent;
            border: none;
            color: var(--text-primary);
        }
        
        /* 文件上传区域样式 - 现在通过内联样式处理 */
        
        /* 已上传文件网格 */
        .uploaded-files-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 0.75rem;
            margin-top: 1rem;
        }
        
        .uploaded-file-card {
            background: var(--background-secondary);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 0.75rem;
            transition: all 0.3s ease;
            cursor: default;
            position: relative;
            overflow: hidden;
        }
        
        .uploaded-file-card:hover {
            border-color: var(--primary-color);
            transform: translateY(-2px);
            box-shadow: var(--shadow);
        }
        
        .file-thumbnail {
            width: 100%;
            height: 80px;
            border-radius: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--background-primary), var(--background-tertiary));
            border: 1px solid var(--border-color);
            overflow: hidden;
            position: relative;
        }
        
        .file-thumbnail img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            border-radius: 0.5rem;
        }
        
        /* 确保非图片内容也能正确居中显示 */
        .file-thumbnail > div {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        
        .file-card-info {
            text-align: center;
        }
        
        .file-card-name {
            font-weight: 600;
            color: var(--text-primary);
            font-size: 0.8rem;
            margin-bottom: 0.25rem;
            word-break: break-word;
            line-height: 1.2;
        }
        
        .file-card-size {
            font-size: 0.7rem;
            color: var(--text-muted);
        }
        
        /* 按钮样式优化 */
        .stButton > button {
            background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
            color: white;
            border: none;
            border-radius: 0.75rem;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            transition: all 0.2s;
            box-shadow: var(--shadow);
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        
        /* 展开器样式 */
        .streamlit-expanderHeader {
            background: var(--background-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            color: var(--text-primary);
        }
        
        .streamlit-expanderContent {
            background: var(--background-secondary);
            border: 1px solid var(--border-color);
            border-top: none;
            border-radius: 0 0 0.5rem 0.5rem;
        }
        
        /* 代码块样式 */
        .stCode {
            background: var(--background-primary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
        }
        
        /* 滚动条样式 */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--background-secondary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--primary-color);
        }
        
        /* 响应式设计 */
        @media (max-width: 768px) {
            .message-container {
                max-width: 95%;
            }
            
            .message-bubble {
                padding: 1rem;
            }
            
            .top-navigation {
                padding: 0.75rem 1rem;
            }
        }
        </style>
        """
    
    @staticmethod
    def get_sidebar_styles():
        """获取侧边栏专用样式"""
        return """
        <style>
        .sidebar-button {
            width: 100%;
            background: transparent !important;
            color: var(--text-secondary) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 0.75rem !important;
            padding: 0.75rem 1rem !important;
            text-align: left !important;
            margin: 0.25rem 0 !important;
            transition: all 0.2s ease !important;
        }
        
        .sidebar-button:hover {
            background: var(--background-primary) !important;
            border-color: var(--primary-color) !important;
            transform: translateX(4px) !important;
        }
        
        .sidebar-button.active {
            background: var(--primary-color) !important;
            border-color: var(--primary-color) !important;
            color: white !important;
        }
        </style>
        """
    
    def apply_main_styles(self):
        """应用主要样式"""
        st.markdown(self.get_main_styles(), unsafe_allow_html=True)
    
    def apply_sidebar_styles(self):
        """应用侧边栏样式"""
        st.markdown(self.get_sidebar_styles(), unsafe_allow_html=True)

class UIComponentRenderer:
    """UI组件渲染器"""
    
    @staticmethod
    def render_top_navigation(title="Finance DeepResearch Assistant", user_name="User"):
        """渲染顶部导航栏"""
        st.markdown(f"""
        <div class="top-navigation">
            <div class="nav-content">
                <div class="logo">✨ {title}</div>
                <div style="color: var(--text-secondary);">
                    Welcome, {user_name}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def render_chat_message(content, role="user", avatar="👤", timestamp=None):
        """渲染聊天消息"""
        import datetime
        
        if timestamp is None:
            timestamp = datetime.datetime.now().strftime("%H:%M")
        
        is_user = role == "user"
        message_class = "user-message" if is_user else "ai-message"
        avatar_class = "user-avatar" if is_user else "ai-avatar"
        
        st.markdown(f"""
        <div class="chat-message {message_class}">
            <div class="message-container">
                <div class="message-avatar {avatar_class}">{avatar}</div>
                <div class="message-bubble">
                    <div class="message-header">
                        {role.title()}
                        <div class="message-time">{timestamp}</div>
                    </div>
                    <div>{content}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def render_tool_execution(tool_name, status="running"):
        """Render tool execution status"""
        if status == "running":
            dots = '<div class="loading-dots"><span></span><span></span><span></span></div>'
            st.markdown(f"""
            <div class="tool-execution">
                <div class="tool-header">
                    🧠 Running {tool_name}
                    {dots}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="tool-execution">
                <div class="tool-header">
                    ✅ {tool_name} completed
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    @staticmethod
    def render_file_preview(filename, content_preview="", file_type="unknown"):
        """渲染文件预览"""
        icons = {
            "csv": "📊",
            "xlsx": "📈", 
            "json": "📋",
            "txt": "📄",
            "pdf": "📕",
            "html": "🌐",
            "png": "🖼️",
            "jpg": "🖼️",
            "jpeg": "🖼️"
        }
        
        icon = icons.get(file_type.lower(), "📁")
        
        st.markdown(f"""
        <div class="file-preview">
            <div class="file-header">
                {icon} {filename}
            </div>
            <div>{content_preview}</div>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def render_file_upload_area():
        """渲染文件上传区域 - 合并自定义样式和原生上传器"""
        import streamlit as st
        
        # 获取动态key，用于重置文件上传器
        if "file_uploader_key" not in st.session_state:
            st.session_state.file_uploader_key = 0
        uploader_key = f"unified_file_uploader_{st.session_state.file_uploader_key}"
        
        # 使用容器来包装，确保正确的层级关系
        upload_container = st.container()
        
        with upload_container:
            # 添加自定义样式，让原生上传器看起来像我们的设计
            st.markdown("""
            <style>
            /* 重写当前页面的文件上传器样式 - 上下分层布局 */
            div[data-testid="stFileUploader"] {
                border: 2px dashed #cbd5e1 !important;
                border-radius: 1rem !important;
                background: linear-gradient(135deg, #f1f5f9, #ffffff) !important;
                padding: 0 !important;
                transition: all 0.3s ease !important;
                min-height: 140px !important;
                display: flex !important;
                flex-direction: column !important;
                position: relative !important;
                overflow: hidden !important;
            }
            
            div[data-testid="stFileUploader"]:hover {
                border-color: #6366f1 !important;
                background: linear-gradient(135deg, #ffffff, rgba(99, 102, 241, 0.05)) !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1) !important;
            }
            
            /* Top layer: Custom description area */
            div[data-testid="stFileUploader"]::before {
                content: "📎 Drag and drop or click to upload files\\ASupports images, documents, data files and more • Multiple files supported" !important;
                display: block !important;
                padding: 1.25rem 1.5rem !important;
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(16, 185, 129, 0.05)) !important;
                border-bottom: 1px solid rgba(203, 213, 225, 0.6) !important;
                color: #4f46e5 !important;
                font-weight: 600 !important;
                font-size: 0.95rem !important;
                text-align: center !important;
                white-space: pre-line !important;
                line-height: 1.6 !important;
                pointer-events: none !important;
                position: relative !important;
            }
            
            /* 下层：Streamlit组件区域 */
            div[data-testid="stFileUploader"] > div {
                flex: 1 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                padding: 1.25rem 1.5rem !important;
                background: transparent !important;
                min-height: 70px !important;
            }
            
            /* 优化原生上传区域 */
            div[data-testid="stFileUploaderDropzone"] {
                width: 100% !important;
                height: 100% !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                text-align: center !important;
                background: rgba(255, 255, 255, 0.9) !important;
                border: 1px dashed #cbd5e1 !important;
                border-radius: 0.5rem !important;
                transition: all 0.3s ease !important;
                padding: 1.25rem !important;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
            }
            
            div[data-testid="stFileUploaderDropzone"]:hover {
                border-color: #6366f1 !important;
                background: rgba(99, 102, 241, 0.08) !important;
                transform: translateY(-1px) !important;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.08) !important;
            }
            
            /* 优化拖拽区域文字 */
            div[data-testid="stFileUploaderDropzone"] span {
                color: #64748b !important;
                font-size: 0.875rem !important;
                font-weight: 500 !important;
            }
            
            /* 隐藏原生标签 */
            div[data-testid="stFileUploader"] label {
                display: none !important;
            }
            
            /* 让整个区域都可以拖拽 */
            div[data-testid="stFileUploader"] {
                cursor: pointer !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # 使用原生文件上传器，但样式已被覆盖，使用动态key
            uploaded_files = st.file_uploader(
                "Choose files", # This label will be hidden by CSS
                accept_multiple_files=True,
                type=['txt', 'csv', 'xlsx', 'xls', 'json', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'doc', 'docx', 'ppt', 'pptx', 'mp4', 'mp3', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', 'wav', 'aac', 'ogg', 'flac'],
                help="Supports multiple file formats including videos and audio",
                label_visibility="collapsed",
                key=uploader_key  # Use dynamic key
            )
        
        return uploaded_files
    
    @staticmethod 
    def render_uploaded_files_grid(uploaded_files):
        """Render grid of uploaded files (with real content preview)"""
        import streamlit as st
        
        if not uploaded_files:
            return
        
        st.markdown("#### 📁 Uploaded Files")
        
        # 创建网格布局
        cols = st.columns(min(len(uploaded_files), 4))  # 最多4列，更紧凑
        
        for i, uploaded_file in enumerate(uploaded_files):
            col_idx = i % 4
            with cols[col_idx]:
                UIComponentRenderer._render_simple_file_card(uploaded_file)
    
    @staticmethod
    def _render_simple_file_card(uploaded_file):
        """Render simplified file card (with real content preview)"""
        import streamlit as st
        
        # 获取文件信息
        filename = uploaded_file.name
        file_size = uploaded_file.size
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        # 格式化文件大小
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        
        # 使用FilePreviewGenerator生成真实的文件内容预览
        preview_content = FilePreviewGenerator.generate_preview_html(uploaded_file)
        
        # 渲染文件卡片
        card_html = f"""
        <div class="uploaded-file-card">
            <div class="file-thumbnail">
                {preview_content}
            </div>
            <div class="file-card-info">
                <div class="file-card-name" title="{filename}">{filename[:15]}{'...' if len(filename) > 15 else ''}</div>
                <div class="file-card-size">{size_str}</div>
            </div>
        </div>
        """
        
        st.markdown(card_html, unsafe_allow_html=True)

class ChatHistoryManager:
    """Chat History Manager"""
    
    @staticmethod
    def render_chat_history_item(chat_id, preview_text, message_count, timestamp, is_active=False):
        """Render individual chat history item"""
        active_class = "active" if is_active else ""
        
        return f"""
        <div class="chat-history-item {active_class}">
            <div class="chat-preview">{preview_text}</div>
            <div class="chat-meta">
                <span>💬 {message_count} messages</span>
                <span>{timestamp}</span>
            </div>
        </div>
        """
    
    @staticmethod
    def get_message_preview(messages, max_length=50):
        """Get message preview text"""
        
        if not messages:
            return "New conversation"
        
        # Get the first user message instead of the last one
        for msg in messages:
            if msg.get('content'):
                content = msg['content']
                if len(content) > max_length:
                    return content[:max_length] + "..."
                return content
        
        return "Chat history"
    
    @staticmethod
    def format_timestamp(timestamp):
        """Format timestamp"""
        import datetime
        
        try:
            if isinstance(timestamp, str):
                # 处理包含下划线的时间戳格式（如 1748465159_7745898）
                if '_' in timestamp:
                    # 提取下划线前的主要时间戳部分
                    main_timestamp = timestamp.split('_')[0]
                    dt = datetime.datetime.fromtimestamp(float(main_timestamp))
                elif '.' in timestamp:
                    # 处理包含小数点的时间戳
                    dt = datetime.datetime.fromtimestamp(float(timestamp))
                elif timestamp.isdigit():
                    # 处理纯数字时间戳
                    dt = datetime.datetime.fromtimestamp(float(timestamp))
                else:
                    # 尝试解析日期时间字符串格式
                    dt = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            else:
                # 处理数字类型的时间戳
                dt = datetime.datetime.fromtimestamp(float(timestamp))
            
            now = datetime.datetime.now()
            diff = now - dt
            
            if diff.days > 7:
                return dt.strftime("%Y-%m-%d")
            elif diff.days > 0:
                return f"{diff.days} days ago"
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600} hours ago"
            elif diff.seconds > 60:
                return f"{diff.seconds // 60} minutes ago"
            else:
                return "Just now"
        except Exception as e:
            # 如果解析失败，返回原始时间戳的简化版本
            try:
                if isinstance(timestamp, str) and '_' in timestamp:
                    return f"ID: {timestamp.split('_')[0][-4:]}"
                return f"ID: {str(timestamp)[-4:]}"
            except:
                return "Unknown time"