import torch
import random
import os
import sys
import inspect
import subprocess
import autogen
import asyncio
import warnings
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple, Annotated, Literal
from autogen import AssistantAgent, UserProxyAgent, ConversableAgent
from src.core.code_utils import filter_pip_output, cut_execute_result_by_token, cut_logs_by_token
from src.utils.pip_install_error.judge_pip_error import judge_pip_package
from src.services.autogen_upgrade.autogen_fix_execution import filter_duplicate_commands
from src.services.autogen_upgrade.file_monitor import get_directory_files, compare_and_display_new_files
from autogen import Agent
from autogen.agentchat.conversable_agent import logger


from autogen.formatting_utils import colored
from autogen.io.base import IOStream


from src.services.agents.agent_client import TrackableAssistantAgent, TrackableUserProxyAgent
from src.services.autogen_upgrade.codeblock_judge import llm_judge_code_blocks, process_and_filter_code_blocks


def check_code_block(content):
    if content is None:
        return None
    if "```" in content:
        import re
        # Use more precise regular expression to match Markdown code blocks and capture language identifiers
        code_block_pattern = r"```[ \t]*(\w+)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```"
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        if not matches:
            return None
        
        # Define list of common programming languages
        common_languages = {
            # Common programming languages
            "python", "python3", 
            "sh", "bash", "shell"
        }
        
        # Shell command related language identifiers
        shell_languages = {"sh", "bash", "shell"}

        code_blocks = []
        for lang, code in matches:
            lang = lang.lower().strip()
            # If language is empty or shell command related, skip
            if lang in common_languages:
                code_blocks.append({"language": lang, "code": code.strip()})
            else:
                return None
        
        return code_blocks if code_blocks else None
    return None

