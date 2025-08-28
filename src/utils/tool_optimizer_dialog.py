# dialogue_optimizer.py

import json
import ast
from src.utils.agent_gpt4 import AzureGPT4Chat  # Assuming the previous code is in azure_gpt4_chat.py

# Import the prompt template
from src.services.prompts.optimized_task_execution import (
    Optimized_Task_Execution_Prompt,
    Optimiz_Dialogue_History_Prompt,
)


def normalize_parsed_data(data):
    """
    Normalize the parsed data to ensure consistency between ast.literal_eval and json.loads results.
    """
    if isinstance(data, list):
        return [normalize_parsed_data(item) for item in data]
    elif isinstance(data, dict):
        return {str(k): normalize_parsed_data(v) for k, v in data.items()}
    elif isinstance(data, (int, float)):
        return str(data)  # Convert numbers to strings to match json.loads behavior
    else:
        return data

def parse_optimized_dialogue(response):
    """
    Parse the optimized dialogue from the GPT-4 response.
    """
    try:
        # Find the start and end of the Python list in the response
        start = response.find("[")
        end = response.rfind("]") + 1
        
        if start == -1 or end == -1:
            raise ValueError("Could not find the optimized dialogue list in the response")
        
        # Extract the dialogue string
        dialogue_str = response[start:end].strip()
        
        # Try to parse as JSON first
        try:
            dialogue_list = json.loads(dialogue_str)
        except json.JSONDecodeError:
            # If JSON parsing fails, use ast.literal_eval and then normalize the result
            dialogue_list = normalize_parsed_data(ast.literal_eval(dialogue_str))
        
        # Ensure the result is a list of dictionaries
        if not isinstance(dialogue_list, list) or not all(isinstance(item, dict) for item in dialogue_list):
            raise ValueError("Parsed result is not a list of dictionaries")
        
        # Validate the structure of each dictionary
        for item in dialogue_list:
            if "role" not in item or "content" not in item:
                raise ValueError("Invalid dictionary structure in the dialogue list")
            
            # Ensure 'role' and 'content' are strings
            item['role'] = str(item['role'])
            item['content'] = str(item['content'])
            
            # Handle 'tool_calls' if present
            if 'tool_calls' in item:
                if not isinstance(item['tool_calls'], list):
                    item['tool_calls'] = [item['tool_calls']]
                item['tool_calls'] = [normalize_parsed_data(tool_call) for tool_call in item['tool_calls']]
        
        return dialogue_list
    except Exception as e:
        print(f"Error parsing optimized dialogue: {str(e)}")
        return None

def get_optimization(original_dialogue, optimiz_type, max_retries=5):
    """
    Optimize the given dialogue using GPT-4 and return the optimized version.
    """
    gpt4_chat = AzureGPT4Chat(system_prompt="You are a helpful AI assistant.")
    
    for attempt in range(max_retries):
        try:
            # Generate the complete prompt
            if optimiz_type == 'dialog_history':
                complete_prompt = Optimiz_Dialogue_History_Prompt.format(dialog_history=original_dialogue)
            elif optimiz_type == 'task_execution':
                complete_prompt = Optimized_Task_Execution_Prompt.format(dialog_history=original_dialogue)
            
            # Get the response from GPT-4
            optimized_dialogue = gpt4_chat.chat(complete_prompt, json_format=False)
            
            # Parse the optimized dialogue
            # optimized_dialogue = parse_optimized_dialogue(response)
            
            if optimized_dialogue is not None:
                return optimized_dialogue
            else:
                print(f"Attempt {attempt + 1} failed. Retrying...")
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
    
    print("Max retries reached. Optimization failed.")
    return None

def optimize_dialogue(original_dialogue, max_retries=5):
    return get_optimization(original_dialogue, 'dialog_history', max_retries)

def optimize_execution(original_dialogue, max_retries=5):
    return get_optimization(original_dialogue, 'task_execution', max_retries)
    

