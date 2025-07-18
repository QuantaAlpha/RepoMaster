import os   
import uuid
from core.tree_code import GlobalCodeTreeBuilder
from core.code_explorer_tools import CodeExplorerTools
from scripts.mle_task import get_mle_task, get_dataset_examples, create_small_data


def init_venv():
    """初始化虚拟环境"""
    default_venvs_dir = './.venvs'
    venv_path = os.path.join(default_venvs_dir, "persistent_venv")
    
    if os.path.exists(venv_path):
        os.system(f"rm -rf {venv_path}")
    
    from core.code_utils import _create_virtual_env
    _create_virtual_env(venv_path)
    
    return

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
    
    load_dotenv("configs/.env")
    
    
    
    
