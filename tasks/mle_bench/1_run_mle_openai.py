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

def get_llm_config(timeout=200, temperature=0.7):
    """获取LLM配置"""

    # 配置 LLM
    return {
        "config_list": [
            {
                "model": "llama-3.1-70b",
                "api_key": "sk-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                # "base_url": ChatHandler().service_urls,
                "base_url": "http://claude0openai.a.pinggy.link/v1",
                # "response_format": {"type": "json_object"}
                "max_tokens": 20000
            }
        ],
        "timeout": timeout,
        "temperature": temperature,
    }    

    return {
        "config_list": [{
            "model": "claude-3-7-sonnet-20250219",
            "base_url": "https://api.anthropic.com/v1",
            # "api_key": os.environ["ANTHROPIC_API_KEY"]
            "api_key": "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"
        }],
        "timeout": timeout,
        "temperature": temperature,
    }


def random_uuid():
    return 'task'+str(random.randint(1, 100))

def get_mle_task(task_name: str, data_path: str):
    task_desc = open(f"{data_path}/description.md").read()
    
    # 将数据示例格式化为字符串
    examples_str = f"\n\n# 数据集地址：{data_path}\n"
    
    examples_str += f"""<data_preview>
{generate_preview(data_path)}
</data_preview>
"""

    task = f"帮我基于给定的仓库来完成以下任务:\n任务描述：\nKaggle Task: {task_name}\n{task_desc}{examples_str}\n"
    return task

def get_dir_size(path):
    """使用du命令获取目录大小（单位：字节）"""
    result = subprocess.run(['du', '-sb', path], capture_output=True, text=True)
    if result.returncode == 0:
        # du输出格式为: "大小 路径"，我们提取第一个数字
        return int(result.stdout.split()[0])
    return 0

def write_submission(submission_path, work_dir, task_id, repo_path, data_path, score, cmd=''):
    result = {
        "task_id": task_id,
        "score": score,
        "repo_path": repo_path,
        "data_path": data_path,
        "cmd": cmd,
        "work_dir": work_dir,
    }
    with open(submission_path, "a") as f:
        f.write(f"{json.dumps(result, ensure_ascii=False)}\n")
    json.dump(result, open(f"{work_dir}/submission.json", "w"), ensure_ascii=False, indent=2)
    return result

def extract_score(result):
    # 使用正则表达式提取JSON
    import re
    json_pattern = re.compile(r'{.*}', re.DOTALL)
    match = json_pattern.search(result)
    
    if match:
        try:
            submission_json_str = match.group(0)
            return submission_json_str
        except Exception as e:
            print(f"提取score时发生错误: {e}")
    return str(result)

def cp_dataset(data_path, target_path):
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

