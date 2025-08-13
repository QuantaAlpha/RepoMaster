from typing import Annotated
import json
from core.code_utils import get_code_abs_token

from utils.agent_gpt4 import AzureGPT4Chat


def generate_repository_summary(
    code_list: list[dict[Annotated[str, "文件路径"], Annotated[str, "文件内容"]]],
    max_important_files_token: int = 2000
):
    """
    生成代码仓库的摘要
    
    Args:
        code_list: 包含代码文件信息的列表，每个元素应包含文件路径和内容
        [
            {
                "file_path": "文件路径",
                "file_content": "文件内容"
            }
        ]
        max_important_files_token: 重要文件的token数量限制
    """
    
    def judge_file_is_important(code_list: list[dict[Annotated[str, "文件路径"], Annotated[str, "文件内容"]]]):
        
        judge_prompt = f"""
        你是一个帮助开发者理解代码仓库的助手。请判断当前文件是否对于理解整个仓库很重要。
        重要的文件输出yes，不重要的文件输出no。
        
        请根据以下规则判断文件是否重要：
        1. 如果文件是README.md，且文件内容中包含对整个仓库的描述，则认为它很重要
        2. 如果是配置文件或者测试文件或者示例文件，则认为它很重要
        3. 如果文件内容中包含对理解整个仓库比较重要的信息，则认为它很重要，请不要忽略任何重要的信息
        4. 如果几个文件是完全重复的文件内容，可能只是文件名不同或language不同，则只保留其中一个（输出yes），其他删除（输出no）
        
        ## Please note:
        - 请不要忽略任何重要的信息
        
        请返回一个JSON list(list按照重要性排序)格式，包含文件是否重要的判断：
        [
            {{
                "file_path": "文件路径",
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
    
    def split_code_lists(code_list: list[dict[Annotated[str, "文件路径"], Annotated[str, "文件内容"]]]):
        # 按照tiktoken的token数量进行分割
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

    # 并行计算

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
    获取README.md和其他重要文档文件的摘要，对整个仓库进行整体理解
    
    Args:
        code_list: 包含代码文件信息的列表，每个元素应包含文件路径和内容
        
    Returns:
        str: 仓库摘要，包含对重要内容的引用
    """
    
    system_prompt = """
    你是一个帮助开发者理解代码仓库的助手。请基于提供的README和其他文档文件，对整个仓库进行整体理解并生成摘要。
    
    在生成摘要时，请遵循以下规则：
    1. 重点关注项目的主要功能、架构设计和使用方法，生成的内容尽量精简，但不要遗漏重要的代码块和命令, 不要遗漏任何重要的信息(特别是模型和文件下载方式和模型使用方法)
    2. 当遇到重要的代码是可以直接引用文档中的代码，使用<cite>引用内容</cite>格式
    3. 保持摘要简洁、全面且具有信息性
    4. 包括项目的安装方法、依赖项和示例用法（如果文档中有提供）
    5. 如果是一些免责声明还是一些其他对于代码仓库理解无关紧要的内容，则忽略。
    6. 如果和history_summary中内容重复，则不需要重复输出。
    """
    
    prompt = f"""
    以下是代码仓库中的README和其他重要文档:
    <code_content>
    {code_content}
    </code_content>
    
    以下是其他重要文档的摘要:
    <history_summary>
    {history_summary}
    </history_summary>
    
    如果和history_summary中内容重复，则不需要重复输出。
    """
    
    response = AzureGPT4Chat().chat_with_message(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        json_format=True
    )
    return response
