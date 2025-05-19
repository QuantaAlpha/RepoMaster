import json
import os

origin_data_path = "/mnt/ceph/huacan/Code/Tasks/CodeAgent/data/GitTaskBench"

# /mnt/ceph/huacan/Code/Tasks/CodeAgent/data/GitTaskBench/queries/AnimeGANv3_01/query.json

TASK_PROMPT = """## 任务描述
{task_description}

## 可用仓库
仓库名称: {repo_name}
仓库路径 (绝对): {repo_path}
理解指南: {repo_understanding_guidelines}

## 文件路径
输入文件路径和描述:
{input_data_info}

输出：
输出文件目录: {output_dir_path}, 如果只有一个文件，就以 `output` 命名; 如果存在多个以 `output_01`开始命名，格式根据需求指定。

## 补充说明
**核心目标**: 快速理解和分析代码仓库，生成并执行必要的代码或调用工具，以高效、准确地完成用户指定的任务。
"""

def get_task_list(root_path):
    
    root_query_path = os.path.join(root_path, "queries")
    root_code_path = os.path.join(root_path, "code_base")
    root_eval_path = os.path.join(root_path, "eval")
    
    task_list = {}
    task_names = os.listdir(root_query_path)
    for task_name in task_names:
        # /mnt/ceph/huacan/Code/Tasks/CodeAgent/data/GitTaskBench/queries/AnimeGANv3_01/query.json
        task_file = os.path.join(root_query_path, task_name, "query.json")
        if not os.path.exists(task_file):
            continue
        task_details = json.load(open(task_file, "r"))
        
        # 获取原始repo路径
        origin_repo_path = task_details['repositories']
        if len(origin_repo_path) != 1:
            import pdb; pdb.set_trace()
        target_repo_path = os.path.join(
            root_path, 
            origin_repo_path[0]['path'].replace("/GitTaskBench/", "")
        )
        if not os.path.exists(target_repo_path):
            print(f"not exists: {target_repo_path}")
            # import pdb; pdb.set_trace()
        
        
        # 获取原始数据路径
        input_data_info = task_details['file_paths']['input_files']
        source_data_path = input_data_info[0]['path']
        
        if all([input_file['path'] == "" for input_file in input_data_info]):
            data_path = ''
        elif '.' not in source_data_path:
            if not source_data_path.endswith('/input'):
                data_path = os.path.dirname(source_data_path)
            else:
                data_path = source_data_path
            # print(f"not file: {source_data_path}", input_data_info)
        else:
            data_path = os.path.dirname(source_data_path)
        
        for idx, input_file in enumerate(input_data_info):
            if data_path == "":
                continue
            if os.path.dirname(input_file['path']) != os.path.dirname(source_data_path):
                print(f"not matches: {input_file['path']}")
                import pdb; pdb.set_trace()
            
            input_data_info[idx]['path'] = os.path.join(
                root_path,
                input_file['path'].replace("/GitTaskBench/", "")
            )
            if not os.path.exists(input_data_info[idx]['path']):
                print(f"not exists: {input_data_info[idx]['path']}")
                input_data_info[idx]['path'].replace("/GitTaskBench/", "")
        
        if '.' not in source_data_path or data_path == '':
            print(f"not file: {source_data_path}", input_data_info)
            # import pdb; pdb.set_trace()
        
        if not data_path.endswith('/input') and data_path != '':
            import pdb; pdb.set_trace()
        
        if data_path.endswith('/input'):
            data_path = os.path.join(root_path, data_path.replace('/GitTaskBench/', ''))
            input_data_info = json.dumps(input_data_info, indent=2, ensure_ascii=False)
        else:
            data_path = ''
            input_data_info = ''
            
        task_prompt_dict = {
            "task_description": task_details['task_description'],
            "repo_name": task_details['repositories'][0]['name'],
            "repo_path": target_repo_path,
            "repo_understanding_guidelines": task_details['repositories'][0]['understanding_guidelines'],
            "data_path": data_path,
            "input_data_info": input_data_info,
            "output_dir_path": "<output_dir_path>"
        }
        task_prompt = TASK_PROMPT.format(**task_prompt_dict)
        
        task_list[task_name] = {
            "task_prompt": task_prompt,
            'task_info': task_prompt_dict,
            'task_origin_info': task_details,
        }

    return task_list

def prepare_data():
    root_data_path = "/mnt/ceph/huacan/Code/Tasks/CodeAgent/data/GitTaskBench"
    task_list = get_task_list(root_data_path)
    json.dump(task_list, open("gitbench_task_list.json", "w"), indent=2, ensure_ascii=False)
    # import pdb; pdb.set_trace()
    return task_list

if __name__ == "__main__":
    prepare_data()
