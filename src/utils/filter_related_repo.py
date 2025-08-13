import json
import os
from src.core.code_explorer_tools import GlobalCodeTreeBuilder
from src.core.code_utils import get_code_abs_token
from src.utils.agent_gpt4 import AzureGPT4Chat
import concurrent.futures
import threading
from tqdm import tqdm

class RepoFilter:
    def __init__(self, repo_path, max_tokens=10000):
        self.repo_path = repo_path
        self.max_tokens = max_tokens
        
        self.builder = None
        self.important_modules_str = None # Used to store important_modules string
        self._build_new_tree()

    def _build_new_tree(self):
        """Build new code tree and generate important modules summary"""
        print(f"Analyzing code repository: {self.repo_path}")
        if not os.path.exists(self.repo_path):
            print(f"Repository {self.repo_path} does not exist")
            return
        try:
            self.builder = GlobalCodeTreeBuilder(
                self.repo_path,
            )
            self.builder.parse_repository()
            self.code_tree = self.builder.code_tree
            important_modules_data = self.builder.generate_llm_important_modules(max_tokens=self.max_tokens, is_file_summary=False)
            # Convert important_modules to string and store
            if isinstance(important_modules_data, (dict, list)):
                self.important_modules_str = json.dumps(important_modules_data, ensure_ascii=False, indent=2)
            else:
                self.important_modules_str = str(important_modules_data)

        except Exception as e:
            print(f"Error occurred while analyzing repository {self.repo_path}: {e}")
            self.builder = None # Ensure builder is None when error occurs
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
    """Multi-dimensional scoring of repositories"""
    
    system_prompt = """You are a professional code review expert who is good at analyzing the relevance of code repositories to specific tasks.
Your task is: Carefully read the Kaggle task description and core file information of the code repository provided by the user.
Based on this information, determine whether the code repository contains code that helps solve the Kaggle task (e.g., model architecture, training process, data processing, feature engineering, etc.).
Evaluate the relevance of the following code repositories to the task, scoring 0 or 1 from multiple dimensions:

Please score each repository from the following dimensions (0 or 1):
1. Algorithm Match: Whether the code algorithm matches the task requirements
2. Domain Applicability: Whether the code is applicable to the task domain
3. Data Processing Capability: Whether there are comprehensive data processing functions
4. Model Implementation Quality: Whether the model implementation is high quality
5. Code Readability: Whether the code is clear and readable
6. Structure Organization: Whether the project structure is reasonable
7. Experimental Results: Whether the experimental results are good
8. Scalability: Whether the code is easy to extend

Additionally, please give an overall score (1-10 points), which should comprehensively consider code quality, task matching, implementation completeness and other aspects. You can judge according to your experience, but there should be certain discrimination.

# Please note that if the model structure in the repository is mainly based on TensorFlow, it is considered irrelevant

Only return JSON format: 
[{{"repo_index": 1 or 0, "Algorithm Match": 1 or 0, "Domain Applicability": 1 or 0, "Data Processing Capability": 1 or 0, "Model Implementation Quality": 1 or 0, "Code Readability": 1 or 0, "Structure Organization": 1 or 0, "Experimental Results": 1 or 0, "Scalability": 1 or 0, "Overall Score": 1-10}}, ...]
"""
    
    repos_info = "\n".join([f"Repository{i+1}:\n<code>\n{r['important_modules_str']}\n</code>\n" for i, r in enumerate(repos_group)])
    
    prompt = f"""

Task: {task}

Repository List:
{repos_info}

Only return JSON format: 
[{{"repo_index": 1 or 0, "Algorithm Match": 1 or 0, "Domain Applicability": 1 or 0, "Data Processing Capability": 1 or 0, "Model Implementation Quality": 1 or 0, "Code Readability": 1 or 0, "Structure Organization": 1 or 0, "Experimental Results": 1 or 0, "Scalability": 1 or 0, "Overall Score": 1-10}}, ...]
"""
    
    # print(prompt)
    # import pdb; pdb.set_trace()
    
    try:
        scores = AzureGPT4Chat().chat_with_message(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ], 
            json_format=True
        )
        
        for score_info in scores:
            idx = score_info["repo_index"] - 1
            if 0 <= idx < len(repos_group):
                # Save dimension scores
                repos_group[idx]["dimensions"] = {k: v for k, v in score_info.items() if k != "repo_index"}
                
                # Calculate weighted total score directly in code
                dimensions_score = (
                    score_info["Experimental Results"] * 0.2 + 
                    score_info["Algorithm Match"] * 0.2 + 
                    score_info["Domain Applicability"] * 0.15 + 
                    score_info["Data Processing Capability"] * 0.15 + 
                    score_info["Model Implementation Quality"] * 0.15 + 
                    score_info["Code Readability"] * 0.1 + 
                    score_info["Structure Organization"] * 0.1 + 
                    score_info["Scalability"] * 0.05
                )
                
                # Overall score (1-10 points) converted to 0-1 range
                overall_score = score_info.get("Overall Score", 0) / 10
                
                # Combine dimension score and overall score in 6:4 ratio
                total_score = dimensions_score * 0.6 + overall_score * 0.4
                
                repos_group[idx]["llm_score"] = total_score
                
    except Exception as e:
        print(f"LLM evaluation error: {e}")
        if try_times > 0:
            print(f"Retry attempt {try_times}")
            return rate_repos_by_dimensions(task, repos_group, try_times - 1)
        else:
            # Set default score for each repository when error occurs
            for repo in repos_group:
                if "llm_score" not in repo:
                    repo["llm_score"] = 0
    
    return repos_group

