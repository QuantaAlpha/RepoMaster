# RepoMaster Configuration Guide

This guide provides configuration options and usage examples for RepoMaster based on the actual project documentation.

## 📋 Table of Contents

- [LLM Configuration](#llm-configuration)
- [Code Execution Configuration](#code-execution-configuration)
- [Explorer Configuration](#explorer-configuration)
- [Basic Usage Examples](#basic-usage-examples)
- [Advanced Usage Examples](#advanced-usage-examples)

---

## 🔑 LLM Configuration

### Supported Models

```python
llm_config = {
    "config_list": [
        {
            "model": "gpt-4o",  # Supported: gpt-4o, claude-3-5-sonnet, deepseek-chat
            "api_key": "your_api_key",
            "base_url": "api_endpoint"
        }
    ],
    "timeout": 2000,
    "temperature": 0.1,
}
```

### Model Options

- **GPT-4o**: OpenAI's latest model
- **Claude-3-5-Sonnet**: Anthropic's Claude model
- **DeepSeek-Chat**: DeepSeek's model

---

## ⚙️ Code Execution Configuration

```python
code_execution_config = {
    "work_dir": "workspace",      # Working directory
    "use_docker": False,          # Whether to use Docker
    "timeout": 7200,              # Execution timeout (seconds)
}
```

### Configuration Options

- **work_dir**: Directory for storing temporary files and results
- **use_docker**: Enable Docker containerization (experimental)
- **timeout**: Maximum execution time in seconds

---

## 🔧 Explorer Configuration

```python
explorer_config = {
    "max_turns": 40,              # Maximum conversation turns
    "use_venv": True,             # Whether to use virtual environment
    "function_call": True,        # Whether to enable function calling
    "repo_init": True,            # Whether to perform repository initialization analysis
}
```

### Configuration Options

- **max_turns**: Maximum number of conversation rounds
- **use_venv**: Create and use Python virtual environment
- **function_call**: Enable LLM function calling capabilities
- **repo_init**: Perform initial repository structure analysis

---

## 💻 Basic Usage Examples

### Simple Task Execution

```python
from core.agent_scheduler import RepoMasterAgent

# Initialize RepoMaster
llm_config = {
    "config_list": [{
        "model": "claude-3-5-sonnet-20241022",
        # "api_key": "your_api_key", # Replace with your API Key
        # "base_url": "https://api.anthropic.com" # Replace with your API Endpoint
    }],
    "timeout": 2000,
    "temperature": 0.1,
}

code_execution_config = {
    "work_dir": "workspace", 
    "use_docker": False
}

repo_master = RepoMasterAgent(
    llm_config=llm_config,
    code_execution_config=code_execution_config,
)

# Define a complex AI task
task = """
I need to convert a content image to a specific artistic style.
Content image path: 'example/origin.jpg'
Style reference image path: 'example/style.jpg'
Please save the final stylized image as 'workspace/merged_styled_image.png'
"""

# User only needs one line of code to start the task
# RepoMaster will automatically complete the entire process of search, understanding, execution, and debugging
result_summary = repo_master.solve_task_with_repo(task)

print("Task completion summary:")
print(result_summary)
```

---

## 🚀 Advanced Usage Examples

### 1. Direct Repository Usage

```python
from core.git_task import TaskManager, AgentRunner

# Construct task configuration
task_info = {
    "repo": {
        "type": "github",
        "url": "https://github.com/spatie/pdf-to-text",
    },
    "task_description": "Extract PDF text content",
    "input_data": [
        {
            "path": "/path/to/input.pdf",
            "description": "PDF file to process"
        }
    ],
}

# Execute task
result = AgentRunner.run_agent(task_info)
```

### 2. Local Repository Analysis

```python
from core.git_agent import CodeExplorer

# Initialize code explorer
explorer = CodeExplorer(
    local_repo_path="/path/to/local/repo",
    work_dir="workspace",
    task_type="general",
    use_venv=True,
    llm_config=llm_config
)

# Execute code analysis
task = "Analyze the core functionality of this repository and generate usage examples"
result = explorer.code_analysis(task)
```

---

## 🛠️ Core Components

### 1. Repository Search Module (`deep_search.py`)

```python
async def github_repo_search(self, task):
    """
    Execute GitHub repository deep search
    
    Parameters:
        task: Task description
        
    Returns:
        JSON list of matching repositories
    """
```

### 2. Code Exploration Tool (`git_agent.py`)

```python
class CodeExplorer:
    """
    Core code exploration and analysis tool
    
    Main functions:
    - Repository structure analysis
    - Dependency relationship construction
    - Intelligent code navigation
    - Task-driven code generation
    """
```

### 3. Task Manager (`git_task.py`)

```python
class TaskManager:
    """
    Task initialization, environment preparation and execution management
    
    Main functions:
    - Working environment creation
    - Dataset copying and processing
    - Task configuration management
    """
```

---

## 🔧 Custom Extensions

### Adding Custom Tools

```python
from util.toolkits import register_toolkits

def custom_analysis_tool(file_path: str) -> str:
    """Custom analysis tool"""
    # Implement your analysis logic
    return analysis_result

# Register tools
register_toolkits(
    [custom_analysis_tool],
    scheduler_agent,
    user_proxy_agent,
)
```

### Extending Repository Search

```python
class CustomRepoSearcher:
    def __init__(self):
        self.search_strategies = [
            "keyword_based",
            "semantic_search", 
            "dependency_analysis"
        ]
    
    def search_repositories(self, task_description):
        # Implement custom search logic
        pass
```

---

## 📖 Experiments and Evaluation

### Reproducing Experimental Results

```bash
# Evaluate on GitTaskBench
python -m core.git_task --config configs/gittaskbench.yaml

# Evaluate on MLE-Bench
python -m core.git_task --config configs/mle_r.yaml
```

---

## 📝 Use Cases

### Case 1: PDF Text Extraction

```python
task = """
Please extract all text content from the first page of the PDF to a txt file.
Input file: /path/to/document.pdf
Output requirement: Save as output.txt
"""

result = repo_master.solve_task_with_repo(task)
# RepoMaster will automatically:
# 1. Search for PDF processing related repositories
# 2. Analyze repository structure and API
# 3. Generate extraction code
# 4. Execute and save results
```

### Case 2: Machine Learning Pipeline

```python
task = """
Train an image classification model based on the given image dataset.
Dataset: /path/to/image_dataset/
Requirements: Use pre-trained model for fine-tuning, save the best model
"""

result = repo_master.solve_task_with_repo(task)
# RepoMaster will automatically:
# 1. Find suitable deep learning repositories
# 2. Understand data loading and model structure
# 3. Set up training pipeline
# 4. Execute training and save model
```

### Case 3: Video Processing

```python
task = """
Extract key frames from video and perform 3D pose estimation.
Input: /path/to/video.mp4
Output: 3D joint coordinate JSON file
"""

result = repo_master.solve_task_with_repo(task)
# RepoMaster will automatically:
# 1. Search for video processing and pose estimation repositories
# 2. Understand preprocessing and inference pipeline
# 3. Implement end-to-end processing pipeline
# 4. Generate structured output
```

---

## 🤝 Contributing

### Development Environment Setup

```bash
git clone https://github.com/QuantaAlpha/RepoMaster.git
cd RepoMaster
pip install -e ".[dev]"
pre-commit install
```

### Contribution Types

- 🐛 Bug fixes
- ✨ New feature development
- 📚 Documentation improvements
- 🧪 Test case additions
- 🔧 Tools and utilities

---

## 📞 Support

- 📧 **Email**: quantaalpha.ai@gmail.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/QuantaAlpha/RepoMaster/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/QuantaAlpha/RepoMaster/discussions)

---

*Last updated: December 2024*
