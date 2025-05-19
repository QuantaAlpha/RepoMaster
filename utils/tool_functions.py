#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict, Union, Any, Tuple, Callable


def read_file(target_file: str, offset: int = None, limit: int = None,
             should_read_entire_file: bool = False) -> Dict[str, Any]:
    """
    读取文件内容。
    
    Args:
        target_file: 要读取的文件路径。可以使用相对于工作区的相对路径或绝对路径。
        offset: 开始读取的行偏移量（1-indexed）
        limit: 要读取的行数
        should_read_entire_file: 是否读取整个文件
        
    Returns:
        包含文件内容和元数据的字典
    
    Note:
        每次调用此命令时，应该:
        1) 评估所查看的内容是否足以继续任务
        2) 如果需要读取文件的多个部分，最好一次调用工具并指定更大的行范围
        3) 如果已找到要编辑的位置或合理的答案，请不要继续调用工具
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(target_file):
            return {"error": f"文件 {target_file} 不存在"}
        
        # 读取整个文件
        with open(target_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        # 决定要读取的行范围
        if should_read_entire_file:
            content_lines = all_lines
            start_line = 1
            end_line = total_lines
        else:
            # 默认值和验证
            if offset is None:
                offset = 1
            else:
                # 确保offset是1-indexed
                offset = max(1, offset)
            
            if limit is None:
                # 默认读取150行(最小值)
                limit = 150
            
            # 确保不超过最大行数限制(250)和最小行数要求(150)
            limit = max(min(limit, 250), 150)
            
            # 计算实际的开始和结束行(0-indexed)
            start_idx = offset - 1  # 转换为0-indexed
            end_idx = min(start_idx + limit, total_lines)
            
            # 调整以满足最小行数要求
            if end_idx - start_idx < 150 and total_lines >= 150:
                if start_idx + 150 <= total_lines:
                    end_idx = start_idx + 150
                else:
                    # 从末尾向前取150行
                    end_idx = total_lines
                    start_idx = max(0, end_idx - 150)
            
            # 提取指定范围的行
            content_lines = all_lines[start_idx:end_idx]
            start_line = start_idx + 1  # 转回1-indexed
            end_line = end_idx
        
        # 构建摘要信息
        summary_before = ""
        if start_line > 1:
            summary_before = f"[行 1-{start_line-1} 的内容未显示]"
        
        summary_after = ""
        if end_line < total_lines:
            summary_after = f"[行 {end_line+1}-{total_lines} 的内容未显示]"
        
        # 构建结果
        result = {
            "content": "".join(content_lines),
            "metadata": {
                "file_path": target_file,
                "total_lines": total_lines,
                "viewed_lines": {
                    "start": start_line,
                    "end": end_line
                }
            }
        }
        
        if summary_before:
            result["summary_before"] = summary_before
        if summary_after:
            result["summary_after"] = summary_after
            
        return result
        
    except Exception as e:
        return {"error": f"读取文件时出错: {str(e)}"}


def run_terminal_cmd(command: str, is_background: bool, explanation: str = None) -> Dict[str, Any]:
    """
    代表用户提出要运行的命令。
    
    Args:
        command: 要执行的终端命令
        is_background: 命令是否应该在后台运行
        explanation: 关于为什么需要运行此命令以及它如何有助于目标的一句话解释
        
    Returns:
        包含命令执行状态的字典
        
    Note:
        - 用户必须在命令执行前批准它
        - 用户可能会拒绝或修改命令
        - 在用户批准之前，命令不会执行
    """
    # 在实际环境中，此函数会提出命令给用户批准
    # 此处我们只返回命令提议信息
    
    result = {
        "status": "waiting_for_approval",
        "command": command,
        "is_background": is_background
    }
    
    if explanation:
        result["explanation"] = explanation
        
    return result


def list_dir(relative_workspace_path: str, explanation: str = None) -> Dict[str, Any]:
    """
    列出目录的内容。
    
    Args:
        relative_workspace_path: 要列出内容的路径，相对于工作区根目录
        explanation: 关于为什么使用该工具以及它如何有助于目标的一句话解释
        
    Returns:
        包含目录内容的字典
    """
    try:
        # 检查目录是否存在
        if not os.path.exists(relative_workspace_path):
            return {"error": f"目录 {relative_workspace_path} 不存在"}
        
        if not os.path.isdir(relative_workspace_path):
            return {"error": f"{relative_workspace_path} 不是一个目录"}
        
        # 获取目录内容
        contents = []
        
        for item in os.listdir(relative_workspace_path):
            item_path = os.path.join(relative_workspace_path, item)
            
            # 获取文件大小和行数（对于文件）
            if os.path.isfile(item_path):
                try:
                    size = os.path.getsize(item_path)
                    size_str = f"{size/1024:.1f}KB" if size >= 1024 else f"{size}B"
                    
                    # 尝试计算行数
                    line_count = 0
                    try:
                        with open(item_path, 'r', encoding='utf-8') as f:
                            for _ in f:
                                line_count += 1
                    except:
                        line_count = None
                    
                    lines_str = f"{line_count} lines" if line_count is not None else "? lines"
                    
                    contents.append({
                        "type": "file",
                        "name": item,
                        "size": size_str,
                        "lines": lines_str
                    })
                except:
                    contents.append({
                        "type": "file",
                        "name": item,
                        "size": "未知",
                        "lines": "未知"
                    })
            else:
                # 目录
                try:
                    item_count = len(os.listdir(item_path))
                    contents.append({
                        "type": "directory",
                        "name": item,
                        "items": f"{item_count} items"
                    })
                except:
                    contents.append({
                        "type": "directory",
                        "name": item,
                        "items": "? items"
                    })
        
        result = {
            "path": relative_workspace_path,
            "contents": contents
        }
        
        if explanation:
            result["explanation"] = explanation
            
        return result
        
    except Exception as e:
        return {"error": f"列出目录内容时出错: {str(e)}"}


def grep_search(query: str, case_sensitive: bool = False, 
               include_pattern: str = None, exclude_pattern: str = None,
               explanation: str = None) -> Dict[str, Any]:
    """
    基于文本的正则表达式搜索，查找文件或目录中的精确模式匹配。
    
    Args:
        query: 要搜索的正则表达式模式
        case_sensitive: 搜索是否应该区分大小写
        include_pattern: 要包含的文件的Glob模式(例如 '*.ts' 表示TypeScript文件)
        exclude_pattern: 要排除的文件的Glob模式
        explanation: 关于为什么使用该工具以及它如何有助于目标的一句话解释
        
    Returns:
        包含搜索结果的字典
    """
    try:
        # 构建ripgrep命令
        cmd = ["rg"]
        
        # 添加选项
        if not case_sensitive:
            cmd.append("-i")
        
        # 限制最大结果数
        cmd.extend(["-m", "50"])
        
        # 添加包含/排除模式
        if include_pattern:
            cmd.extend(["-g", include_pattern])
        
        if exclude_pattern:
            cmd.extend(["-g", f"!{exclude_pattern}"])
        
        # 添加查询
        cmd.append(query)
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 解析结果
        matches = []
        for line in result.stdout.strip().split("\n"):
            if line:
                # 尝试解析ripgrep输出格式：file:line:content
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    file_path, line_num, content = parts[0], parts[1], parts[2]
                    matches.append({
                        "file": file_path,
                        "line": int(line_num),
                        "content": content
                    })
                else:
                    matches.append({"raw_match": line})
        
        search_result = {
            "query": query,
            "case_sensitive": case_sensitive,
            "matches": matches,
            "match_count": len(matches)
        }
        
        if include_pattern:
            search_result["include_pattern"] = include_pattern
        
        if exclude_pattern:
            search_result["exclude_pattern"] = exclude_pattern
            
        if explanation:
            search_result["explanation"] = explanation
            
        return search_result
        
    except Exception as e:
        return {"error": f"执行grep搜索时出错: {str(e)}"}


def edit_file(target_file: str, instructions: str, code_edit: str) -> Dict[str, Any]:
    """
    提出对现有文件的编辑。
    
    Args:
        target_file: 要修改的目标文件
        instructions: 描述编辑内容的单句指令
        code_edit: 指定仅精确的要编辑的代码行
        
    Returns:
        包含编辑状态的字典
    
    Note:
        编辑时，应指定每个编辑的序列，并使用特殊注释 `// ... existing code ...` 
        表示编辑行之间未更改的代码。
    """
    # 检查文件是否存在
    if not os.path.exists(target_file):
        return {"error": f"文件 {target_file} 不存在"}
    
    # 在实际环境中，此函数会提交编辑给应用模型
    # 此处我们只返回编辑提议信息
    
    return {
        "status": "edit_proposed",
        "target_file": target_file,
        "instructions": instructions,
        "edit_length": len(code_edit.split("\n"))
    }


def file_search(query: str, explanation: str) -> Dict[str, Any]:
    """
    基于模糊匹配对文件路径进行快速文件搜索。
    
    Args:
        query: 要搜索的模糊文件名
        explanation: 关于为什么使用该工具以及它如何有助于目标的一句话解释
        
    Returns:
        包含搜索结果的字典
    """
    try:
        # 使用find命令执行模糊搜索
        cmd = ["find", ".", "-type", "f", "-name", f"*{query}*"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 解析结果
        found_files = result.stdout.strip().split("\n")
        found_files = [f for f in found_files if f]  # 过滤空行
        
        # 限制结果数量
        if len(found_files) > 10:
            found_files = found_files[:10]
        
        return {
            "query": query,
            "files": found_files,
            "count": len(found_files),
            "explanation": explanation
        }
        
    except Exception as e:
        return {"error": f"执行文件搜索时出错: {str(e)}"}


def delete_file(target_file: str, explanation: str = None) -> Dict[str, Any]:
    """
    删除指定路径的文件。
    
    Args:
        target_file: 要删除的文件路径，相对于工作区根目录
        explanation: 关于为什么使用该工具以及它如何有助于目标的一句话解释
        
    Returns:
        包含删除操作状态的字典
    
    Note:
        如果出现以下情况，操作将优雅地失败：
        - 文件不存在
        - 出于安全原因操作被拒绝
        - 文件无法删除
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(target_file):
            return {"error": f"文件 {target_file} 不存在", "success": False}
        
        # 检查是否为文件
        if not os.path.isfile(target_file):
            return {"error": f"{target_file} 不是一个文件", "success": False}
        
        # 删除文件
        os.remove(target_file)
        
        result = {
            "success": True,
            "target_file": target_file,
            "message": f"文件 {target_file} 已成功删除"
        }
        
        if explanation:
            result["explanation"] = explanation
            
        return result
        
    except Exception as e:
        return {"error": f"删除文件时出错: {str(e)}", "success": False}


