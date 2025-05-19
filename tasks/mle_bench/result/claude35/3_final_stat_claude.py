import json
import pandas as pd
import os
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
    
    re_run_res_path = [
        "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/tasks/res/submission/submission_20250501_183032_sorted.json",
        "/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/res/manual_run/claude3.5/merged_results_20250508_135239.json",
    ]
    all_result = []
    for path in re_run_res_path:
        try:
            for result in json.load(open(path)):
                # line = json.loads(extract_score(line))
                score = extract_score(result['cmd_output'])
                all_result.append(json.loads(score))
                # import pdb; pdb.set_trace()
        except Exception as e:
            # import pdb; pdb.set_trace()
            import traceback
            # print(traceback.format_exc())
            for res in open(path).readlines():
                # print("res: ", res)
                res = json.loads(res)
                score = res['score']
                try:
                    if isinstance(score, str):
                        score = json.loads(score)                    
                    all_result.append(score)
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
    new_all_result = {k: v for k, v in sorted(new_all_result.items(), key=lambda x: x[0])}
                
    return new_all_result


# Determine if higher or lower score is better based on medal thresholds
def is_higher_better(submissions):
    if not submissions:
        return True
    
    # Get the first submission with threshold data
    submission = submissions[0]
    
    # Check the relationship between gold and silver thresholds
    if submission["gold_threshold"] > submission["median_threshold"]:
        return True  # Higher score is better
    else:
        return False  # Lower score is better

# Find the best submission for each competition
def find_best_submissions(competitions):
    best_submissions = {}
    
    for comp_name, submissions in competitions.items():
        if not submissions:
            continue
            
        higher_better = is_higher_better(submissions)
        
        # Find the best submission
        best_score = None
        best_submission = None
        
        for submission in submissions:
            score = submission["score"]
            if score is None or not isinstance(score, (int, float)):
                if not best_score is None:
                    continue
            if best_score is None or (higher_better and score >= best_score) or (not higher_better and score <= best_score):
                best_score = score
                best_submission = submission
        
        best_submissions[comp_name] = best_submission
    
    return best_submissions

# Count medals and statistics
def count_statistics(competitions):
    stats = {
        "gold_medals": 0,
        "silver_medals": 0,
        "bronze_medals": 0,
        "total_medals": 0,
        "valid_submissions": 0,
        "submission_exists": 0,
        "above_median": 0,
        "total_submissions": 0
    }
    
    # 首先找出每个比赛的最佳提交
    best_submissions = find_best_submissions(competitions)
    
    # 只统计最佳提交的奖牌和统计数据
    for comp_name, submission in best_submissions.items():
        if submission:
            stats["gold_medals"] += 1 if submission.get("gold_medal", False) else 0
            stats["silver_medals"] += 1 if submission.get("silver_medal", False) else 0
            stats["bronze_medals"] += 1 if submission.get("bronze_medal", False) else 0
            stats["total_medals"] += 1 if submission.get("any_medal", False) else 0
            stats["valid_submissions"] += 1 if submission.get("valid_submission", False) else 0
            stats["submission_exists"] += 1 if submission.get("submission_exists", False) else 0
            stats["above_median"] += 1 if submission.get("above_median", False) else 0
            stats["total_submissions"] += 1
    
    return stats

# Create summary table for best submissions
def create_best_submissions_table(best_submissions):
    data = []
    
    for comp_name, submission in best_submissions.items():
        if submission:
            # Create a row for the dataframe
            row = {
                "competition": comp_name,
                "score": submission["score"],
                "gold_threshold": submission["gold_threshold"],
                "silver_threshold": submission["silver_threshold"],
                "bronze_threshold": submission["bronze_threshold"],
                "median_threshold": submission["median_threshold"],
                "any_medal": submission["any_medal"],
                "gold_medal": submission["gold_medal"],
                "silver_medal": submission["silver_medal"],
                "bronze_medal": submission["bronze_medal"],
                "above_median": submission["above_median"],
                "valid_submission": submission["valid_submission"],
                "submission_exists": submission["submission_exists"]
            }
            data.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    return df

# Main function to process the data
def analyze_competition_data(competitions_data):
    # Deserialize all the string JSON objects within the dictionary
    competitions = {}
    for comp_name, submissions_list in competitions_data.items():
        competitions[comp_name] = []
        for submission_str in submissions_list:
            # Parse the JSON string to a dictionary
            submission = json.loads(submission_str)
            competitions[comp_name].append(submission)
    
    # 先找出最佳提交
    best_submissions = find_best_submissions(competitions)
    
    # 计算统计信息
    stats = count_statistics(competitions)
    stats_df = pd.DataFrame({
        "Statistic": ["Gold Medals", "Silver Medals", "Bronze Medals", "Total Medals", 
                      "Valid Submissions", "Submission Exists", "Above Median", "Total Submissions"],
        "Count": [stats["gold_medals"], stats["silver_medals"], stats["bronze_medals"], 
                  stats["total_medals"], stats["valid_submissions"], 
                  stats["submission_exists"], stats["above_median"], stats["total_submissions"]]
    })
    
    # 创建最佳提交表格
    best_df = create_best_submissions_table(best_submissions)
    
    return stats_df, best_df

if __name__ == "__main__":
    # Usage example:
    all_result = cal_all_best_result()
    stats_df, best_df = analyze_competition_data(all_result)
    
    output_path = './'
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    stats_df.to_csv(os.path.join(output_path, 'stats_df.csv'), index=False)
    best_df.to_csv(os.path.join(output_path, 'best_df.csv'), index=False)
    print(stats_df)
    print(best_df)