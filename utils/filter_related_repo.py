import json
import os
from core.code_explorer_tools import GlobalCodeTreeBuilder
from core.code_utils import llm_generte_response, get_code_abs_token, parse_llm_response
import concurrent.futures
import threading
from tqdm import tqdm

class RepoFilter:
    def __init__(self, repo_path, max_tokens=10000):
        self.repo_path = repo_path
        self.max_tokens = max_tokens
        
        self.builder = None
        self.important_modules_str = None # 用于存储 important_modules 字符串
        self._build_new_tree()

    def _build_new_tree(self):
        """构建新的代码树并生成重要模块摘要"""
        print(f"正在分析代码仓库: {self.repo_path}")
        if not os.path.exists(self.repo_path):
            print(f"仓库 {self.repo_path} 不存在")
            return
        try:
            self.builder = GlobalCodeTreeBuilder(
                self.repo_path,
            )
            self.builder.parse_repository()
            self.code_tree = self.builder.code_tree
            important_modules_data = self.builder.generate_llm_important_modules(max_tokens=self.max_tokens, is_file_summary=False)
            # 将 important_modules 转换为字符串并存储
            if isinstance(important_modules_data, (dict, list)):
                self.important_modules_str = json.dumps(important_modules_data, ensure_ascii=False, indent=2)
            else:
                self.important_modules_str = str(important_modules_data)

        except Exception as e:
            print(f"分析仓库 {self.repo_path} 时出错: {e}")
            self.builder = None # 确保 builder 在出错时为 None
            self.important_modules_str = None
    

def fisrt_step_filter_related_repo(filter_related_path):
    
    git_search_path = '/mnt/ceph/huacan/Code/Tasks/CodeAgent/Tool-Learner/git_search/res/2_git_clone_record.json'
    filter_related_repo_list = {}
    
    for task_id, task_info in json.load(open(git_search_path, 'r')).items():
        task = task_info['task']
        repo_list = task_info['results']
        filter_related_repo_list[task_id] = {
            'task': task,
            'results': []
        }
        for repo in repo_list:
            repo_path = repo['repo_path']
            is_related = RepoFilter(repo_path).related_repo_filter(task)
            if is_related:
                filter_related_repo_list[task_id]['results'].append(repo)
    json.dump(filter_related_repo_list, open(filter_related_path, 'w'), ensure_ascii=False, indent=2)
    
