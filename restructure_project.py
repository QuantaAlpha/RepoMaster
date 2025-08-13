#!/usr/bin/env python3
"""
RepoMaster 项目重构脚本
======================

该脚本用于重构 RepoMaster 项目的目录结构，使其更加规范和易于维护。

主要功能：
1. 重新组织目录结构
2. 移动和重命名文件
3. 更新Python文件中的import路径
4. 清理临时文件和无用目录
5. 统一配置文件位置

新的目录结构：
repomaster/
├── README.md
├── CLAUDE.md
├── requirements.txt              # 合并后的依赖
├── setup.py                     # Python包配置
├── .env.example                 # 环境变量示例
├── .gitignore                   # Git忽略文件
├── run.sh                       # 启动脚本
├── repomaster/                  # 主要Python包
│   ├── __init__.py
│   ├── main.py                  # 主入口
│   ├── config/                  # 配置管理
│   │   ├── __init__.py
│   │   ├── settings.py          # 统一配置
│   │   └── llm_config.py        # LLM配置
│   ├── core/                    # 核心功能
│   │   ├── __init__.py
│   │   ├── agents/              # AI代理
│   │   │   ├── __init__.py
│   │   │   ├── scheduler.py     # 任务调度器
│   │   │   ├── code_explorer.py # 代码探索器
│   │   │   ├── general_coder.py # 通用编码器
│   │   │   └── deep_search.py   # 深度搜索
│   │   ├── analysis/            # 代码分析
│   │   │   ├── __init__.py
│   │   │   ├── tree_builder.py  # AST树构建
│   │   │   ├── code_utils.py    # 代码工具
│   │   │   ├── importance_analyzer.py
│   │   │   └── repo_summary.py
│   │   ├── execution/           # 任务执行
│   │   │   ├── __init__.py
│   │   │   ├── task_manager.py  # 任务管理
│   │   │   ├── docker_executor.py
│   │   │   └── git_operations.py
│   │   └── tools/              # 工具集
│   │       ├── __init__.py
│   │       ├── toolkit_registry.py
│   │       ├── web_search.py
│   │       └── file_operations.py
│   ├── frontend/               # Web界面
│   │   ├── __init__.py
│   │   ├── app.py             # Streamlit主应用
│   │   ├── components/        # UI组件
│   │   │   ├── __init__.py
│   │   │   ├── chat_interface.py
│   │   │   ├── file_browser.py
│   │   │   └── auth_manager.py
│   │   └── utils/             # 前端工具
│   │       ├── __init__.py
│   │       ├── ui_styles.py
│   │       └── session_manager.py
│   ├── services/              # 服务层
│   │   ├── __init__.py
│   │   ├── autogen/           # AutoGen服务
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py
│   │   │   ├── code_judge.py
│   │   │   └── message_editor.py
│   │   └── prompts/           # 提示词管理
│   │       ├── __init__.py
│   │       ├── agent_prompts.py
│   │       └── task_prompts.py
│   └── utils/                 # 通用工具
│       ├── __init__.py
│       ├── logging.py         # 日志配置
│       ├── file_utils.py      # 文件操作
│       ├── error_handlers.py  # 错误处理
│       └── data_preview.py    # 数据预览
├── tasks/                     # 任务和基准测试
│   ├── __init__.py
│   ├── benchmarks/            # 基准测试
│   │   ├── __init__.py
│   │   ├── git_bench/         # Git基准测试
│   │   └── mle_bench/         # MLE基准测试
│   └── examples/              # 示例任务
│       ├── __init__.py
│       └── sample_tasks.yaml
├── tests/                     # 测试文件
│   ├── __init__.py
│   ├── test_core/
│   ├── test_frontend/
│   └── test_utils/
├── docs/                      # 文档
│   ├── api.md
│   ├── architecture.md
│   └── user_guide.md
├── scripts/                   # 脚本工具
│   ├── setup_env.sh
│   └── clean_workspace.sh
└── workspace/                 # 工作空间
    ├── logs/                  # 日志文件
    ├── data/                  # 数据文件
    └── temp/                  # 临时文件

使用方法：
1. 审查这个脚本的内容
2. 备份当前项目：cp -r RepoMaster RepoMaster_backup
3. 运行脚本：python restructure_project.py
4. 验证结果并测试功能
"""

