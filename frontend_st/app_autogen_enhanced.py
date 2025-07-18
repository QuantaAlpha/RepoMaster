import os
import time
import uuid
import random
import joblib
import streamlit as st
import hashlib
import json
import datetime
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, List, Union, Callable, Any
from auth_utils import login, register, generate_user_id
from utils.tool_streamlit import AppContext
from call_agent import AgentCaller

# 导入新的UI管理器
from frontend_st.ui_styles import UIStyleManager, UIComponentRenderer, ChatHistoryManager

# 导入文件浏览器模块
from file_browser import render_file_browser_interface, render_file_browser_button

# 如果ChatHistoryManager不存在，创建一个简单的实现
try:
    from ui_styles import ChatHistoryManager
except ImportError:
    class ChatHistoryManager:
        """Simple chat history manager"""
        
        def get_message_preview(self, messages: List[Dict]) -> str:
            """Get message preview"""
            if not messages:
                return "New conversation"
            
            # 获取第一条用户消息作为预览
            for msg in messages:
                if msg.get('role') == 'user' and msg.get('content'):
                    content = msg['content'].strip()
                    return content[:50] if len(content) > 50 else content
            
            return "New conversation"
        
        def format_timestamp(self, chat_id: str) -> str:
            """Format timestamp"""
            try:
                # 处理包含下划线的chat_id格式（如：1703123456_789）
                if '_' in chat_id:
                    # 将下划线替换回小数点
                    timestamp_str = chat_id.replace('_', '.')
                    timestamp = float(timestamp_str)
                else:
                    # 直接转换为浮点数（兼容旧格式）
                    timestamp = float(chat_id)
                
                dt = datetime.datetime.fromtimestamp(timestamp)
                return dt.strftime("%m/%d %H:%M")
            except (ValueError, OSError):
                return "Unknown time"

# Constants
DATA_DIR = 'data/'
ENV_FILE = "../../configs/.env"
PAST_CHATS_FILE = 'data/past_chats_list'
MODEL_ROLE = 'ai'
AI_AVATAR_ICON = '✨'
USER_AVATAR_ICON = '👤'
MODEL_NAME = "gpt-3.5-turbo"

# 短ID生成函数
def generate_short_id(length: int = 8) -> str:
    """生成短的随机ID，默认8位字符"""
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.choice(chars) for _ in range(length))

def generate_chat_id() -> str:
    """生成聊天ID，格式：时间戳后4位+随机4位"""
    return f'{time.time()}'.replace('.','_')


# Configuration management
def load_config() -> Dict[str, str | None]:
    load_dotenv(ENV_FILE)
    return {
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
    }

# Data management
def initialize_data_directory():
    os.makedirs(DATA_DIR, exist_ok=True)

def get_user_id():
    """获取用户ID"""
    if st.session_state.get('logged_in'):
        return st.session_state.user_id
    else:
        if 'guest_user_id' not in st.session_state:
            st.session_state.guest_user_id = generate_short_id(6)  # 6位短ID
        return st.session_state.guest_user_id

def load_past_chats(user_id: str) -> Dict[str, str]:
    try:
        return joblib.load(f'{DATA_DIR}{user_id}_past_chats')
    except FileNotFoundError:
        return {}

def save_past_chats(user_id: str, past_chats: Dict[str, str]):
    joblib.dump(past_chats, f'{DATA_DIR}{user_id}_past_chats')

def load_chat_messages(user_id: str, chat_id: str) -> List[Dict[str, str]]:
    try:
        return joblib.load(f'{DATA_DIR}{user_id}_{chat_id}_messages')
    except FileNotFoundError:
        return []

def save_chat_messages(user_id: str, chat_id: str, messages: List[Dict[str, str]]):
    joblib.dump(messages, f'{DATA_DIR}{user_id}_{chat_id}_messages')

def load_display_messages(user_id: str, chat_id: str) -> List[Dict]:
    """加载显示消息历史"""
    try:
        return joblib.load(f'{DATA_DIR}{user_id}_{chat_id}_display_messages')
    except FileNotFoundError:
        return []

def save_display_messages(user_id: str, chat_id: str, display_messages: List[Dict]):
    """保存显示消息历史"""
    joblib.dump(display_messages, f'{DATA_DIR}{user_id}_{chat_id}_display_messages')

