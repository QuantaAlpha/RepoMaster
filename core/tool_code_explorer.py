import os
import re
import sys
import pickle
import json
from typing import Dict, List, Optional, Union, Any, Tuple, Annotated, Callable
from core.tree_code import GlobalCodeTreeBuilder
import ast
from grep_ast import TreeContext
import tiktoken
from core.code_utils import get_code_abs_token, should_ignore_path, ignored_dirs, ignored_file_patterns, cut_logs_by_token
from utils.data_preview import file_tree, _parse_ipynb_file





class CodeExplorerTools:
    def __init__(self, repo_path: str, work_dir: Optional[str] = None, docker_work_dir: Optional[str] = None, init_embeddings: bool = False):
        """初始化代码仓库探索工具
        
        Args:
            repo_path: 代码仓库本地路径
            work_dir: 工作目录
        """
        self.context_lines = 0
        
        self.repo_path = repo_path
        self.work_dir = work_dir.rstrip('/') if work_dir else ''
        
        # 统一定义要忽略的目录和文件模式
        self.ignored_dirs = ignored_dirs
        self.ignored_file_patterns = ignored_file_patterns
        
        self._build_new_tree()
        
        # 初始化数据结构
        self._initialize_data_structures()
        
        # 初始化向量搜索相关属性
        self.init_embeddings = init_embeddings
        
        if init_embeddings:
            self.retriever = self.init_embeddings()
    
    def _build_new_tree(self):
        """构建新的代码树"""
        print(f"正在分析代码仓库: {self.repo_path}")
        self.builder = GlobalCodeTreeBuilder(
            self.repo_path,
        )
        self.builder.parse_repository()
        self.code_tree = self.builder.code_tree
    
    def _initialize_data_structures(self):
        """初始化内部数据结构"""
        # 确保code_tree包含所需的基本结构
        if not hasattr(self, 'code_tree'):
            self.code_tree = {'modules': {}, 'classes': {}, 'functions': {}}
        
        # 从code_tree中提取数据或使用builder中的数据
        if hasattr(self, 'builder'):
            self.modules = self.builder.modules
            self.classes = self.builder.classes
            self.functions = self.builder.functions
            self.other_files = self.builder.other_files
            self.imports = getattr(self.builder, 'imports', {})
        else:
            # 如果没有builder，需要从缓存加载的code_tree中提取或重新生成树
            # 注意：缓存的code_tree可能不包含完整的类和函数信息
            if not self.code_tree.get('classes') and not self.code_tree.get('functions'):
                print("缓存中没有找到类和函数信息，重新生成代码树...")
                self._build_new_tree()
                self.modules = self.builder.modules
                self.other_files = self.builder.other_files
                self.classes = self.builder.classes
                self.functions = self.builder.functions
                self.imports = getattr(self.builder, 'imports', {})
            else:
                # 正常从code_tree中提取
                self.modules = self.code_tree.get('modules', {})
                self.other_files = self.code_tree.get('other_files', {})
                self.classes = self.code_tree.get('classes', {})
                self.functions = self.code_tree.get('functions', {})
                self.imports = self.code_tree.get('imports', {})
        
        # 打印调试信息
        print(f"已加载 {len(self.modules)} 个模块")
        print(f"已加载 {len(self.classes)} 个类")
        print(f"已加载 {len(self.functions)} 个函数")
    
    def _find_entity(self, entity_id: str, entity_type: str) -> Tuple[Optional[str], Optional[str]]:
        """通用实体搜索函数
        
        Args:
            entity_id: 要搜索的实体ID或名称
            entity_type: 实体类型，如"function"、"class"或"module"
            
        Returns:
            Tuple[Optional[str], Optional[str]]: (匹配的实体ID, 错误信息)
            如果找到唯一匹配，返回(实体ID, None)
            如果有多个匹配或没有匹配，返回(None, 错误信息)
        """
        entity_type_cn = {
            "function": "函数",
            "class": "类",
            "module": "模块"
        }.get(entity_type, entity_type)
        
        # 获取对应的实体集合
        if entity_type == "class":
            entities = self.classes
        else:
            entities = getattr(self, f"{entity_type}s", {})
        matches = []
        
        # 完全匹配
        if entity_id in entities:
            matches.append(entity_id)
        else:
            # 部分匹配
            for eid in entities:
                # 如果实体ID以搜索词结尾或包含搜索词
                if eid.endswith("." + entity_id) or entity_id in eid:
                    matches.append(eid)
        
        # 处理匹配结果
        if len(matches) > 5:
            return None, f"找到 {len(matches)} 个匹配的{entity_type_cn}，请提供更具体的名称。前5个匹配项:\n" + "\n".join([f"- {eid}" for eid in matches[:5]]) + "\n..."
        elif len(matches) > 1:
            return None, f"找到 {len(matches)} 个匹配的{entity_type_cn}，请选择一个:\n" + "\n".join([f"- {eid}" for eid in matches])
        elif not matches:
            return None, f"找不到{entity_type_cn}: {entity_id}"
        
        # 只有一个匹配项
        return matches[0], None
    
    def _normalize_file_path(self, file_path: str, return_abs_path: bool = False) -> str:
        """标准化文件路径为模块ID格式"""
        if return_abs_path:
            return file_path
            
        if file_path.startswith('/') and self.repo_path in file_path:
            file_path = os.path.relpath(file_path, self.repo_path)

        if file_path.endswith('.py'):
            file_path = file_path[:-3]
        return file_path.replace('/', '.').replace('\\', '.')
    
    def _format_call_info(self, call: Dict) -> str:
        """格式化函数调用信息"""
        if call['type'] == 'simple':
            return f"{call['name']}()"
        elif call['type'] == 'attribute':
            return f"{call['object']}.{call['attribute']}()"
        elif call['type'] == 'nested_attribute':
            return f"{call['full_path']}()"
        return f"未知调用类型: {call}"
    
    def _format_docstring(self, docstring: str, max_lines: int = 3) -> str:
        """格式化文档字符串，限制行数"""
        if not docstring:
            return ""
        
        doc_lines = docstring.split('\n')
        if len(doc_lines) > max_lines:
            return f"'''\n{doc_lines[0]}\n...\n'''"
        return f"'''{docstring}'''"
    
    
    def _format_parameters(self, parameters: List[Dict]) -> str:
        """格式化函数参数信息"""
        if not parameters:
            return ""
        return ", ".join(p['name'] for p in parameters)
    

    def list_files(self, startpath, max_depth: int = 4):
        """列出文件，当单个目录下文件超过30个时进行省略显示
        
        Args:
            startpath: 起始路径
            max_depth: 最大搜索深度，默认为4层
        """
        result = []
        for root, dirs, files in os.walk(startpath):
            # 计算当前深度
            current_depth = root.replace(startpath, '').count(os.sep)
            if current_depth >= max_depth:
                # 达到最大深度，跳过子目录
                dirs.clear()
                result.append(' ' * 4 * current_depth + '... 已达到最大深度限制')
                continue
                
            # 过滤掉需要忽略的目录
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            indent = ' ' * 4 * current_depth
            
            # 添加当前目录名
            result.append('{}{}/'.format(indent, os.path.basename(root)))
            
            # 过滤掉需要忽略的文件
            files = [f for f in files if not should_ignore_path(f)]
            
            # 如果文件数量超过30个，只显示前30个并添加省略提示
            subindent = ' ' * 4 * (current_depth + 1)
            if len(files) > 30:
                for f in sorted(files)[:30]:
                    result.append('{}{}'.format(subindent, f))
                result.append('{}... 还有 {} 个文件未显示'.format(subindent, len(files) - 30))
            else:
                for f in sorted(files):
                    result.append('{}{}'.format(subindent, f))
        
        return "\n".join(result)

    def list_repository_structure(self, path: Annotated[Optional[str], "要列出结构的路径（必须是绝对路径）。如果为None，则显示整个仓库结构。"] = None) -> Annotated[Union[str, Dict], "返回格式化的仓库结构字典结构"]:
        """列出仓库结构
        
        此函数用于可视化展示代码仓库的目录结构。提供了文件和文件夹的层次化视图，帮助理解项目的组织方式。
        """
        return_dict = True
        if not path:
            path = self.repo_path
        
        path = self._normalize_file_path(path, return_abs_path=True)
        
        # 确保路径存在
        if not os.path.exists(path):
            return f"路径不存在: {path}" if not return_dict else {"error": f"路径不存在: {path}"}
        
        # return self.list_files(path)
        return file_tree(path, show_size=False)
    
        # 递归函数用于生成目录结构
        def format_dir_structure(dir_path, indent=0, prefix=""):
            result = []
            try:
                # 获取目录内容并排序
                items = sorted(os.listdir(dir_path))
                
                for item in items:
                    item_path = os.path.join(dir_path, item)
                    rel_path = os.path.relpath(item_path, self.repo_path)
                    module_id = rel_path.replace('\\', '/').replace('/', '.').replace('.py', '') if item.endswith('.py') else None
                    
                    # 使用统一的函数检查是否应该忽略
                    if should_ignore_path(rel_path):
                        continue
                    
                    if os.path.isdir(item_path):
                        # 处理目录
                        result.append(f"{'  ' * indent}📁 {item}/")
                        # 递归处理子目录
                        children = format_dir_structure(item_path, indent + 1, f"{prefix}/{item}" if prefix else item)
                        result.extend(children)
                    else:
                        # 处理文件，保留所有文件类型和扩展名
                        file_info = f" [{module_id}]" if module_id else ""
                        file_info = ""
                        result.append(f"{'  ' * indent}📄 {item}{file_info}")
            except PermissionError:
                result.append(f"{'  ' * indent}🔒 无法访问 {os.path.basename(dir_path)}/ (权限被拒绝)")
            except Exception as e:
                result.append(f"{'  ' * indent}❌ 读取错误: {str(e)}")
            
            return result
        
        # 递归函数用于生成目录结构化数据
        def build_dir_structure_dict(dir_path):
            try:
                items = sorted(os.listdir(dir_path))
                children = []
                
                for item in items:
                    item_path = os.path.join(dir_path, item)
                    rel_path = os.path.relpath(item_path, self.repo_path)
                    
                    # 使用统一的函数检查是否应该忽略
                    if should_ignore_path(rel_path):
                        continue
                    
                    if os.path.isdir(item_path):
                        # 处理目录
                        children.append({
                            'name': item,
                            'type': 'directory',
                            'path': rel_path,
                            'children': build_dir_structure_dict(item_path)
                        })
                    else:
                        # 处理文件
                        children.append({
                            'name': item,
                            'type': 'file',
                            'path': rel_path
                        })
                
                return children
                
            except PermissionError:
                return [{'name': os.path.basename(dir_path), 'type': 'error', 'error': '权限被拒绝'}]
            except Exception as e:
                return [{'name': os.path.basename(dir_path), 'type': 'error', 'error': str(e)}]
        
        # 根据return_dict参数决定返回类型
        if return_dict:
            # 返回字典结构
            dir_name = os.path.basename(path)
            if dir_name == '':  # 处理根目录
                dir_name = os.path.basename(os.path.dirname(path))
            
            return {
                'name': dir_name,
                'type': 'directory',
                'root_path': path,  # 添加根目录绝对路径
                'children': build_dir_structure_dict(path)
            }
        else:
            # 返回字符串格式
            return "\n".join(format_dir_structure(path))

    def search_keyword_include_code(self, 
                                   keyword_or_code: Annotated[str, "要搜索匹配的关键词或代码片段"],
                                   query_intent: Annotated[Optional[str], "搜索意图，描述此次搜索想解决什么问题或查找什么内容"] = None
                                  ) -> Annotated[str, "搜索结果，包含匹配的函数/类及代码片段，匹配行使用 '>>> ' 标记。"]:
        """搜索匹配代码仓库中包含特定关键词和代码片段的文本行，并显示匹配行及其所在文件。类似于 grep 命令，但返回结果更详细。"""
        
        search_result, results_module_name = self._search_keyword_include_code(keyword_or_code, query_intent=query_intent)
        
        if self.get_code_abs_token(search_result) > 5000:
            search_result = "下面有多个文件包含关键词或代码片段，请选择一个文件进行查看:\n"
            output = []
            for module_info in sorted(results_module_name, key=lambda x: len(x['match_codes']), reverse=True):
                output.append(f"{module_info['module_path']}:       包含{len(module_info['match_codes'])}行匹配代码")
            search_result += "\n".join(output)
        
        if self.init_embeddings:
            # 尝试使用向量搜索
            search_query = f"search intent: {query_intent}\nkeyword: {keyword_or_code}"
            vector_search_codes = self._search_with_embeddings(search_query, topk=4)
            if vector_search_codes:
                search_result += f"\n\n>>>>>> 向量+关键词检索相关函数:\n{vector_search_codes}"
        
        return search_result
    
    def search_keyword_include_files(self, pattern: Annotated[str, "要搜索匹配的关键词"]) -> Annotated[str, "匹配的文件列表，每个文件都显示为完整的模块路径，如果没有匹配项则返回提示信息"]:
        """搜索匹配包含关键词的文件，在代码仓库中搜索文件名或路径包含指定模式的文件"""
        matches = []
        
        all_paths = [file['path'] for file in {**self.modules, **self.other_files}.values()]
        
        for path in sorted(all_paths):
            if pattern.lower() in path.lower():
                matches.append(f">>> {path}")
        
        if not matches:
            return f"没有找到匹配模式 '{pattern}' 的文件"
        
        return "找到以下匹配文件或目录:\n" + "\n".join(sorted(matches))
    
    def view_filename_tree_sitter(self, 
                                 file_path: Annotated[str, "文件路径, only support python file"], 
                                 simplified: Annotated[bool, "是否使用简化视图。默认为True，仅显示结构而非完整代码"] = True
                                ) -> Annotated[str, "格式化的文件结构信息，包括模块名、类、函数和它们的基本信息"]:
        """查看文件的结构解析
        
        解析并显示Python文件的结构信息，包括类、函数、方法等，提供文件的结构化视图。
        可以选择简化显示(仅结构)或完整显示(包含源代码)。
        
        示例:
            >>> view_filename_tree_sitter("src/utils.py")
            # 模块: src/utils.py
            
            class Helper:
                '''工具类...'''
                def format_data(data):
                    # 格式化输入数据
            
            def validate(input):
                # 验证输入数据
        """
        # 处理文件路径格式，兼容不同输入方式
        module_id = self._normalize_file_path(file_path)
        # import pdb;pdb.set_trace()
        
        # 查找匹配的模块
        found_module_id, error = self._find_entity(module_id, "module")
        if error:
            return error
        
        # 获取模块信息并返回
        return self._view_filename_tree_sitter(found_module_id, simplified)
    
    def _view_filename_tree_sitter(self, module_id, simplified: bool = True):
        module_info = self.modules[module_id]
        
        if simplified:
            # 显示简化的结构
            result = [f"### 模块: {module_id}"]
            result.append(f"**文件绝对路径: {self.repo_path}/{module_info['path']}**")
            
            # 添加文档字符串
            if module_info['docstring']:
                result.append(self._format_docstring(module_info['docstring']))
            
            # 添加类
            for class_id in module_info['classes']:
                class_info = self.classes[class_id]
                result.append(f"\nclass {class_info['name']}:")
                
                # 添加文档字符串简写
                if class_info['docstring']:
                    doc_lines = class_info['docstring'].split('\n')
                    result.append(f"    '''{doc_lines[0]}...'''")
                
                # 添加方法
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
            
            # 添加函数
            for func_id in module_info['functions']:
                func_info = self.functions[func_id]
                params_str = self._format_parameters(func_info['parameters'])
                result.append(f"\ndef {func_info['name']}({params_str}):")
                if func_info['docstring']:
                    doc_lines = func_info['docstring'].split('\n')
                    result.append(f"    # {doc_lines[0]}")
            
            return "\n".join(result)
        else:
            # 显示完整文件内容，不再依赖tree-sitter
            lines = module_info['content'].splitlines()
            if len(lines) > 50:
                return "\n".join(lines[:50]) + f"\n... [省略 {len(lines)-50} 行]"
            return module_info['content']
    
    def view_class_details(self, class_id: Annotated[str, "类的标识符，可以是完整路径（如'src.models.User'）或简单名称（如'User'）"]) -> Annotated[str, "格式化的类详细信息，包括所在模块、文档字符串、继承关系、方法列表和源代码"]:
        """查看类的详细信息
        
        提供类的全面信息，包括继承关系、方法列表、文档字符串和源代码。
        这是理解类设计和功能的重要工具。
        
        示例:
            >>> view_class_details("User")
            # 类: User
            所在模块: src.models
            
            文档:
            '''用户实体类，表示系统中的用户'''
            
            继承自: BaseModel
            
            方法:
            - __init__(self, username, email) -> None
            - authenticate(self, password) -> bool
            
            源代码:
            class User:
                ...
        """
        # 使用通用实体搜索函数
        found_class_id, error = self._find_entity(class_id, "class")
        if error:
            return error
        
        # 只有一个匹配项，直接展示
        class_info = self.classes[found_class_id]
        result = [f"# 类: {class_info['name']}"]
        result.append(f"所在模块: {class_info['module']}")
        
        # 添加文档字符串
        if class_info['docstring']:
            result.append(f"\n文档:\n{self._format_docstring(class_info['docstring'])}")
        
        # 添加继承关系
        if class_info['base_classes']:
            result.append(f"\n继承自: {', '.join(class_info['base_classes'])}")
        
        # 添加方法列表
        if class_info['methods']:
            result.append("\n方法:")
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method = self.functions[method_id]
                    params_str = self._format_parameters(method['parameters'])
                    return_type = f" -> {method['return_type']}" if method['return_type'] else ""
                    result.append(f"- {method['name']}({params_str}){return_type}")
        else:
            result.append("\n该类没有方法")
        
        # 添加源代码摘要
        result.append("\n源代码:")
        
        max_token = 1000
        if self.get_code_abs_token(class_info['source']) > max_token:
            class_info_summary = self._get_code_abs(f"{class_info['module']}.py", class_info['source'], max_token=max_token)
            if self.get_code_abs_token(class_info_summary) > max_token:
                class_info_summary = self._get_code_summary(class_info['source'])
        else:
            class_info_summary = class_info['source']
        result.append(class_info_summary)
        
        return "\n".join(result)
    
    def view_function_details(self, function_id: Annotated[str, "函数的标识符，可以是完整路径（如'src.utils.format_data'）或简单名称（如'format_data'）"]) -> Annotated[str, "格式化的函数详细信息，包括函数类型、参数、返回类型、调用关系和源代码"]:
        """查看函数的详细信息
        
        提供函数或方法的全面信息，包括参数、返回类型、文档字符串、调用关系和源代码。
        这对理解函数用途和实现细节非常有用。
        
        示例:
            >>> view_function_details("format_data")
            # 函数: format_data
            所在模块: src.utils
            
            文档:
            '''格式化输入数据为指定格式'''
            
            参数:
            - data: Dict
            - format_type: str
            
            返回类型: Dict[str, Any]
            
            调用的函数:
            - validate()
            
            源代码:
            def format_data(data, format_type="json"):
                ...
        """
        # 使用通用实体搜索函数
        found_function_id, error = self._find_entity(function_id, "function")
        if error:
            return error
        
        # 只有一个匹配项，直接展示
        func_info = self.functions[found_function_id]
        result = [f"# {'方法' if func_info['class'] else '函数'}: {func_info['name']}"]
        result.append(f"所在模块: {func_info['module']}")
        result.append(f"所在文件绝对路径: {self.repo_path}/{self.modules[func_info['module']]['path']}")
        
        if func_info['class']:
            result.append(f"所属类: {func_info['class']}")
        
        # 添加文档字符串
        if func_info['docstring']:
            result.append(f"\n文档:\n{self._format_docstring(func_info['docstring'])}")
        
        # 添加参数信息
        result.append("\n参数:")
        if func_info['parameters']:
            for param in func_info['parameters']:
                type_str = f": {param['type']}" if param['type'] else ""
                result.append(f"- {param['name']}{type_str}")
        else:
            result.append("- 无参数")
        
        # 添加返回类型
        if func_info['return_type']:
            result.append(f"\n返回类型: {func_info['return_type']}")
        
        # 添加调用关系
        if func_info['calls']:
            result.append("\n调用的函数:")
            for call in func_info['calls']:
                result.append(f"- {self._format_call_info(call)}")
        
        if func_info['called_by']:
            result.append("\n被以下函数调用:")
            for caller in func_info['called_by']:
                result.append(f"- {caller}")
        
        # 添加源代码
        result.append("\n源代码:")
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
                       entity_id: Annotated[str, "实体的标识符，可以是完整路径或简单名称"], 
                       entity_type: Annotated[str, "实体类型，必须是 'function'、'class' 或 'module' 之一"]
                      ) -> Annotated[str, "引用列表，包括函数调用、类继承或模块导入的情况"]:
        """查找对特定实体的引用
        
        查找代码库中所有引用指定实体的地方，帮助理解实体的使用情况和影响范围。
                
        示例:
            >>> find_references("format_data", "function")
            函数 utils.format_data 被以下函数调用:
            - services.data_processor.process
            - api.endpoints.format_response
        """
        # 使用通用实体搜索函数
        found_entity_id, error = self._find_entity(entity_id, entity_type)
        if error:
            return error
            
        if entity_type == "function":
            func_info = self.functions[found_entity_id]
            called_by = func_info['called_by']
            
            if not called_by:
                return f"函数 {found_entity_id} 没有被其他函数调用"
            
            result = [f"函数 {found_entity_id} 被以下函数调用:"]
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
            
            # 查找继承关系
            for other_id, other_info in self.classes.items():
                if found_entity_id in other_info['base_classes'] or class_info['name'] in other_info['base_classes']:
                    references.append(f"- 类 {other_id} 继承自该类")
            
            # 查找方法被调用的情况
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method_info = self.functions[method_id]
                    for caller in method_info['called_by']:
                        caller_info = self.functions[caller]
                        caller_class = caller_info['class']
                        references.append(f"- 方法 {method_id} 被 {caller} 调用")
            
            if not references:
                return f"类 {found_entity_id} 没有被引用"
            
            return f"类 {found_entity_id} 的引用:\n" + "\n".join(references)
            
        elif entity_type == "module":
            references = []
            for module_id, imports in self.imports.items():
                for imp in imports:
                    if ((imp['type'] == 'import' and imp['name'] == found_entity_id) or 
                        (imp['type'] == 'importfrom' and imp['module'] == found_entity_id)):
                        references.append(f"- 被模块 {module_id} 导入")
            
            if not references:
                return f"模块 {found_entity_id} 没有被引用"
            
            return f"模块 {found_entity_id} 的引用:\n" + "\n".join(references)
        
        return f"不支持的实体类型: {entity_type}"
    
    def find_dependencies(self, 
                         entity_id: Annotated[str, "实体的标识符，可以是完整路径或简单名称"], 
                         entity_type: Annotated[str, "实体类型，必须是 'function'、'class' 或 'module' 之一"]
                        ) -> Annotated[str, "依赖项列表，包括函数调用的其他函数、类继承的基类或模块导入的其他模块"]:
        """查找特定实体的依赖项
        
        查找指定实体（函数、类或模块）依赖的其他实体，帮助理解其实现所需的依赖关系。
        
        示例:
            >>> find_dependencies("UserService", "class")
            类 UserService 的依赖项:
            
            继承自以下类:
            - BaseService
            
            方法调用:
            - 方法 create_user 调用 User()
            - 方法 authenticate 调用 utils.validate()
        """
        # 使用通用实体搜索函数
        found_entity_id, error = self._find_entity(entity_id, entity_type)
        if error:
            return error
            
        if entity_type == "function":
            func_info = self.functions[found_entity_id]
            calls = func_info['calls']
            
            if not calls:
                return f"函数 {found_entity_id} 没有调用其他函数"
            
            result = [f"函数 {found_entity_id} 调用了以下函数:"]
            for call in calls:
                result.append(f"- {self._format_call_info(call)}")
            
            return "\n".join(result)
            
        elif entity_type == "class":
            class_info = self.classes[found_entity_id]
            dependencies = []
            
            # 查找基类依赖
            if class_info['base_classes']:
                dependencies.append("继承自以下类:")
                for base in class_info['base_classes']:
                    dependencies.append(f"- {base}")
            
            # 查找方法调用的其他函数
            method_calls = []
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method_info = self.functions[method_id]
                    for call in method_info['calls']:
                        method_calls.append(f"- 方法 {method_info['name']} 调用 {self._format_call_info(call)}")
            
            if method_calls:
                dependencies.append("\n方法调用:")
                dependencies.extend(method_calls)
            
            if not dependencies:
                return f"类 {found_entity_id} 没有依赖项"
            
            return f"类 {found_entity_id} 的依赖项:\n" + "\n".join(dependencies)
            
        elif entity_type == "module":
            if found_entity_id not in self.imports or not self.imports[found_entity_id]:
                return f"模块 {found_entity_id} 没有导入其他模块"
            
            result = [f"模块 {found_entity_id} 导入了以下模块:"]
            for imp in self.imports[found_entity_id]:
                if imp['type'] == 'import':
                    result.append(f"- import {imp['name']}" + (f" as {imp['alias']}" if imp['alias'] else ""))
                else:  # importfrom
                    result.append(f"- from {imp['module']} import {imp['name']}" + 
                                 (f" as {imp['alias']}" if imp['alias'] else ""))
            
            return "\n".join(result)
        
        return f"不支持的实体类型: {entity_type}"

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
        from utils.tool_retriever_embed import EmbeddingMatcher
        import uuid
        
        # 准备文档
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
        """使用向量检索和BM25混合搜索查找匹配的代码片段"""
        try:
            # 执行搜索
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
            print(f"向量搜索失败: {e}")
            return ''

    def _search_keyword_include_code(self, query, max_token=2000, query_intent=None):
        # 创建一个按模块分组的结果字典
        results_by_module = []
        results_module_name = []
        
        # 如果有搜索意图，添加到结果中
        if query_intent:
            results_by_module.append(f"# 搜索意图: {query_intent}\n# 关键词: {query}\n# 搜索结果:\n")
            
        # 如果向量搜索没有结果，回退到简单文本搜索
        def _search_keywords(code, query, context_lines=0):
            # 提取匹配行及其上下文
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
        
        # 搜索类和方法
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
    
    def get_module_dependencies(self, module_path: Annotated[str, "模块路径，可以是绝对路径、相对路径或模块路径（如'src.utils'）"]) -> Annotated[str, "模块的依赖列表，包括所有导入语句对应的模块"]:
        """获取模块依赖
        
        分析并返回特定模块所导入的所有依赖项，帮助理解模块间的依赖关系。
                
        示例:
            >>> get_module_dependencies("src.services")
            模块 src.services 的依赖:
            datetime
            src.models
            src.utils.helpers
            src.config
        """
        # 如果提供的是完整路径，转换为模块路径
        if os.path.isabs(module_path):
            rel_path = os.path.relpath(module_path, self.repo_path)
            module_path = rel_path.replace(os.sep, '.').replace('.py', '')
        else:
            # 尝试直接作为模块路径处理
            module_path = module_path.replace('/', '.').replace('.py', '')
        
        # 查找模块文件
        file_path = os.path.join(self.repo_path, *module_path.split('.')) + '.py'
        if not os.path.exists(file_path):
            return f"找不到模块: {module_path}"
        
        # 解析文件内容
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return f"无法解析模块: {module_path}"
        
        # 提取导入
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
            return f"模块 {module_path} 没有依赖"
        
        return f"模块 {module_path} 的依赖:\n" + "\n".join(imports)
    
    def check_file_dir(self, file_path: Annotated[str, "可以是相对路径、文件名（如'src/utils.py或者utils.py、README.md'）"]):
        """检查文件或目录是否存在
        
        检查给定的文件或目录是否存在于代码仓库中。
        
        """
        output = {
            "is_python_module": False,
            "abs_path": None,
            "relative_path": None,
        }
            
        module_id = self._normalize_file_path(file_path)
        found_module_id, error = self._find_entity(module_id, "module")
        if not error and found_module_id:
            print(f"python 文件或目录存在: {file_path}")
            output["is_python_module"] = True
            output["abs_path"] = found_module_id
            output["relative_path"] = file_path
        else:
            print(f"python 文件或目录不存在: check another file type")
            
        if not output["is_python_module"]:
            # 处理作为文件路径的情况
            # 标准化到绝对路径
            if os.path.isabs(file_path):
                abs_path = file_path
            else:
                abs_path = os.path.join(self.repo_path, file_path)
            
            if os.path.exists(abs_path):
                output["abs_path"] = abs_path
                output["relative_path"] = file_path
            else:
                print(f"文件或目录不存在: {file_path}")
                return None
        return output
    

    def view_file_content(self, file_path: Annotated[str, "可以是文件路径、文件名"], query_intent: Annotated[Optional[str], "查看意图，描述查看此文件想解决什么问题或寻找什么内容"] = None) -> Annotated[str, "文件内容或其智能摘要（对于大文件）"]:
        """查看文件的完整内容, 但无法编辑文件
        
        显示文件的源代码，对于较大文件会提供智能摘要或结构视图。
        这是检查和理解代码实现的基本工具。
                
        示例:
            >>> view_file_content("src.models")
            # 文件: src.models.py
            
            ```python
            from dataclasses import dataclass
            
            @dataclass
            class User:
                username: str
                email: str
                
                def authenticate(self, password):
                    # 验证用户密码
                    ...
            ```
            
            >>> view_file_content("README.md")
            # 文件: README.md
            
            ```markdown
            # 项目标题
            
            项目描述...
            ```
        """
        # 使用统一的函数检查是否应该忽略
        if should_ignore_path(file_path):
            return f"文件 {file_path} 是编译或临时文件，通常不需要查看内容。"
        
        # 记录查看意图（如果有）
        result = []
        if query_intent:
            result.append(f"# 浏览的意图、目的: {query_intent}\n")
        
        # 检查是否是Python模块路径
        module_id = self._normalize_file_path(file_path)
        found_module_id, error = self._find_entity(module_id, "module")
        
        if not error and found_module_id:
            # 处理找到的Python模块
            module_info = self.modules[found_module_id]
            content = self._format_file_content(found_module_id, module_info, "python", max_tokens=5000)
            if result:
                return "\n".join(result) + content
            return content
        
        # 处理作为文件路径的情况
        # 标准化到绝对路径
        file_path = self._normalize_file_path(file_path, return_abs_path=True)
        if os.path.isabs(file_path):
            abs_path = file_path
        else:
            abs_path = os.path.join(self.repo_path, file_path)
        
        if not os.path.exists(abs_path):
            return f"找不到文件: {file_path}"
        
        # 读取文件内容
        try:
            # 检查是否是.ipynb文件
            if abs_path.lower().endswith('.ipynb'):
                content = _parse_ipynb_file(abs_path)
            else:
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
        except Exception as e:
            return f"无法读取文件 {file_path}: {str(e)}"
        
        # 确定文件类型
        filename = os.path.basename(abs_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # 根据扩展名确定语言
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
            '.ipynb': 'python',  # 添加.ipynb文件类型映射
        }
        
        lang = lang_map.get(file_ext, 'text')
        
        # 格式化输出，加上查看意图
        if result:
            output = "\n".join(result) + f"**文件: {file_path}**\n\n```{lang}\n{content}\n```"
        else:
            output = content
        
        if '.' not in file_path or any(file_path.endswith(ext) for ext in ['.py', '.ipynb', '.md']):
            output = cut_logs_by_token(output, max_token=8000)
        else:
            output = cut_logs_by_token(output, max_token=4000)
        
        return output

    def _format_file_content(self, found_module_id: str, module_info, lang: str, max_tokens: int = 5000) -> str:
        """格式化文件内容输出
        
        Args:
            file_path: 文件路径
            content: 文件内容
            lang: 编程语言或文件类型
            
        Returns:
            格式化的内容字符串
        """
        # 使用tiktoken计算文件内容的token数量
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model("gpt-4o")
            content_tokens = len(encoding.encode(module_info['content']))
            
            # 如果token数量超过3000，返回tree-sitter摘要
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
                
                return f"### 模块: {found_module_id}\n\n**文件绝对路径: {self.repo_path}/{module_info['path']}**\n\n文件大小: {len(module_info['content'])} 字符，约 {content_tokens} tokens\n\n```python {found_module_id}.py\n{summary}\n```"
        except Exception as e:
            print(f"Error: {e}")
            if len(module_info['content']) > 15000:  # 粗略估计15000字符约3000 tokens
                # 使用简化版显示代码框架
                return self._view_filename_tree_sitter(found_module_id, simplified=True)
        
        # 返回完整文件内容
        return f"### 模块: {found_module_id}\n\n**文件绝对路径: {self.repo_path}/{module_info['path']}**\n\n```python\n{module_info['content']}\n```"
    
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
            line_number=False,  # 显示行号
            child_context=child_context,  # 不显示子上下文
            last_line=False,
            margin=0,  # 不设置边距
            mark_lois=False,  # 不标记感兴趣的行
            loi_pad=0,
            show_top_of_file_parent_scope=False,
        )

        if level == 1:
            # 查找所有函数、类定义和关键结构
            structure_lines = []
            for i, line in enumerate(context.lines):
                # 匹配函数定义、类定义、导入语句等
                if re.match(r'^\s*(def|class|import|from|async def)', line):
                    structure_lines.append(i)
                # 匹配参数和变量定义（简单版）
                elif re.match(r'^\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=', line):
                    structure_lines.append(i)
            context.lines_of_interest = set(structure_lines)

        elif level >= 2:
            structure_lines = []
            important_lines = []
            
            for i, line in enumerate(context.lines):
                # 匹配函数定义、类定义、导入语句等
                if re.match(r'^\s*(def|class)\s+', line):
                    # 函数和类定义是最重要的结构
                    important_lines.append(i)
                elif re.match(r'^\s*(import|from)\s+', line) and i < 50:
                    # 只关注文件开头的导入语句
                    structure_lines.append(i)
                # 匹配方法参数和重要变量定义
                elif re.match(r'^\s+[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[A-Z]', line) or re.search(r'__init__', line):
                    # 常量变量和初始化参数更重要
                    structure_lines.append(i)
            
            # 添加找到的结构行作为感兴趣的行
            context.lines_of_interest = set(important_lines)
            context.add_lines_of_interest(structure_lines)
            
        # 添加上下文
        context.add_context()
        
        # 格式化并输出结果
        formatted_code = context.format()
        
        if self.get_code_abs_token(formatted_code) > max_token and level <= 3:
            return self._get_code_abs(filename, source_code, level=level+1, max_token=max_token)
        
        return formatted_code
        
    def _get_code_summary(self, source_code: str, max_lines: int = 20) -> str:
        import ast
        tree = ast.parse(source_code)
        
        # 提取主要结构
        result = []
        
        # 处理导入
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
            result.append("# 导入")
            result.extend(imports)
            result.append("")
        
        # 处理类
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                # 获取类定义
                bases = [b.id if isinstance(b, ast.Name) else "..." for b in node.bases]
                base_str = f"({', '.join(bases)})" if bases else ""
                result.append(f"class {node.name}{base_str}:")
                
                # 获取类文档字符串
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Str)):
                    doc = node.body[0].value.s.split('\n')[0]  # 只取第一行
                    result.append(f"    \"\"\"{doc}...\"\"\"")
                
                # 获取方法
                methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        params = []
                        for arg in item.args.args:
                            params.append(arg.arg)
                        param_str = ", ".join(params)
                        methods.append(f"    def {item.name}({param_str}):")
                        # 添加文档字符串
                        if (item.body and isinstance(item.body[0], ast.Expr) and 
                            isinstance(item.body[0].value, ast.Str)):
                            doc = item.body[0].value.s.split('\n')[0]  # 只取第一行
                            methods.append(f"        \"\"\"{doc}...\"\"\"")
                        methods.append("        ...")
                
                if methods:
                    result.extend(methods)
                else:
                    result.append("    pass")
                
                result.append("")
        
        # 处理函数
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                params = []
                for arg in node.args.args:
                    params.append(arg.arg)
                param_str = ", ".join(params)
                result.append(f"def {node.name}({param_str}):")
                
                # 获取函数文档字符串
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Str)):
                    doc = node.body[0].value.s.split('\n')[0]  # 只取第一行
                    result.append(f"    \"\"\"{doc}...\"\"\"")
                
                result.append("    ...")
                result.append("")
        
        if not result:
            # 如果没有找到类或函数，返回前几行代码
            lines = source_code.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... [省略剩余 {len(lines) - max_lines} 行]"
            return source_code
        
        return "\n".join(result)
            

    def view_reference_relationships(self, 
                                    entity_id: Annotated[str, "实体的标识符，可以是完整路径或简单名称"], 
                                    entity_type: Annotated[str, "实体类型，必须是 'function'、'class' 或 'module' 之一"]
                                   ) -> Annotated[str, "格式化的引用关系信息，包括调用关系、继承关系和方法调用关系"]:
        """查看实体的引用和被引用关系
        
        分析并显示特定实体（函数、类或模块）的引用关系图，包括它调用了什么和被什么调用。
        这对理解代码间的依赖关系和交互模式非常有用。
                
        示例:
            >>> view_reference_relationships("User", "class")
            # 类 models.User 的引用关系
            
            ## 继承关系:
            继承自以下类:
            - BaseModel
            
            ## 被以下类继承:
            - AdminUser
            - GuestUser
            
            ## 方法调用关系:
            方法被以下函数调用:
            - 方法 authenticate 被 auth.login 调用
        """
        # 使用通用实体搜索函数
        found_entity_id, error = self._find_entity(entity_id, entity_type)
        if error:
            return error
            
        result = []
        
        if entity_type == "function":
            func_info = self.functions[found_entity_id]
            result.append(f"# 函数 {found_entity_id} 的引用关系")
            
            # 被引用关系
            result.append("\n## 被以下函数调用:")
            if func_info['called_by']:
                for caller_id in func_info['called_by']:
                    if caller_id in self.functions:
                        caller = self.functions[caller_id]
                        caller_name = caller['name']
                        if caller['class']:
                            caller_name = f"{caller['class']}.{caller_name}"
                        result.append(f"- {caller['module']}.{caller_name}")
            else:
                result.append("- 没有被其他函数调用")
            
            # 引用关系
            result.append("\n## 调用了以下函数:")
            if func_info['calls']:
                for call in func_info['calls']:
                    result.append(f"- {self._format_call_info(call)}")
            else:
                result.append("- 没有调用其他函数")
            
        elif entity_type == "class":
            class_info = self.classes[found_entity_id]
            result.append(f"# 类 {found_entity_id} 的引用关系")
            
            # 继承关系
            result.append("\n## 继承关系:")
            if class_info['base_classes']:
                result.append("继承自以下类:")
                for base in class_info['base_classes']:
                    result.append(f"- {base}")
            else:
                result.append("- 没有继承自其他类")
            
            # 被继承关系
            result.append("\n## 被以下类继承:")
            subclasses = []
            for other_id, other_info in self.classes.items():
                if found_entity_id in other_info['base_classes'] or class_info['name'] in other_info['base_classes']:
                    subclasses.append(f"- {other_id}")
            
            if subclasses:
                result.extend(subclasses)
            else:
                result.append("- 没有被其他类继承")
            
            # 方法调用关系
            result.append("\n## 方法调用关系:")
            method_calls = []
            method_called_by = []
            
            for method_id in class_info['methods']:
                if method_id in self.functions:
                    method_info = self.functions[method_id]
                    
                    # 方法调用的函数
                    for call in method_info['calls']:
                        method_calls.append(f"- 方法 {method_info['name']} 调用 {self._format_call_info(call)}")
                    
                    # 方法被调用
                    for caller_id in method_info['called_by']:
                        if caller_id in self.functions:
                            caller = self.functions[caller_id]
                            caller_name = caller['name']
                            if caller['class']:
                                caller_name = f"{caller['class']}.{caller_name}"
                            method_called_by.append(f"- 方法 {method_info['name']} 被 {caller['module']}.{caller_name} 调用")
            
            if 0 and method_calls:
                result.append("方法调用了以下函数:")
                result.extend(method_calls)
            
            if method_called_by:
                result.append("\n方法被以下函数调用:")
                result.extend(method_called_by)
            else:
                result.append("\n- 类的方法没有被其他函数调用")
        
        elif entity_type == "module":
            result.append(f"### 模块 {found_entity_id} 的引用关系")
            
            # 查找导入当前模块的其他模块
            result.append("\n## 被以下模块导入:")
            imports_by = []
            for module_id, imports in self.imports.items():
                for imp in imports:
                    if ((imp['type'] == 'import' and imp['name'] == found_entity_id) or 
                        (imp['type'] == 'importfrom' and imp['module'] == found_entity_id)):
                        imports_by.append(f"- {module_id}")
            
            if imports_by:
                result.extend(imports_by)
            else:
                result.append("- 没有被其他模块导入")
            
            # 查找当前模块导入的其他模块
            result.append("\n## 导入了以下模块:")
            if found_entity_id in self.imports and self.imports[found_entity_id]:
                for imp in self.imports[found_entity_id]:
                    if imp['type'] == 'import':
                        result.append(f"- import {imp['name']}" + (f" as {imp['alias']}" if imp['alias'] else ""))
                    else:  # importfrom
                        result.append(f"- from {imp['module']} import {imp['name']}" + 
                                     (f" as {imp['alias']}" if imp['alias'] else ""))
            else:
                result.append("- 没有导入其他模块")
        
        else:
            return f"不支持的实体类型: {entity_type}，请使用 'function'、'class' 或 'module'"
        
        return "\n".join(result)
    
    def read_files_index(
        self, 
        target_file: Annotated[str, "要读取的文件路径。可以使用相对于工作区的相对路径或绝对路径。"],
        source_code: Annotated[Optional[str], "文件内容。"] = None,
        max_tokens: Annotated[int, "最大token数。"] = 5000
    ):
        if source_code is None:
            source_code = self.view_file_content(target_file)
    
        return source_code
        
    def _read_file_index(self, file_path):
        """读取文件索引"""
        with open(file_path, "r") as f:
            return json.load(f)

    def run_examples(self):
        """运行示例操作"""
        print("\n===== 代码探索工具示例 =====\n")
        
        try:
            # 示例1: 列出仓库结构
            print("示例1: 列出仓库顶层结构")
            print("-" * 50)
            print(self.list_repository_structure(self.work_dir))
            print("\n")
            exit()
            
            # 示例2: 搜索文件
            print("示例2: 搜索包含'README'的文件")
            print("-" * 50)
            print(self.search_keyword_include_files("README"))
            print(self.search_keyword_include_files(".ipynb"))
            print("\n")


            # 示例4: 搜索代码
            first_code = "checkpoint"
            print(f"示例4: 搜索代码中包含 {first_code} 的部分")
            print("-" * 50)
            print(self.search_keyword_include_code(first_code, query_intent="搜索代码中包含 checkpoint 的部分"))
            print("\n")            
            
            # 示例3: 查看第一个可用模块的结构
            print("示例3: 查看文件结构")
            print("-" * 50)
            if self.modules:
                # first_module = next(iter(self.modules))
                first_module = "lyrapdf/convert.py"
                first_module = "pre_proc"
                print(f"查看模块: {first_module}")
                print(self.view_filename_tree_sitter(first_module))
            else:
                print("没有找到可用的模块")
            print("\n")
            
            if 1:

                
                # 示例5: 查看可用的类和函数
                print("示例5: 查看类和函数")
                print("-" * 50)
                if self.classes:
                    first_class = next(iter(self.classes))
                    first_class = first_class.split(".")[-1]
                    first_class = "TrackableUserProxyAgent"
                    print(f"查看类详情: {first_class}")
                    print(self.view_class_details(first_class))
                
                first_func = next(iter(self.functions))
                first_func = first_func.split(".")[-1]
                # first_class = "search_retrieval"
                first_func = "lyrapdf.app.extract_and_process"
                print(f"\n查看函数详情: {first_func}")
                print(self.view_function_details(first_func))


                # 新增示例: 查看文件内容
                print("示例6: 查看文件内容")
                print("-" * 50)
                first_module = next(iter(self.modules))
                # first_module = "services.agents.deepsearch_2agents"
                first_module = "README.md"
                first_module = "/workspace/lyrapdf/README.md"
                first_module = "/workspace/lyrapdf/txt_ext.py"
                print(f"查看文件内容: {first_module}")
                print(self.view_file_content(first_module))
                print("\n")
                
            
            # 新增示例: 查看引用关系
            print("示例7: 查看引用关系")
            print("-" * 50)
            if self.functions:
                first_func = next(iter(self.functions))
                first_func = first_func.split(".")[-1]
                first_func = "utils.agent_gpt4.AzureGPT4Chat.chat_with_message"
                print(f"查看函数引用关系: {first_func}")
                print(self.view_reference_relationships(first_func, "function"))
            else:
                print("没有找到可用的函数")
            print("-" * 50)
            if self.classes:
                first_class = next(iter(self.classes))
                first_class = first_class.split(".")[-1]
                first_class = "TrackableUserProxyAgent"
                print(f"查看类引用关系: {first_class}")
                print(self.view_reference_relationships(first_class, "class"))
            else:
                print("没有找到可用的类")
            
        except Exception as e:
            print(f"运行示例时出错: {str(e)}")
            raise
        
        print("\n===== 示例结束 =====")