class BasicConversableAgent(ConversableAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _generate_oai_reply_from_client(self, llm_client, messages, cache) -> Optional[Union[str, dict[str, Any]]]:
        # unroll tool_responses
        all_messages = []
        for message in messages:
            tool_responses = message.get("tool_responses", [])
            if tool_responses:
                all_messages += tool_responses
                # tool role on the parent message means the content is just concatenation of all of the tool_responses
                if message.get("role") != "tool":
                    all_messages.append({key: message[key] for key in message if key != "tool_responses"})
            else:
                all_messages.append(message)

        # TODO: #1143 handle token limit exceeded error
        response = llm_client.create(
            context=messages[-1].pop("context", None),
            messages=all_messages,
            cache=cache,
            agent=self,
        )
        extracted_response = llm_client.extract_text_or_completion_object(response)[0]

        if extracted_response is None:
            warnings.warn(f"Extracted_response from {response} is None.", UserWarning)
            return None
        
        # ensure function and tool calls will be accepted when sent back to the LLM
        if not isinstance(extracted_response, str) and hasattr(extracted_response, "model_dump"):
            extracted_response = extracted_response.model_dump()
        if isinstance(extracted_response, dict):
            if extracted_response.get("function_call"):
                extracted_response["function_call"]["name"] = self._normalize_name(
                    extracted_response["function_call"]["name"]
                )
            for tool_call in extracted_response.get("tool_calls") or []:
                tool_call["function"]["name"] = self._normalize_name(tool_call["function"]["name"])
                # Remove id and type if they are not present.
                # This is to make the tool call object compatible with Mistral API.
                if tool_call.get("id") is None:
                    tool_call.pop("id")
                if tool_call.get("type") is None:
                    tool_call.pop("type")
                    
        # Check if both code blocks and tool calls exist simultaneously
        if isinstance(extracted_response, dict) and extracted_response.get('content') and (
            check_code_block(extracted_response['content']) is not None
        ) and (
            extracted_response.get("tool_calls", "") or extracted_response.get("function_call", "")
        ):
            extracted_response.pop("tool_calls", None)
            extracted_response.pop("function_call", None)
            
        return extracted_response


class ExtendedAssistantAgent(BasicConversableAgent, TrackableAssistantAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ExtendedUserProxyAgent(BasicConversableAgent, TrackableUserProxyAgent):
    def __init__(self, remote_repo_path=None, local_repo_path=None, work_dir=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.remote_repo_path = remote_repo_path
        self.local_repo_path = local_repo_path
        self.work_dir = work_dir
        
        # self.replace_function_call_func()
        self.replace_code_execution_func()

    async def a_initiate_chat(
        self,
        recipient: "ConversableAgent",
        clear_history: bool = True,
        silent: Optional[bool] = False,
        cache = None,
        max_turns: Optional[int] = None,
        summary_method = ConversableAgent.DEFAULT_SUMMARY_METHOD,
        summary_args: Optional[dict[str, Any]] = {},
        message = None,
        **kwargs: Any,
    ):
        if kwargs.get('history_message_load', None):
            history_message_load = kwargs.get('history_message_load')
            kwargs.pop('history_message_load')
            clear_history = False
            
            self.chat_messages[recipient] = history_message_load[:-1]
            recipient.chat_messages[self] = history_message_load[:-1]
            self._oai_messages[recipient] = history_message_load[:-1]
            recipient._oai_messages[self] = history_message_load[:-1]
            
            message = history_message_load[-1]['content']
            
        return await super().a_initiate_chat(recipient, clear_history, silent, cache, max_turns, summary_method, summary_args, message, **kwargs)

    def replace_code_execution_func(self):

        # Use a wrapper function to avoid duplicate parameter passing
        def wrapped_code_execution_func(agent, messages=None, sender=None, config=None):
            return self.generate_code_execution_reply_using_executor(messages, sender, config) 
        
        for i, func in enumerate(self._reply_func_list):
            if hasattr(func['reply_func'], '__name__') and '_generate_code_execution_reply_using_executor' in func['reply_func'].__name__:
                del self._reply_func_list[i]
                self.register_reply([Agent, None], wrapped_code_execution_func, ignore_async_in_sync_chat=True, position=i)
        
    def replace_function_call_func(self):

        # Use a wrapper function to avoid duplicate parameter passing
        async def wrapped_a_tool_calls_reply(agent, messages=None, sender=None, config=None):
            message = messages[-1]
            code_blocks = check_code_block(message.get("content", ""))
            if code_blocks is not None:
                return False, None
            return await self.a_generate_tool_calls_reply(messages, sender, config) 
        
        # Use a wrapper function to avoid duplicate parameter passing
        def wrapped_tool_calls_reply(agent, messages=None, sender=None, config=None):
            message = messages[-1]
            code_blocks = check_code_block(message.get("content", ""))
            if code_blocks is not None:
                return False, None
            return self.generate_tool_calls_reply(messages, sender, config)
        
        for i, func in enumerate(self._reply_func_list):
            if hasattr(func['reply_func'], '__name__') and 'a_generate_tool_calls_reply' in func['reply_func'].__name__:
                del self._reply_func_list[i]
                self.register_reply([Agent, None], wrapped_a_tool_calls_reply, ignore_async_in_sync_chat=True, position=i)

            if hasattr(func['reply_func'], '__name__') and 'generate_tool_calls_reply' in func['reply_func'].__name__:
                del self._reply_func_list[i]
                self.register_reply([Agent, None], wrapped_tool_calls_reply, position=i)                

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
        execute_result = await super().a_execute_function(func_call, call_id, verbose)
        is_exec_success, result_dict = execute_result
        if isinstance(result_dict, dict) and 'content' in result_dict and isinstance(result_dict['content'], str):
            result_dict['content'] = cut_logs_by_token(result_dict['content'], max_token=8000)
        return is_exec_success, result_dict

    async def _a_execute_tool_call(self, tool_call):
        tool_call_id = tool_call["id"]
        function_call = tool_call.get("function", {})
        _, func_return = await self.a_execute_function(function_call, call_id=tool_call_id)
        return {
            "tool_call_id": tool_call_id,
            "role": "tool",
            "content": func_return.get("content", ""),
        }
    
    def check_gpu_usage(self):
        # Detect GPU usage, only use idle GPUs
        try:
            import nvidia_smi
            nvidia_smi.nvmlInit()
            free_gpus = []
            for i in range(torch.cuda.device_count()):
                handle = nvidia_smi.nvmlDeviceGetHandleByIndex(i)
                info = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
                # If GPU memory usage is below 20%, consider it idle
                if info.used / info.total < 0.3:
                    free_gpus.append(i)
            if free_gpus:
                os.environ['CUDA_VISIBLE_DEVICES'] = str(random.choice(free_gpus))
            else:
                # If no idle GPU, use all GPUs
                os.environ['CUDA_VISIBLE_DEVICES'] = str(random.choice(range(torch.cuda.device_count())))
            nvidia_smi.nvmlShutdown()
        except Exception as e:
            print(f"Failed to detect GPU usage: {e}")
            # Use all GPUs when error occurs
            os.environ['CUDA_VISIBLE_DEVICES'] = str(random.choice(range(torch.cuda.device_count())))      

    def set_env(self,):

        # Check GPU usage
        # self.check_gpu_usage()
                    
        if self.remote_repo_path and self.remote_repo_path not in sys.path:
            sys.path.append(self.remote_repo_path)
            if 'PYTHONPATH' not in os.environ:
                os.environ['PYTHONPATH'] = f"{self.remote_repo_path}:{self.work_dir}:{os.getcwd()}"
            else:
                if self.remote_repo_path not in os.environ['PYTHONPATH']:
                    os.environ['PYTHONPATH'] = f"{os.environ['PYTHONPATH']}:{self.remote_repo_path}"
                if self.work_dir not in os.environ['PYTHONPATH']:
                    os.environ['PYTHONPATH'] = f"{os.environ['PYTHONPATH']}:{self.work_dir}"

        if self.local_repo_path and self.local_repo_path not in sys.path:
            sys.path.append(self.local_repo_path)
            if 'PYTHONPATH' not in os.environ:
                os.environ['PYTHONPATH'] = f"{self.local_repo_path}:{self.work_dir}:{os.getcwd()}"
            else:
                if self.local_repo_path not in os.environ['PYTHONPATH']:
                    os.environ['PYTHONPATH'] = f"{os.environ['PYTHONPATH']}:{self.local_repo_path}"
                if self.work_dir not in os.environ['PYTHONPATH']:
                    os.environ['PYTHONPATH'] = f"{os.environ['PYTHONPATH']}:{self.work_dir}"
        
        if self.work_dir and self.work_dir not in sys.path:
            sys.path.append(self.work_dir)
            if 'PYTHONPATH' not in os.environ:
                os.environ['PYTHONPATH'] = f"{self.work_dir}:{os.getcwd()}"
            else:
                os.environ['PYTHONPATH'] = f"{os.environ['PYTHONPATH']}:{self.work_dir}"
        


    def process_import_error(self, args, retry_times=0):
        execute_result = args['execute_result']
        if 'ModuleNotFoundError: No module named' in execute_result:
            # If ModuleNotFoundError: No module named appears, need to install library
            # Get libraries to install
            code_blocks = args.get('code_blocks', None)
            
            if code_blocks and isinstance(execute_result, tuple):
                exitcode, logs_all = execute_result
            else:
                logs_all = execute_result
            # Extract module names from error messages
            packages = judge_pip_package(logs_all)
            packages = [package for package in packages if '.' not in  package]
            print(f"Libraries to install: {packages}", flush=True)
            if packages:
                if retry_times < 3:
                    # # Install libraries
                    try:
                        for package in packages:
                            print(f"Auto-installing library: {package}", flush=True)
                            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    except Exception as e:
                        print(f"Library installation failed, error message: {e}", flush=True)
                        return args
                    
                    # # Re-execute code
                    if code_blocks:
                        execute_result = super().execute_code_blocks(code_blocks)
                        args['execute_result'] = execute_result
                        return self.process_import_error(args, retry_times=retry_times+1)
                    else:
                        
                        is_exec_success, execute_result = self.generate_code_execution_reply_using_executor(
                            messages=args['messages'],
                            sender=args['sender'],
                            config=args['config']
                        )
                        args['is_exec_success'] = is_exec_success
                        args['execute_result'] = execute_result
                        
                        return self.process_import_error(args, retry_times=retry_times+1)
                else:
                    args['execute_result'] += f"Please try pip install {','.join(packages)} first to install libraries. If installation fails, please regenerate the code."
        return args

    def clean_execute_result(self, execute_result):
        
        try:
            execute_result = filter_pip_output(execute_result)
            # print(f"Execute code block result 3: {execute_result}")
        except Exception as e:
            # import pdb;pdb.set_trace()
            print(f"ERR Execute code block result 3: {execute_result}")
            
        execute_result = cut_execute_result_by_token(execute_result, max_token=4000)
        
        return execute_result
    
    def execute_code_blocks(self, code_blocks):
        """Override the code execution to handle path issues"""
        # Add project root to Python path
        self.set_env()
        
        # print(f"Execute code block 1: {code_blocks}")
        code_blocks, shell_cmds = filter_duplicate_commands(code_blocks)
        for cmd in shell_cmds:
            print(f"echo {cmd} >> {self._code_execution_config['work_dir']}/run_all_cmd.sh", flush=True)
            os.system(f"echo {cmd} >> {self._code_execution_config['work_dir']}/run_all_cmd.sh")
        # print(f"Execute code block 2: {code_blocks}"))
        
        execute_result = super().execute_code_blocks(code_blocks)
        
        if 0:
            execute_result = self.process_import_error(args={"execute_result": execute_result, "code_blocks": code_blocks})
            execute_result = execute_result['execute_result']
        
        exitcode, logs_all = execute_result
        
        return exitcode, self.clean_execute_result(logs_all)

    def _generate_code_execution_reply_using_executor(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply using code executor."""
        iostream = IOStream.get_default()

        if config is not None:
            raise ValueError("config is not supported for _generate_code_execution_reply_using_executor.")
        if self._code_execution_config is False:
            return False, None
        if messages is None:
            messages = self._oai_messages[sender]
        last_n_messages = self._code_execution_config.get("last_n_messages", "auto")

        if not (isinstance(last_n_messages, (int, float)) and last_n_messages >= 0) and last_n_messages != "auto":
            raise ValueError("last_n_messages must be either a non-negative integer, or the string 'auto'.")

        num_messages_to_scan = last_n_messages
        if last_n_messages == "auto":
            # Find when the agent last spoke
            num_messages_to_scan = 0
            for message in reversed(messages):
                if "role" not in message:
                    break
                elif message["role"] != "user":
                    break
                else:
                    num_messages_to_scan += 1
        num_messages_to_scan = min(len(messages), num_messages_to_scan)
        messages_to_scan = messages[-num_messages_to_scan:]

        # iterate through the last n messages in reverse
        # if code blocks are found, execute the code blocks and return the output
        # if no code blocks are found, continue
        for message in reversed(messages_to_scan):
            if not message["content"]:
                continue
            code_blocks = self._code_executor.code_extractor.extract_code_blocks(message["content"])
            if len(code_blocks) == 0:
                continue
            # Use LLM to judge, deduplicate and sort code blocks
            code_blocks = process_and_filter_code_blocks(code_blocks)
            if len(code_blocks) == 0:
                continue
 
            num_code_blocks = len(code_blocks)
            if num_code_blocks == 1:
                iostream.print(
                    colored(
                        f"\n>>>>>>>> EXECUTING CODE BLOCK (inferred language is {code_blocks[0].language})...",
                        "red",
                    ),
                    flush=True,
                )
            else:
                iostream.print(
                    colored(
                        f"\n>>>>>>>> EXECUTING {num_code_blocks} CODE BLOCKS (inferred languages are [{', '.join([x.language for x in code_blocks])}])...",
                        "red",
                    ),
                    flush=True,
                )
 
            # found code blocks, execute code.
            code_result = self._code_executor.execute_code_blocks(code_blocks)
            exitcode2str = "execution succeeded" if code_result.exit_code == 0 else "execution failed"
            return True, f"exitcode: {code_result.exit_code} ({exitcode2str})\nCode output: {code_result.output}"

        return False, None    


    def generate_code_execution_reply_using_executor(
        self,
        messages: Optional[list[dict[str, Any]]] = None,
        sender: Optional[Agent] = None,
        config: Optional[Union[dict[str, Any], Literal[False]]] = None,
    ):
        """Generate a reply using code executor."""
        # exitcode2str = "execution succeeded" if code_result.exit_code == 0 else "execution failed"
        # return True, f"exitcode: {code_result.exit_code} ({exitcode2str})\nCode output: {code_result.output}"
        
        self.set_env()
        
        # Record files in working directory before execution
        work_dir_path = None
        before_files = {}
        if self.work_dir:
            work_dir_path = Path(self.work_dir)
            before_files = get_directory_files(work_dir_path)
            print(f"Before execution: working directory {self.work_dir} contains {len(before_files)} files", flush=True)
        
        try:
            is_exec_success, execute_result = self._generate_code_execution_reply_using_executor(messages, sender, config)
        except Exception as e:
            error_logs = traceback.format_exc()
            exit_code = 1
            exitcode2str = "execution succeeded" if exit_code==0 else "execution failed"
            return exit_code, f"exitcode: {exit_code} ({exitcode2str})\nCode output: {error_logs}"
        
        if execute_result is None:
            return is_exec_success, None
        
        # Record files in working directory after execution and compare changes
        file_changes_info = ""
        if work_dir_path and work_dir_path.exists():
            after_files = get_directory_files(work_dir_path)
            print(f"After execution: working directory {self.work_dir} contains {len(after_files)} files", flush=True)
            
            try:
                file_changes_info = compare_and_display_new_files(before_files, after_files, work_dir_path)
                if file_changes_info != "No new files generated during execution":
                    print(f"File changes:\n{file_changes_info}", flush=True)
            except Exception as e:
                file_changes_info = f"Error monitoring file changes: {str(e)}"
                print(f"File monitoring error: {traceback.format_exc()}", flush=True)
        
        if 0:
            re_execute_result = self.process_import_error(
                args={
                    "is_exec_success": is_exec_success,
                    "execute_result": execute_result,
                    "messages": messages,
                    "sender": sender,
                    "config": config
                }
            )
        
            is_exec_success = re_execute_result['is_exec_success']
            execute_result = re_execute_result['execute_result']
        
        code_exit = execute_result.split('\nCode output: ')[0]
        code_result = ''.join(execute_result.split('\nCode output: ')[1:])
        
        try:
            code_result = self.clean_execute_result(code_result)
        except Exception as e:
            print(f"clean_execute_result failed: {traceback.format_exc()}")
        
        # Append file change information to execution result
        final_result = f"{code_exit}\nCode output: {code_result}"
        if file_changes_info and file_changes_info != "No new files generated during execution":
            final_result += (
                f"\n\n=== File Changes ===\n{file_changes_info}"
                f"\n\n=== Task Reminder ==="
                f"\n- Please check in conjunction with the task objective whether the expected result files have been generated. If generated, please provide the path to the result files and pay attention to whether the path is correct. If not generated, check if the task execution failed, then think of a new solution and give a specific correction plan."
            )
        
        return is_exec_success, final_result