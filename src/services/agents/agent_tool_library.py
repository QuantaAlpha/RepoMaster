import json
import requests
from typing import Annotated, Optional, Union, Callable
from src.utils.agent_gpt4 import AzureGPT4Chat
import tiktoken

class AgentToolLibrary:
    def __init__(
        self, 
        llm_config=None, 
        code_execution_config=None, 
        tool_list={
            "agent_coder": False,
            "deep_search": False,
        },
        chat_history_provider: Optional[Callable[[], dict]] = None
    ):
        """
        Initialize AgentToolLibrary
        
        Args:
            llm_config: LLM configuration
            code_execution_config: Code execution configuration
            tool_list: Tool list configuration
            chat_history_provider: Callback function for dynamically getting chat_history
        """
        self.chat_history = {}
        self.chat_history_provider = chat_history_provider
        self.llm_config = llm_config
        self.code_execution_config = code_execution_config
        self.tool_list = tool_list
        
        if self.tool_list["agent_coder"]:
            from src.services.agents.agent_general_coder import GeneralCoder
            self.general_coder_agent = GeneralCoder(
                self.llm_config, self.code_execution_config,
            )
        
        if self.tool_list["deep_search"]:
            from src.utils.web_search_agent.tool_web_engine import WebBrowser
            self.web_browser = WebBrowser()
        
        # Lazy initialization of deep_search_agent
        self.deep_search_agent = None

    def get_tool_list(self):
        tools = []
        if self.tool_list["agent_coder"]:
            tools.append(self.create_code_tool)
        if self.tool_list["deep_search"]:
            tools.append(self.deep_search_tool)
        return tools
    
    def update_chat_history(self, chat_history):
        """Update static chat_history"""
        self.chat_history = chat_history
    
    def get_current_chat_history(self) -> dict:
        """
        Get current chat_history, prioritizing dynamic data provided by provider
        
        Returns:
            dict: Merged chat_history
        """
        # Start with static history
        result = self.chat_history.copy()
        
        # If callback function exists, get dynamic data and merge
        if self.chat_history_provider:
            try:
                dynamic_history = self.chat_history_provider()
                if dynamic_history:
                    if not isinstance(dynamic_history, dict):
                        dynamic_history = {"chat_history": dynamic_history}
                    self.chat_history = dynamic_history
                    return dynamic_history
            except Exception as e:
                print(f"Error getting dynamic chat history: {e}")
        
        return result

    async def searching(self, query: Annotated[str, "The query content to search for"]) -> str:
        """
        Use search engine to query information and return results
        """
        search_result = await self.web_browser.searching(query)
        return search_result

    def get_browsing_reasoning_system_prompt(self):
        return """
You are a professional deep research analysis assistant, specialized in intelligent analysis and reasoning of web browsing results.

# Your Core Tasks
1. **Relevance Assessment**: First determine if the webpage content is relevant to the user's browsing purpose and contains useful information
2. **Deep Analysis**: Conduct in-depth analysis and reasoning of relevant content
3. **Context Association**: Combine conversation history to understand user's overall needs and research direction
4. **Information Extraction**: Extract key information most relevant to user's purpose from webpage content
5. **Logic Reasoning**: Perform logical analysis of obtained information to draw valuable conclusions
6. **Structured Output**: Present analysis results in a clear, structured manner

# Analysis Methods
## Step 1: Relevance Judgment
- Quickly scan browsing results to determine if content is related to browsing_target
- Assess if it contains useful information that can answer user questions or meet user needs
- If irrelevant or useless, directly return conclusion of "no relevant useful information"

## Step 2: Information Filtering (only execute when relevant)
- Identify core information directly related to browsing_target
- Filter out irrelevant ads, navigation, copyright and other content
- Focus on key elements such as data, facts, opinions, trends

## Step 3: Context Integration
- Analyze correlation between current browsing results and conversation history
- Identify user's deep needs and research context
- Supplement or verify previously obtained information

## Step 4: Reasoning Analysis
- Analyze causal relationships of obtained information
- Identify trends and patterns behind data
- Provide evidence-based inferences and insights

## Input contains three structured pieces of information:
<browsing_target> —— User's research/search objective  
<browsing_result> —— Original webpage content  
<chat_history> —— Historical conversation

## 【Task】
1. **Primary Task**: Quickly determine if <browsing_result> is relevant to <browsing_target> and contains useful information
2. If irrelevant or no useful information, directly return concise "no relevant information" conclusion
3. If relevant and useful, perform deep information extraction and reasoning on <browsing_result> with full understanding of <browsing_target>
4. Combine <chat_history> to complete context, keeping answers consistent with user's overall demands
5. Output refined, structured reasoning analysis and conclusions that directly satisfy <browsing_target>

## 【Workflow】(No need to expose thinking process in final answer)
Step-1 Relevance Judgment: Quickly assess if browsing results are relevant to user goals and contain useful information
Step-2 Information Filtering: (Only when relevant) Remove ads/navigation noise, keep only facts, data, arguments, conclusions
Step-3 Relevance Assessment: (Only when relevant) Judge correlation between filtered information and <browsing_target>, keep only highly relevant items
Step-4 Evidence-Conclusion Chain: (Only when relevant) Establish "evidence→reasoning→conclusion" chain for each highly relevant piece of information
Step-5 Inductive Reasoning: (Only when relevant) Summarize trends, causal relationships or insights based on evidence chains, cross-verify with <chat_history> if necessary
Step-6 Generate Answer: Write final reply according to the following【Output Format】

## 【Output Format】
### Case 1: Content irrelevant or no useful information
```
### Relevance Assessment
The webpage content is not relevant to the query target, and no useful information for answering user questions was found.
```

### Case 2: Content relevant with useful information
Use Markdown with the following fixed titles:
```
### Key Information  
- (1) …  
- (2) …  

### Reasoning and Insights  
- …  
```

## Output Requirements
- **Efficiency Priority**: Quickly judge relevance, avoid detailed analysis of irrelevant content
- **Concise and Clear**: Avoid repeating original content, focus on analysis results
- **Clear Logic**: Organize information by importance and logical order
- **Conclusion-Oriented**: Clearly answer user's browsing purpose, provide actionable insights

Please analyze the provided webpage browsing results based on the above principles for relevance judgment and analysis.
"""

    async def browsing(self, query: Annotated[str, "The purpose of browsing this webpage, what information to obtain, what problem to solve"], url: Annotated[str, "The URL of the webpage to browse"]) -> str:
        """
        Browse detailed content of a specific URL and extract relevant information
        """
        browsing_result = await self.web_browser.browsing_url(url)
        token_count = len(tiktoken.encoding_for_model("gpt-4o").encode(browsing_result))
        if token_count < 2000:
            return browsing_result
        
        prompt = (
            f"<browsing_target>\n{query}\n</browsing_target>\n"
            f"<browsing_result>\n{browsing_result}\n</browsing_result>\n"
        )

        try:
            response = AzureGPT4Chat().chat_with_message(
                [
                    {"role": "system", "content": self.get_browsing_reasoning_system_prompt()},
                    {"role": "user", "content": prompt}
                ]
            )
        except Exception as e:
            import traceback
            print(f"Error: {e}, {traceback.format_exc()}")
            import pdb; pdb.set_trace()
            return f"Error: {e}, {traceback.format_exc()}"
        print(f"Browsing Result: {response}")
        return f"\n\n<Task>\n{query}\n\n<Browsing URL>\n{url}\n\n<Browsing Result>\n\n{response}\n\nPlease check the information, if not enough, please search more information."

    async def create_code_tool(
        self,
        task_description: Annotated[str, "Detailed description of the task, including required operations and expected results(Not code)."],
        context: Annotated[Optional[str|dict], "Additional background information or context for the task(include the user's original question, and necessary information about the task, necessary data path, etc.)."] = None,
        # read_local_file_path: Annotated[Optional[Dict[str, str]], "Dictionory of Local read files path and their descriptions about the file."],
        required_libraries: Annotated[Optional[list], "List of Python libraries that might be needed for the task."] = None,
    ) -> Union[str, dict]:
        """
        Generate, execute code and return the execution results.

        This function uses an AI coding assistant to generate code, then executes
        the code and returns the execution results. The entire process includes
        code generation, error handling, code execution, and result return.

        Returns:
        Union[str, dict]: The result of code execution. It can be a string (for simple output)
                          or a dictionary (for more complex results, such as multiple outputs or error information).
        """
        try:
            current_chat_history = self.get_current_chat_history()
            if self.chat_history:
                task_description = task_description + "\n\n" + "\n\n".join([f"{k}: {v}" for k, v in self.chat_history.items()])
            
            if self.tool_list["agent_coder"]:
                return await self.general_coder_agent.create_code_tool(
                    task_description, context, required_libraries
                )
        except Exception as e:
            import traceback
            return f"Error: {e}, {traceback.format_exc()}"

    async def deep_search_tool(
        self,
        query: Annotated[str, "The search query or question to research in depth"],
    ) -> str:
        """
        Perform deep search using web search and browsing capabilities.
        
        This function uses AI agents to search the web, browse specific pages,
        and provide comprehensive answers to complex questions.
        
        Args:
            query: The question or topic to research
            
        Returns:
            str: Comprehensive answer based on web research
        """
        # Lazy import to avoid circular import
        if self.deep_search_agent is None:
            from src.services.agents.deep_search_agent import AutogenDeepSearchAgent
            self.deep_search_agent = AutogenDeepSearchAgent(
                llm_config=self.llm_config,
                code_execution_config=self.code_execution_config
            )
        
        return await self.deep_search_agent.a_web_agent_answer(query)

    async def run_task(self):
        pass
    
    