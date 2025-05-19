import json



# Determine if higher or lower score is better based on medal thresholds
def is_higher_better(submission):
    if not submission:
        return True
    
    # Check the relationship between gold and silver thresholds
    if submission["gold_threshold"] > submission["median_threshold"]:
        return True  # Higher score is better
    else:
        return False  # Lower score is better

def resort_result():
    read_path = "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/tasks/res/submission/submission_20250501_183032.json"
    out_path = read_path.replace('.json', '_sorted.json')
    out_path_2 = read_path.replace('.json', '_sorted_2.json')
    print(out_path)
    
    new_output = {}
    resort_result = []
    out_json = open(out_path, 'w')
    out_json_2 = open(out_path_2, 'w')
    
    read_json = open(read_path).readlines()
    for line in read_json:
        line_dict = json.loads(line)
        score_dict = line_dict['score']
        task_id = line_dict['task_id']
        # import pdb; pdb.set_trace()
        try:
            scores = json.loads(score_dict)
            if scores['score'] is None:
                continue
            line_dict['score'] = scores
            if task_id not in new_output:
                new_output[task_id] = [line_dict]
            else:
                new_output[task_id].append(line_dict)
        except Exception as e:
            print(line)

    for task_id, lines in new_output.items():
        try:
            is_reverse = is_higher_better(lines[0]['score'])
            lines.sort(key=lambda x: x['score']['score'], reverse=is_reverse)
            
            for idx, line in enumerate(lines):
                if idx >= 2:
                    break
                print(line['work_dir'])
                out_dict = {
                    'repo_name': line['work_dir'].split('/')[-1],
                }
                out_dict.update(**line)
                resort_result.append(out_dict)
                out_json.write(json.dumps(out_dict, ensure_ascii=False) + '\n')
                out_json_2.write(json.dumps({k:v for k,v in out_dict.items() if k in ['repo_name', 'task_id']}, ensure_ascii=False) + '\n')
                
        except Exception as e:
            print(e)
            import pdb; pdb.set_trace()
    
    
if __name__ == "__main__":
    resort_result()