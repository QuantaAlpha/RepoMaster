TASK_PROMPT = """## 任务描述
{task_description}

## 可用仓库
仓库名称: {repo_name}
仓库路径 (绝对): {repo_path}
理解指南: {repo_understanding_guidelines}

## 文件路径
输入文件路径和描述:
{input_data_info}

输出：
输出文件目录: {output_dir_path}, 如果只有一个文件，就以 `output` 命名; 如果存在多个以 `output_01`开始命名，格式根据需求指定。

## 补充说明
**核心目标**: 快速理解和分析代码仓库，生成并执行必要的代码或调用工具，以高效、准确地完成用户指定的任务。
"""