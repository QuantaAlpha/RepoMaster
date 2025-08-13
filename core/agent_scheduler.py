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
    RepoMaster agent for searching and utilizing GitHub repositories to solve user tasks.
    
    This agent can search for relevant GitHub repositories based on user tasks, analyze repository content,
    and generate solutions. The main work is accomplished through collaboration between scheduler agent and user agent.
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
        Initialize scheduler agent and user agent.
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
    
    async def web_search(self, query: Annotated[str, "Query for general web search to get real-time information or answer non-code-related questions"]) -> str:
        """
        Perform general web search to find real-time information or solve general problems that don't require code.
        
        This method allows the agent to search the internet for the latest information, such as current events and recent data.
        It is suitable for scenarios that require information beyond the model's knowledge scope or need the latest information.
        
        Features:
        - Search the internet and generate answers based on results
        - Provide real-time information about current events and latest data
        - Return formatted search result information
        - Access information beyond the model's knowledge cutoff date
        """
        return await self.repo_searcher.deep_search(query)
    
    async def github_repo_search(self, task: Annotated[str, "Description of tasks that need to be solved through GitHub repositories, used to search for the most relevant code libraries"]) -> str:
        """
        Search for relevant code repositories on GitHub based on task description.
        
        This method is designed to find the most suitable GitHub repositories based on user tasks. It analyzes
        the README files of repositories to determine their relevance and returns a list of repositories
        most suitable for solving the task.

        Returns:
            A JSON string containing a list of the most matching repository information.
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
        return await self.repo_searcher.deep_search(query)
    
    def run_repo_agent(
        self, 
        task_description: Annotated[str, "User's task description to be solved, maintain the completeness of task description, do not omit any information"],
        github_url: Annotated[str, "GitHub repository URL (format: https://github.com/repo_name/repo_name)"],
        input_data: Annotated[Optional[str], "A JSON string representing local input data. Must be provided when user task explicitly mentions or implies the need to use local files as input. Format: '[{\"path\": \"local input data path\", \"description\": \"input data description\"}]'. If task doesn't require local input data, can pass empty list '[]'."]
    ):
        """
        Execute user tasks based on specified GitHub repository.
        
        This method clones the specified GitHub repository, then based on the provided task description and input data,
        calls task manager and agent runner to complete the task execution process. The entire process includes:
        1. Validate and process input data
        2. Initialize task environment (create working directory, clone repository, etc.)
        3. Run code agent to analyze and execute tasks
        
        Returns:
            Result of agent executing the task, usually containing task completion status and description of output content
        """
        if input_data:
            try:
                input_data = json.loads(input_data)
            except:
                raise ValueError("input_data format error, please check input data format")
            
            assert isinstance(input_data, list), "input_data must be list type"
            for data in input_data:
                assert isinstance(data, dict), "Elements in input_data must be dict type"
                assert 'path' in data, "Each data item must contain 'path' field"
                assert 'description' in data, "Each data item must contain 'description' field"
                assert os.path.exists(data['path']), f"Path does not exist: {data['path']}"

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
        Register the toolkit required by the agent.
        """
        register_toolkits(
            [
                self.web_search,
                self.run_repo_agent,
                self.github_repo_search,
            ],
            self.scheduler,
            self.user_proxy,
        )

    def solve_task_with_repo(self, task: Annotated[str, "Detailed task description that user needs to solve"]) -> str:
        """
        Search GitHub repositories and use them to solve user tasks.
        
        This method is the main entry point of RepoMaster, which coordinates the entire solution process:
        1. Search for relevant GitHub repositories
        2. Analyze repository content
        3. Generate solutions
        4. Execute solutions
        
        Args:
            task: Detailed task description that user needs to solve
            
        Returns:
            Complete solution report including found repositories, analyzed methods and execution results
        """
        # Set initial message
        initial_message = task
        
        # Start conversation
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
        """Extract final answer from chat history"""
        # Extract final result
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
    task = "Help me convert '/data/huacan/Code/workspace/RepoMaster/data/DeepResearcher.pdf' to markdown and save"
    result = repo_master.solve_task_with_repo(task)
    print(result)

if __name__ == "__main__":
    test_run_all()