def process_repo(repo):
    """Process single repository function for parallel calling"""
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
        print(f"Error occurred while analyzing repository {repo_path}: {e}")
        return None

def filter_repos_and_save(git_search_path, output_path):
    """
    Filter related repositories and save to local file, using parallel processing to improve efficiency
    
    Args:
        git_search_path: git search result file path
        output_path: output file path
    """
    filter_related_repo_list = {}
    
    # Create a lock for safe printing
    print_lock = threading.Lock()
    
    for task_id, task_info in json.load(open(git_search_path, 'r')).items():
        task = task_info['task']
        repo_list = task_info['results']
        filter_related_repo_list[task_id] = {
            'task': task,
            'results': []
        }
        
        # Step 1: Filter related repositories in parallel
        related_repos = []
        
        # Use ThreadPoolExecutor for parallel processing, maximum concurrency of 10
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks
            future_to_repo = {executor.submit(process_repo, repo): repo for repo in repo_list}
            
            # Use tqdm to show progress
            with tqdm(total=len(future_to_repo), desc=f"Processing repositories for task {task_id}") as pbar:
                for future in concurrent.futures.as_completed(future_to_repo):
                    result = future.result()
                    if result:
                        related_repos.append(result)
                    pbar.update(1)
        
        filter_related_repo_list[task_id]['results'] = related_repos
    
    # Save results to local file
    json.dump(filter_related_repo_list, open(output_path, 'w'), ensure_ascii=False, indent=2)
    print(f"Related repository information saved to: {output_path}")
    return filter_related_repo_list

def filter_and_rank_repos(git_search_path, out_path, top_k=5, filtered_repos_path=None):
    """
    Merge relevance filtering and ranking scoring steps
    
    Args:
        git_search_path: git search result file path
        out_path: output file path
        top_k: select top k repositories with highest scores
        filtered_repos_path: filtered repository information file path, if provided, read directly without re-filtering
    """
    # If filtered repository file path is provided and file exists, read directly
    if filtered_repos_path and os.path.exists(filtered_repos_path):
        print(f"Reading filtered repository information: {filtered_repos_path}")
        filter_related_repo_list = json.load(open(filtered_repos_path, 'r'))
    else:
        # Otherwise re-filter
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
            if repo['important_modules_str'] == """[\n  \"# Repository Core Files Summary\\n\",\n  \"[]\"\n]""":
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
        
        # Step 3: Multi-dimensional scoring for each group
        ranked_repos = []
        for group in repo_groups:
            rated_repos = rate_repos_by_dimensions(task, group)
            ranked_repos.extend(rated_repos)
        
        # Sort and select top_k
        ranked_repos = sorted(ranked_repos, key=lambda x: x.get('llm_score', 0), reverse=True)
        filter_related_repo_list[task_id]['results'] = ranked_repos[:top_k]

    json.dump(filter_related_repo_list, open(out_path, 'w'), ensure_ascii=False, indent=2)

def main():
    root_path = '/mnt/ceph/huacan/Code/Tasks/Code-Repo-Agent/git_repos/_mle_bench_repo'
    git_search_path = '/mnt/ceph/huacan/Code/Tasks/CodeAgent/Tool-Learner/git_search/res/2_git_clone_record.json'
    
    # Execute in two steps: first filter related repositories, then rank
    filtered_repos_path = os.path.join(root_path, 'filtered_repos.json')
    # filter_repos_and_save(git_search_path, filtered_repos_path)
    
    # Use filtered repositories for ranking, select top3
    topk_repo_path = os.path.join(root_path, 'topk_repo_list.json')
    filter_and_rank_repos(git_search_path, topk_repo_path, filtered_repos_path=filtered_repos_path)
    
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv('configs/.env')
    main()