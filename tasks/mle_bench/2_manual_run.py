import os
import glob
import subprocess
import json
import datetime
import multiprocessing
import random
import time
import traceback
from tasks.mle_bench.task_record_claude import get_task_record

def find_python_files(directory):
    """查找目录下的所有Python文件"""
    return glob.glob(os.path.join(directory, "*.py"))

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

def execute_command(cmd, env=None):
    """执行命令并返回输出结果"""
    try:
        result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        # print(f"stderr: {result.stderr}")
        # print(f"stdout: {result.stdout}")
        submit_score = result.stderr.decode('utf-8')
        submit_score = extract_score(submit_score)        
        return submit_score
    except subprocess.CalledProcessError as e:
        return f"命令执行失败: {e}\n{e.stderr.decode('utf-8')}"

def check_result_exist():
    for task in get_task_record():
        work_dir = task['work_dir'] if 'work_dir' in task else os.path.dirname(task['repo_path'])
        if not os.path.exists(work_dir):
            print(task['repo_path'], flush=True)
            import pdb;pdb.set_trace()
            continue
        print(work_dir, flush=True)
    

def get_output_dir():
    """获取输出目录"""
    # return "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/manual_run/gpt4o"
    return "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/manual_run/claude3.5"

def save_task_result(task_result):
    """保存单个任务的结果到对应的任务文件夹"""
    try:
        # 创建输出主目录
        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建任务特定的子目录
        task_id = task_result.get("task_id", "unknown_task")
        task_dir = os.path.join(output_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 使用时间戳和进程ID创建唯一文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        process_id = os.getpid()
        gpu_id = task_result.get("gpu_id", "unknown")
        result_file = os.path.join(task_dir, f"{timestamp}_{process_id}_gpu{gpu_id}.json")
        
        # 保存结果到文件
        with open(result_file, 'w') as f:
            json.dump(task_result, f, indent=2, ensure_ascii=False)
        
        print(f"任务结果已保存到: {result_file}", flush=True)
        return result_file
    except Exception as e:
        print(f"保存任务结果时出错: {str(e)}", flush=True)
        print(traceback.format_exc(), flush=True)
        return None

def process_task(task):
    try:
        # 处理单个任务并保存结果
        result = process_task_single(task)
        
        # 保存单个任务结果
        if result:
            save_task_result(result)
        
        return result
    except Exception as e:
        error_result = {
            "task_id": task.get("task_id", "unknown"),
            "repo_path": task.get("repo_path", "unknown"),
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        save_task_result(error_result)
        return error_result

def process_task_single(task):
    """处理单个任务"""
    # 使用task_index来确定GPU分配
    # 这个task_index会在run_tasks函数中传入
    gpu_id = task.get('task_index', 0) % 8  # 使用任务索引对8取模来分配GPU
    
    task_env = os.environ.copy()
    task_env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    
    task_result = {"task_id": task["task_id"], "repo_path": task["repo_path"], "gpu_id": gpu_id}
    
    print(f"处理任务: {task['task_id']} 使用GPU: {gpu_id}", flush=True)
    
    work_dir = task['work_dir'] if 'work_dir' in task else os.path.dirname(task['repo_path'])
    
    # 切换到repo_path目录
    try:
        os.chdir(work_dir)
        task_result["change_dir"] = "成功"
    except Exception as e:
        task_result["change_dir"] = f"失败: {str(e)}"
        return task_result
    
    # 查找Python文件
    python_files = find_python_files(work_dir)
    task_result["python_files"] = [str(f) for f in python_files]  # 确保所有列表元素是字符串类型
    
    # 选择要执行的Python文件
    py_file_to_run = None
    if any(os.path.basename(f) == "train_and_predict.py" for f in python_files):
        py_file_to_run = "train_and_predict.py"
    elif python_files:
        py_file_to_run = os.path.basename(python_files[0])
    
    if py_file_to_run:
        # 执行Python文件
        py_cmd = f"python3 {py_file_to_run}"
        task_result["python_cmd"] = py_cmd
        py_output = execute_command(py_cmd, env=task_env)
        task_result["python_output"] = py_output
    
    # 执行cmd命令
    if task.get("cmd", ""):
        cmd = task["cmd"]
    else:
        cmd = f"mlebench grade-sample {task['repo_path']}/result_submission.csv {task['task_id']}"
    
    task_result["cmd"] = cmd
    cmd_output = execute_command(cmd, env=task_env)
    print(f"cmd output: {cmd_output}", flush=True)
    task_result["cmd_output"] = cmd_output
    task_result['repo_path'] = task['repo_path']
    task_result['work_dir'] = work_dir
    task_result['timestamp'] = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return task_result

def collect_all_results():
    """收集所有任务的结果并合并到一个文件中"""
    output_dir = get_output_dir()
    all_results = []
    
    # 遍历所有任务目录
    for task_dir in glob.glob(os.path.join(output_dir, "*")):
        if os.path.isdir(task_dir):
            # 获取该任务目录下的所有结果文件
            result_files = glob.glob(os.path.join(task_dir, "*.json"))
            for result_file in result_files:
                try:
                    with open(result_file, 'r') as f:
                        result = json.load(f)
                        all_results.append(result)
                except Exception as e:
                    print(f"读取结果文件 {result_file} 时出错: {str(e)}", flush=True)
    
    # 保存合并后的结果
    if all_results:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        merged_file = os.path.join(output_dir, f"merged_results_{timestamp}.json")
        with open(merged_file, 'w') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"所有结果已合并保存到: {merged_file}", flush=True)
        return merged_file
    else:
        print("没有找到任何结果文件", flush=True)
        return None

def run_tasks():
    """并行运行所有任务并保存结果"""
    # 检查任务结果是否存在
    # check_result_exist()
    
    # 为每个任务分配索引，用于GPU分配
    tasks_with_index = []
    for i, task in enumerate(get_task_record()):
        task_with_index = task.copy()
        task_with_index['task_index'] = i
        tasks_with_index.append(task_with_index)
    
    # 创建进程池
    pool = multiprocessing.Pool(processes=min(8, len(tasks_with_index)))  # 最多使用8个进程同时运行
    
    # 启动任务
    results = []
    for result in pool.imap_unordered(process_task, tasks_with_index):
        if result:
            results.append(result)
            print(f"已完成任务: {result.get('task_id', 'unknown')} 使用GPU: {result.get('gpu_id', 'unknown')}", flush=True)

    # 关闭进程池
    pool.close()
    pool.join()
    
    # 合并所有结果并保存
    merged_file = collect_all_results()
    
    print(f"所有任务已完成，结果已合并到: {merged_file}", flush=True)

if __name__ == "__main__":
    
    # step1: manual change the epoch number in the train_and_predict.py
    # check_result_exist()
    
    # step2: run the script
    run_tasks()
    