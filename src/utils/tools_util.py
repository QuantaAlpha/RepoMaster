import os
import re
import json
import random
import string

import pandas as pd
from pandas import DataFrame
from datetime import date, timedelta, datetime

from autogen.oai.client import ModelClient, OpenAIWrapper
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    Annotated,
)


# Define custom annotated types
# VerboseType = Annotated[bool, "Whether to print data to console. Default to True."]
SavePathType = Annotated[str, "Optional path to save the data. If None, data is not saved."]


# def process_output(data: pd.DataFrame, tag: str, verbose: VerboseType = True, save_path: SavePathType = None) -> None:
#     if verbose:
#         print(data.to_string())
#     if save_path:
#         data.to_csv(save_path)
#         print(f"{tag} saved to {save_path}")

def get_autogen_message_history(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    return all_messages

def is_table_file(file_path):
    """
    Check if the given file is likely to be a table format file.
    """
    _, ext = os.path.splitext(file_path)
    table_extensions = [".xlsx", ".xls", ".csv", ".ods"]

    if ext.lower() in table_extensions:
        try:
            if ext.lower() in [".xlsx", ".xls", ".ods"]:
                table = pd.read_excel(file_path, nrows=5)
            else:  # CSV
                table = pd.read_csv(file_path, nrows=5)
            return True, table
        except Exception:
            pass

    return False, None


def random_string(length=12):
    letters = string.ascii_lowercase + string.digits
    return "".join(random.choice(letters) for i in range(length))


def save_output(data: Any, save_path: Optional[str], tag="") -> Union[str, None]:
    """
    Save data to the specified path based on the file extension.

    Args:
        data (Any): The data to save.
        save_path (Optional[str]): The path where the data should be saved. If None, the function does nothing.

    Returns:
        Union[str, None]: The file path if saved, otherwise None.

    Example:
        >>> save_output(df, 'dataframe.csv')
    """
    if save_path:
        _, ext = os.path.splitext(save_path)
        ext = ext.lower()

        if ext in [".csv", ".xlsx"]:
            if isinstance(data, DataFrame):
                if ext == ".csv":
                    data.to_csv(save_path, index=False)
                elif ext == ".xlsx":
                    data.to_excel(save_path, index=False)
            else:
                raise ValueError("Data is not a DataFrame, cannot save as CSV or Excel")

        elif ext == ".txt" and isinstance(data, str):
            with open(save_path, "w") as f:
                f.write(data)
        else:
            raise ValueError(
                f"Unsupported file extension or data type for: {save_path}"
            )

        return save_path

    return None


def get_current_date():
    return date.today().strftime("%Y-%m-%d")


def register_keys_from_json(file_path):
    with open(file_path, "r") as f:
        keys = json.load(f)
    for key, value in keys.items():
        os.environ[key] = value


def decorate_all_methods(decorator):
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator


def get_next_weekday(date):

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date


# def create_inner_assistant(
#         name, system_message, llm_config, max_round=10,
#         code_execution_config=None
#     ):

#     inner_assistant = autogen.AssistantAgent(
#         name=name,
#         system_message=system_message + "Reply TERMINATE when the task is done.",
#         llm_config=llm_config,
#         is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0,
#     )
#     executor = autogen.UserProxyAgent(
#         name=f"{name}-executor",
#         human_input_mode="NEVER",
#         code_execution_config=code_execution_config,
#         default_auto_reply="",
#         is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0,
#     )
#     assistant.register_nested_chats(
#         [{"recipient": assistant, "message": reflection_message, "summary_method": "last_msg", "max_turns": 1}],
#         trigger=ConversableAgent
#         )
#     return manager


def order_trigger(sender):
    # Check if the last message contains the path to the instruction text file
    return "instruction & resources saved to" in sender.last_message()["content"]


def order_message(recipient, messages, sender, config):
    # Extract the path to the instruction text file from the last message
    full_order = recipient.chat_messages_for_summary(sender)[-1]["content"]
    txt_path = full_order.replace("instruction & resources saved to ", "").strip()
    with open(txt_path, "r") as f:
        instruction = f.read() + "\n\nReply TERMINATE at the end of your response."
    return instruction


def print_st_markdown(st, content):
    st.markdown(content)


def _print_received_message(message: Union[Dict, str], sender, **kwargs):
    # Function to print message using streamlit
    st = kwargs["st"]

    def print_markdown(content):
        st.markdown(content)

    # Print the sender name
    agent_name = kwargs.get("agent_name", "")
    # print_markdown(f"**{sender.name}** (to **{agent_name}**):")

    if message.get("tool_responses"):  # Handle tool multi-call responses
        for tool_response in message["tool_responses"]:
            _print_received_message(tool_response, sender, **kwargs)
        if message.get("role") == "tool":
            return  # If role is tool, then content is just a concatenation of all tool_responses

    if message.get("role") in ["function", "tool"]:
        if message["role"] == "function":
            id_key = "name"
        else:
            id_key = "tool_call_id"
        id = message.get(id_key, "No id found")
        func_print = f"**Response from calling {message['role']} ({id})**"
        print_markdown(func_print)
        print_markdown(message["content"])
        print_markdown(f"{'*' * len(func_print)}")
    else:
        content = message.get("content")
        if content is not None:
            if "context" in message:
                content = OpenAIWrapper.instantiate(
                    content,
                    message["context"],
                    # self.llm_config and self.llm_config.get("allow_format_str_template", False),
                )
            print_markdown(content)
        if "function_call" in message and message["function_call"]:
            function_call = dict(message["function_call"])
            func_print = f"**Suggested function call: {function_call.get('name', '(No function name found)')}**"
            print_markdown(func_print)
            print_markdown(
                "Arguments:\n" + function_call.get("arguments", "(No arguments found)")
            )
            print_markdown(f"{'*' * len(func_print)}")
        if "tool_calls" in message and message["tool_calls"]:
            for tool_call in message["tool_calls"]:
                id = tool_call.get("id", "No tool call id found")
                function_call = dict(tool_call.get("function", {}))
                func_print = f"**Suggested tool call ({id}): {function_call.get('name', '(No function name found)')}**"
                print_markdown(func_print)
                print_markdown(
                    "Arguments:\n"
                    + function_call.get("arguments", "(No arguments found)")
                )
                print_markdown(f"{'*' * len(func_print)}")

    # print_markdown("\n" + "-" * 80)


def display_pd_and_save_data(df: DataFrame, file_path, num_rows=5):
    """
    Display part of the DataFrame data and save all the data to the specified folder.

    Parameters:
    df (pd.DataFrame): DataFrame to be processed.
    file_path (str): The full file path to save the data.
    num_rows (int): The number of rows to display, default is 5.

    Returns:
    str: Markdown format string of part of the DataFrame data.
    """
    display_df = df.head(num_rows)

    markdown_data = display_df.to_markdown(index=False)

    save_output(df, file_path)

    return markdown_data

def remove_work_dir_prefix(filename, work_dir):
    # Normalize paths
    work_dir = os.path.normpath(work_dir)
    filename = os.path.normpath(filename)

    # Check if filename contains work_dir
    if os.path.commonpath([work_dir, filename]) == work_dir:
        # If it contains, get relative path
        return os.path.relpath(filename, work_dir)
    else:
        return filename

def sanitize_filename(filename):
    # Remove any non-word characters (everything except numbers, letters and underscores)
    filename = re.sub(r'[^\w\-_\. ]', '', filename)
    filename = re.sub(r'\s+', '_', filename)
    
    # Remove leading/trailing periods and underscores
    filename = filename.strip('._').lower()
    
    # Limit length to 255 characters (common filesystem limit)
    filename = filename[:40]
    
    return filename

def print_file_content(file_path):
    if os.path.exists(file_path):
        print(f"# {file_path.split('/')[-1]}")
        with open(file_path, 'r') as file:
            print(file.read())
        print("\n" + "=" * 50 + "\n")
    else:
        print(f"File not found: {file_path}")


def display(message: str, message_type: str = 'text', output_handler: Optional[Any] = None):
    """
    Display function that can handle different output methods.
    
    :param message: The message to display
    :param message_type: The type of message ('text', 'code', etc.)
    :param output_handler: Object handling the output (e.g., Streamlit)
    """
    if output_handler and hasattr(output_handler, 'markdown') and hasattr(output_handler, 'code'):
        if message_type == 'code':
            output_handler.code(message)
        else:
            output_handler.markdown(message)
    else:
        print(message)

def get_output_handler():
    from src.utils.tool_streamlit import AppContext
    output_handler = AppContext.get_instance().st
    return output_handler          

if __name__ == "__main__":
    files_to_check = [
        "/home/dfoadmin/huacan/Agent/Finance_Agent/FEB/FinAgent/utils/article_search/tool_arxiv_search.py",
        "/home/dfoadmin/huacan/Agent/Finance_Agent/FEB/FinAgent/utils/article_search/tool_github_search.py",
    ]

    for file_path in files_to_check:
        print_file_content(file_path)