import os
import shutil
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('restructure.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ProjectRestructurer:
    """项目重构工具类"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.backup_path = self.root_path.parent / f"{self.root_path.name}_backup"
        
        # 文件移动映射表：(源路径, 目标路径)
        self.file_moves = [
            # 主要Python包
            ("main.py", "repomaster/main.py"),
            
            # 配置文件
            ("configs/config.py", "repomaster/config/settings.py"),
            ("configs/oai_config.py", "repomaster/config/llm_config.py"),
            
            # 核心模块 - 代理
            ("core/agent_scheduler.py", "repomaster/core/agents/scheduler.py"),
            ("core/agent_code_explore.py", "repomaster/core/agents/code_explorer.py"),
            ("services/agents/agent_general_coder.py", "repomaster/core/agents/general_coder.py"),
            ("services/agents/deepsearch_2agents.py", "repomaster/core/agents/deep_search.py"),
            
            # 核心模块 - 分析
            ("core/tree_code.py", "repomaster/core/analysis/tree_builder.py"),
            ("core/code_utils.py", "repomaster/core/analysis/code_utils.py"),
            ("core/importance_analyzer.py", "repomaster/core/analysis/importance_analyzer.py"),
            ("core/repo_summary.py", "repomaster/core/analysis/repo_summary.py"),
            ("core/base_code_explorer.py", "repomaster/core/analysis/base_explorer.py"),
            
            # 核心模块 - 执行
            ("core/git_task.py", "repomaster/core/execution/task_manager.py"),
            ("core/agent_docker_executor.py", "repomaster/core/execution/docker_executor.py"),
            
            # 核心模块 - 工具
            ("utils/toolkits.py", "repomaster/core/tools/toolkit_registry.py"),
            ("utils/web_search_agent/tool_web_search.py", "repomaster/core/tools/web_search.py"),
            ("core/tool_code_explorer.py", "repomaster/core/tools/code_explorer_tool.py"),
            
            # 前端
            ("frontend_st/app_autogen_enhanced.py", "repomaster/frontend/app.py"),
            ("frontend_st/file_browser.py", "repomaster/frontend/components/file_browser.py"),
            ("frontend_st/call_agent.py", "repomaster/frontend/components/chat_interface.py"),
            ("frontend_st/auth_utils.py", "repomaster/frontend/components/auth_manager.py"),
            ("frontend_st/ui_styles.py", "repomaster/frontend/utils/ui_styles.py"),
            
            # 服务层
            ("services/autogen_upgrade/base_agent.py", "repomaster/services/autogen/base_agent.py"),
            ("services/autogen_upgrade/codeblock_judge.py", "repomaster/services/autogen/code_judge.py"),
            ("services/autogen_upgrade/edit_autogen_msg.py", "repomaster/services/autogen/message_editor.py"),
            ("services/prompts/general_coder_prompt.py", "repomaster/services/prompts/agent_prompts.py"),
            ("core/prompt.py", "repomaster/services/prompts/task_prompts.py"),
            
            # 工具类
            ("utils/agent_gpt4.py", "repomaster/utils/llm_client.py"),
            ("utils/data_preview.py", "repomaster/utils/data_preview.py"),
            ("utils/filter_related_repo.py", "repomaster/utils/repo_filter.py"),
            ("utils/tool_streamlit.py", "repomaster/frontend/utils/session_manager.py"),
            ("utils/tools_util.py", "repomaster/utils/file_utils.py"),
            ("utils/utils_config.py", "repomaster/config/__init__.py"),
            
            # 任务和基准测试
            ("tasks/git_bench/", "tasks/benchmarks/git_bench/"),
            ("tasks/mle_bench/", "tasks/benchmarks/mle_bench/"),
            
            # 依赖文件
            ("enviroment/requirements.txt", "requirements/base.txt"),
            ("enviroment/llm_requirements.txt", "requirements/llm.txt"),
            ("requirement.txt", "requirements/utils.txt"),
        ]
        
        # import路径替换映射
        self.import_replacements = {
            # 旧路径 -> 新路径
            "from core.": "from repomaster.core.",
            "from services.": "from repomaster.services.",
            "from utils.": "from repomaster.utils.",
            "from frontend_st.": "from repomaster.frontend.",
            "from configs.": "from repomaster.config.",
            "import core.": "import repomaster.core.",
            "import services.": "import repomaster.services.",
            "import utils.": "import repomaster.utils.",
            "import frontend_st.": "import repomaster.frontend.",
            "import configs.": "import repomaster.config.",
            
            # 具体模块替换
            "from core.tree_code import": "from repomaster.core.analysis.tree_builder import",
            "from core.agent_scheduler import": "from repomaster.core.agents.scheduler import",
            "from core.code_utils import": "from repomaster.core.analysis.code_utils import",
            "from services.agents.agent_general_coder import": "from repomaster.core.agents.general_coder import",
            "from utils.toolkits import": "from repomaster.core.tools.toolkit_registry import",
            "from frontend_st.auth_utils import": "from repomaster.frontend.components.auth_manager import",
        }
    
    def create_backup(self):
        """创建项目备份"""
        logger.info(f"创建项目备份到: {self.backup_path}")
        if self.backup_path.exists():
            shutil.rmtree(self.backup_path)
        shutil.copytree(self.root_path, self.backup_path)
        logger.info("备份完成")
    
    def create_new_structure(self):
        """创建新的目录结构"""
        logger.info("创建新的目录结构...")
        
        # 定义新目录结构
        new_dirs = [
            "repomaster",
            "repomaster/config",
            "repomaster/core",
            "repomaster/core/agents",
            "repomaster/core/analysis", 
            "repomaster/core/execution",
            "repomaster/core/tools",
            "repomaster/frontend",
            "repomaster/frontend/components",
            "repomaster/frontend/utils",
            "repomaster/services",
            "repomaster/services/autogen",
            "repomaster/services/prompts",
            "repomaster/utils",
            "tasks/benchmarks",
            "tasks/benchmarks/git_bench",
            "tasks/benchmarks/mle_bench",
            "tasks/examples",
            "tests",
            "tests/test_core",
            "tests/test_frontend",
            "tests/test_utils",
            "docs",
            "scripts",
            "workspace",
            "workspace/logs",
            "workspace/data", 
            "workspace/temp",
            "requirements"
        ]
        
        # 创建目录
        for dir_path in new_dirs:
            full_path = self.root_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            
            # 创建__init__.py文件（对于Python包）
            if any(part in dir_path for part in ['repomaster', 'tasks', 'tests']) and not dir_path.endswith(('.git', 'logs', 'data', 'temp', 'docs', 'scripts', 'requirements')):
                init_file = full_path / "__init__.py"
                if not init_file.exists():
                    init_file.write_text('"""Auto-generated __init__.py"""')
        
        logger.info("目录结构创建完成")
    
    def move_files(self):
        """移动文件到新位置"""
        logger.info("开始移动文件...")
        
        for src_rel, dst_rel in self.file_moves:
            src_path = self.root_path / src_rel
            dst_path = self.root_path / dst_rel
            
            # 如果源路径是目录，递归移动
            if src_path.is_dir():
                if dst_path.exists():
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
                logger.info(f"移动目录: {src_rel} -> {dst_rel}")
            elif src_path.is_file():
                # 确保目标目录存在
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                logger.info(f"移动文件: {src_rel} -> {dst_rel}")
            else:
                logger.warning(f"源文件不存在: {src_rel}")
    
    def update_imports(self):
        """更新Python文件中的import语句"""
        logger.info("更新import语句...")
        
        # 遍历所有Python文件
        for py_file in self.root_path.rglob("*.py"):
            # 跳过备份目录、临时目录等
            if any(part in str(py_file) for part in ['_backup', 'coding', 'tmp', '_del', '.venv']):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # 应用import替换
                for old_import, new_import in self.import_replacements.items():
                    content = content.replace(old_import, new_import)
                
                # 如果内容有变化，写回文件
                if content != original_content:
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"更新导入语句: {py_file}")
                    
            except Exception as e:
                logger.error(f"更新文件 {py_file} 时出错: {e}")
    
    def create_setup_py(self):
        """创建setup.py文件"""
        setup_content = '''"""
RepoMaster Setup Configuration
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="repomaster",
    version="0.1.0",
    author="RepoMaster Team",
    description="AI-powered code repository analysis and task execution framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "repomaster=repomaster.main:main",
        ],
    },
)
'''
        setup_file = self.root_path / "setup.py"
        setup_file.write_text(setup_content)
        logger.info("创建 setup.py")
    
    def merge_requirements(self):
        """合并依赖文件"""
        logger.info("合并依赖文件...")
        
        requirements = set()
        
        # 读取各个requirements文件
        req_files = [
            "requirements/base.txt",
            "requirements/llm.txt", 
            "requirements/utils.txt"
        ]
        
        for req_file in req_files:
            req_path = self.root_path / req_file
            if req_path.exists():
                with open(req_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            requirements.add(line)
        
        # 写入合并后的requirements.txt
        main_req_file = self.root_path / "requirements.txt"
        with open(main_req_file, 'w', encoding='utf-8') as f:
            f.write("# RepoMaster Dependencies\n")
            f.write("# Generated by restructure script\n\n")
            for req in sorted(requirements):
                f.write(f"{req}\n")
        
        logger.info("依赖文件合并完成")
    
    def create_env_example(self):
        """创建环境变量示例文件"""
        env_content = '''# RepoMaster Environment Variables
