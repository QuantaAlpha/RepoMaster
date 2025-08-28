import json
import argparse
import asyncio
import os
from typing import Annotated, Optional
from textwrap import dedent
from dotenv import load_dotenv
import autogen
from autogen.cache import Cache

from src.services.autogen_upgrade.base_agent import ExtendedUserProxyAgent, ExtendedAssistantAgent, check_code_block
from src.utils.toolkits import register_toolkits

from src.services.agents.deep_search_agent import AutogenDeepSearchAgent

from src.core.git_task import TaskManager, AgentRunner


scheduler_system_message = dedent("""Role: Enhanced Task Scheduler

Primary Responsibility:
The Enhanced Task Scheduler's main duty is to analyze user input, create a structured task plan based on available tools, and then select and call appropriate tools from the given set to fulfill user requirements. The Enhanced Task Scheduler can work in four distinct modes to fulfill user requirements:
1. **Web Search Mode**: Search the internet for real-time information, current events, or general knowledge.
2. **Repository Mode**: Search and use GitHub repositories or local repositories to solve tasks through hierarchical repository analysis and autonomous exploration. This is the primary approach for complex coding tasks that require repository-level solutions.
3. **General Code Assistant Mode**: Provide general programming assistance without specific repositories.

Mode Selection Strategy:
- **Prioritize Web Search**: Before selecting a primary mode, first determine if the user's query can be directly answered or solved using the `web_search` tool. This is ideal for questions requiring real-time data, definitions, or general knowledge.
- **Repository Mode**: Use `run_repository_agent` for tasks involving code repositories. This unified tool automatically detects whether the repository is a GitHub URL or local path. Triggered when:
  * User mentions local file paths, specific local directories, or phrases like "analyze this local repo"
  * User wants to find existing solutions, mentions GitHub, or needs specialized tools/libraries
  * User provides specific repository URLs or paths
- **General Code Assistant Mode**: Used for general programming questions, requests for code examples, debugging help, or when no specific repository is mentioned.

Working Process:
1.  **Task Analysis and Initial Assessment**:
    *   Upon receiving user input, thoroughly analyze the requirements.
    *   **Step 1 - Web Search Assessment**: Determine if the task requires real-time data, latest information, current events, or external knowledge that would benefit from web search. If yes, execute web search first.
    *   **Step 2 - Plan Creation**: Create a structured plan. For tasks potentially solvable by Repository Mode, this plan must prioritize a two-step approach:
        1.  Search for relevant GitHub repositories using available tools.
        2.  If a suitable repository is identified, plan to use the unified repository tool to execute the task using that repository.

2.  **Tool Selection and Execution Based on Mode**:
    *   Execute the plan by selecting one appropriate tool at a time.
    *   **Repository Mode (GitHub/Local)**: Use the `run_repository_agent` tool with the repository URL or local path. The tool automatically detects whether it's a GitHub repository or local repository.
    *   **General Code Assistant Mode**: Use the `run_general_code_assistant` tool for programming guidance and solutions.
    *   **Web Search**: Use the `web_search` tool for any queries that require real-time information, external documentation, or general knowledge. This tool can be used on its own for non-coding questions or as a part of solving a larger coding task.
    *   **Repository Mode (Repository-First Approach)**:
        1.  **Repository Search**: First, use the `github_repo_search` tool to find a list of the most relevant GitHub repositories for the task.
        2.  **Sequential Execution**: Select the most promising repository from the search results and execute the task using the `run_repository_agent` tool.
        3.  **Result Evaluation and Switching**:
            *   After execution, critically evaluate if the result satisfies the user's requirements. Consider: (1) Was code successfully executed? (2) Does the output directly address the task? (3) Does the result contain the requested information?
            *   If the current repository failed to produce a satisfactory result, select the *next best* repository from the search results and try again with `run_repository_agent`.
            *   Continue this process of executing and evaluating until a repository successfully completes the task, or all viable repository options have been exhausted.

3.  **Sequential Execution and Fallback**:
    *   Subsequent tools are selected based on: (1) The outcomes of previously executed tools (2) The current state of the plan (3) The capabilities of the available tools.
    *   Execute the selected tool(s) according to the plan.
    *   If one approach (e.g., Repository mode) doesn't yield a solution, consider trying an alternative mode if appropriate (e.g., switching to General Code Assistant Mode).
    *   Be persistent in finding a solution. If one repository doesn't work, try another.

Important Notes:
1.  Always validate that local paths exist before using the repository mode with local paths.
2.  In general code assistant mode, aim to create practical, executable examples.
3.  If a tool is successfully called, answer based on the tool's results and your overall task plan.
4.  If no available tool can solve the task, generate an answer based on your own knowledge.
5.  When the task is completed successfully, reply ONLY with "TERMINATE".

Turn-taking and De-duplication Policy:
- Before sending any message, compare it with the previous two messages. If your response would substantially repeat previously stated content (facts, sentences, or structure), do not restate it. If the task has already been fully answered, reply with exactly "TERMINATE" instead.
""")

