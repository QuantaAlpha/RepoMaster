import os   
import uuid
import random
import json
import subprocess
import time
import traceback
import yaml
from core.agent_code_explore import CodeExplorer
from pathlib import Path
import concurrent.futures
from datetime import datetime
import asyncio
from utils.utils_config import AppConfig
from configs.oai_config import get_llm_config


# ======================== 工具类和工具函数 ========================

class PathManager:
    """路径管理类，处理各种路径创建和检查操作"""
    
    @staticmethod
    def generate_task_id():
        """生成随机任务ID"""
        date_str = datetime.now().strftime("%m%d_%H%M")
        return f'gitbench_{date_str}'
    
    @staticmethod
    def create_unique_path(base_path):
        """创建一个不存在的唯一路径"""
        path = f'{base_path}/{PathManager.generate_task_id()}'
        while os.path.exists(path):
            path = f'{base_path}/{PathManager.generate_task_id()}'
        return path
    
    @staticmethod
    def create_unique_dir(base_path, prefix):
        """创建一个不存在的唯一目录"""
        path = f'{base_path}/{prefix}'
        while os.path.exists(path):
            path = f'{path}_{random.randint(1, 10)}'
        os.makedirs(path, exist_ok=True)
        return path
    
    @staticmethod
    def get_dir_size(path):
        """使用du命令获取目录大小（单位：字节）"""
        result = subprocess.run(['du', '-sb', path], capture_output=True, text=True)
        if result.returncode == 0:
            return int(result.stdout.split()[0])
        return 0
    
    @staticmethod
    def check_code_files(repo_path, extensions=[".py", ".ipynb"]):
        """检查仓库中是否存在指定扩展名的代码文件"""
        for root, _, files in os.walk(repo_path):
            if any(file.endswith(ext) for file in files for ext in extensions):
                return True
        return False

class DataProcessor:
    """数据处理类，处理文件复制、解压等操作"""
    
    @staticmethod
    def copy_dataset(data_path, target_path):
        """复制或链接数据集到目标路径"""
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
                    print(f"目标已存在，跳过: {destination}")
                    continue
                print(f"ln -s {source} {target_path}/")
                os.system(f"ln -s {source} {target_path}/")
            else:
                print(f"cp -a {source} {target_path}/")
                os.system(f"cp -a {source} {target_path}/")
        
        return 

    @staticmethod
    def unzip_data(data_path):
        """解压数据集中的zip文件"""
        for file in os.listdir(data_path):
            if file.endswith(".zip"):
                extract_path = f"{data_path}/{file.replace('.zip', '')}"
                os.system(f"unzip {data_path}/{file} -d {extract_path}")
    
    @staticmethod
    def setup_task_environment(task_info, work_dir):
        """准备任务运行环境，复制仓库和数据集"""
        # 处理仓库
        repo_info = task_info['repo']
        repo_type = repo_info.get('type', 'local')
        target_repo_path = None
        
        if repo_type == 'local':
            # 复制本地仓库
            source_repo_path = repo_info['path']
            repo_name = Path(source_repo_path).name
            target_repo_path = f"{work_dir}/{repo_name}"
            
            if not os.path.exists(target_repo_path):
                os.system(f"cp -a {source_repo_path} {target_repo_path}")
        
        elif repo_type == 'github':
            # 克隆GitHub仓库
            repo_url = repo_info['url']
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            target_repo_path = f"{work_dir}/{repo_name}"
            
            if not os.path.exists(target_repo_path):
                clone_cmd = f"git clone {repo_url} {target_repo_path}"
                subprocess.run(clone_cmd, shell=True, check=True)
        
        # 设置输入和输出路径
        target_input_path = PathManager.create_unique_dir(f"{work_dir}", "input_dataset")
        # target_output_path = PathManager.create_unique_dir(f"{work_dir}", "output_result")
        target_output_path = work_dir
        
        # 复制数据集(如果有)
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
            print(f"复制数据集时发生错误: {e}")
            print(traceback.format_exc())
        
        return target_output_path, new_data_info, target_repo_path

