import os   
import uuid
import random
import json
import subprocess
import time
import traceback
import yaml
from src.core.agent_code_explore import CodeExplorer
from pathlib import Path
import concurrent.futures
from datetime import datetime
import asyncio
from src.utils.utils_config import AppConfig
from configs.oai_config import get_llm_config


# ======================== Utility Classes and Functions ========================

class PathManager:
    """Path management class for handling various path creation and checking operations"""
    
    @staticmethod
    def generate_task_id():
        """Generate random task ID"""
        date_str = datetime.now().strftime("%m%d_%H%M")
        return f'gitbench_{date_str}'
    
    @staticmethod
    def create_unique_path(base_path):
        """Create a unique path that doesn't exist"""
        path = f'{base_path}/{PathManager.generate_task_id()}'
        while os.path.exists(path):
            path = f'{base_path}/{PathManager.generate_task_id()}'
        return path
    
    @staticmethod
    def create_unique_dir(base_path, prefix):
        """Create a unique directory that doesn't exist"""
        path = f'{base_path}/{prefix}'
        while os.path.exists(path):
            path = f'{path}_{random.randint(1, 10)}'
        os.makedirs(path, exist_ok=True)
        return path
    
    @staticmethod
    def get_dir_size(path):
        """Get directory size using du command (unit: bytes)"""
        result = subprocess.run(['du', '-sb', path], capture_output=True, text=True)
        if result.returncode == 0:
            return int(result.stdout.split()[0])
        return 0
    
    @staticmethod
    def check_code_files(repo_path, extensions=[".py", ".ipynb"]):
        """Check if repository contains code files with specified extensions"""
        for root, _, files in os.walk(repo_path):
            if any(file.endswith(ext) for file in files for ext in extensions):
                return True
        return False

class DataProcessor:
    """Data processing class for handling file copying, decompression and other operations"""
    
    @staticmethod
    def copy_dataset(data_path, target_path):
        """Copy or link dataset to target path"""
        if not os.path.exists(target_path):
            os.makedirs(target_path, exist_ok=True)
        
        if os.path.isfile(data_path):
            os.system(f"ln -s {data_path} {target_path}/")
            return f"{target_path}/{Path(data_path).name}"
        
        for file in os.listdir(data_path):
            source = f"{data_path}/{file}"
            destination = f"{target_path}/{file}"
            
            if os.path.isdir(source):
                if os.path.exists(destination):
                    print(f"Target already exists, skipping: {destination}")
                    continue
                print(f"ln -s {source} {target_path}/")
                os.system(f"ln -s {source} {target_path}/")
            else:
                print(f"cp -a {source} {target_path}/")
                os.system(f"cp -a {source} {target_path}/")
        
        return 

    @staticmethod
    def unzip_data(data_path):
        """Extract zip files in the dataset"""
        for file in os.listdir(data_path):
            if file.endswith(".zip"):
                extract_path = f"{data_path}/{file.replace('.zip', '')}"
                os.system(f"unzip {data_path}/{file} -d {extract_path}")
    
    @staticmethod
    def setup_task_environment(task_info, work_dir):
        """Prepare task execution environment, copy repository and dataset"""
        # Handle repository
        repo_info = task_info['repo']
        repo_type = repo_info.get('type', 'local')
        target_repo_path = None
        
        if repo_type == 'local':
            # Copy local repository
            source_repo_path = repo_info['path']
            repo_name = Path(source_repo_path).name
            target_repo_path = f"{work_dir}/{repo_name}"
            
            if not os.path.exists(target_repo_path):
                os.system(f"cp -a {source_repo_path} {target_repo_path}")
        
        elif repo_type == 'github':
            # Clone GitHub repository
            repo_url = repo_info['url']
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            target_repo_path = f"{work_dir}/{repo_name}"
            
            if not os.path.exists(target_repo_path):
                clone_cmd = f"git clone {repo_url} {target_repo_path}"
                subprocess.run(clone_cmd, shell=True, check=True)
        
        # Set input and output paths
        target_input_path = PathManager.create_unique_dir(f"{work_dir}", "input_dataset")
        # target_output_path = PathManager.create_unique_dir(f"{work_dir}", "output_result")
        target_output_path = work_dir
        
        # Copy dataset (if exists)
        data_info = task_info.get('input_data', {})
        print(f"data_info: {data_info}")
        if data_info is None:
            data_info = []
        try:
            new_data_info = []
            for data in data_info:
                data_path = data.get('path')
                data_desc = data.get('description')
                if data_path and os.path.exists(data_path):
                    new_data_path = DataProcessor.copy_dataset(data_path, target_input_path)
                    if data_desc:
                        new_data_info.append({
                            'path': new_data_path,
                            'description': data_desc
                        })
                    else:
                        new_data_info.append({
                            'path': new_data_path,
                        })
            
        except Exception as e:
            print(f"Error occurred while copying dataset: {e}")
            print(traceback.format_exc())
        
        return target_output_path, new_data_info, target_repo_path

