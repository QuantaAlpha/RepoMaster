#!/usr/bin/env python
"""
代码重要性分析器 - 用于评估代码库中各组件的重要性

此模块提供了多种方法来分析代码重要性，包括：
1. 基于权重的综合评分模型
2. 语义分析
3. 代码复杂度分析
4. Git提交历史分析
"""

import os
import re
import subprocess
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Union, Any

class ImportanceAnalyzer:
    """代码重要性分析器类，用于评估代码库中各组件的重要性"""
    
    def __init__(self, repo_path: str, modules: Dict, classes: Dict, 
                 functions: Dict, imports: Dict, code_tree: Dict,
                 call_graph: Optional[nx.DiGraph] = None, weights: Optional[Dict] = None):
        """
        初始化重要性分析器
        
        Args:
            repo_path: 代码仓库的路径
            modules: 模块信息字典
            classes: 类信息字典
            functions: 函数信息字典
            imports: 导入信息字典
            code_tree: 代码树结构
            call_graph: 函数调用图 (可选)
            weights: 重要性计算的权重 (可选)
        """
        self.repo_path = repo_path
        self.modules = modules
        self.classes = classes
        self.functions = functions
        self.imports = imports
        self.code_tree = code_tree
        self.call_graph = call_graph
        
        # 定义重要性计算的权重
        default_weights = {
            'key_component': 0.0,    # 关键组件的权重
            'usage': 2.0,            # 使用频率的权重
            'imports_relationships': 3, # 模块间引用关系的权重
            'complexity': 1.0,       # 代码复杂度的权重
            'semantic': 0.5,         # 语义重要性的权重
            'documentation': 0.0,    # 文档完整性的权重
            'git_history': 4.0,      # Git历史的权重
            'size': 0.0              # 代码大小的权重
        }

        
        # 如果传入自定义权重，则更新默认权重
        self.weights = default_weights
        if weights:
            self.weights.update(weights)
        
        # 重要的语义关键词
        self.important_keywords = [
            'main', 'core', 'engine', 'api', 'service',
            'controller', 'manager', 'handler', 'processor',
            'factory', 'builder', 'provider', 'repository',
            'executor', 'scheduler', 'config', 'security'
        ]
        
        # 构建模块引用关系图
        self.module_dependency_graph = self._build_module_dependency_graph()

    def _build_module_dependency_graph(self) -> nx.DiGraph:
        """构建模块之间的引用关系图"""
        graph = nx.DiGraph()
        
        # 添加所有模块作为节点
        for module_id in self.modules:
            graph.add_node(module_id)
        
        # 添加导入关系作为边
        for module_id, imports_list in self.imports.items():
            for imp in imports_list:
                if imp['type'] == 'import':
                    imported_module = imp['name']
                    # 检查导入的是否为已知模块
                    if imported_module in self.modules:
                        graph.add_edge(module_id, imported_module)
                elif imp['type'] == 'importfrom':
                    imported_module = imp['module']
                    # 检查导入的是否为已知模块
                    if imported_module in self.modules:
                        graph.add_edge(module_id, imported_module)
        
        return graph

    def calculate_node_importance(self, node: Dict) -> float:
        """
        计算节点的重要性分数
        
        Args:
            node: 节点信息
            
        Returns:
            重要性分数 (0.0 - 10.0)
        """
        # 如果节点类型不是module或package，返回0
        if 'type' not in node:
            return 0.0
        
        # 根据节点类型选择不同的计算方法
        if node['type'] == 'module':
            return self._calculate_module_importance(node)
        elif node['type'] == 'package':
            return self._calculate_package_importance(node)
        else:
            return 0.0
    
    def _calculate_module_importance(self, node: Dict) -> float:
        """计算模块的重要性分数"""
        importance = 0.0
        
        # # 1. 检查是否是关键组件
        # key_component_score = self._check_key_component(node)
        # importance += key_component_score * self.weights['key_component']
        
        # 2. 使用频率分析
        usage_score = self._analyze_usage(node)
        importance += usage_score * self.weights['usage']
        
        # 3. 模块间引用关系分析
        imports_score = self._analyze_imports_relationships(node)
        importance += imports_score * self.weights['imports_relationships']
        
        # 4. 代码复杂度分析
        complexity_score = self._analyze_complexity(node)
        importance += complexity_score * self.weights['complexity']
        
        # 5. 语义重要性分析
        semantic_score = self._analyze_semantic_importance(node)
        importance += semantic_score * self.weights['semantic']
        
        # # 6. 文档完整性分析
        # documentation_score = self._analyze_documentation(node)
        # importance += documentation_score * self.weights['documentation']
        
        # 7. Git历史分析
        git_score = self._analyze_git_history(node)
        importance += git_score * self.weights['git_history']
        
        # 归一化处理，保证分数在合理范围内
        return min(importance, 10.0)
    
    def _calculate_package_importance(self, node: Dict) -> float:
        """计算包的重要性分数"""
        # 包的重要性基于其包含的模块和子包
        importance = 0.0
        
        # 1. 语义重要性分析
        if 'name' in node:
            semantic_score = self._semantic_importance(node['name'])
            importance += semantic_score * self.weights['semantic']
        
        # 2. 包含的子节点重要性
        if 'children' in node and node['children']:
            child_scores = []
            for child in node['children'].values():
                child_score = self.calculate_node_importance(child)
                child_scores.append(child_score)
            
            if child_scores:
                # 结合最大值和平均值
                max_score = max(child_scores)
                avg_score = sum(child_scores) / len(child_scores)
                # 最大值权重更高
                importance += (max_score * 0.7 + avg_score * 0.3) * 1.5
        
        # 包的特殊性，如果包名是特殊的，给予额外分数
        if 'name' in node:
            if node['name'] in ['src', 'core', 'main', 'api']:
                importance += 2.0
        
        # 归一化处理
        return min(importance, 10.0)
    
    def _analyze_imports_relationships(self, node: Dict) -> float:
        """分析模块间引用关系的重要性"""
        score = 0.0
        
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            
            if module_id in self.module_dependency_graph:
                # 计算入度 - 被多少其他模块导入
                in_degree = self.module_dependency_graph.in_degree(module_id)
                # 计算出度 - 导入了多少其他模块
                out_degree = self.module_dependency_graph.out_degree(module_id)
                
                # 计算PageRank值 - 反映模块在整个依赖网络中的中心性
                if len(self.module_dependency_graph.nodes()) > 0:
                    try:
                        pagerank = nx.pagerank(
                            self.module_dependency_graph, 
                            alpha=0.85,
                            personalization={n: 2.0 if n == module_id else 1.0 for n in self.module_dependency_graph.nodes()}
                        )
                        pagerank_score = pagerank.get(module_id, 0.0) * 10  # 放大PageRank值
                    except:
                        pagerank_score = 0.0
                else:
                    pagerank_score = 0.0
                
                # 计算模块的中间中心性 - 反映模块作为"桥梁"的重要性
                betweenness = 0.0
                if len(self.module_dependency_graph.nodes()) > 1:
                    try:
                        # 因为计算中间中心性可能很耗时，使用估算方法
                        between_dict = nx.betweenness_centrality(
                            self.module_dependency_graph,
                            k=min(20, len(self.module_dependency_graph.nodes())),  # 采样更少的节点加速计算
                            normalized=True
                        )
                        betweenness = between_dict.get(module_id, 0.0)
                    except:
                        betweenness = 0.0
                
                # 计算模块的综合引用重要性分数
                # 入度权重最高 - 被大量引用的模块更重要
                in_degree_score = min(in_degree / 5.0, 1.0) * 0.5
                # 出度适中 - 过多依赖可能不是好事
                out_degree_score = min(out_degree / 10.0, 1.0) * 0.2
                # PageRank反映整体网络中的重要性
                pagerank_score = min(pagerank_score, 1.0) * 0.6
                # 中间中心性反映桥接作用
                betweenness_score = min(betweenness * 10, 1.0) * 0.4
                
                # 将所有分数结合
                score = (in_degree_score + out_degree_score + pagerank_score + betweenness_score) / 1.7
                
                # 如果模块是重要的"根模块"(被多个模块引用但几乎不引用其他模块)
                if in_degree > 2 and out_degree <= 1:
                    score += 0.3
                    
                # 如果模块是关键的"集成模块"(既引用很多模块也被很多模块引用)
                if in_degree > 2 and out_degree > 2:
                    score += 0.2
        
        return min(score, 1.0)
    
    def _check_key_component(self, node: Dict) -> float:
        """检查节点是否是关键组件"""
        # 初始分数为0
        score = 0.0
        
        # 检查节点ID是否在关键组件列表中
        if 'id' in node:
            for component in self.code_tree['key_components']:
                # 完全匹配
                if component.get('id') == node['id']:
                    score = 1.0
                    break
                # 部分匹配（模块包含关键组件）
                if 'module' in component and component['module'] == node['id']:
                    score = 0.8
                    break
        
        return score
    
    def _analyze_usage(self, node: Dict) -> float:
        """分析节点的使用频率"""
        score = 0.0
        
        # 如果是模块，检查被导入的次数
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            # 计算其他模块导入此模块的次数
            import_count = 0
            for imports in self.imports.values():
                for imp in imports:
                    if (imp['type'] == 'import' and imp['name'] == module_id) or \
                       (imp['type'] == 'importfrom' and imp['module'] == module_id):
                        import_count += 1
            
            # 归一化使用频率分数
            score = min(import_count / 5.0, 1.0)
            
            # 检查该模块包含的函数和类被调用的次数
            if 'functions' in node:
                func_call_count = 0
                for func_ref in node['functions']:
                    if isinstance(func_ref, dict) and 'id' in func_ref:
                        func_id = func_ref['id']
                        if func_id in self.functions:
                            func_call_count += len(self.functions[func_id].get('called_by', []))
                
                # 添加函数调用频率分数
                score += min(func_call_count / 10.0, 1.0) * 0.5

            if 'classes' in node:
                class_call_count = 0
                for class_ref in node['classes']:
                    if isinstance(class_ref, dict) and 'id' in class_ref:
                        class_id = class_ref['id']
                        if class_id in self.classes:
                            class_call_count += len(self.classes[class_id].get('called_by', []))
                
                # 添加类调用频率分数
                score += min(class_call_count / 10.0, 1.0) * 0.5
        
        return score
    
    def _analyze_complexity(self, node: Dict) -> float:
        """分析节点的代码复杂度"""
        score = 0.0
        
        # 如果是模块，分析其复杂度
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            if module_id in self.modules and 'content' in self.modules[module_id]:
                content = self.modules[module_id]['content']
                
                # 计算分支和循环的数量
                lines = content.splitlines()
                if_count = sum(1 for line in lines if re.search(r'\bif\b', line))
                for_count = sum(1 for line in lines if re.search(r'\bfor\b', line))
                while_count = sum(1 for line in lines if re.search(r'\bwhile\b', line))
                except_count = sum(1 for line in lines if re.search(r'\bexcept\b', line))
                
                # 计算总的分支数
                branch_count = if_count + for_count + while_count + except_count
                
                # 归一化复杂度分数
                score = min(branch_count / 50.0, 1.0)
                
                # 检查函数的嵌套深度
                def_pattern = re.compile(r'^(\s*)def\s+', re.MULTILINE)
                matches = def_pattern.findall(content)
                if matches:
                    # 计算最大缩进级别
                    max_indent = max(len(indent) for indent in matches)
                    indent_level = max_indent / 4  # 假设每级缩进是4个空格
                    
                    # 添加嵌套深度分数
                    score += min(indent_level / 5.0, 1.0) * 0.3
        
        return score
    
    def _analyze_semantic_importance(self, node: Dict) -> float:
        """分析节点的语义重要性"""
        score = 0.0
        
        # 从节点名称中提取语义信息
        if 'name' in node:
            score += self._semantic_importance(node['name'])
        
        # 从节点ID中提取语义信息
        if 'id' in node:
            module_parts = node['id'].split('.')
            for part in module_parts:
                score += self._semantic_importance(part) * 0.5  # 减小权重，避免重复计算
        
        # 归一化分数
        return min(score, 1.0)
    
    def _semantic_importance(self, name: str) -> float:
        """基于名称的语义重要性分析"""
        score = 0.0
        name_lower = name.lower()
        
        # 检查是否包含重要关键词
        for keyword in self.important_keywords:
            if keyword in name_lower:
                score += 0.3
                break
        
        # 特殊处理入口点
        if name == '__main__' or name == 'main':
            score += 0.7
        
        # 处理常见的重要文件名
        if name in ['__init__', 'app', 'settings', 'config', 'utils', 'constants']:
            score += 0.5
        
        return min(score, 1.0)
    
    def _analyze_documentation(self, node: Dict) -> float:
        """分析节点的文档完整性"""
        score = 0.0
        
        # 检查是否有文档字符串
        if 'docstring' in node and node['docstring']:
            docstring = node['docstring']
            
            # 基于文档长度的基础分数
            score = min(len(docstring) / 200.0, 1.0) * 0.7
            
            # 检查文档质量
            # 1. 是否包含参数说明
            if 'Args:' in docstring or 'Parameters:' in docstring:
                score += 0.15
            
            # 2. 是否包含返回值说明
            if 'Returns:' in docstring or 'Return:' in docstring:
                score += 0.15
            
            # 3. 是否包含示例
            if 'Example:' in docstring or 'Examples:' in docstring:
                score += 0.1
        
        return min(score, 1.0)
    
    def _analyze_size(self, node: Dict) -> float:
        """分析节点的代码大小"""
        score = 0.0
        
        # 检查节点是否有行数信息
        if 'lines' in node:
            # 基于行数计算分数，较大的文件可能更重要，但有上限
            score = min(node['lines'] / 500.0, 1.0)
        
        return score
    
    def _analyze_git_history(self, node: Dict) -> float:
        """分析节点的Git历史"""
        score = 0.0
        
        # 如果是模块，获取对应文件的路径
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            if module_id in self.modules and 'path' in self.modules[module_id]:
                file_path = os.path.join(self.repo_path, self.modules[module_id]['path'])
                
                # 获取Git历史信息
                score = self.get_file_history_importance(file_path)
        
        return score
    
    def get_file_history_importance(self, file_path: str) -> float:
        """
        基于文件的Git历史计算重要性
        
        Args:
            file_path: 文件路径
            
        Returns:
            重要性分数 (0.0 - 1.0)
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return 0.0
            
            # 检查是否在Git仓库中
            repo_dir = os.path.dirname(file_path)
            if not os.path.exists(os.path.join(repo_dir, '.git')) and \
               not os.path.exists(os.path.join(self.repo_path, '.git')):
                # 尝试向上查找.git目录
                current_dir = repo_dir
                found_git = False
                for _ in range(5):  # 限制向上查找的次数
                    parent_dir = os.path.dirname(current_dir)
                    if parent_dir == current_dir:  # 已到达根目录
                        break
                    if os.path.exists(os.path.join(parent_dir, '.git')):
                        found_git = True
                        break
                    current_dir = parent_dir
                
                if not found_git:
                    return 0.0  # 不在Git仓库中
            
            # 获取提交次数
            try:
                rel_path = os.path.relpath(file_path, self.repo_path)
                cmd = ['git', '-C', self.repo_path, 'log', '--oneline', '--', rel_path]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                if result.returncode == 0:
                    commit_lines = result.stdout.strip().split('\n')
                    commit_count = len([line for line in commit_lines if line])
                    
                    # 根据提交次数计算分数
                    score = min(commit_count / 20.0, 1.0)
                    
                    # 获取最后修改时间
                    cmd_last_commit = ['git', '-C', self.repo_path, 'log', '-1', '--format=%at', '--', rel_path]
                    result_last = subprocess.run(cmd_last_commit, capture_output=True, text=True, check=False)
                    
                    if result_last.returncode == 0 and result_last.stdout.strip():
                        import time
                        try:
                            last_commit_time = int(result_last.stdout.strip())
                            current_time = int(time.time())
                            days_since_last_commit = (current_time - last_commit_time) / (60 * 60 * 24)
                            
                            # 最近修改的文件可能更重要
                            recency_score = max(0, 1.0 - (days_since_last_commit / 365))
                            
                            # 结合提交次数和最近修改时间
                            score = (score * 0.7) + (recency_score * 0.3)
                        except:
                            pass
                    
                    return score
                
                return 0.0
            
            except subprocess.SubprocessError:
                return 0.0
                
        except Exception:
            return 0.0
