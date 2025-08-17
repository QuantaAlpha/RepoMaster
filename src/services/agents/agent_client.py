import sys
import os
import json
import glob
import asyncio
import traceback
import pandas as pd
import datetime
from pathlib import Path
from autogen import AssistantAgent, UserProxyAgent, GroupChatManager
from autogen.oai.client import OpenAIWrapper
from autogen.agentchat.conversable_agent import ConversableAgent as Agent
from typing import Union, Dict, Callable, Any, TypeVar, List, Tuple

from src.services.autogen_upgrade.file_monitor import get_directory_files, compare_and_display_new_files

from autogen.formatting_utils import colored

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from pdf2image import convert_from_path, convert_from_bytes
from src.utils.tools_util import _print_received_message
from src.utils.tool_streamlit import AppContext
from src.utils.utils_config import AppConfig

from streamlit_extras.colored_header import colored_header

# Try to import UI style manager
try:
    from src.frontend.ui_styles import UIComponentRenderer, UIStyleManager
except ImportError:
    UIComponentRenderer = None
    UIStyleManager = None

from autogen.tools.function_utils import load_basemodels_if_needed, serialize_to_str
from autogen.runtime_logging import log_event, log_function_use, log_new_agent, logging_enabled

F = TypeVar("F", bound=Callable[..., Any])