def rate_repos_by_dimensions(task, repos_group, try_times=3):
    """对仓库进行多维度评分"""
    
    system_prompt = """你是一位专业的代码评审专家，擅长分析代码仓库与特定任务的相关性。
你的任务是：仔细阅读用户提供的 Kaggle 任务描述和该代码仓库的核心文件信息。
基于这些信息，判断该代码仓库是否包含有助于解决该 Kaggle 任务的代码（例如，模型架构、训练流程、数据处理、特征工程等）。
评估以下代码仓库与任务的相关性，从多个维度进行0或1打分:

请从以下维度为每个仓库评分(0或1):
1. 算法匹配度：代码算法是否与任务需求匹配
2. 领域适用性：代码是否适用于该任务领域
3. 数据处理能力：是否有完善的数据处理功能
4. 模型实现质量：模型实现是否高质量
5. 代码可读性：代码是否清晰易读
6. 结构组织：项目结构是否合理
7. 实验效果：实验结果是不是较优
8. 可扩展性：代码是否易于扩展

另外，请给出一个总体评分（1-10分），这个分数应该综合考虑代码质量、任务匹配度、实现完整性等等各个方面，你可以根据你的经验自行判断，但要有一定的区分度。

# 特别注意，如果仓库中的模型结构主要以TensorFlow为主，则认为不相关

只返回JSON格式: 
[{{"repo_index": 1 or 0, "算法匹配度": 1 or 0, "领域适用性": 1 or 0, "数据处理能力": 1 or 0, "模型实现质量": 1 or 0, "代码可读性": 1 or 0, "结构组织": 1 or 0, "实验效果": 1 or 0, "可扩展性": 1 or 0, "总体评分": 1-10}}, ...]
"""
    
    repos_info = "\n".join([f"仓库{i+1}:\n<code>\n{r['important_modules_str']}\n</code>\n" for i, r in enumerate(repos_group)])
    
    prompt = f"""

任务: {task}

仓库列表:
{repos_info}

只返回JSON格式: 
[{{"repo_index": 1 or 0, "算法匹配度": 1 or 0, "领域适用性": 1 or 0, "数据处理能力": 1 or 0, "模型实现质量": 1 or 0, "代码可读性": 1 or 0, "结构组织": 1 or 0, "实验效果": 1 or 0, "可扩展性": 1 or 0, "总体评分": 1-10}}, ...]
"""
    
    # print(prompt)
    # import pdb; pdb.set_trace()
    
    try:
        response = llm_generte_response([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        scores = parse_llm_response(response)
        
        import time
        time.sleep(4)
        
        for score_info in scores:
            idx = score_info["repo_index"] - 1
            if 0 <= idx < len(repos_group):
                # 保存各维度得分
                repos_group[idx]["dimensions"] = {k: v for k, v in score_info.items() if k != "repo_index"}
                
                # 直接代码中计算加权总分
                dimensions_score = (
                    score_info["实验效果"] * 0.2 + 
                    score_info["算法匹配度"] * 0.2 + 
                    score_info["领域适用性"] * 0.15 + 
                    score_info["数据处理能力"] * 0.15 + 
                    score_info["模型实现质量"] * 0.15 + 
                    score_info["代码可读性"] * 0.1 + 
                    score_info["结构组织"] * 0.1 + 
                    score_info["可扩展性"] * 0.05
                )
                
                # 总体评分（1-10分）转换为0-1区间
                overall_score = score_info.get("总体评分", 0) / 10
                
                # 将维度得分和总体评分按6:4的比例组合
                total_score = dimensions_score * 0.6 + overall_score * 0.4
                
                repos_group[idx]["llm_score"] = total_score
                
    except Exception as e:
        print(f"LLM评估错误: {e}")
        if try_times > 0:
            print(f"重试第{try_times}次")
            return rate_repos_by_dimensions(task, repos_group, try_times - 1)
        else:
            # 出错时为每个仓库设置默认分数
            for repo in repos_group:
                if "llm_score" not in repo:
                    repo["llm_score"] = 0
    
    return repos_group

def process_repo(repo):
    """处理单个仓库的函数，用于并行调用"""
    try:
        if 'repo_path' not in repo:
            return None
        repo_path = repo['repo_path']
        repo_filter = RepoFilter(repo_path, max_tokens=4000)
        important_modules_str = repo_filter.important_modules_str
        if important_modules_str:
            return {
                'repo_path': repo_path,
                'important_modules_str': important_modules_str,
            }
        return None
    except Exception as e:
        print(f"分析仓库 {repo_path} 时出错: {e}")
        return None

def filter_repos_and_save(git_search_path, output_path):
    """
    筛选相关仓库并保存到本地文件，使用并行处理提高效率
    
    Args:
        git_search_path: git搜索结果文件路径
        output_path: 输出文件路径
    """
    filter_related_repo_list = {}
    
    # 创建一个锁，用于安全的打印
    print_lock = threading.Lock()
    
    for task_id, task_info in json.load(open(git_search_path, 'r')).items():
        task = task_info['task']
        repo_list = task_info['results']
        filter_related_repo_list[task_id] = {
            'task': task,
            'results': []
        }
        
        # 第一步：并行筛选相关仓库
        related_repos = []
        
        # 使用ThreadPoolExecutor进行并行处理，最大并发为10
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # 提交所有任务
            future_to_repo = {executor.submit(process_repo, repo): repo for repo in repo_list}
            
            # 使用tqdm显示进度
            with tqdm(total=len(future_to_repo), desc=f"处理任务 {task_id} 的仓库") as pbar:
                for future in concurrent.futures.as_completed(future_to_repo):
                    result = future.result()
                    if result:
                        related_repos.append(result)
                    pbar.update(1)
        
        filter_related_repo_list[task_id]['results'] = related_repos
    
    # 保存结果到本地文件
    json.dump(filter_related_repo_list, open(output_path, 'w'), ensure_ascii=False, indent=2)
    print(f"相关仓库信息已保存到: {output_path}")
    return filter_related_repo_list

def filter_and_rank_repos(git_search_path, out_path, top_k=5, filtered_repos_path=None):
    """
    合并相关性过滤和排名评分步骤
    
    Args:
        git_search_path: git搜索结果文件路径
        out_path: 输出文件路径
        top_k: 选择评分最高的k个仓库
        filtered_repos_path: 已过滤的仓库信息文件路径，如果提供则直接读取而不重新过滤
    """
    # 如果提供了已过滤的仓库文件路径且文件存在，直接读取
    if filtered_repos_path and os.path.exists(filtered_repos_path):
        print(f"正在读取已过滤的仓库信息: {filtered_repos_path}")
        filter_related_repo_list = json.load(open(filtered_repos_path, 'r'))
    else:
        # 否则重新过滤
        temp_filtered_path = filtered_repos_path or os.path.join(os.path.dirname(out_path), 'filtered_repos_temp.json')
        filter_related_repo_list = filter_repos_and_save(git_search_path, temp_filtered_path)

    idx = 0
    for task_id, task_info in filter_related_repo_list.items():
        # if idx > 1:
        #     break
        idx += 1
        task = task_info['task']
        related_repos = task_info['results']

        repo_groups = []
        current_group = []
        current_tokens = 0
        max_tokens = 60000
        
        for repo in related_repos:
            if 'important_modules_str' not in repo:
                continue
            if repo['important_modules_str'] == """[\n  \"# 仓库核心文件摘要\\n\",\n  \"[]\"\n]""":
                # import pdb; pdb.set_trace()
                continue
            tokens = get_code_abs_token(repo['important_modules_str'])
            if current_tokens + tokens > max_tokens and current_group:
                repo_groups.append(current_group)
                current_group = [repo]
                current_tokens = tokens
            else:
                current_group.append(repo)
                current_tokens += tokens
        
        if current_group:
            repo_groups.append(current_group)
        
        # 第三步：对每组进行多维度评分
        ranked_repos = []
        for group in repo_groups:
            rated_repos = rate_repos_by_dimensions(task, group)
            ranked_repos.extend(rated_repos)
        
        # 排序并选出top_k
        ranked_repos = sorted(ranked_repos, key=lambda x: x.get('llm_score', 0), reverse=True)
        filter_related_repo_list[task_id]['results'] = ranked_repos[:top_k]

    json.dump(filter_related_repo_list, open(out_path, 'w'), ensure_ascii=False, indent=2)

def main():
    root_path = '/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/git_repos/_mle_bench_repo'
    git_search_path = '/mnt/ceph/huacan/Code/Tasks/CodeAgent/Tool-Learner/git_search/res/2_git_clone_record.json'
    
    # 分两步执行：先过滤相关仓库，再进行排名
    filtered_repos_path = os.path.join(root_path, 'filtered_repos.json')
    # filter_repos_and_save(git_search_path, filtered_repos_path)
    
    # 使用已过滤的仓库进行排名，选出top3
    topk_repo_path = os.path.join(root_path, 'topk_repo_list.json')
    filter_and_rank_repos(git_search_path, topk_repo_path, filtered_repos_path=filtered_repos_path)
    
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv('/mnt/ceph/huacan/Code/Tasks/envs/.env')
    main()