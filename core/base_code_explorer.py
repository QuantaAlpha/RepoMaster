import json
import os
import venv
import shutil
import subprocess
import asyncio
from datetime import datetime
from textwrap import dedent
from typing import Dict, List, Optional, Union, Any, Tuple, Annotated

import autogen
from autogen import Agent, AssistantAgent, UserProxyAgent, ConversableAgent
from autogen.coding import DockerCommandLineCodeExecutor, LocalCommandLineCodeExecutor
from autogen.code_utils import create_virtual_env

from utils.autogen_upgrade.base_agent import ExtendedUserProxyAgent
from core.code_utils import filter_pip_output, get_code_abs_token, get_llm_config, llm_generte_response, parse_llm_response


class BaseCodeExplorer:
    """通用代理基类，提供虚拟环境管理和代理设置的基础功能"""
    
    def __init__(self, work_dir: str, use_venv=False, task_id=None, is_cleanup_venv=True):
        """初始化基类代理"""
        
        self.restart_count = 0
        self.chat_turns = 0
        self.is_restart = False
        self.use_venv = use_venv
        self.is_cleanup_venv = False if not is_cleanup_venv and task_id else True
        self.task_id = task_id or datetime.now().strftime('%Y%m%d%H%M%S')
        self.work_dir = work_dir
        
    
    def _load_venv_context(self, venv_dir=None, is_clear_venv=None, base_venv_path=None):
        """加载虚拟环境，如果不存在则创建"""
        
        def load_base_venv(base_venv_path):
            # 如果指定了基础环境且该环境存在，则从基础环境复制
            if base_venv_path and not os.path.exists(base_venv_path):
                os.makedirs(os.path.dirname(base_venv_path), exist_ok=True)
                self._create_virtual_env(base_venv_path)
                    
            if base_venv_path and os.path.exists(base_venv_path):
                if not os.path.exists(self.venv_path):
                    print(f"从基础环境复制: {base_venv_path} -> {self.venv_path}")
                    os.system(f"cp -a {base_venv_path} {self.venv_path}")
                
                # 加载复制后的环境
                env_builder = venv.EnvBuilder(with_pip=True)
                self.venv_context = env_builder.ensure_directories(self.venv_path)
                print(f"成功从基础环境复制并加载虚拟环境")
                return self.venv_context
            return None      
        
        # 确定虚拟环境路径
        if venv_dir is None:
            # 非临时环境且未指定路径，使用默认持久化路径 ./venvs'
            default_venvs_dir = './.venvs'
            self.venv_path = os.path.join(default_venvs_dir, "persistent_venv")
        else:
            self.venv_path = os.path.join(venv_dir, "persistent_venv")            

        # 确保工作目录存在
        venv_dir = os.path.dirname(self.venv_path)
        if not os.path.exists(venv_dir):
            os.makedirs(venv_dir, exist_ok=True)            
        
        if is_clear_venv is not None:
            self.is_cleanup_venv = is_clear_venv
        
        # 如果指定了基础环境，则从基础环境复制
        if base_venv_path:
            venv_context = load_base_venv(base_venv_path)
            if venv_context:
                return venv_context
        
        # 根据is_cleanup_venv决定是否加载或创建环境
        if not self.is_cleanup_venv:
            # 如果不需要清理环境（持久环境），则尝试加载现有环境
            activate_script = os.path.join(self.venv_path, "bin", "activate")
            if os.path.exists(self.venv_path) and os.path.exists(activate_script):
                print(f"加载已存在的虚拟环境: {self.venv_path}")
                env_builder = venv.EnvBuilder(with_pip=True)
                self.venv_context = env_builder.ensure_directories(self.venv_path)
            else:
                print(f"虚拟环境不存在，开始创建: {self.venv_path}")
                self.venv_context = self._create_virtual_env(self.venv_path)
        else:
            # 如果需要清理环境（临时环境），则每次都创建新环境
            print(f"创建新的临时虚拟环境: {self.venv_path}")
            self.venv_context = self._create_virtual_env(self.venv_path)
        
        return self.venv_context
    
    def _create_virtual_env(self, venv_path):
        """创建虚拟环境并安装基础依赖"""
        
        # 使用autogen的方法创建虚拟环境
        self.venv_context = create_virtual_env(venv_path)
        
        # 安装基础依赖 - 使用 . 代替 source，兼容sh和bash
        # 并明确指定使用bash执行命令
        activate_script = os.path.join(venv_path, "bin", "activate")
        activate_cmd = f"bash -c '. {activate_script} && "
        
        print(f"开始安装LLM相关依赖到虚拟环境: {venv_path}", flush=True)
        
        # 更新pip
        subprocess.run(f"{activate_cmd} pip install -U pip'", shell=True)
        
        # 获取requirements文件的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        requirements_path = os.path.join(os.path.dirname(current_dir), "enviroment/llm_requirements.txt")
        
        # 检查requirements文件是否存在
        if os.path.exists(requirements_path):
            print(f"使用requirements文件安装依赖: {requirements_path}")
            # 使用requirements文件安装所有依赖
            subprocess.run(
                f"{activate_cmd} pip install -r {requirements_path}'",
                shell=True
            )
        else:
            print(f"⚠️ 警告: requirements文件不存在 {requirements_path}，使用备用方式安装")
            # 备用方式: 直接安装关键依赖
            subprocess.run(
                f"{activate_cmd} pip install numpy pandas torch transformers==4.35.0 tokenizers'",
                shell=True
            )
        
        print(f"虚拟环境创建并安装完成: {venv_path}", flush=True)
        return self.venv_context
    
    def cleanup_venv(self):
        """清理虚拟环境"""
        if not self.is_cleanup_venv:
            return
        
        if self.use_venv and hasattr(self, 'venv_path') and os.path.exists(self.venv_path):
            shutil.rmtree(self.venv_path)
            print(f"已清理虚拟环境: {self.venv_path}")
    
    
    def _setup_agents(self):
        """设置AutoGen代理（需要在子类中实现）"""
        raise NotImplementedError("子类必须实现_setup_agents方法")
    
    def _register_tools(self):
        """注册工具函数到执行者智能体（需要在子类中实现）"""
        raise NotImplementedError("子类必须实现_register_tools方法")
    
    def summary_chat_history(self, task, all_messages) -> str:
        """总结对话历史"""
        
        last_message_start = len(all_messages)-1
        
        if len(all_messages) <= 3 or 'tool_response' in all_messages[last_message_start]:
            last_message_start = len(all_messages)
        
        history_messages = all_messages[1:last_message_start]
        for idx, message in enumerate(history_messages):
            if 'tool_response' in message:
                history_messages[idx].pop('tool_responses')
        history_messages = json.dumps(history_messages, ensure_ascii=False, indent=2)
        
        system_prompt = dedent("""You are an AI assistant specializing in summarizing technical dialogues for context continuity. Your task is to distill the provided chat history into a concise JSON object, focusing *only* on the information essential for resuming the `task` effectively. Prioritize brevity and relevance for the *next* steps.

# 总结要求：
1.  **识别核心路径**: 从历史记录中提取与完成原始任务最相关的、最有效的步骤序列（包括工具调用、代码生成与执行）。忽略不重要或偏离目标的交互。
2.  **提取关键代码与结果**: 包含直接服务于任务目标、或揭示了重要信息的代码片段及其执行结果（成功或失败的分析）。避免冗余。
3.  **反思与学习**: 如果历史中存在错误或挑战，简要分析原因，并说明从中得到的经验或后续应如何调整策略。
4.  **忠于原文**: 严格基于提供的历史内容进行总结，不要添加历史中不存在的信息或进行不必要的推断。
5.  **严格的 JSON 输出**: 最终输出必须是一个单一、完整、语法正确的 JSON 对象，严格遵循下面指定的结构。注意 JSON 语法细节，如逗号、引号、括号的正确使用。

## JSON 输出结构：
```json
{
    "history_summary": [ // 使用 "history_summary" 作为顶层键
        {
            "subtask_goal": "{{当前步骤或子任务的目标描述}}", // 明确这一步的目标
            "tool_calls": [ // 如果此步骤有工具调用
                {
                    "function_name": "{{工具函数名称}}",
                    "arguments": "{{工具函数参数}}",
                    "response_summary": "{{工具调用结果的关键信息或结论摘要}}"
                }
                 // ... 其他工具调用 ...
            ], // 如果没有工具调用，则此键可以省略或设置为空数组 []
            "code_executions": [ // 如果此步骤有代码生成和执行
                {
                    "intention": "{{生成此代码的目的}}",
                    "code": "{{生成的代码片段}}",
                    "execution_result_analysis": "{{代码执行结果的分析（成功、失败原因、关键输出）}}"
                }
                // ... 其他代码执行 ...
            ], // 如果没有代码执行，则此键可以省略或设置为空数组 []
            "reflection": "{{对此步骤的反思、错误分析或经验教训，可选}}" // 如果有值得反思的地方
        }
        // ... 其他关键历史步骤的总结 ...
    ]
}
```
""")

        user_prompt = dedent(f"""请根据 System Prompt 中的指示，基于以下原始任务和对话历史，生成所需的 JSON 总结。

**原始任务**
<task>
{task}
</task>

**对话历史**
<chat_history>
{history_messages}
</chat_history>

**请再次确认：你的输出必须是一个符合 System Prompt 中定义的结构的单一、有效的 JSON 对象。**
""")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        summary = llm_generte_response(messages, llm_config=self.llm_config or None)
        try:
            parsed_summary = parse_llm_response(summary)
            summary = json.dumps(parsed_summary, ensure_ascii=False)
        except Exception as e:
            print(f"ERR summary_chat_history: {e}")
            pass

        # 构造用于总结的消息列表
        messages_summary = {
            "content": summary,
            "role": 'assistant',
            "name": "history_summary",
        }

        out_summary_message = all_messages[:1] + [messages_summary] + all_messages[last_message_start:]
        
        for idx, message in enumerate(out_summary_message):
            if 'tool_response' in message:
                out_summary_message[idx].pop('tool_responses')
        return json.dumps(out_summary_message, ensure_ascii=False, indent=2) 