class EnhancedMessageProcessor:
    """Enhanced message processor - static tool class"""
    
    @staticmethod
    def create_display_info(
        message_content: str,
        sender_name: str,
        receiver_name: str,
        sender_role: str,
        llm_config: Dict = None,
        new_files: List[str] = None
    ) -> Dict:
        """
        Create standard display information format
        
        Args:
            message_content: Message content
            sender_name: Sender name
            receiver_name: Receiver name
            sender_role: Sender role ('user' or 'assistant')
            llm_config: LLM configuration dictionary
            new_files: New file list
            
        Returns:
            Standard format display information dictionary
        """
        import datetime
        import json
        
        return {
            "message": {"content": message_content, "role": sender_role},
            "sender_info": {
                "name": sender_name,
                "description": "",
                "system_message": ""
            },
            "receiver_name": receiver_name,
            "llm_config": llm_config if llm_config else {},
            "sender_role": sender_role,
            "timestamp": datetime.datetime.now().isoformat(),
            "new_files": json.dumps(new_files) if new_files else "[]"
        }
    
    @staticmethod
    def add_display_message_to_session(
        st, 
        message_content: str,
        sender_name: str,
        receiver_name: str,
        sender_role: str,
        llm_config: Dict = None,
        new_files: List[str] = None,
        check_duplicate: bool = True
    ):
        """
        Add display message to session_state.display_messages
        
        Args:
            st: streamlit object
            message_content: Message content
            sender_name: Sender name
            receiver_name: Receiver name
            sender_role: Sender role
            llm_config: LLM configuration dictionary
            new_files: New file list
            check_duplicate: Whether to check for duplicate messages
        """
        if not hasattr(st.session_state, 'display_messages'):
            st.session_state.display_messages = []
        
        # Internal call to create_display_info to create standard format
        display_info = EnhancedMessageProcessor.create_display_info(
            message_content=message_content,
            sender_name=sender_name,
            receiver_name=receiver_name,
            sender_role=sender_role,
            llm_config=llm_config,
            new_files=new_files
        )
            
        # Check for duplicates (optional)
        if check_duplicate and st.session_state.display_messages:
            last_message = st.session_state.display_messages[-1]
            if last_message.get("message", {}).get("content") == message_content:
                return  # Skip duplicate message
        
        st.session_state.display_messages.append(display_info)
    
    @staticmethod
    def add_message_to_session(st, role: str, content: str, check_duplicate: bool = True):
        """
        Add messages to session_state.messages
        
        Args:
            st: streamlit object
            role: Message role ('user' or 'assistant')
            content: Message content
            check_duplicate: Whether to check for duplicate messages
        """
        if not hasattr(st.session_state, 'messages'):
            st.session_state.messages = []
            
        message = {"role": role, "content": content}
        
        # Check for duplicates (optional)
        if check_duplicate and st.session_state.messages:
            if st.session_state.messages[-1] == message:
                return  # Skip duplicate message
        
        st.session_state.messages.append(message)
    
    @staticmethod
    def get_latest_files(directory: str) -> List[str]:
        """
        Get latest files in directory (deprecated)
        
        Note: This function is deprecated, please use file_monitor.get_directory_files() instead,
        which provides more powerful recursive file detection, file filtering and structured information features.
        
        Args:
            directory: Directory path
            
        Returns:
            File path list (only includes specific extensions, non-recursive)
        """
        import warnings
        warnings.warn(
            "get_latest_files() is deprecated. Use file_monitor.get_directory_files() instead for better functionality.",
            DeprecationWarning,
            stacklevel=2
        )
        
        new_files = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.csv', '*.xlsx', '*.json', '*.txt', '*.pdf', '*.html']:
            new_files.extend(glob.glob(os.path.join(directory, ext)))
        return new_files
    
    @staticmethod
    def detect_new_files(work_dir: str, previous_files_info: Dict[str, Dict] = None) -> Tuple[Dict[str, Dict], List[str]]:
        """
        Detect new file changes using powerful file_monitor functionality
        
        Args:
            work_dir: Working directory path
            previous_files_info: Previous file information dictionary (from get_directory_files)
            
        Returns:
            Tuple[Current file information dictionary, New file path list]
        """
        if not work_dir or not os.path.exists(work_dir):
            return {}, []
        
        work_dir_path = Path(work_dir)
        current_files_info = get_directory_files(work_dir_path)
        
        if previous_files_info is None:
            # If no previous file information, return all current files
            new_file_paths = list(current_files_info.keys())
        else:
            # Find newly added files
            new_file_paths = [
                file_path for file_path in current_files_info.keys()
                if file_path not in previous_files_info
            ]
        
        return current_files_info, new_file_paths
    
    @staticmethod
    def display_single_file(file_path: str, st):
        """Display single file"""
        file_name = os.path.basename(file_path)
        file_ext = file_path.split('.')[-1].lower()
        
        # Generate unique key based on file path
        import hashlib
        file_key = hashlib.md5(file_path.encode()).hexdigest()[:8]
        
        if file_ext in ['png', 'jpg', 'jpeg']:
            st.image(file_path, caption=f"🖼️ {file_name}")
        
        elif file_ext in ['csv', 'xlsx']:
            try:
                if file_ext == 'csv':
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)
                
                st.markdown(f"**📊 {file_name}**")
                st.dataframe(df.head(100))  # Only show first 100 rows
                
                if len(df) > 100:
                    st.info(f"Showing first 100 rows, total {len(df)} rows")
            except Exception as e:
                st.error(f"Unable to read {file_name}: {str(e)}")
        
        elif file_ext == 'json':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                st.markdown(f"**📋 {file_name}**")
                st.json(json_data)
            except Exception as e:
                st.error(f"Unable to read JSON file {file_name}: {str(e)}")
        
        elif file_ext == 'txt':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                st.markdown(f"**📄 {file_name}**")
                
                if len(text_content) > 2000:
                    with st.expander(
                        f"View full content ({len(text_content)} characters)", 
                        expanded=False
                    ):
                        st.text_area(
                            label="File Content", 
                            value=text_content, 
                            height=300, 
                            disabled=True,
                            key=f"txt_full_{file_key}",
                            label_visibility="hidden"
                        )
                else:
                    st.text_area(
                        label="File Content", 
                        value=text_content, 
                        height=min(200, max(100, text_content.count('\n') * 20)), 
                        disabled=True,
                        key=f"txt_short_{file_key}",
                        label_visibility="hidden"
                    )
            except Exception as e:
                st.error(f"Unable to read text file {file_name}: {str(e)}")
        
        elif file_ext == 'pdf':
            try:
                pdf_images = convert_pdf_to_images(file_path)
                st.markdown(f"**📕 {file_name}**")
                for i, img in enumerate(pdf_images[:3]):  # Only show first 3 pages
                    st.image(img, caption=f"Page {i+1}", use_column_width=True)
                if len(pdf_images) > 3:
                    st.info(f"Showing first 3 pages, total {len(pdf_images)} pages")
            except Exception as e:
                st.error(f"Unable to process PDF file {file_name}: {str(e)}")
        
        elif file_ext == 'html':
            try:
                st.markdown(f"**🌐 {file_name}**")
                html_img = read_html_as_image(file_path)
                st.image(html_img, caption=f"HTML preview: {file_name}", use_column_width=True)
                
                with st.expander("View HTML source code", expanded=False):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    st.code(html_content, language="html")
            except Exception as e:
                st.error(f"Unable to process HTML file {file_name}: {str(e)}")
    
    @staticmethod
    def display_new_files_header(new_files_count: int, st):
        """Display new files header"""
        if new_files_count > 0:
            st.markdown(f"""
            <div style="background: var(--secondary-color); color: white; padding: 0.75rem 1rem; border-radius: 0.5rem; margin: 1rem 0; text-align: center; font-weight: 600;">
                📁 Generated {new_files_count} new files
            </div>
            """, unsafe_allow_html=True)
    
    @staticmethod
    def display_files_batch(work_dir: str, previous_files_info: Dict[str, Dict], st) -> Tuple[Dict[str, Dict], List[str]]:
        """
        Display files in batch and return updated file information and new file list
        
        Args:
            work_dir: Working directory path
            previous_files_info: Previous file information dictionary
            st: streamlit object
            
        Returns:
            Tuple[Current file information dictionary, New file path list]
        """
        if work_dir is None or st is None:
            return previous_files_info or {}, []
        
        try:
            work_dir_path = Path(work_dir)
            if not work_dir_path.exists():
                return previous_files_info or {}, []
            
            # Use powerful file_monitor functionality
            current_files_info = get_directory_files(work_dir_path)
            
            if previous_files_info is None:
                previous_files_info = {}
            
            # Directly use compare_and_display_new_files to get formatted display information
            file_changes_info = compare_and_display_new_files(
                previous_files_info, current_files_info, work_dir_path
            )
            
            # Get new file list
            new_file_paths = [
                file_path for file_path in current_files_info.keys()
                if file_path not in previous_files_info
            ]
            
            if new_file_paths and file_changes_info != "No new files generated during execution":
                # Display new files header and structured information
                EnhancedMessageProcessor.display_new_files_header(len(new_file_paths), st)
                

                
                # Try to use compact one-line display method, fallback to simplified version if failed
                try:
                    EnhancedMessageProcessor.display_files_compact(new_file_paths, st)
                except Exception as e:
                    print(f"display_files_compact failed, using simple version: {e}")
                    EnhancedMessageProcessor.display_files_compact_simple(new_file_paths, st)
            
            return current_files_info, new_file_paths
            
        except Exception as e:
            print(f"\n{'-'*30}\ndisplay_files_batch ERROR: {e}\n{'-'*30}\n")
        
        return previous_files_info or {}, []

    @staticmethod
    def get_file_priority(file_path: str) -> int:
        """Get file display priority, lower number means higher priority"""
        ext = file_path.split('.')[-1].lower() if '.' in file_path else ''
        image_exts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg']
        if ext in image_exts:
            return 0  # Image files have highest priority
        elif ext in ['pdf']:
            return 1  # PDF files have second priority
        elif ext in ['csv', 'xlsx', 'json']:
            return 2  # Data files
        else:
            return 3  # Other files

    @staticmethod
    def display_files_compact_simple(new_files: List[str], st):
        """Simplified compact file display (fallback option)"""
        if not new_files or not st:
            return
        
        try:
            # Sort file list by priority, images first
            sorted_files = sorted(new_files, key=EnhancedMessageProcessor.get_file_priority)
            
            # Limit display file count
            display_files = sorted_files[:8]
            if len(new_files) > 8:
                st.info(f"📁 Generated {len(new_files)} files, prioritizing display of images and other important files (first 8)")
            
            # Create column layout
            cols = st.columns(len(display_files))
            
            for i, file_path in enumerate(display_files):
                with cols[i]:
                    filename = os.path.basename(file_path)
                    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                    
                    # Format file size
                    if file_size < 1024:
                        size_str = f"{file_size} B"
                    elif file_size < 1024 * 1024:
                        size_str = f"{file_size / 1024:.1f} KB"
                    else:
                        size_str = f"{file_size / (1024 * 1024):.1f} MB"
                    
                    # Get file icon
                    file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
                    icon_map = {
                        'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️',
                        'pdf': '📕', 'csv': '📊', 'xlsx': '📈', 'json': '📋',
                        'txt': '📄', 'py': '🐍', 'html': '🌐', 'css': '🎨',
                        'md': '📝', 'yml': '⚙️', 'yaml': '⚙️', 'xml': '📋'
                    }
                    icon = icon_map.get(file_ext, '📄')
                    
                    # Display file information
                    st.markdown(f"""
                    <div style="text-align: center; padding: 0.5rem; border: 1px solid #e2e8f0; border-radius: 0.5rem; background: #f8fafc;">
                        <div style="font-size: 2rem; margin-bottom: 0.25rem;">{icon}</div>
                        <div style="font-size: 0.7rem; font-weight: 600; color: #334155; margin-bottom: 0.1rem;" title="{filename}">
                            {filename[:10]}{'...' if len(filename) > 10 else ''}
                        </div>
                        <div style="font-size: 0.6rem; color: #64748b;">{size_str}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        except Exception as e:
            print(f"\n{'-'*30}\ndisplay_files_compact_simple ERROR: {e}\n{'-'*30}\n")

    @staticmethod
    def display_files_compact(new_files: List[str], st):
        """Compact one-line display for new files (reusing file_browser.py display logic)"""
        if not new_files or not st:
            return
        
        # Add necessary CSS styles
        st.markdown("""
        <style>
        .uploaded-file-card {
            background: var(--background-secondary, #f1f5f9);
            border: 1px solid var(--border-color, #cbd5e1);
            border-radius: 0.75rem;
            padding: 0.75rem;
            transition: all 0.3s ease;
            cursor: default;
            position: relative;
            overflow: hidden;
        }
        
        .uploaded-file-card:hover {
            border-color: var(--primary-color, #6366f1);
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
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
            background: linear-gradient(135deg, #ffffff, #e2e8f0);
            border: 1px solid var(--border-color, #cbd5e1);
            overflow: hidden;
            position: relative;
        }
        
        .file-thumbnail img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            border-radius: 0.5rem;
        }
        
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
            color: var(--text-primary, #1e293b);
            font-size: 0.8rem;
            margin-bottom: 0.25rem;
            word-break: break-word;
            line-height: 1.2;
        }
        
        .file-card-size {
            font-size: 0.7rem;
            color: var(--text-muted, #64748b);
        }
        </style>
        """, unsafe_allow_html=True)
        
        try:
            # Sort file list by priority, images first
            sorted_files = sorted(new_files, key=EnhancedMessageProcessor.get_file_priority)
            
            # Create mock uploaded_files object to display thumbnails
            mock_files = []
            for file_path in sorted_files[:8]:  # Display maximum 8 files
                if os.path.isfile(file_path):
                    # Create a simple mock object to simulate uploaded_file
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
            
            if mock_files:
                # Create one-line display column layout, maximum 8 columns
                file_count = len(mock_files)
                if file_count > 8:
                    st.info(f"📁 Generated {len(new_files)} files, prioritizing display of preview for images and other important files (first 8)")
                    file_count = 8
                
                cols = st.columns(file_count)
                
                for i, mock_file in enumerate(mock_files[:file_count]):
                    with cols[i]:
                        # Get file information
                        filename = mock_file.name
                        file_size = mock_file.size
                        
                        # Format file size
                        if file_size < 1024:
                            size_str = f"{file_size} B"
                        elif file_size < 1024 * 1024:
                            size_str = f"{file_size / 1024:.1f} KB"
                        else:
                            size_str = f"{file_size / (1024 * 1024):.1f} MB"
                        
                        # Use FilePreviewGenerator to generate real file content preview
                        try:
                            from src.frontend.ui_styles import FilePreviewGenerator
                            preview_content = FilePreviewGenerator.generate_preview_html(mock_file)
                        except (ImportError, Exception) as e:
                            # If import fails or preview generation fails, use fallback icon
                            file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
                            icon_map = {
                                'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️',
                                'pdf': '📕', 'csv': '📊', 'xlsx': '📈', 'json': '📋',
                                'txt': '📄', 'py': '🐍', 'html': '🌐', 'css': '🎨',
                                'md': '📝', 'yml': '⚙️', 'yaml': '⚙️', 'xml': '📋'
                            }
                            preview_content = icon_map.get(file_ext, '📄')
                        
                        # Render compact file card
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
        
        except Exception as e:
            print(f"\n{'-'*30}\ndisplay_files_compact ERROR: {e}\n{'-'*30}\n")

    @staticmethod
    def process_tool_calls(tool_calls, st):
        """Process tool call display"""
        if not tool_calls:
            return
        
        # Get all unique function names
        function_names = []
        function_call_list = []
        for tool_call in tool_calls:
            function_call = tool_call.get("function", {})
            name = function_call.get('name', '')
            if not name:
                continue
            if name not in function_names:
                function_names.append(name)

            function_call_list.append({
                name: function_call.get('arguments','')
            })

        function_content = ' | '.join([f"{k}: {str(v)[:min(len(str(v)),400)]}" for calls in function_call_list for k,v in calls.items()])
        function_content = EnhancedMessageProcessor.fliter_message(function_content)
        
        # Display tool execution status
        if function_names:
            tools_text = " | ".join(function_names)
            st.markdown(f"""
            <div style="background: var(--background-tertiary); border: 1px solid var(--warning-color); border-radius: 0.75rem; padding: 1rem; margin: 1rem 0;">
                <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--warning-color); font-weight: 600;">
                    🧠 Executing tools: {tools_text}
                    <div style="display: inline-flex; gap: 0.25rem; margin-left: 1rem;">
                        <span style="width: 6px; height: 6px; background: var(--warning-color); border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both;"></span>
                        <span style="width: 6px; height: 6px; background: var(--warning-color); border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; animation-delay: -0.16s;"></span>
                        <span style="width: 6px; height: 6px; background: var(--warning-color); border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; animation-delay: -0.32s;"></span>
                    </div>
                </div>
            </div>
            <style>
            @keyframes bounce {{
                0%, 80%, 100% {{ transform: scale(0); }}
                40% {{ transform: scale(1); }}
            }}
            </style>
            """, unsafe_allow_html=True)
        
        # Display detailed parameters
        with st.expander(f"🔧 Click to expand tool call details ({len(tool_calls)} items), Preview: 📋 {function_content}", expanded=False):
            for i, tool_call in enumerate(tool_calls):
                function_call = tool_call.get("function", {})
                st.markdown(f"**Tool {i+1}: {function_call.get('name', 'Unknown')}**")
                
                try:
                    args = json.loads(function_call.get("arguments", "{}"))
                    st.json(args)
                except:
                    st.code(function_call.get("arguments", "No parameters"))
                
                if i < len(tool_calls) - 1:
                    st.markdown("---")

    @staticmethod
    def fliter_message(content):
        content_filter = content.replace('/mnt/ceph/huacan/','/')
        content_filter = content_filter.replace('/mnt/ceph/','/')
        content_filter = content_filter.replace('/home/dfo/','/')
        content_filter = content_filter.replace('/home/huacan/','/')
        content_filter = content_filter.replace('/dfo/','/')
        content_filter = content_filter.replace('/huacan/','/')
        content_filter = content_filter.replace('/.dfo/','/')
        
        return content_filter    
    
    @staticmethod
    def streamlit_display_message(
        st,
        message: Union[Dict, str],
        sender_name: str,
        receiver_name: str,
        llm_config: Dict,
        sender_role=None,
        save_to_history: bool = True,
        timestamp: str = None,
    ):
        """Enhanced Streamlit message display"""        
        try:
            # Initialize new file records
            if st is not None and save_to_history:
                if not hasattr(st.session_state, '_current_new_files'):
                    st.session_state._current_new_files = []
            
            # Ensure message is in dictionary format
            if isinstance(message, str):
                message = {"content": message}
            elif not isinstance(message, dict):
                message = {"content": str(message)}
            
            # Only save complete display information in non-replay mode
            if save_to_history and st is not None:
                EnhancedMessageProcessor.save_display_info(
                    st, message, sender_name, receiver_name, llm_config, sender_role
                )
            
            # Process tool responses
            if message.get("tool_responses"):
                for idx, tool_response in enumerate(message["tool_responses"]):
                    # Process tool_response directly, avoid recursive calls
                    if tool_response.get("role") in ["function", "tool"]:
                        # Only show title for first tool_response
                        show_title = (idx == 0)
                        EnhancedMessageProcessor.display_function_tool_message(st, tool_response, show_title)
                
                if message.get("role") == "tool":
                    return

            # Process function/tool role messages
            if message.get("role") in ["function", "tool"]:
                EnhancedMessageProcessor.display_function_tool_message(st, message, first_display)
            
            else:
                # Process regular message content
                content = message.get("content")
                if content:
                    content = EnhancedMessageProcessor.fliter_message(content)
                    
                    # Add timestamp - use passed timestamp or current time
                    if timestamp:
                        # If timestamp is passed, need to convert format
                        try:
                            # Convert from ISO format to display format
                            dt = datetime.datetime.fromisoformat(timestamp)
                            display_timestamp = dt.strftime("%H:%M:%S")
                        except:
                            display_timestamp = timestamp
                    else:
                        display_timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; font-size: 0.875rem; opacity: 0.7;">
                        <span>{sender_name}</span>
                        <span style="margin-left: auto;">{display_timestamp}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(content)
                
                # Process function_call
                if "function_call" in message and message["function_call"]:
                    function_call = dict(message["function_call"])
                    function_name = function_call.get('name', 'Unknown function')
                    
                    st.markdown(f"""
                    <div style="background: var(--background-tertiary); border: 1px solid var(--warning-color); border-radius: 0.75rem; padding: 1rem; margin: 1rem 0;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--warning-color); font-weight: 600;">
                            🧠 Calling function: {function_name}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander("View function parameters", expanded=False):
                        try:
                            args = json.loads(function_call.get("arguments", "{}"))
                            st.json(args)
                        except:
                            st.code(function_call.get("arguments", "no arguments found"))
                
                # Process tool_calls
                if "tool_calls" in message and message["tool_calls"]:
                    EnhancedMessageProcessor.process_tool_calls(message["tool_calls"], st)

            # Save to message history
            if sender_role is not None and st is not None and "messages" in st.session_state:
                history_entry = {"role": sender_role}
                
                if message.get("content"):
                    history_entry["content"] = message.get("content")

                # Add function_call if present
                if "function_call" in message and message["function_call"]:
                    history_entry["function_call"] = message["function_call"]
                
                # Add tool_calls if present
                if "tool_calls" in message and message["tool_calls"]:
                    history_entry["tool_calls"] = message["tool_calls"]
                
                # Add tool_responses if present
                if 0 and "tool_responses" in message and message["tool_responses"]:
                    history_entry["tool_responses"] = message["tool_responses"]
                
                st.session_state.messages.append(history_entry)

        except Exception as e:
            print(traceback.format_exc())
            print(f"\n{'-'*30}\nstreamlit_display_message ERROR: {e}\n{'-'*30}\n")

    @staticmethod
    def save_display_info(st, message: Dict, sender_name: str, receiver_name: str, llm_config: Dict, sender_role: str):
        """Save complete display information for historical conversation replay"""
        if st is None or sender_role is None:
            return
            
        if "display_messages" not in st.session_state:
            st.session_state.display_messages = []
        
        try:
            # Convert Agent object to serializable dictionary
            sender_info = {
                "name": sender_name,
                "description": "",
                "system_message": "",
            }
            
            # Get currently detected new file information (if exists)
            new_files = getattr(st.session_state, '_current_new_files', [])
            
            display_info = {
                "message": message,
                "sender_info": sender_info,
                "receiver_name": receiver_name,
                "llm_config": llm_config if llm_config else {},
                "sender_role": sender_role,
                "timestamp": datetime.datetime.now().isoformat(),
                "new_files": json.dumps(new_files) if new_files else "[]"  # Save as JSON format
            }
            
            st.session_state.display_messages.append(display_info)
            
            # Clear temporary new file records
            st.session_state._current_new_files = []
            
        except Exception as e:
            print(f"\n{'-'*30}\nsave_display_info ERROR: {e}\n{'-'*30}\n")

    @staticmethod
    def replay_display_messages(st, display_messages: List[Dict]):
        """Replay historical display messages - directly call streamlit_display_message"""
        
        # Initialize or reset local_files_info state to ensure no duplicate file display during history replay
        if "local_files_info" not in st.session_state:
            st.session_state["local_files_info"] = {}
        
        for i, display_info in enumerate(display_messages):
            try:
                message = display_info["message"]
                sender_info = display_info["sender_info"]
                receiver_name = display_info["receiver_name"]
                llm_config = display_info["llm_config"]
                sender_role = display_info["sender_role"]
                
                # Get historical record timestamp
                historical_timestamp = display_info.get("timestamp", None)
                
                # Get historical record new file information
                new_files_json = display_info.get("new_files", "[]")
                if isinstance(new_files_json, str):
                    try:
                        new_files = json.loads(new_files_json)
                    except:
                        new_files = []
                else:
                    new_files = new_files_json if isinstance(new_files_json, list) else []
                
                # If there are new files to display
                if new_files:
                    EnhancedMessageProcessor.display_new_files_header(len(new_files), st)
                    
                    # Filter existing files and use compact display
                    existing_files = []
                    for file_path in new_files:
                        file_path = 'coding/'+file_path.split('/coding/')[-1]
                        if os.path.exists(file_path):  # Check if file still exists
                            existing_files.append(file_path)
                    
                    if existing_files:
                        try:
                            EnhancedMessageProcessor.display_files_compact(existing_files, st)
                        except Exception as e:
                            print(f"Compact display failed in replay, using simple version: {e}")
                            EnhancedMessageProcessor.display_files_compact_simple(existing_files, st)
                
                if sender_role == "assistant":
                    with st.chat_message("user", avatar="🔷" if i<len(display_messages)-1 else "✨"):
                        EnhancedMessageProcessor.streamlit_display_message(
                            st=st,
                            message=message,
                            sender_name=sender_info["name"],
                            receiver_name=receiver_name,
                            llm_config=llm_config,
                            sender_role=sender_role,
                            save_to_history=False,  # Don't save during history replay
                            timestamp=historical_timestamp,  # Pass historical timestamp
                        )
                else:
                    with st.chat_message("assistant", avatar="👨‍💼" if i!=0 else "✨"):
                        EnhancedMessageProcessor.streamlit_display_message(
                            st=st,
                            message=message,
                            sender_name=sender_info["name"],
                            receiver_name=receiver_name,
                            llm_config=llm_config,
                            sender_role=sender_role,
                            save_to_history=False,  # Don't save during history replay
                            timestamp=historical_timestamp,  # Pass historical timestamp
                        )
                
            except Exception as e:
                print(f"\n{'-'*30}\nreplay_display_messages ERROR: {e}\n{'-'*30}\n")

    @staticmethod
    def display_function_tool_message(st, message_data: Dict, show_title: bool = False):
        """Handle display logic for function/tool role messages"""
        id_key = "name" if message_data["role"] == "function" else "tool_call_id"
        tool_id = message_data.get(id_key, "No id found")
        content = message_data.get("content", "")

        if not isinstance(content, str):
            content = str(content)
        content = EnhancedMessageProcessor.fliter_message(content)
        content = content.strip()
        
        if show_title:
            st.markdown(f"📚 **Response Details Expand**")
        
        # Create clearer preview content
        if len(content) > 300:
            preview_content = content[:300] + "..."
        else:
            preview_content = content
        
        # Use multi-line format title to enhance visual distinction
        expander_title = f"""🔥 Length: {len(content)} characters
📋 Preview: {preview_content}"""
        
        with st.expander(expander_title, expanded=False):
            if content.startswith("#"):
                st.markdown(f"""
                <div style="background: var(--background-primary); border-radius: 0.5rem; padding: 1.5rem; border: 1px solid var(--border-color);">
                    {content}
                </div>
                """, unsafe_allow_html=True)
            elif content.startswith(('[', '{')):
                try:
                    json_data = json.loads(content)
                    st.json(json_data)
                except:
                    st.code(content, language="json")
            else:
                st.code(content)

def read_html_as_image(file):
    """Convert HTML to image"""
    if isinstance(file, str):
        with open(file, 'r', encoding='utf-8') as file:
            content = file.read()
    else:
        content = file
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text()

    img = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((10, 10), text, fill=(0, 0, 0), font=font)

    return img

def convert_pdf_to_images(pdf_file):
    """Convert PDF to images"""
    if isinstance(pdf_file, str):
        images = convert_from_path(pdf_file)
    else:
        images = convert_from_bytes(pdf_file)
    return images

def save_temp_file(uploaded_file, temp_path):
    """Save temporary file"""
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return temp_path

def run_pdf_html_reader():
    """PDF and HTML reader interface"""
    import streamlit as st
    
    st.title('Display Local HTML and PDF Content as Images')

    html_file = st.file_uploader("Upload HTML File", type=["html"])
    if html_file is not None:
        html_image = read_html_as_image(html_file.read())
        st.image(html_image, caption='HTML Content', use_column_width=True)

    pdf_file = st.file_uploader("Upload PDF File", type=["pdf"])
    if pdf_file is not None:
        pdf_images = convert_pdf_to_images(pdf_file.read())
        for i, img in enumerate(pdf_images[:1]):
            st.image(img, caption=f'PDF Page {i+1}', use_column_width=True)

def check_openai_message(message, st):
    # Check for empty response
    if not isinstance(message, dict):
        return False
    try:
        if (not message.get("content") and 
            not message.get("function_call") and 
            not message.get("tool_calls") and 
            not message.get("tool_responses")):
            return False
        
        # Check content type
        elif isinstance(message.get("content"), str):
            if st is not None:
                content = message.get("content", "")
                
                # Filter system messages
                if (content.lstrip().startswith("[Current User Question]:") or 
                    content.lstrip().startswith("[History Message]:") or 
                    content == json.dumps(st.session_state.messages, ensure_ascii=False)):
                    return False
                
                # Avoid displaying duplicate messages
                if (hasattr(st.session_state, 'messages') and 
                    st.session_state.messages and 
                    content == st.session_state.messages[-1].get('content', '')):
                    return False
    
    except Exception as e:
        print("check_openai_message ERROR:",e)
        pass
    return True

class TrackableUserProxyAgent(UserProxyAgent):
    """Enhanced user agent"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        context = AppContext.get_instance()
        self.st = context.st

        if self.st is not None:
            self.work_dir = self.st.session_state.work_dir 
            
        if AppConfig.get_instance().is_initialized():
            self.st = None
            self.work_dir = AppConfig.get_instance().get_current_session()['work_dir']

        self.data_save_func_list = [
            # 'get_stock_data',
        ]

    def chat_messages_for_summary(self, agent: Agent) -> list[dict[str, Any]]:
        """A list of messages as a conversation to summarize."""
        
        messages = self._oai_messages[agent]
        if messages and 'tool_calls' in messages[-1]:
            messages = messages[:-1]
        return messages

    def execute_code_blocks(self, code_blocks):
        """Override the code execution to handle path issues"""
        original_path = sys.path.copy()
        original_cwd = os.getcwd()
        
        # Add project root to Python path
        project_root = os.path.dirname(os.path.dirname(self._code_execution_config["work_dir"]))
        if project_root not in sys.path:
            sys.path.append(project_root)
        
        return super().execute_code_blocks(code_blocks)
        
    def _process_received_message(self, message, sender, silent):
        if check_openai_message(self._message_to_dict(message), self.st):
            if self.st is not None and not silent:
                with self.st.chat_message("assistant", avatar="👨‍💼"):
                    colored_header(label=f"{sender.name}", description="", color_name="violet-70")
                    # Process file display and recording before showing message
                    if hasattr(self, 'work_dir') and self.work_dir:
                        previous_files_info = self.st.session_state.get("local_files_info", {})
                        current_files_info, new_files = EnhancedMessageProcessor.display_files_batch(
                            self.work_dir, 
                            previous_files_info, 
                            self.st
                        )
                        self.st.session_state["local_files_info"] = current_files_info
                        
                        # Record new file information for subsequent save_display_info use
                        if new_files:
                            if not hasattr(self.st.session_state, '_current_new_files'):
                                self.st.session_state._current_new_files = []
                            self.st.session_state._current_new_files.extend(new_files)
                    
                    # Process message first
                    processed_message = self._message_to_dict(message)
                    EnhancedMessageProcessor.streamlit_display_message(
                        st=self.st,
                        message=processed_message,
                        sender_name=sender.name,
                        receiver_name=self.name,
                        llm_config=self.llm_config,
                        sender_role="assistant",
                        save_to_history=True,  # Save during normal conversation
                    )
        return super()._process_received_message(message, sender, silent)
    
    def get_func_result(self, function_call, func_return, arguments):
        """Get function results"""
        if arguments is not None:
            try:
                df = pd.read_csv(arguments['save_path'])
                columns = str(df.columns.tolist())
                output = f"""✅ Successfully retrieved {arguments['symbol']} stock data
📅 Time range: {arguments['start_date']} to {arguments['end_date']}
📁 Save location: ```{arguments['save_file']}```
📊 Data columns: ```{columns}```

Data has been saved and is ready for further analysis."""
                func_return['content'] = output
            except Exception as e:
                func_return['content'] = f"Data retrieval completed, but error occurred during preview: {str(e)}"
            
        return func_return
    
    def add_func_params(self, function_call):
        """Add function parameters"""
        arguments = None
        if function_call.get('name', '') in self.data_save_func_list:
            try:
                arguments = json.loads(function_call['arguments'])
                save_file = f"{arguments['symbol']}_{arguments['start_date']}_{arguments['end_date']}.csv"
                save_path = f"{self.work_dir}/{save_file}"
                arguments['save_path'] = save_path
                function_call['arguments'] = json.dumps(arguments)
                arguments['save_file'] = save_file
                os.makedirs(self.work_dir, exist_ok=True)
            except Exception as e:
                print(f"add_func_params ERROR: {e}")
            
        return function_call, arguments


class TrackableAssistantAgent(AssistantAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        context = AppContext.get_instance()
        self.st = context.st
        
        if self.st is not None:
            self.work_dir = self.st.session_state.work_dir

        if AppConfig.get_instance().is_initialized():
            self.st = None
            self.work_dir = AppConfig.get_instance().get_current_session()['work_dir']

    def chat_messages_for_summary(self, agent: Agent) -> list[dict[str, Any]]:
        """Get message list for summary"""
        messages = self._oai_messages[agent]
        if messages and 'tool_calls' in messages[-1]:
            messages = messages[:-1]
        return messages
    
    def display_files(self):
        """Display files"""
        if self.work_dir is None or self.st is None:
            return
        
        try:
            previous_files_info = self.st.session_state.get("local_files_info", {})
            current_files_info, new_files = EnhancedMessageProcessor.display_files_batch(
                self.work_dir, 
                previous_files_info, 
                self.st
            )
            self.st.session_state["local_files_info"] = current_files_info
            
            # Record new file information for subsequent save_display_info use
            if new_files:
                if not hasattr(self.st.session_state, '_current_new_files'):
                    self.st.session_state._current_new_files = []
                self.st.session_state._current_new_files.extend(new_files)
                            
        except Exception as e:
            print(f"\n{'-'*30}\ndisplay_files ERROR: {e}\n{'-'*30}\n")

    def _process_received_message(self, message, sender, silent):
        if check_openai_message(self._message_to_dict(message), self.st):
            if self.st is not None and not silent:
                with self.st.chat_message("assistant", avatar="🔷"):
                    colored_header(label=f"{sender.name}", description="", color_name="violet-70")
                    self.display_files()  
                    # Process message first
                    processed_message = self._message_to_dict(message)
                    EnhancedMessageProcessor.streamlit_display_message(
                        st=self.st,
                        message=processed_message,
                        sender_name=sender.name,
                        receiver_name=self.name,
                        llm_config=self.llm_config,
                        sender_role="user",
                        save_to_history=True,  # Save during normal conversation
                    )
        return super()._process_received_message(message, sender, silent)

class TrackableGroupChatManager(GroupChatManager):
    
    def __init__(self, *args, _streamlit=None, work_dir=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.work_dir = work_dir
        self.st = _streamlit
        self.latest_files_info = {}

    def display_files(self):
        """Display files"""
        if self.work_dir is None:
            return
        
        current_files_info, new_files = EnhancedMessageProcessor.detect_new_files(self.work_dir, self.latest_files_info)
        self.latest_files_info = current_files_info

        if new_files:
            EnhancedMessageProcessor.display_new_files_header(len(new_files), self.st)
            
            for file_path in new_files:
                EnhancedMessageProcessor.display_single_file(file_path, self.st)
            
            # Record new file information for subsequent save_display_info use
            if self.st is not None:
                if not hasattr(self.st.session_state, '_current_new_files'):
                    self.st.session_state._current_new_files = []
                self.st.session_state._current_new_files.extend(new_files)

    def _process_received_message(self, message, sender, silent):
        """Handle received messages"""
        if self.st is not None and not silent:
            with self.st.chat_message("human", avatar="👤"):
                colored_header(label=f"Group Manager: {sender.name}", description="", color_name="green-70")
                self.display_files()
                message = self._message_to_dict(message)

                if message.get('content'):
                    # Limit content length to avoid display issues
                    content = message.get('content', '')
                    if len(content) > 20000:
                        content = content[:20000] + "\n\n[Content truncated...]"
                    message['content'] = content
                
                _print_received_message(message, sender=sender, st=self.st, agent_name=self.name)

        return super()._process_received_message(message, sender, silent)

if __name__ == "__main__":
    run_pdf_html_reader()