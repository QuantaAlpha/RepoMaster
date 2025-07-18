import sys
import os
import json
import glob
import asyncio
import traceback
import pandas as pd
import datetime
from autogen import AssistantAgent, UserProxyAgent, GroupChatManager
from autogen.oai.client import OpenAIWrapper
from autogen.agentchat.conversable_agent import ConversableAgent as Agent
from typing import Union, Dict, Callable, Any, TypeVar, List, Tuple

from autogen.formatting_utils import colored

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from pdf2image import convert_from_path, convert_from_bytes
from utils.tools_util import _print_received_message
from utils.tool_streamlit import AppContext
from utils.utils_config import AppConfig

from streamlit_extras.colored_header import colored_header

# 尝试导入UI样式管理器
try:
    from frontend_st.ui_styles import UIComponentRenderer, UIStyleManager
except ImportError:
    UIComponentRenderer = None
    UIStyleManager = None

from autogen.tools.function_utils import load_basemodels_if_needed, serialize_to_str
from autogen.runtime_logging import log_event, log_function_use, log_new_agent, logging_enabled

F = TypeVar("F", bound=Callable[..., Any])

class EnhancedMessageProcessor:
    """增强版消息处理器 - 静态工具类"""
    
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
        创建标准的显示信息格式
        
        Args:
            message_content: 消息内容
            sender_name: 发送者名称
            receiver_name: 接收者名称
            sender_role: 发送者角色 ('user' 或 'assistant')
            llm_config: LLM配置字典
            new_files: 新文件列表
            
        Returns:
            标准格式的显示信息字典
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
        添加显示消息到session_state.display_messages中
        
        Args:
            st: streamlit对象
            message_content: 消息内容
            sender_name: 发送者名称
            receiver_name: 接收者名称
            sender_role: 发送者角色
            llm_config: LLM配置字典
            new_files: 新文件列表
            check_duplicate: 是否检查重复消息
        """
        if not hasattr(st.session_state, 'display_messages'):
            st.session_state.display_messages = []
        
        # 内部调用create_display_info创建标准格式
        display_info = EnhancedMessageProcessor.create_display_info(
            message_content=message_content,
            sender_name=sender_name,
            receiver_name=receiver_name,
            sender_role=sender_role,
            llm_config=llm_config,
            new_files=new_files
        )
            
        # 检查重复（可选）
        if check_duplicate and st.session_state.display_messages:
            last_message = st.session_state.display_messages[-1]
            if last_message.get("message", {}).get("content") == message_content:
                return  # 跳过重复消息
        
        st.session_state.display_messages.append(display_info)
    
    @staticmethod
    def add_message_to_session(st, role: str, content: str, check_duplicate: bool = True):
        """
        将消息添加到session_state.messages中
        
        Args:
            st: streamlit对象
            role: 消息角色 ('user' 或 'assistant')
            content: 消息内容
            check_duplicate: 是否检查重复消息
        """
        if not hasattr(st.session_state, 'messages'):
            st.session_state.messages = []
            
        message = {"role": role, "content": content}
        
        # 检查重复（可选）
        if check_duplicate and st.session_state.messages:
            if st.session_state.messages[-1] == message:
                return  # 跳过重复消息
        
        st.session_state.messages.append(message)
    
    @staticmethod
    def get_latest_files(directory: str) -> List[str]:
        """获取目录中的最新文件"""
        new_files = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.csv', '*.xlsx', '*.json', '*.txt', '*.pdf', '*.html']:
            new_files.extend(glob.glob(os.path.join(directory, ext)))
        return new_files
    
    @staticmethod
    def detect_new_files(work_dir: str, previous_files: List[str]) -> Tuple[List[str], List[str]]:
        """检测新文件并返回当前文件列表和新文件列表"""
        current_files = EnhancedMessageProcessor.get_latest_files(work_dir)
        new_files = list(set(current_files) - set(previous_files))
        return current_files, new_files
    
    @staticmethod
    def display_single_file(file_path: str, st):
        """显示单个文件"""
        file_name = os.path.basename(file_path)
        file_ext = file_path.split('.')[-1].lower()
        
        # 生成唯一的key，基于文件路径
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
                st.dataframe(df.head(100))  # 只显示前100行
                
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
                for i, img in enumerate(pdf_images[:3]):  # 只显示前3页
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
        """显示新文件标题"""
        if new_files_count > 0:
            st.markdown(f"""
            <div style="background: var(--secondary-color); color: white; padding: 0.75rem 1rem; border-radius: 0.5rem; margin: 1rem 0; text-align: center; font-weight: 600;">
                📁 Generated {new_files_count} new files
            </div>
            """, unsafe_allow_html=True)
    
    @staticmethod
    def display_files_batch(work_dir: str, previous_files: List[str], st) -> Tuple[List[str], List[str]]:
        """批量显示文件并返回更新后的文件列表和新文件列表"""
        if work_dir is None or st is None:
            return previous_files, []
        
        try:
            current_files, new_files = EnhancedMessageProcessor.detect_new_files(work_dir, previous_files)
            
            if new_files:
                EnhancedMessageProcessor.display_new_files_header(len(new_files), st)
                
                for file_path in new_files:
                    EnhancedMessageProcessor.display_single_file(file_path, st)
                
                return current_files, new_files
            
        except Exception as e:
            print(f"\n{'-'*30}\ndisplay_files_batch ERROR: {e}\n{'-'*30}\n")
        
        return previous_files, []

    @staticmethod
    def process_tool_calls(tool_calls, st):
        """处理工具调用显示"""
        if not tool_calls:
            return
        
        # 获取所有unique的function names
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
        
        # 显示工具执行状态
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
        
        # 显示详细参数
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
        """增强版Streamlit消息显示"""        
        try:
            # 初始化新文件记录
            if st is not None and save_to_history:
                if not hasattr(st.session_state, '_current_new_files'):
                    st.session_state._current_new_files = []
            
            # 确保message是字典格式
            if isinstance(message, str):
                message = {"content": message}
            elif not isinstance(message, dict):
                message = {"content": str(message)}
            
            # 只在非重现模式下保存完整的显示信息
            if save_to_history and st is not None:
                EnhancedMessageProcessor.save_display_info(
                    st, message, sender_name, receiver_name, llm_config, sender_role
                )
            
            # 处理工具响应
            if message.get("tool_responses"):
                for idx, tool_response in enumerate(message["tool_responses"]):
                    # 直接处理tool_response，避免递归调用
                    if tool_response.get("role") in ["function", "tool"]:
                        # 只在第一个tool_response时显示标题
                        show_title = (idx == 0)
                        EnhancedMessageProcessor.display_function_tool_message(st, tool_response, show_title)
                
                if message.get("role") == "tool":
                    return

            # 处理function/tool角色的消息
            if message.get("role") in ["function", "tool"]:
                EnhancedMessageProcessor.display_function_tool_message(st, message, first_display)
            
            else:
                # 处理普通消息内容
                content = message.get("content")
                if content:
                    content = EnhancedMessageProcessor.fliter_message(content)
                    
                    # 添加时间戳 - 使用传入的timestamp或当前时间
                    if timestamp:
                        # 如果传入了timestamp，需要转换格式
                        try:
                            # 从ISO格式转换为显示格式
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
                
                # 处理function_call
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
                
                # 处理tool_calls
                if "tool_calls" in message and message["tool_calls"]:
                    EnhancedMessageProcessor.process_tool_calls(message["tool_calls"], st)

            # 保存到消息历史
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
        """保存完整的显示信息用于历史对话重现"""
        if st is None or sender_role is None:
            return
            
        if "display_messages" not in st.session_state:
            st.session_state.display_messages = []
        
        try:
            # 将Agent对象转换为可序列化的字典
            sender_info = {
                "name": sender_name,
                "description": "",
                "system_message": "",
            }
            
            # 获取当前检测到的新文件信息（如果存在的话）
            new_files = getattr(st.session_state, '_current_new_files', [])
            
            display_info = {
                "message": message,
                "sender_info": sender_info,
                "receiver_name": receiver_name,
                "llm_config": llm_config if llm_config else {},
                "sender_role": sender_role,
                "timestamp": datetime.datetime.now().isoformat(),
                "new_files": json.dumps(new_files) if new_files else "[]"  # 转为JSON格式保存
            }
            
            st.session_state.display_messages.append(display_info)
            
            # 清除临时的新文件记录
            st.session_state._current_new_files = []
            
        except Exception as e:
            print(f"\n{'-'*30}\nsave_display_info ERROR: {e}\n{'-'*30}\n")

    @staticmethod
    def replay_display_messages(st, display_messages: List[Dict]):
        """重现历史显示消息 - 直接调用streamlit_display_message"""
        
        # 初始化或重置local_files状态，确保重现历史时不重复展示文件
        if "local_files" not in st.session_state:
            st.session_state["local_files"] = []
        
        for i, display_info in enumerate(display_messages):
            try:
                message = display_info["message"]
                sender_info = display_info["sender_info"]
                receiver_name = display_info["receiver_name"]
                llm_config = display_info["llm_config"]
                sender_role = display_info["sender_role"]
                
                # 获取历史记录的时间戳
                historical_timestamp = display_info.get("timestamp", None)
                
                # 获取历史记录的新文件信息
                new_files_json = display_info.get("new_files", "[]")
                if isinstance(new_files_json, str):
                    try:
                        new_files = json.loads(new_files_json)
                    except:
                        new_files = []
                else:
                    new_files = new_files_json if isinstance(new_files_json, list) else []
                
                # 如果有新文件需要展示
                if new_files:
                    EnhancedMessageProcessor.display_new_files_header(len(new_files), st)
                    
                    for file_path in new_files:
                        file_path = 'coding/'+file_path.split('/coding/')[-1]
                        if os.path.exists(file_path):  # 检查文件是否仍然存在
                            EnhancedMessageProcessor.display_single_file(file_path, st)
                
                if sender_role == "assistant":
                    with st.chat_message("user", avatar="🔷" if i<len(display_messages)-1 else "✨"):
                        EnhancedMessageProcessor.streamlit_display_message(
                            st=st,
                            message=message,
                            sender_name=sender_info["name"],
                            receiver_name=receiver_name,
                            llm_config=llm_config,
                            sender_role=sender_role,
                            save_to_history=False,  # 重现历史时不保存
                            timestamp=historical_timestamp,  # 传递历史时间戳
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
                            save_to_history=False,  # 重现历史时不保存
                            timestamp=historical_timestamp,  # 传递历史时间戳
                        )
                
            except Exception as e:
                print(f"\n{'-'*30}\nreplay_display_messages ERROR: {e}\n{'-'*30}\n")

    @staticmethod
    def display_function_tool_message(st, message_data: Dict, show_title: bool = False):
        """处理function/tool角色消息的显示逻辑"""
        id_key = "name" if message_data["role"] == "function" else "tool_call_id"
        tool_id = message_data.get(id_key, "No id found")
        content = message_data.get("content", "")

        if not isinstance(content, str):
            content = str(content)
        content = EnhancedMessageProcessor.fliter_message(content)
        content = content.strip()
        
        if show_title:
            st.markdown(f"📚 **Response Details Expand**")
        
        # 创建更清晰的预览内容
        if len(content) > 300:
            preview_content = content[:300] + "..."
        else:
            preview_content = content
        
        # 使用多行格式的标题，增强视觉区分
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
    """将HTML转换为图像"""
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
    """将PDF转换为图像"""
    if isinstance(pdf_file, str):
        images = convert_from_path(pdf_file)
    else:
        images = convert_from_bytes(pdf_file)
    return images

def save_temp_file(uploaded_file, temp_path):
    """保存临时文件"""
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return temp_path

def run_pdf_html_reader():
    """PDF和HTML阅读器界面"""
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
        
        # 检查内容类型
        elif isinstance(message.get("content"), str):
            if st is not None:
                content = message.get("content", "")
                
                # 过滤系统消息
                if (content.lstrip().startswith("[Current User Question]:") or 
                    content.lstrip().startswith("[History Message]:") or 
                    content == json.dumps(st.session_state.messages, ensure_ascii=False)):
                    return False
                
                # 避免重复显示相同消息
                if (hasattr(st.session_state, 'messages') and 
                    st.session_state.messages and 
                    content == st.session_state.messages[-1].get('content', '')):
                    return False
    
    except Exception as e:
        print("check_openai_message ERROR:",e)
        pass
    return True

class TrackableUserProxyAgent(UserProxyAgent):
    """增强版用户代理"""
    
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
                    # 在显示消息前先处理文件展示和记录
                    if hasattr(self, 'work_dir') and self.work_dir:
                        previous_files = self.st.session_state.get("local_files", [])
                        current_files, new_files = EnhancedMessageProcessor.display_files_batch(
                            self.work_dir, 
                            previous_files, 
                            self.st
                        )
                        self.st.session_state["local_files"] = current_files
                        
                        # 记录新文件信息，供后续的save_display_info使用
                        if new_files:
                            if not hasattr(self.st.session_state, '_current_new_files'):
                                self.st.session_state._current_new_files = []
                            self.st.session_state._current_new_files.extend(new_files)
                    
                    # 先处理message
                    processed_message = self._message_to_dict(message)
                    EnhancedMessageProcessor.streamlit_display_message(
                        st=self.st,
                        message=processed_message,
                        sender_name=sender.name,
                        receiver_name=self.name,
                        llm_config=self.llm_config,
                        sender_role="assistant",
                        save_to_history=True,  # 正常对话时保存
                    )
        return super()._process_received_message(message, sender, silent)
    
    def get_func_result(self, function_call, func_return, arguments):
        """获取函数结果"""
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
        """添加函数参数"""
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
        """获取用于摘要的消息列表"""
        messages = self._oai_messages[agent]
        if messages and 'tool_calls' in messages[-1]:
            messages = messages[:-1]
        return messages
    
    def display_files(self):
        """显示文件"""
        if self.work_dir is None or self.st is None:
            return
        
        try:
            previous_files = self.st.session_state.get("local_files", [])
            current_files, new_files = EnhancedMessageProcessor.display_files_batch(
                self.work_dir, 
                previous_files, 
                self.st
            )
            self.st.session_state["local_files"] = current_files
            
            # 记录新文件信息，供后续的save_display_info使用
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
                    # 先处理message
                    processed_message = self._message_to_dict(message)
                    EnhancedMessageProcessor.streamlit_display_message(
                        st=self.st,
                        message=processed_message,
                        sender_name=sender.name,
                        receiver_name=self.name,
                        llm_config=self.llm_config,
                        sender_role="user",
                        save_to_history=True,  # 正常对话时保存
                    )
        return super()._process_received_message(message, sender, silent)

class TrackableGroupChatManager(GroupChatManager):
    
    def __init__(self, *args, _streamlit=None, work_dir=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.work_dir = work_dir
        self.st = _streamlit
        self.latest_files = []

    def display_files(self):
        """显示文件"""
        if self.work_dir is None:
            return
        
        current_files, new_files = EnhancedMessageProcessor.detect_new_files(self.work_dir, self.latest_files)
        self.latest_files = current_files

        if new_files:
            EnhancedMessageProcessor.display_new_files_header(len(new_files), self.st)
            
            for file_path in new_files:
                EnhancedMessageProcessor.display_single_file(file_path, self.st)
            
            # 记录新文件信息，供后续的save_display_info使用
            if self.st is not None:
                if not hasattr(self.st.session_state, '_current_new_files'):
                    self.st.session_state._current_new_files = []
                self.st.session_state._current_new_files.extend(new_files)

    def _process_received_message(self, message, sender, silent):
        """处理接收到的消息"""
        if self.st is not None and not silent:
            with self.st.chat_message("human", avatar="👤"):
                colored_header(label=f"Group Manager: {sender.name}", description="", color_name="green-70")
                self.display_files()
                message = self._message_to_dict(message)

                if message.get('content'):
                    # 限制内容长度以避免显示问题
                    content = message.get('content', '')
                    if len(content) > 20000:
                        content = content[:20000] + "\n\n[内容已截断...]"
                    message['content'] = content
                
                _print_received_message(message, sender=sender, st=self.st, agent_name=self.name)

        return super()._process_received_message(message, sender, silent)

if __name__ == "__main__":
    run_pdf_html_reader()