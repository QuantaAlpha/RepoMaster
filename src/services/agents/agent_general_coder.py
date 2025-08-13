from dotenv import load_dotenv
import autogen
import os
import json
from autogen.cache import Cache
from datetime import datetime
from src.utils.agent_gpt4 import AzureGPT4Chat

from src.utils.tools_util import remove_work_dir_prefix
from src.utils.toolkits import register_toolkits
from autogen.agentchat.chat import ChatResult

from src.services.autogen_upgrade.base_agent import ExtendedAssistantAgent, ExtendedUserProxyAgent
from src.services.prompts.general_coder_prompt import Coder_Prompt as Coder_Prompt
from textwrap import dedent
from typing import Annotated, Optional, Union, Dict, Any


class GeneralCoder():
    def __init__(
            self,
            llm_config: dict[str, any],
            code_execution_config: dict[str, any],
            connection_id: Optional[str] = None,
            send_message_function: Optional[callable] = None,
            agent_history: list = None
    ) -> None:
        super().__init__(
            connection_id=connection_id,
            send_message_function=send_message_function,
            agent_history=agent_history
        )
        self.llm_config = llm_config
        self.code_execution_config = code_execution_config
        self.is_termination_msg = lambda x: x.get("content", "").strip().endswith("TERMINATE") or "TERMINATE" in x.get("content", "")[-10:]

        self.initiate_agents()
        # self.register_toolkits()
        
        self.chat_history = None
        
        if self.code_execution_config.get("work_dir"):
            self.work_dir = os.path.normpath(self.code_execution_config["work_dir"])
        else:
            try:
                self.work_dir = os.path.normpath(self.code_execution_config['executor'].work_dir)
            except Exception as e:
                import pdb; pdb.set_trace()

    def initiate_agents(self, **kwargs):    
        self.general_coder = ExtendedAssistantAgent(
            name="General_Coder",
            system_message=Coder_Prompt.format(current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), additional_info=""),
            llm_config=self.llm_config,
        )

        self.coder_excute = ExtendedUserProxyAgent(
            name="Coder_Excute",
            llm_config=self.llm_config,
            is_termination_msg=self.is_termination_msg,
            human_input_mode="NEVER",
            # max_consecutive_auto_reply=10,
            code_execution_config=self.code_execution_config,
        )

    def register_toolkits(self):
        """
        Register the toolkits required for the agents to function properly.
        """
        register_toolkits(
            [
                coding.CodingUtils.see_file,
                coding.CodingUtils.list_dir,
            ],
            self.coder_excute,
            self.general_coder,
        )
    
    def update_system_message(self, ):
        description_file = os.path.join(self.work_dir, "Task_description.json")
        
        additional_info = dedent('''> **Note:** 
        >> When reading local files, please use only the filename for reading, not the full path.(For example: `coding/4roumnst/$filename.csv` -> `$filename.csv`)''')
        additional_info += f"\n>> When you need to save downloaded data, please follow these guidelines:\n>> 1. Only save data after all code has executed successfully\n>> 2. Always add a description to the file by calling `insert_file_description_to_file(filename, description)`\n>> 3. If any part of the code execution fails, do not save the data\n>> 4. Always save both your data files AND your code file using `insert_file_description_to_file`\n>> Example: ```python\ntry:\n    # Your data processing code here\n    # Only save after successful execution\n    from src.services.functional.coding import CodingUtils as cu\n    \n    # Save the data file\n    cu.insert_file_description_to_file('stock_data.csv', 'This is the stock data of Nvidia')\n    \n    # Also save the code file itself\n    cu.insert_file_description_to_file('nvidia_analysis.py', 'Python script to analyze Nvidia stock data')\nexcept Exception as e:\n    print(f'Error occurred: {{e}}')\n    # Do not save data when errors occur\n```\n"
        additional_info += "\n>> **CRITICAL INSTRUCTION:** For complex problems requiring multiple steps, DO NOT write all code in a single file. Instead:\n>> 1. Break down the problem into logical components (data acquisition, processing, analysis, visualization)\n>> 2. Create SEPARATE FILES for each component (e.g., `data_fetcher.py`, `data_processor.py`, `visualizer.py`)\n>> 3. Execute these files in sequence or in parallel as appropriate\n>> 4. This modular approach makes debugging easier, isolates errors, and increases overall success\n>> \n>> Example workflow:\n>> ```\n>> # Step 1: Create data_fetcher.py to download stock data\n>> # Step 2: Execute data_fetcher.py to verify data acquisition works\n>> # Step 3: Create data_analyzer.py to process the downloaded data\n>> # Step 4: Execute data_analyzer.py to verify analysis works\n>> # Step 5: Create visualizer.py to create charts from the analysis\n>> ```"
        additional_info += "\n>> **CODE QUALITY REQUIREMENTS:**\n>> 1. Avoid repetitive and redundant code\n>> 2. Keep your analysis separate from execution code\n>> 3. Only output executable code in code blocks\n>> 4. First explain your approach, then provide clean, concise code that's ready to execute\n>> 5. Do not mix explanations within code blocks unless they are actual comments"
        
        if os.path.exists(description_file):
            with open(description_file, 'r') as f:
                data = json.load(f)
                additional_info += f"\n>> You should consider the following local saved files if is your task related: {json.dumps(data, ensure_ascii=False)}\n"
        
        self.general_coder.update_system_message(Coder_Prompt.format(current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), additional_info=additional_info))

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
        message = f"#### Task Description:\n- {task_description}\n"
        
        if self.chat_history:
            message += f"#### Chat History:\n- {self.chat_history}\n"

        if context:
            message += f"#### Context:\n- {context}\n"

        message = message.replace(self.work_dir+"/", "")
        
        self.update_system_message()
        
        chat_result: ChatResult = await self.coder_excute.a_initiate_chat(
            self.general_coder,
            message=message,
            max_turns=50,
            summary_method="reflection_with_llm",
            summary_args= {
                'summary_prompt': "Summarize takeaway from the conversation and generate a complete and detailed report at last. Do not add any introductory phrases. The final answer should correspond to the user's question and request."
            }
        )
        
        # Extract and summarize files created during the conversation using LLM
        file_summary = await self.summarize_created_files_with_llm(chat_result)
        
        # Return both the chat result summary and file summary
        if file_summary:
            return {
                "execution_result": chat_result.summary,
                "file_summary": file_summary
            }
        return chat_result.summary
    
    async def summarize_created_files_with_llm(self, chat_result: ChatResult) -> dict:
        """
        Use LLM to analyze the chat history and identify files created during the conversation.
        
        Args:
            chat_result: The ChatResult object from autogen
            
        Returns:
            dict: A dictionary containing information about created files
        """
        # Get the chat history from the chat result, but filter out failed execution sessions
        filtered_chat_history = self._filter_failed_execution_sessions(chat_result.chat_history)
        
        # Format the filtered chat history
        chat_history = []
        for message in filtered_chat_history:
            if message.get("content"):
                role = message.get("role", "")
                content = message.get("content", "")
                chat_history.append(f"{role}: {content}")
        
        # Combine the chat history into a single string
        chat_history_text = "\n\n".join(chat_history)
        
        # Create a prompt for the LLM to analyze the chat history
        prompt = f"""
        Please analyze the following conversation between a user and an AI assistant. 
        The conversation involves coding tasks and file creation.
        
        Your task is to identify all files that were created during this conversation, including:
        1. Code files (like .py, .js, .html, .css, .R files)
        2. Data files (like .csv, .json, .xlsx, .txt files)
        3. Image files (like .png, .jpg, .pdf files)
        
        For each file, provide:
        - The filename
        - A brief description of what the file contains or its purpose
        - The type of file (code, data, or image)
        
        Focus on the final versions of files that were successfully created. Ignore temporary files or files that were mentioned but not actually created.
        
        Look for patterns like:
        - File saving operations (to_csv, to_json, savefig, etc.)
        - File writing operations (with open(..., 'w'), write_text, etc.)
        - Explicit file description calls (insert_file_description_to_file)
        - Successful execution results showing file creation
        
        Return your analysis as a JSON object with this structure:
        {{
            "code_files": [
                {{"filename": "example.py", "description": "Script that analyzes stock data"}}
            ],
            "data_files": [
                {{"filename": "data.csv", "description": "Stock price data for NVIDIA"}}
            ],
            "image_files": [
                {{"filename": "plot.png", "description": "Visualization of stock performance"}}
            ]
        }}
        
        Only include files that were actually created or saved during the conversation. 
        Only output the json format data, do not include any other text.

        Here is the conversation:
        
        {chat_history_text}
        """
        
        file_summary = AzureGPT4Chat().chat(prompt, json_format=True)
        print("file_summary", file_summary)
        
        output = {}
        for file_type in ["code_files", "data_files", "image_files"]:
            if file_summary and file_summary.get(file_type):
                output[file_type] = file_summary[file_type]
                
        return output
            

    
    def _filter_failed_execution_sessions(self, chat_history: list) -> list:
        """
        Filter out entire failed execution sessions from the chat history.
        This includes the code message before the execution and the execution result.
        
        Args:
            chat_history: The original chat history
            
        Returns:
            list: Filtered chat history without failed execution sessions
        """
        filtered_history = []
        i = 0
        
        while i < len(chat_history):
            # Check if this is an execution result message with failure
            if (i < len(chat_history) and 
                "exitcode: 1 (execution failed)" in chat_history[i].get("content", "")):
                
                # Find the preceding code message (usually from the assistant)
                preceding_code_index = i - 1
                while preceding_code_index >= 0:
                    if chat_history[preceding_code_index].get("role") == "assistant":
                        break
                    preceding_code_index -= 1
                
                # Skip both the code message and the execution result
                if preceding_code_index >= 0:
                    i = i + 1  # Skip the execution result
                    continue
                else:
                    # If we couldn't find a preceding code message, just skip this message
                    i += 1
                    continue
            
            # Add this message to the filtered history
            filtered_history.append(chat_history[i])
            i += 1
        
        return filtered_history