def save_uploaded_files(uploaded_files, work_dir: str) -> List[str]:
    """Save uploaded files to work directory"""
    from pathlib import Path
    import re
    import datetime
    
    if not uploaded_files:
        return []
    
    file_paths = []
    work_dir_path = Path(work_dir)
    
    # 确保工作目录存在
    work_dir_path.mkdir(parents=True, exist_ok=True)
    
    for uploaded_file in uploaded_files:
        if uploaded_file is not None:
            # 生成安全的文件名
            safe_filename = get_safe_filename(uploaded_file.name)
            file_path = work_dir_path / safe_filename
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            file_paths.append(str(file_path))
            
    return file_paths

def get_safe_filename(filename: str) -> str:
    """Generate safe filename"""
    import re
    import datetime
    
    # 移除危险字符
    safe_name = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # 如果文件名太长，截断它
    if len(safe_name) > 100:
        name_parts = safe_name.rsplit('.', 1)
        if len(name_parts) == 2:
            name, ext = name_parts
            safe_name = name[:90] + '.' + ext
        else:
            safe_name = safe_name[:100]
    
    # 添加时间戳避免重名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name_parts = safe_name.rsplit('.', 1)
    if len(name_parts) == 2:
        name, ext = name_parts
        safe_name = f"{name}_{timestamp}.{ext}"
    else:
        safe_name = f"{safe_name}_{timestamp}"
    
    return safe_name