# Copy this file to .env and fill in your actual values

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Claude Configuration  
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Azure OpenAI Configuration (Optional)
AZURE_OPENAI_MODEL=gpt-4
AZURE_OPENAI_API_KEY=your_azure_api_key_here
AZURE_OPENAI_BASE_URL=https://your-resource.openai.azure.com/

# X.AI Grok Configuration (Optional)
XAI_API_KEY=your_xai_api_key_here

# Application Settings
PYTHONPATH=.
WORKSPACE_DIR=./workspace
LOG_LEVEL=INFO
'''
        env_file = self.root_path / ".env.example"
        env_file.write_text(env_content)
        logger.info("创建 .env.example")
    
    def update_gitignore(self):
        """更新.gitignore文件"""
        gitignore_content = '''# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# celery beat schedule file
celerybeat-schedule

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/
.venvs/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# RepoMaster specific
workspace/logs/
workspace/data/
workspace/temp/
coding/
tmp/
_del/
*.backup
restructure.log
'''
        gitignore_file = self.root_path / ".gitignore"
        gitignore_file.write_text(gitignore_content)
        logger.info("更新 .gitignore")
    
    def update_run_script(self):
        """更新启动脚本"""
        run_content = '''#!/bin/bash
# RepoMaster 启动脚本

# 设置环境变量
export PYTHONPATH=$(pwd):$PYTHONPATH

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动Streamlit应用
echo "启动 RepoMaster Web 界面..."
streamlit run repomaster/frontend/app.py

