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

# Modify tree-sitter import
import tree_sitter
from tree_sitter_language_pack import get_language, get_parser

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GlobalCodeTreeBuilder:
    """Global code tree builder, used to parse code repositories and build LLM-friendly structured representations"""
    
    def __init__(self, repo_path: str):
        """
        Initialize code tree builder
        
        Args:
            repo_path: Path to the code repository
            ignored_dirs: List of directories to ignore
            ignored_file_patterns: List of file patterns to ignore
        """
        self.repo_path = repo_path
        self.call_graph = nx.DiGraph()  # Function call graph
        self.modules = {}  # Module information
        self.functions = {}  # Function information
        self.classes = {}  # Class information
        self.other_files = {}  # Other file information
        self.imports = defaultdict(list)  # Import information
        self.code_tree = {  # Hierarchical code tree
            'modules': {},
            'stats': {
                'total_modules': 0,
                'total_classes': 0,
                'total_functions': 0,
                'total_lines': 0
            },
            'key_components': []  # Key components
        }
        
        # Uniformly define directories and file patterns to ignore, use defaults if not provided in parameters
        self.ignored_dirs = ignored_dirs
        self.ignored_file_patterns = ignored_file_patterns
        
        # Check if Jupyter Notebook parsing is supported
        self.jupyter_support = False
        try:
            import nbformat
            self.jupyter_support = True
            logger.info("Successfully loaded nbformat library, will support Jupyter Notebook parsing")
        except ImportError:
            logger.warning("Unable to import nbformat library, will skip Jupyter Notebook parsing")
        
        # Initialize tree-sitter
        self.parser = None
        self.python_language = None
        
        if tree_sitter is not None:
            try:
                # Use tree_sitter_languages to simplify language loading
                self.parser = get_parser('python')
                self.python_language = get_language('python')
                if self.parser and self.python_language:
                    logger.info("Successfully loaded tree-sitter Python language")
                else:
                    logger.warning("Unable to load tree-sitter Python language")
            except Exception as e:
                logger.warning(f"Unable to initialize tree-sitter: {e}, will use simple code display")
        else:
            logger.warning("tree-sitter library not available, will use simple code display")
        
    def parse_repository(self) -> None:
        """Parse the entire code repository"""
        logger.info(f"Starting to parse code repository: {self.repo_path}")
        
        # Find and parse all Python files and Jupyter Notebook files
        for root, dirs, files in os.walk(self.repo_path):
            # Calculate current directory depth (relative to repository root)
            rel_path = os.path.relpath(root, self.repo_path)
            current_depth = 0 if rel_path == '.' else len(rel_path.split(os.sep))
            
            # If directory depth exceeds 5, skip this directory and its subdirectories
            if current_depth > 3:
                dirs[:] = []  # Clear dirs list so os.walk won't enter subdirectories
                # logger.info(f"Directory {rel_path} depth exceeds 4, skipping this directory and its subdirectories")
                continue
            
            # Modify dirs list in place, skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            
            # Limit processing to maximum 40 files per directory
            file_count = 0
            max_files_per_dir = 40
            
            if len(files) > 100:
                continue
            elif len(files) > 50:
                files = files[:5]
            
            
            for file in files:
                # If already processed 40 files, ignore remaining files in this directory
                if file_count >= max_files_per_dir:
                    # logger.info(f"Directory {rel_path} contains more than {max_files_per_dir} files, ignoring remaining files")
                    break
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repo_path)
                
                # Use unified function to check if should be ignored
                if should_ignore_path(rel_path):
                    continue
                
                # Add before processing files
                file_size = os.path.getsize(file_path)
                if file_size > 10 * 1024 * 1024:  # Skip files larger than 10MB
                    # logger.info(f"File {rel_path} is too large ({file_size/1024/1024:.2f}MB), skipping")
                    continue
                
                try:
                    if file.endswith('.py'):
                        self._parse_python_file(file_path, rel_path)
                    else:
                        self._parse_other_file(file_path, rel_path)
                    
                    # Increment count after successfully processing file
                    file_count += 1
                    
                except Exception as e:
                    logger.error(f"Error parsing file {rel_path}: {e}", exc_info=True)
        
        # Build various relationships
        self._build_call_relationships()
        self._build_hierarchical_code_tree()
        
        # Identify key components
        self._identify_key_class()
        
        # Identify key modules
        key_modules = self._identify_key_modules()
        if key_modules:
            self.code_tree['key_modules'] = key_modules
            logger.info(f"Identified {len(key_modules)} key modules")
        
        logger.info(f"Code repository parsing completed, found {len(self.modules)} modules, {len(self.classes)} classes, {len(self.functions)} functions")
    
    def _parse_python_file(self, file_path: str, rel_path: str) -> None:
        """
        Parse single Python file
        
        Args:
            file_path: Absolute path of the file
            rel_path: Path relative to repository root
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            module_node = ast.parse(content, filename=rel_path)
            module_docstring = ast.get_docstring(module_node) or ""
            
            # Create module ID with dot-separated path
            module_id = rel_path.replace('/', '.').replace('\\', '.').replace('.py', '')
            self.modules[module_id] = {
                'path': rel_path,
                'docstring': module_docstring,
                'content': content,
                'functions': [],
                'classes': []
            }
            
            # Process import statements
            self._process_imports(module_node, module_id)
            
            # Parse functions and classes
            for node in ast.walk(module_node):
                # Process function definitions
                if isinstance(node, ast.FunctionDef):
                    if not hasattr(node, 'parent_class'):
                        self._process_function(node, module_id, None)
                
                # Process class definitions
                elif isinstance(node, ast.ClassDef):
                    class_id = f"{module_id}.{node.name}"
                    class_docstring = ast.get_docstring(node) or ""
                    
                    # Analyze class inheritance relationships
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
                    
                    # Process methods in the class
                    for class_node in node.body:
                        if isinstance(class_node, ast.FunctionDef):
                            # Add parent class attribute for method
                            class_node.parent_class = class_id
                            self._process_function(class_node, module_id, class_id)
        
        except SyntaxError as e:
            logger.warning(f"File {rel_path} has syntax errors: {e}")
        except Exception as e:
            logger.error(f"Error processing file {rel_path}: {e}")
    
    def _parse_other_file(self, file_path: str, rel_path: str) -> None:
        """
        Parse non-Python files, including Jupyter Notebooks etc
        
        Args:
            file_path: Absolute path of the file
            rel_path: Path relative to repository root
        """
        try:
            if file_path.endswith('.ipynb'):
                content = _parse_ipynb_file(file_path)
            else:
                content = open(file_path, 'r', encoding='utf-8').read()
            
            # Create a simple module record for non-Python files
            # Use file extension as "language" identifier
            file_ext = os.path.splitext(file_path)[1][1:]  # Remove the dot
            module_id = rel_path.replace('/', '.').replace('\\', '.').replace(f'.{file_ext}', '')
            
            self.other_files[module_id] = {
                'path': rel_path,
                'docstring': f"Non-Python file: {file_ext.upper()} code",
                'content': content,
                'functions': [],
                'classes': [],
                'language': file_ext
            }
            
            logger.debug(f"Recorded non-Python file: {rel_path}")
        
        except Exception as e:
            logger.error(f"Error processing non-Python file {rel_path}: {e}")
    
    def _process_imports(self, module_node: ast.Module, module_id: str) -> None:
        """Process import statements in the module"""
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
        """Process function or method definition"""
        function_name = node.name
        if class_id:
            function_id = f"{class_id}.{function_name}"
            self.classes[class_id]['methods'].append(function_id)
        else:
            function_id = f"{module_id}.{function_name}"
            self.modules[module_id]['functions'].append(function_id)
        
        docstring = ast.get_docstring(node) or ""
        
        # Get source code
        source = self._get_source(self.modules[module_id]['content'], node)
        
        # Analyze function parameters
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
        
        # Analyze function return type
        return_type = None
        if hasattr(node, 'returns') and node.returns:
            if isinstance(node.returns, ast.Name):
                return_type = node.returns.id
            elif isinstance(node.returns, ast.Attribute):
                return_type = self._get_attribute_path(node.returns)
            elif isinstance(node.returns, ast.Subscript):
                return_type = self._get_subscript_annotation(node.returns)
        
        # Analyze function calls in the function body
        calls = self._extract_function_calls(node)
        
        self.functions[function_id] = {
            'name': function_name,
            'module': module_id,
            'class': class_id,
            'docstring': docstring,
            'parameters': parameters,
            'return_type': return_type,
            'calls': calls,
            'called_by': [],  # Will be populated when building call relationships
            'source': source
        }
        
        # Add node to call graph
        self.call_graph.add_node(function_id)
    
    def _extract_function_calls(self, node: ast.FunctionDef) -> List[Dict]:
        """Extract function calls from function body"""
        calls = []
        
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                call_info = self._analyze_call(subnode)
                if call_info:
                    calls.append(call_info)
        
        return calls
    
    def _analyze_call(self, node: ast.Call) -> Optional[Dict]:
        """Analyze function call expression"""
        if isinstance(node.func, ast.Name):
            # Simple function call func()
            return {'type': 'simple', 'name': node.func.id}
        
        elif isinstance(node.func, ast.Attribute):
            # Attribute call obj.method()
            if isinstance(node.func.value, ast.Name):
                return {
                    'type': 'attribute',
                    'object': node.func.value.id,
                    'attribute': node.func.attr
                }
            # Nested attribute call module.sub.func()
            return {
                'type': 'nested_attribute',
                'full_path': self._get_attribute_path(node.func)
            }
        
        return None
    
    def _get_attribute_path(self, node: ast.Attribute) -> str:
        """Get complete attribute path (e.g. module.submodule.function)"""
        parts = []
        current = node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
        
        return '.'.join(reversed(parts))
    
    def _get_subscript_annotation(self, node: ast.Subscript) -> str:
        """Get subscript expression in type annotation (e.g. List[str])"""
        # Handle Python 3.8+
        try:
            if isinstance(node.value, ast.Name):
                container = node.value.id
            elif isinstance(node.value, ast.Attribute):
                container = self._get_attribute_path(node.value)
            else:
                return "unknown"
            
            # Compatible with Python 3.8 and earlier
            if hasattr(node, 'slice') and isinstance(node.slice, ast.Index):
                slice_value = node.slice.value
                if isinstance(slice_value, ast.Name):
                    param = slice_value.id
                elif isinstance(slice_value, ast.Attribute):
                    param = self._get_attribute_path(slice_value)
                else:
                    param = "unknown"
            # Compatible with Python 3.9+
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
        """Build call relationships between functions"""
        logger.info("Building function call relationships...")
        
        for func_id, func_info in self.functions.items():
            calls = func_info['calls']
            module_id = func_info['module']
            
            for call in calls:
                called_func_id = self._resolve_call(call, module_id, func_info['class'])
                
                if called_func_id and called_func_id in self.functions:
                    # Add to call graph
                    self.call_graph.add_edge(func_id, called_func_id)
                    
                    # Update called function information
                    if func_id not in self.functions[called_func_id]['called_by']:
                        self.functions[called_func_id]['called_by'].append(func_id)
    
    def _resolve_call(self, call: Dict, module_id: str, class_id: Optional[str]) -> Optional[str]:
        """Resolve function call and return the ID of the called function"""
        if call['type'] == 'simple':
            # Check functions in the same module
            direct_func_id = f"{module_id}.{call['name']}"
            if direct_func_id in self.functions:
                return direct_func_id
            
            # Check methods in the same class
            if class_id:
                method_id = f"{class_id}.{call['name']}"
                if method_id in self.functions:
                    return method_id
                
                # Check methods in parent classes
                if class_id in self.classes:
                    for base_class in self.classes[class_id]['base_classes']:
                        # Try to construct complete base class path
                        # If it's a simple name, try to find it in the same module
                        if '.' not in base_class:
                            potential_base = f"{module_id}.{base_class}"
                            if potential_base in self.classes:
                                base_method_id = f"{potential_base}.{call['name']}"
                                if base_method_id in self.functions:
                                    return base_method_id
                        else:
                            # Already a complete path
                            base_method_id = f"{base_class}.{call['name']}"
                            if base_method_id in self.functions:
                                return base_method_id
            
            # Check imported functions
            for imp in self.imports[module_id]:
                if imp['type'] == 'importfrom' and imp['name'] == call['name']:
                    imported_module = imp['module']
                    imported_func_id = f"{imported_module}.{call['name']}"
                    if imported_func_id in self.functions:
                        return imported_func_id
        
        elif call['type'] == 'attribute':
            obj_name = call['object']
            attr_name = call['attribute']
            
            # Check if it's a class instance method call
            for cls_id in self.classes:
                if cls_id.endswith(f".{obj_name}"):
                    method_id = f"{cls_id}.{attr_name}"
                    if method_id in self.functions:
                        return method_id
            
            # Check imported modules
            for imp in self.imports[module_id]:
                if ((imp['type'] == 'import' and imp['name'] == obj_name) or 
                    (imp['type'] == 'import' and imp['alias'] == obj_name)):
                    imported_func_id = f"{imp['name']}.{attr_name}"
                    if imported_func_id in self.functions:
                        return imported_func_id
        
        elif call['type'] == 'nested_attribute':
            # Handle nested attribute calls
            full_path = call['full_path']
            
            # Check exact match
            if full_path in self.functions:
                return full_path
            
            # Check partial match
            for func_id in self.functions:
                if func_id.endswith(f".{full_path}"):
                    return func_id
        
        return None
    
    def _get_source(self, content: str, node: ast.AST) -> str:
        """Extract source code corresponding to AST node"""
        source_lines = content.splitlines()
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            start_line = node.lineno - 1  # AST line numbers start from 1, list indices start from 0
            end_line = node.end_lineno
            return "\n".join(source_lines[start_line:end_line])
        return ""

    def _build_hierarchical_code_tree(self) -> None:
        """Build hierarchical code tree structure for easy browsing and analysis"""
        logger.info("Building hierarchical code tree...")
        
        # Calculate statistics
        self.code_tree['stats']['total_modules'] = len(self.modules)
        self.code_tree['stats']['total_classes'] = len(self.classes)
        self.code_tree['stats']['total_functions'] = len(self.functions)
        
        total_lines = 0
        for module_id, module_info in self.modules.items():
            module_lines = len(module_info['content'].splitlines())
            total_lines += module_lines
            
            # Create module node
            path_parts = module_id.split('.')
            self._add_to_tree(self.code_tree['modules'], path_parts, {
                'type': 'module',
                'id': module_id,
                'name': path_parts[-1],
                'docstring': module_info['docstring'][:100] + ('...' if len(module_info['docstring']) > 100 else ''),
                'classes': [],
                'functions': [],
                'lines': module_lines,
                'is_notebook': module_info.get('is_notebook', False)  # Pass notebook flag
            })
            
            # Add classes
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
                    'from_notebook': class_info.get('from_notebook', False)  # Pass from_notebook flag
                }
                
                # Ensure module node has classes key
                if 'classes' not in self.code_tree['modules'][path_parts[0]]:
                    self.code_tree['modules'][path_parts[0]]['classes'] = []
                
                self.code_tree['modules'][path_parts[0]]['classes'].append(class_node)
                
                # Add methods
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
            
            # Add module-level functions
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
                
                # Get reference to module node
                module_node = self._get_tree_node(self.code_tree['modules'], path_parts)
                if module_node:
                    # Ensure module node has functions key
                    if 'functions' not in module_node:
                        module_node['functions'] = []
                    
                    module_node['functions'].append(func_node)
        
        self.code_tree['stats']['total_lines'] = total_lines
        
        # Initialize importance analyzer
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
                logger.info("Initialized code importance analyzer")
            except Exception as e:
                logger.error(f"Error initializing code importance analyzer: {e}")
    
    def _add_to_tree(self, tree: Dict, path: List[str], node_data: Dict) -> None:
        """
        Add node to tree structure
        
        Args:
            tree: Tree structure
            path: Path
            node_data: Node data
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
        Get node from tree
        
        Args:
            tree: Tree structure
            path: Path
            
        Returns:
            Found node or None
        """
        if len(path) == 1:
            return tree.get(path[0])
        
        if path[0] not in tree:
            return None
        
        if 'children' not in tree[path[0]]:
            return None
        
        return self._get_tree_node(tree[path[0]]['children'], path[1:])
    
    def _identify_key_components(self) -> None:
        """Identify key components in the codebase"""
        logger.info("Identifying key components...")
        
        # Only identify class-level key components
        try:
            # 1. Calculate class importance
            class_importance = {}
            
            # Create a virtual node for each class
            class_graph = nx.DiGraph()
            
            # Add all classes as nodes
            for class_id in self.classes:
                class_graph.add_node(class_id)
            
            # Add call relationship edges between classes
            for class_id, class_info in self.classes.items():
                # Get all methods of this class
                methods = class_info['methods']
                
                # Record other classes called by this class
                called_classes = set()
                
                # Iterate through all methods of this class
                for method_id in methods:
                    if method_id in self.functions:
                        method_info = self.functions[method_id]
                        
                        # Iterate through all functions called by this method
                        for call in method_info['calls']:
                            called_func_id = self._resolve_call(call, method_info['module'], method_info['class'])
                            
                            if called_func_id and called_func_id in self.functions:
                                called_func = self.functions[called_func_id]
                                
                                # If calling a method of another class
                                if called_func['class'] and called_func['class'] != class_id:
                                    called_classes.add(called_func['class'])
                
                # Add edges for each call relationship
                for called_class in called_classes:
                    class_graph.add_edge(class_id, called_class)
            
            # If class graph is not empty, calculate PageRank
            if len(class_graph.nodes()) > 0:
                class_pagerank = nx.pagerank(class_graph, alpha=0.85, max_iter=100)
                class_importance = class_pagerank
            
            # Add important classes
            key_components = []
            for class_id, score in sorted(class_importance.items(), key=lambda x: x[1], reverse=True):
                class_info = self.classes[class_id]
                
                # Calculate total lines of the class
                class_lines = len(class_info['source'].splitlines())
                
                # Calculate number of methods in the class
                methods_count = len(class_info['methods'])
                
                # Calculate number of times the class is called (through its methods)
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
            
            # Sort by importance score
            self.code_tree['key_components'] = sorted(key_components, key=lambda x: x['importance_score'], reverse=True)

        except Exception as e:
            logger.error(f"Error calculating component importance: {e}", exc_info=True)
            
            # Fallback: use simple heuristic method
            try:
                key_components = []
                
                # Process classes
                class_stats = []
                for class_id, class_info in self.classes.items():
                    # Calculate number of methods in the class
                    methods_count = len(class_info['methods'])
                    
                    # Calculate number of times the class is called (through its methods)
                    called_by_count = 0
                    calls_count = 0
                    
                    for method_id in class_info['methods']:
                        if method_id in self.functions:
                            method_info = self.functions[method_id]
                            called_by_count += len(method_info['called_by'])
                            calls_count += len([c for c in method_info['calls'] 
                                              if self._resolve_call(c, method_info['module'], method_info['class'])])
                    
                    # Simple weighted calculation of importance score
                    importance = (0.4 * called_by_count) + (0.3 * calls_count) + (0.3 * methods_count)
                    
                    class_stats.append((class_id, importance))
                
                # Get top 10 classes by importance ranking
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
                
                # Sort by importance score
                self.code_tree['key_components'] = sorted(key_components, key=lambda x: x['importance_score'], reverse=True)
                
            except Exception as e:
                logger.error(f"Error calculating component importance using fallback method: {e}", exc_info=True)
    
    def _identify_key_modules(self) -> List[Dict]:
        """Identify key modules in the codebase"""
        logger.info("Identifying key modules...")
        
        # Only identify module-level key components
        if not self.modules:
            logger.warning("No module information available, unable to identify key modules")
            return []
        
        # Check if there are too many modules
        if len(self.modules) > 300:
            logger.warning(f"Too many modules ({len(self.modules)}), skipping key module importance calculation")
            return []
            
        key_modules = []
        
        try:
            # Collect all modules and calculate their importance
            module_importance = {}
            
            # Check if importance analyzer is available
            if hasattr(self, 'importance_analyzer') and self.importance_analyzer is not None:
                # Use ImportanceAnalyzer to calculate importance scores
                for module_id, module_info in self.modules.items():
                    # Create node dictionary, ensure it has 'type' field
                    node_info = {'id': module_id, 'type': 'module'}
                    if 'docstring' in module_info:
                        node_info['docstring'] = module_info['docstring']
                    if 'path' in module_info:
                        node_info['path'] = module_info['path']
                    
                    # Calculate importance score
                    try:
                        importance_score = self.importance_analyzer.calculate_node_importance(node_info)
                        module_importance[module_id] = importance_score
                    except Exception as e:
                        logger.warning(f"Error calculating importance for module {module_id}: {e}")
                        # Use backup calculation method
                        module_importance[module_id] = self._calculate_node_importance(node_info)
            else:
                # Use internal method to calculate importance
                logger.info("Using internal method to calculate module importance")
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
            
            # Sort by importance and generate key modules list
            for module_id, score in sorted(module_importance.items(), key=lambda x: x[1], reverse=True):  # Get top 15 most important modules
                module_info = self.modules[module_id]
                
                # Calculate number of classes and functions in the module
                classes_count = len(module_info.get('classes', []))
                functions_count = len(module_info.get('functions', []))
                lines_count = len(module_info.get('content', '').splitlines())
                
                # Add to key modules list
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
            
            logger.info(f"Identified {len(key_modules)} key modules")
            
            # Add key modules to code tree
            if 'key_modules' not in self.code_tree:
                self.code_tree['key_modules'] = []
            
            self.code_tree['key_modules'] = sorted(key_modules, key=lambda x: x['importance_score'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error identifying key modules: {e}", exc_info=True)
            # Error handling, ensure returning a valid list
            if not key_modules:
                # Use simple heuristic method as fallback
                for module_id, module_info in list(self.modules.items())[:10]:  # Only process first 10 modules
                    key_modules.append({
                        'id': module_id,
                        'name': module_id.split('.')[-1],
                        'type': 'module',
                        'importance_score': 0.5,  # Default medium importance
                        'path': module_info.get('path', ''),
                        'docstring': module_info.get('docstring', '')[:200] if module_info.get('docstring') else ""
                    })
        
        return key_modules
    
    def _identify_key_class(self) -> None:
        """Use ImportanceAnalyzer to identify key components in the codebase"""
        logger.info("Using ImportanceAnalyzer to identify key components...")
        
        if not hasattr(self, 'importance_analyzer') or self.importance_analyzer is None:
            logger.warning("ImportanceAnalyzer not available, will use original method to identify key components")
            self._identify_key_components()
            return
        
        if len(self.modules) > 300:
            logger.warning(f"Too many modules ({len(self.modules)}), skipping key class importance calculation")
            return
            
        try:
            # Collect all class nodes and calculate their importance
            class_importance = {}
            for class_id, class_info in self.classes.items():
                class_importance[class_id] = 0            

            # Add important classes
            key_components = []
            for class_id, score in sorted(class_importance.items(), key=lambda x: x[1], reverse=True):
                class_info = self.classes[class_id]
                
                # Calculate total lines of the class
                class_lines = len(class_info['source'].splitlines())
                
                # Calculate number of methods in the class
                methods_count = len(class_info['methods'])
                
                # Calculate number of times the class is called (through its methods)
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
            
            # Sort by importance score
            self.code_tree['key_components'] = sorted(key_components, key=lambda x: x['importance_score'], reverse=True)
            
            logger.info(f"Identified {len(key_components)} key components using ImportanceAnalyzer")
            
        except Exception as e:
            logger.error(f"Error calculating component importance using ImportanceAnalyzer: {e}", exc_info=True)
            # Fall back to original method when failed
            logger.info("Falling back to original method to identify key components")
            self._identify_key_components()
    
    def save_code_tree(self, output_file: str) -> None:
        """
        Save code tree to file
        
        Args:
            output_file: Output file path
        """
        # Ensure code tree contains complete class and function information
        complete_tree = {
            'modules': self.code_tree['modules'],
            'stats': self.code_tree['stats'],
            'key_components': self.code_tree['key_components'],
            'classes': self.classes,  # Add complete class information
            'functions': self.functions,  # Add complete function information
            'imports': dict(self.imports)  # Add import information
        }
        
        # Add key modules information
        if 'key_modules' in self.code_tree:
            complete_tree['key_modules'] = self.code_tree['key_modules']
        
        with open(output_file, 'wb') as f:
            pickle.dump(complete_tree, f)
        logger.info(f"Code tree saved to file: {output_file}")
    
    def _calculate_node_importance(self, node: Dict) -> float:
        """
        Calculate node importance score
        
        Args:
            node: Node information
            
        Returns:
            Importance score
        """
        # If there's a dedicated importance analyzer, use it
        if hasattr(self, 'importance_analyzer') and self.importance_analyzer is not None:
            try:
                return self.importance_analyzer.calculate_node_importance(node)
            except Exception as e:
                logger.warning(f"Error calculating node importance using importance analyzer: {e}")
        
        # Fall back to simple importance calculation method
        importance = 0.0
        
        # If it's a module node
        if node['type'] == 'module':
            # 1. Check if it contains key components
            for component in self.code_tree['key_components']:
                if component['module'] == node['id']:
                    importance += 1.0
            
            # 2. Check number of classes and functions
            class_count = len(node.get('classes', []))
            func_count = len(node.get('functions', []))
            importance += (class_count * 0.3) + (func_count * 0.2)
            
            # 3. Check documentation completeness
            if node.get('docstring'):
                importance += 0.2
            
            # 4. Check lines of code (normalized to 0-1 range)
            if 'lines' in node:
                importance += min(node['lines'] / 1000, 1.0) * 0.3
        
        # If it's a package node
        elif node['type'] == 'package':
            # Recursively calculate importance of child nodes
            if 'children' in node:
                for child in node['children'].values():
                    importance += self._calculate_node_importance(child) * 0.5
        
        return importance

    def _append_package_structure(self, content_parts: List[str], tree: Dict, level: int, min_importance: float = 0.5) -> None:
        """
        Recursively add package structure to content, only showing important parts
        
        Args:
            content_parts: List of content parts
            tree: Tree structure
            level: Indentation level
            min_importance: Minimum importance threshold
        """
        # Use ignore lists already defined in class attributes, rather than redefining
        
        # Sort nodes by name and importance score
        sorted_nodes = []
        for name, node in tree.items():
            # Skip names to be ignored
            if name in self.ignored_dirs or any(re.match(pattern, name) for pattern in self.ignored_file_patterns):
                continue
            
            importance = self._calculate_node_importance(node)
            sorted_nodes.append((name, node, importance))
        
        # Sort by importance in descending order
        sorted_nodes.sort(key=lambda x: x[2], reverse=True)
        
        # Process all nodes
        for name, node, importance in sorted_nodes:
            # Skip if importance is below threshold
            if importance < min_importance:
                continue
                
            indent = "  " * level
            if node['type'] == 'package':
                # Display package name
                content_parts.append(f"{indent}- 📦 {name}/")
                
                # Recursively process child nodes, but apply higher filtering threshold for lower-level packages
                # This increases filtering strength as we go deeper into levels
                next_min_importance = min_importance * (1.0 + level * 0.1)
                if 'children' in node:
                    self._append_package_structure(
                        content_parts, 
                        node['children'], 
                        level + 1,
                        min(next_min_importance, 5.0)  # Limit maximum threshold
                    )
            elif node['type'] == 'module':
                # Display module name, use special icon if it's a Jupyter Notebook
                if node.get('is_notebook', False):
                    content_parts.append(f"{indent}- 📔 {name}.ipynb")
                else:
                    content_parts.append(f"{indent}- 📄 {name}.py")
                
                # Add brief docstring hint
                if node.get('docstring'):
                    short_doc = node['docstring'].split('\n')[0][:50]
                    if short_doc:
                        content_parts.append(f" - {short_doc}...")
                # content_parts.append("\n")
                
                # Add classes and functions in the module
                if node.get('classes'):
                    for cls in node['classes']:
                        # Add special mark for classes from Notebook
                        if cls.get('from_notebook', False):
                            content_parts.append(f"{indent}  - {cls['name']} (Notebook Class)")
                        else:
                            content_parts.append(f"{indent}  - {cls['name']} (Class)")
                
                # if node.get('functions'):
                #     for func in node['functions']:
                #         content_parts.append(f"{indent}  - {func['name']} (Function)\n")
    
    def to_json(self) -> str:
        """
        Convert code tree to JSON format
        
        Returns:
            Code tree in JSON format
        """
        # Create a serializable dictionary
        serializable_tree = {
            'modules': self.code_tree['modules'],
            'stats': self.code_tree['stats'],
            'key_components': self.code_tree['key_components'],
            'classes': self.classes,
            'functions': self.functions,
            'imports': dict(self.imports)
        }
        
        # Add key modules information
        if 'key_modules' in self.code_tree:
            serializable_tree['key_modules'] = self.code_tree['key_modules']

        # Convert to JSON string
        return json.dumps(serializable_tree, ensure_ascii=False, indent=2)
    
    def save_json(self, output_file: str) -> None:
        """
        Save code tree to file in JSON format
        
        Args:
            output_file: Output file path
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
        logger.info(f"Code tree saved to file in JSON format: {output_file}")

    def _parse_package_import(self, codes: str) -> str:
        # Parse import statements in code
        code_dependce = ""
        if self.parser and self.python_language:
            # Use tree-sitter to parse source code
            tree = self.parser.parse(bytes(codes, 'utf8'))
            root_node = tree.root_node
            
            # Find all import statements
            import_nodes = []
            for child in root_node.children:
                if child.type in ['import_statement', 'import_from_statement']:
                    import_nodes.append(child)
            
            # Extract text from import statements
            if import_nodes:
                imports_text = []
                for node in import_nodes:
                    start_point, end_point = node.start_point, node.end_point
                    start_line, start_col = start_point
                    end_line, end_col = end_point
                    
                    # Get source code of import statements
                    if start_line == end_line:
                        line = codes.splitlines()[start_line]
                        imports_text.append(line[start_col:end_col])
                    else:
                        lines = codes.splitlines()[start_line:end_line+1]
                        lines[0] = lines[0][start_col:]
                        lines[-1] = lines[-1][:end_col]
                        imports_text.append('\n'.join(lines))
                
                code_dependce = "# Import dependencies\n" + "\n".join(imports_text) + "\n\n"
        return code_dependce

    def generate_llm_important_class(self, max_tokens: int = 3000) -> str:
        """
        Generate LLM-ready key component source code
        """
        def class_code_to_string(important_codes: Dict) -> str:
            important_codes_list = []
            important_codes_list.append("# Key component source code examples\n")
            for class_path, codes in important_codes.items():
                important_codes_list.append(f"```python\n## {class_path}\n")
                code_content = self.modules[codes['module']]['content']
                important_codes_list.append(self._parse_package_import(code_content))
                important_codes_list.append("\n".join(codes['class_list'])+"\n```\n")            
            return "\n".join(important_codes_list)
        
        important_codes = {}
        if self.code_tree['key_components']:
            # Select top 3 key components to display source code
            for component in self.code_tree['key_components']:
                token = tiktoken.encoding_for_model("gpt-4o")
                if len(token.encode(class_code_to_string(important_codes))) > max_tokens:
                    continue
                # Check if component ID exists in corresponding dictionary
                if component['type'] == 'class' and component['id'] in self.classes:
                    class_info = self.classes[component['id']]
                    class_path = self.modules[class_info['module']]['path']
                    if class_path not in important_codes:
                        important_codes[class_path] = {
                            'module': class_info['module'],
                            'name': class_info['name'],
                            'class_list': []
                        }
                    # important_codes[class_path].append(f"## {class_info['name']} (Class)\n")
                    # Use tree-sitter to generate code structure summary instead of complete source code
                    important_codes[class_path]['class_list'].append(self._get_ast_simple_summary(class_info['source']))
        
        return class_code_to_string(important_codes)
    
    def generate_llm_browsable_content(self, max_tokens: int = 8000) -> str:
        """
        Generate content suitable for LLM browsing
        
        Args:
            max_tokens: Maximum number of tokens to control content length
            
        Returns:
            LLM-friendly codebase representation
        """
        logger.info(f"Generating LLM browsable content, max tokens: {max_tokens}")
        
        content_parts = []
        
        # 1. Repository overview
        content_parts.append("# Code Repository Overview\n")
        content_parts.append(f"Repository path: {self.repo_path}\n")
        content_parts.append(f"Total modules: {self.code_tree['stats']['total_modules']}\n")
        content_parts.append(f"Total classes: {self.code_tree['stats']['total_classes']}\n")
        content_parts.append(f"Total functions: {self.code_tree['stats']['total_functions']}\n")
        content_parts.append(f"Total lines of code: {self.code_tree['stats']['total_lines']}\n")
        
        
        # 3. Package structure overview - use dynamic importance threshold filtering
        content_parts.append("# Package Structure\n")
        self._append_package_structure(content_parts, self.code_tree['modules'], 0, min_importance=1.0)
        content_parts.append("\n")
        
        return "\n".join(content_parts)

    def _get_ast_simple_summary(self, source_code: str, max_lines: int = 20) -> str:
        """
        Generate structured code summary using tree-sitter
        
        Args:
            source_code: Source code
            max_lines: Maximum lines to display
            
        Returns:
            Code structure summary
        """
        if not self.parser:
            # If tree-sitter is not available, return simplified version
            lines = source_code.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + "\n... (omitted remaining {} lines)".format(len(lines) - max_lines)
            return source_code
            
        try:
            tree = self.parser.parse(bytes(source_code, 'utf8'))
            root_node = tree.root_node
            
            # Extract main structure
            result = []
            stats = {"classes": 0, "functions": 0, "nested_functions": 0, "lambdas": 0, "async_funcs": 0, "decorators": 0}
            
            # Use method similar to test_tree_sitter.py to extract structure
            def extract_node_info(node, depth=0, is_nested=False):
                if node.type == 'class_definition':
                    # Get class name
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        class_name = source_code[name_node.start_byte:name_node.end_byte]
                        indent = "  " * depth
                        
                        # Check decorators
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
                        
                        # Process class body
                        body_node = node.child_by_field_name('body')
                        if body_node:
                            for i in range(body_node.named_child_count):
                                child = body_node.named_child(i)
                                extract_node_info(child, depth + 1)
                
                elif node.type in ['function_definition', 'async_function_definition']:
                    # Get function name
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        func_name = source_code[name_node.start_byte:name_node.end_byte]
                        
                        # Get parameters
                        params_text = "()"
                        params_node = node.child_by_field_name('parameters')
                        if params_node:
                            params_text = source_code[params_node.start_byte:params_node.end_byte]
                        
                        indent = "  " * depth
                        
                        # Check decorators
                        decorator_list = []
                        for child in node.children:
                            if child.type == 'decorator':
                                decorator_text = source_code[child.start_byte:child.end_byte].strip()
                                decorator_list.append(decorator_text)
                        
                        if decorator_list:
                            for decorator in decorator_list:
                                result.append(f"{indent}{decorator}")
                        
                        # Determine if it's an async function
                        is_async = node.type == 'async_function_definition'
                        if is_async:
                            stats["async_funcs"] += 1
                            
                        # Generate function declaration line
                        func_prefix = "async def" if is_async else "def"
                        
                        # Add special mark for nested functions
                        if is_nested:
                            result.append(f"{indent}{func_prefix} {func_name}{params_text}: # [Nested function]")
                            stats["nested_functions"] += 1
                        else:
                            result.append(f"{indent}{func_prefix} {func_name}{params_text}:")
                            stats["functions"] += 1
                        
                        # Get first line of function body (possibly docstring)
                        body_node = node.child_by_field_name('body')
                        if body_node and body_node.named_child_count > 0:
                            first_stmt = body_node.named_child(0)
                            has_docstring = False
                            
                            if first_stmt.type == "expression_statement":
                                for child in first_stmt.children:
                                    if child.type == "string":
                                        docstring = source_code[child.start_byte:child.end_byte]
                                        # Simplify docstring display
                                        doc_lines = docstring.split('\n')
                                        if len(doc_lines) > 1:
                                            clean_doc = doc_lines[0].strip('\"\'')
                                            result.append(f"{indent}  # Doc: {clean_doc}")
                                        else:
                                            clean_doc = docstring.strip('\"\'')
                                            result.append(f"{indent}  # Doc: {clean_doc}")
                                        has_docstring = True
                                        break
                            
                            # If no docstring, try to infer main function functionality
                            if not has_docstring:
                                # Find key statements in function body
                                key_verbs = []
                                for i in range(min(3, body_node.named_child_count)):
                                    stmt = body_node.named_child(i)
                                    stmt_text = source_code[stmt.start_byte:stmt.end_byte].strip()
                                    first_line = stmt_text.split('\n')[0]
                                    if len(first_line) > 5 and not first_line.startswith('#'):
                                        key_verbs.append(first_line[:40] + ('...' if len(first_line) > 40 else ''))
                                
                                if key_verbs:
                                    result.append(f"{indent}  # Function: {key_verbs[0]}")
                            
                            # Recursively process other nodes in function body, especially nested functions and classes
                            if body_node.named_child_count > 0:
                                nested_items = []
                                for i in range(body_node.named_child_count):
                                    child = body_node.named_child(i)
                                    # Process nested function and class definitions
                                    if child.type in ['function_definition', 'class_definition', 'async_function_definition']:
                                        nested_items.append(child)
                                
                                # If there are nested definitions, add hint
                                if nested_items:
                                    if not has_docstring and not key_verbs:
                                        result.append(f"{indent}  # Contains {len(nested_items)} nested definitions")
                                    
                                    # Recursively process nested definitions
                                    for nested_item in nested_items:
                                        extract_node_info(nested_item, depth + 1, is_nested=True)
                
                # Process lambda expressions - tree-sitter may mark them as lambda expressions or anonymous functions
                elif node.type in ['lambda', 'lambda_expression', 'anonymous_function']:
                    indent = "  " * depth
                    lambda_text = source_code[node.start_byte:node.end_byte]
                    if len(lambda_text) > 40:
                        lambda_text = lambda_text[:37] + "..."
                    result.append(f"{indent}lambda: {lambda_text}")
                    stats["lambdas"] += 1
                
                # Recursively process other node types that may contain functions or classes
                elif node.type in ['if_statement', 'for_statement', 'while_statement', 'try_statement', 'with_statement']:
                    # Check if the body of these statements contains function or class definitions
                    body_index = -1
                    for i, child in enumerate(node.children):
                        if child.type == 'block':
                            body_index = i
                            break
                    
                    if body_index >= 0 and body_index < len(node.children):
                        body_node = node.children[body_index]
                        # Recursively check nodes within the body
                        for i in range(body_node.named_child_count):
                            child = body_node.named_child(i)
                            if child.type in ['function_definition', 'class_definition', 'async_function_definition']:
                                extract_node_info(child, depth + 1, is_nested=True)
            
            # Process top-level nodes
            for i in range(root_node.named_child_count):
                node = root_node.named_child(i)
                extract_node_info(node, 0)
            
            # Add summary information
            if any(stats.values()):
                summary = []
                if stats["classes"] > 0:
                    summary.append(f"{stats['classes']} classes")
                if stats["functions"] > 0:
                    summary.append(f"{stats['functions']} functions")
                if stats["nested_functions"] > 0:
                    summary.append(f"{stats['nested_functions']} nested functions")
                if stats["async_funcs"] > 0:
                    summary.append(f"{stats['async_funcs']} async functions")
                if stats["lambdas"] > 0:
                    summary.append(f"{stats['lambdas']} lambda expressions")
                if stats["decorators"] > 0:
                    summary.append(f"{stats['decorators']} decorators")
                
                if summary:
                    result.append(f"\n# Total: {', '.join(summary)}")
            
            return "\n".join(result) if result else "# No class or function definitions found"
            
        except Exception as e:
            logger.warning(f"Error parsing code with tree-sitter: {e}")
            # Fallback to simple display
            lines = source_code.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... (omitted remaining {len(lines) - max_lines} lines)"
            return source_code
    
    def get_repo_summary_list(self, max_tokens, is_file_summary):

        # Get repository core files, LLM generates repository summary
        important_repo_files_keys = [
            'README', 'main.py', '.ipynb', 'app.py', 'inference', 'test',
        ]
        
        # First process README files in the first-level directory
        readme_files = []
        other_important_files = []
        
        for file_id, file_info in {**self.modules, **self.other_files}.items():
            file_path = file_info['path']
            if len(other_important_files) > 20:
                break
            # Check if it's a README file in the first-level directory
            if '/' not in file_path and 'README' in file_path.upper():
                readme_files.append({
                    'file_path': file_path,
                    'file_content': file_info['content']
                })
            # Other important files
            elif any(key.lower() in file_path.lower() for key in important_repo_files_keys):
                other_important_files.append({
                    'file_path': file_path,
                    'file_content': file_info['content']
                })
        
        # Initialize result list, first add README files (no summary needed)
        repo_summary_list = readme_files.copy()
        current_token = get_code_abs_token(json.dumps(repo_summary_list, ensure_ascii=False, indent=2))
        if current_token >= max_tokens:
            return repo_summary_list
        elif current_token+get_code_abs_token(json.dumps(other_important_files, ensure_ascii=False, indent=2)) <= max_tokens:
            return repo_summary_list+other_important_files

        # Process other important files
        if is_file_summary:
            # Generate summary for other files
            other_summary = generate_repository_summary(other_important_files, max_important_files_token=max_tokens-current_token)
            # If returned is a dictionary, convert to list format
            if isinstance(other_summary, dict):
                other_summary_list = [{'file_path': k, 'file_content': v} for k, v in other_summary.items()]
            else:
                other_summary_list = other_summary
            # Add summary of other files to result
            repo_summary_list.extend(other_summary_list)
        else:
            # Directly add file content without generating summary
            for file_info in other_important_files:
                if get_code_abs_token(json.dumps(file_info, ensure_ascii=False, indent=2))+current_token > max_tokens:
                    break
                repo_summary_list.append({
                    'file_path': file_info['file_path'],
                    'file_content': file_info['file_content']
                })
                
        return repo_summary_list

    def generate_llm_important_modules(self, max_tokens: int = 4000, is_file_summary: bool = True) -> str:
        """Get the most core parts of the entire repository code"""
        out_content_list = []
        repo_summary_list = self.get_repo_summary_list(max_tokens, is_file_summary)
        out_content_list.append("# Repository core file summary\n")
        out_content_list.append(json.dumps(repo_summary_list, ensure_ascii=False))
        # out_content_list.append(json.dumps([{'file_summary': file_info['file_content']} for file_info in repo_summary_list], indent=2, ensure_ascii=False))
        
        # Get key module code based on importance weighting, generate code structure summary through tree-sitter
        if 'key_modules' in self.code_tree and self.code_tree['key_modules']:
            important_codes_list = {}
            out_content_list.append("# Key module abstract code tree\n")                
            
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
                out_content_list.append("# Other key module file names\n")
                out_content_list.append("```"+"\n".join(other_content_list)+"\n```\n")

        return "```\n"+json.dumps(out_content_list, indent=2, ensure_ascii=False)+"\n```"

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("/mnt/ceph/huacan/Code/Tasks/envs/.env")
    
    # Or more detailed way
    builder = GlobalCodeTreeBuilder('git_repos/fish-speech')
    
    builder.parse_repository()
    builder.save_code_tree('res/code_tree.pkl')
    
    # Save as JSON format
    builder.save_json('res/code_tree.json')
    
    content = builder.generate_llm_important_modules()
    print(content)
    
    # content = builder.generate_llm_important_class()
    # print(content)