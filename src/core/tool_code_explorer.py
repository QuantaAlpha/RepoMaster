import os
import re
import sys
import pickle
import json
from typing import Dict, List, Optional, Union, Any, Tuple, Annotated, Callable
from src.core.tree_code import GlobalCodeTreeBuilder
import ast
from grep_ast import TreeContext
import tiktoken
from src.core.code_utils import get_code_abs_token, should_ignore_path, ignored_dirs, ignored_file_patterns, cut_logs_by_token
from src.utils.data_preview import file_tree, _parse_ipynb_file




class CodeExplorerTools:
    def __init__(self, repo_path: str, work_dir: Optional[str] = None, docker_work_dir: Optional[str] = None, init_embeddings: bool = False):
        """Initialize code repository exploration tool
        
        Args:
            repo_path: Local path of code repository
            work_dir: Working directory
        """
        self.context_lines = 0
        
        self.repo_path = repo_path
        self.work_dir = work_dir.rstrip('/') if work_dir else ''
        
        # Uniformly define directories and file patterns to ignore
        self.ignored_dirs = ignored_dirs
        self.ignored_file_patterns = ignored_file_patterns
        
        self._build_new_tree()
        
        # Initialize data structures
        self._initialize_data_structures()
        
        # Initialize vector search related properties
        self.init_embeddings = init_embeddings
        
        if init_embeddings:
            self.retriever = self.init_embeddings()
    
    def _build_new_tree(self):
        """Build new code tree"""
        print(f"Analyzing code repository: {self.repo_path}")
        self.builder = GlobalCodeTreeBuilder(
            self.repo_path,
        )
        self.builder.parse_repository()
        self.code_tree = self.builder.code_tree
    
    def _initialize_data_structures(self):
        """Initialize internal data structures"""
        # Ensure code_tree contains necessary basic structure
        if not hasattr(self, 'code_tree'):
            self.code_tree = {'modules': {}, 'classes': {}, 'functions': {}}
        
        # Extract data from code_tree or use data from builder
        if hasattr(self, 'builder'):
            self.modules = self.builder.modules
            self.classes = self.builder.classes
            self.functions = self.builder.functions
            self.other_files = self.builder.other_files
            self.imports = getattr(self.builder, 'imports', {})
        else:
            # If no builder, need to extract from cached code_tree or regenerate tree
            # Note: Cached code_tree may not contain complete class and function information
            if not self.code_tree.get('classes') and not self.code_tree.get('functions'):
                print("Class and function information not found in cache, regenerating code tree...")
                self._build_new_tree()
                self.modules = self.builder.modules
                self.other_files = self.builder.other_files
                self.classes = self.builder.classes
                self.functions = self.builder.functions
                self.imports = getattr(self.builder, 'imports', {})
            else:
                # Normal extraction from code_tree
                self.modules = self.code_tree.get('modules', {})
                self.other_files = self.code_tree.get('other_files', {})
                self.classes = self.code_tree.get('classes', {})
                self.functions = self.code_tree.get('functions', {})
                self.imports = self.code_tree.get('imports', {})
        
        # Print debug information
        print(f"Loaded {len(self.modules)} modules")
        print(f"Loaded {len(self.classes)} classes")
        print(f"Loaded {len(self.functions)} functions")
    
    def _find_entity(self, entity_id: str, entity_type: str) -> Tuple[Optional[str], Optional[str]]:
        """Generic entity search function
        
        Args:
            entity_id: Entity ID or name to search for
            entity_type: Entity type, such as "function", "class" or "module"
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (matching entity ID, error message)
            If unique match found, return (entity ID, None)
            If multiple matches or no match, return (None, error message)
        """
        entity_type_en = {
            "function": "function",
            "class": "class",
            "module": "module"
        }.get(entity_type, entity_type)
        
        # Get corresponding entity collection
        if entity_type == "class":
            entities = self.classes
        else:
            entities = getattr(self, f"{entity_type}s", {})
        matches = []
        
        # Exact match
        if entity_id in entities:
            matches.append(entity_id)
        else:
            # Partial match
            for eid in entities:
                # If entity ID ends with search term or contains search term
                if eid.endswith("." + entity_id) or entity_id in eid:
                    matches.append(eid)
        
        # Handle match results
        if len(matches) > 5:
            return None, f"Found {len(matches)} matching {entity_type_en}, please provide more specific name. First 5 matches:\n" + "\n".join([f"- {eid}" for eid in matches[:5]]) + "\n..."
        elif len(matches) > 1:
            return None, f"Found {len(matches)} matching {entity_type_en}, please select one:\n" + "\n".join([f"- {eid}" for eid in matches])
        elif not matches:
            return None, f"Cannot find {entity_type_en}: {entity_id}"
        
        # Only one match
        return matches[0], None
    
    def _normalize_file_path(self, file_path: str, return_abs_path: bool = False) -> str:
        """Normalize file path to module ID format"""
        if return_abs_path:
            return file_path
            
        if file_path.startswith('/') and self.repo_path in file_path:
            file_path = os.path.relpath(file_path, self.repo_path)

        if file_path.endswith('.py'):
            file_path = file_path[:-3]
        return file_path.replace('/', '.').replace('\\', '.')
    
    def _format_call_info(self, call: Dict) -> str:
        """Format function call information"""
        if call['type'] == 'simple':
            return f"{call['name']}()"
        elif call['type'] == 'attribute':
            return f"{call['object']}.{call['attribute']}()"
        elif call['type'] == 'nested_attribute':
            return f"{call['full_path']}()"
        return f"Unknown call type: {call}"
    
    def _format_docstring(self, docstring: str, max_lines: int = 3) -> str:
        """Format docstring, limit number of lines"""
        if not docstring:
            return ""
        
        doc_lines = docstring.split('\n')
        if len(doc_lines) > max_lines:
            return f"'''\n{doc_lines[0]}\n...\n'''"
        return f"'''{docstring}'''"
    

    def _format_parameters(self, parameters: List[Dict]) -> str:
        """Format function parameter information"""
        if not parameters:
            return ""
        return ", ".join(p['name'] for p in parameters)
    

    def list_files(self, startpath, max_depth: int = 4):
        """List files, omit display when more than 30 files in a single directory
        
        Args:
            startpath: Starting path
            max_depth: Maximum search depth, default is 4 levels
        """
        result = []
        for root, dirs, files in os.walk(startpath):
            # Calculate current depth
            current_depth = root.replace(startpath, '').count(os.sep)
            if current_depth >= max_depth:
                # Reached maximum depth, skip subdirectories
                dirs.clear()
                result.append(' ' * 4 * current_depth + '... Maximum depth limit reached')
                continue
                
            # Filter out directories to ignore
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            indent = ' ' * 4 * current_depth
            
            # Add current directory name
            result.append('{}{}/'.format(indent, os.path.basename(root)))
            
            # Filter out files to ignore
            files = [f for f in files if not should_ignore_path(f)]
            
            # If file count exceeds 30, only show first 30 and add ellipsis
            subindent = ' ' * 4 * (current_depth + 1)
            if len(files) > 30:
                for f in sorted(files)[:30]:
                    result.append('{}{}'.format(subindent, f))
                result.append('{}... {} more files not displayed'.format(subindent, len(files) - 30))
            else:
                for f in sorted(files):
                    result.append('{}{}'.format(subindent, f))
        
        return "\n".join(result)

    def list_repository_structure(self, path: Annotated[Optional[str], "Path to list structure (must be absolute path). If None, shows entire repository structure."] = None) -> Annotated[Union[str, Dict], "Returns formatted repository structure dictionary"]:
        """List repository structure
        
        This function is used to visually display the directory structure of code repository. Provides hierarchical view of files and folders to help understand project organization.
        """
        return_dict = True
        if not path:
            path = self.repo_path
        
        path = self._normalize_file_path(path, return_abs_path=True)
        
        # Ensure path exists
        if not os.path.exists(path):
            return f"Path does not exist: {path}" if not return_dict else {"error": f"Path does not exist: {path}"}
        
        # return self.list_files(path)
        return file_tree(path, show_size=False)
    
        # Recursive function to generate directory structure
        def format_dir_structure(dir_path, indent=0, prefix=""):
            result = []
            try:
                # Get directory contents and sort
                items = sorted(os.listdir(dir_path))
                
                for item in items:
                    item_path = os.path.join(dir_path, item)
                    rel_path = os.path.relpath(item_path, self.repo_path)
                    module_id = rel_path.replace('\\', '/').replace('/', '.').replace('.py', '') if item.endswith('.py') else None
                    
                    # Use unified function to check if should ignore
                    if should_ignore_path(rel_path):
                        continue
                    
                    if os.path.isdir(item_path):
                        # Handle directory
                        result.append(f"{'  ' * indent}📁 {item}/")
                        # Recursively handle subdirectory
                        children = format_dir_structure(item_path, indent + 1, f"{prefix}/{item}" if prefix else item)
                        result.extend(children)
                    else:
                        # Handle file, keep all file types and extensions
                        file_info = f" [{module_id}]" if module_id else ""
                        file_info = ""
                        result.append(f"{'  ' * indent}📄 {item}{file_info}")
            except PermissionError:
                result.append(f"{'  ' * indent}🔒 Cannot access {os.path.basename(dir_path)}/ (permission denied)")
            except Exception as e:
                result.append(f"{'  ' * indent}❌ Read error: {str(e)}")
            
            return result
        
        # Recursive function to generate directory structured data
        def build_dir_structure_dict(dir_path):
            try:
                items = sorted(os.listdir(dir_path))
                children = []
                
                for item in items:
                    item_path = os.path.join(dir_path, item)
                    rel_path = os.path.relpath(item_path, self.repo_path)
                    
                    # Use unified function to check if should ignore
                    if should_ignore_path(rel_path):
                        continue
                    
                    if os.path.isdir(item_path):
                        # Handle directory
                        children.append({
                            'name': item,
                            'type': 'directory',
                            'path': rel_path,
                            'children': build_dir_structure_dict(item_path)
                        })
                    else:
                        # Handle file
                        children.append({
                            'name': item,
                            'type': 'file',
                            'path': rel_path
                        })
                
                return children
                
            except PermissionError:
                return [{'name': os.path.basename(dir_path), 'type': 'error', 'error': 'permission denied'}]
            except Exception as e:
                return [{'name': os.path.basename(dir_path), 'type': 'error', 'error': str(e)}]
        
        # Decide return type based on return_dict parameter
        if return_dict:
            # Return dictionary structure
            dir_name = os.path.basename(path)
            if dir_name == '':  # Handle root directory
                dir_name = os.path.basename(os.path.dirname(path))
            
            return {
                'name': dir_name,
                'type': 'directory',
                'root_path': path,  # Add root directory absolute path
                'children': build_dir_structure_dict(path)
            }
        else:
            # Return string format
            return "\n".join(format_dir_structure(path))

    def search_keyword_include_code(self, 
                                   keyword_or_code: Annotated[str, "Keywords or code snippets to search for matches"],
                                   query_intent: Annotated[Optional[str], "Search intent, describing what problem this search aims to solve or what content to find"] = None
                                  ) -> Annotated[str, "Search results containing matching functions/classes and code snippets, matching lines marked with '>>> '."]:
        """Search for text lines containing specific keywords and code snippets in code repository, and display matching lines and their files. Similar to grep command but returns more detailed results."""
        
        search_result, results_module_name = self._search_keyword_include_code(keyword_or_code, query_intent=query_intent)
        
        if self.get_code_abs_token(search_result) > 5000:
            search_result = "Multiple files contain keywords or code snippets below, please select a file to view:\n"
            output = []
            for module_info in sorted(results_module_name, key=lambda x: len(x['match_codes']), reverse=True):
                output.append(f"{module_info['module_path']}:       contains {len(module_info['match_codes'])} matching code lines")
            search_result += "\n".join(output)
        
        if self.init_embeddings:
            # Try using vector search
            search_query = f"search intent: {query_intent}\nkeyword: {keyword_or_code}"
            vector_search_codes = self._search_with_embeddings(search_query, topk=4)
            if vector_search_codes:
                search_result += f"\n\n>>>>>> Vector+keyword retrieval related functions:\n{vector_search_codes}"
        
        return search_result
    
    def search_keyword_include_files(self, pattern: Annotated[str, "Keywords to search for matches"]) -> Annotated[str, "List of matching files, each file displayed as complete module path, returns hint if no matches found"]:
        """Search for files containing keywords, search for files whose file names or paths contain specified pattern in code repository"""
        matches = []
        
        all_paths = [file['path'] for file in {**self.modules, **self.other_files}.values()]
        
        for path in sorted(all_paths):
            if pattern.lower() in path.lower():
                matches.append(f">>> {path}")
        
        if not matches:
            return f"No files found matching pattern '{pattern}'"
        
        return "Found the following matching files or directories:\n" + "\n".join(sorted(matches))
    
    def view_filename_tree_sitter(self, 
                                 file_path: Annotated[str, "File path, only supports python files"], 
                                 simplified: Annotated[bool, "Whether to use simplified view. Default is True, showing only structure without complete code"] = True
                                ) -> Annotated[str, "Formatted file structure information including module name, classes, functions and their basic information"]:
        """View file structure parsing
        
        Parse and display structure information of Python files, including classes, functions, methods, etc., providing structured view of files.
        Can choose simplified display (structure only) or complete display (including source code).
        
        Example:
            >>> view_filename_tree_sitter("src/utils.py")
            # Module: src/utils.py
            
            class Helper:
                '''Tool class...'''
                def format_data(data):
                    # Format input data
            
            def validate(input):
                # Validate input data
        """
        # Handle file path format, compatible with different input methods
        module_id = self._normalize_file_path(file_path)
        # import pdb;pdb.set_trace()
        
        # Find matching module
        found_module_id, error = self._find_entity(module_id, "module")
        if error:
            return error
        
        # Get module information and return
        return self._view_filename_tree_sitter(found_module_id, simplified)
    
    def _view_filename_tree_sitter(self, module_id, simplified: bool = True):
        module_info = self.modules[module_id]
        
        if simplified:
            # Show simplified structure
            result = [f"### Module: {module_id}"]
            result.append(f"**File absolute path: {self.repo_path}/{module_info['path']}**")
            
            # Add docstring
            if module_info['docstring']:
                result.append(self._format_docstring(module_info['docstring']))
            
            # Add classes
            for class_id in module_info['classes']:
                class_info = self.classes[class_id]
                result.append(f"\nclass {class_info['name']}:")
                
                # Add abbreviated docstring
                if class_info['docstring']:
                    doc_lines = class_info['docstring'].split('\n')
                    result.append(f"    '''{doc_lines[0]}...'''")
                
                # Add methods
                for method_id in class_info['methods']:
                    if method_id in self.functions:
                        method_info = self.functions[method_id]
                        params_str = self._format_parameters(method_info['parameters'])
                        result.append(f"    def {method_info['name']}({params_str}):")
                        if method_info['docstring']:
                            doc_lines = method_info['docstring'].split('\n')
                            result.append(f"        # {doc_lines[0]}")
                
                if not class_info['methods']:
                    result.append("    pass")
            
            # Add functions
            for func_id in module_info['functions']:
                func_info = self.functions[func_id]
                params_str = self._format_parameters(func_info['parameters'])
                result.append(f"\ndef {func_info['name']}({params_str}):")
                if func_info['docstring']:
                    doc_lines = func_info['docstring'].split('\n')
                    result.append(f"    # {doc_lines[0]}")
            
            return "\n".join(result)
        else:
            # Show complete file content, no longer rely on tree-sitter
            lines = module_info['content'].splitlines()
            if len(lines) > 50:
                return "\n".join(lines[:50]) + f"\n... [Omitted {len(lines)-50} lines]"
            return module_info['content']
    
    def view_class_details(self, class_id: Annotated[str, "Class identifier, can be complete path (like 'src.models.User') or simple name (like 'User')"]) -> Annotated[str, "Formatted detailed class information including module location, docstring, inheritance relationships, method list and source code"]:
        """View detailed class information
        
        Provides comprehensive class information including inheritance relationships, method list, docstring and source code.
        This is an important tool for understanding class design and functionality.
        
        Example:
            >>> view_class_details("User")
            # Class: User
            Module location: src.models
            
            Documentation:
            '''User entity class representing users in the system'''
            
            Inherits from: BaseModel
            
            Methods:
            - __init__(self, username, email) -> None
            - authenticate(self, password) -> bool
            
            Source code:
            class User:
                ...
        """
        # Use generic entity search function
        found_class_id, error = self._find_entity(class_id, "class")
        if error:
            return error
        
        # Only one match, display directly
        class_info = self.classes[found_class_id]
        result = [f"# Class: {class_info['name']}"]
        result.append(f"Module location: {class_info['module']}")
        
        # Add docstring
        if class_info['docstring']:
            result.append(f"\nDocumentation:\n{self._format_docstring(class_info['docstring'])}")
        
        # Add inheritance relationships
        if class_info['base_classes']:
            result.append(f"\nInherits from: {', '.join(class_info['base_classes'])}")
        
        # Add method list
        if class_info['methods']:
            result.append("\nMethods:")
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method = self.functions[method_id]
                    params_str = self._format_parameters(method['parameters'])
                    return_type = f" -> {method['return_type']}" if method['return_type'] else ""
                    result.append(f"- {method['name']}({params_str}){return_type}")
        else:
            result.append("\nThis class has no methods")
        
        # Add source code summary
        result.append("\nSource code:")
        
        max_token = 1000
        if self.get_code_abs_token(class_info['source']) > max_token:
            class_info_summary = self._get_code_abs(f"{class_info['module']}.py", class_info['source'], max_token=max_token)
            if self.get_code_abs_token(class_info_summary) > max_token:
                class_info_summary = self._get_code_summary(class_info['source'])
        else:
            class_info_summary = class_info['source']
        result.append(class_info_summary)
        
        return "\n".join(result)
    
    def view_function_details(self, function_id: Annotated[str, "Function identifier, can be complete path (like 'src.utils.format_data') or simple name (like 'format_data')"]) -> Annotated[str, "Formatted detailed function information including function type, parameters, return type, call relationships and source code"]:
        """View detailed function information
        
        Provides comprehensive function or method information including parameters, return type, docstring, call relationships and source code.
        This is very useful for understanding function purpose and implementation details.
        
        Example:
            >>> view_function_details("format_data")
            # Function: format_data
            Module location: src.utils
            
            Documentation:
            '''Format input data to specified format'''
            
            Parameters:
            - data: Dict
            - format_type: str
            
            Return type: Dict[str, Any]
            
            Called functions:
            - validate()
            
            Source code:
            def format_data(data, format_type="json"):
                ...
        """
        # Use generic entity search function
        found_function_id, error = self._find_entity(function_id, "function")
        if error:
            return error
        
        # Only one match, display directly
        func_info = self.functions[found_function_id]
        result = [f"# {'Method' if func_info['class'] else 'Function'}: {func_info['name']}"]
        result.append(f"Module location: {func_info['module']}")
        result.append(f"File absolute path: {self.repo_path}/{self.modules[func_info['module']]['path']}")
        
        if func_info['class']:
            result.append(f"Belongs to class: {func_info['class']}")
        
        # Add docstring
        if func_info['docstring']:
            result.append(f"\nDocumentation:\n{self._format_docstring(func_info['docstring'])}")
        
        # Add parameter information
        result.append("\nParameters:")
        if func_info['parameters']:
            for param in func_info['parameters']:
                type_str = f": {param['type']}" if param['type'] else ""
                result.append(f"- {param['name']}{type_str}")
        else:
            result.append("- No parameters")
        
        # Add return type
        if func_info['return_type']:
            result.append(f"\nReturn type: {func_info['return_type']}")
        
        # Add call relationships
        if func_info['calls']:
            result.append("\nCalled functions:")
            for call in func_info['calls']:
                result.append(f"- {self._format_call_info(call)}")
        
        if func_info['called_by']:
            result.append("\nCalled by following functions:")
            for caller in func_info['called_by']:
                result.append(f"- {caller}")
        
        # Add source code
        result.append("\nSource code:")
        max_token = 1000
        if self.get_code_abs_token(func_info['source']) > max_token:
            func_info_summary = self._get_code_abs(f"{func_info['module']}.py", func_info['source'], max_token=max_token)
            if self.get_code_abs_token(func_info_summary) > max_token:
                func_info_summary = self._get_code_summary(func_info['source'])
        else:
            func_info_summary = func_info['source']
        result.append(func_info_summary)
        return "\n".join(result)
    
    def find_references(self, 
                       entity_id: Annotated[str, "Entity identifier, can be complete path or simple name"], 
                       entity_type: Annotated[str, "Entity type, must be one of 'function', 'class' or 'module'"]
                      ) -> Annotated[str, "Reference list including function calls, class inheritance or module imports"]:
        """Find references to specific entity
        
        Find all places in codebase that reference specified entity, helping understand entity usage and impact scope.
                
        Example:
            >>> find_references("format_data", "function")
            Function utils.format_data is called by following functions:
            - services.data_processor.process
            - api.endpoints.format_response
        """
        # Use generic entity search function
        found_entity_id, error = self._find_entity(entity_id, entity_type)
        if error:
            return error
            
        if entity_type == "function":
            func_info = self.functions[found_entity_id]
            called_by = func_info['called_by']
            
            if not called_by:
                return f"Function {found_entity_id} is not called by other functions"
            
            result = [f"Function {found_entity_id} is called by following functions:"]
            for caller_id in called_by:
                caller = self.functions[caller_id]
                module = caller['module']
                class_name = caller['class'].split('.')[-1] if caller['class'] else None
                
                if class_name:
                    result.append(f"- {module}.{class_name}.{caller['name']}()")
                else:
                    result.append(f"- {module}.{caller['name']}()")
            
            return "\n".join(result)
            
        elif entity_type == "class":
            class_info = self.classes[found_entity_id]
            references = []
            
            # Find inheritance relationships
            for other_id, other_info in self.classes.items():
                if found_entity_id in other_info['base_classes'] or class_info['name'] in other_info['base_classes']:
                    references.append(f"- Class {other_id} inherits from this class")
            
            # Find method call situations
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method_info = self.functions[method_id]
                    for caller in method_info['called_by']:
                        caller_info = self.functions[caller]
                        caller_class = caller_info['class']
                        references.append(f"- Method {method_id} is called by {caller}")
            
            if not references:
                return f"Class {found_entity_id} is not referenced"
            
            return f"References of class {found_entity_id}:\n" + "\n".join(references)
            
        elif entity_type == "module":
            references = []
            for module_id, imports in self.imports.items():
                for imp in imports:
                    if ((imp['type'] == 'import' and imp['name'] == found_entity_id) or 
                        (imp['type'] == 'importfrom' and imp['module'] == found_entity_id)):
                        references.append(f"- Imported by module {module_id}")
            
            if not references:
                return f"Module {found_entity_id} is not referenced"
            
            return f"References of module {found_entity_id}:\n" + "\n".join(references)
        
        return f"Unsupported entity type: {entity_type}"
    
    def find_dependencies(self, 
                         entity_id: Annotated[str, "Entity identifier, can be complete path or simple name"], 
                         entity_type: Annotated[str, "Entity type, must be one of 'function', 'class' or 'module'"]
                        ) -> Annotated[str, "Dependency list including other functions called by function, base classes inherited by class, or other modules imported by module"]:
        """Find dependencies of specific entity
        
        Find other entities that specified entity (function, class or module) depends on, helping understand dependency relationships required for implementation.
        
        Example:
            >>> find_dependencies("UserService", "class")
            Dependencies of class UserService:
            
            Inherits from following classes:
            - BaseService
            
            Method calls:
            - Method create_user calls User()
            - Method authenticate calls utils.validate()
        """
        # Use generic entity search function
        found_entity_id, error = self._find_entity(entity_id, entity_type)
        if error:
            return error
            
        if entity_type == "function":
            func_info = self.functions[found_entity_id]
            calls = func_info['calls']
            
            if not calls:
                return f"Function {found_entity_id} does not call other functions"
            
            result = [f"Function {found_entity_id} calls following functions:"]
            for call in calls:
                result.append(f"- {self._format_call_info(call)}")
            
            return "\n".join(result)
            
        elif entity_type == "class":
            class_info = self.classes[found_entity_id]
            dependencies = []
            
            # Find base class dependencies
            if class_info['base_classes']:
                dependencies.append("Inherits from following classes:")
                for base in class_info['base_classes']:
                    dependencies.append(f"- {base}")
            
            # Find other functions called by methods
            method_calls = []
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method_info = self.functions[method_id]
                    for call in method_info['calls']:
                        method_calls.append(f"- Method {method_info['name']} calls {self._format_call_info(call)}")
            
            if method_calls:
                dependencies.append("\nMethod calls:")
                dependencies.extend(method_calls)
            
            if not dependencies:
                return f"Class {found_entity_id} has no dependencies"
            
            return f"Dependencies of class {found_entity_id}:\n" + "\n".join(dependencies)
            
        elif entity_type == "module":
            if found_entity_id not in self.imports or not self.imports[found_entity_id]:
                return f"Module {found_entity_id} does not import other modules"
            
            result = [f"Module {found_entity_id} imports following modules:"]
            for imp in self.imports[found_entity_id]:
                if imp['type'] == 'import':
                    result.append(f"- import {imp['name']}" + (f" as {imp['alias']}" if imp['alias'] else ""))
                else:  # importfrom
                    result.append(f"- from {imp['module']} import {imp['name']}" + 
                                 (f" as {imp['alias']}" if imp['alias'] else ""))
            
            return "\n".join(result)
        
        return f"Unsupported entity type: {entity_type}"

    def _prepare_documents(self, docs):
        """Convert docs to Langchain Documents."""
        from langchain.schema import Document
        if isinstance(docs[0], dict):
            return [
                Document(
                    page_content=doc['source'],
                ) for doc in docs
            ]
    def init_embeddings(self, topk=4):
        from src.utils.tool_retriever_embed import EmbeddingMatcher
        import uuid
        
        # Prepare documents
        documents = []
        for func_id, func_info in self.functions.items():
            if 'source' not in func_info:
                continue
            func_info['source'] = f"module: {func_info['module']}\nclass: {func_info['class']}\n{func_info['source']}"
            content = func_info
            documents.append(content)
        
        if not documents:
            return None   
        
        retriever = EmbeddingMatcher(
            topk=topk, 
            chunk_size=5000,
            chunk_overlap=0,
            embedding_weight=0.6,
            document_converter=self._prepare_documents,
            initial_docs=documents,
            persistent_db=True,
            persistent_db_path=f"db/{str(uuid.uuid4())}",
            persistent_collection_name=str(uuid.uuid4()),
        )
        
        return retriever

    def _search_with_embeddings(self, query, topk=4):
        """Use vector retrieval and BM25 hybrid search to find matching code snippets"""
        try:
            # Execute search
            results = self.retriever.match_docs_with_bm25(query)
            
            max_token = 500
            
            out_results = []
            for result in results:
                if len(result) < 5:
                    continue
                result_summary = result
                if get_code_abs_token(result) > max_token:
                    result_summary = self._get_code_abs(f"test.py", result, max_token=max_token)
                    if get_code_abs_token(result_summary) > max_token:
                        result_summary = self._get_code_summary(result)
                else:
                    result_summary = result
                if get_code_abs_token(result_summary) > max_token:
                    continue
                out_results.append(result_summary)
                out_results.append(">>>")
                    
            return "\n".join(out_results)
            
        except Exception as e:
            print(f"Vector search failed: {e}")
            return ''

    def _search_keyword_include_code(self, query, max_token=2000, query_intent=None):
        # Create a result dictionary grouped by module
        results_by_module = []
        results_module_name = []
        
        # If there's search intent, add to results
        if query_intent:
            results_by_module.append(f"# Search intent: {query_intent}\n# Keywords: {query}\n# Search results:\n")
            
        # If vector search has no results, fallback to simple text search
        def _search_keywords(code, query, context_lines=0):
            # Extract matching lines and their context
            context = []
            lines = code.split('\n')
            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    for j in range(start, end):
                        prefix = ">>> " if j == i else "    "
                        context.append(f"{prefix}{lines[j]}")
                if len(context) > 50:
                    break
            return "\n".join(context)        
        
        # Search classes and methods
        for module_id, module_info in {**self.modules, **self.other_files}.items():
            # import pdb;pdb.set_trace()
            if 'content' not in module_info:
                continue
            code = module_info['content']
            match_code = _search_keywords(code, query)
            if match_code:
                results_by_module.append(f"```## {module_info['path']}\n" + match_code + "\n```")
                results_module_name.append({
                    'module_name': module_id,
                    'module_path': module_info['path'],
                    'match_codes': match_code.split('\n')
                })
        
        return "\n".join(results_by_module), results_module_name
    
    def get_module_dependencies(self, module_path: Annotated[str, "Module path, can be absolute path, relative path or module path (like 'src.utils')"]) -> Annotated[str, "Module dependency list including all modules corresponding to import statements"]:
        """Get module dependencies
        
        Analyze and return all dependencies imported by specific module, helping understand inter-module dependency relationships.
                
        Example:
            >>> get_module_dependencies("src.services")
            Dependencies of module src.services:
            datetime
            src.models
            src.utils.helpers
            src.config
        """
        # If complete path is provided, convert to module path
        if os.path.isabs(module_path):
            rel_path = os.path.relpath(module_path, self.repo_path)
            module_path = rel_path.replace(os.sep, '.').replace('.py', '')
        else:
            # Try to handle as module path directly
            module_path = module_path.replace('/', '.').replace('.py', '')
        
        # Find module file
        file_path = os.path.join(self.repo_path, *module_path.split('.')) + '.py'
        if not os.path.exists(file_path):
            return f"Cannot find module: {module_path}"
        
        # Parse file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return f"Cannot parse module: {module_path}"
        
        # Extract imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(f"{node.module}.{name.name}" for name in node.names)
                else:
                    imports.append(f".{name.name}" for name in node.names)
        
        if not imports:
            return f"Module {module_path} has no dependencies"
        
        return f"Dependencies of module {module_path}:\n" + "\n".join(imports)
    
    def check_file_dir(self, file_path: Annotated[str, "Can be relative path, filename (like 'src/utils.py' or 'utils.py', 'README.md')"]):
        """Check if file or directory exists
        
        Check if given file or directory exists in code repository.
        
        """
        output = {
            "is_python_module": False,
            "abs_path": None,
            "relative_path": None,
        }
            
        module_id = self._normalize_file_path(file_path)
        found_module_id, error = self._find_entity(module_id, "module")
        if not error and found_module_id:
            print(f"Python file or directory exists: {file_path}")
            output["is_python_module"] = True
            output["abs_path"] = found_module_id
            output["relative_path"] = file_path
        else:
            print(f"Python file or directory does not exist: check another file type")
            
        if not output["is_python_module"]:
            # Handle as file path
            # Normalize to absolute path
            if os.path.isabs(file_path):
                abs_path = file_path
            else:
                abs_path = os.path.join(self.repo_path, file_path)
            
            if os.path.exists(abs_path):
                output["abs_path"] = abs_path
                output["relative_path"] = file_path
            else:
                print(f"File or directory does not exist: {file_path}")
                return None
        return output
    

    def view_file_content(self, file_path: Annotated[str, "Can be file path or filename"], query_intent: Annotated[Optional[str], "View intent, describing what problem viewing this file aims to solve or what content to find"] = None) -> Annotated[str, "File content or its intelligent summary (for large files)"]:
        """View complete file content, but cannot edit file
        
        Display file source code, provide intelligent summary or structure view for larger files.
        This is a basic tool for checking and understanding code implementation.
                
        Example:
            >>> view_file_content("src.models")
            # File: src.models.py
            
            ```python
            from dataclasses import dataclass
            
            @dataclass
            class User:
                username: str
                email: str
                
                def authenticate(self, password):
                    # Validate user password
                    ...
            ```
            
            >>> view_file_content("README.md")
            # File: README.md
            
            ```markdown
            # Project Title
            
            Project description...
            ```
        """
        # Use unified function to check if should ignore
        if should_ignore_path(file_path):
            return f"File {file_path} is compiled or temporary file, usually no need to view content."
        
        # Record view intent (if any)
        result = []
        if query_intent:
            result.append(f"# Browse intent/purpose: {query_intent}\n")
        
        # Check if it's Python module path
        module_id = self._normalize_file_path(file_path)
        found_module_id, error = self._find_entity(module_id, "module")
        
        if not error and found_module_id:
            # Handle found Python module
            module_info = self.modules[found_module_id]
            content = self._format_file_content(found_module_id, module_info, "python", max_tokens=5000)
            if result:
                return "\n".join(result) + content
            return content
        
        # Handle as file path
        # Normalize to absolute path
        file_path = self._normalize_file_path(file_path, return_abs_path=True)
        if os.path.isabs(file_path):
            abs_path = file_path
        else:
            abs_path = os.path.join(self.repo_path, file_path)
        
        if not os.path.exists(abs_path):
            return f"Cannot find file: {file_path}"
        
        # Read file content
        try:
            # Check if it's .ipynb file
            if abs_path.lower().endswith('.ipynb'):
                content = _parse_ipynb_file(abs_path)
            else:
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
        except Exception as e:
            return f"Cannot read file {file_path}: {str(e)}"
        
        # Determine file type
        filename = os.path.basename(abs_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Determine language based on extension
        lang_map = {
            '.py': 'python',
            '.md': 'markdown',
            '.js': 'javascript',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.txt': 'text',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.sh': 'bash',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.go': 'go',
            '.rs': 'rust',
            '.ipynb': 'python',  # Add .ipynb file type mapping
        }
        
        lang = lang_map.get(file_ext, 'text')
        
        # Format output, add view intent
        if result:
            output = "\n".join(result) + f"**File: {file_path}**\n\n```{lang}\n{content}\n```"
        else:
            output = content
        
        if '.' not in file_path or any(file_path.endswith(ext) for ext in ['.py', '.ipynb', '.md']):
            output = cut_logs_by_token(output, max_token=8000)
        else:
            output = cut_logs_by_token(output, max_token=4000)
        
        return output

    def _format_file_content(self, found_module_id: str, module_info, lang: str, max_tokens: int = 5000) -> str:
        """Format file content output
        
        Args:
            file_path: File path
            content: File content
            lang: Programming language or file type
            
        Returns:
            Formatted content string
        """
        # Use tiktoken to calculate token count of file content
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4o")
            content_tokens = len(encoding.encode(module_info['content']))
            
            # If token count exceeds 3000, return tree-sitter summary
            if content_tokens < max_tokens:
                summary = module_info['content']
            else:
                summary = self._get_code_abs(f"{found_module_id}.py", module_info['content'], max_token=max_tokens)
                if len(encoding.encode(summary)) > max_tokens:
                    summary = self._get_code_summary(module_info['content'])
                    if len(encoding.encode(summary)) > max_tokens:
                        summary = self._view_filename_tree_sitter(found_module_id, simplified=True)
                
                print(f"compare: before {content_tokens} after {len(encoding.encode(summary))}")
        
                # return self._view_filename_tree_sitter(found_module_id, simplified=True)
                # summary = self._get_code_summary(module_info['content'])
                
                return f"### Module: {found_module_id}\n\n**File absolute path: {self.repo_path}/{module_info['path']}**\n\nFile size: {len(module_info['content'])} characters, approximately {content_tokens} tokens\n\n```python {found_module_id}.py\n{summary}\n```"
        except Exception as e:
            print(f"Error: {e}")
            if len(module_info['content']) > 15000:  # Rough estimate 15000 characters ≈ 3000 tokens
                # Use simplified version to show code framework
                return self._view_filename_tree_sitter(found_module_id, simplified=True)
        
        # Return complete file content
        return f"### Module: {found_module_id}\n\n**File absolute path: {self.repo_path}/{module_info['path']}**\n\n```python\n{module_info['content']}\n```"
    
    def get_code_abs_token(self, content):
        encoding = tiktoken.encoding_for_model("gpt-4o")
        return len(encoding.encode(content))
    
    def _get_code_abs(self, filename, source_code, level=1, max_token=3000):
        # import pdb;pdb.set_trace()
        
        if level == 2:
            child_context = True
        else:
            child_context = False
        
        context = TreeContext(
            filename,
            source_code,
            color=False,
            line_number=False,  # Show line numbers
            child_context=child_context,  # Don't show child context
            last_line=False,
            margin=0,  # Don't set margin
            mark_lois=False,  # Don't mark lines of interest
            loi_pad=0,
            show_top_of_file_parent_scope=False,
        )

        if level == 1:
            # Find all function, class definitions and key structures
            structure_lines = []
            for i, line in enumerate(context.lines):
                # Match function definitions, class definitions, import statements, etc.
                if re.match(r'^\s*(def|class|import|from|async def)', line):
                    structure_lines.append(i)
                # Match parameter and variable definitions (simple version)
                elif re.match(r'^\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=', line):
                    structure_lines.append(i)
            context.lines_of_interest = set(structure_lines)

        elif level >= 2:
            structure_lines = []
            important_lines = []
            
            for i, line in enumerate(context.lines):
                # Match function definitions, class definitions, import statements, etc.
                if re.match(r'^\s*(def|class)\s+', line):
                    # Function and class definitions are most important structures
                    important_lines.append(i)
                elif re.match(r'^\s*(import|from)\s+', line) and i < 50:
                    # Only focus on import statements at beginning of file
                    structure_lines.append(i)
                # Match method parameters and important variable definitions
                elif re.match(r'^\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[A-Z]', line) or re.search(r'__init__', line):
                    # Constant variables and initialization parameters are more important
                    structure_lines.append(i)
            
            # Add found structure lines as lines of interest
            context.lines_of_interest = set(important_lines)
            context.add_lines_of_interest(structure_lines)
            
        # Add context
        context.add_context()
        
        # Format and output result
        formatted_code = context.format()
        
        if self.get_code_abs_token(formatted_code) > max_token and level <= 3:
            return self._get_code_abs(filename, source_code, level=level+1, max_token=max_token)
        
        return formatted_code
        
    def _get_code_summary(self, source_code: str, max_lines: int = 20) -> str:
        import ast
        tree = ast.parse(source_code)
        
        # Extract main structures
        result = []
        
        # Handle imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(f"import {name.name}" + (f" as {name.asname}" if name.asname else ""))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    imports.append(f"from {module} import {name.name}" + 
                                    (f" as {name.asname}" if name.asname else ""))
        
        if imports:
            result.append("# Imports")
            result.extend(imports)
            result.append("")
        
        # Handle classes
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                # Get class definition
                bases = [b.id if isinstance(b, ast.Name) else "..." for b in node.bases]
                base_str = f"({', '.join(bases)})" if bases else ""
                result.append(f"class {node.name}{base_str}:")
                
                # Get class docstring
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Str)):
                    doc = node.body[0].value.s.split('\n')[0]  # Only take first line
                    result.append(f"    \"\"\"{doc}...\"\"\"")
                
                # Get methods
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        params = []
                        for arg in item.args.args:
                            params.append(arg.arg)
                        param_str = ", ".join(params)
                        methods.append(f"    def {item.name}({param_str}):")
                        # Add docstring
                        if (item.body and isinstance(item.body[0], ast.Expr) and 
                            isinstance(item.body[0].value, ast.Str)):
                            doc = item.body[0].value.s.split('\n')[0]  # Only take first line
                            methods.append(f"        \"\"\"{doc}...\"\"\"")
                        methods.append("        ...")
                
                if methods:
                    result.extend(methods)
                else:
                    result.append("    pass")
                
                result.append("")
        
        # Handle functions
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                params = []
                for arg in node.args.args:
                    params.append(arg.arg)
                param_str = ", ".join(params)
                result.append(f"def {node.name}({param_str}):")
                
                # Get function docstring
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Str)):
                    doc = node.body[0].value.s.split('\n')[0]  # Only take first line
                    result.append(f"    \"\"\"{doc}...\"\"\"")
                
                result.append("    ...")
                result.append("")
        
        if not result:
            # If no classes or functions found, return first few lines of code
            lines = source_code.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... [Omitted remaining {len(lines) - max_lines} lines]"
            return source_code
        
        return "\n".join(result)
            

    def view_reference_relationships(self, 
                                    entity_id: Annotated[str, "Entity identifier, can be complete path or simple name"], 
                                    entity_type: Annotated[str, "Entity type, must be one of 'function', 'class' or 'module'"]
                                   ) -> Annotated[str, "Formatted reference relationship information including call relationships, inheritance relationships and method call relationships"]:
        """View reference and referenced relationships of entity
        
        Analyze and display reference relationship graph of specific entity (function, class or module), including what it calls and what calls it.
        This is very useful for understanding dependency relationships and interaction patterns between code.
                
        Example:
            >>> view_reference_relationships("User", "class")
            # Reference relationships of class models.User
            
            ## Inheritance relationships:
            Inherits from following classes:
            - BaseModel
            
            ## Inherited by following classes:
            - AdminUser
            - GuestUser
            
            ## Method call relationships:
            Methods called by following functions:
            - Method authenticate called by auth.login
        """
        # Use generic entity search function
        found_entity_id, error = self._find_entity(entity_id, entity_type)
        if error:
            return error
            
        result = []
        
        if entity_type == "function":
            func_info = self.functions[found_entity_id]
            result.append(f"# Reference relationships of function {found_entity_id}")
            
            # Referenced relationships
            result.append("\n## Called by following functions:")
            if func_info['called_by']:
                for caller_id in func_info['called_by']:
                    if caller_id in self.functions:
                        caller = self.functions[caller_id]
                        caller_name = caller['name']
                        if caller['class']:
                            caller_name = f"{caller['class']}.{caller_name}"
                        result.append(f"- {caller['module']}.{caller_name}")
            else:
                result.append("- Not called by other functions")
            
            # Reference relationships
            result.append("\n## Calls following functions:")
            if func_info['calls']:
                for call in func_info['calls']:
                    result.append(f"- {self._format_call_info(call)}")
            else:
                result.append("- Does not call other functions")
            
        elif entity_type == "class":
            class_info = self.classes[found_entity_id]
            result.append(f"# Reference relationships of class {found_entity_id}")
            
            # Inheritance relationships
            result.append("\n## Inheritance relationships:")
            if class_info['base_classes']:
                result.append("Inherits from following classes:")
                for base in class_info['base_classes']:
                    result.append(f"- {base}")
            else:
                result.append("- Does not inherit from other classes")
            
            # Inherited relationships
            result.append("\n## Inherited by following classes:")
            subclasses = []
            for other_id, other_info in self.classes.items():
                if found_entity_id in other_info['base_classes'] or class_info['name'] in other_info['base_classes']:
                    subclasses.append(f"- {other_id}")
            
            if subclasses:
                result.extend(subclasses)
            else:
                result.append("- Not inherited by other classes")
            
            # Method call relationships
            result.append("\n## Method call relationships:")
            method_calls = []
            method_called_by = []
            
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method_info = self.functions[method_id]
                    
                    # Functions called by method
                    for call in method_info['calls']:
                        method_calls.append(f"- Method {method_info['name']} calls {self._format_call_info(call)}")
                    
                    # Method called by
                    for caller_id in method_info['called_by']:
                        if caller_id in self.functions:
                            caller = self.functions[caller_id]
                            caller_name = caller['name']
                            if caller['class']:
                                caller_name = f"{caller['class']}.{caller_name}"
                            method_called_by.append(f"- Method {method_info['name']} called by {caller['module']}.{caller_name}")
            
            if 0 and method_calls:
                result.append("Methods call following functions:")
                result.extend(method_calls)
            
            if method_called_by:
                result.append("\nMethods called by following functions:")
                result.extend(method_called_by)
            else:
                result.append("\n- Class methods not called by other functions")
        
        elif entity_type == "module":
            result.append(f"### Reference relationships of module {found_entity_id}")
            
            # Find other modules that import current module
            result.append("\n## Imported by following modules:")
            imports_by = []
            for module_id, imports in self.imports.items():
                for imp in imports:
                    if ((imp['type'] == 'import' and imp['name'] == found_entity_id) or 
                        (imp['type'] == 'importfrom' and imp['module'] == found_entity_id)):
                        imports_by.append(f"- {module_id}")
            
            if imports_by:
                result.extend(imports_by)
            else:
                result.append("- Not imported by other modules")
            
            # Find other modules imported by current module
            result.append("\n## Imports following modules:")
            if found_entity_id in self.imports and self.imports[found_entity_id]:
                for imp in self.imports[found_entity_id]:
                    if imp['type'] == 'import':
                        result.append(f"- import {imp['name']}" + (f" as {imp['alias']}" if imp['alias'] else ""))
                    else:  # importfrom
                        result.append(f"- from {imp['module']} import {imp['name']}" + 
                                     (f" as {imp['alias']}" if imp['alias'] else ""))
            else:
                result.append("- Does not import other modules")
        
        else:
            return f"Unsupported entity type: {entity_type}, please use 'function', 'class' or 'module'"
        
        return "\n".join(result)
    
    def read_files_index(
        self, 
        target_file: Annotated[str, "File path to read. Can use relative path to workspace or absolute path."],
        source_code: Annotated[Optional[str], "File content."] = None,
        max_tokens: Annotated[int, "Maximum token count."] = 5000
    ):
        if source_code is None:
            source_code = self.view_file_content(target_file)
    
        return source_code
        
    def _read_file_index(self, file_path):
        """Read file index"""
        with open(file_path, "r") as f:
            return json.load(f)

    def run_examples(self):
        """Run example operations"""
        print("\n===== Code exploration tool examples =====\n")
        
        try:
            # Example 1: List repository structure
            print("Example 1: List repository top-level structure")
            print("-" * 50)
            print(self.list_repository_structure(self.work_dir))
            print("\n")
            exit()
            
            # Example 2: Search files
            print("Example 2: Search files containing 'README'")
            print("-" * 50)
            print(self.search_keyword_include_files("README"))
            print(self.search_keyword_include_files(".ipynb"))
            print("\n")


            # Example 4: Search code
            first_code = "checkpoint"
            print(f"Example 4: Search code containing {first_code}")
            print("-" * 50)
            print(self.search_keyword_include_code(first_code, query_intent=f"Search code containing checkpoint"))
            print("\n")            
            
            # Example 3: View first available module structure
            print("Example 3: View file structure")
            print("-" * 50)
            if self.modules:
                # first_module = next(iter(self.modules))
                first_module = "lyrapdf/convert.py"
                first_module = "pre_proc"
                print(f"View module: {first_module}")
                print(self.view_filename_tree_sitter(first_module))
            else:
                print("No available modules found")
            print("\n")
            
            if 1:

                
                # Example 5: View available classes and functions
                print("Example 5: View classes and functions")
                print("-" * 50)
                if self.classes:
                    first_class = next(iter(self.classes))
                    first_class = first_class.split(".")[-1]
                    first_class = "TrackableUserProxyAgent"
                    print(f"View class details: {first_class}")
                    print(self.view_class_details(first_class))
                
                first_func = next(iter(self.functions))
                first_func = first_func.split(".")[-1]
                # first_class = "search_retrieval"
                first_func = "lyrapdf.app.extract_and_process"
                print(f"\nView function details: {first_func}")
                print(self.view_function_details(first_func))


                # New example: View file content
                print("Example 6: View file content")
                print("-" * 50)
                first_module = next(iter(self.modules))
                # first_module = "services.agents.deep_search_agent"
                first_module = "README.md"
                first_module = "/workspace/lyrapdf/README.md"
                first_module = "/workspace/lyrapdf/txt_ext.py"
                print(f"View file content: {first_module}")
                print(self.view_file_content(first_module))
                print("\n")
                
            
            # New example: View reference relationships
            print("Example 7: View reference relationships")
            print("-" * 50)
            if self.functions:
                first_func = next(iter(self.functions))
                first_func = first_func.split(".")[-1]
                first_func = "utils.agent_gpt4.AzureGPT4Chat.chat_with_message"
                print(f"View function reference relationships: {first_func}")
                print(self.view_reference_relationships(first_func, "function"))
            else:
                print("No available functions found")
            print("-" * 50)
            if self.classes:
                first_class = next(iter(self.classes))
                first_class = first_class.split(".")[-1]
                first_class = "TrackableUserProxyAgent"
                print(f"View class reference relationships: {first_class}")
                print(self.view_reference_relationships(first_class, "class"))
            else:
                print("No available classes found")
            
        except Exception as e:
            print(f"Error running examples: {str(e)}")
            raise
        
        print("\n===== Examples end =====")


