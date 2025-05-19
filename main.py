import os   
import uuid
from core.tree_code import GlobalCodeTreeBuilder
from core.code_explorer_tools import CodeExplorerTools
from scripts.mle_task import get_mle_task, get_dataset_examples, create_small_data
def test_agent():
    from core.git_agent import CodeExplorer
    
    work_dir = f'{os.path.dirname(__file__)}/coding/{uuid.uuid4()}'
    os.makedirs(work_dir, exist_ok=True)
    
    if 0:
        repo_path = f"{os.path.dirname(__file__)}/git_repos/lyrapdf"
        task = f"帮我基于给定的仓库来完成以下任务（且只能使用给定仓库的代码），将{work_dir}/4005877.pdf文件解析成文本格式并保存为markdown格式到本地"
        os.system(f"cp -a /mnt/ceph/huacan/Code/Tasks/DeepRAG_Multimodal/picked_LongDoc/4005877.pdf {work_dir}/4005877.pdf")
    if 0:
        repo_path = f"{os.path.dirname(__file__)}/git_repos/fish-speech"
        task = "帮我基于给定的仓库来完成以下任务（且只能使用给定仓库的代码），合成'hello world'文本对应的音频文件，并保存到本地, 你需要check文件是否生成"
    if 0:
        repo_path = f"{os.path.dirname(__file__)}/git_repos/SWE-agent"
        task = "帮我基于给定的仓库来完成以下任务（且只能使用给定仓库的代码），帮我整理出仓库中所有的function call工具和整个Agent链路的逻辑,并生成一个完整的Agent链路代码， 完成网页自动爬取任务"
    if 1:
        # repo_path = f"{os.path.dirname(__file__)}/git_repos/APTOS2019BlindnessDetection"
        repo_path = f"{os.path.dirname(__file__)}/git_repos/Kaggle-2019-Blindness-Detection"
        # repo_path = f"{os.path.dirname(__file__)}/git_repos/kaggle-aptos2019-blindness-detection"
        
        data_path = "/mnt/ceph/huacan/Code/Tasks/CodeAgent/data/mle-bench-data/data/aptos2019-blindness-detection/prepared/public"
        os.system(f"cp -a {data_path} {work_dir}/data")
        data_path = f"{work_dir}/data"
        small_data_path = f"{work_dir}/data_small"
        create_small_data(data_path, small_data_path)
        task = get_mle_task('aptos2019-blindness-detection', small_data_path)


    # 测试代码分析
    print(work_dir)
    os.system(f"cp -a {repo_path} {work_dir}/{repo_path.split('/')[-1]}")
    repo_path = f"{work_dir}/{repo_path.split('/')[-1]}"
    
    remote_repo_path=f"/workspace/{repo_path.split('/')[-1]}"
    explorer = CodeExplorer(repo_path, work_dir=work_dir, remote_repo_path=None)
    answer = explorer.code_analysis(task, max_turns=50)
    print(f"分析结果: {answer}")

def test_repomap_importance():
    # 或者更详细的方式
    # builder = GlobalCodeTreeBuilder('git_repos/lyrapdf')
    builder = GlobalCodeTreeBuilder('git_repos/fish-speech')
    
    builder.parse_repository()
    builder.save_code_tree('res/code_tree.pkl')
    
    # 保存为JSON格式
    builder.save_json('res/code_tree.json')
    
    content = builder.generate_llm_important_modules()
    print(content)

def test_repomap_search():
    explorer = CodeExplorerTools(repo_path="git_repos/fish-speech")
    
    # 运行示例
    # explorer.run_examples()
    print(explorer.builder.generate_llm_important_modules())

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("/mnt/ceph/huacan/Code/Tasks/envs/.env")
    
    test_agent()
    # test_repomap_importance()
    # test_repomap_search()
    
    
    
