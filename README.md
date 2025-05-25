# RepoMaster

RepoMaster是一个代码仓库任务执行工具，能够自动分析并在本地或GitHub仓库上执行各种任务。

## 功能特点

- 支持本地仓库和GitHub仓库
- 基于YAML的简洁任务配置
- 支持并行任务执行
- 自动环境准备和数据集处理
- 支持虚拟环境隔离

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 创建任务配置文件

在`config`目录下创建一个YAML配置文件，例如`my_tasks.yaml`：

```yaml
tasks:
  task_1:
    repo:
      type: local
      path: /path/to/local/repository
    description: |
      请分析{repo_path}中的代码，并完成以下任务：
      1. 分析代码结构和主要功能
      2. 生成分析报告，保存到{output_path}目录
```

### 运行任务

```bash
python RepoMaster/tasks/1_run_git.py --config RepoMaster/config/my_tasks.yaml
```

要启用并行模式：

```bash
python RepoMaster/tasks/1_run_git.py --config RepoMaster/config/my_tasks.yaml --parallel --parallel_workers 4
```

## 配置文件格式

YAML配置文件定义如下：

```yaml
tasks:
  task_id:                     # 任务唯一标识符
    repo:                      # 仓库信息
      type: local | github     # 仓库类型：本地或GitHub
      path: /path/to/repo      # 如果是本地仓库，指定路径
      url: https://...         # 如果是GitHub仓库，指定URL
    
    description: |             # 任务描述，支持多行文本
      任务描述内容，可以包含占位符：
      {repo_path}：仓库路径
      {output_path}：输出路径
      {input_path}：输入数据路径
    
    data:                      # 数据相关配置（可选）
      input_path: /path/...    # 输入数据路径
      input_info:              # 输入数据信息（可选）
        - name: "数据名称"
          path: "数据路径"
          description: "数据说明"
    
    parameters:                # 额外参数（可选）
      timeout: 1800            # 任务超时时间（秒）
      priority: 1              # 任务优先级
```

## 命令行参数

```
--config            指定YAML配置文件路径（必需）
--retry             任务失败后重试次数（默认：2）
--max_repo          最大处理仓库数量（默认：5）
--parallel          使用并行模式执行任务
--parallel_workers  并行工作进程数（默认：4）
```

## 示例

查看`RepoMaster/config/sample_tasks.yaml`获取完整的配置示例。