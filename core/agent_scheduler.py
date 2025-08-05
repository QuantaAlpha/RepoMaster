import json
import argparse
import asyncio
import os
from typing import Annotated, Optional
from textwrap import dedent
from dotenv import load_dotenv
import autogen
from autogen.cache import Cache

from services.autogen_upgrade.base_agent import ExtendedUserProxyAgent, ExtendedAssistantAgent, check_code_block
from utils.toolkits import register_toolkits

from services.agents.deepsearch_2agents import AutogenDeepSearchAgent

from core.git_task import TaskManager, AgentRunner


scheduler_system_message = dedent("""Role: Task Scheduler

Primary Responsibility:
The Task Scheduler's main duty is to analyze user input, create a task plan based on available tools, and then select and call suitable task tools from the given set to fulfill the user's requirements. This agent is responsible for task scheduling; it first attempts to find a relevant code repository and then uses it to solve the task. If a repository-based solution is not feasible, it will resort to other tools or methods.

Role Description:
As a Task Scheduler, your process involves these key steps:
1.  Task Analysis and Planning:
    *   Upon receiving user input, thoroughly analyze the requirements.
    *   Create a structured plan. This plan must prioritize a two-step approach for tasks potentially solvable by code:
        1.  Search for relevant GitHub repositories using available tools.
        2.  If a suitable repository is identified, plan to use tools to execute the task using that repository.
    *   If a repository-based solution is not appropriate for the task, or as a fallback, the plan should outline the use of other available tools (e.g., general search, financial data tools).

2.  Tool Selection and Execution:
    *   Execute the plan by selecting one appropriate tool at a time.
    *   Repository-First Approach:
        *   If the plan dictates a repository search: Execute the repository search tool.
        *   If a suitable repository is found: Execute the tool for running tasks with the identified repository.
    *   Sequential Execution: Subsequent tools are selected based on the outcomes of previously executed tools, the current state of the plan, and the capabilities of the available tools.
    *   Result Evaluation and Repository Switching:
        *   After executing a task with a repository, critically evaluate if the result actually satisfies the user's requirements.
        *   Consider these evaluation factors: (1) Whether code was successfully executed (2) Whether the output directly addresses the task (3) Whether the result contains relevant information or data requested.
        *   If the current repository failed to produce a satisfactory result, select the next best repository from your search results and execute the task again using that repository.
        *   Continue this process until you find a repository that successfully completes the task or exhaust all viable repository options.

Important Notes:
1. Always consider the specific set of tools provided when creating your task plan and selecting tools for execution.
2. If a tool is successfully called, answer the user's question based on the tool's return results and your overall task plan.
3. If no tool from the given set can satisfy a step in your plan or the user's input question, generate answers based directly on your understanding.
4. When you determine that the task has been completed successfully, only reply "TERMINATE" without continuing the conversation.
5. Be persistent in finding a solution - if one repository doesn't work, try another until the task is properly completed.""")

