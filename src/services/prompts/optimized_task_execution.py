Optimized_Task_Execution_Prompt = """
# Task Execution Path Optimization Prompt (Including Code Correction and Task Summary)

Your task is to analyze the given dialogue and execution trace, and generate an optimized task execution path, paying special attention to code generation and correction processes, and finally providing a comprehensive task summary. Please follow these steps:

1. Task Objective Extraction
   - Carefully read the entire dialogue, identify and clearly state the main task objectives.

2. Key Step Identification
   - List all critical steps required to complete the task.
   - For each step, briefly explain its purpose and importance.

3. Error and Redundancy Elimination
   - Identify any errors in the execution process, including code errors, and provide corrections.
   - Remove all unnecessary interactions and redundant steps.

4. Code Correction Tracking
   - Pay special attention to the code generation and repair process.
   - Only retain the final corrected version of the code.

5. Optimal Path Generation
   - Based on the above analysis, create a concise, step-by-step optimal execution path.
   - Maintain the dialogue format, but only include necessary interactions.
   - For steps involving code, only include the final correct code version.

6. Role Definition Preservation
   - Identify and preserve all distinct role definitions present in the original dialog_history.
   - Maintain the original role types such as "code agent", "researcher", "executor", etc.
   - Ensure each message in the optimized path retains the correct role attribution from the original dialogue.
   - If a role has specific characteristics or domain expertise, preserve these attributes in the optimized content.

7. Task Summary
   - At the end of the optimized path, provide a concise but comprehensive task summary.
   - Include task objectives, main steps, key results, and any important findings or conclusions.

8. Output Format
   Please output the optimized execution path in the following format:

   ```
   [
     {{"role": "user", "content": "Original user query"}},
     {{"role": original role type from the dialogue (e.g., "assistant", "code_agent", "researcher", etc.), "content": "Task objective overview and execution plan"}},
     {{"role": original role type from the dialogue (e.g., "assistant", "code_agent", "researcher", etc.), "content": "Step 1 execution", "tool_calls": [{{"relevant tool call information"}}]}},
     {{"role": "user", "content": "Step 1 result"}},
     {{"role": "assistant" or original specialized role, "content": "Step 2 execution (if includes code, only show the final correct version)", "tool_calls": [{{"relevant tool call information"}}]}},
     {{"role": "user", "content": "Step 2 result"}},
     ...,
     {{"role": "assistant" or original specialized role, "content": "Task completion summary, including main steps, key results, and important findings"}}
   ]
   ```

Please ensure that the optimized path is concise and clear, while retaining all necessary information and steps to accurately complete the original task. Emphasize that for steps involving code generation and repair, the final output should only include the final correct code version after all necessary corrections. Finally, provide a comprehensive task summary that outlines the entire process and highlights key outcomes.
Do not add or supplement any information not present in the original text.

Historical Execution:
{dialog_history}

Based on the above historical execution path, please generate an optimized task execution path following the guidelines provided.
"""