def run_agent(work_dir, task_id, source_repo_path, data_path, submission_path, root_path, retry_times=2):
    
    # work_dir = f"{work_dir}"
    result_path = f"{work_dir}/result_submission.csv"
    
    os.makedirs(work_dir, exist_ok=True)

    # 测试代码分析
    print(work_dir)
    repo_path = f"{work_dir}/{source_repo_path.split('/')[-1]}"
    if not os.path.exists(repo_path):
        os.system(f"cp -a {source_repo_path} {repo_path}")
    
    remote_repo_path=f"/workspace/{repo_path.split('/')[-1]}"    
    
    data_target_path = f"{repo_path}/data"
    while os.path.exists(data_target_path):
        data_target_path = data_target_path + '_' + str(random.randint(1, 10))
    
    try:
        cp_dataset(data_path, data_target_path)
    except Exception as e:
        print(f"复制数据集时发生错误: {e}")
        print(traceback.format_exc())
    
    # small_data_path = f"{work_dir}/data_small"
    # create_small_data(data_path, small_data_path)
    if os.path.exists(data_path):
        # 计算数据集文件目录大小
        dir_size = get_dir_size(data_path)
        if dir_size > 1024 * 1024 * 1024 * 5:
            epoch = 2
        elif dir_size > 1024 * 1024 * 1024 * 1:
            epoch = 4
        elif dir_size > 1024 * 1024 * 500:
            epoch = 10
        else:
            epoch = 15
        epoch = 15
        print(f"数据集大小: {dir_size} | {data_path}", flush=True)
        print(f"训练{epoch}个epoch", flush=True)

    task = get_mle_task(task_id, data_target_path)
    task += f"""
## 注意: 只需要训练{epoch}个epoch，不要训练太久。
## 注意: 模型训练需要用GPU，请使用GPU训练。判断device：device = torch.device('cuda' if torch.cuda.is_available() else 'cpu'), model.to(device)。
## 注意: 不要使用TensorFlow（因为目前环境是pytorch），请你转成pytorch的模型框架进行训练和推理, 需要提升训练的效率。
## 注意: 训练和解码的文件名保存为train_and_predict.py,路径为{work_dir}/train_and_predict.py。
## 注意: 需要提交的结果文件保存为result_submission.csv, 路径为{work_dir}/result_submission.csv。请用测试函数检查结果文件是否存在和格式正确。
    """
    
    # Code Agent running
    explorer = CodeExplorer(repo_path, work_dir=work_dir, remote_repo_path=None, task_type="kaggle", use_venv=True, is_cleanup_venv=False, llm_config=None)
    answer = explorer.code_analysis(task, max_turns=30)
    print("==== code analysis done", answer)
    time.sleep(10)

    if not os.path.exists(result_path):
        if os.path.exists(f"{work_dir}/data/result_submission.csv"):
            result_path = f"{work_dir}/data/result_submission.csv"
    
    if not os.path.exists(result_path) and retry_times > 0:
        print(f"---任务{task_id}提交失败，重试{retry_times}次---")
        return run_agent(work_dir, task_id, repo_path, data_path, submission_path, root_path, retry_times - 1)
    
    print(f"---结果文件: {result_path}---")

    cmd = f"export PYTHONPATH=$PYTHONPATH:{repo_path}\n"
    # cmd2 = cmd1 + f"python3 {work_dir}/train_and_predict.py\n"
    
    cmd += f"mlebench grade-sample {result_path} {task_id}\n"
    os.system(f"echo {cmd} >> {work_dir}/run_all_cmd.sh")
    
    if os.path.exists(result_path):
        submit_score = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        submit_score = extract_score(submit_score.stderr)
        print(f"---任务提交结果: {submit_score}---")
        result = write_submission(submission_path, work_dir, task_id, repo_path, data_path, submit_score, cmd=cmd)
        return result
    else:
        print(f"---任务{task_id}运行失败---, 结果文件不存在 repo_path: {repo_path}")
        result = write_submission(submission_path, work_dir, task_id, repo_path, data_path, f"---failed: 任务{task_id}运行失败---", cmd=cmd)
        return result
    
def unzip_data(data_path):
    files = os.listdir(data_path)
    for file in files:
        if file.endswith(".zip"):
            os.system(f"unzip {data_path}/{file} -d {data_path}/{file.replace('.zip', '')}")

def prepare_data():
    filter_topk_repo_path = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/git_repos/_mle_bench_repo/topk_repo_list.json"
    filter_topk_repo_list = json.load(open(filter_topk_repo_path))
    prepare_dataset = {}
    for task_id, task_info in filter_topk_repo_list.items():
        
        repo_list = task_info['results']
        data_path = f"/mnt/ceph/huacan/Code/Tasks/CodeAgent/data/mle-bench-data/data/{task_id}/prepared/public"
        # task = get_mle_task(task_id, data_path)
        if not os.path.exists(data_path):
            print(f"数据集{task_id}不存在")
            continue
        if not os.path.exists(f"{data_path}/description.md"):
            print(f"数据集{task_id}不存在description.md")
            continue
        # unzip_data(data_path)
        prepare_dataset[task_id] = {
            'repo_list': repo_list,
            'data_path': data_path
        }
    return prepare_dataset

def check_code_files(repo_path):
    important_files = [".py", ".ipynb"]
    ## 递归检查是否存在代码文件
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if any(file.endswith(ext) for ext in important_files):
                return True
    return False

def process_single_repo(repo_path, task_id, data_path, work_task_path, submission_path, root_path, args):
    """
    处理单个仓库的逻辑
    """
    repo_name = '_'.join(repo_path.split('/')[-2:])
    work_dir = f'{work_task_path}/{task_id}/{uuid.uuid4()}'
    while os.path.exists(work_dir):
        work_dir = f'{work_task_path}/{task_id}/{uuid.uuid4()}'
    
    print(f"任务: {task_id} | 仓库: {repo_path}")
    if not check_code_files(repo_path):
        print(f"仓库{repo_path}不存在代码文件")
        result = write_submission(submission_path, work_dir, task_id, repo_path, data_path, f'--failed: 仓库{repo_path}不存在代码文件--')
        return False
    try:
        result = run_agent(work_dir, task_id, repo_path, data_path, submission_path, root_path, retry_times=args.retry)
        return True
    except Exception as e:
        print(f"=== 任务{task_id}提交失败: {e}")
        print(traceback.format_exc())
        result = write_submission(submission_path, work_dir, task_id, repo_path, data_path, f'--failed: 任务{task_id}提交失败 | {e}--')
        return False

