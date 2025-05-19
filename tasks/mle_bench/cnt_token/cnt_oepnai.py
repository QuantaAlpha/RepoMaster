import os
import copy
import json
import tiktoken
import subprocess
import re
from collections import defaultdict

def find_files_with_string(directory, target_string):
    """查找目录下包含指定字符串的所有文件"""
    print(f"正在搜索包含 '{target_string}' 的文件...")
    
    # 使用subprocess运行grep命令查找文件
    cmd = f"find {directory} -type f -exec grep -l \"{target_string}\" {{}} \\;"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"搜索出错: {result.stderr}")
        return []
    
    # 返回文件列表
    files = result.stdout.strip().split('\n')
    # 过滤掉空行
    files = [f for f in files if f]
    
    print(f"找到 {len(files)} 个文件")
    return files

def find_files_by_pattern(directory, pattern):
    """查找目录下符合指定模式的所有文件"""
    print(f"正在搜索符合模式 '{pattern}' 的文件...")
    
    # 使用subprocess运行find命令查找文件
    cmd = f"find {directory} -type f -name \"{pattern}\""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"搜索出错: {result.stderr}")
        return []
    
    # 返回文件列表
    files = result.stdout.strip().split('\n')
    # 过滤掉空行
    files = [f for f in files if f]
    
    print(f"找到 {len(files)} 个文件")
    return files