Optimiz_Dialogue_History_Prompt = '''
# Enhanced Dialogue History Optimization Prompt (Including Tool Calls)

Your task is to analyze the given dialogue history and generate a concise version for subsequent user interactions. Please follow these steps and principles:

1. Core Topic Identification
   - Carefully read the entire dialogue, identify and clearly state the core topics and key discussion points.

2. Key Information Extraction
   - Identify information crucial to understanding the dialogue context and topics.
   - Retain key interactions that reflect the dialogue's progress and turning points.

3. Removal of Redundant and Unnecessary Information
   - Delete repetitive information and viewpoints.
   - Remove marginal discussions that are irrelevant or have little impact on the core topic.
   - Eliminate lengthy explanations, retaining concise expressions.

4. Context Preservation
   - Ensure the streamlined dialogue maintains logical coherence.
   - Retain key background information for understanding subsequent interactions.

5. User Intent Preservation
   - Ensure the user's main questions and intentions are clearly reflected in the streamlined version.

6. Information Density Optimization
   - Increase the information density of each interaction while ensuring information integrity.

7. Error Information and Fix Process Handling
   - Remove detailed error messages from code execution failures.
   - Retain the final fixed code version, briefly explaining the key points of the fix.

8. Execution Process Optimization
   - Merge or delete intermediate confirmations and descriptions in the data collection process.
   - Retain key execution steps and results, removing redundant intermediate process descriptions.

9. Code Version Management
   - Keep only the final fixed code version, removing all intermediate error versions.
   - If necessary, briefly explain the key points of code evolution.

10. Data Display Simplification
    - Delete or significantly simplify detailed displays of data file contents (e.g., first few rows of CSV files).
    - Retain only data summaries or key statistics crucial for understanding the results.

11. Role Definition Preservation
    - Identify all distinct role types in the original dialogue (e.g., "code agent", "researcher", "executor").
    - Preserve these specialized roles in the optimized output exactly as they appear in the original dialogue.
    - Maintain the relationship between role types and their specific responsibilities or expertise.
    - When a specialized role performs an action, ensure this attribution is maintained in the optimized dialogue.

12. Tool Call Preservation
    - Retain the "tool_calls" key and its contents from the original dialogue (if present).
    - Ensure the preserved tool call information remains consistent with the optimized dialogue content.

13. Output Format
    Please output the optimized dialogue history in the following Python string format:

    ```
    [
      {{"role": "user", "content": "Streamlined user query/statement"}},
      {{"role": original role type from the dialogue (e.g., "assistant", "code_agent", "researcher", etc.), "content": "Streamlined assistant reply, including key code or results", "tool_calls": [{{"relevant tool call information, if present in the original dialogue"}}]}},
      {{"role": "user", "content": "Streamlined user follow-up question/response"}},
      {{"role": original role type from the dialogue, "content": "Streamlined assistant answer/reply, including final fixed code or key results", "tool_calls": [{{"relevant tool call information, if present in the original dialogue"}}]}},
      ...
    ]
   ```

14. Summary
    - At the end of the optimized dialogue, add a brief statement summarizing the main content of the original dialogue, key results, and important information retained during the streamlining process.

Do not add or supplement any information not present in the original text.

Historical Dialogue:
{dialog_history}    

Please ensure that the optimized dialogue history is concise and clear while retaining all necessary information to provide sufficient context for subsequent interactions. The focus is on distilling the most valuable information, maintaining the coherence and completeness of the dialogue, while significantly reducing redundant content and unnecessary technical details.
'''


