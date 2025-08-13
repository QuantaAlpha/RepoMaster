from typing import Annotated
import json
from src.core.code_utils import get_code_abs_token

from src.utils.agent_gpt4 import AzureGPT4Chat


def generate_repository_summary(
    code_list: list[dict[Annotated[str, "File path"], Annotated[str, "File content"]]],
    max_important_files_token: int = 2000
):
    """
    Generate code repository summary
    
    Args:
        code_list: List containing code file information, each element should contain file path and content
        [
            {
                "file_path": "File path",
                "file_content": "File content"
            }
        ]
        max_important_files_token: Token count limit for important files
    """
    
    def judge_file_is_important(code_list: list[dict[Annotated[str, "File path"], Annotated[str, "File content"]]]):
        
        judge_prompt = f"""
        You are an assistant that helps developers understand code repositories. Please judge whether the current file is important for understanding the entire repository.
        Output yes for important files, no for unimportant files.
        
        Please judge whether a file is important according to the following rules:
        1. If the file is README.md and the file content contains a description of the entire repository, then consider it very important
        2. If it is a configuration file or test file or example file, then consider it very important
        3. If the file content contains information that is important for understanding the entire repository, then consider it very important, please do not ignore any important information
        4. If several files have completely duplicate file content, possibly with different filenames or languages, then keep only one (output yes) and delete the others (output no)
        
        ## Please note:
        - Please do not ignore any important information
        
        Please return a JSON list (list sorted by importance) format containing judgment of whether files are important:
        [
            {{
                "file_path": "File path",
                "is_important": "yes" or "no"
            }}
        ]
        """
        messages = [
            {"role": "system", "content": judge_prompt},
            {"role": "user", "content": json.dumps(code_list, ensure_ascii=False, indent=2)}
        ]
        try:
            response_dict = AzureGPT4Chat().chat_with_message(messages, json_format=True)
            print('response_dict: ', response_dict)
            if not isinstance(response_dict, list):
                return code_list
            out_list = []
            for judge_result in response_dict:
                if judge_result['is_important'].lower() == 'yes':
                    for file in code_list:
                        if judge_result['file_path'] == file['file_path']:
                            out_list.append(file)
            return out_list
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return code_list
    
    def split_code_lists(code_list: list[dict[Annotated[str, "File path"], Annotated[str, "File content"]]]):
        # Split according to tiktoken token count
        max_token = 50000
        out_code_list = []
        split_code_list = []
        for file in code_list:
            if get_code_abs_token(str(file)) > max_token:
                continue
            split_code_list.append(file)
            if get_code_abs_token(json.dumps(split_code_list, ensure_ascii=False, indent=2)) > max_token:
                out_code_list.append(split_code_list)
                split_code_list = []
        if split_code_list:
            out_code_list.append(split_code_list)
        return out_code_list

    # Parallel computation

    all_file_content = json.dumps(code_list, ensure_ascii=False)
    if get_code_abs_token(all_file_content) < max_important_files_token:
        return code_list    
    
    important_files = []
    for s_code_list in split_code_lists(code_list):
        important_files.extend(judge_file_is_important(s_code_list))
    
    print('important_files: ', len(code_list), len(important_files), [file['file_path'] for file in important_files])
    
    repository_summary = {}
    
    for file in important_files:
        file_path = file['file_path']
        file_content = file['file_content']
        try:
            summary = get_readme_summary(file_content, repository_summary)
            if '<none>' not in str(summary).lower():
                if get_code_abs_token(json.dumps(repository_summary, ensure_ascii=False)+str(summary))> max_important_files_token:
                    break
                repository_summary[file_path] = summary
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            continue
    print('repository_summary: ', get_code_abs_token(json.dumps(repository_summary, ensure_ascii=False)))
    return repository_summary

def get_readme_summary(code_content: str, history_summary: dict):
    """
    Get summary of README.md and other important documentation files, for overall understanding of the entire repository
    
    Args:
        code_list: List containing code file information, each element should contain file path and content
        
    Returns:
        str: Repository summary, including references to important content
    """
    
    system_prompt = """
    You are an assistant that helps developers understand code repositories. Please provide an overall understanding of the entire repository based on the provided README and other documentation files and generate a summary.
    
    When generating the summary, please follow these rules:
    1. Focus on the project's main functions, architectural design and usage methods, generate content as concise as possible, but do not miss important code blocks and commands, do not miss any important information (especially model and file download methods and model usage methods)
    2. When encountering important code that can be directly referenced from documentation, use <cite>referenced content</cite> format
    3. Keep the summary concise, comprehensive and informative
    4. Include installation methods, dependencies and example usage (if provided in documentation)
    5. If it's disclaimers or other content unimportant to code repository understanding, then ignore it.
    6. If it duplicates content in history_summary, then no need to output repeatedly.
    """
    
    prompt = f"""
    The following is the README and other important documents in the code repository:
    <code_content>
    {code_content}
    </code_content>
    
    The following is the summary of other important documents:
    <history_summary>
    {history_summary}
    </history_summary>
    
    If it duplicates content in history_summary, then no need to output repeatedly.
    """
    
    response = AzureGPT4Chat().chat_with_message(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        json_format=True
    )
    return response
