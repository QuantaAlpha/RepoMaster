#!/usr/bin/env python
"""
Code Importance Analyzer - Used to evaluate the importance of various components in a code repository

This module provides multiple methods to analyze code importance, including:
1. Weight-based comprehensive scoring model
2. Semantic analysis
3. Code complexity analysis
4. Git commit history analysis
"""

import os
import re
import subprocess
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Union, Any

class ImportanceAnalyzer:
    """Code importance analyzer class, used to evaluate the importance of various components in a code repository"""
    
    def __init__(self, repo_path: str, modules: Dict, classes: Dict, 
                 functions: Dict, imports: Dict, code_tree: Dict,
                 call_graph: Optional[nx.DiGraph] = None, weights: Optional[Dict] = None):
        """
        Initialize importance analyzer
        
        Args:
            repo_path: Path to the code repository
            modules: Module information dictionary
            classes: Class information dictionary
            functions: Function information dictionary
            imports: Import information dictionary
            code_tree: Code tree structure
            call_graph: Function call graph (optional)
            weights: Weights for importance calculation (optional)
        """
        self.repo_path = repo_path
        self.modules = modules
        self.classes = classes
        self.functions = functions
        self.imports = imports
        self.code_tree = code_tree
        self.call_graph = call_graph
        
        # Define weights for importance calculation
        default_weights = {
            'key_component': 0.0,    # Weight for key components
            'usage': 2.0,            # Weight for usage frequency
            'imports_relationships': 3, # Weight for inter-module reference relationships
            'complexity': 1.0,       # Weight for code complexity
            'semantic': 0.5,         # Weight for semantic importance
            'documentation': 0.0,    # Weight for documentation completeness
            'git_history': 4.0,      # Weight for Git history
            'size': 0.0              # Weight for code size
        }

        
        # If custom weights are provided, update default weights
        self.weights = default_weights
        if weights:
            self.weights.update(weights)
        
        # Important semantic keywords
        self.important_keywords = [
            'main', 'core', 'engine', 'api', 'service',
            'controller', 'manager', 'handler', 'processor',
            'factory', 'builder', 'provider', 'repository',
            'executor', 'scheduler', 'config', 'security'
        ]
        
        # Build module dependency graph
        self.module_dependency_graph = self._build_module_dependency_graph()

    def _build_module_dependency_graph(self) -> nx.DiGraph:
        """Build dependency graph between modules"""
        graph = nx.DiGraph()
        
        # Add all modules as nodes
        for module_id in self.modules:
            graph.add_node(module_id)
        
        # Add import relationships as edges
        for module_id, imports_list in self.imports.items():
            for imp in imports_list:
                if imp['type'] == 'import':
                    imported_module = imp['name']
                    # Check if the imported module is a known module
                    if imported_module in self.modules:
                        graph.add_edge(module_id, imported_module)
                elif imp['type'] == 'importfrom':
                    imported_module = imp['module']
                    # Check if the imported module is a known module
                    if imported_module in self.modules:
                        graph.add_edge(module_id, imported_module)
        
        return graph

    def calculate_node_importance(self, node: Dict) -> float:
        """
        Calculate importance score of a node
        
        Args:
            node: Node information
            
        Returns:
            Importance score (0.0 - 10.0)
        """
        # If node type is not module or package, return 0
        if 'type' not in node:
            return 0.0
        
        # Choose different calculation methods based on node type
        if node['type'] == 'module':
            return self._calculate_module_importance(node)
        elif node['type'] == 'package':
            return self._calculate_package_importance(node)
        else:
            return 0.0
    
    def _calculate_module_importance(self, node: Dict) -> float:
        """Calculate importance score of a module"""
        importance = 0.0
        
        # # 1. Check if it's a key component
        # key_component_score = self._check_key_component(node)
        # importance += key_component_score * self.weights['key_component']
        
        # 2. Usage frequency analysis
        usage_score = self._analyze_usage(node)
        importance += usage_score * self.weights['usage']
        
        # 3. Inter-module reference relationship analysis
        imports_score = self._analyze_imports_relationships(node)
        importance += imports_score * self.weights['imports_relationships']
        
        # 4. Code complexity analysis
        complexity_score = self._analyze_complexity(node)
        importance += complexity_score * self.weights['complexity']
        
        # 5. Semantic importance analysis
        semantic_score = self._analyze_semantic_importance(node)
        importance += semantic_score * self.weights['semantic']
        
        # # 6. Documentation completeness analysis
        # documentation_score = self._analyze_documentation(node)
        # importance += documentation_score * self.weights['documentation']
        
        # 7. Git history analysis
        git_score = self._analyze_git_history(node)
        importance += git_score * self.weights['git_history']
        
        # Normalization to ensure score is within reasonable range
        return min(importance, 10.0)
    
    def _calculate_package_importance(self, node: Dict) -> float:
        """Calculate package importance score"""
        # Package importance is based on the modules and sub-packages it contains
        importance = 0.0
        
        # 1. Semantic importance analysis
        if 'name' in node:
            semantic_score = self._semantic_importance(node['name'])
            importance += semantic_score * self.weights['semantic']
        
        # 2. Importance of contained child nodes
        if 'children' in node and node['children']:
            child_scores = []
            for child in node['children'].values():
                child_score = self.calculate_node_importance(child)
                child_scores.append(child_score)
            
            if child_scores:
                # Combine maximum and average values
                max_score = max(child_scores)
                avg_score = sum(child_scores) / len(child_scores)
                # Maximum value has higher weight
                importance += (max_score * 0.7 + avg_score * 0.3) * 1.5
        
        # Package specificity, if package name is special, give extra points
        if 'name' in node:
            if node['name'] in ['src', 'core', 'main', 'api']:
                importance += 2.0
        
        # Normalization processing
        return min(importance, 10.0)
    
    def _analyze_imports_relationships(self, node: Dict) -> float:
        """Analyze the importance of inter-module reference relationships"""
        score = 0.0
        
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            
            if module_id in self.module_dependency_graph:
                # Calculate in-degree - how many other modules import this
                in_degree = self.module_dependency_graph.in_degree(module_id)
                # Calculate out-degree - how many other modules this imports
                out_degree = self.module_dependency_graph.out_degree(module_id)
                
                # Calculate PageRank value - reflects module's centrality in the entire dependency network
                if len(self.module_dependency_graph.nodes()) > 0:
                    try:
                        pagerank = nx.pagerank(
                            self.module_dependency_graph, 
                            alpha=0.85,
                            personalization={n: 2.0 if n == module_id else 1.0 for n in self.module_dependency_graph.nodes()}
                        )
                        pagerank_score = pagerank.get(module_id, 0.0) * 10  # Amplify PageRank value
                    except:
                        pagerank_score = 0.0
                else:
                    pagerank_score = 0.0
                
                # Calculate module's betweenness centrality - reflects module's importance as a "bridge"
                betweenness = 0.0
                if len(self.module_dependency_graph.nodes()) > 1:
                    try:
                        # Since computing betweenness centrality can be time-consuming, use estimation method
                        between_dict = nx.betweenness_centrality(
                            self.module_dependency_graph,
                            k=min(20, len(self.module_dependency_graph.nodes())),  # Sample fewer nodes to speed up computation
                            normalized=True
                        )
                        betweenness = between_dict.get(module_id, 0.0)
                    except:
                        betweenness = 0.0
                
                # Calculate comprehensive reference importance score for module
                # In-degree weight is highest - modules referenced by many others are more important
                in_degree_score = min(in_degree / 5.0, 1.0) * 0.5
                # Out-degree is moderate - too many dependencies may not be good
                out_degree_score = min(out_degree / 10.0, 1.0) * 0.2
                # PageRank reflects importance in overall network
                pagerank_score = min(pagerank_score, 1.0) * 0.6
                # Betweenness centrality reflects bridging role
                betweenness_score = min(betweenness * 10, 1.0) * 0.4
                
                # Combine all scores
                score = (in_degree_score + out_degree_score + pagerank_score + betweenness_score) / 1.7
                
                # If module is an important "root module" (referenced by many modules but references few others)
                if in_degree > 2 and out_degree <= 1:
                    score += 0.3
                    
                # If module is a key "integration module" (both references many modules and is referenced by many modules)
                if in_degree > 2 and out_degree > 2:
                    score += 0.2
        
        return min(score, 1.0)
    
    def _check_key_component(self, node: Dict) -> float:
        """Check if node is a key component"""
        # Initial score is 0
        score = 0.0
        
        # Check if node ID is in key components list
        if 'id' in node:
            for component in self.code_tree['key_components']:
                # Exact match
                if component.get('id') == node['id']:
                    score = 1.0
                    break
                # Partial match (module contains key component)
                if 'module' in component and component['module'] == node['id']:
                    score = 0.8
                    break
        
        return score
    
    def _analyze_usage(self, node: Dict) -> float:
        """Analyze node usage frequency"""
        score = 0.0
        
        # If it's a module, check how many times it's imported
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            # Count how many other modules import this module
            import_count = 0
            for imports in self.imports.values():
                for imp in imports:
                    if (imp['type'] == 'import' and imp['name'] == module_id) or \
                       (imp['type'] == 'importfrom' and imp['module'] == module_id):
                        import_count += 1
            
            # Normalize usage frequency score
            score = min(import_count / 5.0, 1.0)
            
            # Check how many times functions and classes in this module are called
            if 'functions' in node:
                func_call_count = 0
                for func_ref in node['functions']:
                    if isinstance(func_ref, dict) and 'id' in func_ref:
                        func_id = func_ref['id']
                        if func_id in self.functions:
                            func_call_count += len(self.functions[func_id].get('called_by', []))
                
                # Add function call frequency score
                score += min(func_call_count / 10.0, 1.0) * 0.5

            if 'classes' in node:
                class_call_count = 0
                for class_ref in node['classes']:
                    if isinstance(class_ref, dict) and 'id' in class_ref:
                        class_id = class_ref['id']
                        if class_id in self.classes:
                            class_call_count += len(self.classes[class_id].get('called_by', []))
                
                # Add class call frequency score
                score += min(class_call_count / 10.0, 1.0) * 0.5
        
        return score
    
    def _analyze_complexity(self, node: Dict) -> float:
        """Analyze node code complexity"""
        score = 0.0
        
        # If it's a module, analyze its complexity
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            if module_id in self.modules and 'content' in self.modules[module_id]:
                content = self.modules[module_id]['content']
                
                # Count branches and loops
                lines = content.splitlines()
                if_count = sum(1 for line in lines if re.search(r'\bif\b', line))
                for_count = sum(1 for line in lines if re.search(r'\bfor\b', line))
                while_count = sum(1 for line in lines if re.search(r'\bwhile\b', line))
                except_count = sum(1 for line in lines if re.search(r'\bexcept\b', line))
                
                # Calculate total branch count
                branch_count = if_count + for_count + while_count + except_count
                
                # Normalize complexity score
                score = min(branch_count / 50.0, 1.0)
                
                # Check function nesting depth
                def_pattern = re.compile(r'^(\s*)def\s+', re.MULTILINE)
                matches = def_pattern.findall(content)
                if matches:
                    # Calculate maximum indentation level
                    max_indent = max(len(indent) for indent in matches)
                    indent_level = max_indent / 4  # Assume each indentation level is 4 spaces
                    
                    # Add nesting depth score
                    score += min(indent_level / 5.0, 1.0) * 0.3
        
        return score
    
    def _analyze_semantic_importance(self, node: Dict) -> float:
        """Analyze node semantic importance"""
        score = 0.0
        
        # Extract semantic information from node name
        if 'name' in node:
            score += self._semantic_importance(node['name'])
        
        # Extract semantic information from node ID
        if 'id' in node:
            module_parts = node['id'].split('.')
            for part in module_parts:
                score += self._semantic_importance(part) * 0.5  # Reduce weight to avoid double counting
        
        # Normalize score
        return min(score, 1.0)
    
    def _semantic_importance(self, name: str) -> float:
        """Semantic importance analysis based on name"""
        score = 0.0
        name_lower = name.lower()
        
        # Check if contains important keywords
        for keyword in self.important_keywords:
            if keyword in name_lower:
                score += 0.3
                break
        
        # Special handling for entry points
        if name == '__main__' or name == 'main':
            score += 0.7
        
        # Handle common important file names
        if name in ['__init__', 'app', 'settings', 'config', 'utils', 'constants']:
            score += 0.5
        
        return min(score, 1.0)
    
    def _analyze_documentation(self, node: Dict) -> float:
        """Analyze node documentation completeness"""
        score = 0.0
        
        # Check if has docstring
        if 'docstring' in node and node['docstring']:
            docstring = node['docstring']
            
            # Base score based on documentation length
            score = min(len(docstring) / 200.0, 1.0) * 0.7
            
            # Check documentation quality
            # 1. Contains parameter description
            if 'Args:' in docstring or 'Parameters:' in docstring:
                score += 0.15
            
            # 2. Contains return value description
            if 'Returns:' in docstring or 'Return:' in docstring:
                score += 0.15
            
            # 3. Contains examples
            if 'Example:' in docstring or 'Examples:' in docstring:
                score += 0.1
        
        return min(score, 1.0)
    
    def _analyze_size(self, node: Dict) -> float:
        """Analyze node code size"""
        score = 0.0
        
        # Check if node has line count information
        if 'lines' in node:
            # Calculate score based on line count, larger files may be more important, but with upper limit
            score = min(node['lines'] / 500.0, 1.0)
        
        return score
    
    def _analyze_git_history(self, node: Dict) -> float:
        """Analyze node Git history"""
        score = 0.0
        
        # If it's a module, get the corresponding file path
        if node['type'] == 'module' and 'id' in node:
            module_id = node['id']
            if module_id in self.modules and 'path' in self.modules[module_id]:
                file_path = os.path.join(self.repo_path, self.modules[module_id]['path'])
                
                # Get Git history information
                score = self.get_file_history_importance(file_path)
        
        return score
    
    def get_file_history_importance(self, file_path: str) -> float:
        """
        Calculate importance based on file's Git history
        
        Args:
            file_path: File path
            
        Returns:
            Importance score (0.0 - 1.0)
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return 0.0
            
            # Check if in Git repository
            repo_dir = os.path.dirname(file_path)
            if not os.path.exists(os.path.join(repo_dir, '.git')) and \
               not os.path.exists(os.path.join(self.repo_path, '.git')):
                # Try to find .git directory upwards
                current_dir = repo_dir
                found_git = False
                for _ in range(5):  # Limit upward search count
                    parent_dir = os.path.dirname(current_dir)
                    if parent_dir == current_dir:  # Reached root directory
                        break
                    if os.path.exists(os.path.join(parent_dir, '.git')):
                        found_git = True
                        break
                    current_dir = parent_dir
                
                if not found_git:
                    return 0.0  # Not in Git repository
            
            # Get commit count
            try:
                rel_path = os.path.relpath(file_path, self.repo_path)
                cmd = ['git', '-C', self.repo_path, 'log', '--oneline', '--', rel_path]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                if result.returncode == 0:
                    commit_lines = result.stdout.strip().split('\n')
                    commit_count = len([line for line in commit_lines if line])
                    
                    # Calculate score based on commit count
                    score = min(commit_count / 20.0, 1.0)
                    
                    # Get last modification time
                    cmd_last_commit = ['git', '-C', self.repo_path, 'log', '-1', '--format=%at', '--', rel_path]
                    result_last = subprocess.run(cmd_last_commit, capture_output=True, text=True, check=False)
                    
                    if result_last.returncode == 0 and result_last.stdout.strip():
                        import time
                        try:
                            last_commit_time = int(result_last.stdout.strip())
                            current_time = int(time.time())
                            days_since_last_commit = (current_time - last_commit_time) / (60 * 60 * 24)
                            
                            # Recently modified files may be more important
                            recency_score = max(0, 1.0 - (days_since_last_commit / 365))
                            
                            # Combine commit count and recent modification time
                            score = (score * 0.7) + (recency_score * 0.3)
                        except:
                            pass
                    
                    return score
                
                return 0.0
            
            except subprocess.SubprocessError:
                return 0.0
                
        except Exception:
            return 0.0
