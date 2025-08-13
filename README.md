# RepoMaster

RepoMaster is a code repository task execution tool that can automatically analyze and execute various tasks on local or GitHub repositories.

## Features

- Support for local repositories and GitHub repositories
- Concise task configuration based on YAML
- Support for parallel task execution
- Automatic environment preparation and dataset processing
- Support for virtual environment isolation

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Create Task Configuration File

Create a YAML configuration file in the `config` directory, for example `my_tasks.yaml`:

```yaml
tasks:
  task_1:
    repo:
      type: local
      path: /path/to/local/repository
    description: |
      Please analyze the code in {repo_path} and complete the following tasks:
      1. Analyze code structure and main functionality
      2. Generate analysis report and save to {output_path} directory
```

### Run Tasks

```bash
python RepoMaster/tasks/1_run_git.py --config RepoMaster/config/my_tasks.yaml
```

To enable parallel mode:

```bash
python RepoMaster/tasks/1_run_git.py --config RepoMaster/config/my_tasks.yaml --parallel --parallel_workers 4
```

## Configuration File Format

YAML configuration file is defined as follows:

```yaml
tasks:
  task_id:                     # Unique task identifier
    repo:                      # Repository information
      type: local | github     # Repository type: local or GitHub
      path: /path/to/repo      # If local repository, specify path
      url: https://...         # If GitHub repository, specify URL
    
    description: |             # Task description, supports multi-line text
      Task description content, can include placeholders:
      {repo_path}: Repository path
      {output_path}: Output path
      {input_path}: Input data path
    
    data:                      # Data-related configuration (optional)
      input_path: /path/...    # Input data path
      input_info:              # Input data information (optional)
        - name: "Data Name"
          path: "Data Path"
          description: "Data Description"
    
    parameters:                # Additional parameters (optional)
      timeout: 1800            # Task timeout (seconds)
      priority: 1              # Task priority
```

## Command Line Arguments

```
--config            Specify YAML configuration file path (required)
--retry             Number of retries after task failure (default: 2)
--max_repo          Maximum number of repositories to process (default: 5)
--parallel          Use parallel mode to execute tasks
--parallel_workers  Number of parallel worker processes (default: 4)
```

## Examples

See `RepoMaster/config/sample_tasks.yaml` for complete configuration examples.