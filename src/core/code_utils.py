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

    
def get_code_abs_token(content):
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(content))

def should_ignore_path(path: str) -> bool:
    """Determine whether a given path should be ignored"""

    # Unified definition of directories and file patterns to ignore, use default values if not provided in parameters

    # For .ipynb files, special handling, we want to parse them
    if path.endswith('.ipynb') and not any(part in ignored_dirs for part in path.split(os.sep)):
        return False
    
    if path.startswith('.') or path.startswith('__'):
        return True
    
    # If it's an image file, ignore it
    if path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico', '.webp')):
        return True
    
    # If it's a video file, ignore it
    if path.endswith(('.mp4', '.avi', '.mov', '.wmv', '.flv', '.mpeg', '.mpg', '.m4v', '.mkv', '.webm')):
        return True
    
    # If it's an audio file, ignore it
    if path.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac', '.wma', '.m4b', '.m4p')):
        return True
    
    # If it's a compressed file, ignore it
    if path.endswith(('.zip', '.rar', '.tar', '.gz', '.bz2', '.7z', '.iso', '.dmg', '.pkg', '.deb', '.rpm', '.msi', '.exe', '.app', '.dmg', '.pkg', '.deb', '.rpm', '.msi', '.exe', '.app')):
        return True
    
    # If it's a PDF file, ignore it
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
        line_number=False,  # Show line numbers
        child_context=child_context,  # Don't show child context
        last_line=False,
        margin=0,  # Don't set margins
        mark_lois=False,  # Don't mark lines of interest
        loi_pad=0,
        show_top_of_file_parent_scope=False,
    )


    structure_lines = []
    important_lines = []
    
    for i, line in enumerate(context.lines):
        # Match function definitions, class definitions, import statements, etc.
        if re.match(r'^\s*(def|class)\s+', line):
            # Function and class definitions are the most important structures
            important_lines.append(i)
            
            # Check if current line contains single-line docstring
            if ('"""' in line and line.count('"""') >= 2) or ("'''" in line and line.count("'''") >= 2):
                # Single-line docstring, already in important_lines, no additional processing needed
                pass
            else:
                # Check if the following line is the start of a docstring
                docstring_start = i + 1
                if docstring_start < len(context.lines):
                    next_line = context.lines[docstring_start]
                    # Detect docstring start
                    triple_double = '"""' in next_line
                    triple_single = "'''" in next_line
                    
                    if triple_double or triple_single:
                        quote_type = '"""' if triple_double else "'''"
                        
                        # Check if it's a single-line docstring
                        if next_line.count(quote_type) >= 2:
                            # Single-line docstring
                            important_lines.append(docstring_start)
                        else:
                            # Multi-line docstring, find the end marker
                            for j in range(docstring_start, len(context.lines)):
                                important_lines.append(j)  # Add each line of docstring to important lines
                                if j > docstring_start and quote_type in context.lines[j]:
                                    break  # Found end marker
        elif re.match(r'^\s*(import|from)\s+', line) and i < 50:
            # Only focus on import statements at the beginning of the file
            structure_lines.append(i)
        # Match method parameters and important variable definitions
        elif re.match(r'^\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[A-Z]', line) or re.search(r'__init__', line):
            # Constant variables and initialization parameters are more important
            # import pdb;pdb.set_trace()
            # structure_lines.append(i)
            pass
        
    # Add found structure lines as lines of interest
    context.lines_of_interest = set(important_lines)
    context.add_lines_of_interest(structure_lines)
        
    # Add context
    context.add_context()
    
    # Format and output result
    formatted_code = context.format()
    # import pdb;pdb.set_trace()
    formatted_code = '\n'.join([line[1:] for line in formatted_code.split('\n')])
    
    return formatted_code