class TaskManager:
    """任务管理类，处理任务初始化、执行和结果管理"""

    @staticmethod
    def get_work_dir():
        if AppConfig.get_instance().is_initialized():
            self.st = None
        
        work_dir = AppConfig.get_instance().get_current_session()['work_dir']
        return work_dir
    
    @staticmethod
    def get_task_prompt():
        """获取任务提示"""
        return """### 任务描述
{task_description}

#### 仓库路径 (绝对路径): 
```
{repo_path}
```
理解指南: ['阅读README.md了解项目基本功能和使用方法']

#### 文件路径
- 输入文件路径和描述:
{input_data}

- 输出文件目录: 
必须把结果保存在{output_dir_path}目录下, 如果结果保存在仓库目录下, 则需要把结果移动到{output_dir_path}目录下.

#### 补充说明
**核心目标**: 快速理解和分析代码仓库，生成并执行必要的代码或调用工具，以高效、准确地完成用户指定的任务。
"""
    
    @staticmethod
    def prepare_task_description(task_info, target_output_path, target_input_data, target_repo_path):
        """根据任务信息生成任务描述"""
        # 使用YAML中的描述或默认描述
        task_desc = task_info.get('task_prompt', '请分析代码仓库并完成相关任务')
        
        # 替换描述中的占位符
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
        
        return f"\n\n帮我基于搜索到的仓库来完成以下任务:\n\n{task_desc}\n\n"
    
    @staticmethod
    def load_config(config_path):
        """从YAML配置文件加载任务信息"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        return config
    
    @staticmethod
    def initialize_tasks(args, root_path='coding'):
        """初始化任务环境和任务列表"""
        root_path = root_path if root_path else args.root_path
        work_task_path = PathManager.create_unique_path(root_path)
        
        # 使用已加载的配置
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
    """代理运行器，负责运行代码代理执行任务"""
    
    @staticmethod
    def run_agent(task_info, retry_times=2, work_dir=None):
        """运行Code Agent执行任务"""
        try:
            task_id = task_info['task_id']
            work_task_path = task_info['work_task_path']
            
            # 确定仓库信息用于显示
            repo_info = task_info['repo']
            repo_display = repo_info.get('path', repo_info.get('url', '未指定'))
            print(f"任务: {task_id} | 仓库: {repo_display}")
            
            # 创建工作目录
            # work_dir = f'{work_task_path}/{task_id}/workspace'
            work_dir = work_dir if work_dir else f'{work_task_path}/{task_id}/workspace'
            os.makedirs(work_dir, exist_ok=True)
            # import pdb; pdb.set_trace()
            # 准备环境
            target_output_path, target_input_data, target_repo_path = DataProcessor.setup_task_environment(
                task_info, work_dir
            )
            
            # 生成任务描述
            task = TaskManager.prepare_task_description(
                task_info, target_output_path, target_input_data, target_repo_path
            )
            task += f"\n```\n# Github仓库地址: \n{repo_display}\n```\n"
            # task += "## 非常重要, 请注意: 保存的输出结果需要以output开头来命名，比如output.txt, output.wav等等, 如果存在多个文件，就以output_01, output_02, 等等来命名. 记住一定要保存在的一级子目录下(比如<'{target_output_path}/output.txt'>), 因为后续需要在该子目录下根据文件的这个字段匹配来获取结果, 进行后续的任务完成效果测试."
            
            # work_dir = target_repo_path
            print(f"✅ 工作目录: {work_dir}")
            
            # 运行代码代理
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
            
            # 检查是否需要重试
            if not os.path.exists(target_output_path) and retry_times > 0:
                print(f"---任务{task_id}提交失败，重试{retry_times}次---")
                return AgentRunner.run_agent(task_info, retry_times - 1)
            
            for key in ["work_dir", "target_output_path", "target_input_data", "target_repo_path"]:
                task_info[key] = eval(key)
                        
            # json.dump(task_info, open(f"{work_dir}/task_info.json", "w"), indent=2, ensure_ascii=False)
            
            return answer
        except Exception as e:
            print(f"=== 任务{task_id}提交失败: {e}")
            print(traceback.format_exc())
            import pdb; pdb.set_trace()
            raise e
    
    @staticmethod
    def process_single_task(task_info, args):
        """处理单个任务"""
        task_id = task_info['task_id']
        try:
            AgentRunner.run_agent(task_info, retry_times=args.retry)
            print(f"任务 {task_id} 处理完成")
        except Exception as e:
            print(f"=== 任务{task_id}提交失败: {e}")
            print(traceback.format_exc())
    
    @staticmethod
    def run_sequential(args):
        """顺序执行所有任务"""
        task_info = TaskManager.initialize_tasks(args)
        
        print(f"开始处理任务: {task_info.get('task_id')}")
        AgentRunner.process_single_task(task_info, args)
            

def init_venv():
    """初始化虚拟环境"""
    default_venvs_dir = './.venvs'
    venv_path = os.path.join(default_venvs_dir, "persistent_venv")
    
    if os.path.exists(venv_path):
        return
    
    from core.code_utils import _create_virtual_env
    _create_virtual_env(venv_path)
    
    return

# ======================== 命令行参数和主函数 ========================

def get_args():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description="代码仓库任务执行工具")
    parser.add_argument("--config", type=str, required=True, help="YAML配置文件路径")
    parser.add_argument("--retry", type=int, default=2, help="任务失败后重试次数")
    parser.add_argument("--max_repo", type=int, default=5, help="最大处理仓库数量")
    parser.add_argument("--parallel", action="store_true", help="是否使用并行模式执行任务")
    parser.add_argument("--parallel_workers", type=int, default=4, help="并行模式下的最大工作进程数")
    parser.add_argument("--root_path", type=str, default='coding', help="根目录路径")
    return parser.parse_args()

if __name__ == "__main__":
    from dotenv import load_dotenv

    init_venv()
    
    # 加载环境变量
    load_dotenv("configs/.env")
    args = get_args()
    
    # 在main函数中加载配置
    config = TaskManager.load_config(args.config)
    # 将配置添加到args对象中
    args.config_data = config
    
    if args.parallel:
        print("使用并行模式运行...")
        AgentRunner.run_parallel(args)
    else:
        print("使用非并行模式运行...")
        AgentRunner.run_sequential(args)

