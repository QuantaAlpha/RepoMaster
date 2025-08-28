import time
import json
import autogen
from typing import Dict, List, Optional, Union, Any, Tuple, Annotated
from src.utils.toolkits import register_toolkits
import asyncio
import os
import subprocess
from datetime import datetime
from textwrap import dedent
from autogen import Agent, AssistantAgent, UserProxyAgent, ConversableAgent
from autogen.coding import DockerCommandLineCodeExecutor, LocalCommandLineCodeExecutor
from autogen.code_utils import create_virtual_env
from src.core.code_utils import filter_pip_output, get_code_abs_token
from src.core.prompt import USER_EXPLORER_PROMPT, CODE_ASSISTANT_PROMPT, SYSTEM_EXPLORER_PROMPT, TRAIN_PROMPT
from src.core.tool_code_explorer import CodeExplorerTools
from src.services.autogen_upgrade.base_agent import ExtendedUserProxyAgent, ExtendedAssistantAgent, check_code_block
from src.core.base_code_explorer import BaseCodeExplorer
from src.services.agents.deep_search_agent import AutogenDeepSearchAgent
from src.core.agent_docker_executor import EnhancedDockerCommandLineCodeExecutor
from src.utils.tools_cc import FileEditTool
from configs.oai_config import get_llm_config

