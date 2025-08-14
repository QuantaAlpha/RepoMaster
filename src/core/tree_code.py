#!/usr/bin/env python
"""
Global code tree builder - Used to parse Python code repositories and create a structured code tree
Can save code tree locally and generate context content suitable for LLM browsing and analysis
"""

import os
import ast
import re
import json
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Union, Any
import argparse
import logging
from collections import defaultdict
import time
import pickle
from tqdm import tqdm
import tiktoken
from src.core.code_utils import _get_code_abs, get_code_abs_token, should_ignore_path, ignored_dirs, ignored_file_patterns
from src.core.repo_summary import generate_repository_summary
import glob
from src.utils.data_preview import _parse_ipynb_file
# Import importance analyzer
try:
    from src.core.importance_analyzer import ImportanceAnalyzer
except ImportError:
    # Try relative import
    try:
        from src.core.importance_analyzer import ImportanceAnalyzer
    except ImportError:
        ImportanceAnalyzer = None
        logging.warning("Cannot import ImportanceAnalyzer, code importance analysis will not be available.")

# 修改tree-sitter导入
import tree_sitter
from tree_sitter_language_pack import get_language, get_parser

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GlobalCodeTreeBuilder:
    """Global code tree builder, used to parse code repositories and build LLM-friendly structured representations"""
    
    def __init__(self, repo_path: str):
        """
        初始化代码树构建器
        
        Args:
            repo_path: 代码仓库的路径
            ignored_dirs: 要忽略的目录列表
            ignored_file_patterns: 要忽略的文件模式列表
        """
        self.repo_path = repo_path
        self.call_graph = nx.DiGraph()  # 函数调用图
        self.modules = {}  # 模块信息
        self.functions = {}  # 函数信息
        self.classes = {}  # 类信息
        self.other_files = {}  # 其他文件信息
        self.imports = defaultdict(list)  # 导入信息
        self.code_tree = {  # 分层代码树
            'modules': {},
            'stats': {
                'total_modules': 0,
                'total_classes': 0,
                'total_functions': 0,
                'total_lines': 0
            },
            'key_components': []  # 关键组件
        }
        
        # 统一定义要忽略的目录和文件模式，如果参数中没有提供，使用默认值
        self.ignored_dirs = ignored_dirs
        self.ignored_file_patterns = ignored_file_patterns
        
        # 检查是否支持Jupyter Notebook解析
        self.jupyter_support = False
        try:
            import nbformat
            self.jupyter_support = True
            logger.info("成功加载nbformat库，将支持Jupyter Notebook解析")
        except ImportError:
            logger.warning("无法导入nbformat库，将跳过Jupyter Notebook解析")
        
        # 初始化tree-sitter
        self.parser = None
        self.python_language = None
        
        if tree_sitter is not None:
            try:
                # 使用tree_sitter_languages简化语言加载
                self.parser = get_parser('python')
                self.python_language = get_language('python')
                if self.parser and self.python_language:
                    logger.info("成功加载tree-sitter Python语言")
                else:
                    logger.warning("无法加载tree-sitter Python语言")
            except Exception as e:
                logger.warning(f"无法初始化tree-sitter: {e}，将使用简单代码展示")
        else:
            logger.warning("tree-sitter库不可用，将使用简单代码展示")
        
    def parse_repository(self) -> None:
        """解析整个代码仓库"""
        logger.info(f"开始解析代码仓库: {self.repo_path}")
        
        # 查找并解析所有Python文件和Jupyter Notebook文件
        for root, dirs, files in os.walk(self.repo_path):
            # 计算当前目录深度 (相对于仓库根目录)
            rel_path = os.path.relpath(root, self.repo_path)
            current_depth = 0 if rel_path == '.' else len(rel_path.split(os.sep))
            
            # 如果目录深度超过5，则跳过此目录及其子目录
            if current_depth > 3:
                dirs[:] = []  # 清空dirs列表，这样os.walk就不会进入子目录
                # logger.info(f"目录 {rel_path} 深度超过4，跳过此目录及其子目录")
                continue
            
            # 就地修改dirs列表，跳过被忽略的目录
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            
            # 限制每个目录最多处理40个文件
            file_count = 0
            max_files_per_dir = 40
            
            if len(files) > 100:
                continue
            elif len(files) > 50:
                files = files[:5]
            
            
            for file in files:
                # 如果已经处理了40个文件，则忽略此目录中的剩余文件
                if file_count >= max_files_per_dir:
                    # logger.info(f"目录 {rel_path} 中文件超过{max_files_per_dir}个，忽略剩余文件")
                    break
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repo_path)
                
                # 使用统一的函数检查是否应该忽略
                if should_ignore_path(rel_path):
                    continue
                
                # 在处理文件前添加
                file_size = os.path.getsize(file_path)
                if file_size > 10 * 1024 * 1024:  # 跳过大于10MB的文件
                    # logger.info(f"文件 {rel_path} 过大 ({file_size/1024/1024:.2f}MB)，跳过")
                    continue
                
                try:
                    if file.endswith('.py'):
                        self._parse_python_file(file_path, rel_path)
                    else:
                        self._parse_other_file(file_path, rel_path)
                    
                    # 成功处理文件后增加计数
                    file_count += 1
                    
                except Exception as e:
                    logger.error(f"解析文件 {rel_path} 时出错: {e}", exc_info=True)
        
        # 构建各种关系
        self._build_call_relationships()
        self._build_hierarchical_code_tree()
        
        # 识别重要组件
        self._identify_key_class()
        
        # 识别重要模块
        key_modules = self._identify_key_modules()
        if key_modules:
            self.code_tree['key_modules'] = key_modules
            logger.info(f"已识别 {len(key_modules)} 个关键模块")
        
        logger.info(f"代码仓库解析完成，共发现 {len(self.modules)} 个模块，{len(self.classes)} 个类，{len(self.functions)} 个函数")
    
    def _parse_python_file(self, file_path: str, rel_path: str) -> None:
        """
        解析单个Python文件
        
        Args:
            file_path: 文件的绝对路径
            rel_path: 文件相对于仓库根目录的路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            module_node = ast.parse(content, filename=rel_path)
            module_docstring = ast.get_docstring(module_node) or ""
            
            # 创建模块ID，以点分隔的路径
            module_id = rel_path.replace('/', '.').replace('\\', '.').replace('.py', '')
            self.modules[module_id] = {
                'path': rel_path,
                'docstring': module_docstring,
                'content': content,
                'functions': [],
                'classes': []
            }
            
            # 处理导入语句
            self._process_imports(module_node, module_id)
            
            # 解析函数和类
            for node in ast.walk(module_node):
                # 处理函数定义
                if isinstance(node, ast.FunctionDef):
                    if not hasattr(node, 'parent_class'):
                        self._process_function(node, module_id, None)
                
                # 处理类定义
                elif isinstance(node, ast.ClassDef):
                    class_id = f"{module_id}.{node.name}"
                    class_docstring = ast.get_docstring(node) or ""
                    
                    # 分析类的继承关系
                    base_classes = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            base_classes.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            base_classes.append(self._get_attribute_path(base))
                    
                    self.classes[class_id] = {
                        'name': node.name,
                        'module': module_id,
                        'docstring': class_docstring,
                        'methods': [],
                        'base_classes': base_classes,
                        'source': self._get_source(content, node)
                    }
                    
                    self.modules[module_id]['classes'].append(class_id)
                    
                    # 处理类中的方法
                    for class_node in node.body:
                        if isinstance(class_node, ast.FunctionDef):
                            # 为方法添加父类属性
                            class_node.parent_class = class_id
                            self._process_function(class_node, module_id, class_id)
        
        except SyntaxError as e:
            logger.warning(f"文件 {rel_path} 存在语法错误: {e}")
        except Exception as e:
            logger.error(f"处理文件 {rel_path} 时发生错误: {e}")
    
    def _parse_other_file(self, file_path: str, rel_path: str) -> None:
        """
        解析非Python文件，包括Jupyter Notebook等
        
        Args:
            file_path: 文件的绝对路径
            rel_path: 文件相对于仓库根目录的路径
        """
        try:
            if file_path.endswith('.ipynb'):
                content = _parse_ipynb_file(file_path)
            else:
                content = open(file_path, 'r', encoding='utf-8').read()
            
            # 为非Python文件创建一个简单的模块记录
            # 使用文件扩展名作为"语言"标识
            file_ext = os.path.splitext(file_path)[1][1:]  # 去掉点号
            module_id = rel_path.replace('/', '.').replace('\\', '.').replace(f'.{file_ext}', '')
            
            self.other_files[module_id] = {
                'path': rel_path,
                'docstring': f"非Python文件: {file_ext.upper()} 代码",
                'content': content,
                'functions': [],
                'classes': [],
                'language': file_ext
            }
            
            logger.debug(f"已记录非Python文件: {rel_path}")
        
        except Exception as e:
            logger.error(f"处理非Python文件 {rel_path} 时出错: {e}")
    
    def _process_imports(self, module_node: ast.Module, module_id: str) -> None:
        """处理模块中的导入语句"""
        for node in module_node.body:
            if isinstance(node, ast.Import):
                for name in node.names:
                    self.imports[module_id].append({
                        'type': 'import',
                        'name': name.name,
                        'alias': name.asname
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for name in node.names:
                    self.imports[module_id].append({
                        'type': 'importfrom',
                        'module': module,
                        'name': name.name,
                        'alias': name.asname
                    })
    
    def _process_function(self, node: ast.FunctionDef, module_id: str, class_id: Optional[str]) -> None:
        """处理函数或方法定义"""
        function_name = node.name
        if class_id:
            function_id = f"{class_id}.{function_name}"
            self.classes[class_id]['methods'].append(function_id)
        else:
            function_id = f"{module_id}.{function_name}"
            self.modules[module_id]['functions'].append(function_id)
        
        docstring = ast.get_docstring(node) or ""
        
        # 获取源代码
        source = self._get_source(self.modules[module_id]['content'], node)
        
        # 分析函数参数
        parameters = []
        for arg in node.args.args:
            param_name = arg.arg
            param_type = None
            if hasattr(arg, 'annotation') and arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param_type = arg.annotation.id
                elif isinstance(arg.annotation, ast.Attribute):
                    param_type = self._get_attribute_path(arg.annotation)
                elif isinstance(arg.annotation, ast.Subscript):
                    param_type = self._get_subscript_annotation(arg.annotation)
            parameters.append({
                'name': param_name,
                'type': param_type
            })
        
        # 分析函数返回类型
        return_type = None
        if hasattr(node, 'returns') and node.returns:
            if isinstance(node.returns, ast.Name):
                return_type = node.returns.id
            elif isinstance(node.returns, ast.Attribute):
                return_type = self._get_attribute_path(node.returns)
            elif isinstance(node.returns, ast.Subscript):
                return_type = self._get_subscript_annotation(node.returns)
        
        # 分析函数体中的函数调用
        calls = self._extract_function_calls(node)
        
        self.functions[function_id] = {
            'name': function_name,
            'module': module_id,
            'class': class_id,
            'docstring': docstring,
            'parameters': parameters,
            'return_type': return_type,
            'calls': calls,
            'called_by': [],  # 将在构建调用关系时填充
            'source': source
        }
        
        # 将节点添加到调用图中
        self.call_graph.add_node(function_id)
    
    def _extract_function_calls(self, node: ast.FunctionDef) -> List[Dict]:
        """从函数体中提取函数调用"""
        calls = []
        
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                call_info = self._analyze_call(subnode)
                if call_info:
                    calls.append(call_info)
        
        return calls
    
    def _analyze_call(self, node: ast.Call) -> Optional[Dict]:
        """分析函数调用表达式"""
        if isinstance(node.func, ast.Name):
            # 简单函数调用 func()
            return {'type': 'simple', 'name': node.func.id}
        
        elif isinstance(node.func, ast.Attribute):
            # 属性调用 obj.method()
            if isinstance(node.func.value, ast.Name):
                return {
                    'type': 'attribute',
                    'object': node.func.value.id,
                    'attribute': node.func.attr
                }
            # 嵌套属性调用 module.sub.func()
            return {
                'type': 'nested_attribute',
                'full_path': self._get_attribute_path(node.func)
            }
        
        return None
    
    def _get_attribute_path(self, node: ast.Attribute) -> str:
        """获取完整的属性路径 (例如 module.submodule.function)"""
        parts = []
        current = node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
        
        return '.'.join(reversed(parts))
    
    def _get_subscript_annotation(self, node: ast.Subscript) -> str:
        """获取类型注解中的下标表达式 (例如 List[str])"""
        # 处理 Python 3.8+
        try:
            if isinstance(node.value, ast.Name):
                container = node.value.id
            elif isinstance(node.value, ast.Attribute):
                container = self._get_attribute_path(node.value)
            else:
                return "unknown"
            
            # 兼容 Python 3.8 及之前
            if hasattr(node, 'slice') and isinstance(node.slice, ast.Index):
                slice_value = node.slice.value
                if isinstance(slice_value, ast.Name):
                    param = slice_value.id
                elif isinstance(slice_value, ast.Attribute):
                    param = self._get_attribute_path(slice_value)
                else:
                    param = "unknown"
            # 兼容 Python 3.9+
            elif hasattr(node, 'slice'):
                if isinstance(node.slice, ast.Name):
                    param = node.slice.id
                elif isinstance(node.slice, ast.Attribute):
                    param = self._get_attribute_path(node.slice)
                else:
                    param = "unknown"
            else:
                param = "unknown"
            
            return f"{container}[{param}]"
        except Exception:
            return "unknown"
    
    def _build_call_relationships(self) -> None:
        """构建函数间的调用关系"""
        logger.info("构建函数调用关系...")
        
        for func_id, func_info in self.functions.items():
            calls = func_info['calls']
            module_id = func_info['module']
            
            for call in calls:
                called_func_id = self._resolve_call(call, module_id, func_info['class'])
                
                if called_func_id and called_func_id in self.functions:
                    # 添加到调用图
                    self.call_graph.add_edge(func_id, called_func_id)
                    
                    # 更新被调用函数的信息
                    if func_id not in self.functions[called_func_id]['called_by']:
                        self.functions[called_func_id]['called_by'].append(func_id)
    
    def _resolve_call(self, call: Dict, module_id: str, class_id: Optional[str]) -> Optional[str]:
        """解析函数调用，返回被调用函数的ID"""
        if call['type'] == 'simple':
            # 检查同一模块中的函数
            direct_func_id = f"{module_id}.{call['name']}"
            if direct_func_id in self.functions:
                return direct_func_id
            
            # 检查同一类中的方法
            if class_id:
                method_id = f"{class_id}.{call['name']}"
                if method_id in self.functions:
                    return method_id
                
                # 检查父类中的方法
                if class_id in self.classes:
                    for base_class in self.classes[class_id]['base_classes']:
                        # 尝试构造完整的基类路径
                        # 如果是简单名称，尝试在同一模块中查找
                        if '.' not in base_class:
                            potential_base = f"{module_id}.{base_class}"
                            if potential_base in self.classes:
                                base_method_id = f"{potential_base}.{call['name']}"
                                if base_method_id in self.functions:
                                    return base_method_id
                        else:
                            # 已经是完整路径
                            base_method_id = f"{base_class}.{call['name']}"
                            if base_method_id in self.functions:
                                return base_method_id
            
            # 检查导入的函数
            for imp in self.imports[module_id]:
                if imp['type'] == 'importfrom' and imp['name'] == call['name']:
                    imported_module = imp['module']
                    imported_func_id = f"{imported_module}.{call['name']}"
                    if imported_func_id in self.functions:
                        return imported_func_id
        
        elif call['type'] == 'attribute':
            obj_name = call['object']
            attr_name = call['attribute']
            
            # 检查是否是类的实例方法调用
            for cls_id in self.classes:
                if cls_id.endswith(f".{obj_name}"):
                    method_id = f"{cls_id}.{attr_name}"
                    if method_id in self.functions:
                        return method_id
            
            # 检查导入的模块
            for imp in self.imports[module_id]:
                if ((imp['type'] == 'import' and imp['name'] == obj_name) or 
                    (imp['type'] == 'import' and imp['alias'] == obj_name)):
                    imported_func_id = f"{imp['name']}.{attr_name}"
                    if imported_func_id in self.functions:
                        return imported_func_id
        
        elif call['type'] == 'nested_attribute':
            # 处理嵌套属性调用
            full_path = call['full_path']
            
            # 检查完全匹配
            if full_path in self.functions:
                return full_path
            
            # 检查部分匹配
            for func_id in self.functions:
                if func_id.endswith(f".{full_path}"):
                    return func_id
        
        return None
    
    def _get_source(self, content: str, node: ast.AST) -> str:
        """提取AST节点对应的源代码"""
        source_lines = content.splitlines()
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            start_line = node.lineno - 1  # AST行号从1开始，列表索引从0开始
            end_line = node.end_lineno
            return "\n".join(source_lines[start_line:end_line])
        return ""

    def _build_hierarchical_code_tree(self) -> None:
        """构建层次化的代码树结构，便于浏览和分析"""
        logger.info("构建层次化代码树...")
        
        # 计算统计信息
        self.code_tree['stats']['total_modules'] = len(self.modules)
        self.code_tree['stats']['total_classes'] = len(self.classes)
        self.code_tree['stats']['total_functions'] = len(self.functions)
        
        total_lines = 0
        for module_id, module_info in self.modules.items():
            module_lines = len(module_info['content'].splitlines())
            total_lines += module_lines
            
            # 创建模块节点
            path_parts = module_id.split('.')
            self._add_to_tree(self.code_tree['modules'], path_parts, {
                'type': 'module',
                'id': module_id,
                'name': path_parts[-1],
                'docstring': module_info['docstring'][:100] + ('...' if len(module_info['docstring']) > 100 else ''),
                'classes': [],
                'functions': [],
                'lines': module_lines,
                'is_notebook': module_info.get('is_notebook', False)  # 传递notebook标记
            })
            
            # 添加类
            for class_id in module_info['classes']:
                class_info = self.classes[class_id]
                class_lines = len(class_info['source'].splitlines())
                
                class_node = {
                    'type': 'class',
                    'id': class_id,
                    'name': class_info['name'],
                    'docstring': class_info['docstring'][:100] + ('...' if len(class_info['docstring']) > 100 else ''),
                    'methods': [],
                    'base_classes': class_info['base_classes'],
                    'lines': class_lines,
                    'from_notebook': class_info.get('from_notebook', False)  # 传递from_notebook标记
                }
                
                # 确保模块节点有classes键
                if 'classes' not in self.code_tree['modules'][path_parts[0]]:
                    self.code_tree['modules'][path_parts[0]]['classes'] = []
                
                self.code_tree['modules'][path_parts[0]]['classes'].append(class_node)
                
                # 添加方法
                for method_id in class_info['methods']:
                    method_info = self.functions[method_id]
                    method_lines = len(method_info['source'].splitlines())
                    
                    method_node = {
                        'type': 'method',
                        'id': method_id,
                        'name': method_info['name'],
                        'docstring': method_info['docstring'][:100] + ('...' if len(method_info['docstring']) > 100 else ''),
                        'parameters': method_info['parameters'],
                        'return_type': method_info['return_type'],
                        'calls': [c for c in method_info['calls'] if self._resolve_call(c, method_info['module'], method_info['class'])],
                        'called_by': method_info['called_by'],
                        'lines': method_lines
                    }
                    
                    class_node['methods'].append(method_node)
            
            # 添加模块级函数
            for func_id in module_info['functions']:
                func_info = self.functions[func_id]
                func_lines = len(func_info['source'].splitlines())
                
                func_node = {
                    'type': 'function',
                    'id': func_id,
                    'name': func_info['name'],
                    'docstring': func_info['docstring'][:100] + ('...' if len(func_info['docstring']) > 100 else ''),
                    'parameters': func_info['parameters'],
                    'return_type': func_info['return_type'],
                    'calls': [c for c in func_info['calls'] if self._resolve_call(c, func_info['module'], None)],
                    'called_by': func_info['called_by'],
                    'lines': func_lines
                }
                
                # 获取模块节点的引用
                module_node = self._get_tree_node(self.code_tree['modules'], path_parts)
                if module_node:
                    # 确保模块节点有functions键
                    if 'functions' not in module_node:
                        module_node['functions'] = []
                    
                    module_node['functions'].append(func_node)
        
        self.code_tree['stats']['total_lines'] = total_lines
        
        # 初始化重要性分析器
        self.importance_analyzer = None
        if ImportanceAnalyzer is not None:
            try:
                self.importance_analyzer = ImportanceAnalyzer(
                    repo_path=self.repo_path,
                    modules=self.modules,
                    classes=self.classes,
                    functions=self.functions,
                    imports=self.imports,
                    code_tree=self.code_tree,
                    call_graph=self.call_graph
                )
                logger.info("已初始化代码重要性分析器")
            except Exception as e:
                logger.error(f"初始化代码重要性分析器时出错: {e}")
    
    def _add_to_tree(self, tree: Dict, path: List[str], node_data: Dict) -> None:
        """
        在树结构中添加节点
        
        Args:
            tree: 树结构
            path: 路径
            node_data: 节点数据
        """
        if len(path) == 1:
            if path[0] not in tree:
                tree[path[0]] = node_data
            return
        
        if path[0] not in tree:
            tree[path[0]] = {
                'type': 'package',
                'name': path[0],
                'children': {}
            }
        
        if 'children' not in tree[path[0]]:
            tree[path[0]]['children'] = {}
        
        self._add_to_tree(tree[path[0]]['children'], path[1:], node_data)
    
    def _get_tree_node(self, tree: Dict, path: List[str]) -> Optional[Dict]:
        """
        获取树中的节点
        
        Args:
            tree: 树结构
            path: 路径
            
        Returns:
            找到的节点或None
        """
        if len(path) == 1:
            return tree.get(path[0])
        
        if path[0] not in tree:
            return None
        
        if 'children' not in tree[path[0]]:
            return None
        
        return self._get_tree_node(tree[path[0]]['children'], path[1:])
    
    def _identify_key_components(self) -> None:
        """识别代码库中的关键组件"""
        logger.info("识别关键组件...")
        
        # 只识别类级别的关键组件
        try:
            # 1. 计算类的重要性
            class_importance = {}
            
            # 为每个类创建一个虚拟节点
            class_graph = nx.DiGraph()
            
            # 添加所有类作为节点
            for class_id in self.classes:
                class_graph.add_node(class_id)
            
            # 添加类之间的调用关系边
            for class_id, class_info in self.classes.items():
                # 获取该类的所有方法
                methods = class_info['methods']
                
                # 记录该类调用的其他类
                called_classes = set()
                
                # 遍历该类的所有方法
                for method_id in methods:
                    if method_id in self.functions:
                        method_info = self.functions[method_id]
                        
                        # 遍历该方法调用的所有函数
                        for call in method_info['calls']:
                            called_func_id = self._resolve_call(call, method_info['module'], method_info['class'])
                            
                            if called_func_id and called_func_id in self.functions:
                                called_func = self.functions[called_func_id]
                                
                                # 如果调用的是另一个类的方法
                                if called_func['class'] and called_func['class'] != class_id:
                                    called_classes.add(called_func['class'])
                
                # 为每个调用关系添加边
                for called_class in called_classes:
                    class_graph.add_edge(class_id, called_class)
            
            # 如果类图不为空，计算PageRank
            if len(class_graph.nodes()) > 0:
                class_pagerank = nx.pagerank(class_graph, alpha=0.85, max_iter=100)
                class_importance = class_pagerank
            
            # 添加重要的类
            key_components = []
            for class_id, score in sorted(class_importance.items(), key=lambda x: x[1], reverse=True):
                class_info = self.classes[class_id]
                
                # 计算类的总行数
                class_lines = len(class_info['source'].splitlines())
                
                # 计算类的方法数量
                methods_count = len(class_info['methods'])
                
                # 计算类被调用的次数（通过其方法）
                called_by_count = 0
                for method_id in class_info['methods']:
                    if method_id in self.functions:
                        called_by_count += len(self.functions[method_id]['called_by'])
                
                key_components.append({
                    'id': class_id,
                    'name': class_info['name'],
                    'type': 'class',
                    'module': class_info['module'],
                    'importance_score': score,
                    'methods_count': methods_count,
                    'called_by_count': called_by_count,
                    'lines': class_lines,
                    'path': self.modules[class_info['module']]['path'],
                    'docstring': class_info['docstring'][:200] if class_info['docstring'] else ""
                })
            
            # 按重要性分数排序
            self.code_tree['key_components'] = sorted(key_components, key=lambda x: x['importance_score'], reverse=True)

        except Exception as e:
            logger.error(f"计算组件重要性时出错: {e}", exc_info=True)
            
            # 备选方案：使用简单的启发式方法
            try:
                key_components = []
                
                # 处理类
                class_stats = []
                for class_id, class_info in self.classes.items():
                    # 计算类的方法数量
                    methods_count = len(class_info['methods'])
                    
                    # 计算类被调用的次数（通过其方法）
                    called_by_count = 0
                    calls_count = 0
                    
                    for method_id in class_info['methods']:
                        if method_id in self.functions:
                            method_info = self.functions[method_id]
                            called_by_count += len(method_info['called_by'])
                            calls_count += len([c for c in method_info['calls'] 
                                              if self._resolve_call(c, method_info['module'], method_info['class'])])
                    
                    # 简单加权计算重要性分数
                    importance = (0.4 * called_by_count) + (0.3 * calls_count) + (0.3 * methods_count)
                    
                    class_stats.append((class_id, importance))
                
                # 获取重要度排名前10的类
                for class_id, score in sorted(class_stats, key=lambda x: x[1], reverse=True)[:10]:
                    class_info = self.classes[class_id]
                    
                    key_components.append({
                        'id': class_id,
                        'name': class_info['name'],
                        'type': 'class',
                        'module': class_info['module'],
                        'importance_score': score,
                        'methods_count': len(class_info['methods']),
                        'called_by_count': sum(len(self.functions[m]['called_by']) for m in class_info['methods'] if m in self.functions),
                        'lines': len(class_info['source'].splitlines()),
                        'docstring': class_info['docstring'][:200] if class_info['docstring'] else ""
                    })
                
                # 按重要性分数排序
                self.code_tree['key_components'] = sorted(key_components, key=lambda x: x['importance_score'], reverse=True)
                
            except Exception as e:
                logger.error(f"使用备选方案计算组件重要性时出错: {e}", exc_info=True)
    
    def _identify_key_modules(self) -> List[Dict]:
        """识别代码库中的关键模块"""
        logger.info("识别关键模块...")
        
        # 只识别模块级别的关键组件
        if not self.modules:
            logger.warning("没有模块信息，无法识别关键模块")
            return []
        
        # 检查模块数量是否过多
        if len(self.modules) > 300:
            logger.warning(f"模块数量过多({len(self.modules)})，跳过关键模块重要度计算")
            return []
            
        key_modules = []
        
        try:
            # 收集所有模块并计算其重要性
            module_importance = {}
            
            # 检查是否有重要性分析器
            if hasattr(self, 'importance_analyzer') and self.importance_analyzer is not None:
                # 使用ImportanceAnalyzer计算重要性分数
                for module_id, module_info in self.modules.items():
                    # 创建节点字典，确保它有'type'字段
                    node_info = {'id': module_id, 'type': 'module'}
                    if 'docstring' in module_info:
                        node_info['docstring'] = module_info['docstring']
                    if 'path' in module_info:
                        node_info['path'] = module_info['path']
                    
                    # 计算重要性分数
                    try:
                        importance_score = self.importance_analyzer.calculate_node_importance(node_info)
                        module_importance[module_id] = importance_score
                    except Exception as e:
                        logger.warning(f"计算模块 {module_id} 重要性时出错: {e}")
                        # 使用备用计算方法
                        module_importance[module_id] = self._calculate_node_importance(node_info)
            else:
                # 使用内部方法计算重要性
                logger.info("使用内部方法计算模块重要性")
                for module_id, module_info in self.modules.items():
                    node_info = {
                        'id': module_id, 
                        'type': 'module',
                        'docstring': module_info.get('docstring', ''),
                        'classes': module_info.get('classes', []),
                        'functions': module_info.get('functions', [])
                    }
                    if 'content' in module_info:
                        node_info['lines'] = len(module_info['content'].splitlines())
                    
                    module_importance[module_id] = self._calculate_node_importance(node_info)
            
            # 按重要性排序并生成关键模块列表
            for module_id, score in sorted(module_importance.items(), key=lambda x: x[1], reverse=True):  # 获取前15个最重要的模块
                module_info = self.modules[module_id]
                
                # 计算模块的类和函数数量
                classes_count = len(module_info.get('classes', []))
                functions_count = len(module_info.get('functions', []))
                lines_count = len(module_info.get('content', '').splitlines())
                
                # 添加到关键模块列表
                key_modules.append({
                    'id': module_id,
                    'name': module_id.split('.')[-1],
                    'type': 'module',
                    'importance_score': score,
                    'classes_count': classes_count,
                    'functions_count': functions_count,
                    'lines': lines_count,
                    'path': module_info.get('path', ''),
                    'docstring': module_info.get('docstring', '')[:200] if module_info.get('docstring') else ""
                })
            
            logger.info(f"识别了 {len(key_modules)} 个关键模块")
            
            # 将关键模块添加到代码树中
            if 'key_modules' not in self.code_tree:
                self.code_tree['key_modules'] = []
            
            self.code_tree['key_modules'] = sorted(key_modules, key=lambda x: x['importance_score'], reverse=True)
            
        except Exception as e:
            logger.error(f"识别关键模块时出错: {e}", exc_info=True)
            # 错误处理，确保返回一个有效的列表
            if not key_modules:
                # 使用简单的启发式方法作为备选
                for module_id, module_info in list(self.modules.items())[:10]:  # 只处理前10个模块
                    key_modules.append({
                        'id': module_id,
                        'name': module_id.split('.')[-1],
                        'type': 'module',
                        'importance_score': 0.5,  # 默认中等重要性
                        'path': module_info.get('path', ''),
                        'docstring': module_info.get('docstring', '')[:200] if module_info.get('docstring') else ""
                    })
        
        return key_modules
    
    def _identify_key_class(self) -> None:
        """利用ImportanceAnalyzer识别代码库中的关键组件"""
        logger.info("使用ImportanceAnalyzer识别关键组件...")
        
        if not hasattr(self, 'importance_analyzer') or self.importance_analyzer is None:
            logger.warning("ImportanceAnalyzer不可用，将使用原始方法识别关键组件")
            self._identify_key_components()
            return
        
        if len(self.modules) > 300:
            logger.warning(f"模块数量过多({len(self.modules)})，跳过关键类重要度计算")
            return
            
        try:
            # 收集所有类节点并计算其重要性
            class_importance = {}
            for class_id, class_info in self.classes.items():
                class_importance[class_id] = 0            

            # 添加重要的类
            key_components = []
            for class_id, score in sorted(class_importance.items(), key=lambda x: x[1], reverse=True):
                class_info = self.classes[class_id]
                
                # 计算类的总行数
                class_lines = len(class_info['source'].splitlines())
                
                # 计算类的方法数量
                methods_count = len(class_info['methods'])
                
                # 计算类被调用的次数（通过其方法）
                called_by_count = 0
                for method_id in class_info['methods']:
                    if method_id in self.functions:
                        called_by_count += len(self.functions[method_id]['called_by'])
                
                key_components.append({
                    'id': class_id,
                    'name': class_info['name'],
                    'type': 'class',
                    'module': class_info['module'],
                    'importance_score': score,
                    'methods_count': methods_count,
                    'called_by_count': called_by_count,
                    'lines': class_lines,
                    'docstring': class_info['docstring'][:200] if class_info['docstring'] else ""
                })
            
            # 按重要性分数排序
            self.code_tree['key_components'] = sorted(key_components, key=lambda x: x['importance_score'], reverse=True)
            
            logger.info(f"使用ImportanceAnalyzer识别了 {len(key_components)} 个关键组件")
            
        except Exception as e:
            logger.error(f"使用ImportanceAnalyzer计算组件重要性时出错: {e}", exc_info=True)
            # 失败时回退到原始方法
            logger.info("回退到原始方法识别关键组件")
            self._identify_key_components()
    
    def save_code_tree(self, output_file: str) -> None:
        """
        将代码树保存到文件
        
        Args:
            output_file: 输出文件路径
        """
        # 确保代码树包含完整的类和函数信息
        complete_tree = {
            'modules': self.code_tree['modules'],
            'stats': self.code_tree['stats'],
            'key_components': self.code_tree['key_components'],
            'classes': self.classes,  # 添加完整的类信息
            'functions': self.functions,  # 添加完整的函数信息
            'imports': dict(self.imports)  # 添加导入信息
        }
        
        # 添加关键模块信息
        if 'key_modules' in self.code_tree:
            complete_tree['key_modules'] = self.code_tree['key_modules']
        
        with open(output_file, 'wb') as f:
            pickle.dump(complete_tree, f)
        logger.info(f"代码树已保存到文件: {output_file}")
    
    def _calculate_node_importance(self, node: Dict) -> float:
        """
        计算节点的重要性分数
        
        Args:
            node: 节点信息
            
        Returns:
            重要性分数
        """
        # 如果有专门的重要性分析器，使用它
        if hasattr(self, 'importance_analyzer') and self.importance_analyzer is not None:
            try:
                return self.importance_analyzer.calculate_node_importance(node)
            except Exception as e:
                logger.warning(f"使用重要性分析器计算节点重要性时出错: {e}")
        
        # 回退到简单的重要性计算方法
        importance = 0.0
        
        # 如果是模块节点
        if node['type'] == 'module':
            # 1. 检查是否包含关键组件
            for component in self.code_tree['key_components']:
                if component['module'] == node['id']:
                    importance += 1.0
            
            # 2. 检查类和函数数量
            class_count = len(node.get('classes', []))
            func_count = len(node.get('functions', []))
            importance += (class_count * 0.3) + (func_count * 0.2)
            
            # 3. 检查文档完整性
            if node.get('docstring'):
                importance += 0.2
            
            # 4. 检查代码行数（归一化到0-1之间）
            if 'lines' in node:
                importance += min(node['lines'] / 1000, 1.0) * 0.3
        
        # 如果是包节点
        elif node['type'] == 'package':
            # 递归计算子节点的重要性
            if 'children' in node:
                for child in node['children'].values():
                    importance += self._calculate_node_importance(child) * 0.5
        
        return importance

    def _append_package_structure(self, content_parts: List[str], tree: Dict, level: int, min_importance: float = 0.5) -> None:
        """
        递归地添加包结构到内容中，只显示重要的部分
        
        Args:
            content_parts: 内容部分列表
            tree: 树结构
            level: 缩进级别
            min_importance: 最小重要性阈值
        """
        # 使用类属性中已定义的忽略列表，而不是重新定义
        
        # 按名称排序节点，并按重要性得分排序
        sorted_nodes = []
        for name, node in tree.items():
            # 跳过要忽略的名称
            if name in self.ignored_dirs or any(re.match(pattern, name) for pattern in self.ignored_file_patterns):
                continue
            
            importance = self._calculate_node_importance(node)
            sorted_nodes.append((name, node, importance))
        
        # 按重要性降序排序
        sorted_nodes.sort(key=lambda x: x[2], reverse=True)
        
        # 处理所有节点
        for name, node, importance in sorted_nodes:
            # 如果重要性低于阈值，跳过
            if importance < min_importance:
                continue
                
            indent = "  " * level
            if node['type'] == 'package':
                # 显示包名
                content_parts.append(f"{indent}- 📦 {name}/")
                
                # 递归处理子节点，但对较低级别的包应用更高的过滤阈值
                # 这样可以随着层级深入增加过滤强度
                next_min_importance = min_importance * (1.0 + level * 0.1)
                if 'children' in node:
                    self._append_package_structure(
                        content_parts, 
                        node['children'], 
                        level + 1,
                        min(next_min_importance, 5.0)  # 限制最大阈值
                    )
            elif node['type'] == 'module':
                # 显示模块名，如果是Jupyter Notebook，使用特殊图标
                if node.get('is_notebook', False):
                    content_parts.append(f"{indent}- 📔 {name}.ipynb")
                else:
                    content_parts.append(f"{indent}- 📄 {name}.py")
                
                # 添加简短的文档字符串提示
                if node.get('docstring'):
                    short_doc = node['docstring'].split('\n')[0][:50]
                    if short_doc:
                        content_parts.append(f" - {short_doc}...")
                # content_parts.append("\n")
                
                # 添加模块中的类和函数
                if node.get('classes'):
                    for cls in node['classes']:
                        # 对于来自Notebook的类，添加特殊标记
                        if cls.get('from_notebook', False):
                            content_parts.append(f"{indent}  - {cls['name']} (Notebook Class)")
                        else:
                            content_parts.append(f"{indent}  - {cls['name']} (Class)")
                
                # if node.get('functions'):
                #     for func in node['functions']:
                #         content_parts.append(f"{indent}  - {func['name']} (函数)\n")
    
    def to_json(self) -> str:
        """
        将代码树转换为JSON格式
        
        Returns:
            JSON格式的代码树
        """
        # 创建一个可序列化的字典
        serializable_tree = {
            'modules': self.code_tree['modules'],
            'stats': self.code_tree['stats'],
            'key_components': self.code_tree['key_components'],
            'classes': self.classes,
            'functions': self.functions,
            'imports': dict(self.imports)
        }
        
        # 添加关键模块信息
        if 'key_modules' in self.code_tree:
            serializable_tree['key_modules'] = self.code_tree['key_modules']

        # 转换为JSON字符串
        return json.dumps(serializable_tree, ensure_ascii=False, indent=2)
    
    def save_json(self, output_file: str) -> None:
        """
        将代码树以JSON格式保存到文件
        
        Args:
            output_file: 输出文件路径
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info(f"代码树已以JSON格式保存到文件: {output_file}")

    def _parse_package_import(self, codes: str) -> str:
        # 解析代码中的导入语句
        code_dependce = ""
        if self.parser and self.python_language:
            # 使用tree-sitter解析源代码
            tree = self.parser.parse(bytes(codes, 'utf8'))
            root_node = tree.root_node
            
            # 查找所有导入语句
            import_nodes = []
            for child in root_node.children:
                if child.type in ['import_statement', 'import_from_statement']:
                    import_nodes.append(child)
            
            # 提取导入语句的文本
            if import_nodes:
                imports_text = []
                for node in import_nodes:
                    start_point, end_point = node.start_point, node.end_point
                    start_line, start_col = start_point
                    end_line, end_col = end_point
                    
                    # 获取导入语句的源代码
                    if start_line == end_line:
                        line = codes.splitlines()[start_line]
                        imports_text.append(line[start_col:end_col])
                    else:
                        lines = codes.splitlines()[start_line:end_line+1]
                        lines[0] = lines[0][start_col:]
                        lines[-1] = lines[-1][:end_col]
                        imports_text.append('\n'.join(lines))
                
                code_dependce = "# 导入依赖\n" + "\n".join(imports_text) + "\n\n"
        return code_dependce

    def generate_llm_important_class(self, max_tokens: int = 3000) -> str:
        """
        生成LLM可用的关键组件源代码
        """
        def class_code_to_string(important_codes: Dict) -> str:
            important_codes_list = []
            important_codes_list.append("# 关键组件源代码样例\n")
            for class_path, codes in important_codes.items():
                important_codes_list.append(f"```python\n## {class_path}\n")
                code_content = self.modules[codes['module']]['content']
                important_codes_list.append(self._parse_package_import(code_content))
                important_codes_list.append("\n".join(codes['class_list'])+"\n```\n")            
            return "\n".join(important_codes_list)
        
        important_codes = {}
        if self.code_tree['key_components']:
            # 选取前3个关键组件展示源代码
            for component in self.code_tree['key_components']:
                token = tiktoken.encoding_for_model("gpt-4o")
                if len(token.encode(class_code_to_string(important_codes))) > max_tokens:
                    continue
                # 检查组件ID是否存在于相应的字典中
                if component['type'] == 'class' and component['id'] in self.classes:
                    class_info = self.classes[component['id']]
                    class_path = self.modules[class_info['module']]['path']
                    if class_path not in important_codes:
                        important_codes[class_path] = {
                            'module': class_info['module'],
                            'name': class_info['name'],
                            'class_list': []
                        }
                    # important_codes[class_path].append(f"## {class_info['name']} (类)\n")
                    # 使用tree-sitter生成代码结构摘要，而不是完整源代码
                    important_codes[class_path]['class_list'].append(self._get_ast_simple_summary(class_info['source']))
        
        return class_code_to_string(important_codes)
    
    def generate_llm_browsable_content(self, max_tokens: int = 8000) -> str:
        """
        生成适合LLM浏览的内容
        
        Args:
            max_tokens: 最大标记数，用于控制内容长度
            
        Returns:
            LLM友好的代码库表示
        """
        logger.info(f"生成LLM可浏览内容，最大标记数: {max_tokens}")
        
        content_parts = []
        
        # 1. 仓库概述
        content_parts.append("# 代码仓库概述\n")
        content_parts.append(f"仓库路径: {self.repo_path}\n")
        content_parts.append(f"总模块数: {self.code_tree['stats']['total_modules']}\n")
        content_parts.append(f"总类数: {self.code_tree['stats']['total_classes']}\n")
        content_parts.append(f"总函数数: {self.code_tree['stats']['total_functions']}\n")
        content_parts.append(f"总代码行数: {self.code_tree['stats']['total_lines']}\n")
        
        
        # 3. 包结构概览 - 使用动态重要性阈值过滤
        content_parts.append("# 包结构\n")
        self._append_package_structure(content_parts, self.code_tree['modules'], 0, min_importance=1.0)
        content_parts.append("\n")
        
        return "\n".join(content_parts)

    def _get_ast_simple_summary(self, source_code: str, max_lines: int = 20) -> str:
        """
        使用tree-sitter生成代码的结构化摘要
        
        Args:
            source_code: 源代码
            max_lines: 最大显示行数
            
        Returns:
            代码结构摘要
        """
        if not self.parser:
            # 如果tree-sitter不可用，返回简化版本
            lines = source_code.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + "\n... (省略剩余 {} 行)".format(len(lines) - max_lines)
            return source_code
            
        try:
            tree = self.parser.parse(bytes(source_code, 'utf8'))
            root_node = tree.root_node
            
            # 提取主要结构
            result = []
            stats = {"classes": 0, "functions": 0, "nested_functions": 0, "lambdas": 0, "async_funcs": 0, "decorators": 0}
            
            # 使用类似于test_tree_sitter.py中的方法提取结构
            def extract_node_info(node, depth=0, is_nested=False):
                if node.type == 'class_definition':
                    # 获取类名
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        class_name = source_code[name_node.start_byte:name_node.end_byte]
                        indent = "  " * depth
                        
                        # 检查装饰器
                        decorator_list = []
                        for child in node.children:
                            if child.type == 'decorator':
                                decorator_text = source_code[child.start_byte:child.end_byte].strip()
                                decorator_list.append(decorator_text)
                                stats["decorators"] += 1
                        
                        if decorator_list:
                            for decorator in decorator_list:
                                result.append(f"{indent}{decorator}")
                                
                        result.append(f"{indent}class {class_name}:")
                        stats["classes"] += 1
                        
                        # 处理类体
                        body_node = node.child_by_field_name('body')
                        if body_node:
                            for i in range(body_node.named_child_count):
                                child = body_node.named_child(i)
                                extract_node_info(child, depth + 1)
                
                elif node.type in ['function_definition', 'async_function_definition']:
                    # 获取函数名
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        func_name = source_code[name_node.start_byte:name_node.end_byte]
                        
                        # 获取参数
                        params_text = "()"
                        params_node = node.child_by_field_name('parameters')
                        if params_node:
                            params_text = source_code[params_node.start_byte:params_node.end_byte]
                        
                        indent = "  " * depth
                        
                        # 检查装饰器
                        decorator_list = []
                        for child in node.children:
                            if child.type == 'decorator':
                                decorator_text = source_code[child.start_byte:child.end_byte].strip()
                                decorator_list.append(decorator_text)
                        
                        if decorator_list:
                            for decorator in decorator_list:
                                result.append(f"{indent}{decorator}")
                        
                        # 确定是否是异步函数
                        is_async = node.type == 'async_function_definition'
                        if is_async:
                            stats["async_funcs"] += 1
                            
                        # 生成函数声明行
                        func_prefix = "async def" if is_async else "def"
                        
                        # 为嵌套函数添加特殊标记
                        if is_nested:
                            result.append(f"{indent}{func_prefix} {func_name}{params_text}: # [嵌套函数]")
                            stats["nested_functions"] += 1
                        else:
                            result.append(f"{indent}{func_prefix} {func_name}{params_text}:")
                            stats["functions"] += 1
                        
                        # 获取函数体的第一行（可能是文档字符串）
                        body_node = node.child_by_field_name('body')
                        if body_node and body_node.named_child_count > 0:
                            first_stmt = body_node.named_child(0)
                            has_docstring = False
                            
                            if first_stmt.type == "expression_statement":
                                for child in first_stmt.children:
                                    if child.type == "string":
                                        docstring = source_code[child.start_byte:child.end_byte]
                                        # 简化文档字符串显示
                                        doc_lines = docstring.split('\n')
                                        if len(doc_lines) > 1:
                                            clean_doc = doc_lines[0].strip('\"\'')
                                            result.append(f"{indent}  # 文档: {clean_doc}")
                                        else:
                                            clean_doc = docstring.strip('\"\'')
                                            result.append(f"{indent}  # 文档: {clean_doc}")
                                        has_docstring = True
                                        break
                            
                            # 如果没有文档字符串，尝试推断函数的主要功能
                            if not has_docstring:
                                # 查找函数体中的关键语句
                                key_verbs = []
                                for i in range(min(3, body_node.named_child_count)):
                                    stmt = body_node.named_child(i)
                                    stmt_text = source_code[stmt.start_byte:stmt.end_byte].strip()
                                    first_line = stmt_text.split('\n')[0]
                                    if len(first_line) > 5 and not first_line.startswith('#'):
                                        key_verbs.append(first_line[:40] + ('...' if len(first_line) > 40 else ''))
                                
                                if key_verbs:
                                    result.append(f"{indent}  # 功能: {key_verbs[0]}")
                            
                            # 递归处理函数体中的其他节点，特别是嵌套函数和类
                            if body_node.named_child_count > 0:
                                nested_items = []
                                for i in range(body_node.named_child_count):
                                    child = body_node.named_child(i)
                                    # 处理嵌套的函数和类定义
                                    if child.type in ['function_definition', 'class_definition', 'async_function_definition']:
                                        nested_items.append(child)
                                
                                # 如果有嵌套定义，添加提示
                                if nested_items:
                                    if not has_docstring and not key_verbs:
                                        result.append(f"{indent}  # 包含 {len(nested_items)} 个嵌套定义")
                                    
                                    # 递归处理嵌套定义
                                    for nested_item in nested_items:
                                        extract_node_info(nested_item, depth + 1, is_nested=True)
                
                # 处理lambda表达式 - tree-sitter可能将其标记为lambda表达式或匿名函数
                elif node.type in ['lambda', 'lambda_expression', 'anonymous_function']:
                    indent = "  " * depth
                    lambda_text = source_code[node.start_byte:node.end_byte]
                    if len(lambda_text) > 40:
                        lambda_text = lambda_text[:37] + "..."
                    result.append(f"{indent}lambda: {lambda_text}")
                    stats["lambdas"] += 1
                
                # 递归处理其他可能包含函数或类的节点类型
                elif node.type in ['if_statement', 'for_statement', 'while_statement', 'try_statement', 'with_statement']:
                    # 检查这些语句的主体是否包含函数或类定义
                    body_index = -1
                    for i, child in enumerate(node.children):
                        if child.type == 'block':
                            body_index = i
                            break
                    
                    if body_index >= 0 and body_index < len(node.children):
                        body_node = node.children[body_index]
                        # 递归检查主体内的节点
                        for i in range(body_node.named_child_count):
                            child = body_node.named_child(i)
                            if child.type in ['function_definition', 'class_definition', 'async_function_definition']:
                                extract_node_info(child, depth + 1, is_nested=True)
            
            # 处理顶级节点
            for i in range(root_node.named_child_count):
                node = root_node.named_child(i)
                extract_node_info(node, 0)
            
            # 添加摘要信息
            if any(stats.values()):
                summary = []
                if stats["classes"] > 0:
                    summary.append(f"{stats['classes']} 个类")
                if stats["functions"] > 0:
                    summary.append(f"{stats['functions']} 个函数")
                if stats["nested_functions"] > 0:
                    summary.append(f"{stats['nested_functions']} 个嵌套函数")
                if stats["async_funcs"] > 0:
                    summary.append(f"{stats['async_funcs']} 个异步函数")
                if stats["lambdas"] > 0:
                    summary.append(f"{stats['lambdas']} 个lambda表达式")
                if stats["decorators"] > 0:
                    summary.append(f"{stats['decorators']} 个装饰器")
                
                if summary:
                    result.append(f"\n# 总计: {', '.join(summary)}")
            
            return "\n".join(result) if result else "# 未找到类或函数定义"
            
        except Exception as e:
            logger.warning(f"使用tree-sitter解析代码时出错: {e}")
            # 回退到简单展示
            lines = source_code.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... (省略剩余 {len(lines) - max_lines} 行)"
            return source_code
    
    def get_repo_summary_list(self, max_tokens, is_file_summary):

        # 获取仓库核心文件,LLM生成仓库摘要
        important_repo_files_keys = [
            'README', 'main.py', '.ipynb', 'app.py', 'inference', 'test',
        ]
        
        # 先处理一级目录下的README文件
        readme_files = []
        other_important_files = []
        
        for file_id, file_info in {**self.modules, **self.other_files}.items():
            file_path = file_info['path']
            if len(other_important_files) > 20:
                break
            # 判断是否是一级目录下的README文件
            if '/' not in file_path and 'README' in file_path.upper():
                readme_files.append({
                    'file_path': file_path,
                    'file_content': file_info['content']
                })
            # 其他重要文件
            elif any(key.lower() in file_path.lower() for key in important_repo_files_keys):
                other_important_files.append({
                    'file_path': file_path,
                    'file_content': file_info['content']
                })
        
        # 初始化结果列表，先加入README文件（不需要摘要）
        repo_summary_list = readme_files.copy()
        current_token = get_code_abs_token(json.dumps(repo_summary_list, ensure_ascii=False, indent=2))
        if current_token >= max_tokens:
            return repo_summary_list
        elif current_token+get_code_abs_token(json.dumps(other_important_files, ensure_ascii=False, indent=2)) <= max_tokens:
            return repo_summary_list+other_important_files

        # 处理其他重要文件
        if is_file_summary:
            # 对其他文件生成摘要
            other_summary = generate_repository_summary(other_important_files, max_important_files_token=max_tokens-current_token)
            # 如果返回的是字典则转换为列表格式
            if isinstance(other_summary, dict):
                other_summary_list = [{'file_path': k, 'file_content': v} for k, v in other_summary.items()]
            else:
                other_summary_list = other_summary
            # 将其他文件的摘要添加到结果中
            repo_summary_list.extend(other_summary_list)
        else:
            # 直接添加文件内容，不生成摘要
            for file_info in other_important_files:
                if get_code_abs_token(json.dumps(file_info, ensure_ascii=False, indent=2))+current_token > max_tokens:
                    break
                repo_summary_list.append({
                    'file_path': file_info['file_path'],
                    'file_content': file_info['file_content']
                })
                
        return repo_summary_list

    def generate_llm_important_modules(self, max_tokens: int = 4000, is_file_summary: bool = True) -> str:
        """获取整个仓库最核心的部分代码"""
        out_content_list = []
        repo_summary_list = self.get_repo_summary_list(max_tokens, is_file_summary)
        out_content_list.append("# 仓库核心文件摘要\n")
        out_content_list.append(json.dumps(repo_summary_list, ensure_ascii=False))
        # out_content_list.append(json.dumps([{'file_summary': file_info['file_content']} for file_info in repo_summary_list], indent=2, ensure_ascii=False))
        
        # 基于重要性加权获取关键模块代码， 通过tree-sitter生成代码结构摘要
        if 'key_modules' in self.code_tree and self.code_tree['key_modules']:
            important_codes_list = {}
            out_content_list.append("# 关键模块抽象代码树\n")                
            
            key_modules = self.code_tree['key_modules']
            for idx, module in enumerate(key_modules):
                if module['path'] in repo_summary_list:
                    continue
                
                if '/' not in module['path']:
                    key_modules[idx]['importance_score'] = key_modules[idx]['importance_score']*5
            
            key_modules.sort(key=lambda x: x['importance_score'], reverse=True)
            
            for module in key_modules:
                if get_code_abs_token("\n".join(out_content_list)) > max_tokens:
                    break
                code_content = self.modules[module['id']]['content']
                module_path = self.modules[module['id']]['path']
                tree_sitter_summary = _get_code_abs(module_path, code_content, child_context=False)
                
                important_codes_list[module['id']] = {
                    'name': module['name'],
                    'id': module['id'],
                    'path': module_path,
                    'content': code_content,
                    'tree_sitter_summary': tree_sitter_summary
                }
                
                # out_content_list.append(f"```python\n## {self.modules[module['id']]['path']}\n")
                # out_content_list.append(tree_sitter_summary+"\n```\n")
                out_content_list.append(f"```python\n## {self.modules[module['id']]['path']}\n"+tree_sitter_summary+"\n```\n")
            
            other_content_list = []
            for module in self.code_tree['key_modules'][:20]:
                if module['id'] not in important_codes_list:
                    other_content_list.append(self.modules[module['id']]['path'])
            if other_content_list:
                out_content_list.append("# 其他关键模块文件名\n")
                out_content_list.append("```"+"\n".join(other_content_list)+"\n```\n")

        return "```\n"+json.dumps(out_content_list, indent=2, ensure_ascii=False)+"\n```"           

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("/mnt/ceph/huacan/Code/Tasks/envs/.env")
    
    # 或者更详细的方式
    builder = GlobalCodeTreeBuilder('git_repos/fish-speech')
    
    builder.parse_repository()
    builder.save_code_tree('res/code_tree.pkl')
    
    # 保存为JSON格式
    builder.save_json('res/code_tree.json')
    
    content = builder.generate_llm_important_modules()
    print(content)
    
    # content = builder.generate_llm_important_class()
    # print(content)