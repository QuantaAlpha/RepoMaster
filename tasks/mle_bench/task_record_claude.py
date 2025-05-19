import json
from tasks.mle_bench.manual_list.openai_list import Result_Cal

            
def get_task_record():

    data = open("/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/tasks/res/submission/submission_20250501_183032_sorted.json").readlines()
    
    out_data = []
    for line in data:
        line_dict = json.loads(line)
        out_data.append(line_dict)
    return out_data

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


def cal_all_best_result():
    all_result = Result_Cal.run_task1 + Result_Cal.run_task2 + Result_Cal.run_task3
    all_result = [json.loads(item['score']) for item in all_result]
    
    re_run_res_path = [
        "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/manual_run/gpt4o/merged_results_20250428_083910.json",
        "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/manual_run/20250428_083536.json",
        "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/submission/submission_20250428_205342.json",
        "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/submission/submission_20250428_201936.json"
    ]
    for path in re_run_res_path:
        try:
            for result in json.load(open(path)):
                # line = json.loads(extract_score(line))
                score = extract_score(result['cmd_output'])
                all_result.append(json.loads(score))
                # import pdb; pdb.set_trace()
        except Exception as e:
            for res in open(path).readlines():
                res = json.loads(res)
                score = extract_score(res['score'])
                try:
                    all_result.append(json.loads(score))
                except Exception as e:
                    print(f"读取文件{path}时发生错误: {e} | {res}")
                    pass

    new_all_result = {}
    for result in all_result:
        competition_id = result['competition_id']
        item = {
            'score': result['score'],
            'gold_threshold': result['gold_threshold'],
            'silver_threshold': result['silver_threshold'],
            'bronze_threshold': result['bronze_threshold'],
            'median_threshold': result['median_threshold'],
            'any_medal': result['any_medal'],
            'gold_medal': result['gold_medal'],
            'silver_medal': result['silver_medal'],
            'bronze_medal': result['bronze_medal'],
            'above_median': result['above_median'],
            'submission_exists': result['submission_exists'],
            'valid_submission': result['valid_submission'],
            'submission_path': result['submission_path'],
        }
        item = json.dumps(item, ensure_ascii=False)
        if competition_id not in new_all_result:
            new_all_result[competition_id] = [item]
        else:
            if item not in new_all_result[competition_id]:
                new_all_result[competition_id].append(item)
                
    json.dump(new_all_result, open('all_best_result.json', 'w'), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # run_task1 = get_task_record()
    # print(run_task1)
    cal_all_best_result()