class CodeExplorer(BaseCodeExplorer):
    def __init__(self, local_repo_path: str, work_dir: str, remote_repo_path=None, llm_config=None, code_execution_config=None, task_type=None, use_venv=False, task_id=None, is_cleanup_venv=True, args={}):
        """Initialize code repository exploration tool"""
        
        # Call base class initialization method
        super().__init__(work_dir, use_venv, task_id, is_cleanup_venv)
        
        self.llm_config = get_llm_config(service_type='code_explore') if llm_config is None else llm_config

        self.code_execution_config = {"work_dir": work_dir, "use_docker": False} if code_execution_config is None else code_execution_config
        
        self.task_type = task_type
        
        self.local_repo_path = local_repo_path
        self.repo_name = local_repo_path.split('/')[-1] if local_repo_path else 'general_workspace'

        self.docker_path_prefix = "/workspace" if remote_repo_path else ''
        self.remote_repo_path = remote_repo_path if remote_repo_path else (self.local_repo_path if local_repo_path else work_dir)
        
        # Set timeout to 2 hours
        self.code_execution_config['timeout'] = 2 * 60 * 60
        self.timeout = 2 * 60 * 60
        # self.timeout = 60*5
        
        self.work_dir = work_dir
        self.args = args
        
        # Add message history summary related parameters
        self.max_tool_messages_before_summary = 2  # How many rounds of tool calls to accumulate before summarizing
        self.current_tool_call_count = 0
        self.token_limit = 2000  # Set token count limit
        self.limit_restart_tokens = 80000  # Set restart token count limit
        
        # self.is_cleanup_venv = False
        
        # If virtual environment is enabled, load or create virtual environment
        if self.use_venv:
            self.venv_context = self._load_venv_context(
                # venv_dir=os.path.dirname(self.work_dir), 
                is_clear_venv=False,
                # base_venv_path='.venvs/base_venv'
            )
        print("="*100)
        time_start = time.time()
        self._setup_tool_library()
        time_end = time.time()
        print(f"init_tool_library time: {time_end - time_start} seconds")
        print("="*100)
        
        # Create AutoGen agents
        self._setup_agents()
    
    def _setup_tool_library(self):
        """Setup tool library"""
        time_start = time.time()
        if self.local_repo_path:
            self.code_library = CodeExplorerTools(
                self.local_repo_path,
                work_dir=self.work_dir,
                docker_work_dir=self.docker_path_prefix
            )
        else:
            self.code_library = None
        time_end = time.time()
        print(f"setup_tool_library time: {time_end - time_start} seconds")
        if self.local_repo_path and self.args.get("repo_init", True):
            time_start = time.time()
            self.code_importance = self.code_library.builder.generate_llm_important_modules(max_tokens=8000)
            time_end = time.time()
            print(f"generate_llm_important_modules time: {time_end - time_start} seconds")
        else:
            self.code_importance = ""

    def token_limit_termination(self, msg):
        """Check if token limit is reached to decide whether to terminate conversation"""
        # Check original termination conditions
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
                
        # Terminate if original conditions are met
        if (
            original_termination and 
            check_code_block(content) is None and
            not check_tool_call(msg)
        ):
            self.is_restart = False
            return True
        
        # Get current conversation history
        messages = self.executor.chat_messages.get(self.explore, [])
        # Calculate total token count
        total_tokens = 0
        for m in messages:
            if m.get("content"):
                total_tokens += get_code_abs_token(str(m.get("content", "")))
        
        # If over the limit, terminate
        if total_tokens > self.limit_restart_tokens:
            self.is_restart = True
            self.chat_turns += len(messages)-1
            return True
        return False
    
    def _setup_agents(self):
        """Setup AutoGen agents"""
        if self.remote_repo_path and not self.use_venv:
            # Use Docker executor
            print("run docker executor")
            executor = EnhancedDockerCommandLineCodeExecutor(
                image="whc_docker",  # Image with PyTorch and CUDA support
                timeout=self.timeout,  # Increase timeout to accommodate more complex computations
                work_dir=self.work_dir,
                keep_same_path=True,
                network_mode="host",
            )
            self.code_execution_config = {"executor": executor}
        elif self.use_venv:
            # Use local virtual environment executor
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
        
        self.issue_searcher = AutogenDeepSearchAgent(
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
        )        

        # Create code analyzer agent
        self.explore = ExtendedAssistantAgent(
            name="Code_Explorer",
            system_message=explorer_system_message,
            llm_config=self.llm_config,
            is_termination_msg=self.token_limit_termination,
        )
        
        # Create executor agent
        self.executor = ExtendedUserProxyAgent(
            name="Coder_Excuter",
            system_message=dedent("""You are the assistant to the code analyzer, responsible for executing code analysis and viewing operations.
            After completing operations, return the results to the code analyzer for analysis.
            When the task is completed or cannot be completed, you should reply "TERMINATE" to end the conversation.
            # Please note:
            - Only reply "TERMINATE" when the code analyzer explicitly indicates that the analysis is complete
            """),
            human_input_mode="NEVER",
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
            is_termination_msg=self.token_limit_termination,
            remote_repo_path=self.remote_repo_path,
            local_repo_path=self.local_repo_path,
            work_dir=self.work_dir,
        )
        
        # Register tool functions
        if self.args.get("function_call", True) and self.code_library:
            self._register_tools()

    async def issue_solution_search(self, issue_description: Annotated[str, "Description of specific programming issues or errors encountered by the user"]) -> str:
        """
        For specific programming issues or errors encountered during code exploration or development, perform web search to find possible solutions.

        Args:
            issue_description: Detailed description of the specific programming issue or error encountered by the user.

        Returns:
            A string containing the solution information found. If no relevant solutions are found, may return an empty string or prompt message.
        """
        query = f"""
Please search for solutions to the following programming issue:
<issue_description>
{issue_description}
</issue_description>

Follow these steps:
1. Search the web (including GitHub, Stack Overflow, official documentation, forums) for solutions, code snippets, or discussions related to this specific issue.
2. Prioritize solutions that are well-explained, come from reputable sources, or are highly rated/accepted.
3. If multiple promising solutions are found, select up to 3 of the most relevant ones.
4. For each selected solution, provide a concise summary, the source URL, and the source name (e.g., "Stack Overflow", "GitHub Gist: foobar.py", "Official Python Docs", "Relevant GitHub Issue").
5. Present the findings as a clear and readable text. You can use markdown for formatting if it helps readability.
If no relevant solutions are found, please indicate that.
"""
        return await self.issue_searcher.a_web_agent_answer(query)

    def _register_tools(self):
        """Register tool functions to the executor agent"""
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
                self.issue_solution_search,
                FileEditTool.edit,
                # self.code_library.view_reference_relationships,
                # self.code_library.get_module_dependencies,
            ],
            self.explore,
            self.executor,
        )
    
    async def analyze_code(self, task: str, max_turns: int = 40) -> str:
        """
        Analyze code repository and complete specific tasks
        
        Args:
            task: User's programming task description
            max_turns: Maximum conversation turns
            
        Returns:
            Analysis results and implementation plan
        """
        # Reset tool call count
        self.task = task
        self.current_tool_call_count = 0
        
        # Set initial message based on task type
        if self.task_type == "general":
            initial_message = CODE_ASSISTANT_PROMPT.format(
                task=task, work_dir=self.work_dir)
        else:
            initial_message = USER_EXPLORER_PROMPT.format(
                task=task, work_dir=self.work_dir, 
                remote_repo_path=self.remote_repo_path, code_importance=self.code_importance)
        
        # initial_message += f"""## Repository directory structure: {self.local_repo_path}\n\n{self.code_library.list_repository_structure(self.local_repo_path)}"""
        
        history_message_list = []
        if self.is_restart and self.restart_count < 2:
            history_message_list = self.executor.chat_messages.get(self.explore, [])
            
            initial_message = self.summary_chat_history(task, history_message_list)
            # print('\n=====initial_message: \n', initial_message)
            self.restart_count += 1
            self.is_restart = False
            history_message_list = json.loads(initial_message)

        # Start conversation
        chat_result = await self.executor.a_initiate_chat(
            self.explore,
            message=initial_message,
            max_turns=max_turns,
            # summary_method="reflection_with_llm"
            history_message_load=history_message_list
        )
        
        if self.is_restart and self.restart_count < 2:
            return await self.analyze_code(task, max_turns)
        
        # Extract final result
        messages = chat_result.chat_history
        final_answer = chat_result.summary.strip().lstrip()

        task_trace_dir = f"res/trace/code_analysis_{self.task_id}"
        # if not os.path.exists(task_trace_dir):
        #     os.makedirs(task_trace_dir)
        
        if 0 and os.path.exists(self.work_dir ):
            with open(f"{self.work_dir}/trace_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt", "w") as f:
                    f.write(json.dumps(messages, ensure_ascii=False, indent=2))
        
        return final_answer
    
    def code_analysis(self, task: Annotated[str, "Programming task description"], max_turns: int = 40) -> str:
        """
        Analyze code repository and complete specific tasks
        
        Args:
            task: User's programming task description
            max_turns: Maximum conversation turns
            
        Returns:
            Analysis results and implementation plan
        """
        try:
            return asyncio.run(self.analyze_code(task, max_turns))
        finally:
            # If virtual environment is enabled, optionally clean up after task completion
            if self.use_venv and hasattr(self, 'cleanup_venv') and self.cleanup_venv:
                self.cleanup_venv()
    
    async def a_code_analysis(self, task: Annotated[str, "Programming task description"], max_turns: int = 40) -> str:
        """
        Analyze code repository and complete specific tasks (asynchronous version)
        
        Args:
            task: User's programming task description
            max_turns: Maximum conversation turns
            
        Returns:
            Analysis results and implementation plan
        """
        try:
            return await self.analyze_code(task, max_turns)
        finally:
            # If virtual environment is enabled, optionally clean up after task completion
            if self.use_venv and hasattr(self, 'cleanup_venv') and self.cleanup_venv:
                self.cleanup_venv()