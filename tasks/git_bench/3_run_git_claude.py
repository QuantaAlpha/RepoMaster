import os   
import uuid
import random
import json
import subprocess
import time
import traceback
from core.git_agent import CodeExplorer
from pathlib import Path
import concurrent.futures  # 添加并行处理模块

# ======================== 常量配置 ========================

DEFAULT_ROOT_PATH = "/mnt/ceph/huacan/Data/coding_run"
TASK_LIST_PATH = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/tasks/git_bench/gitbench_task_list.json"
ENV_PATH = "/mnt/ceph/huacan/Code/Tasks/envs/.env"

# ======================== 工具类和工具函数 ========================

class PathManager:
    """路径管理类，处理各种路径创建和检查操作"""
    
    @staticmethod
    def generate_task_id():
        """生成随机任务ID"""
        return f'task{random.randint(1, 100)}'
    
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
        # 复制仓库
        source_repo_path = task_info['task_info']['repo_path']
        repo_name = Path(source_repo_path).name
        target_repo_path = f"{work_dir}/{repo_name}"
        
        if not os.path.exists(target_repo_path):
            os.system(f"cp -a {source_repo_path} {target_repo_path}")
        
        # 设置输入和输出路径
        target_input_path = PathManager.create_unique_dir(f"{target_repo_path}", "input_dataset")
        target_output_path = PathManager.create_unique_dir(f"{target_repo_path}", "output_result")
        
        # 复制数据集(如果有)
        data_path = task_info['task_info']['data_path']
        try:
            if data_path:
                DataProcessor.copy_dataset(data_path, target_input_path)
        except Exception as e:
            print(f"复制数据集时发生错误: {e}")
            print(traceback.format_exc())
        
        return target_output_path, target_input_path, target_repo_path

class TaskManager:
    """任务管理类，处理任务初始化、执行和结果管理"""
    
    @staticmethod
    def get_llm_config(timeout=200, temperature=0.7):
        """获取LLM配置"""
        # return {
        #     "config_list": [{
        #         "model": "qwen2.5-72b-GPTQ-Int8",
        #         "api_key": "sk-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        #         "base_url": "http://claude0openai.a.pinggy.link/v1"
        #     }],
        #     "timeout": timeout,
        #     "temperature": temperature,
        # }

        return {
            "config_list": [{
                "model": "claude-3-5-sonnet-20241022",
                "base_url": "https://api.anthropic.com/v1",
                # "api_key": os.environ["ANTHROPIC_API_KEY"]
                "api_key": "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"
            }],
            "timeout": timeout,
            "temperature": temperature,
        }        
    
    @staticmethod
    def prepare_task_description(task_info, target_output_path, target_input_path, target_repo_path):
        """根据任务信息生成任务描述"""
        task_desc = task_info['task_prompt']
        task_details = task_info['task_info']
        
        # 替换路径
        task_desc = task_desc.replace(task_details['repo_path'], target_repo_path)
        task_desc = task_desc.replace(task_details['output_dir_path'], target_output_path)
        
        # 处理输入数据信息
        if task_details['data_path']:
            try:
                input_data_info = json.loads(task_details['input_data_info'])
                for idx, input_data in enumerate(input_data_info):
                    input_data_info[idx]['path'] = input_data['path'].replace(
                        task_details['data_path'], target_input_path
                    )
                task_desc = task_desc.replace(
                    task_details['input_data_info'],
                    json.dumps(input_data_info, indent=2, ensure_ascii=False)
                )
            except Exception as e:
                print(f"替换input_data_info时发生错误: {e}")
                print(traceback.format_exc())
        else:
            task_desc = task_desc.replace(task_details['input_data_info'], '')
        
        task_desc = task_desc.replace('<output_dir_path>', target_output_path)
        print(task_desc)
        
        return f"帮我基于给定的仓库来完成以下任务:\n\n{task_desc}\n\n"
    
    @staticmethod
    def load_task_list():
        """从任务列表文件加载任务"""
        return json.load(open(TASK_LIST_PATH))
    
    @staticmethod
    def initialize_tasks(args, root_path=DEFAULT_ROOT_PATH):
        """初始化任务环境和任务列表"""
        work_task_path = PathManager.create_unique_path(root_path)
        
        # 加载任务列表并添加必要字段
        task_info_list = TaskManager.load_task_list()
        for task_id, task_info in task_info_list.items():
            task_info_list[task_id].update({
                'root_path': root_path,
                'work_task_path': work_task_path,
                'task_id': task_id
            })
        
        return task_info_list
    
    @staticmethod
    def get_task_results():
        """获取任务结果"""
        results_path = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/scripts_run/all_best_result.json"
        return json.load(open(results_path))