def filter_pip_output(logs_all):
    """
    Parse pip install output results and remove the following cases:
    1. Package already exists (already installed) - "Requirement already satisfied"
    2. Dependency resolution and installation - "Collecting"
    3. Cache usage information - "Using cached"
    
    Args:
        output_lines (str or list): pip install output results, can be string or list of lines
        
    Returns:
        list: Filtered list of output lines
    """
    # Convert string to list of lines
    if isinstance(logs_all, str):
        logs_lines = logs_all.strip().split('\n')
    else:
        logs_lines = logs_all
        
    import re
    
    # Verify if this is pip output
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
    
    # First check if it's pip output
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
    
    # If not pip output, return as is
    if not is_pip_output:
        return logs_all
    
    # Define regex patterns to filter
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
    
    # Filter lines
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
    Extract installation commands from pip install output results
    """
    exitcode, logs_all = execute_result
    
    prompt = f"""
    Extract installation commands from the following pip install output results:
    {logs_all}
    
    Please return a list containing installation commands, one command per line.
    """ 
    
    client = OpenAIWrapper(**get_llm_config())
    response = client.create(
        messages=[
            {"role": "system", "content": "You are a professional Python developer, skilled at extracting installation commands from pip install output results."},
            {"role": "user", "content": prompt}
        ]
    )
    

def cut_logs_by_token(logs_all, max_token: int = 4000):
    """
    Cut logs based on token count limit, keeping half at head and half at tail
    If logs are single line or few long lines, truncate text directly
    """    
    if get_code_abs_token(logs_all) <= max_token:
        return logs_all

    encoding = tiktoken.encoding_for_model("gpt-4o")
    
    # Cut logs
    logs_lines = logs_all.strip().split('\n')
    
    # if len(logs_lines) == 1 or (len(logs_lines) < 5 and get_code_abs_token(logs_all) / len(logs_lines) > max_token / 2):
    # Process single long text directly by characters
    tokens = encoding.encode(logs_all)
    
    half_token = max_token // 2
    head_tokens = tokens[:half_token]
    tail_tokens = tokens[-half_token:]
    
    head_text = encoding.decode(head_tokens)
    tail_text = encoding.decode(tail_tokens)
    
    return f"{head_text}\n\n>>> ...omitted content... <<<\n\n{tail_text}"
    
    # Allocate token quota, half for head and half for tail
    half_token = max_token // 2
    
    # Keep head
    head_lines = []
    head_tokens = 0
    for line in logs_lines:
        line_tokens = get_code_abs_token(line) + 1  # +1 for newline
        if head_tokens + line_tokens > half_token:
            break
        head_lines.append(line)
        head_tokens += line_tokens
    
    # Keep tail
    tail_lines = []
    tail_tokens = 0
    for line in reversed(logs_lines):
        line_tokens = get_code_abs_token(line) + 1  # +1 for newline
        if tail_tokens + line_tokens > half_token:
            break
        tail_lines.insert(0, line)  # Insert at beginning of list
        tail_tokens += line_tokens
    
    # Combine results
    result_lines = []
    result_lines.extend(head_lines)
    
    # If there are omitted lines between head and tail, add omission indicator
    if len(head_lines) + len(tail_lines) < len(logs_lines):
        result_lines.append("\n>>> ...omitted logs... <<<\n")
    
    # Ensure tail lines are not duplicated
    for line in tail_lines:
        if line not in head_lines[-len(tail_lines):]:
            result_lines.append(line)
    cut_logs = '\n'.join(result_lines)
    
    # Final check to ensure it doesn't exceed maximum limit
    if get_code_abs_token(cut_logs) > max_token*1.5:
        # If still too long, truncate directly
        encoding = tiktoken.encoding_for_model("gpt-4o")
        tokens = encoding.encode(cut_logs)
        cut_logs = encoding.decode(tokens[:max_token])
        cut_logs += "\n\n>>> ...truncated content... <<<\n\n"

    return cut_logs

def cut_execute_result_by_token(logs_all, max_token: int = 4000):
    """
    Cut execution results based on token count limit, keeping half at head and half at tail
    """
    cut_logs = cut_logs_by_token(logs_all, max_token)
    
    return cut_logs


def _create_virtual_env(venv_path):
    """Create virtual environment and install basic dependencies"""
    
    # Use autogen's method to create virtual environment
    venv_context = create_virtual_env(venv_path)
    
    # Install basic dependencies - use . instead of source, compatible with sh and bash
    # And explicitly specify using bash to execute commands
    activate_script = os.path.join(venv_path, "bin", "activate")
    activate_cmd = f"bash -c '. {activate_script} && "
    
    print(f"Starting to install LLM-related dependencies to virtual environment: {venv_path}", flush=True)
    
    # Update pip
    subprocess.run(f"{activate_cmd} pip install -U pip'", shell=True)
    
    # Get absolute path of requirements file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    requirements_path = os.path.join(os.path.dirname(current_dir), "configs/docker_src/llm_requirements.txt")
    
    # Check if requirements file exists
    if os.path.exists(requirements_path):
        print(f"Installing dependencies using requirements file: {requirements_path}")
        # Install all dependencies using requirements file
        subprocess.run(
            f"{activate_cmd} pip install -r {requirements_path}'",
            shell=True
        )
    else:
        print(f"⚠️ Warning: requirements file does not exist {requirements_path}, using fallback installation method")
        # Fallback method: directly install key dependencies
        subprocess.run(
            f"{activate_cmd} pip install numpy pandas torch transformers==4.35.0 tokenizers'",
            shell=True
        )
    
    print(f"Virtual environment created and installation completed: {venv_path}", flush=True)
    return venv_context