# Example usage
if __name__ == "__main__":
    from configs.oai_config import load_envs_func
    
    load_envs_func()
    
    # Original Task_Dialog string
    Task_Dialog = [
        {"role": "user", "content": "Help me collect NVIDIA 2022 data and calculate maximum drawdown"},
        {"role": "user", "content": "[{\"role\": \"user\", \"content\": \"Help me collect NVIDIA 2022 data and calculate maximum drawdown\"}]"},
        {
            "role": "assistant",
            "content": "Great, we will complete this task in two steps:\n\n1. Collect NVIDIA 2022 data: We will use data search tools to get NVIDIA's 2022 stock data.\n2. Calculate maximum drawdown: We will use code writing tools to calculate maximum drawdown.\n\nFirst, we will collect NVIDIA's 2022 data.",
            "tool_calls": [
                {
                    "id": "call_ntzu1pQA7epFJuUISSSTQAr9",
                    "function": {
                        "arguments": "{\"data_instruction\":\"Collect NVIDIA 2022 stock data\"}",
                        "name": "get_data_by_search"
                    },
                    "type": "function"
                }
            ]
        },
        {"role": "user", "content": "Collect NVIDIA 2022 stock data"},
        {
            "role": "assistant",
            "content": "To collect NVIDIA 2022 stock data, I will take the following steps:\n\n1. Get NVIDIA's full-year 2022 stock historical data.\n2. Save the data to the specified path.\n\nFirst, I will call the stock data tool to collect 2022 data.\n\nI will start executing the first step.",
            "tool_calls": [
                {
                    "id": "call_4LTcHnC4eZw32peAdHwErin0",
                    "function": {
                        "arguments": "{\"ticker_symbol\":\"NVDA\",\"start_date\":\"2022-01-01\",\"end_date\":\"2022-12-31\",\"period\":\"1d\",\"save_path\":\"coding/bp5xt9z8/NVDA_2022_stock_data.csv\"}",
                        "name": "get_stock_data"
                    },
                    "type": "function"
                }
            ]
        },
        {"role": "user", "content": "The complete table is stored in:\n\n[coding/bp5xt9z8/get_stock_data_ticker_symbolnvda_start_d.csv]\n\nThe following is a display of some of its contents:\n\n| Date | Open | High | Low | Close | Volume | Dividends | Stock Splits | RSI |\n|:--------------------------|--------:|--------:|--------:|--------:|----------:|------------:|---------------:|------:|\n| 2022-01-03 00:00:00-05:00 | 29.7701 | 30.6647 | 29.7401 | 30.0756 | 391547000 | 0 | 0 | nan |\n| 2022-01-04 00:00:00-05:00 | 30.2314 | 30.4221 | 28.3063 | 29.2459 | 527154000 | 0 | 0 | nan |\n| 2022-01-05 00:00:00-05:00 | 28.9054 | 29.3717 | 27.4915 | 27.5624 | 498064000 | 0 | 0 | nan |\n| 2022-01-06 00:00:00-05:00 | 27.5984 | 28.3952 | 27.0242 | 28.1356 | 454186000 | 0 | 0 | nan |\n| 2022-01-07 00:00:00-05:00 | 28.0986 | 28.3792 | 27.0162 | 27.206 | 409939000 | 0 | 0 | nan |"},
        {"role": "assistant", "content": "NVIDIA 2022 stock data has been successfully obtained and saved. File path is:\n\n- File path: coding/bp5xt9z8/get_stock_data_ticker_symbolnvda_start_d.csv\n\nThis file contains NVIDIA's daily stock data for the entire year 2022. Task completed.\n\nTERMINATE"},
        {"role": "user", "content": "The NVIDIA (NVDA) stock data for the year 2022 has been successfully collected and saved to the file located at coding/bp5xt9z8/get_stock_data_ticker_symbolnvda_start_d.csv, which includes daily stock information for the entire year."},
        {
            "role": "assistant",
            "content": "We have successfully collected NVIDIA's 2022 stock data, and the data file is located at coding/bp5xt9z8/get_stock_data_ticker_symbolnvda_start_d.csv.\n\nNext, we will write code to calculate the maximum drawdown.",
            "tool_calls": [
                {
                    "id": "call_5mc18ebnOnJC7676fxxg0c39",
                    "function": {
                        "arguments": "{\"task_description\":\"Calculate NVIDIA's maximum drawdown for 2022.\",\"read_local_file_path\":{\"stock_data\":\"coding/bp5xt9z8/get_stock_data_ticker_symbolnvda_start_d.csv\"},\"required_libraries\":[\"pandas\",\"numpy\"]}",
                        "name": "create_code_tool"
                    },
                    "type": "function"
                }
            ]
        },
        {"role": "user", "content": "### Task Description:\n- Calculate NVIDIA's maximum drawdown for 2022.\n\n#### Required Libraries:\n- pandas\n- numpy\n\n#### Local Files:\n- stock_data: get_stock_data_ticker_symbolnvda_start_d.csv\n\n> Note: When reading local files, please use only the filename for reading, not the full path.\n> (For example: coding/4roumnst/$filename.csv -> $filename.csv)"},
        {"role": "assistant", "content": "To calculate the maximum drawdown for Nvidia's stock in 2022, we'll follow these steps:\n\n1. Read the stock data from the CSV file.\n2. Filter the data for the year 2022.\n3. Calculate the daily drawdown.\n4. Find the maximum drawdown.\n\nLet's proceed with the code:\n\npython\n# filename: calculate_max_drawdown.py\n\nimport pandas as pd\nimport numpy as np\n\n# Step 1: Read the stock data from the CSV file\nstock_data = pd.read_csv('get_stock_data_ticker_symbolnvda_start_d.csv')\n\n# Step 2: Convert the 'Date' column to datetime format and filter for the year 2022\nstock_data['Date'] = pd.to_datetime(stock_data['Date'])\nstock_data_2022 = stock_data[stock_data['Date'].dt.year == 2022]\n\n# Step 3: Calculate the daily drawdown\nstock_data_2022['Cumulative Max'] = stock_data_2022['Close'].cummax()\nstock_data_2022['Drawdown'] = stock_data_2022['Close'] / stock_data_2022['Cumulative Max'] - 1\n\n# Step 4: Find the maximum drawdown\nmax_drawdown = stock_data_2022['Drawdown'].min()\n\nprint(f\"The maximum drawdown for Nvidia in 2022 was: {max_drawdown * 100:.2f}%\")\n\n\nPlease save the above code in a file named calculate_max_drawdown.py and execute it. The output will display the maximum drawdown for Nvidia in 2022."},
        {"role": "user", "content": "exitcode: 1 (execution failed)\nCode output: \ncalculate_max_drawdown.py:10: FutureWarning: In a future version of pandas, parsing datetimes with mixed time zones will raise an error unless utc=True. Please specify utc=True to opt in to the new behaviour and silence this warning. To create a Series with mixed offsets and object dtype, please use apply and datetime.datetime.strptime\n stock_data['Date'] = pd.to_datetime(stock_data['Date'])\nTraceback (most recent call last):\n File \"calculate_max_drawdown.py\", line 11, in <module>\n stock_data_2022 = stock_data[stock_data['Date'].dt.year == 2022]\n ^^^^^^^^^^^^^^^^^^^^^\n File \"/home/dfoadmin/anaconda3/envs/whc/lib/python3.11/site-packages/pandas/core/generic.py\", line 6296, in getattr\n return object.getattribute(self, name)\n ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n File \"/home/dfoadmin/anaconda3/envs/whc/lib/python3.11/site-packages/pandas/core/accessor.py\", line 224, in get\n accessor_obj = self._accessor(obj)\n ^^^^^^^^^^^^^^^^^^^\n File \"/home/dfoadmin/anaconda3/envs/whc/lib/python3.11/site-packages/pandas/core/indexes/accessors.py\", line 643, in new\n raise AttributeError(\"Can only use .dt accessor with datetimelike values\")\nAttributeError: Can only use .dt accessor with datetimelike values. Did you mean: 'at'?\n"},
        {"role": "assistant", "content": "It seems there was an issue with parsing the 'Date' column due to mixed time zones. We need to specify utc=True when converting the 'Date' column to datetime format. Let's fix that and try again.\n\nHere's the revised code:\n\npython\n# filename: calculate_max_drawdown.py\n\nimport pandas as pd\nimport numpy as np\n\n# Step 1: Read the stock data from the CSV file\nstock_data = pd.read_csv('get_stock_data_ticker_symbolnvda_start_d.csv')\n\n# Step 2: Convert the 'Date' column to datetime format with utc=True\nstock_data['Date'] = pd.to_datetime(stock_data['Date'], utc=True)\nstock_data['Date'] = stock_data['Date'].dt.tz_localize(None) # Remove timezone information\n\n# Step 3: Filter for the year 2022\nstock_data_2022 = stock_data[stock_data['Date'].dt.year == 2022]\n\n# Step 4: Calculate the daily drawdown\nstock_data_2022['Cumulative Max'] = stock_data_2022['Close'].cummax()\nstock_data_2022['Drawdown'] = stock_data_2022['Close'] / stock_data_2022['Cumulative Max'] - 1\n\n# Step 5: Find the maximum drawdown\nmax_drawdown = stock_data_2022['Drawdown'].min()\n\nprint(f\"The maximum drawdown for Nvidia in 2022 was: {max_drawdown * 100:.2f}%\")\n\n\nPlease save this revised code in the same file calculate_max_drawdown.py and execute it. The output will display the maximum drawdown for Nvidia in 2022."},
        {"role": "user", "content": "exitcode: 0 (execution succeeded)\nCode output: \nThe maximum drawdown for Nvidia in 2022 was: -62.70%\n"},
        {"role": "assistant", "content": "The calculation has been successfully completed. The maximum drawdown for Nvidia in 2022 was -62.70%.\n\nTERMINATE"},
        {"role": "user", "content": "The maximum drawdown for Nvidia in 2022 was -62.70%, calculated by reading stock data from a CSV file, filtering for the year 2022, calculating daily drawdowns, and identifying the maximum drawdown."},
        {"role": "assistant", "content": "NVIDIA's maximum drawdown in 2022 was -62.70%. Task completed.\n\nTERMINATE"}
    ]
    # import pdb;pdb.set_trace()
    
    from src.services.prompts.optimized_task_execution import optimized_task_execution_test
    # optimized_dialogue = optimize_dialogue(Task_Dialog)
    # optimized_dialogue = optimize_execution(optimized_task_execution_test())
    optimized_dialogue = optimize_execution(Task_Dialog)
    
    if optimized_dialogue:
        print("Optimized Dialogue:", optimized_dialogue)
        # print(json.dumps(optimized_dialogue, indent=2, ensure_ascii=False))
        content = ""
        for message in optimized_dialogue:
            tmp_content = json.dumps(message['content'], ensure_ascii=False)
            if 'tool_calls' in message:
                tmp_content += f"\nfunction call: {json.dumps([message['tool_calls']], ensure_ascii=False)}"
            content += f"{message['role']}: \n{tmp_content}\n\n"
        print(content)
    else:
        print("Failed to optimize the dialogue.")