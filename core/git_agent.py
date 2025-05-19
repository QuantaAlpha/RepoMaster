import json
import autogen
from typing import Dict, List, Optional, Union, Any, Tuple, Annotated
from utils.toolkits import register_toolkits
import asyncio
import os
import subprocess
from datetime import datetime
from textwrap import dedent
from autogen import Agent, AssistantAgent, UserProxyAgent, ConversableAgent
from autogen.coding import DockerCommandLineCodeExecutor, LocalCommandLineCodeExecutor
from autogen.code_utils import create_virtual_env
from core.code_utils import filter_pip_output, get_code_abs_token, get_llm_config, llm_generte_response, parse_llm_response
from core.prompt import USER_EXPLORER_PROMPT, SYSTEM_EXPLORER_PROMPT, TRAIN_PROMPT
from core.tool_code_explorer import CodeExplorerTools
from utils.autogen_upgrade.base_agent import ExtendedUserProxyAgent, ExtendedAssistantAgent, check_code_block
from core.base_code_explorer import BaseCodeExplorer

class CodeExplorer(BaseCodeExplorer):
    def __init__(self, local_repo_path: str, work_dir: str, remote_repo_path=None, llm_config=None, code_execution_config=None, task_type=None, use_venv=False, task_id=None, is_cleanup_venv=True, args={}):
        """初始化代码仓库探索工具"""
        
        # 调用基类初始化方法
        super().__init__(work_dir, use_venv, task_id, is_cleanup_venv)
        
        self.llm_config = get_llm_config() if llm_config is None else llm_config
        print(f"llm_config: {self.llm_config}")
        self.code_execution_config = {"work_dir": work_dir, "use_docker": False} if code_execution_config is None else code_execution_config
        
        self.task_type = task_type
        
        self.local_repo_path = local_repo_path
        self.repo_name = local_repo_path.split('/')[-1]

        self.docker_path_prefix = "/workspace" if remote_repo_path else ''
        self.remote_repo_path = remote_repo_path if remote_repo_path else self.local_repo_path
        
        # 设置超时时间 2小时
        self.code_execution_config['timeout'] = 2 * 60 * 60
        self.timeout = 2 * 60 * 60
        # self.timeout = 60*5
        
        self.work_dir = work_dir
        self.args = args
        
        # 添加消息历史摘要相关参数
        self.max_tool_messages_before_summary = 2  # 累积多少轮工具调用后进行摘要
        self.current_tool_call_count = 0
        self.token_limit = 2000  # 设置token数量限制
        self.limit_restart_tokens = 80000  # 设置重启token数量限制
        
        # self.is_cleanup_venv = False
        
        # 如果启用虚拟环境，加载或创建虚拟环境
        if self.use_venv:
            self.venv_context = self._load_venv_context(
                # venv_dir=os.path.dirname(self.work_dir), 
                is_clear_venv=False,
                # base_venv_path='.venvs/base_venv'
            )

        self._setup_tool_library()
        # 创建AutoGen代理
        self._setup_agents()
    
    def _setup_tool_library(self):
        """设置工具库"""
        self.code_library = CodeExplorerTools(
            self.local_repo_path,
            work_dir=self.work_dir,
            docker_work_dir=self.docker_path_prefix
        )
        if self.args.get("repo_init", True):
            self.code_importance = self.code_library.builder.generate_llm_important_modules(max_tokens=8000)
        else:
            self.code_importance = ""

    def token_limit_termination(self, msg):
        """检查是否达到token限制，决定是否终止对话"""
        # 检查原有的终止条件
        def check_tool_call(msg):
            if msg.get("tool_calls", []):
                return True
            if msg.get("tool_response", []):
                return True
            return False
        
        content = msg.get("content", "")
        if isinstance(content, str):
            content = content.strip()
        original_termination = (content and 
                                (len(content.split("TERMINATE")[-1])<3 or 
                                (len(content.split("<TERMINATE>")[-1])<2)))
        
        if msg is None:
            return False
        
        if (not check_tool_call(msg)) and (not content):
            return True
                
        # 如果原有条件满足则终止
        if (
            original_termination and 
            check_code_block(content) is None and
            not check_tool_call(msg)
        ):
            self.is_restart = False
            return True
        
        # 获取当前对话历史
        messages = self.executor.chat_messages.get(self.explore, [])
        # 计算总token数
        total_tokens = 0
        for m in messages:
            if m.get("content"):
                total_tokens += get_code_abs_token(str(m.get("content", "")))
        
        # 如果超过限制则终止
        if total_tokens > self.limit_restart_tokens:
            self.is_restart = True
            self.chat_turns += len(messages)-1
            return True
        return False
    
    def _setup_agents(self):
        """设置AutoGen代理"""
        if self.remote_repo_path and not self.use_venv:
            # 使用Docker执行器
            executor = DockerCommandLineCodeExecutor(
                image="whc_docker",  # 包含PyTorch和CUDA支持的镜像
                timeout=self.timeout,  # 增加超时时间以适应更复杂的计算
                work_dir=self.work_dir,
            )
            self.code_execution_config = {"executor": executor}
        elif self.use_venv:
            # 使用本地虚拟环境执行器
            local_executor = LocalCommandLineCodeExecutor(
                work_dir=self.work_dir,
                timeout=self.timeout,
                virtual_env_context=self.venv_context
            )
            self.code_execution_config = {"executor": local_executor}
            
        additional_instructions = TRAIN_PROMPT if self.task_type == 'kaggle' else ''

        explorer_system_message = SYSTEM_EXPLORER_PROMPT.format(
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            remote_repo_path=self.remote_repo_path,
            additional_instructions=additional_instructions
        )

        # 创建代码分析者智能体
        self.explore = ExtendedAssistantAgent(
            name="Code_Explorer",
            system_message=explorer_system_message,
            llm_config=self.llm_config,
            is_termination_msg=self.token_limit_termination,
        )
        
        # 创建执行者智能体
        self.executor = ExtendedUserProxyAgent(
            name="Coder_Excuter",
            system_message=dedent("""你是代码分析者的助手，负责执行代码分析和查看操作。
            执行完操作后，将结果返回给代码分析者进行分析。
            当任务完成后，或者当前任务无法完成时，你应该回复"TERMINATE"来结束对话。
            # 请注意：
            - 只有在代码分析者明确表示已完成分析时才回复"TERMINATE"
            """),
            human_input_mode="NEVER",
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
            is_termination_msg=self.token_limit_termination,
            remote_repo_path=self.remote_repo_path,
            local_repo_path=self.local_repo_path,
            work_dir=self.work_dir,
        )
        
        # 注册工具函数
        if self.args.get("function_call", True):
            self._register_tools()

    def _register_tools(self):
        """注册工具函数到执行者智能体"""
        register_toolkits(
            [
                self.code_library.list_repository_structure,
                # self.code_library.search_keyword_include_files,
                self.code_library.search_keyword_include_code,
                # self.code_library.view_filename_tree_sitter,
                self.code_library.view_class_details,
                self.code_library.view_function_details,
                self.code_library.find_references,
                self.code_library.find_dependencies,
                self.code_library.view_file_content,
                # self.code_library.view_reference_relationships,
                # self.code_library.get_module_dependencies,
            ],
            self.explore,
            self.executor,
        )
    
    async def analyze_code(self, task: str, max_turns: int = 15) -> str:
        """
        分析代码仓库并完成特定任务
        
        参数:
            task: 用户的编程任务描述
            max_turns: 最大对话轮次
            
        返回:
            分析结果和实现方案
        """
        # 重置工具调用计数
        self.task = task
        self.current_tool_call_count = 0
        
        # 设置初始消息
        initial_message = USER_EXPLORER_PROMPT.format(
            task=task, work_dir=self.work_dir, 
            remote_repo_path=self.remote_repo_path, code_importance=self.code_importance)
        
        # initial_message += f"""## 仓库目录结构：{self.local_repo_path}\n\n{self.code_library.list_repository_structure(self.local_repo_path)}"""
        
        history_message_list = []
        if self.is_restart and self.restart_count < 2:
            history_message_list = self.executor.chat_messages.get(self.explore, [])
            
            initial_message = self.summary_chat_history(task, history_message_list)
            # print('\n=====initial_message: \n', initial_message)
            self.restart_count += 1
            self.is_restart = False
            history_message_list = json.loads(initial_message)

        # 启动对话
        chat_result = await self.executor.a_initiate_chat(
            self.explore,
            message=initial_message,
            max_turns=max_turns,
            # summary_method="reflection_with_llm"
            history_message_load=history_message_list
        )
        
        if self.is_restart and self.restart_count < 2:
            return await self.analyze_code(task, max_turns)
        
        # 提取最终结果
        messages = chat_result.chat_history
        final_answer = chat_result.summary.strip().lstrip()

        task_trace_dir = f"res/trace/code_analysis_{self.task_id}"
        # if not os.path.exists(task_trace_dir):
        #     os.makedirs(task_trace_dir)
        
        if os.path.exists(self.work_dir ):
            with open(f"{self.work_dir}/trace_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt", "w") as f:
                    f.write(json.dumps(messages, ensure_ascii=False, indent=2))
        
        return final_answer
    
    def code_analysis(self, task: Annotated[str, "编程任务描述"], max_turns: int = 15) -> str:
        """
        分析代码仓库并完成特定任务
        
        参数:
            task: 用户的编程任务描述
            max_turns: 最大对话轮次
            
        返回:
            分析结果和实现方案
        """
        try:
            return asyncio.run(self.analyze_code(task, max_turns))
        finally:
            # 如果启用了虚拟环境，任务完成后可以选择清理
            if self.use_venv and hasattr(self, 'cleanup_venv') and self.cleanup_venv:
                self.cleanup_venv()
    
    async def a_code_analysis(self, task: Annotated[str, "编程任务描述"], max_turns: int = 15) -> str:
        """
        分析代码仓库并完成特定任务（异步版本）
        
        参数:
            task: 用户的编程任务描述
            max_turns: 最大对话轮次
            
        返回:
            分析结果和实现方案
        """
        try:
            return await self.analyze_code(task, max_turns)
        finally:
            # 如果启用了虚拟环境，任务完成后可以选择清理
            if self.use_venv and hasattr(self, 'cleanup_venv') and self.cleanup_venv:
                self.cleanup_venv()