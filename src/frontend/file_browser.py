import streamlit as st
import os
import mimetypes
import base64
from pathlib import Path
from typing import List, Dict
from ui_styles import UIStyleManager, UIComponentRenderer
import datetime

class FileBrowserManager:
    """File browser manager"""
    
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        self.style_manager = UIStyleManager()
    
    @staticmethod
    def get_file_icon(file_path: str) -> str:
        """Return corresponding icon based on file type"""
        if os.path.isdir(file_path):
            return "📁"
        
        suffix = Path(file_path).suffix.lower()
        icon_map = {
            '.py': '🐍',
            '.js': '📜',
            '.html': '🌐',
            '.css': '🎨',
            '.txt': '📄',
            '.md': '📝',
            '.pdf': '📕',
            '.jpg': '🖼️',
            '.jpeg': '🖼️',
            '.png': '🖼️',
            '.gif': '🖼️',
            '.mp4': '🎬',
            '.mp3': '🎵',
            '.zip': '📦',
            '.json': '📋',
            '.csv': '📊',
            '.xlsx': '📈',
            '.doc': '📄',
            '.docx': '📄',
            '.ppt': '📊',
            '.pptx': '📊',
            '.xml': '📋',
            '.yml': '⚙️',
            '.yaml': '⚙️',
            '.log': '📜',
            '.sql': '🗃️',
            '.db': '🗃️',
            '.sqlite': '🗃️',
        }
        return icon_map.get(suffix, '📄')
    
    @staticmethod
    def get_file_color(file_path: str) -> str:
        """Return corresponding color based on file type"""
        if os.path.isdir(file_path):
            return "#3b82f6"  # Blue
        
        suffix = Path(file_path).suffix.lower()
        color_map = {
            '.py': '#3776ab',      # Python blue
            '.js': '#f7df1e',      # JavaScript yellow
            '.html': '#e34f26',    # HTML orange
            '.css': '#1572b6',     # CSS blue
            '.json': '#000000',    # JSON black
            '.md': '#083fa1',      # Markdown blue
            '.txt': '#6b7280',     # Text gray
            '.pdf': '#dc2626',     # PDF red
            '.jpg': '#10b981',     # Image green
            '.jpeg': '#10b981',
            '.png': '#10b981',
            '.gif': '#10b981',
            '.mp4': '#7c3aed',     # Video purple
            '.mp3': '#f59e0b',     # Audio orange
            '.zip': '#374151',     # Archive gray
            '.csv': '#059669',     # CSV green
            '.xlsx': '#059669',    # Excel green
        }
        return color_map.get(suffix, '#6b7280')
    
    @staticmethod
    def get_file_size(file_path: str) -> str:
        """Get file size"""
        try:
            size = os.path.getsize(file_path)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except:
            return "Unknown"
    
    @staticmethod
    def get_file_modified_time(file_path: str) -> str:
        """Get file modification time"""
        try:
            timestamp = os.path.getmtime(file_path)
            dt = datetime.datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return "Unknown"
    
    @staticmethod
    def is_text_file(file_path: str) -> bool:
        """Check if it's a text file"""
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith('text'):
                return True
            
            text_extensions = {
                '.py', '.js', '.html', '.css', '.txt', '.md', '.json', '.csv', 
                '.xml', '.yml', '.yaml', '.log', '.sql', '.sh', '.bat', '.ini', 
                '.cfg', '.conf', '.properties', '.env', '.gitignore', '.dockerfile',
                '.makefile', '.cmake', '.toml', '.rst', '.tex', '.r', '.scala',
                '.go', '.rs', '.swift', '.kt', '.dart', '.php', '.rb', '.pl',
                '.lua', '.vim', '.emacs', '.bashrc', '.zshrc', '.profile'
            }
            return Path(file_path).suffix.lower() in text_extensions
        except:
            return False
    
    @staticmethod
    def read_file_content(file_path: str) -> str:
        """Read file content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    return f.read()
            except:
                return "Unable to read file content (encoding issue)"
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    @staticmethod
    def create_download_link(file_path: str) -> str:
        """Create file download link"""
        try:
            with open(file_path, "rb") as f:
                bytes_data = f.read()
                b64 = base64.b64encode(bytes_data).decode()
                filename = os.path.basename(file_path)
                href = f'''
                <a href="data:application/octet-stream;base64,{b64}" download="{filename}" 
                   style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; 
                          background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; 
                          text-decoration: none; border-radius: 0.5rem; font-weight: 500; 
                          transition: all 0.2s ease; box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);">
                    📥 Download File
                </a>
                '''
                return href
        except:
            return "Unable to create download link"
    
    def render_file_browser(self):
        """Render file browser interface"""
        # Add custom styles
        st.markdown("""
        <style>
        .file-browser-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-radius: 0.75rem;
            color: white;
            text-align: center;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.2);
        }
        
        .file-browser-header h2 {
            margin: 0;
            font-size: 1.5rem;
            font-weight: 600;
        }
        
        .file-browser-header p {
            margin: 0.5rem 0 0 0;
            opacity: 0.9;
            font-size: 0.9rem;
        }
        
        .breadcrumb {
            background: #f8fafc;
            padding: 0.5rem 0.75rem;
            border-radius: 0.375rem;
            margin-bottom: 1rem;
            border: 1px solid #e2e8f0;
            font-family: monospace;
            font-size: 0.8rem;
            color: #475569;
        }
        
        .stats-card {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border-radius: 0.5rem;
            padding: 0.75rem;
            text-align: center;
            border: 1px solid #bae6fd;
            margin-bottom: 0.5rem;
        }
        
        .stats-number {
            font-size: 1.25rem;
            font-weight: 700;
            color: #0369a1;
            margin-bottom: 0.25rem;
        }
        
        .stats-label {
            font-size: 0.75rem;
            color: #0284c7;
            font-weight: 500;
        }
        
        .file-item-container {
            margin-bottom: 0.5rem;
        }
        
        .file-icon-colored {
            font-size: 1.25rem;
            text-align: center;
            margin: 0;
        }
        
        .file-size-text {
            font-size: 0.7rem;
            color: #6b7280;
            text-align: right;
            margin: 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Render title
        st.markdown("""
        <div class="file-browser-header">
            <h2>📁 Smart File Browser</h2>
            <p>Explore your work directory and preview file contents</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Initialize current path
        if 'browser_current_path' not in st.session_state:
            st.session_state.browser_current_path = self.work_dir
        
        # Ensure path is within work directory scope
        if not st.session_state.browser_current_path.startswith(self.work_dir):
            st.session_state.browser_current_path = self.work_dir
        
        # Create two-column layout
        col1, col2 = st.columns([1, 1.2], gap="medium")
        
        with col1:
            with st.container():
                self._render_directory_panel()
        
        with col2:
            with st.container():
                self._render_file_preview_panel()
    
    def _render_directory_panel(self):
        """Render directory panel"""
        st.markdown("### 📂 Directory Navigation")
        
        # Display current path breadcrumbs
        relative_path = os.path.relpath(st.session_state.browser_current_path, self.work_dir)
        if relative_path == '.':
            breadcrumb = "🏠 Root Directory"
        else:
            breadcrumb = f"🏠 Root Directory / {relative_path.replace(os.sep, ' / ')}"
        
        st.markdown(f'<div class="breadcrumb">{breadcrumb}</div>', unsafe_allow_html=True)
        
        # Navigation buttons
        self._render_navigation_buttons()
        
        # Display directory contents
        self._render_directory_contents()
    
    def _render_navigation_buttons(self):
        """Render navigation buttons"""
        col1, col2 = st.columns(2)
        
        with col1:
            # Return to parent directory button
            if st.session_state.browser_current_path != self.work_dir:
                if st.button("⬆️ Parent Directory", key="browser_up", use_container_width=True, type="secondary"):
                    parent_path = os.path.dirname(st.session_state.browser_current_path)
                    if parent_path.startswith(self.work_dir):
                        st.session_state.browser_current_path = parent_path
                        st.rerun()
        
        with col2:
            # Return to root directory button
            if st.session_state.browser_current_path != self.work_dir:
                if st.button("🏠 Root Directory", key="browser_home", use_container_width=True, type="secondary"):
                    st.session_state.browser_current_path = self.work_dir
                    st.rerun()
    
    def _render_directory_contents(self):
        """Render directory contents"""
        try:
            # Get directory contents
            items = []
            if os.path.exists(st.session_state.browser_current_path):
                for item in os.listdir(st.session_state.browser_current_path):
                    item_path = os.path.join(st.session_state.browser_current_path, item)
                    items.append({
                        'name': item,
                        'path': item_path,
                        'is_dir': os.path.isdir(item_path),
                        'icon': self.get_file_icon(item_path),
                        'color': self.get_file_color(item_path),
                        'size': self.get_file_size(item_path) if not os.path.isdir(item_path) else "-",
                        'modified': self.get_file_modified_time(item_path)
                    })
                
                # Sort: directories first, then by name
                items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
                
                # Display directory contents
                st.markdown("**📂 Directory Contents:**")
                
                # Display file list
                for i, item in enumerate(items[:50]):  # Limit display count
                    # Create file item
                    file_type = "Folder" if item['is_dir'] else "File"
                    button_key = f"browser_btn_{item['name']}_{i}"
                    
                    # Use simplified layout
                    col_icon, col_content, col_size = st.columns([0.15, 0.65, 0.2])
                    
                    with col_icon:
                        st.markdown(
                            f"<div class='file-icon-colored' style='color: {item['color']};'>{item['icon']}</div>", 
                            unsafe_allow_html=True
                        )
                    
                    with col_content:
                        if st.button(
                            item['name'], 
                            key=button_key, 
                            use_container_width=True,
                            help=f"{file_type} - Modified: {item['modified']}"
                        ):
                            if item['is_dir']:
                                st.session_state.browser_current_path = item['path']
                                st.rerun()
                            else:
                                st.session_state.browser_selected_file = item['path']
                                st.rerun()
                    
                    with col_size:
                        if not item['is_dir']:
                            st.markdown(
                                f"<div class='file-size-text'>{item['size']}</div>", 
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown("<div class='file-size-text'>-</div>", unsafe_allow_html=True)
                
                if len(items) > 50:
                    st.info(f"📁 Directory contains {len(items)} items, showing first 50")
            
            else:
                st.error("❌ Directory does not exist or is inaccessible")
                
        except PermissionError:
            st.error("🔒 No permission to access this directory")
        except Exception as e:
            st.error(f"❌ Error reading directory: {str(e)}")
    
    def _render_file_preview_panel(self):
        """Render file preview panel"""
        st.markdown("### 📄 File Preview")
        
        if 'browser_selected_file' in st.session_state and os.path.exists(st.session_state.browser_selected_file):
            self._render_file_details()
        else:
            self._render_directory_stats()
    
    def _render_file_details(self):
        """Render file details"""
        file_path = st.session_state.browser_selected_file
        file_name = os.path.basename(file_path)
        file_size = self.get_file_size(file_path)
        file_modified = self.get_file_modified_time(file_path)
        file_icon = self.get_file_icon(file_path)
        file_color = self.get_file_color(file_path)
        
        # If it's a text file, get statistics
        extra_info = ""
        if self.is_text_file(file_path):
            content = self.read_file_content(file_path)
            lines = content.count('\n') + 1 if content else 0
            chars = len(content)
            extra_info = f" | 📝 {lines} lines | 🔤 {chars} chars"
        
        # File information card (includes statistics)
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); 
                    padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;
                    border: 1px solid #e2e8f0;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                <div style="font-size: 1.5rem; color: {file_color};">{file_icon}</div>
                <div style="flex: 1;">
                    <h4 style="margin: 0; color: #1f2937; font-weight: 600; font-size: 1rem;">{file_name}</h4>
                    <div style="color: #6b7280; font-size: 0.75rem; margin-top: 0.25rem;">
                        📏 {file_size} | 🕒 {file_modified}{extra_info}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Download link
        st.markdown(self.create_download_link(file_path), unsafe_allow_html=True)
        
        # File preview
        self._render_file_content_preview(file_path)
    
    def _render_file_content_preview(self, file_path: str):
        """Render file content preview"""
        if self.is_text_file(file_path):
            content = self.read_file_content(file_path)
            
            # Choose appropriate display method based on file type
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.py':
                st.code(content, language='python')
            elif file_ext == '.js':
                st.code(content, language='javascript')
            elif file_ext == '.html':
                st.code(content, language='html')
            elif file_ext == '.css':
                st.code(content, language='css')
            elif file_ext == '.json':
                self._render_json_preview(content)
            elif file_ext == '.csv':
                self._render_csv_preview(file_path)
            elif file_ext == '.md':
                st.markdown("**Markdown Rendered:**")
                st.markdown(content)
                st.markdown("**Raw Content:**")
                st.code(content, language='markdown')
            elif file_ext in ['.yml', '.yaml']:
                self._render_yaml_preview(content)
            elif file_ext == '.sql':
                st.code(content, language='sql')
            elif file_ext == '.xml':
                st.code(content, language='xml')
            elif file_ext == '.log':
                self._render_log_preview(content)
            else:
                st.text_area("File Content", content, height=300, key="browser_content_area")
        
        elif file_path.lower().endswith(('.xlsx', '.xls')):
            self._render_excel_preview(file_path)
        
        elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg')):
            try:
                st.image(file_path, caption=os.path.basename(file_path), use_column_width=True)
            except Exception as e:
                st.warning(f"⚠️ Unable to display image: {str(e)}")
        
        elif file_path.lower().endswith(('.pdf',)):
            self._render_pdf_preview(file_path)
        
        else:
            st.markdown("""
            <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 0.5rem; 
                        padding: 1rem; text-align: center; margin: 1rem 0;">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">📄</div>
                <div style="color: #92400e; font-weight: 500;">
                    This file type is not supported for preview, please download to view
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_csv_preview(self, file_path: str):
        """Render CSV file preview"""
        try:
            import pandas as pd
            
            # Read CSV file, limit rows for performance
            df = pd.read_csv(file_path, nrows=100)
            
            st.markdown("**📊 CSV Data Preview:**")
            
            # Display data information
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📏 Rows", len(df))
            with col2:
                st.metric("📋 Columns", len(df.columns))
            with col3:
                # Check if there's more data
                try:
                    total_df = pd.read_csv(file_path)
                    if len(total_df) > 100:
                        st.metric("📄 Total Rows", len(total_df))
                    else:
                        st.metric("📄 Total Rows", len(df))
                except:
                    st.metric("📄 Displayed Rows", len(df))
            
            # Display data table
            st.dataframe(df, use_container_width=True, height=400)
            
            # Display column information
            if len(df.columns) > 0:
                st.markdown("**📋 Column Information:**")
                col_info = []
                for col in df.columns:
                    dtype = str(df[col].dtype)
                    null_count = df[col].isnull().sum()
                    col_info.append({
                        'Column Name': col,
                        'Data Type': dtype,
                        'Null Count': null_count,
                        'Non-null Count': len(df) - null_count
                    })
                
                info_df = pd.DataFrame(col_info)
                st.dataframe(info_df, use_container_width=True)
                
        except Exception as e:
            st.error(f"❌ Unable to preview CSV file: {str(e)}")
            # Fallback to text preview
            content = self.read_file_content(file_path)
            st.text_area("CSV File Content", content[:2000] + "..." if len(content) > 2000 else content, height=300)
    
    def _render_excel_preview(self, file_path: str):
        """Render Excel file preview"""
        try:
            import pandas as pd
            
            # Get all worksheet names
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            st.markdown("**📈 Excel File Preview:**")
            
            # If there are multiple worksheets, let user choose
            if len(sheet_names) > 1:
                selected_sheet = st.selectbox(
                    "Select Worksheet:", 
                    sheet_names, 
                    key="excel_sheet_selector"
                )
            else:
                selected_sheet = sheet_names[0]
            
            # Read selected worksheet
            df = pd.read_excel(file_path, sheet_name=selected_sheet, nrows=100)
            
            # Display data information
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📏 Rows", len(df))
            with col2:
                st.metric("📋 Columns", len(df.columns))
            with col3:
                st.metric("📄 Worksheets", len(sheet_names))
            
            # Display data table
            st.dataframe(df, use_container_width=True, height=400)
            
        except Exception as e:
            st.error(f"❌ Unable to preview Excel file: {str(e)}")
            st.info("💡 Please ensure openpyxl or xlrd library is installed to support Excel file preview")
    
    def _render_json_preview(self, content: str):
        """Render JSON file preview"""
        try:
            import json
            
            # 解析JSON
            data = json.loads(content)
            
            st.markdown("**📋 JSON Data Preview:**")
            
            # 显示JSON信息
            col1, col2 = st.columns(2)
            with col1:
                if isinstance(data, dict):
                    st.metric("🔑 Key Count", len(data.keys()))
                elif isinstance(data, list):
                    st.metric("📝 Array Length", len(data))
                else:
                    st.metric("📄 Data Type", type(data).__name__)
            
            with col2:
                # 计算JSON深度
                def get_depth(obj, depth=0):
                    if isinstance(obj, dict):
                        return max([get_depth(v, depth+1) for v in obj.values()], default=depth)
                    elif isinstance(obj, list) and obj:
                        return max([get_depth(item, depth+1) for item in obj], default=depth)
                    return depth
                
                st.metric("🌳 Nesting Depth", get_depth(data))
            
            # 显示格式化的JSON
            st.json(data)
            
            # 如果是字典，显示键列表
            if isinstance(data, dict) and len(data) > 0:
                st.markdown("**🔑 Main Keys:**")
                keys = list(data.keys())[:10]  # 只显示前10个键
                for key in keys:
                    value_type = type(data[key]).__name__
                    st.markdown(f"- `{key}`: {value_type}")
                if len(data.keys()) > 10:
                    st.markdown(f"... and {len(data.keys()) - 10} more keys")
                    
        except json.JSONDecodeError as e:
            st.error(f"❌ JSON format error: {str(e)}")
            st.code(content, language='json')
        except Exception as e:
            st.error(f"❌ Unable to parse JSON: {str(e)}")
            st.code(content, language='json')
    
    def _render_yaml_preview(self, content: str):
        """Render YAML file preview"""
        try:
            import yaml
            
            # 解析YAML
            data = yaml.safe_load(content)
            
            st.markdown("**⚙️ YAML Configuration Preview:**")
            
            # 显示YAML信息
            if isinstance(data, dict):
                st.metric("🔑 Configuration Items", len(data.keys()))
                
                # 显示主要配置项
                st.markdown("**🔧 Main Configuration Items:**")
                for key, value in list(data.items())[:10]:
                    value_type = type(value).__name__
                    if isinstance(value, (str, int, float, bool)):
                        st.markdown(f"- `{key}`: {value} ({value_type})")
                    else:
                        st.markdown(f"- `{key}`: {value_type}")
                
                if len(data.keys()) > 10:
                    st.markdown(f"... and {len(data.keys()) - 10} more configuration items")
            
            # 显示原始YAML内容
            st.markdown("**📄 YAML Content:**")
            st.code(content, language='yaml')
            
        except Exception as e:
            st.error(f"❌ Unable to parse YAML: {str(e)}")
            st.code(content, language='yaml')
    
    def _render_log_preview(self, content: str):
        """Render log file preview"""
        st.markdown("**📜 Log File Preview:**")
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 显示日志统计
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📏 Total Lines", total_lines)
        with col2:
            # 统计错误行
            error_lines = len([line for line in lines if any(keyword in line.lower() for keyword in ['error', 'err', 'exception', 'fail'])])
            st.metric("❌ Error Lines", error_lines)
        with col3:
            # 统计警告行
            warning_lines = len([line for line in lines if any(keyword in line.lower() for keyword in ['warn', 'warning'])])
            st.metric("⚠️ Warning Lines", warning_lines)
        
        # 显示最后几行日志（通常最重要）
        st.markdown("**📋 Recent Logs (Last 50 lines):**")
        recent_logs = '\n'.join(lines[-50:]) if len(lines) > 50 else content
        st.text_area("Log Content", recent_logs, height=400, key="log_content_area")
        
        # 如果有错误或警告，单独显示
        if error_lines > 0 or warning_lines > 0:
            st.markdown("**🚨 Error and Warning Messages:**")
            error_warning_lines = [line for line in lines if any(keyword in line.lower() for keyword in ['error', 'err', 'exception', 'fail', 'warn', 'warning'])]
            if error_warning_lines:
                st.text_area("Errors/Warnings", '\n'.join(error_warning_lines[-20:]), height=200, key="error_warning_area")
    
    def _render_pdf_preview(self, file_path: str):
        """Render PDF file preview"""
        st.markdown("**📕 PDF File Preview:**")
        
        try:
            # 显示文件信息
            file_size = self.get_file_size(file_path)
            st.info(f"📄 PDF file size: {file_size}")
            
            # 尝试使用streamlit的内置PDF查看器
            with open(file_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
            
            # 创建PDF查看器
            pdf_display = f'''
            <iframe src="data:application/pdf;base64,{base64_pdf}" 
                    width="100%" height="600" type="application/pdf">
                <p>Your browser does not support PDF preview. Please <a href="data:application/pdf;base64,{base64_pdf}" download="{os.path.basename(file_path)}">download the file</a> to view.</p>
            </iframe>
            '''
            
            st.markdown(pdf_display, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"❌ Unable to preview PDF file: {str(e)}")
            st.info("💡 PDF preview requires browser support, recommend downloading the file to view")
    
    def _render_directory_stats(self):
        """Render directory statistics"""
        st.markdown("""
        <div style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); 
                    border-radius: 0.5rem; padding: 1.5rem; text-align: center; 
                    border: 1px solid #93c5fd; margin-bottom: 1rem;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">👆</div>
            <div style="color: #1e40af; font-weight: 600; font-size: 1rem;">
                Please select a file on the left for preview
            </div>
            <div style="color: #3730a3; margin-top: 0.25rem; font-size: 0.875rem;">
                Click on the file name to view detailed content
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 显示当前目录的统计信息
        try:
            if os.path.exists(st.session_state.browser_current_path):
                files = [f for f in os.listdir(st.session_state.browser_current_path) 
                        if os.path.isfile(os.path.join(st.session_state.browser_current_path, f))]
                dirs = [d for d in os.listdir(st.session_state.browser_current_path) 
                       if os.path.isdir(os.path.join(st.session_state.browser_current_path, d))]
                
                st.markdown("#### 📊 Directory Statistics")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"""
                    <div class="stats-card">
                        <div class="stats-number">{len(dirs)}</div>
                        <div class="stats-label">📁 Folders</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="stats-card">
                        <div class="stats-number">{len(files)}</div>
                        <div class="stats-label">📄 Files</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # 文件类型分布
                if files:
                    st.markdown("#### 📈 File Type Distribution")
                    file_types = {}
                    for file in files:
                        ext = Path(file).suffix.lower() or 'No extension'
                        file_types[ext] = file_types.get(ext, 0) + 1
                    
                    # 显示前5种文件类型
                    sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:5]
                    for ext, count in sorted_types:
                        icon = self.get_file_icon(f"dummy{ext}")
                        st.markdown(f"**{icon} {ext}**: {count} files")
                        
        except Exception as e:
            st.error(f"❌ Error getting directory statistics: {str(e)}")

def render_file_browser_interface():
    """Render file browser interface"""
    style_manager = UIStyleManager()
    style_manager.apply_main_styles()
    
    # 渲染顶部导航
    user_name = st.session_state.get('username', 'Guest')
    UIComponentRenderer.render_top_navigation(user_name=user_name)
    
    # 返回聊天界面按钮
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔙 Back to Chat", key="back_to_chat", use_container_width=True, type="primary"):
            st.session_state.show_file_browser = False
            st.rerun()
    
    st.markdown("---")
    
    # 获取工作目录
    work_dir = st.session_state.get('work_dir', os.getcwd())
    
    # 创建并渲染文件浏览器
    browser_manager = FileBrowserManager(work_dir)
    browser_manager.render_file_browser()

def render_file_browser_button(key_suffix: str = "", button_text: str = "📁 Browse Work Directory", help_text: str = "View all files in current work directory"):
    """Render file browser button"""
    # 获取工作目录信息
    work_dir = st.session_state.get('work_dir', os.getcwd())
    
    # 获取目录统计和文件类型
    file_count = 0
    dir_count = 0
    file_types = []
    
    try:
        if os.path.exists(work_dir):
            items = os.listdir(work_dir)
            files = [f for f in items if os.path.isfile(os.path.join(work_dir, f))]
            dirs = [d for d in items if os.path.isdir(os.path.join(work_dir, d))]
            
            file_count = len(files)
            dir_count = len(dirs)
            if file_count == 0 and dir_count == 0:
                return
            
            # 获取常见文件类型的缩略图
            type_icons = {}
            for file in files[:20]:  # 只检查前20个文件以提高性能
                ext = Path(file).suffix.lower()
                if ext and ext not in type_icons:
                    type_icons[ext] = FileBrowserManager.get_file_icon(file)
                if len(type_icons) >= 6:  # 最多显示6种文件类型
                    break
            
            # 添加文件夹图标
            if dirs:
                type_icons['folder'] = '📁'
            
            file_types = list(type_icons.items())[:6]
    except:
        pass
    
    # 创建缩略图显示
    thumbnails_display = ""
    for file_type, icon in file_types:
        thumbnails_display += f"{icon} "
    
    # 如果没有文件类型，显示默认图标
    if not thumbnails_display:
        thumbnails_display = "📁 📄 🖼️ "
    
    # 直接调用ui_styles.py中的缩略图展示效果
    from ui_styles import UIComponentRenderer
    
    # 使用form来创建可点击的自定义按钮
    with st.form(key=f"file_browser_form_{key_suffix}"):
        # 添加自定义样式
        st.markdown("""
        <style>
        .file-browser-custom {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            padding: 16px 20px;
            margin: 8px 0;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            color: white;
            border: none;
            position: relative;
            overflow: hidden;
        }
        
        .file-browser-custom:hover {
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        
        .file-browser-content-flex {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
        }
        
        .file-browser-left-content {
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
        }
        
        .file-browser-main-icon {
            font-size: 24px;
            background: rgba(255, 255, 255, 0.2);
            padding: 8px;
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }
        
        .file-browser-text-content {
            flex: 1;
        }
        
        .file-browser-title-text {
            font-size: 16px;
            font-weight: 600;
            margin: 0 0 4px 0;
            line-height: 1.2;
        }
        
        .file-browser-subtitle-text {
            font-size: 12px;
            opacity: 0.8;
            margin: 0 0 4px 0;
            line-height: 1.2;
        }
        
        .file-browser-stats {
            display: flex;
            gap: 12px;
            font-size: 11px;
            opacity: 0.7;
        }
        
        .file-browser-right-content {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
        }
        
        .file-browser-thumbnails-text {
            opacity: 0.8;
        }
        
        .file-browser-arrow-text {
            font-size: 18px;
            opacity: 0.8;
        }
        
        .file-browser-bg-decoration {
            position: absolute;
            top: 0;
            right: 0;
            width: 100px;
            height: 100%;
            background: url("data:image/svg+xml,%3Csvg width='40' height='40' viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M20 20c0 11.046-8.954 20-20 20v-40c11.046 0 20 8.954 20 20z'/%3E%3C/g%3E%3C/svg%3E");
            opacity: 0.3;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 渲染自定义按钮内容
        st.markdown(f"""
        <div class="file-browser-custom">
            <div class="file-browser-bg-decoration"></div>
            <div class="file-browser-content-flex">
                <div class="file-browser-left-content">
                    <div class="file-browser-main-icon">📁</div>
                    <div class="file-browser-text-content">
                        <div class="file-browser-title-text">{button_text}</div>
                        <div class="file-browser-subtitle-text">{help_text}</div>
                        <div class="file-browser-stats">
                            <span>📁 {dir_count} folders</span>
                            <span>📄 {file_count} files</span>
                        </div>
                    </div>
                </div>
                <div class="file-browser-right-content">
                    <div class="file-browser-thumbnails-text">{thumbnails_display}</div>
                    <div class="file-browser-arrow-text">→</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        

    
        # 展示工作目录中文件的缩略图效果（紧凑一行展示）
        if file_count > 0:
            # 创建模拟的uploaded_files对象来展示缩略图
            mock_files = []
            try:
                for file in files[:8]:  # 最多显示8个文件
                    file_path = os.path.join(work_dir, file)
                    if os.path.isfile(file_path):
                        # 创建一个简单的mock对象来模拟uploaded_file
                        class MockFile:
                            def __init__(self, filepath):
                                self.name = os.path.basename(filepath)
                                self.size = os.path.getsize(filepath)
                                self._filepath = filepath
                            
                            def read(self):
                                try:
                                    with open(self._filepath, 'rb') as f:
                                        return f.read()
                                except:
                                    return b''
                            
                            def seek(self, pos):
                                pass
                        
                        mock_files.append(MockFile(file_path))
            except:
                pass
            
            if mock_files:
                # 使用紧凑的一行展示，而不是网格布局
                st.markdown("#### 📁 Directory File Preview")
                
                # 创建一行展示的列布局
                cols = st.columns(len(mock_files))
                
                for i, mock_file in enumerate(mock_files):
                    with cols[i]:
                        # 获取文件信息
                        filename = mock_file.name
                        file_size = mock_file.size
                        
                        # 格式化文件大小
                        if file_size < 1024:
                            size_str = f"{file_size} B"
                        elif file_size < 1024 * 1024:
                            size_str = f"{file_size / 1024:.1f} KB"
                        else:
                            size_str = f"{file_size / (1024 * 1024):.1f} MB"
                        
                        # 使用FilePreviewGenerator生成真实的文件内容预览
                        from ui_styles import FilePreviewGenerator
                        preview_content = FilePreviewGenerator.generate_preview_html(mock_file)
                        
                        # 渲染紧凑的文件卡片
                        card_html = f"""
                        <div class="uploaded-file-card">
                            <div class="file-thumbnail">
                                {preview_content}
                            </div>
                            <div class="file-card-info">
                                <div class="file-card-name" title="{filename}">{filename[:12]}{'...' if len(filename) > 12 else ''}</div>
                                <div class="file-card-size">{size_str}</div>
                            </div>
                        </div>
                        """
                        
                        st.markdown(card_html, unsafe_allow_html=True)

        # 使用form_submit_button来处理点击
        if st.form_submit_button("Click to Browse Files", use_container_width=True, type="primary"):
            st.session_state.show_file_browser = True
            st.rerun()                        