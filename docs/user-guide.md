# RepoMaster User Guide

This comprehensive guide provides everything you need to use RepoMaster effectively, from basic configuration to advanced usage patterns.

## 📋 Table of Contents

- [🚀 Getting Started](#-getting-started)
- [💻 Usage Modes](#-usage-modes)
- [🔧 Advanced Usage](#-advanced-usage)
- [📝 Use Cases](#-use-cases)
- [📖 Running Tests](#-running-tests)

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Git
- Internet connection for repository cloning

### Installation
```bash
git clone https://github.com/QuantaAlpha/RepoMaster.git
cd RepoMaster
pip install -r requirements.txt
```

### Basic Configuration
Create `configs/.env` file with your API keys:
```bash
# Set the default API provider (openai, claude, deepseek, azure_openai)
DEFAULT_API_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=openai_model

# Claude Configuration  
ANTHROPIC_API_KEY=your_claude_key
ANTHROPIC_MODEL=claude_model

# DeepSeek Configuration
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek_model

# Google Gemini Configuration
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini_model

# Web Search APIs (Required for deep search functionality)
Serper_API_KEY=your_serper_key          # For Google search results
JINA_API_KEY=your_jina_key              # For web content extraction
```

---

## 💻 Usage Modes

### Frontend Mode (Web Interface)

Launch the interactive web interface for multi-user access and visual interaction:

```bash
python launcher.py --mode frontend
# Access: http://localhost:8501
```

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

## 🔧 Advanced Usage

### Basic Programming Interface

```python
from core.agent_scheduler import RepoMasterAgent

# Simple task execution
task = "Transform this portrait into Van Gogh style using content.jpg and style.jpg"
result = repo_master.solve_task_with_repo(task)
```

For detailed programming examples, see our [Documentation](../docs/).

---

## 📝 Use Cases

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

## 📖 Running Tests

```bash
# Run configuration tests
python test_config.py

# Run full test suite
pytest tests/

# Run specific benchmark
python -m core.git_task --config configs/gittaskbench.yaml
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
