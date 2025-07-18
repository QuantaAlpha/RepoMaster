import json
from typing import List, Dict, Annotated, Optional, Any, Tuple, Union

import sys
from utils.agent_gpt4 import AzureGPT4Chat
from utils.web_search_agent.tool_web_engine import SerperSearchEngine, WebBrowser
from streamlit_extras.colored_header import colored_header

import streamlit as st
from datetime import datetime
import asyncio
import autogen
import os
from autogen import Agent, AssistantAgent, UserProxyAgent, ConversableAgent
from textwrap import dedent
from utils.toolkits import register_toolkits
import time
from services.autogen_upgrade.base_agent import ExtendedAssistantAgent, ExtendedUserProxyAgent
from services.agents.agent_general_coder import GeneralCoder
from utils.tools_util import get_autogen_message_history

import traceback
import tiktoken  # 添加这个导入用于计算token数量
from copy import deepcopy

from utils.tool_summary import generate_summary

from services.agents.agent_tool_library import AgentToolLibrary
from services.prompts.deepsearch_prompt import EXECUTOR_SYSTEM_PROMPT, DEEP_SEARCH_SYSTEM_PROMPT, DEEP_SEARCH_CONTEXT_SUMMARY_PROMPT, DEEP_SEARCH_RESULT_REPORT_PROMPT

from utils.tool_optimizer_dialog import optimize_execution, optimize_dialogue

from configs.oai_config import get_llm_config


class DeepSearchExecutor(ExtendedUserProxyAgent):
    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
    
    async def a_execute_function(
        self, func_call: dict[str, Any], call_id: Optional[str] = None, verbose: bool = False
    ) -> tuple[bool, dict[str, Any]]:
        """Execute a function call and return the result.

        Override this function to modify the way to execute function and tool calls.

        Args:
            func_call: a dictionary extracted from openai message at "function_call" or "tool_calls" with keys "name" and "arguments".
            call_id: a string to identify the tool call.
            verbose (bool): Whether to send messages about the execution details to the
                output stream. When True, both the function call arguments and the execution
                result will be displayed. Defaults to False.


        Returns:
            A tuple of (is_exec_success, result_dict).
            is_exec_success (boolean): whether the execution is successful.
            result_dict: a dictionary with keys "name", "role", and "content". Value of "role" is "function".

        "function_call" deprecated as of [OpenAI API v1.1.0](https://github.com/openai/openai-python/releases/tag/v1.1.0)
        See https://platform.openai.com/docs/api-reference/chat/create#chat-create-function_call
        """
        code_summary_args = await self.a_merge_code_chat_history(func_call)
        if code_summary_args is not None and isinstance(code_summary_args, str):
            func_call["arguments"] = code_summary_args
        
        return await super().a_execute_function(func_call, call_id, verbose)
        
    
    async def a_merge_code_chat_history(self, func_call: dict[str, Any]):

        func_name = func_call.get("name", "")
        func = self._function_map.get(func_name, None)

        arguments = json.loads(func_call.get("arguments", "{}"))
        print(func_name)
            
        if arguments is not None:
            if isinstance(arguments, dict) and func_name == 'create_code_tool':
                chat_history = self._oai_messages
                clean_chat_history = []
                chat_history = chat_history[[key for key in chat_history.keys()][0]]
                
                for message in chat_history:
                    if message.get("tool_responses", None):
                        continue
                    clean_chat_history.append(message)
                clean_chat_history = json.dumps(clean_chat_history, ensure_ascii=False)
                summary_chat_history = generate_summary(clean_chat_history)
                if arguments.get("chat_history", None) is not None:
                    arguments["chat_history"] = summary_chat_history
                else:
                    arguments["chat_history"] = summary_chat_history
                return json.dumps(arguments, ensure_ascii=False)
                
        return None