# 其他常用命令示例：
# python -m repomaster.main  # 运行主程序
# python tasks/benchmarks/git_bench/run_benchmark.py  # 运行Git基准测试
# python tasks/benchmarks/mle_bench/run_benchmark.py  # 运行MLE基准测试
'''
        run_file = self.root_path / "run.sh"
        run_file.write_text(run_content)
        run_file.chmod(0o755)  # 添加执行权限
        logger.info("更新 run.sh")
    
    def cleanup_old_files(self):
        """清理旧文件和临时目录"""
        logger.info("清理旧文件和目录...")
        
        # 要删除的目录和文件
        cleanup_items = [
            "coding",
            "tmp", 
            "_del",
            "frontend_st",
            "services",
            "utils",
            "core",
            "configs",
            "enviroment",
            "data",  # 移动到workspace/data
            "logs",  # 移动到workspace/logs
            "requirement.txt",  # 已合并到requirements.txt
        ]
        
        for item in cleanup_items:
            item_path = self.root_path / item
            if item_path.exists():
                if item_path.is_dir():
                    # 特殊处理：移动重要数据
                    if item == "data":
                        workspace_data = self.root_path / "workspace" / "data"
                        if not workspace_data.exists():
                            shutil.move(str(item_path), str(workspace_data))
                            logger.info(f"移动数据目录: {item} -> workspace/data")
                            continue
                    elif item == "logs":
                        workspace_logs = self.root_path / "workspace" / "logs"
                        if not workspace_logs.exists():
                            shutil.move(str(item_path), str(workspace_logs))
                            logger.info(f"移动日志目录: {item} -> workspace/logs")
                            continue
                    
                    shutil.rmtree(item_path)
                    logger.info(f"删除目录: {item}")
                else:
                    item_path.unlink()
                    logger.info(f"删除文件: {item}")
    
    def create_example_task(self):
        """创建示例任务配置"""
        task_content = '''# RepoMaster 示例任务配置