def main():
    import configs.config
    from dotenv import load_dotenv
    import asyncio  # Add this import
    
    llm_config = configs.config.get_llm_config()
    load_dotenv("../../configs/.env")
    
    code_execution_config={"work_dir": 'coding/test', "use_docker": False}
    
    Coder = GeneralCoder(
        llm_config=llm_config,
        code_execution_config=code_execution_config,
    )
    # args = {"task_description":"Calculate the maximum drawdown of AMD stock data in 2022 and output stock trend chart.","read_local_file_path":{"stock_data":"coding/4roumnst/get_stock_data_ticker_symbolamd_start_da.csv"},"required_libraries":["pandas","matplotlib","numpy"]}
    args = {
        # "task_description": "Use akshare to get Moutai company's stock data from last year and save it locally.",
        # "read_local_file_path": None,
        # "required_libraries": ["akshare", "pandas"],
        # "context": "Get Moutai company's stock data from last year and save as CSV file.",
        "task_description": "Calculate NVIDIA's maximum drawdown in 2024",
        # "context": "Get Guizhou Moutai (stock code: 600519) stock data from the past year and save as CSV file.",
        # "task_description": "import akshare as ak\nimport pandas as pd\nfrom datetime import datetime, timedelta\n\n# Get current date and date from one year ago\nend_date = datetime.now()\nstart_date = end_date - timedelta(days=365)\n\n# Format dates\nstart_date_str = start_date.strftime('%Y-%m-%d')\nend_date_str = end_date.strftime('%Y-%m-%d')\n\n# Get Guizhou Moutai stock data\nstock_data = ak.stock_zh_a_hist(symbol='600519', period='daily', start_date=start_date_str, end_date=end_date_str)\n\n# Save data to CSV file\nstock_data.to_csv('maotai_stock_data.csv', index=False)\n\nprint('Data has been saved to maotai_stock_data.csv')"
    }
    # Create an async function to run the coroutine
    async def run_task():
        result = await Coder.create_code_tool(**args)
        print(result)
    
    # Run the async function with asyncio
    result = asyncio.run(run_task())
    print(result)

if __name__ == "__main__":
    main()