class TaskManager:
    """Task management class for handling task initialization, execution and result management"""

    @staticmethod
    def get_work_dir():
        if AppConfig.get_instance().is_initialized():
            self.st = None
        
        work_dir = AppConfig.get_instance().get_current_session()['work_dir']
        return work_dir
    
    @staticmethod
    def get_task_prompt():
        """Get task prompt"""
        return """### Task Description
{task_description}

#### Repository Path (Absolute Path): 
```
{repo_path}
```
Understanding Guide: ['Read README.md to understand basic project functionality and usage']

#### File Paths
- Input file paths and descriptions:
{input_data}

- Output file directory: 
Results must be saved in the {output_dir_path} directory. If results are saved in the repository directory, they need to be moved to the {output_dir_path} directory.

#### Additional Notes
**Core Objective**: Quickly understand and analyze the code repository, generate and execute necessary code or call tools to efficiently and accurately complete user-specified tasks.
"""
    
    @staticmethod
    def prepare_task_description(task_info, target_output_path, target_input_data, target_repo_path):
        """Generate task description based on task information"""
        # Use description from YAML or default description
        task_desc = task_info.get('task_prompt', 'Please analyze the code repository and complete related tasks')
        
        # Replace placeholders in description
        if isinstance(target_input_data, list):
            if len(target_input_data) > 1:
                target_input_data = json.dumps(target_input_data, indent=2, ensure_ascii=False)
            elif len(target_input_data) == 1:
                target_input_data = json.dumps(target_input_data[0], indent=2, ensure_ascii=False)
            else:
                target_input_data = ''
        else:
            target_input_data = str(target_input_data)
        
        placeholders = {
            '{repo_path}': target_repo_path,
            '{input_data}': target_input_data,
            '{output_dir_path}': target_output_path,
            '{task_description}': task_info.get('task_description', '')
        }
        for placeholder, value in placeholders.items():
            print(f"placeholder: {placeholder}, value: {value}")
            task_desc = task_desc.replace(placeholder, value)
        
        print(task_desc)
        
        return f"\n\nPlease help me complete the following task:\n\n{task_desc}\n\n"
    
    @staticmethod
    def load_config(config_path):
        """Load task information from YAML configuration file"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file does not exist: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        return config
    
    @staticmethod
    def initialize_tasks(args, root_path='coding'):
        """Initialize task environment and task list"""
        root_path = root_path if root_path else args.root_path
        work_task_path = PathManager.create_unique_path(root_path)
        
        # Use loaded configuration
        task_info = args.config_data
        task_id = "repo_master"
        
        out_task_info = {
            'repo': task_info['repo'],
            'task_description': task_info['task_description'],
            'task_prompt': task_info['task_prompt'] if 'task_prompt' in task_info else TaskManager.get_task_prompt(),
            'input_data': task_info['input_data'],
            'parameters': task_info.get('parameters', {}),
            'root_path': root_path,
            'work_task_path': work_task_path,
            'task_id': task_id
        }
        
        return out_task_info

class AgentRunner:
    """Agent runner responsible for running code agents to execute tasks"""
    
    @staticmethod
    def run_agent(task_info, retry_times=2, work_dir=None):
        """Run Code Agent to execute tasks"""
        try:
            task_id = task_info['task_id']
            work_task_path = task_info['work_task_path']
            
            # Determine repository information for display
            repo_info = task_info['repo']
            repo_display = repo_info.get('path', repo_info.get('url', 'Not specified'))
            print(f"Task: {task_id} | Repository: {repo_display}")
            
            # Create working directory
            # work_dir = f'{work_task_path}/{task_id}/workspace'
            work_dir = work_dir if work_dir else f'{work_task_path}/{task_id}/workspace'
            os.makedirs(work_dir, exist_ok=True)
            # import pdb; pdb.set_trace()
            # Prepare environment
            target_output_path, target_input_data, target_repo_path = DataProcessor.setup_task_environment(
                task_info, work_dir
            )
            
            # Generate task description
            task = TaskManager.prepare_task_description(
                task_info, target_output_path, target_input_data, target_repo_path
            )
            task += f"\n```\n# Github Repository URL: \n{repo_display}\n```\n"
            # task += "## Very Important Note: Output results must be named starting with 'output', such as output.txt, output.wav, etc. If there are multiple files, name them as output_01, output_02, etc. Remember to save them in the first-level subdirectory (e.g., <'{target_output_path}/output.txt'>), as the system will match files based on this naming pattern to retrieve results for subsequent task completion testing."
            
            # work_dir = target_repo_path
            print(f"✅ Working Directory: {work_dir}")
            
            # Run code agent
            explorer = CodeExplorer(
                target_repo_path, 
                work_dir=work_dir, 
                remote_repo_path=None, 
                task_type="gitbench", 
                use_venv=True, 
                is_cleanup_venv=False, 
            )
            
            answer = asyncio.run(explorer.a_code_analysis(task, max_turns=20))
            
            # answer = explorer.code_analysis(task, max_turns=30)
            print("==== code analysis done", answer)
            time.sleep(10)
            
            # Check if retry is needed
            if not os.path.exists(target_output_path) and retry_times > 0:
                print(f"---Task {task_id} submission failed, retrying {retry_times} times---")
                return AgentRunner.run_agent(task_info, retry_times - 1)
            
            for key in ["work_dir", "target_output_path", "target_input_data", "target_repo_path"]:
                task_info[key] = eval(key)
                        
            # json.dump(task_info, open(f"{work_dir}/task_info.json", "w"), indent=2, ensure_ascii=False)
            
            return answer
        except Exception as e:
            print(f"=== Task {task_id} submission failed: {e}")
            print(traceback.format_exc())
            raise e
    
    @staticmethod
    def process_single_task(task_info, args):
        """Process single task"""
        task_id = task_info['task_id']
        try:
            AgentRunner.run_agent(task_info, retry_times=args.retry)
            print(f"Task {task_id} processing completed")
        except Exception as e:
            print(f"=== Task {task_id} submission failed: {e}")
            print(traceback.format_exc())
    
    @staticmethod
    def run_sequential(args):
        """Execute all tasks sequentially"""
        task_info = TaskManager.initialize_tasks(args)
        
        print(f"Starting to process task: {task_info.get('task_id')}")
        AgentRunner.process_single_task(task_info, args)
            

def init_venv():
    """Initialize virtual environment"""
    default_venvs_dir = './.venvs'
    venv_path = os.path.join(default_venvs_dir, "persistent_venv")
    
    if os.path.exists(venv_path):
        return
    
    from src.core.code_utils import _create_virtual_env
    _create_virtual_env(venv_path)
    
    return

# ======================== Command Line Arguments and Main Function ========================

def get_args():
    """Parse command line arguments"""
    import argparse
    parser = argparse.ArgumentParser(description="Code repository task execution tool")
    parser.add_argument("--config", type=str, required=True, help="YAML configuration file path")
    parser.add_argument("--retry", type=int, default=2, help="Number of retries after task failure")
    parser.add_argument("--max_repo", type=int, default=5, help="Maximum number of repositories to process")
    parser.add_argument("--parallel", action="store_true", help="Whether to use parallel mode for task execution")
    parser.add_argument("--parallel_workers", type=int, default=4, help="Maximum number of worker processes in parallel mode")
    parser.add_argument("--root_path", type=str, default='coding', help="Root directory path")
    return parser.parse_args()

if __name__ == "__main__":
    from dotenv import load_dotenv

    init_venv()
    
    # Load environment variables
    load_dotenv("configs/.env")
    args = get_args()
    
    # Load configuration in main function
    config = TaskManager.load_config(args.config)
    # Add configuration to args object
    args.config_data = config
    
    if args.parallel:
        print("Running in parallel mode...")
        AgentRunner.run_parallel(args)
    else:
        print("Running in non-parallel mode...")
        AgentRunner.run_sequential(args)