class EnhancedSidebarManager:
    """Enhanced sidebar manager"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.style_manager = UIStyleManager()
        self.history_manager = ChatHistoryManager()
    
    def render_sidebar(self) -> str:
        """Render enhanced sidebar"""
        with st.sidebar:
            # 动态获取最新的past_chats
            past_chats = load_past_chats(self.user_id)
            
            # 应用侧边栏样式
            self.style_manager.apply_sidebar_styles()
            
            # 侧边栏标题
            st.markdown("""
            <div style="text-align: center; margin-bottom: 2rem;">
                <h2 style="color: var(--primary-color); margin: 0;">💬 Chat Management</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # 新建对话按钮
            if st.button("➕ New Chat", key="new_chat_button", help="Start a new conversation", use_container_width=True):
                return self._create_new_chat(past_chats)
            
            st.markdown("---")
            
            # 聊天历史标题
            st.markdown('<div class="section-title">📚 Chat History</div>', unsafe_allow_html=True)
            
            # 初始化chat_id
            if "chat_id" not in st.session_state:
                st.session_state.chat_id = generate_chat_id()  # 使用短ID
            
            # 渲染聊天历史
            self._render_chat_history(past_chats)
            
            # 底部操作区域
            st.markdown("---")
            self._render_bottom_actions()
            
        return st.session_state.chat_id
    
    def _create_new_chat(self, past_chats: Dict[str, str]) -> str:
        """Create new conversation"""
        new_chat_id = generate_chat_id()  # 使用短ID
        st.session_state.chat_id = new_chat_id
        st.session_state.chat_title = f'Chat-{datetime.datetime.now().strftime("%m/%d %H:%M")}'
        st.session_state.messages = []
        st.session_state.display_messages = []  # 初始化display_messages
        
        # 更新工作目录，确保新聊天有独立的工作目录
        update_work_dir(self.user_id, new_chat_id)
        
        # 清空文件上传相关的状态
        if "local_files" in st.session_state:
            st.session_state.local_files = []
        
        if "file_uploader_key" not in st.session_state:
            st.session_state.file_uploader_key = 0
        st.session_state.file_uploader_key += 1
        
        # 保存到历史记录
        past_chats[new_chat_id] = st.session_state.chat_title
        save_past_chats(self.user_id, past_chats)
        
        st.rerun()
        return new_chat_id
    
    def _render_chat_history(self, past_chats: Dict[str, str]):
        """Render chat history"""
        if not past_chats:
            st.markdown("""
            <div style="text-align: center; color: var(--text-muted); padding: 2rem;">
                <p>No chat history yet</p>
                <p>Start your first conversation!</p>
            </div>
            """, unsafe_allow_html=True)
            return
        
        # 按时间排序显示聊天历史
        sorted_chats = sorted(past_chats.items(), key=lambda x: float(x[0]), reverse=True)
        
        for chat_id, chat_title in sorted_chats:
            messages = load_chat_messages(self.user_id, chat_id)
            display_messages = load_display_messages(self.user_id, chat_id)
            # print("display_messages", display_messages)
            if not display_messages:
                continue
            # 移除这个条件检查，即使没有消息也显示聊天项
            # if not messages:
            #     continue
                
            # 获取预览信息
            if messages:
                preview_text = self.history_manager.get_message_preview(messages)
                message_count = len(messages)
            else:
                preview_text = "New conversation"
                message_count = 0
            
            timestamp = self.history_manager.format_timestamp(chat_id)
            is_active = chat_id == st.session_state.get('chat_id')
            
            # 创建聊天项容器，使用列布局来放置聊天按钮和删除按钮
            col1, col2 = st.columns([5, 1])
            
            with col1:
                # 创建聊天按钮
                button_key = f"chat_button_{chat_id}"
                if message_count > 0:
                    button_label = f"💬 {preview_text[:25]}..."
                else:
                    button_label = f"💬 {chat_title}"
                
                if st.button(
                    button_label, 
                    key=button_key,
                    help=f"{message_count} messages • {timestamp}",
                    use_container_width=True
                ):
                    st.session_state.chat_id = chat_id
                    st.session_state.chat_title = chat_title
                    st.session_state.messages = messages
                    
                    # 加载display_messages
                    display_messages = load_display_messages(self.user_id, chat_id)
                    st.session_state.display_messages = display_messages
                    
                    # 切换对话时更新工作目录，确保每个聊天会话有独立的工作目录
                    update_work_dir(self.user_id, chat_id)
                    
                    # 切换对话时也清空文件上传相关的状态
                    if "local_files" in st.session_state:
                        st.session_state.local_files = []
                    
                    # 重置文件上传器的key
                    if "file_uploader_key" not in st.session_state:
                        st.session_state.file_uploader_key = 0
                    st.session_state.file_uploader_key += 1
                    
                    st.rerun()
            
            with col2:
                # 创建删除按钮 - 使用小图标和自定义样式
                delete_key = f"delete_button_{chat_id}"
                
                # 添加自定义CSS类到删除按钮
                st.markdown("""
                <style>
                div[data-testid="column"]:nth-child(2) button[kind="secondary"] {
                    background: rgba(248, 250, 252, 0.8) !important;
                    color: #94a3b8 !important;
                    border: 1px solid #e2e8f0 !important;
                    border-radius: 0.5rem !important;
                    padding: 0.3rem !important;
                    font-size: 1rem !important;
                    font-weight: 600 !important;
                    transition: all 0.2s ease !important;
                    min-height: 32px !important;
                    width: 100% !important;
                    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
                }
                
                div[data-testid="column"]:nth-child(2) button[kind="secondary"]:hover {
                    background: #ef4444 !important;
                    color: white !important;
                    border-color: #ef4444 !important;
                    transform: scale(1.1) !important;
                    box-shadow: 0 4px 8px rgba(239, 68, 68, 0.3) !important;
                }
                
                div[data-testid="column"]:nth-child(2) button[kind="secondary"]:active {
                    transform: scale(0.95) !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                if st.button(
                    "×", 
                    key=delete_key,
                    help="Delete this conversation",
                    use_container_width=True,
                    type="secondary"
                ):
                    self._delete_chat(chat_id, past_chats)
            
            # 显示元信息
            st.markdown(f"""
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem; text-align: center;">
                📝 {message_count} messages • ⏰ {timestamp}
            </div>
            """, unsafe_allow_html=True)
    
    def _delete_chat(self, chat_id: str, past_chats: Dict[str, str]):
        """Delete chat history"""
        import os
        from pathlib import Path
        
        try:
            # 从past_chats中移除
            if chat_id in past_chats:
                del past_chats[chat_id]
                save_past_chats(self.user_id, past_chats)
            
            # 删除相关文件
            data_dir = Path(DATA_DIR)
            files_to_delete = [
                data_dir / f"{self.user_id}_{chat_id}_messages",
                data_dir / f"{self.user_id}_{chat_id}_display_messages"
            ]
            
            for file_path in files_to_delete:
                if file_path.exists():
                    file_path.unlink()
            
            # 删除工作目录（如果存在）
            pwd = os.getcwd()
            work_dir = Path(f"{pwd}/coding/{self.user_id}/{chat_id}")
            if work_dir.exists():
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            
            # 如果删除的是当前聊天，切换到新聊天
            if chat_id == st.session_state.get('chat_id'):
                # 创建新聊天
                new_chat_id = generate_chat_id()
                st.session_state.chat_id = new_chat_id
                st.session_state.chat_title = f'Chat-{datetime.datetime.now().strftime("%m/%d %H:%M")}'
                st.session_state.messages = []
                st.session_state.display_messages = []
                
                # 更新工作目录
                update_work_dir(self.user_id, new_chat_id)
                
                # 清空文件上传相关的状态
                if "local_files" in st.session_state:
                    st.session_state.local_files = []
                
                if "file_uploader_key" not in st.session_state:
                    st.session_state.file_uploader_key = 0
                st.session_state.file_uploader_key += 1
                
                # 保存新聊天到历史记录
                past_chats[new_chat_id] = st.session_state.chat_title
                save_past_chats(self.user_id, past_chats)
            
            # 显示成功消息
            st.success("Chat history deleted successfully", icon="✅")
            st.rerun()
            
        except Exception as e:
            st.error(f"Delete failed: {str(e)}", icon="❌")
    
    def _render_bottom_actions(self):
        """Render bottom action area"""
        # 用户状态显示
        if st.session_state.get('logged_in'):
            user_name = st.session_state.get('username', 'User')
            st.markdown(f"""
            <div style="padding: 1rem; background: var(--background-tertiary); border-radius: 0.75rem; margin-bottom: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--secondary-color);">
                    👤 <strong>{user_name}</strong>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
                    Logged in user
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🚪 Logout", key="logout_button", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username = None
                st.rerun()
        else:
            st.markdown(f"""
            <div style="padding: 1rem; background: var(--background-tertiary); border-radius: 0.75rem; margin-bottom: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--warning-color);">
                    🏃 <strong>Guest Mode</strong>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">
                    Data saved in local session
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🔑 Login/Register", key="login_button", use_container_width=True):
                st.session_state.show_login = True
                st.rerun()

class EnhancedMessageRenderer:
    """Enhanced message renderer"""
    
    def __init__(self):
        self.component_renderer = UIComponentRenderer()
    
    def display_chat_history(self, messages: List[Dict[str, str]], display_messages: List[Dict] = None):
        """Display chat history"""
        if not messages and not display_messages:
            self._display_welcome_message()
            return
        
        # 如果有display_messages，优先使用它来重现历史对话
        if display_messages:
            self._replay_display_messages(display_messages)
        else:
            # 否则使用原有的消息渲染逻辑
            for i, message in enumerate(messages):
                self._render_single_message(message, i)

        # 添加文件浏览按钮 - 在AI响应后显示
        st.markdown("---")
        render_file_browser_button("after_response", "📁 Browse Work Directory Files", "View files and content generated by Agent")                
    
    def _replay_display_messages(self, display_messages: List[Dict]):
        """Replay historical display messages"""
        # 导入EnhancedMessageProcessor
        from services.agents.agent_client import EnhancedMessageProcessor
        
        # 直接调用EnhancedMessageProcessor的replay方法
        EnhancedMessageProcessor.replay_display_messages(st, display_messages)
    
    def _display_welcome_message(self):
        """Display welcome message"""
        st.markdown("""
        <div style="text-align: center; padding: 4rem 2rem; color: var(--text-secondary);">
            <div style="font-size: 3rem; margin-bottom: 1rem;">✨</div>
            <h2 style="color: var(--primary-color); margin-bottom: 1rem;">RepoMaster</h2>
            <p style="font-size: 1.1rem; margin-bottom: 2rem;">Hello! I'm your AI coding assistant. How can I help you?</p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <div style="background: var(--background-secondary); padding: 1rem; border-radius: 0.75rem; border: 1px solid var(--border-color);">
                    🔍 GitHub Repo Search
                </div>
                <div style="background: var(--background-secondary); padding: 1rem; border-radius: 0.75rem; border: 1px solid var(--border-color);">
                    🐛 Bug Fix & Debug
                </div>
                <div style="background: var(--background-secondary); padding: 1rem; border-radius: 0.75rem; border: 1px solid var(--border-color);">
                    💻 Code Analysis
                </div>
                <div style="background: var(--background-secondary); padding: 1rem; border-radius: 0.75rem; border: 1px solid var(--border-color);">
                    🚀 Project Development
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_single_message(self, message: Dict[str, str], index: int):
        """渲染单条消息 - 简化版本，主要用于基本消息显示"""
        role = message.get('role', 'user')
        content = message.get('content', '')
        
        # 确定头像和样式
        if role == 'user':
            avatar = USER_AVATAR_ICON
        else:
            avatar = AI_AVATAR_ICON
        
        # 使用Streamlit的chat_message组件
        with st.chat_message(role, avatar=avatar):
            # 添加消息头部
            timestamp = datetime.datetime.now().strftime("%H:%M")
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; font-size: 0.875rem; font-weight: 600;">
                <span style="color: var(--{'primary-color' if role == 'user' else 'secondary-color'});">
                    {role.title()}
                </span>
                <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: auto;">
                    {timestamp}
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            # 显示消息内容
            if content:
                st.markdown(content)

def chat_interface():
    """Enhanced chat interface"""
    # 应用主要样式
    style_manager = UIStyleManager()
    style_manager.apply_main_styles()
    
    # 渲染顶部导航
    user_name = st.session_state.get('username', 'Guest')
    UIComponentRenderer.render_top_navigation(title="Code RepoMaster", user_name=user_name)
    
    # 获取用户ID
    user_id = get_user_id()
    
    # 初始化配置和数据
    config = load_config()
    initialize_data_directory()
    past_chats = load_past_chats(user_id)
    
    # 设置增强版侧边栏
    sidebar_manager = EnhancedSidebarManager(user_id)
    chat_id = sidebar_manager.render_sidebar()
    
    # 确保有chat_id
    if not chat_id:
        chat_id = generate_chat_id()  # 使用短ID
        st.session_state.chat_id = chat_id
        st.session_state.chat_title = f'Chat-{datetime.datetime.now().strftime("%m/%d %H:%M")}'
        st.session_state.messages = []
        st.session_state.display_messages = []  # 初始化display_messages
        past_chats[chat_id] = st.session_state.chat_title
        save_past_chats(user_id, past_chats)
    
    # 确保当前聊天在past_chats中
    if chat_id not in past_chats:
        past_chats[chat_id] = st.session_state.get('chat_title', f'Chat-{datetime.datetime.now().strftime("%m/%d %H:%M")}')
        save_past_chats(user_id, past_chats)
    
    # 设置工作目录（在确定chat_id之后）
    work_dir = update_work_dir(user_id, chat_id)
    AppContext.set_streamlit(st)
    
    # 初始化消息
    if 'messages' not in st.session_state:
        st.session_state.messages = load_chat_messages(user_id, chat_id)
    
    # 初始化display_messages
    if 'display_messages' not in st.session_state:
        st.session_state.display_messages = load_display_messages(user_id, chat_id)
    
    # 显示聊天历史
    message_renderer = EnhancedMessageRenderer()
    message_renderer.display_chat_history(
        st.session_state.messages, 
        st.session_state.display_messages
    )
    
    # 初始化 local_files 状态，确保包含当前工作目录中的所有文件
    # 这样可以避免在新对话轮次中重复显示已存在的文件
    if "local_files" not in st.session_state:
        from services.agents.agent_client import EnhancedMessageProcessor
        st.session_state["local_files"] = EnhancedMessageProcessor.get_latest_files(work_dir)
    
    # 文件上传区域 - 放在输入框上方，使用新的简化设计
    st.markdown("---")  # 分隔线
    component_renderer = UIComponentRenderer()
    uploaded_files = component_renderer.render_file_upload_area()
    
    # 显示已上传文件的网格
    if uploaded_files:
        component_renderer.render_uploaded_files_grid(uploaded_files)
    
    # 处理上传的文件 - 在agent_caller初始化之前
    file_paths = []
    if uploaded_files:
        file_paths = save_uploaded_files(uploaded_files, st.session_state.work_dir)
        
        # 将上传的文件添加到local_files中，防止agent重复展示
        if "local_files" not in st.session_state:
            st.session_state["local_files"] = []
        
        # 添加新上传的文件到local_files列表
        for file_path in file_paths:
            if file_path not in st.session_state["local_files"]:
                st.session_state["local_files"].append(file_path)
    
    # 设置代理调用器
    agent_caller = AgentCaller()
    
    # 处理用户输入
    if prompt := st.chat_input('💬 Please input your question...', key="chat_input"):
        # 在开始处理之前，先同步 local_files 状态，确保包含当前工作目录中的所有文件
        # 这样可以避免在新的对话轮次中重复显示已存在的文件
        from services.agents.agent_client import EnhancedMessageProcessor
        current_files = EnhancedMessageProcessor.get_latest_files(st.session_state.work_dir)
        if "local_files" not in st.session_state:
            st.session_state["local_files"] = current_files
        else:
            # 确保包含所有当前存在的文件
            st.session_state["local_files"] = list(set(st.session_state["local_files"] + current_files))
        
        # 清除之前的输出
        st.empty()
        AppContext.get_instance().st.empty()
        
        # 使用简化的接口保存用户消息
        from services.agents.agent_client import EnhancedMessageProcessor
        
        if 0:
            # 保存到基础消息
            EnhancedMessageProcessor.add_message_to_session(
                st=st,
                role="user",
                content=prompt,
                check_duplicate=False
            )
            
            # 保存到显示消息
            EnhancedMessageProcessor.add_display_message_to_session(
                st=st,
                message_content=prompt,
                sender_name="User",
                receiver_name="Assistant",
                sender_role="user",
                check_duplicate=False
            )
        
        # 显示用户消息
        with st.chat_message('user', avatar=USER_AVATAR_ICON):
            timestamp_display = datetime.datetime.now().strftime("%H:%M:%S")
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; font-size: 0.875rem; font-weight: 600;">
                <span style="color: var(--primary-color);">User</span>
                <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: auto;">{timestamp_display}</span>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(prompt)
        
        # 获取AI响应，传递文件路径
        ai_response = agent_caller.create_chat_completion(prompt, user_id, chat_id, file_paths) 
        
        # 保存更新的聊天消息
        save_chat_messages(user_id, chat_id, st.session_state.messages)
        
        # 保存display_messages
        if hasattr(st.session_state, 'display_messages'):
            save_display_messages(user_id, chat_id, st.session_state.display_messages)
        
        # 立即更新past_chats，确保聊天历史能显示
        if chat_id not in past_chats:
            past_chats[chat_id] = st.session_state.get('chat_title', f'Chat-{datetime.datetime.now().strftime("%m/%d %H:%M")}')
            save_past_chats(user_id, past_chats)
        
        # 强制重新渲染页面以更新侧边栏
        st.rerun()

def enhanced_login_interface():
    """Enhanced login interface"""
    style_manager = UIStyleManager()
    style_manager.apply_main_styles()
    
    st.markdown("""
    <div style="display: flex; justify-content: center; align-items: center; min-height: 70vh;">
        <div style="background: var(--background-secondary); padding: 3rem; border-radius: 1rem; border: 1px solid var(--border-color); max-width: 400px; width: 100%;">
            <div style="text-align: center; margin-bottom: 2rem;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">✨</div>
                <h2 style="color: var(--primary-color); margin: 0;">RepoMaster</h2>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">Login to your account</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 调用原有的登录注册逻辑
    if st.session_state.show_register:
        register()
    else:
        login()
    
    # 返回主界面按钮
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🏠 Back to Main", use_container_width=True):
            st.session_state.show_login = False
            st.rerun()

def file_browser_interface():
    """File browser interface"""
    render_file_browser_interface()

def update_work_dir(user_id: str, chat_id: str):
    """Update work directory, ensure each chat session has independent work directory"""
    pwd = os.getcwd()
    work_dir = f"{pwd}/coding/{user_id}/{chat_id}"
    st.session_state.work_dir = work_dir
    os.makedirs(work_dir, exist_ok=True)
    AppContext.set_work_dir(work_dir)
    return work_dir

def main():
    """Main application entry"""
    st.set_page_config(
        page_title="RepoMaster", 
        page_icon="✨",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 初始化session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    if 'show_login' not in st.session_state:
        st.session_state.show_login = False
    if 'show_file_browser' not in st.session_state:
        st.session_state.show_file_browser = False
    
    # 路由逻辑
    if st.session_state.show_login:
        enhanced_login_interface()
    elif st.session_state.show_file_browser:
        file_browser_interface()
    else:
        chat_interface()

if __name__ == "__main__":
    main()