#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python包错误提取工具

此脚本用于从Python执行结果或日志文件中提取与包相关的错误，
并提供详细的错误分析和修复建议。

使用方法：
1. 作为模块导入:
   from package_error_extractor import PackageErrorExtractor
   extractor = PackageErrorExtractor()
   errors = extractor.extract_errors_from_text(error_text)

2. 作为脚本直接运行:
   python package_error_extractor.py
   
   这将运行内置的测试样例，展示各种包错误的识别和分析。
"""

import re
import sys
import os
from typing import List, Dict, Tuple, Optional, Union
import json


class PackageErrorExtractor:
    """Python包错误提取器类"""
    
    def __init__(self):
        """初始化错误模式和分类"""
        # 错误模式字典: {错误类型: (正则模式, 捕获组说明)}
        self.error_patterns = {
            "missing_package": (
                r"(?:ImportError|ModuleNotFoundError): No module named ['\"]([^'\"]+)['\"]",
                ["package_name"]
            ),
            "import_name_error": (
                r"(?:ImportError): cannot import name ['\"]([^'\"]+)['\"] from ['\"]([^'\"]+)['\"]",
                ["component_name", "package_name"]
            ),
            "attribute_error": (
                r"(?:AttributeError): module ['\"]([^'\"]+)['\"] has no attribute ['\"]([^'\"]+)['\"]",
                ["package_name", "attribute_name"]
            ),
            "version_conflict": (
                r"(?:.*?)requires ([^\s]+) ([^,]+), but ([^\s]+) is installed",
                ["package_name", "required_version", "installed_version"]
            ),
            "syntax_error_in_package": (
                r"(?:SyntaxError|IndentationError)(?:.*?)File ['\"](?:.*?)site-packages[/\\]([^/\\]+)[/\\](?:.*?)['\"], line (\d+)",
                ["package_name", "line_number"]
            ),
            "import_error_in_package": (
                r"(?:ImportError): (?:.*?)site-packages[/\\]([^/\\]+)[/\\](?:.*?): ([^\"'\n]+)",
                ["package_name", "error_details"]
            ),
            "dependency_error": (
                r"(?:.*?)([^\s]+) requires ([^\s]+), which is not installed",
                ["package_name", "dependency_name"]
            ),
            "dll_load_error": (
                r"(?:ImportError): DLL load failed while importing ([^:]+): ([^\"'\n]+)",
                ["module_name", "error_details"]
            ),
            "permission_error": (
                r"(?:PermissionError)(?:.*?)site-packages[/\\]([^/\\]+)[/\\]",
                ["package_name"]
            ),
            "pkg_resources_error": (
                r"(?:pkg_resources\.DistributionNotFound): The '([^']+)(?:[^']*?)' distribution was not found",
                ["package_name"]
            ),
            "incompatible_version": (
                r"(?:.*?)([^\s]+) ([^\s]+) is incompatible with ([^\s]+) ([^\s]+)",
                ["package1", "version1", "package2", "version2"]
            ),
        }
        
        # 修复建议字典
        self.fix_suggestions = {
            "missing_package": "使用 pip 安装缺失的包: pip install {package_name}",
            "import_name_error": "检查包 {package_name} 的版本是否正确。该组件 {component_name} 可能在新版本中添加或在当前版本中不存在。",
            "attribute_error": "检查包 {package_name} 的文档，确认 {attribute_name} 是否存在或需要额外导入。",
            "version_conflict": "安装所需版本的包: pip install {package_name}=={required_version} 或使用虚拟环境隔离依赖。",
            "syntax_error_in_package": "包 {package_name} 可能安装不完整或损坏。尝试重新安装: pip uninstall {package_name} && pip install {package_name}",
            "import_error_in_package": "包 {package_name} 内部依赖问题: {error_details}。检查其依赖是否完整安装。",
            "dependency_error": "安装缺失的依赖: pip install {dependency_name}",
            "dll_load_error": "模块 {module_name} 加载DLL失败: {error_details}。可能需要安装系统级依赖或VC++运行库。",
            "permission_error": "包 {package_name} 访问权限问题。尝试以管理员/sudo权限运行或检查文件权限。",
            "pkg_resources_error": "分发包 {package_name} 未找到。尝试: pip install {package_name}",
            "incompatible_version": "包版本冲突: {package1} {version1} 与 {package2} {version2} 不兼容。创建虚拟环境或调整依赖版本。",
        }

    def extract_errors_from_text(self, text: str) -> List[Dict]:
        """从文本中提取所有包相关错误
        
        Args:
            text: 包含错误信息的文本
            
        Returns:
            错误信息列表，每项包含错误类型、匹配内容和相关详情
        """
        results = []
        
        # 对每个错误模式进行匹配
        for error_type, (pattern, capture_groups) in self.error_patterns.items():
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
            
            for match in matches:
                error_info = {
                    "error_type": error_type,
                    "match_text": match.group(0),
                    "details": {}
                }
                
                # 提取捕获组信息
                for i, group_name in enumerate(capture_groups, 1):
                    if i <= len(match.groups()):
                        error_info["details"][group_name] = match.group(i)
                
                # 根据错误类型和详情生成修复建议
                suggestion_template = self.fix_suggestions.get(error_type, "无可用修复建议")
                try:
                    error_info["suggestion"] = suggestion_template.format(**error_info["details"])
                except KeyError:
                    error_info["suggestion"] = "无法生成修复建议，详情不完整"
                
                # 获取错误上下文（前后各3行）
                error_line_match = re.search(r'(?:.*\n){0,3}' + re.escape(match.group(0)) + r'(?:\n.*){0,3}', text)
                if error_line_match:
                    error_info["context"] = error_line_match.group(0)
                
                results.append(error_info)
        
        return results

    def extract_errors_from_file(self, file_path: str) -> List[Dict]:
        """从文件中提取包相关错误
        
        Args:
            file_path: 错误日志文件路径
            
        Returns:
            错误信息列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.extract_errors_from_text(content)
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                return self.extract_errors_from_text(content)
            except Exception as e:
                print(f"读取文件时出错: {e}")
                return []
        except Exception as e:
            print(f"处理文件时出错: {e}")
            return []

    def get_error_summary(self, errors: List[Dict]) -> Dict:
        """生成错误摘要信息
        
        Args:
            errors: 错误信息列表
            
        Returns:
            包含错误摘要的字典
        """
        if not errors:
            return {"total_errors": 0, "error_types": {}}
        
        summary = {
            "total_errors": len(errors),
            "error_types": {},
            "affected_packages": set(),
        }
        
        for error in errors:
            error_type = error["error_type"]
            if error_type not in summary["error_types"]:
                summary["error_types"][error_type] = 0
            summary["error_types"][error_type] += 1
            
            # 收集受影响的包
            for key, value in error["details"].items():
                if "package" in key or "module" in key:
                    # 提取基础包名（去除子模块）
                    base_package = value.split('.')[0]
                    summary["affected_packages"].add(base_package)
        
        # 转换为列表以便JSON序列化
        summary["affected_packages"] = list(summary["affected_packages"])
        
        return summary

    def generate_fix_commands(self, errors: List[Dict]) -> Tuple[List[str], List[str]]:
        """生成可能的修复命令
        
        Args:
            errors: 错误信息列表
            install_packages: 可以在安装的包列表
            
        Returns:
            修复命令列表
        """
        fix_commands = []
        install_packages = []
        seen_packages = set()
        
        for error in errors:
            error_type = error["error_type"]
            details = error["details"]
            if error_type in ["missing_package", "version_conflict", "dependency_error", "pkg_resources_error", "syntax_error_in_package"]:
                install_packages.append(details["package_name"])
            if error_type == "missing_package" and "package_name" in details:
                package = details["package_name"]
                base_package = package.split('.')[0]  # 获取基础包名
                if base_package not in seen_packages:
                    fix_commands.append(f"pip install {base_package}")
                    seen_packages.add(base_package)
                    
            elif error_type == "dependency_error" and "dependency_name" in details:
                dependency = details["dependency_name"]
                if dependency not in seen_packages:
                    fix_commands.append(f"pip install {dependency}")
                    seen_packages.add(dependency)
                    
            elif error_type == "version_conflict" and all(k in details for k in ["package_name", "required_version"]):
                package = details["package_name"]
                version = details["required_version"]
                cmd = f"pip install {package}=={version}"
                if cmd not in fix_commands:
                    fix_commands.append(cmd)
                    
            elif error_type == "syntax_error_in_package" and "package_name" in details:
                package = details["package_name"]
                if package not in seen_packages:
                    fix_commands.append(f"pip uninstall -y {package} && pip install --no-cache-dir {package}")
                    seen_packages.add(package)
        
        # 添加创建虚拟环境的建议
        if fix_commands:
            fix_commands.insert(0, "# 建议在虚拟环境中安装依赖，以避免版本冲突")
            fix_commands.insert(1, "python -m venv venv")
            fix_commands.insert(2, "# Windows: venv\\Scripts\\activate")
            fix_commands.insert(3, "# Linux/Mac: source venv/bin/activate")
            
        return fix_commands, install_packages

    def print_errors(self, errors: List[Dict]):
        """打印错误信息到控制台
        
        Args:
            errors: 错误信息列表
        """
        if not errors:
            print("未发现任何包相关错误。")
            return
            
        summary = self.get_error_summary(errors)
        fix_commands, install_packages = self.generate_fix_commands(errors)
        
        print("=" * 80)
        print("Python包错误分析报告")
        print("=" * 80)
        print()
        print("摘要:")
        print(f"- 发现 {summary['total_errors']} 个包相关错误")
        print(f"- 受影响的包: {', '.join(summary['affected_packages'])}")
        print()
        print("错误类型分布:")
        
        for error_type, count in summary["error_types"].items():
            print(f"- {self._friendly_error_name(error_type)}: {count}个")
        
        print()
        
        if fix_commands:
            print("建议修复命令:")
            print("-" * 40)
            for cmd in fix_commands:
                print(cmd)
            print("-" * 40)
            print()
        
        print("详细错误信息:")
        print()
        
        for i, error in enumerate(errors, 1):
            print(f"错误 #{i}: {self._friendly_error_name(error['error_type'])}")
            print("-" * 40)
            
            # 错误详情
            print("详情:")
            for key, value in error["details"].items():
                print(f"  {key}: {value}")
            
            # 上下文
            if "context" in error:
                print("\n上下文:")
                print(f"{error['context']}")
            
            # 修复建议
            print("\n修复建议:")
            print(f"{error['suggestion']}")
            
            print("\n" + "=" * 80 + "\n")

    def _friendly_error_name(self, error_type: str) -> str:
        """将错误类型转换为友好的描述
        
        Args:
            error_type: 错误类型代码
            
        Returns:
            错误类型的友好描述
        """
        name_map = {
            "missing_package": "缺少包",
            "import_name_error": "导入名称错误",
            "attribute_error": "属性错误",
            "version_conflict": "版本冲突",
            "syntax_error_in_package": "包中的语法错误",
            "import_error_in_package": "包导入错误",
            "dependency_error": "依赖错误",
            "dll_load_error": "DLL加载错误",
            "permission_error": "权限错误",
            "pkg_resources_error": "资源分发错误",
            "incompatible_version": "版本不兼容"
        }
        return name_map.get(error_type, error_type)