def get_researcher_system_message():
    return DEEP_SEARCH_SYSTEM_PROMPT.format(current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")) #+ thinking_prompt


# 新增的Autogen深度搜索实现
class AutogenDeepSearchAgent:
    def __init__(self, llm_config=None, code_execution_config=None, return_chat_history=False, save_log=False):
        self.web_browser = WebBrowser()
        self.llm_config = get_llm_config(service_type="deepsearch") if llm_config is None else llm_config
        self.code_execution_config={"work_dir": 'coding', "use_docker": False} if code_execution_config is None else code_execution_config
        
        self.return_chat_history = return_chat_history
        self.save_log = save_log
        
        # 添加消息历史摘要相关参数
        self.max_tool_messages_before_summary = 2  # 累积多少轮工具调用后进行摘要
        self.current_tool_call_count = 0
        self.token_limit = 2000  # 设置token数量限制
        self.encoding = tiktoken.get_encoding("cl100k_base")  # 使用OpenAI的编码器
        
        # 创建研究员智能体 - 负责思考和分析
        self.researcher = ExtendedAssistantAgent(
            name="researcher",
            system_message=get_researcher_system_message(),
            llm_config=self.llm_config,
            # is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").replace("**", "").endswith("TERMINATE") or '<TERMINATE>' in x.get("content", ""),
            is_termination_msg=lambda x: (x.get("content", "") and len(x.get("content", "").split("TERMINATE")[-1])<5) or (x.get("content", "") and '<TERMINATE>' in x.get("content", "")),
        )
        
        # 创建执行者智能体 - 负责执行搜索和浏览操作
        self.executor = DeepSearchExecutor(
            name="executor",
            system_message=EXECUTOR_SYSTEM_PROMPT,
            human_input_mode="NEVER",
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
            # is_termination_msg=lambda x: x.get("content", "") and len(x.get("content", "").split("TERMINATE")[-1])<5 or '<TERMINATE>' in x.get("content", ""),
            is_termination_msg=lambda x: (x.get("content", "") and len(x.get("content", "").split("TERMINATE")[-1])<5) or (x.get("content", "") and '<TERMINATE>' in x.get("content", "")),
        )
        
        self.agent_tool_library = AgentToolLibrary(
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
            tool_list={
                "agent_coder": False,
                "deep_search": True,
            },
            chat_history_provider=self._get_researcher_chat_history
        )
        
        # 注册工具函数
        self._register_tools()
        
        # 修改智能体的消息处理方法以支持动态摘要
        self._patch_agent_message_handlers()
        
    def _register_tools(self):
        """注册工具函数到执行者智能体"""
        register_toolkits(
            [
                self.agent_tool_library.searching,
                self.agent_tool_library.browsing,
                # self.agent_tool_library.create_code_tool,
            ],
            self.researcher,
            self.executor,
        )
    
    def _patch_agent_message_handlers(self):
        """修补智能体的消息处理方法以支持动态摘要"""
        # 保存原始方法
        original_executor_receive = self.executor._process_received_message
        original_researcher_receive = self.researcher._process_received_message
        
        # 为执行者添加消息处理拦截
        def executor_receive_with_summary(message, sender, silent):
            # 检查是否是来自研究员的函数调用
            message_history = deepcopy(self.executor.chat_messages[self.researcher])
            if sender == self.researcher and len(message_history)>1:
                if 'tool_responses' in message_history[-1] and 'tool_calls' in message_history[-2]:
                    # 增加工具调用计数
                    self._summarize_tool_response(message_history, message)
                    self.current_tool_call_count += 1
            
            # 正常处理消息
            return original_executor_receive(message, sender, silent)
        
        # 为研究员添加消息处理拦截
        def researcher_receive_with_summary(message, sender, silent):
            # 检查是否是来自执行者的工具响应
            if sender == self.executor and self.current_tool_call_count >= self.max_tool_messages_before_summary:
                # 执行消息历史摘要
                # 重置计数器
                self.current_tool_call_count = 0
            
            # 正常处理消息
            return original_researcher_receive(message, sender, silent)
        
        # 替换原始方法
        self.executor._process_received_message = executor_receive_with_summary
        self.researcher._process_received_message = researcher_receive_with_summary
    
    def _summarize_tool_response(self, chat_history, current_message):
        """对消息历史进行摘要处理"""
        # 获取当前对话历史
        
        tool_calls = chat_history[-2]['tool_calls']
        tool_responses_list = chat_history[-1]['tool_responses']
        
        del self.executor.chat_messages[self.researcher][-1]['content']
        del self.researcher.chat_messages[self.executor][-2]['content']

        if not isinstance(tool_responses_list, list):
            tool_responses_list = [tool_responses_list]
        
        summary_list = []
            
        for tool_responses in tool_responses_list:
        
            if isinstance(tool_responses, list) or isinstance(tool_responses, dict):
                tool_responses = json.dumps(tool_responses)
            elif not isinstance(tool_responses, str):
                tool_responses = str(tool_responses)
            
            if isinstance(tool_calls, list) or isinstance(tool_calls, dict):
                tool_calls = json.dumps(tool_calls)
            elif not isinstance(tool_calls, str):
                tool_calls = str(tool_calls)
            
            # 计算token数量而不是字符数
            token_count = len(self.encoding.encode(tool_responses))
            if token_count < self.token_limit:
                continue
            
            # chat_history.append(current_message)
            chat_history = json.dumps(chat_history[:-2], ensure_ascii=False)
            
            # 生成摘要
            response_summary = self._generate_summary_for_search_result(chat_history, tool_responses)
            # print(response_summary)
            summary_list.append(response_summary)
        
        try:
            for idx, sumary in enumerate(summary_list):
                self.executor.chat_messages[self.researcher][-1]['tool_responses'][idx]['content'] = sumary
                self.researcher.chat_messages[self.executor][-2]['tool_responses'][idx]['content'] = sumary
        except Exception as e:
            print(e)
            import pdb;pdb.set_trace()
            

    def _generate_summary_for_search_result(self, messages, tool_responses):
        """为一组消息生成摘要"""
        
        # 使用LLM生成摘要
        summary_prompt = DEEP_SEARCH_CONTEXT_SUMMARY_PROMPT.format(tool_responses=tool_responses, messages=messages)
        
        # 使用研究员的LLM配置创建一个临时客户端来生成摘要
        from autogen.oai import OpenAIWrapper
        client = OpenAIWrapper(**self.llm_config)
        
        # 创建消息列表
        messages_list = [{"role": "user", "content": summary_prompt}]
        
        # 直接使用client的create方法，不传递额外的API参数
        response = client.create(messages=messages_list)
            
        summary = response.choices[0].message.content
        
        return summary
    
    async def deep_search(self, query: str) -> str:
        """
        执行深度搜索并返回结果
        
        参数:
            query: 用户的查询问题
            
        返回:
            搜索结果和回答
        """
        # 重置工具调用计数
        self.current_tool_call_count = 0
        
        self.original_query = query
        
        initial_message = dedent(f"""
        I need you to help me research the following question in depth:
        
        {query}
        """)
        
        self.agent_tool_library.update_chat_history({"original_query": self.original_query})
        self.researcher.update_system_message(get_researcher_system_message())
        
        # 启动对话
        chat_result = await self.executor.a_initiate_chat(
            self.researcher,
            message=initial_message,
            max_turns=30,
            summary_method="reflection_with_llm", # Supported strings are "last_msg" and "reflection_with_llm":
            summary_args= {
                'summary_prompt': DEEP_SEARCH_RESULT_REPORT_PROMPT
            }
        )
        final_answer = self._extract_final_answer(chat_result)
        if self.return_chat_history:
            return final_answer, get_autogen_message_history(chat_result.chat_history)
        return final_answer
    
    def _extract_final_answer(self, chat_result) -> str:
        """从聊天历史中提取最终答案"""
        # 提取最终结果

        final_answer = chat_result.summary
        
        if isinstance(final_answer, dict):
            final_answer = final_answer['content']
        
        if final_answer is None:
            final_answer = ""
        final_answer = final_answer.strip().lstrip()
        
        messages = chat_result.chat_history
        final_content = messages[-1].get("content", "")
        if final_content:
            final_content = final_content.strip().lstrip()
        
        if final_answer == "":
            final_answer = final_content
        
        return final_answer
    
    
    def web_agent_answer(self, query: Annotated[str, "The initial search query"]) -> str:
        """
        执行深度搜索并返回结果
        
        参数:
            query: 用户的查询问题
            
        返回:
            搜索结果的JSON字符串
        """
        return asyncio.run(self.deep_search(query))
    
    async def run(self, query: str) -> str:
        """
        执行深度搜索并返回结果（异步版本）
        """
        self.return_chat_history = True
        final_answer, chat_result = await self.deep_search(query)
        return {
            "final_answer": final_answer,
            "trajectory": chat_result
        }
    
    async def a_web_agent_answer(self, query: Annotated[str, "The initial search query"]) -> str:
        """
        执行深度搜索并返回结果（异步版本）
        
        参数:
            query: 用户的查询问题
            
        返回:
            搜索结果的JSON字符串
        """
        try:
            return await self.deep_search(query)
        except Exception as e:
            error_msg = f"Error occurred during deep search: {str(e)}\n"
            error_msg += "Detailed error information:\n"
            error_msg += traceback.format_exc()
            print(error_msg)
            # 记录到日志文件（可选）
            with open("search_error_log.txt", "a") as f:
                f.write(f"[{datetime.now()}] Query: {query}\n")
                f.write(error_msg)
                f.write("\n-----------------------------------\n")
            return f"Error occurred during search:\n{error_msg}"

    def _get_researcher_chat_history(self) -> dict:
        """
        获取researcher的当前chat_history，用于传递给code_tool
        
        这个方法会：
        1. 获取researcher和executor之间的最新对话历史
        2. 过滤掉工具响应消息，只保留有用的对话内容
        3. 限制消息长度和数量，避免传递过多信息
        4. 添加上下文信息如当前时间和原始查询
        
        Returns:
            dict: 包含处理后的chat_history和相关上下文信息
        """
        try:
            result = {
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # 添加原始查询信息
            if hasattr(self, 'original_query'):
                result["original_query"] = self.original_query
            
            # 获取researcher和executor之间的对话历史
            if hasattr(self.researcher, 'chat_messages') and self.executor in self.researcher.chat_messages:
                chat_messages = self.researcher.chat_messages[self.executor]
                
                chat_messages = json.dumps(chat_messages, ensure_ascii=False)
                # chat_messages = optimize_execution(chat_messages)
                chat_messages = optimize_dialogue(chat_messages)
                
                result["chat_history"] = chat_messages
            
            return result

        except Exception as e:
            print(f"Error getting researcher chat history: {e}")
            import traceback
            traceback.print_exc()
            return {
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": f"Failed to get chat history: {str(e)}"
            }

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("/mnt/ceph/huacan/Code/Tasks/envs/.env")
    
    # 使用新的AutogenDeepSearchAgent
    deep_search_agent = AutogenDeepSearchAgent()
    # 设置测试查询
    # query = "autogen的groupchat是什么流程架构，它的底层system prompt是什么"
    # query = "北京到余姚的最便宜的机票价格"
    # query = "查询今日沪市科创板新股国泰君安的申购代码"
    query = "半导体行业2024年毛利率top30的公司有哪些，并进行排名"
    # query = "Free & free trial accounts can no longer use chat with premium models on Cursor Version 0.45 or less. Please upgrade to Pro or use Cursor Version 0.46 or later. Install Cursor at https://www.cursor.com/downloads or update from within the editor.遇到这个问题怎么解决，cursor还能继续免费使用么"
    answer = deep_search_agent.web_agent_answer(query)
    print(f"Answer: {answer}")  