def reapply(target_file: str) -> Dict[str, Any]:
    """
    调用更智能的模型来对指定文件应用上次编辑。
    
    Args:
        target_file: 要重新应用上次编辑的文件的相对路径
        
    Returns:
        包含重新应用状态的字典
        
    Note:
        仅当编辑文件工具调用的结果不符合预期时，才应使用此工具，
        这表明应用更改的模型不够智能，无法遵循您的指示。
    """
    # 检查文件是否存在
    if not os.path.exists(target_file):
        return {"error": f"文件 {target_file} 不存在"}
    
    # 在实际环境中，此函数会调用更智能的模型重新应用编辑
    # 此处我们只返回重新应用的提议信息
    
    return {
        "status": "reapply_requested",
        "target_file": target_file,
        "message": "已请求重新应用上次编辑"
    }


def main():
    """
    测试各个工具函数的主函数
    """
    print("=== 测试工具函数 ===\n")
    
    # 创建测试文件
    test_file = "test_file.txt"
    with open(test_file, "w") as f:
        f.write("\n".join([f"Line {i}" for i in range(1, 301)]))
    
    print("1. 测试 read_file 函数")
    # 测试读取部分文件
    result = read_file(test_file, offset=50, limit=200)
    print(f"读取文件 {test_file} 的第50-250行:")
    print(f"开始行: {result['metadata']['viewed_lines']['start']}")
    print(f"结束行: {result['metadata']['viewed_lines']['end']}")
    print(f"总行数: {result['metadata']['total_lines']}")
    if 'summary_before' in result:
        print(result['summary_before'])
    print(f"内容的前几行:\n{result['content'].split('\n')[:5]}")
    if 'summary_after' in result:
        print(result['summary_after'])
    
    # 测试读取整个文件
    result = read_file(test_file, should_read_entire_file=True)
    print(f"\n读取整个文件 {test_file}:")
    print(f"开始行: {result['metadata']['viewed_lines']['start']}")
    print(f"结束行: {result['metadata']['viewed_lines']['end']}")
    print(f"总行数: {result['metadata']['total_lines']}")
    print(f"内容的前几行:\n{result['content'].split('\n')[:5]}")
    
    print("\n2. 测试 run_terminal_cmd 函数")
    result = run_terminal_cmd("ls -la", False, "列出当前目录的所有文件和详细信息")
    print(f"命令: {result['command']}")
    print(f"后台执行: {result['is_background']}")
    print(f"状态: {result['status']}")
    print(f"解释: {result.get('explanation', '无')}")
    
    print("\n3. 测试 list_dir 函数")
    result = list_dir(".", "探索当前目录结构")
    print(f"路径: {result['path']}")
    print(f"内容数量: {len(result['contents'])}")
    print("前几项内容:")
    for item in result['contents'][:3]:
        if item['type'] == 'file':
            print(f"  文件: {item['name']} ({item['size']}, {item['lines']})")
        else:
            print(f"  目录: {item['name']} ({item['items']})")
    
    print("\n4. 测试 edit_file 函数")
    edit_content = """// ... existing code ...
def new_function():
    print("This is a new function")
    return True
// ... existing code ..."""
    result = edit_file(test_file, "添加一个新的函数", edit_content)
    print(f"目标文件: {result['target_file']}")
    print(f"指令: {result['instructions']}")
    print(f"编辑行数: {result['edit_length']}")
    print(f"状态: {result['status']}")
    
    print("\n5. 测试 file_search 函数")
    # 创建几个测试文件
    os.makedirs("test_dir", exist_ok=True)
    with open("test_dir/test_file1.py", "w") as f:
        f.write("print('Hello')")
    with open("test_dir/another_test.py", "w") as f:
        f.write("print('World')")
    
    result = file_search("test", "寻找包含'test'的文件")
    print(f"查询: {result['query']}")
    print(f"找到的文件数量: {result['count']}")
    print("找到的文件:")
    for file in result['files']:
        print(f"  {file}")
    
    print("\n6. 测试 delete_file 函数")
    temp_file = "temp_file_to_delete.txt"
    with open(temp_file, "w") as f:
        f.write("This file will be deleted")
    
    result = delete_file(temp_file, "删除临时文件")
    print(f"目标文件: {result['target_file']}")
    print(f"成功: {result['success']}")
    print(f"消息: {result['message']}")
    
    # 清理测试文件
    try:
        os.remove(test_file)
        os.remove("test_dir/test_file1.py")
        os.remove("test_dir/another_test.py")
        os.rmdir("test_dir")
    except:
        pass


if __name__ == "__main__":
    main() 