tasks:
  example_analysis:
    repo:
      type: github
      url: https://github.com/example/repo
    description: |
      分析仓库结构并生成报告：
      1. 分析代码结构和主要功能
      2. 识别关键模块和依赖关系
      3. 生成代码质量报告
      4. 输出结果到 {output_path} 目录
    parameters:
      timeout: 1800
      priority: 1
      
  local_repo_task:
    repo:
      type: local
      path: /path/to/local/repository
    description: |
      本地仓库任务示例：
      1. 扫描代码文件
      2. 执行代码分析
      3. 生成改进建议
    data:
      input_path: /path/to/input/data
      input_info:
        - name: "输入数据集"
          path: "data/dataset.csv"
          description: "用于分析的数据集"
'''
        task_file = self.root_path / "tasks" / "examples" / "sample_tasks.yaml"
        task_file.write_text(task_content)
        logger.info("创建示例任务配置")
    
    def run_restructure(self):
        """执行完整的重构流程"""
        logger.info("开始项目重构...")
        
        try:
            # 1. 创建备份
            self.create_backup()
            
            # 2. 创建新目录结构
            self.create_new_structure()
            
            # 3. 移动文件
            self.move_files()
            
            # 4. 更新导入语句
            self.update_imports()
            
            # 5. 创建配置文件
            self.create_setup_py()
            self.merge_requirements()
            self.create_env_example()
            self.update_gitignore()
            self.update_run_script()
            self.create_example_task()
            
            # 6. 清理旧文件（谨慎执行）
            # self.cleanup_old_files()  # 注释掉，让用户手动执行
            
            logger.info("项目重构完成！")
            logger.info(f"备份位置: {self.backup_path}")
            logger.info("请检查新结构并测试功能正常性")
            logger.info("如需清理旧文件，请手动执行 cleanup_old_files() 方法")
            
        except Exception as e:
            logger.error(f"重构过程中发生错误: {e}")
            logger.info("请检查日志文件 restructure.log 获取详细信息")
            raise

def main():
    """主函数"""
    if len(sys.argv) != 2:
        print("使用方法: python restructure_project.py <project_root_path>")
        print("示例: python restructure_project.py /path/to/RepoMaster")
        sys.exit(1)
    
    project_root = sys.argv[1]
    
    if not os.path.exists(project_root):
        print(f"错误: 项目路径不存在 - {project_root}")
        sys.exit(1)
    
    print("=" * 60)
    print("RepoMaster 项目重构工具")
    print("=" * 60)
    print(f"项目路径: {project_root}")
    print("警告: 此操作将重构整个项目结构")
    print("建议在重构前手动备份项目")
    
    response = input("确认继续? (y/N): ").strip().lower()
    if response != 'y':
        print("操作已取消")
        sys.exit(0)
    
    # 执行重构
    restructurer = ProjectRestructurer(project_root)
    restructurer.run_restructure()
    
    print("\n" + "=" * 60)
    print("重构完成！请按以下步骤验证:")
    print("1. 检查新的目录结构")
    print("2. 运行: pip install -e .")
    print("3. 测试启动: ./run.sh")
    print("4. 验证功能正常后，可手动删除旧目录")
    print("=" * 60)

if __name__ == "__main__":
    main()