def main():
    """Main function"""
    from dotenv import load_dotenv
    
    load_dotenv("configs/.env")
    
    explorer = CodeExplorerTools("git_repos/fish-speech")
    
    # Run examples
    explorer.run_examples()
    
    # If interactive operations needed, can uncomment below
    """
    while True:
        print("\n===== Code exploration tool =====")
        print("1. List repository structure")
        print("2. Search files")
        print("3. View file structure")
        print("4. View class details")
        print("5. View function details")
        print("6. Find references")
        print("7. Search code")
        print("8. Get module dependencies")
        print("9. View file content")
        print("10. View class code")
        print("11. View function code")
        print("12. View reference relationships")
        print("0. Exit")
        
        choice = input("\nPlease select operation: ")
        
        if choice == '0':
            break
        elif choice == '1':
            path = input("Please enter path (leave empty for root directory): ")
            print(explorer.list_repository_structure(path if path else None))
        elif choice == '2':
            pattern = input("Please enter search pattern: ")
            print(explorer.search_keyword_include_files(pattern))
        elif choice == '3':
            file_path = input("Please enter file path: ")
            simplified = input("Simplified display (y/n): ").lower() == 'y'
            print(explorer.view_filename_tree_sitter(file_path, simplified))
        elif choice == '4':
            class_id = input("Please enter class ID: ")
            print(explorer.view_class_details(class_id))
        elif choice == '5':
            func_id = input("Please enter function ID: ")
            print(explorer.view_function_details(func_id))
        elif choice == '6':
            entity_id = input("Please enter entity ID: ")
            entity_type = input("Please enter entity type (function, class, or module): ").lower()
            result = explorer.find_references(entity_id, entity_type)
            print("\nReferences:")
            print(result)
        elif choice == '7':
            query = input("Please enter search query: ")
            result = explorer.search_keyword_include_code(query)
            print("\nSearch Results:")
            print(result)
        elif choice == '8':
            module_path = input("Please enter module path: ")
            result = explorer.get_module_dependencies(module_path)
            print("\nModule Dependencies:")
            print(result)
        elif choice == '9':
            file_path = input("Please enter file path: ")
            print(explorer.view_file_content(file_path))
        elif choice == '10':
            class_id = input("Please enter class ID: ")
            print(explorer.view_class_code(class_id))
        elif choice == '11':
            func_id = input("Please enter function ID: ")
            print(explorer.view_function_code(func_id))
        elif choice == '12':
            entity_id = input("Please enter entity ID: ")
            entity_type = input("Please enter entity type (function or class): ").lower()
            print(explorer.view_reference_relationships(entity_id, entity_type))
        else:
            print("Invalid selection!")
    """