def finish_task():
    data = json.load(open("/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/scripts_run/all_best_result.json"))
    return data

def process_task(task_id, task_info, work_task_path, submission_path, root_path, args):


    repo_list = task_info['repo_list']
    data_path = task_info['data_path']
    task = get_mle_task(task_id, data_path)
    
    repo_list = [repo for repo in repo_list if check_code_files(repo['repo_path'])][:args.max_repo]
    
    for repo in repo_list:
        process_single_repo(repo['repo_path'], task_id, data_path, work_task_path, submission_path, root_path, args)

def get_run_mle_base(args):
    """run_mle的基础函数，包含共同的初始化逻辑"""
    # root_path = os.path.dirname(os.path.dirname(__file__))
    root_path = "/mnt/ceph/huacan/Data/coding_run"
    submission_path = f"{root_path}/res/submission"
    os.makedirs(submission_path, exist_ok=True)
    
    submission_path = f"{submission_path}/submission_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    work_task_path = f'{root_path}/{random_uuid()}'
    while os.path.exists(work_task_path):
        work_task_path = f'{root_path}/{random_uuid()}'
    
    prepare_dataset = prepare_data()
    
    return root_path, submission_path, work_task_path, prepare_dataset

def run_mle_parallel(args):
    """并行版本的run_mle函数"""
    root_path, submission_path, work_task_path, prepare_dataset = get_run_mle_base(args)
    
    # 设置任务级别并行度为3
    max_workers = 8
    
    # 使用线程池并行处理任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {
            executor.submit(
                process_task, 
                task_id, 
                task_info, 
                work_task_path, 
                submission_path, 
                root_path, 
                args
            ): task_id for task_id, task_info in prepare_dataset.items()
        }
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            task_id = futures[future]
            try:
                future.result()
                print(f"任务 {task_id} 处理完成")
            except Exception as e:
                print(f"处理任务 {task_id} 时发生异常: {e}")

def run_mle_sequential(args):
    """顺序版本的run_mle函数，使用for循环处理任务"""
    root_path, submission_path, work_task_path, prepare_dataset = get_run_mle_base(args)
    
    # 顺序处理每个任务
    for task_id, task_info in prepare_dataset.items():
        # if task_id not in ["histopathologic-cancer-detection"]:
        #     continue
        # if task_id in ["AI4Code"]:
        #     continue
        print(f"开始处理任务: {task_id}")
        try:
            process_task(task_id, task_info, work_task_path, submission_path, root_path, args)
            print(f"任务 {task_id} 处理完成")
        except Exception as e:
            print(f"处理任务 {task_id} 时发生异常: {e}")
            print(traceback.format_exc())

def test_single_task_repo(task_id, args, repo_path=None):
    """
    简单测试单个任务和单个仓库
    
    参数:
    task_id: 任务ID，如"AI4Code"
    repo_path: 仓库路径
    """
    
    root_path, submission_path, work_task_path, prepare_dataset = get_run_mle_base(args)
    
    task_info = prepare_dataset[task_id]
    repo_list = task_info['repo_list']
    data_path = task_info['data_path']
    
    if repo_path is not None:
        if not check_code_files(repo_path):
            print(f"仓库{repo_path}不存在代码文件")
            return
        process_single_repo(repo_path, task_id, data_path, work_task_path, submission_path, root_path, args)
        return
    
    repo_list = [repo for repo in repo_list if check_code_files(repo['repo_path'])][:args.max_repo]
    
    for repo in repo_list:
        process_single_repo(repo['repo_path'], task_id, data_path, work_task_path, submission_path, root_path, args)
    
    print(f"任务 {task_id} 处理完成") 
    
def get_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry", type=int, default=2)
    parser.add_argument("--max_repo", type=int, default=4)
    # parser.add_argument("--sequential", action="store_true", help="使用非并行模式运行，用于调试")
    return parser.parse_args()

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("/mnt/ceph/huacan/Code/Tasks/envs/.env")
    args = get_args()
    
    if 1:
        print("使用非并行模式运行...")
        run_mle_sequential(args)
    elif 0:
        print("使用并行模式运行...")
        run_mle_parallel(args)
    else:
        test_single_task_repo(
            "denoising-dirty-documents", 
            args, 
            repo_path="/mnt/ceph/huacan/Code/Tasks/CodeAgent/Tool-Learner/git_search/res/repositories/denoising-dirty-documents/mpoegel/Denoising-Dirty-Documents"
        )