def optimized_task_execution_test():
   # Example usage:
   historical_path_example = '''
   [
      {{"role": "user", "content": "Help me collect NVIDIA's 2022 data and calculate the maximum drawdown"}},
      {{"role": "researcher", "content": "Certainly! I'll help you collect NVIDIA's stock data for 2022 and calculate the maximum drawdown. Let's break this down into steps:

   1. Collect NVIDIA's stock data for 2022
   2. Calculate the maximum drawdown

   Let's start with collecting the data."}},
      {{"role": "data_agent", "content": "First, let's use a data retrieval tool to get NVIDIA's stock data for 2022.", "tool_calls": [{{"id": "call_123", "function": {{"name": "get_stock_data", "arguments": "{{\\"ticker_symbol\\":\\"NVDA\\",\\"start_date\\":\\"2022-01-01\\",\\"end_date\\":\\"2022-12-31\\",\\"period\\":\\"1d\\"}}"}}}}]}},
      {{"role": "user", "content": "Stock data for NVIDIA (NVDA) in 2022 has been successfully retrieved and saved to 'nvda_2022_data.csv'."}},
      {{"role": "code_agent", "content": "Great! Now that we have the data, let's calculate the maximum drawdown. I'll write a Python script to do this calculation.", "tool_calls": [{{"id": "call_456", "function": {{"name": "write_python_script", "arguments": "{{\\"script_content\\":\\"import pandas as pd\\n\\n# Read the CSV file\\ndf = pd.read_csv('nvda_2022_data.csv')\\n\\n# Calculate the maximum drawdown\\ndf['cummax'] = df['Close'].cummax()\\ndf['drawdown'] = (df['Close'] - df['cummax']) / df['cummax']\\nmax_drawdown = df['drawdown'].min()\\n\\nprint(f'The maximum drawdown for NVIDIA in 2022 was {{max_drawdown:.2%}}')\\"}}"}}}}]}},
      {{"role": "user", "content": "The Python script has been executed. The output is: 'The maximum drawdown for NVIDIA in 2022 was -62.70%'"}},
      {{"role": "researcher", "content": "Thank you for providing the result. Let me summarize the task for you:

   Task Summary:
   1. We successfully collected NVIDIA's stock data for the year 2022 using a data retrieval tool.
   2. We then wrote and executed a Python script to calculate the maximum drawdown from this data.
   3. The calculation revealed that the maximum drawdown for NVIDIA in 2022 was -62.70%.

   This significant drawdown indicates that NVIDIA experienced a substantial decline in stock price at some point during 2022, with the stock price falling 62.70% from its peak value within that year.

   Is there anything else you would like to know about this data or any other analysis you'd like to perform?"}}
   ]
   '''

   formatted_prompt = Optimized_Task_Execution_Prompt.format(dialog_history=historical_path_example)
   print(formatted_prompt)
   return formatted_prompt


def optimized_dialogue_history_test():
   # Example usage:
   dialogue_history_example = '''
   [
      {{"role": "user", "content": "I need to analyze NVIDIA's 2022 stock data"}},
      {{"role": "researcher", "content": "I can help you analyze NVIDIA's 2022 stock data. We need to first obtain the data, then perform the analysis."}},
      {{"role": "data_agent", "content": "I will use the financial API to get NVIDIA's data.", "tool_calls": [{{"id": "call_123", "function": {{"name": "get_stock_data", "arguments": "{{\\"ticker_symbol\\":\\"NVDA\\",\\"start_date\\":\\"2022-01-01\\",\\"end_date\\":\\"2022-12-31\\",\\"period\\":\\"1d\\"}}"}}}}]}},
      {{"role": "user", "content": "Data has been successfully retrieved and saved as 'nvda_2022_data.csv'."}},
      {{"role": "data_analyst", "content": "I will now analyze this data and calculate some key metrics."}},
      {{"role": "code_agent", "content": "I will write a Python script to analyze the data and calculate the maximum drawdown.", "tool_calls": [{{"id": "call_456", "function": {{"name": "write_python_script", "arguments": "{{\\"script_content\\":\\"import pandas as pd\\n\\n# Read CSV file\\ndf = pd.read_csv('nvda_2022_data.csv')\\n\\n# Calculate maximum drawdown\\ndf['cummax'] = df['Close'].cummax()\\ndf['drawdown'] = (df['Close'] - df['cummax']) / df['cummax']\\nmax_drawdown = df['drawdown'].min()\\n\\nprint(f'The maximum drawdown for NVIDIA in 2022 was {{max_drawdown:.2%}}')\\"}}"}}}}]}},
      {{"role": "user", "content": "Script has been executed. The output result is: 'The maximum drawdown for NVIDIA in 2022 was -62.70%'"}},
      {{"role": "researcher", "content": "The analysis results show that NVIDIA's maximum drawdown in 2022 was -62.70%, indicating that the stock experienced significant price decline in 2022, falling 62.70% from its peak. This data reflects the challenges commonly faced by tech stocks in 2022. Would you like to know more about other analytical metrics for this period?"}}
   ]
   '''

   formatted_prompt = Optimiz_Dialogue_History_Prompt.format(dialog_history=dialogue_history_example)
   print(formatted_prompt)
   
   return formatted_prompt