import os   
import uuid
import datetime
import random
import json
import subprocess
import time
import concurrent.futures
from utils.data_preview import generate_preview
from core.git_agent import CodeExplorer
import traceback

# ======================== 配置和工具函数 ========================

def get_llm_config(timeout: int = 200, temperature: float = 0.7):
    """获取LLM配置"""
    return {
        "config_list": [{
            "model": "qwen2.5-72b-GPTQ-Int8",
            "api_key": "sk-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "base_url": "http://claude0openai.a.pinggy.link/v1"
            # "base_url": json.load(open("/mnt/ceph/huacan/Code/Tools/LLM_service/model_qwen3_32B/share_url.json"))['gradio_share_url']
            }
        ],
        "timeout": timeout,
        "temperature": temperature,
    }

def random_uuid():
    """生成随机任务ID"""
    return 'task'+str(random.randint(1, 100))

def get_dir_size(path):
    """使用du命令获取目录大小（单位：字节）"""
    result = subprocess.run(['du', '-sb', path], capture_output=True, text=True)
    if result.returncode == 0:
        # du输出格式为: "大小 路径"，我们提取第一个数字
        return int(result.stdout.split()[0])
    return 0

def unzip_data(data_path):
    """解压数据集中的zip文件"""
    files = os.listdir(data_path)
    for file in files:
        if file.endswith(".zip"):
            os.system(f"unzip {data_path}/{file} -d {data_path}/{file.replace('.zip', '')}")

def check_code_files(repo_path):
    """检查仓库中是否存在代码文件"""
    important_files = [".py", ".ipynb"]
    ## 递归检查是否存在代码文件
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if any(file.endswith(ext) for ext in important_files):
                return True
    return False

# ======================== 数据处理相关函数 ========================

def cp_dataset(data_path, target_path):
    """复制数据集到目标路径"""
    if not os.path.exists(target_path):
        os.makedirs(target_path, exist_ok=True)
        
    files = os.listdir(data_path)
    for file in files:
        if os.path.isdir(f"{data_path}/{file}"):
            destination = f"{target_path}/{file}"
            if os.path.exists(destination):
                print(f"目标已存在，跳过: {destination}")
                continue
            print(f"ln -s {data_path}/{file} {target_path}/")
            os.system(f"ln -s {data_path}/{file} {target_path}/")
        else:
            print(f"cp -a {data_path}/{file} {target_path}/")
            os.system(f"cp -a {data_path}/{file} {target_path}/")

def cp_all_repo_data(task_info, work_dir):
    """复制仓库和数据集到工作目录"""
    # 复制仓库
    source_repo_path = task_info['task_info']['repo_path']
    target_repo_path = f"{work_dir}/{source_repo_path.split('/')[-1]}"
    if not os.path.exists(target_repo_path):
        os.system(f"cp -a {source_repo_path} {target_repo_path}")
    
    # 复制数据集
    data_path = task_info['task_info']['data_path']
    
    target_input_path = f"{target_repo_path}/input_dataset"
    while os.path.exists(target_input_path):
        target_input_path = target_input_path + '_' + str(random.randint(1, 10))
    
    try:
        if data_path != '':
            cp_dataset(data_path, target_input_path)
    except Exception as e:
        print(f"复制数据集时发生错误: {e}")
        print(traceback.format_exc())
    
    target_output_path = f"{work_dir}/output_result"
    while os.path.exists(target_output_path):
        target_output_path = target_output_path + '_' + str(random.randint(1, 10))
    os.makedirs(target_output_path, exist_ok=True)
    
    return target_output_path, target_input_path, target_repo_path

