<div align="center">

<img src="docs/assets/images/RepoMaster.logo.png" alt="RepoMaster Logo" width="200"/>

# RepoMaster: Autonomous Exploration and Understanding of GitHub Repositories for Complex Task Solving

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-2505.21577-red.svg)](https://arxiv.org/abs/2505.21577)
[![Code](https://img.shields.io/badge/Code-Coming%20Soon-orange.svg)](https://github.com/QuantaAlpha/RepoMaster)

[English](README.md) | [中文](README_CN.md)

</div>

> **📢 Important Notice**: The complete source code will be open-sourced after paper publication. Currently, we provide project demonstrations and partial code examples.

## 🚀 Overview

RepoMaster is a revolutionary autonomous agent framework specifically designed to explore, understand, and utilize GitHub repositories for solving complex real-world tasks. Unlike traditional approaches that generate code from scratch, RepoMaster treats open-source repositories on GitHub as composable tool modules, automatically leveraging these resources through intelligent search, hierarchical analysis, and autonomous exploration.

<img src="docs/assets/images/performance_01.jpg" alt="RepoMaster 效果图" style="width: 600px; padding: 20px; background-color: #ffffff; display: block; margin: 0 auto;" />

## 🚀 Quick Start

RepoMaster can be run in two primary modes. Choose the one that fits your needs:

### 🖥️ Frontend Mode (Web Interface)
Launch the interactive web interface for multi-user access and visual interaction:

```bash
python launcher.py --mode frontend --streamlit-port 8588
```

**Access**: Open your browser and go to `http://localhost:8588`

### 🤖 Backend Mode (Unified AI Assistant) ⭐ Recommended
Run the unified AI assistant that combines all RepoMaster capabilities:

```bash
python launcher.py --mode backend --backend-mode unified
```

**Features**: Deep search, code analysis, repository tasks, and general programming assistance

### Shell Script Shortcuts

```bash
# Frontend
bash run.sh frontend

# Backend unified mode
bash run.sh backend unified
```

---

## 🎯 Quick Demo

Imagine describing a task in natural language, and RepoMaster automatically handles the rest: from finding the most suitable GitHub repository and understanding its complex code structure, to finally executing and completing the task! RepoMaster can handle everything from simple data extraction to complex AI model applications.

**For example, you could tell RepoMaster:**

-   **Simple Tasks**:
    -   "Help me scrape all product names and prices from this webpage."
    -   "Extract all table data from this PDF document and save it as a CSV file."
-   **Complex Tasks**:
    -   "Transform this portrait photo into the style of a Van Gogh oil painting." (As demonstrated below)
    -   "Automatically edit this long video, extract all exciting clips featuring a specific person, and add background music."

### 🎨 Neural Style Transfer Task Demo (Complex Task Example)

<table>
<tr>
<td align="center"><b>Original Image</b></td>
<td align="center"><b>Style Reference</b></td>
<td align="center"><b>Transfer Result</b></td>
</tr>
<tr>
<td><img src="docs/assets/images/origin.jpg" width="200px" /></td>
<td><img src="docs/assets/images/style.jpg" width="200px" /></td>
<td><img src="docs/assets/images/transfer.jpg" width="200px" /></td>
</tr>
</table>

**RepoMaster Automated Workflow (Style Transfer Example)**:
1. 🔍 **Smart Search**: Automatically search for style transfer related repositories on GitHub.
2. 🏗️ **Structure Analysis**: Analyze repository code structure, identify core models and processing pipelines.
3. 🔧 **Autonomous Execution**: Automatically configure environment, load models, and process images.
4. ✅ **Task Completion**: Generate style-transferred images without human intervention.

### 🎬 Complete Execution Demo (Style Transfer) | [📺 YouTube Demo](https://www.youtube.com/watch?v=Kva2wVhBkDU)

<div align="center">

https://github.com/user-attachments/assets/a21b2f2e-a31c-4afd-953d-d143beef781a

*Complete process of RepoMaster autonomously executing neural style transfer task*

</div>

**Demo Highlights**:
- 🤖 **Zero Human Intervention**: Fully automated from task understanding to result generation
- 🧠 **Intelligent Understanding**: Automatically comprehends complex deep learning codebases
- ⚡ **Efficient Execution**: Quickly locates key code, avoiding irrelevant exploration
- 🎯 **Precise Results**: High-quality task completion effects

---

## 🚀 Framework

### 🎨 Illustration of RepoMaster Framework

<img src="docs/assets/images/overview.png" alt="RepoMaster 框架示意图" style="width: 600px; padding: 20px; background-color: #ffffff; display: block; margin: 0 auto;" />

### 🎯 Core Philosophy

- **Repositories as Tools**: Treat open-source repositories as pre-built toolkits for solving complex tasks
- **Human-like Exploration**: Mimic how human programmers explore unfamiliar codebases
- **Smart Compression**: Efficiently manage massive code information within limited LLM context windows
- **Autonomous Execution**: End-to-end completion from task understanding to code execution

## ✨ Key Features

### 🔍 Intelligent Repository Search
- Deep search algorithms based on task descriptions
- Multi-round query optimization and repository quality assessment
- Automated repository relevance analysis

### 🏗️ Hierarchical Repository Analysis
- **Hybrid Structural Modeling**: Build Hierarchical Code Trees (HCT), Function Call Graphs (FCG), and Module Dependency Graphs (MDG)
- **Core Component Identification**: Automatically identify key modules, classes, and functions based on importance scoring
- **Context Initialization**: Intelligently construct initial context containing README, module summaries, and core code

### 🔧 Autonomous Exploration & Execution
- **Granular Code View**: Support file, class, and function-level code inspection
- **Dependency Analysis**: Trace call chains and dependency paths
- **Smart Search**: Keyword matching and semantic search
- **Context-aware Information Selection**: Multi-level content compression strategies

### 💡 Core Advantages
- **Efficiency**: 95% reduction in token consumption compared to existing frameworks
- **Accuracy**: Improve task pass rate from 24.1% to 62.9% on GitTaskBench
- **Universality**: Support multiple LLM backends (GPT-4o, Claude-3.5, DeepSeek-V3)
- **Extensibility**: Modular design supporting custom tools and extensions

---

## 📊 Performance

### GitTaskBench Results
| Framework | Execution Rate | Task Pass Rate | Token Usage |
|-----------|----------------|----------------|-------------|
| SWE-Agent | 44.44% | 14.81% | 330k |
| OpenHands | 48.15% | 24.07% | 3094k |
| **RepoMaster** | **75.92%** | **62.96%** | **154k** |

### MLE-Bench Results
| Framework | Valid Submissions | Medal Rate | Gold Medals |
|-----------|------------------|------------|-------------|
| SWE-Agent | 50.00% | 4.55% | 4.55% |
| OpenHands | 45.45% | 4.55% | 4.55% |
| **RepoMaster** | **95.45%** | **27.27%** | **22.73%** |

---

## 🛠️ Installation

### Prerequisites

```bash
# Python 3.11+ required
python --version  # Should be 3.11+
```

### Install Dependencies

```bash
# Clone the repository
git clone https://github.com/your-org/RepoMaster.git
cd RepoMaster

# Install requirements
pip install -r requirements.txt
```

### Configure API Keys

Create `configs/.env` file:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_key

# Claude Configuration  
ANTHROPIC_API_KEY=your_claude_key

# DeepSeek Configuration
DEEPSEEK_API_KEY=your_deepseek_key

# Azure OpenAI (Optional)
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_BASE_URL=your_azure_endpoint
AZURE_OPENAI_MODEL=gpt-4o

# Web Search APIs (Required for deep search functionality)
Serper_API_KEY=your_serper_key          # For Google search results
JINA_API_KEY=your_jina_key              # For web content extraction

```

#### API Applications Guide

**1. LLM APIs (Choose at least one):**

| Provider | Application Link | Notes |
|----------|------------------|--------|
| OpenAI | https://platform.openai.com/api-keys | GPT-4o models |
| Claude | https://console.anthropic.com/ | Claude-3.5 Sonnet |
| DeepSeek | https://platform.deepseek.com/ | DeepSeek-V3 models |

**2. Web Search APIs (Required for web functionality):**

| Service | Application Link | Usage |
|---------|------------------|--------|
| **Serper** | https://serper.dev/login | Real-time Google search results |
| **Jina AI** | https://jina.ai/ | Web content extraction and processing |

**3. Additional APIs (Optional):**

| Service | Application Link | Usage |
|---------|------------------|--------|
| GitHub | https://github.com/settings/tokens | Repository search and analysis |


#### Manual Configuration Steps

1. **Copy configuration template**:
   ```bash
   cp configs/oai_config_exmaple.py configs/oai_config.py
   ```

2. **Edit configuration file**:
   ```bash
   # Edit with your actual API keys
   nano configs/oai_config.py
   ```

3. **Create environment file (alternative)**:
   ```bash
   # Create configs/.env with your API keys (optional)
   nano configs/.env
   ```

---

## 🎯 Usage

### Frontend Mode

**Start Web Interface**:
```bash
python launcher.py --mode frontend
```
**Access**: Open your browser and go to `http://localhost:8501`

**Custom Port**:
```bash
python launcher.py --mode frontend --streamlit-port 8588
```
**Access**: Open your browser and go to `http://localhost:8588`


**Features**:
- 🌐 Interactive web chat interface
- 📁 File upload and management
- 👥 Multi-user session support
- 📊 Visual task progress tracking

### Backend Mode

**Unified Assistant** (Recommended):
```bash
python launcher.py --mode backend --backend-mode unified
```

**Specialized Modes**:
```bash
# Deep Search & Web Research
python launcher.py --mode backend --backend-mode deepsearch

# General Programming Assistant  
python launcher.py --mode backend --backend-mode general_assistant

# Repository-Specific Tasks
python launcher.py --mode backend --backend-mode repository_agent
```

### Shell Script Shortcuts

```bash
# Frontend
bash run.sh frontend

# Backend modes
bash run.sh backend unified
bash run.sh backend deepsearch  
bash run.sh backend general_assistant
bash run.sh backend repository_agent
```

---

## 💻 Advanced Usage

### Basic Programming Interface

```python
from core.agent_scheduler import RepoMasterAgent

# Simple task execution
task = "Transform this portrait into Van Gogh style using content.jpg and style.jpg"
result = repo_master.solve_task_with_repo(task)
```

For detailed programming examples, see our [Documentation](docs/).

---

## ⚙️ Configuration

### API Providers

| Provider | API Type | Usage |
|----------|----------|-------|
| OpenAI | `openai` | `--api-type openai` |
| Claude | `claude` / `basic_claude4` | `--api-type basic_claude4` |
| DeepSeek | `deepseek` / `basic_deepseek_r1` | `--api-type basic_deepseek_r1` |
| Basic | `basic` | `--api-type basic` (default) |

### Advanced Parameters

```bash
# Model parameters
python launcher.py --mode backend --temperature 0.2 --max-turns 50

# Working directory
python launcher.py --mode backend --work-dir /custom/workspace

# Logging
python launcher.py --mode backend --log-level DEBUG

# Docker execution (experimental)
python launcher.py --mode backend --use-docker
```

### Environment Variables

```bash
# Set working directory
export REPOMASTER_WORK_DIR="/custom/workspace"

# Set log level  
export REPOMASTER_LOG_LEVEL="DEBUG"

# Set default API provider
export REPOMASTER_API_TYPE="basic_claude4"
```

---

## 📚 Use Cases

### 🤖 AI/ML Tasks
**"Train an image classifier on CIFAR-10 dataset using transfer learning"**
- Automatically finds relevant ML repositories and frameworks
- Sets up complete training pipeline with best practices
- Handles data loading, model configuration, and training execution

### 📄 Data Processing  
**"Extract tables from PDF reports and convert to structured CSV format"**
- Discovers PDF processing libraries and tools
- Implements extraction pipeline with error handling
- Outputs clean, structured data in the desired format

### 🌐 Web Development
**"Create a REST API for user authentication with JWT tokens"**
- Searches for authentication frameworks and security libraries
- Generates production-ready API with proper security practices
- Includes documentation and testing examples

### 👁️ Computer Vision
**"Detect and count objects in surveillance video footage"**
- Finds state-of-the-art object detection models
- Implements video processing pipeline with optimization
- Provides detailed analysis results and visualizations

---

## 🚀 Service Management

### Background Services

```bash
# Start as daemon
bash run.sh daemon

# Check status
bash run.sh status

# Stop services
bash run.sh stop

# Restart
bash run.sh restart
```

### Logs

```bash
# View logs
tail -f logs/streamlit.log      # Frontend logs
tail -f logs/backend.log        # Backend logs
tail -f logs/$(date +%Y%m%d).log # Daily logs
```

---

## 🔧 Troubleshooting

### Common Issues

**Port already in use**:
```bash
# Check port usage
lsof -i:8501

# Kill process
pkill -f streamlit

# Use different port
python launcher.py --mode frontend --streamlit-port 8502
```

**Missing dependencies**:
```bash
# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

**API key issues**:
```bash
# Check environment file
cat configs/.env

# Test API connection
python -c "import openai; print('OpenAI OK')"
```

### Performance Optimization

- **Recommended APIs**: Use `basic_claude4` for best results
- **Work Directory**: Ensure sufficient disk space in work directory
- **Network**: Stable connection required for repository cloning
- **Memory**: 8GB+ RAM recommended for large repositories

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md).

### Development Setup

```bash
git clone https://github.com/your-org/RepoMaster.git
cd RepoMaster
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
# Run configuration tests
python test_config.py

# Run full test suite
pytest tests/

# Run specific benchmark
python -m core.git_task --config configs/gittaskbench.yaml
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support

- 📧 **Email**: wanghuacan17@mails.ucas.ac.cn
- 🐛 **Issues**: [GitHub Issues](https://github.com/QuantaAlpha/RepoMaster/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/QuantaAlpha/RepoMaster/discussions)
- 📖 **Documentation**: [Full Documentation](docs/)

---

## 🙏 Acknowledgments

Special thanks to:
- [AutoGen](https://github.com/microsoft/autogen) - Multi-agent framework
- [OpenHands](https://github.com/All-Hands-AI/OpenHands) - Software engineering agents
- [SWE-Agent](https://github.com/princeton-nlp/SWE-agent) - GitHub issue resolution
- [MLE-Bench](https://github.com/openai/mle-bench) - ML engineering benchmarks

---

<div align="center">

**⭐ If RepoMaster helps you, please give us a star!**

Made with ❤️ by the RepoMaster Team

</div>
