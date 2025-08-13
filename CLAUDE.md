# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Architecture

RepoMaster is an AI-powered code repository analysis and task execution framework built with Python and Streamlit. The system combines LLM agents, code analysis tools, and a web interface to automatically analyze repositories and execute complex programming tasks.

### Core Components

- **Core Engine** (`core/`): Repository analysis, code exploration, and task scheduling
  - `agent_scheduler.py`: Main task scheduler with repository-first execution strategy
  - `tree_code.py`: AST-based code tree building using tree-sitter
  - `agent_code_explore.py`: Code exploration agent with semantic search
  - `git_task.py`: Task management and parallel execution framework

- **Agent Services** (`services/`): Specialized AI agents for different tasks
  - `agents/deepsearch_2agents.py`: Deep search agent for code analysis
  - `agents/agent_general_coder.py`: General-purpose coding agent
  - `autogen_upgrade/base_agent.py`: Enhanced AutoGen agents with code execution

- **Frontend Interface** (`frontend_st/`): Streamlit-based web application
  - `app_autogen_enhanced.py`: Main web interface with chat and file browser
  - `call_agent.py`: Agent orchestration and communication layer

- **Utility Libraries** (`utils/`): Supporting tools and configurations
  - `toolkits.py`: Tool registration and management
  - `tool_streamlit.py`: Streamlit-specific utilities
  - `web_search_agent/`: Web search integration

### Data Flow Architecture

1. **Task Input**: Tasks defined via YAML config or Streamlit interface
2. **Repository Discovery**: Search for relevant GitHub repositories
3. **Code Analysis**: Build AST trees, extract module importance, create embeddings
4. **Agent Execution**: Multi-agent collaboration with specialized roles
5. **Result Generation**: Code execution, file output, and user feedback

## Development Commands

### Environment Setup
```bash
# Install core dependencies
pip install -r enviroment/requirements.txt

# Install additional LLM dependencies  
pip install -r enviroment/llm_requirements.txt

# Install basic utilities
pip install -r requirement.txt

# Set up environment variables
cp configs/.env.example configs/.env  # Configure API keys
```

### Running the Application
```bash
# Start the Streamlit web interface (main entry point)
streamlit run frontend_st/app_autogen_enhanced.py

# Set PYTHONPATH for module imports
export PYTHONPATH=$(pwd):$PYTHONPATH

# Alternative: Run specific core modules for testing
python core/agent_scheduler.py
python core/tool_code_explorer.py
```

### Task Execution Examples
```bash
# Run tasks from YAML configuration
python tasks/git_bench/2_run_git_new.py --config config/sample_tasks.yaml

# Run with parallel processing
python tasks/git_bench/2_run_git_new.py --config config/sample_tasks.yaml --parallel --parallel_workers 4

# Run specific benchmark tasks
python tasks/mle_bench/1_run_mle.py
```

## Configuration Requirements

### Required Environment Variables (.env file)
```bash
# Core LLM APIs
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Optional: Azure OpenAI
AZURE_OPENAI_MODEL=your_model
AZURE_OPENAI_API_KEY=your_key  
AZURE_OPENAI_BASE_URL=your_endpoint
```

### LLM Model Configuration
- Primary models: GPT-4, Claude-3.5-Sonnet, Grok-3-Beta
- Fallback configuration in `configs/config.py`
- Temperature: 0.5, Timeout: 120 seconds
- Code execution: Local environment (Docker disabled by default)

## Key Workflows

### Repository Analysis Workflow
1. Clone/access target repository
2. Build code tree using tree-sitter (`core/tree_code.py`)
3. Extract module importance and dependencies
4. Create searchable code embeddings
5. Generate LLM-friendly repository summary

### Multi-Agent Task Execution
1. **Task Scheduler** analyzes requirements and creates execution plan
2. **Repository Search** finds relevant codebases using GitHub API
3. **Code Explorer** analyzes repository structure and key modules
4. **General Coder** executes specific programming tasks
5. **Result Validation** ensures task completion and quality

### Code Execution Environment
- Virtual environment isolation (`.venvs/persistent_venv`)
- Automatic dependency installation and error recovery
- File monitoring and result tracking
- Integration with AutoGen conversation framework

## Testing and Benchmarks

### Available Test Suites
```bash
# Git-based repository tasks
python tasks/git_bench/1_prepare_data.py
python tasks/git_bench/2_run_git_new.py

# Machine learning benchmarks  
python tasks/mle_bench/1_run_mle.py
python tasks/mle_bench/3_final_stat.py
```

### Performance Monitoring
- Token usage tracking in `tasks/mle_bench/cnt_token/`
- Execution logs in `logs/` directory
- Result statistics and analysis tools

## Important Implementation Notes

- All code execution uses virtual environments for safety
- Repository cloning limited by `--max_repo` parameter (default: 5)
- Task timeout configurable via YAML (default: 1800 seconds)
- Parallel processing supported with worker pool management
- Error recovery mechanisms for pip installation failures
- Automatic file description insertion for generated outputs

## Security Considerations

- Local code execution only (Docker support available but disabled)
- Environment variable isolation
- Repository size limits to prevent resource exhaustion
- Virtual environment cleanup between tasks