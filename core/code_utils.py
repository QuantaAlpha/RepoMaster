import re
import os
import tiktoken
import subprocess
from grep_ast import TreeContext
from autogen.oai import OpenAIWrapper
from autogen.code_utils import create_virtual_env

from typing import Annotated
import json
ignored_dirs = ['__pycache__', '.git', '.vscode', 'venv', 'env', 'node_modules', '.pytest_cache', 'build', 'dist', '.github', 'logs']
ignored_file_patterns = [r'.*\.pyc$', r'.*\.pyo$', r'.*\.pyd$', r'.*\.so$', r'.*\.dll$', r'.*\.class$', r'.*\.egg-info$', r'.*~$', r'.*\.swp$']

def get_llm_config(timeout: int = 120, temperature: float = 0.7):
    
    # return {
    #     "config_list": [{
    #         "model": "qwen3-32b-FP8",
    #         "api_key": "sk-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    #         "base_url": "https://1c44275a9c72b32805.gradio.live"
    #         }
    #     ],
    #     "timeout": timeout,
    # }
    
    # return {
    #     "config_list": [{
    #         "model": "qwen3-32b-FP8",
    #         "api_key": "sk-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    #         "base_url": "https://1c44275a9c72b32805.gradio.live"
    #         }
    #     ],
    #     "timeout": timeout,
    #     "temperature": temperature,
    # }
 
    # return {
    #     "config_list": [{
    #         "model": "claude-3-5-sonnet-20241022",
    #         "base_url": "https://api.anthropic.com/v1",
    #         # "api_key": os.environ["ANTHROPIC_API_KEY"]
    #         "api_key": "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"
    #     }],
    #     "timeout": timeout,
    #     "temperature": temperature,
    # }
    
    # 尝试获取Azure配置，如果不存在则使用OpenAI配置
    if all(key in os.environ for key in ["AZURE_OPENAI_MODEL", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_BASE_URL"]):
        return {
            "config_list": [{
                "model": os.environ["AZURE_OPENAI_MODEL"],
                "api_key": os.environ["AZURE_OPENAI_API_KEY"],
                "base_url": os.environ["AZURE_OPENAI_BASE_URL"],
                "api_type": "azure",
                "api_version": "2024-02-15-preview"
                }
            ],
            "timeout": timeout,
            "temperature": temperature,
        }
    else:
        return {
            "config_list": [{
                "model": "gpt-4o",
                "api_key": os.environ["OPENAI_API_KEY"]
                }
            ],
            "timeout": timeout,
            "temperature": temperature,
        }
    
def get_code_abs_token(content):
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(content))

def should_ignore_path(path: str) -> bool:
    """判断给定路径是否应该被忽略"""

    # 统一定义要忽略的目录和文件模式，如果参数中没有提供，使用默认值

    # 对于.ipynb文件，特殊处理，我们希望解析它们
    if path.endswith('.ipynb') and not any(part in ignored_dirs for part in path.split(os.sep)):
        return False
    
    if path.startswith('.') or path.startswith('__'):
        return True
    
    # 如果是图片文件，则忽略
    if path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.webp')):
        return True
    
    # 如果是视频文件，则忽略
    if path.endswith(('.mp4', '.avi', '.mov', '.wmv', '.flv', '.mpeg', '.mpg', '.m4v', '.mkv', '.webm')):
        return True
    
    # 如果是音频文件，则忽略
    if path.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.wma', '.m4b', '.m4p')):
        return True
    
    # 如果是压缩文件，则忽略
    if path.endswith(('.zip', '.rar', '.tar', '.gz', '.bz2', '.7z', '.iso', '.dmg', '.pkg', '.deb', '.rpm', '.msi', '.exe', '.app', '.dmg', '.pkg', '.deb', '.rpm', '.msi', '.exe', '.app')):
        return True
    
    # 如果是PDF文件，则忽略
    if path.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
        return True
    
    path_parts = path.split(os.sep)
    for part in path_parts:
        if part in ignored_dirs:
            return True
    
    file_name = os.path.basename(path)
    for pattern in ignored_file_patterns:
        if re.match(pattern, file_name):
            return True
        
    return False

def _get_code_abs(filename, source_code, max_token=3000, child_context=False):
    # import pdb;pdb.set_trace()
    
    context = TreeContext(
        filename,
        source_code,
        color=False,
        line_number=False,  # 显示行号
        child_context=child_context,  # 不显示子上下文
        last_line=False,
        margin=0,  # 不设置边距
        mark_lois=False,  # 不标记感兴趣的行
        loi_pad=0,
        show_top_of_file_parent_scope=False,
    )


    structure_lines = []
    important_lines = []
    
    for i, line in enumerate(context.lines):
        # 匹配函数定义、类定义、导入语句等
        if re.match(r'^\s*(def|class)\s+', line):
            # 函数和类定义是最重要的结构
            important_lines.append(i)
            
            # 检查当前行是否包含单行docstring
            if ('"""' in line and line.count('"""') >= 2) or ("'''" in line and line.count("'''") >= 2):
                # 单行docstring，已经在important_lines中，无需额外处理
                pass
            else:
                # 检查紧随其后的行是否是docstring的开始
                docstring_start = i + 1
                if docstring_start < len(context.lines):
                    next_line = context.lines[docstring_start]
                    # 检测docstring开始
                    triple_double = '"""' in next_line
                    triple_single = "'''" in next_line
                    
                    if triple_double or triple_single:
                        quote_type = '"""' if triple_double else "'''"
                        
                        # 检查是否是单行docstring
                        if next_line.count(quote_type) >= 2:
                            # 单行docstring
                            important_lines.append(docstring_start)
                        else:
                            # 多行docstring，查找结束标记
                            for j in range(docstring_start, len(context.lines)):
                                important_lines.append(j)  # 将docstring的每一行都添加到重要行
                                if j > docstring_start and quote_type in context.lines[j]:
                                    break  # 找到结束标记
        elif re.match(r'^\s*(import|from)\s+', line) and i < 50:
            # 只关注文件开头的导入语句
            structure_lines.append(i)
        # 匹配方法参数和重要变量定义
        elif re.match(r'^\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[A-Z]', line) or re.search(r'__init__', line):
            # 常量变量和初始化参数更重要
            # import pdb;pdb.set_trace()
            # structure_lines.append(i)
            pass
        
    # 添加找到的结构行作为感兴趣的行
    context.lines_of_interest = set(important_lines)
    context.add_lines_of_interest(structure_lines)
        
    # 添加上下文
    context.add_context()
    
    # 格式化并输出结果
    formatted_code = context.format()
    # import pdb;pdb.set_trace()
    formatted_code = '\n'.join([line[1:] for line in formatted_code.split('\n')])
    
    return formatted_code

def llm_generte_response(messages: list, llm_config=None):
    if llm_config is None:
        llm_config = get_llm_config()
    client = OpenAIWrapper(**llm_config)
    response = client.create(
        messages=messages
    )
    return response.choices[0].message.content

def parse_llm_response(response_text: str):
    """
    Parse LLM response text into dictionary.
    """
    import ast
    # Remove any markdown code block indicators
    response_text = re.sub(r"```(?:json|python)?\s*", "", response_text)
    response_text = response_text.strip("`")

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(response_text)
        except (SyntaxError, ValueError):
            result = {}
            pattern = r'["\']?(\w+)["\']?\s*:\s*([^,}\n]+)'
            matches = re.findall(pattern, response_text)
            for key, value in matches:
                try:
                    result[key] = ast.literal_eval(value)
                except (SyntaxError, ValueError):
                    result[key] = value.strip("\"'")
            return result


def filter_pip_output(logs_all):
    """
    解析pip install的输出结果，删除以下几种情况：
    1. 包已存在（已安装）- "Requirement already satisfied"
    2. 依赖解析和安装 - "Collecting"
    3. 缓存使用信息 - "Using cached"
    
    Args:
        output_lines (str or list): pip install的输出结果，可以是字符串或行列表
        
    Returns:
        list: 过滤后的输出行列表
    """
    # 将字符串转换为行列表
    if isinstance(logs_all, str):
        logs_lines = logs_all.strip().split('\n')
    else:
        logs_lines = logs_all
        
    import re
    
    # 验证这是否是pip输出
    is_pip_output = False
    pip_indicators = [
        r"Successfully installed ",
        r"Requirement already satisfied:",
        r"WARNING: You are using pip version",
        r"ERROR: pip's dependency resolver",
        r"ERROR: Could not install packages",
        r"Attempting uninstall",
        r"Found existing installation",
        r"Successfully uninstalled",
        r"Requirement already satisfied:",
        
    ]
    pip_regexes = [re.compile(pattern) for pattern in pip_indicators]
    
    # 首先检查是否为pip输出
    for line in logs_lines:
        for regex in pip_regexes:
            try:
                if regex.search(line):
                    is_pip_output = True
                    break
            except Exception as e:
                import pdb;pdb.set_trace()
                pass
        if is_pip_output:
            break
    
    # 如果不是pip输出，原样返回
    if not is_pip_output:
        return logs_all
    
    # 定义要过滤的正则表达式模式
    filter_patterns = [
        r"^\s*Requirement already satisfied:",
        r"^\s*Collecting\s+\S+",
        r"^\s*Using cached",
        r"^\s*Installing collected packages",
        r"^\s*Downloading\s+\S+",
        r"^\s*Attempting uninstall",
        r"^\s*Found existing installation",
        r"^\s*Uninstalling",
        r"^\s*Successfully uninstalled",
        r"^\s*Requirement already satisfied:",
    ]
    
    filter_regexes = [re.compile(pattern) for pattern in filter_patterns]
    
    # 过滤行
    filtered_lines = []
    for line in logs_lines:
        should_keep = True
        for regex in filter_regexes:
            if regex.search(line):
                should_keep = False
                break
                
        if should_keep:
            filtered_lines.append(line)
            
    return '\n'.join(filtered_lines)

def get_pip_install_command(execute_result):
    """
    从pip install的输出结果中提取安装命令
    """
    exitcode, logs_all = execute_result
    
    prompt = f"""
    从以下pip install的输出结果中提取安装命令：
    {logs_all}
    
    请返回一个包含安装命令的列表，每个命令占一行。
    """ 
    
    client = OpenAIWrapper(**get_llm_config())
    response = client.create(
        messages=[
            {"role": "system", "content": "你是一个专业的Python开发者，擅长从pip install的输出结果中提取安装命令。"},
            {"role": "user", "content": prompt}
        ]
    )
    

def cut_logs_by_token(logs_all, max_token: int = 4000):
    """
    根据token数量限制，切割日志，保留头尾各一半
    如果日志是单行或少量长行，则直接截断文本
    """    
    if get_code_abs_token(logs_all) <= max_token:
        return logs_all

    encoding = tiktoken.encoding_for_model("gpt-4o")
    
    # 切割日志
    logs_lines = logs_all.strip().split('\n')
    
    # if len(logs_lines) == 1 or (len(logs_lines) < 5 and get_code_abs_token(logs_all) / len(logs_lines) > max_token / 2):
    # 直接按字符处理单行长文本
    tokens = encoding.encode(logs_all)
    
    half_token = max_token // 2
    head_tokens = tokens[:half_token]
    tail_tokens = tokens[-half_token:]
    
    head_text = encoding.decode(head_tokens)
    tail_text = encoding.decode(tail_tokens)
    
    return f"{head_text}\n\n>>> ...省略的内容... <<<\n\n{tail_text}"
    
    # 分配token额度，头尾各一半
    half_token = max_token // 2
    
    # 保留头部
    head_lines = []
    head_tokens = 0
    for line in logs_lines:
        line_tokens = get_code_abs_token(line) + 1  # +1 for newline
        if head_tokens + line_tokens > half_token:
            break
        head_lines.append(line)
        head_tokens += line_tokens
    
    # 保留尾部
    tail_lines = []
    tail_tokens = 0
    for line in reversed(logs_lines):
        line_tokens = get_code_abs_token(line) + 1  # +1 for newline
        if tail_tokens + line_tokens > half_token:
            break
        tail_lines.insert(0, line)  # 插入到列表开头
        tail_tokens += line_tokens
    
    # 组合结果
    result_lines = []
    result_lines.extend(head_lines)
    
    # 如果头尾之间有省略的行，添加省略提示
    if len(head_lines) + len(tail_lines) < len(logs_lines):
        result_lines.append("\n>>> ...省略的日志... <<<\n")
    
    # 确保不会重复添加尾部的行
    for line in tail_lines:
        if line not in head_lines[-len(tail_lines):]:
            result_lines.append(line)
    cut_logs = '\n'.join(result_lines)
    
    # 最终检查，确保不超过最大限制
    if get_code_abs_token(cut_logs) > max_token*1.5:
        # 如果还是太长，直接截断
        encoding = tiktoken.encoding_for_model("gpt-4o")
        tokens = encoding.encode(cut_logs)
        cut_logs = encoding.decode(tokens[:max_token])
        cut_logs += "\n\n>>> ...截断的内容... <<<\n\n"

    return cut_logs

def cut_execute_result_by_token(logs_all, max_token: int = 4000):
    """
    根据token数量限制，切割执行结果，保留头尾各一半
    """
    cut_logs = cut_logs_by_token(logs_all, max_token)
    
    return cut_logs


def _create_virtual_env(venv_path):
    """创建虚拟环境并安装基础依赖"""
    
    # 使用autogen的方法创建虚拟环境
    venv_context = create_virtual_env(venv_path)
    
    # 安装基础依赖 - 使用 . 代替 source，兼容sh和bash
    # 并明确指定使用bash执行命令
    activate_script = os.path.join(venv_path, "bin", "activate")
    activate_cmd = f"bash -c '. {activate_script} && "
    
    print(f"开始安装LLM相关依赖到虚拟环境: {venv_path}", flush=True)
    
    # 更新pip
    subprocess.run(f"{activate_cmd} pip install -U pip'", shell=True)
    
    # 获取requirements文件的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    requirements_path = os.path.join(os.path.dirname(current_dir), "enviroment/llm_requirements.txt")
    
    # 检查requirements文件是否存在
    if os.path.exists(requirements_path):
        print(f"使用requirements文件安装依赖: {requirements_path}")
        # 使用requirements文件安装所有依赖
        subprocess.run(
            f"{activate_cmd} pip install -r {requirements_path}'",
            shell=True
        )
    else:
        print(f"⚠️ 警告: requirements文件不存在 {requirements_path}，使用备用方式安装")
        # 备用方式: 直接安装关键依赖
        subprocess.run(
            f"{activate_cmd} pip install numpy pandas torch transformers==4.35.0 tokenizers'",
            shell=True
        )
    
    print(f"虚拟环境创建并安装完成: {venv_path}", flush=True)
    return venv_context

if __name__ == "__main__":
    out_res = cut_logs_by_token(open("/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/coding/task58/chaii-hindi-and-tamil-question-answering/HarmanDotpy_Multilingual-Question-Answering-NLP/Multilingual-Question-Answering-NLP/rock-the-tim-submission.ipynb").read(), max_token=200)
    print(out_res)
    tokens = get_code_abs_token(out_res)
    print(tokens)
    