class RepoMasterAgent:
    """
    RepoMaster代理，用于搜索和利用GitHub仓库解决用户任务。
    
    该代理能够根据用户任务搜索相关的GitHub仓库，分析仓库内容，
    并生成解决方案。主要由调度器代理和用户代理协作完成任务。
    """
    # def __init__(self, local_repo_path: str, work_dir: str, remote_repo_path=None, llm_config=None, code_execution_config=None, task_type=None, use_venv=False, task_id=None, is_cleanup_venv=True, args={}):
    def __init__(self, llm_config=None, code_execution_config=None):
    
        self.llm_config = llm_config
        self.code_execution_config = code_execution_config
        
        self.repo_searcher = AutogenDeepSearchAgent(
            llm_config=self.llm_config,
            code_execution_config=self.code_execution_config,
        )
        
        self.work_dir = code_execution_config['work_dir']
        
        self.initialize_agents()
        self.register_tools()
       
    def initialize_agents(self, **kwargs):    
        """
        初始化调度器代理和用户代理。
        """
        self.scheduler = ExtendedAssistantAgent(
            name="scheduler_agent",
            system_message=scheduler_system_message,
            is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").endswith("TERMINATE"),
            llm_config=self.llm_config,
        )

        self.user_proxy = ExtendedUserProxyAgent(
            name="user_proxy",
            llm_config=self.llm_config,
            is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").endswith("TERMINATE"),
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            code_execution_config=self.code_execution_config,
        )
    
    async def github_repo_search(self, task: Annotated[str, "用户需要解决的任务描述"]) -> str:
        """
        执行GitHub仓库深度搜索并返回适合解决任务的仓库列表。
        返回:
            包含匹配仓库信息的JSON字符串，格式为：
        """
        query = f"""
Please search for GitHub repositories related to the task:
<task>
{task}
</task>

Please search the GitHub repository for the solution.
Follow these steps:
1. Search for the most relevant GitHub repositories based on the task description.
2. Carefully read the README file of each repository.
3. Determine whether the code in the repository can solve this competition task based on the README file.
4. After reading all the README files, select the top 5 GitHub repositories that are most suitable to solve this task (when selecting, consider the code quality of the repository and whether it is suitable to solve this task).
5. Return the result in JSON format.
The JSON format should be like this:
[
    {{
        "repo_name": "repo_name",
        "repo_url": "repo_url",
        "repo_description": "repo_description"
    }},
    ...
]
"""
        return await self.repo_searcher.a_web_agent_answer(query)
    
    def run_repo_agent(
        self, 
        task_description: Annotated[str, "用户需要解决的任务描述, 保持任务描述的完整性, 不要省略任何信息"],
        github_url: Annotated[str, "GitHub仓库URL(格式是: https://github.com/repo_name/repo_name)"],
        input_data: Annotated[Optional[str], "一个JSON字符串，表示本地输入数据。当用户任务中明确提及或暗示需要使用本地文件作为输入时，必须提供此参数。格式为: '[{\"path\": \"本地输入数据路径\", \"description\": \"输入数据描述\"}]'。如果任务不需要本地输入数据，则可传入空列表'[]'。"]
    ):
        """
        基于指定的GitHub仓库执行用户任务。
        
        该方法克隆指定的GitHub仓库，然后根据提供的任务描述和输入数据，
        调用任务管理器和代理运行器完成任务执行过程。整个流程包括：
        1. 验证和处理输入数据
        2. 初始化任务环境（创建工作目录、克隆仓库等）
        3. 运行代码代理分析和执行任务
        
        返回:
            代理执行任务的结果，通常包含任务完成状态和输出内容的描述
        """
        if input_data:
            try:
                input_data = json.loads(input_data)
            except:
                raise ValueError("input_data 格式错误，请检查输入数据格式")
            
            assert isinstance(input_data, list), "input_data必须是列表类型"
            for data in input_data:
                assert isinstance(data, dict), "input_data中的元素必须是字典类型"
                assert 'path' in data, "每个数据项必须包含'path'字段"
                assert 'description' in data, "每个数据项必须包含'description'字段"
                assert os.path.exists(data['path']), f"路径不存在：{data['path']}"

        args = argparse.Namespace(
            config_data={
                "repo": {
                    "type": "github",
                    "url": github_url,
                },
                "task_description": task_description,
                "input_data": input_data,
                "root_path": self.work_dir,
            },
            root_path='coding',
        )
        
        task_info = TaskManager.initialize_tasks(args)

        result = AgentRunner.run_agent(task_info, retry_times=1, work_dir=self.work_dir)        

        return result

    def register_tools(self):
        """
        注册代理所需的工具集。
        """
        register_toolkits(
            [
                self.run_repo_agent,
                self.github_repo_search,
            ],
            self.scheduler,
            self.user_proxy,
        )

    def solve_task_with_repo(self, task: Annotated[str, "用户需要解决的详细任务描述"]) -> str:
        """
        搜索GitHub仓库并利用其解决用户任务。
        
        该方法是RepoMaster的主要入口点，它协调整个解决方案流程：
        1. 搜索相关GitHub仓库
        2. 分析仓库内容
        3. 生成解决方案
        4. 执行解决方案
        
        参数:
            task: 用户需要解决的详细任务描述
            
        返回:
            完整的解决方案报告，包含找到的仓库、解析的方法和执行结果
        """
        # 设置初始消息
        initial_message = task
        
        # 启动对话
        chat_result = self.user_proxy.initiate_chat(
            self.scheduler,
            message=initial_message,
            max_turns=12,
            summary_method="reflection_with_llm", # Supported strings are "last_msg" and "reflection_with_llm":
            summary_args= {
                'summary_prompt': "Summarize takeaway from the conversation and generate a complete and detailed report at last. Do not add any introductory phrases. The final answer should correspond to the user's question."
            }
        )
        final_answer = self._extract_final_answer(chat_result)  
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

def load_env():
    import configs.config
    from dotenv import load_dotenv
    import uuid
    
    llm_config = configs.config.get_llm_config()
    load_dotenv("configs/.env")
    work_dir = os.path.join(os.getcwd(), "coding", str(uuid.uuid4()))
    code_execution_config={"work_dir": work_dir, "use_docker": False}
    
    return llm_config, code_execution_config

def main():
    
    llm_config, code_execution_config = load_env()
    repo_master = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=code_execution_config,
    )
    import asyncio
    result = repo_master.solve_task_with_repo("What is the stock price of APPLE?")
    print(result)

def test_run_repo_agent():
    llm_config, code_execution_config = load_env()
    
    repo_master = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=code_execution_config,
    )

    arguments = {'task_description': 'Extract all text content from the first page of a PDF file and save it to a txt file. The input PDF file path is: GitTaskBench/queries/PDFPlumber_01/input/PDFPlumber_01_input.pdf', 'github_url': 'https://github.com/spatie/pdf-to-text'}    
    
    result = repo_master.run_repo_agent(
        task_description=arguments['task_description'],
        github_url=arguments['github_url'],
        # input_data=json.dumps(input_data)
        input_data=None
    )
    print(result)

def test_run_all():
    llm_config, code_execution_config = load_env()
    
    repo_master = RepoMasterAgent(
        llm_config=llm_config,
        code_execution_config=code_execution_config,
    )
    task = "帮我把 '/data/huacan/Code/workspace/RepoMaster/data/DeepResearcher.pdf' 转成markdown 保存"
    result = repo_master.solve_task_with_repo(task)
    print(result)

if __name__ == "__main__":
    test_run_all()