def get_gitbench_task(task_info, target_output_path, target_input_path, target_repo_path):
    """根据任务信息生成任务描述"""
    task_desc = task_info['task_prompt']
    task_details = task_info['task_info']
    
    task_desc = task_desc.replace(task_details['repo_path'], target_repo_path)
    task_desc = task_desc.replace(task_details['output_dir_path'], target_output_path)
    if task_details['data_path'] != '':
        input_data_info = json.loads(task_details['input_data_info'])
        try:
            for idx, input_data in enumerate(input_data_info):
                input_data_info[idx]['path'] = input_data['path'].replace(task_details['data_path'], target_input_path)
            task_desc = task_desc.replace(task_details['input_data_info'], json.dumps(input_data_info, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"替换input_data_info时发生错误: {e}")
            print(traceback.format_exc())
            import pdb; pdb.set_trace()
    else:
        task_desc = task_desc.replace(task_details['input_data_info'], '')
    
    task_desc = task_desc.replace('<output_dir_path>', target_output_path)
    print(task_desc)
    task = f"帮我基于给定的仓库来完成以下任务:\n\n{task_desc}\n\n"
    return task

# ======================== 任务执行相关函数 ========================

def run_agent(task_info, retry_times=2):
    """运行Code Agent执行任务"""
    task_id = task_info['task_id']
    work_task_path = task_info['work_task_path']
    repo_path = task_info['task_info']['repo_path']
    print(f"任务: {task_id} | 仓库: {repo_path}")
    
    work_dir = f'{work_task_path}/{task_id}/{uuid.uuid4()}'
    
    task_info['work_dir'] = work_dir    
    
    os.makedirs(work_dir, exist_ok=True)
    print(work_dir)
    
    target_output_path, target_input_path, target_repo_path = cp_all_repo_data(task_info, work_dir)
    task = get_gitbench_task(task_info, target_output_path, target_input_path, target_repo_path)
    
    # Code Agent running
    explorer = CodeExplorer(target_repo_path, work_dir=work_dir, remote_repo_path=None, task_type="gitbench", use_venv=True, is_cleanup_venv=False, llm_config=None)
    answer = explorer.code_analysis(task, max_turns=30)
    print("==== code analysis done", answer)
    time.sleep(10)
    
    if not os.path.exists(target_output_path) and retry_times > 0:
        print(f"---任务{task_id}提交失败，重试{retry_times}次---")
        return run_agent(task_info, retry_times - 1)

def process_single_repo(task_info, args):
    """处理单个仓库任务"""
    task_id = task_info['task_id']
    try:
        result = run_agent(task_info, retry_times=args.retry)
    except Exception as e:
        print(f"=== 任务{task_id}提交失败: {e}")
        print(traceback.format_exc())
        # result = write_submission(task_info, f'--failed: 任务{task_id}提交失败 | {e}--')

# ======================== 任务初始化和管理函数 ========================

def prepare_data(root_path, work_task_path):
    """准备任务数据"""
    filter_topk_repo_path = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/tasks/git_bench/gitbench_task_list.json"
    task_info_list = json.load(open(filter_topk_repo_path))
    for task_id, task_info in task_info_list.items():
        task_info_list[task_id]['root_path'] = root_path
        task_info_list[task_id]['work_task_path'] = work_task_path
        task_info_list[task_id]['task_id'] = task_id
    return task_info_list

def task_init(args):
    """初始化任务环境"""
    # root_path = os.path.dirname(os.path.dirname(__file__))
    root_path = "/mnt/ceph/huacan/Data/coding_run"
    
    work_task_path = f'{root_path}/{random_uuid()}'
    while os.path.exists(work_task_path):
        work_task_path = f'{root_path}/{random_uuid()}'
    
    task_info_list = prepare_data(root_path, work_task_path)
    
    return task_info_list

def run_task_sequential(args):
    """顺序执行所有任务"""
    task_info_list = task_init(args)
    
    # 顺序处理每个任务
    for task_id, task_info in task_info_list.items():
        print(f"开始处理任务: {task_id}")
        try:
            process_single_repo(task_info, args)
            print(f"任务 {task_id} 处理完成")
        except Exception as e:
            print(f"处理任务 {task_id} 时发生异常: {e}")
            print(traceback.format_exc())

def finish_task():
    """获取任务结果"""
    data = json.load(open("/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/scripts_run/all_best_result.json"))
    return data

# ======================== 命令行参数和主函数 ========================

def get_args():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry", type=int, default=2)
    parser.add_argument("--max_repo", type=int, default=5)
    # parser.add_argument("--sequential", action="store_true", help="使用非并行模式运行，用于调试")
    return parser.parse_args()

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("/mnt/ceph/huacan/Code/Tasks/envs/.env")
    args = get_args()
    
    print("使用非并行模式运行...")
    run_task_sequential(args)