def main():
    """主函数: 运行错误提取测试用例"""
    print("运行Python包错误提取器测试用例...")
    
    from test_messages import test_cases
    
    extractor = PackageErrorExtractor()
    
    # 运行所有测试用例
    for case_name, error_text in test_cases.items():
        print("\n" + "=" * 80)
        print(f"测试用例: {case_name}")
        print("=" * 80)
        
        # 提取错误
        errors = extractor.extract_errors_from_text(error_text)
        
        # 打印提取的错误
        extractor.print_errors(errors)
        
    # 组合测试用例
    print("\n" + "=" * 80)
    print("组合测试用例: 所有错误")
    print("=" * 80)
    
    # 合并所有测试文本
    all_errors_text = "\n\n".join(test_cases.values())
    all_errors = extractor.extract_errors_from_text(all_errors_text)
    extractor.print_errors(all_errors)
    
    # 示例: 如何在实际代码中使用此工具
    print("\n" + "=" * 80)
    print("实际应用示例")
    print("=" * 80)
    print("以下是如何在你的代码中使用此工具:")
    print("""
# 示例 1: 从日志文件中提取错误
from package_error_extractor import PackageErrorExtractor

extractor = PackageErrorExtractor()
errors = extractor.extract_errors_from_file('error_log.txt')
extractor.print_errors(errors)

# 示例 2: 直接从错误文本中提取
error_text = '''
Traceback (most recent call last):
  File "example.py", line 10, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
'''
errors = extractor.extract_errors_from_text(error_text)
# 获取提取的错误详情
for error in errors:
    print(f"错误类型: {error['error_type']}")
    print(f"详情: {error['details']}")
    print(f"修复建议: {error['suggestion']}")
    
# 示例 3: 生成修复命令
fix_commands, install_packages = extractor.generate_fix_commands(errors)
for cmd in fix_commands:
    print(cmd)
""")


if __name__ == "__main__":
    main()