user_proxy_system_message = dedent("""Role: Execution Proxy (User Proxy)

Primary Rules:
- Do not provide user-facing answers.
- Never paraphrase or repeat content already provided by scheduler_agent.
- Summarize tool outputs succinctly for the scheduler_agent only when needed; avoid restating conclusions.
- If your candidate message would substantially repeat the last two messages, send exactly "TERMINATE" instead.
- After scheduler_agent has delivered the final complete answer, respond with exactly "TERMINATE" and stop.
""")

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
            system_message=user_proxy_system_message,
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
    
    def run_repository_agent(
        self, 
        task_description: Annotated[str, "Task description that the user needs to solve, maintain the completeness of the task description without omitting any information"],
        repository: Annotated[str, "Repository path or URL. Can be a GitHub repository URL (format: https://github.com/repo_name/repo_name) or local repository absolute path (e.g.: /path/to/my/project)"],
        input_data: Annotated[Optional[str], "JSON string representing local input data. Must be provided when the user task explicitly mentions or implies the need to use local files as input. Format: '[{\"path\": \"local input data path\", \"description\": \"input data description\"}]'. If the task does not require local input data, an empty list '[]' can be passed."] = None,
        repo_type: Annotated[Optional[str], "Repository type, optional values: 'github' or 'local'. If not specified, it will be automatically detected"] = None
    ):
        """
        Unified interface for executing user tasks based on specified repository (GitHub or local).
        
        This method automatically detects or handles GitHub repositories or local repositories based on specified type,
        then calls the task manager and agent runner to complete the task execution process based on the provided
        task description and input data. The entire process includes:
        1. Automatically detect repository type or use specified type
        2. Validate repository path or URL validity
        3. Validate and process input data
        4. Initialize task environment (create working directory, clone or copy repository, etc.)
        5. Run code agent to analyze and execute tasks
        
        Args:
            task_description: Detailed description of the task to be completed
            repository: Repository path or URL, supports GitHub URL or local absolute path
            input_data: Optional JSON string representing input data files
            repo_type: Optional repository type, automatically detected if not specified
            
        Returns:
            Result of agent executing the task, usually containing task completion status and output content description
        """
        # Automatically detect repository type
        if repo_type is None:
            if repository.startswith(('http://', 'https://')) and 'github.com' in repository:
                repo_type = 'github'
            elif os.path.exists(repository):
                repo_type = 'local'
            else:
                # Try to determine if it's a GitHub URL format
                if repository.startswith(('http://', 'https://')) or repository.count('/') >= 1:
                    repo_type = 'github'
                else:
                    raise ValueError(f"Unable to determine repository type. Please provide a valid GitHub URL or local path: {repository}")
        
        # Validate repository
        if repo_type == 'local':
            if not os.path.exists(repository):
                raise ValueError(f"Local repository path does not exist: {repository}")
        elif repo_type == 'github':
            # Basic GitHub URL format validation
            if not (repository.startswith(('http://', 'https://')) or 
                   ('github.com' in repository or repository.count('/') >= 1)):
                raise ValueError(f"Invalid GitHub repository URL format: {repository}")
        else:
            raise ValueError(f"Unsupported repository type: {repo_type}. Supported types: 'github', 'local'")
        
        # Validate and process input data
        if input_data:
            try:
                input_data = json.loads(input_data)
            except:
                raise ValueError("input_data format error, please check input data format")
            
            assert isinstance(input_data, list), "input_data must be of list type"
            for data in input_data:
                assert isinstance(data, dict), "Elements in input_data must be of dict type"
                assert 'path' in data, "Each data item must contain 'path' field"
                assert 'description' in data, "Each data item must contain 'description' field"
        else:
            input_data = []

        # Build configuration based on repository type
        if repo_type == 'github':
            repo_config = {
                "type": "github",
                "url": repository,
            }
        else:  # local
            repo_config = {
                "type": "local", 
                "path": repository,
            }

        args = argparse.Namespace(
            config_data={
                "repo": repo_config,
                "task_description": task_description,
                "input_data": input_data,
                "root_path": self.work_dir,
            },
            root_path='coding',
        )
        
        task_info = TaskManager.initialize_tasks(args)
        result = AgentRunner.run_agent(task_info, retry_times=1, work_dir=self.work_dir)        

        return result

    def run_general_code_assistant(
        self,
        task_description: Annotated[str, "Programming task or question that needs general coding assistance"],
        work_directory: Annotated[Optional[str], "Specific working directory for code execution. If not provided, uses default work directory"] = None
    ):
        """
        Provide general programming assistance without requiring a specific repository.
        
        This method creates a clean workspace and uses the code exploration agent to help with:
        - General programming questions and guidance
        - Writing and executing code snippets
        - Debugging and troubleshooting
        - Creating examples and demonstrations
        - Algorithm implementations
        - Code explanations and tutorials
        
        Args:
            task_description: Detailed description of the programming task or question
            work_directory: Optional specific working directory for code execution
            
        Returns:
            Result containing programming guidance, code examples, and execution results
        """
        import asyncio
        from src.core.agent_code_explore import CodeExplorer
        
        # Determine working directory
        work_dir = work_directory or self.work_dir
        
        # Create CodeExplorer instance for general programming assistance
        explorer = CodeExplorer(
            local_repo_path=None,
            work_dir=work_dir,
            task_type="general",
            use_venv=True,
            is_cleanup_venv=False,
        )
        
        # Enhance the task description for general programming assistance
        enhanced_task = f"""
You are a general programming assistant. Please help with the following task:

{task_description}

As a programming assistant, you can:
- Write and execute code to solve problems
- Provide programming guidance and explanations  
- Create practical examples and demonstrations
- Debug and troubleshoot issues
- Implement algorithms and data structures
- Explain programming concepts
- Create utility scripts and tools

Working directory: {work_dir}

Please provide comprehensive help including code examples, explanations, and practical solutions.
"""
        
        result = asyncio.run(explorer.a_code_analysis(enhanced_task, max_turns=20))
        return result

    def register_tools(self):
        """
        Register the enhanced toolkit required by the agent.
        """
        register_toolkits(
            [
                self.web_search,
                self.run_repository_agent,           # Unified repository processing mode
                self.run_general_code_assistant,     # General code assistant mode
                self.github_repo_search,
            ],
            self.scheduler,
            self.user_proxy,
        )

    def solve_task_with_repo(self, task: Annotated[str, "Detailed task description that user needs to solve"]) -> str:
        """
        Enhanced RepoMaster that can work with GitHub repositories, local repositories, or provide general programming assistance.
        
        This method is the main entry point of Enhanced RepoMaster, which automatically determines the best approach:
        
        **Three Working Modes:**
        1. **Web Search Mode**: Search the internet for real-time information, current events, or general knowledge
        2. **Repository Mode**: Search and use GitHub repositories or local repositories for specialized tasks with hierarchical analysis
        3. **General Code Assistant Mode**: Provide programming assistance without specific repositories
        
        **Auto-Mode Detection:**
        - Detects real-time information needs → Web Search Mode
        - Detects repository paths/URLs (GitHub or local) → Repository Mode
        - Detects general programming questions → General Code Assistant Mode  
        - Default behavior → Repository Mode
        
        **Process:**
        1. Analyze task requirements and detect appropriate mode
        2. Execute using the most suitable approach with advanced repository analysis
        3. Generate comprehensive solutions through hierarchical understanding
        4. Provide execution results and guidance with context optimization
        
        Args:
            task: Detailed task description that user needs to solve
            
        Returns:
            Complete solution report including analysis methods, execution results, and recommendations
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
    
    result = repo_master.run_repository_agent(
        task_description=arguments['task_description'],
        repository=arguments['github_url'],
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