def find_task_trace_files(base_dir, task_id=None, date_pattern=None, specific_path=None):
    """查找特定任务和日期模式的trace文件
    
    参数:
        base_dir: 基础搜索目录
        task_id: 任务ID，如"task77"
        date_pattern: 日期模式，如"2025-05"
        specific_path: 特定路径部分，如"plant-pathology-2020-fgvc7"
    """
    # 构建搜索路径
    if task_id:
        path_pattern = f"{base_dir}/{task_id}"
        if specific_path:
            path_pattern = f"{path_pattern}/{specific_path}"
    else:
        path_pattern = base_dir
    
    # 构建文件名模式
    file_pattern = "trace_"
    if date_pattern:
        file_pattern += f"{date_pattern}-*.txt"
    else:
        file_pattern += "*.txt"
    
    print(f"搜索路径: {path_pattern}")
    print(f"文件模式: {file_pattern}")
    
    # 使用find命令搜索
    # 先查找所有trace文件
    find_cmd = f"find {path_pattern} -type f -name 'trace_*.txt'"
    
    # 然后使用grep过滤特定日期模式
    if date_pattern:
        cmd = f"{find_cmd} | grep '{file_pattern}'"
    else:
        cmd = find_cmd
    
    print(f"执行命令: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0 and result.returncode != 1:  # grep没找到匹配项时返回1
        print(f"搜索出错: {result.stderr}")
        return []
    
    # 返回文件列表
    files = result.stdout.strip().split('\n')
    # 过滤掉空行
    files = [f for f in files if f]
    
    print(f"找到 {len(files)} 个文件")
    return files

def split_message(chat_history):
    """将对话历史按照问答对拆分"""
    message_list = []
    tmp_list = []
    for message in chat_history:
        tmp_list.append(message)
        if message['role'] != 'user':
            if len(tmp_list) > 0:
                message_list.append(copy.deepcopy(tmp_list))

    return message_list

def count_tokens(files):
    """计算文件中的token数量，基于test_task_score.py中的cal_token函数"""
    print("开始计算token...")
    
    encoding = tiktoken.encoding_for_model('gpt-4o')  # 使用与test_task_score.py相同的模型
    all_tokens = []
    files_info = []
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    
                    # 使用与test_task_score.py相同的split_message方法
                    message_list = split_message(data)
                    
                    # 将消息列表转换为JSON字符串并计算token
                    json_str = json.dumps(message_list)
                    tokens = encoding.encode(json_str)
                    token_count = len(tokens)
                    
                    all_tokens.append(token_count)
                    files_info.append({
                        'file': file_path,
                        'tokens': token_count
                    })
                    
                    print(f"文件: {file_path}, Token数: {token_count}")
                except json.JSONDecodeError:
                    print(f"无法解析JSON文件: {file_path}")
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {str(e)}")
    
    # 按test_task_score.py中的方式计算平均token
    if all_tokens:
        # 排序并去除最大的两个值，与test_task_score.py一致
        all_tokens = sorted(all_tokens)
        avg_tokens = sum(all_tokens) / len(all_tokens)
        
        # 按token数量排序文件信息
        files_info.sort(key=lambda x: x['tokens'], reverse=True)
        
        return {
            'total_files': len(all_tokens),
            'avg_tokens': avg_tokens,
            'all_tokens': all_tokens,
            'files_info': files_info
        }
    else:
        return {
            'total_files': 0,
            'avg_tokens': 0,
            'all_tokens': [],
            'files_info': []
        }

def cnt_token_by_trace(files, output_file):

    # 计算token数量
    stats = count_tokens(files)
    
    # 输出统计结果
    print("\n统计结果:")
    print(f"总文件数: {stats['total_files']}")
    print(f"平均Token数: {stats['avg_tokens']:.2f}")
    
    # 输出前10个最大token数的文件
    print("\n前10个最大token数的文件:")
    for i, file_info in enumerate(stats['files_info'][:10]):
        print(f"{i+1}. {file_info['file']} - {file_info['tokens']} tokens")
    
    # 保存结果到JSON文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"\n统计结果已保存到: {output_file}")    

def process_original_search(directory, target_string):
    """执行原有的搜索和token计算流程"""
    print(f"开始在 {directory} 中查找包含 '{target_string}' 的文件...")
    
    # 查找包含目标字符串的文件
    files = find_files_with_string(directory, target_string)
    
    if not files:
        print("未找到匹配的文件")
        return
    
    output_file = "token_stats_mle_bench_openai.json"
    cnt_token_by_trace(files, output_file)

def search_trace_files(base_dir, task_id, date_pattern):
    """查找符合trace_2025-05格式的文件"""
    print(f"\n开始在 {base_dir} 中查找符合 'trace_{date_pattern}' 格式的文件...")
    
    # 使用find命令查找文件
    pattern = f"trace_{date_pattern}*.txt"
    cmd = f"find {base_dir}/{task_id} -maxdepth 3 -type f -name '{pattern}'"
    print(f"执行命令: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"搜索出错: {result.stderr}")
        return []
    
    # 返回文件列表
    files = result.stdout.strip().split('\n')
    # 过滤掉空行
    files = [f for f in files if f]
    
    if files:
        print(f"\n找到 {len(files)} 个文件:")
        for f in files:
            print(f)
    else:
        print(f"\n未找到符合 'trace_{date_pattern}' 格式的文件")
    
    return files

def process_trace_files():
    # 第二部分：查找符合trace_2025-05格式的文件
    trace_dir = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/coding_run"
    task_id = "task77"
    date_pattern = "2025-05"
    all_files = []
    for task_id in ["mle_0514_101638"]:
        all_files.extend(search_trace_files(trace_dir, task_id, date_pattern))
    cnt_token_by_trace(all_files, "token_stats_mle_bench_deepseek.json")

def main():
    # 原始功能：查找包含目标字符串的文件并计算token
    directory = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/trace"
    # target_string = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/coding/task23"  # openai
    target_string = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/tasks/coding/task20"  # claude
    
    # 第一部分：执行原有的搜索和token计算流程
    process_original_search(directory, target_string)
    
    # 第二部分：查找符合trace_2025-05格式的文件
    # process_trace_files()

def test_count_tokens():
    files = ["/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/coding_run/mle_0514_101638/jigsaw-toxic-comment-classification-challenge/afa8b3b1-8291-4d94-897c-78b23ed3bf3c/trace_2025-05-14_23-11-48.txt"]
    with open(files[0], 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 使用与test_task_score.py相同的split_message方法
    message_list = split_message(data)
    import pdb; pdb.set_trace()
    
    encoding = tiktoken.encoding_for_model('gpt-4o') 
    # 将消息列表转换为JSON字符串并计算token
    json_str = json.dumps(message_list)
    tokens = encoding.encode(json_str)
    token_count = len(tokens)
    print(token_count)
if __name__ == "__main__":
    main()
    # test_count_tokens()