def main():
    """主函数"""
    from dotenv import load_dotenv
    
    load_dotenv("configs/.env")
    
    explorer = CodeExplorerTools("git_repos/fish-speech")
    
    # 运行示例
    explorer.run_examples()
    
    # 如果需要交互式操作，可以取消下面的注释
    """
    while True:
        print("\n===== 代码探索工具 =====")
        print("1. 列出仓库结构")
        print("2. 搜索文件")
        print("3. 查看文件结构")
        print("4. 查看类详情")
        print("5. 查看函数详情")
        print("6. 查找引用")
        print("7. 搜索代码")
        print("8. 获取模块依赖")
        print("9. 查看文件内容")
        print("10. 查看类代码")
        print("11. 查看函数代码")
        print("12. 查看引用关系")
        print("0. 退出")
        
        choice = input("\n请选择操作: ")
        
        if choice == '0':
            break
        elif choice == '1':
            path = input("请输入路径(留空为根目录): ")
            print(explorer.list_repository_structure(path if path else None))
        elif choice == '2':
            pattern = input("请输入搜索模式: ")
            print(explorer.search_keyword_include_files(pattern))
        elif choice == '3':
            file_path = input("请输入文件路径: ")
            simplified = input("是否简化显示(y/n): ").lower() == 'y'
            print(explorer.view_filename_tree_sitter(file_path, simplified))
        elif choice == '4':
            class_id = input("请输入类ID: ")
            print(explorer.view_class_details(class_id))
        elif choice == '5':
            func_id = input("请输入函数ID: ")
            print(explorer.view_function_details(func_id))
        elif choice == '6':
            entity_id = input("请输入实体ID: ")
            entity_type = input("请输入实体类型 (function, class, or module): ").lower()
            result = explorer.find_references(entity_id, entity_type)
            print("\nReferences:")
            print(result)
        elif choice == '7':
            query = input("请输入搜索查询: ")
            result = explorer.search_keyword_include_code(query)
            print("\nSearch Results:")
            print(result)
        elif choice == '8':
            module_path = input("请输入模块路径: ")
            result = explorer.get_module_dependencies(module_path)
            print("\nModule Dependencies:")
            print(result)
        elif choice == '9':
            file_path = input("请输入文件路径: ")
            print(explorer.view_file_content(file_path))
        elif choice == '10':
            class_id = input("请输入类ID: ")
            print(explorer.view_class_code(class_id))
        elif choice == '11':
            func_id = input("请输入函数ID: ")
            print(explorer.view_function_code(func_id))
        elif choice == '12':
            entity_id = input("请输入实体ID: ")
            entity_type = input("请输入实体类型 (function 或 class): ").lower()
            print(explorer.view_reference_relationships(entity_id, entity_type))
        else:
            print("无效的选择!")
    """
def test_code_explorer():
    """测试代码探索工具"""
    from dotenv import load_dotenv
    
    load_dotenv("configs/.env")
    
    explorer = CodeExplorerTools("/mnt/ceph/huacan/Data/coding_run/gitbench_0520_1040/task_1/workspace/chat-ui")
    print(explorer.view_file_content("/mnt/ceph/huacan/Data/coding_run/gitbench_0520_1040/task_1/workspace/chat-ui/README.md", "了解项目功能和使用方法"))


if __name__ == "__main__":
    # main()
    test_code_explorer()