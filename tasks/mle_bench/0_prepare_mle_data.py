import json
import os

def prepare_data():
    filter_topk_repo_path = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/git_repos/_mle_bench_repo/topk_repo_list.json"
    filter_topk_repo_list = json.load(open(filter_topk_repo_path))
    prepare_dataset = {}
    for task_id, task_info in filter_topk_repo_list.items():
        repo_list = task_info['results']
        data_path = f"/mnt/ceph/huacan/Code/Tasks/CodeAgent/data/mle-bench-data/data/{task_id}/prepared/public"
        os.system(f"mlebench prepare -c {task_id}")
    return prepare_dataset

if __name__ == "__main__":
    prepare_data()