class AgentRunner:
    """代理运行器，负责运行代码代理执行任务"""
    
    @staticmethod
    def run_agent(task_info, retry_times=2):
        """运行Code Agent执行任务"""
        task_id = task_info['task_id']
        work_task_path = task_info['work_task_path']
        repo_path = task_info['task_info']['repo_path']
        print(f"任务: {task_id} | 仓库: {repo_path}")
        
        # 创建工作目录
        work_dir = f'{work_task_path}/{task_id}/{uuid.uuid4()}'
        os.makedirs(work_dir, exist_ok=True)
        
        # 准备环境
        target_output_path, target_input_path, target_repo_path = DataProcessor.setup_task_environment(
            task_info, work_dir
        )
        
        # 生成任务描述
        task = TaskManager.prepare_task_description(
            task_info, target_output_path, target_input_path, target_repo_path
        )
        task += "## 非常重要, 请注意: 保存的输出结果需要以output开头来命名，比如output.txt, output.wav等等, 如果存在多个文件，就以output_01, output_02, 等等来命名. 记住一定要保存在的一级子目录下(比如<'{target_output_path}/output.txt'>), 因为后续需要在该子目录下根据文件的这个字段匹配来获取结果, 进行后续的任务完成效果测试."
        
        work_dir = target_repo_path
        print(f"✅ 工作目录: {work_dir}")
        
        # 运行代码代理
        explorer = CodeExplorer(
            target_repo_path, 
            work_dir=work_dir, 
            remote_repo_path=None, 
            task_type="gitbench", 
            use_venv=True, 
            is_cleanup_venv=False, 
            llm_config=TaskManager.get_llm_config()
        )
        
        answer = explorer.code_analysis(task, max_turns=30)
        print("==== code analysis done", answer)
        time.sleep(10)
        
        # 检查是否需要重试
        if not os.path.exists(target_output_path) and retry_times > 0:
            print(f"---任务{task_id}提交失败，重试{retry_times}次---")
            return AgentRunner.run_agent(task_info, retry_times - 1)
        
        for key in ["work_dir", "target_output_path", "target_input_path", "target_repo_path"]:
            task_info[key] = eval(key)
                    
        json.dump(task_info, open(f"{work_dir}/task_info.json", "w"), indent=2, ensure_ascii=False)
        
        return answer
    
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
        task_info_list = TaskManager.initialize_tasks(args)
        
        for task_id, task_info in task_info_list.items():
            # if task_id != "DeScratch_01":
            #     continue
            print(f"开始处理任务: {task_id}")
            AgentRunner.process_single_task(task_info, args)
            
    @staticmethod
    def run_parallel(args):
        """并行执行所有任务"""
        task_info_list = TaskManager.initialize_tasks(args)
        max_workers = args.parallel_workers if hasattr(args, 'parallel_workers') else min(4, len(task_info_list))
        
        print(f"使用并行模式运行，最大工作进程数: {max_workers}...")
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for task_id, task_info in task_info_list.items():
                print(f"提交任务: {task_id}", flush=True)
                future = executor.submit(AgentRunner.process_single_task, task_info, args)
                futures[future] = task_id
            
            for future in concurrent.futures.as_completed(futures):
                task_id = futures[future]
                try:
                    future.result()
                    print(f"任务 {task_id} 已完成")
                except Exception as e:
                    print(f"任务 {task_id} 执行出错: {e}")
                    print(traceback.format_exc())

# ======================== 命令行参数和主函数 ========================

def get_args():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description="代码仓库任务执行工具")
    parser.add_argument("--retry", type=int, default=2, help="任务失败后重试次数")
    parser.add_argument("--max_repo", type=int, default=5, help="最大处理仓库数量")
    parser.add_argument("--parallel", action="store_true", help="是否使用并行模式执行任务")
    parser.add_argument("--parallel_workers", type=int, default=4, help="并行模式下的最大工作进程数")
    return parser.parse_args()

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    # 加载环境变量
    load_dotenv(ENV_PATH)
    args = get_args()
    
    if args.parallel:
        print("使用并行模式运行...")
        AgentRunner.run_parallel(args)
    else:
        print("使用非并行模式运行...")
        AgentRunner.run_sequential(args)

