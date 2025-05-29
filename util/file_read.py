import json
import os
import re
import yaml
import xml.etree.ElementTree as ET
import markdown
import csv
from bs4 import BeautifulSoup

class GitHubFileParser:
    """
    解析GitHub仓库中各种类型文件的工具类，提取关键信息，忽略不重要的部分
    """
    
    def __init__(self):
        self.supported_extensions = {
            '.ipynb': self._parse_ipynb_file,
            '.py': self._parse_python_file,
            '.md': self._parse_markdown_file,
            '.yml': self._parse_yaml_file,
            '.yaml': self._parse_yaml_file,
            '.json': self._parse_json_file,
            '.html': self._parse_html_file,
            '.css': self._parse_css_file,
            '.js': self._parse_js_file,
            '.ts': self._parse_typescript_file,
            '.java': self._parse_java_file,
            '.c': self._parse_c_file,
            '.cpp': self._parse_cpp_file,
            '.h': self._parse_header_file,
            '.sh': self._parse_shell_file,
            '.xml': self._parse_xml_file,
            '.csv': self._parse_csv_file,
            '.txt': self._parse_text_file,
            '.rst': self._parse_rst_file,
            '.ini': self._parse_ini_file,
            '.toml': self._parse_toml_file,
            '.Dockerfile': self._parse_dockerfile,
            '.gitignore': self._parse_gitignore,
        }
    
    def parse_file(self, file_path):
        """
        根据文件扩展名解析文件并提取重要信息
        
        Args:
            file_path: 要解析的文件路径
            
        Returns:
            字符串形式的提取内容
        """
        _, ext = os.path.splitext(file_path)
        file_name = os.path.basename(file_path)
        
        # 处理特殊文件名
        if file_name == 'Dockerfile':
            return self._parse_dockerfile(file_path)
        elif file_name == '.gitignore':
            return self._parse_gitignore(file_path)
        
        # 根据扩展名解析文件
        if ext.lower() in self.supported_extensions:
            return self.supported_extensions[ext.lower()](file_path)
        else:
            return self._parse_generic_file(file_path)
    
    def _parse_ipynb_file(self, file_path):
        """
        解析.ipynb文件，提取代码单元格，去掉输出
        
        Args:
            file_path: .ipynb文件路径
            
        Returns:
            提取的Python代码内容字符串
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                notebook = json.load(f)
                
            code_cells = []
            
            # 提取所有代码单元格的内容
            if 'cells' in notebook:
                for cell in notebook['cells']:
                    if cell.get('cell_type') == 'code':
                        # 只提取代码单元格的源代码，忽略输出
                        source = cell.get('source', [])
                        if isinstance(source, list):
                            code_cells.append(''.join(source))
                        else:
                            code_cells.append(source)
                    elif cell.get('cell_type') == 'markdown':
                        # 可选：保留重要的markdown单元格（例如标题和短说明）
                        source = cell.get('source', [])
                        if isinstance(source, list):
                            md_content = ''.join(source)
                        else:
                            md_content = source
                        
                        # 只保留标题和简短说明
                        if md_content.startswith('#') or len(md_content) < 100:
                            code_cells.append(f"# Markdown: {md_content}")
            
            return '\n\n'.join(code_cells)
        except Exception as e:
            return f"无法解析.ipynb文件 {file_path}: {str(e)}"
    
    def _parse_python_file(self, file_path):
        """
        解析Python文件，保留代码和重要注释，去除冗长注释
        
        Args:
            file_path: Python文件路径
            
        Returns:
            处理后的Python代码
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            processed_lines = []
            in_multi_line_comment = False
            skip_lines = 0
            
            for line in lines:
                if skip_lines > 0:
                    skip_lines -= 1
                    continue
                
                # 处理多行注释
                if '"""' in line or "'''" in line:
                    if in_multi_line_comment:
                        in_multi_line_comment = False
                        # 只保留docstring的第一行
                        if line.strip() not in ['"""', "'''"]:
                            processed_lines.append(line)
                    else:
                        in_multi_line_comment = True
                        processed_lines.append(line)
                        # 如果是函数或类的docstring，保留
                        prev_lines = processed_lines[-2:-1]
                        is_def_or_class = any(l.strip().startswith(('def ', 'class ')) for l in prev_lines)
                        if not is_def_or_class:
                            skip_lines = 2  # 跳过接下来的几行详细描述
                elif not in_multi_line_comment:
                    # 保留import语句、类定义、函数定义和重要的单行注释
                    if (line.strip().startswith(('import ', 'from ', 'def ', 'class ', '# TODO', '# FIXME', '# NOTE'))
                            or not line.strip().startswith('#') 
                            or len(line.strip()) < 50):  # 短注释可能重要
                        processed_lines.append(line)
            
            return ''.join(processed_lines)
        except Exception as e:
            return f"无法解析Python文件 {file_path}: {str(e)}"
    
    def _parse_markdown_file(self, file_path):
        """
        解析Markdown文件，提取标题、列表和短段落
        
        Args:
            file_path: Markdown文件路径
            
        Returns:
            处理后的Markdown内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            processed_lines = []
            
            in_code_block = False
            in_long_paragraph = False
            paragraph_lines = []
            
            for line in lines:
                # 处理代码块
                if line.startswith('```'):
                    in_code_block = not in_code_block
                    processed_lines.append(line)
                    continue
                
                if in_code_block:
                    processed_lines.append(line)
                    continue
                
                # 保留标题和列表项
                if line.startswith(('#', '-', '*', '+', '>')):
                    # 如果之前在处理长段落，决定是否保留
                    if in_long_paragraph:
                        if len(paragraph_lines) <= 5:  # 保留短段落
                            processed_lines.extend(paragraph_lines)
                        else:
                            # 只保留段落的第一句和最后一句
                            processed_lines.append(paragraph_lines[0])
                            if len(paragraph_lines) > 1:
                                processed_lines.append('...')
                                processed_lines.append(paragraph_lines[-1])
                        
                        paragraph_lines = []
                        in_long_paragraph = False
                    
                    processed_lines.append(line)
                elif line.strip() == '':
                    # 空行结束段落
                    if in_long_paragraph:
                        if len(paragraph_lines) <= 5:  # 保留短段落
                            processed_lines.extend(paragraph_lines)
                        else:
                            # 只保留段落的第一句和最后一句
                            processed_lines.append(paragraph_lines[0])
                            if len(paragraph_lines) > 1:
                                processed_lines.append('...')
                                processed_lines.append(paragraph_lines[-1])
                        
                        paragraph_lines = []
                        in_long_paragraph = False
                    
                    processed_lines.append(line)
                else:
                    # 普通段落文本
                    if not in_long_paragraph:
                        in_long_paragraph = True
                        paragraph_lines = []
                    
                    paragraph_lines.append(line)
            
            # 处理最后的段落
            if in_long_paragraph:
                if len(paragraph_lines) <= 5:
                    processed_lines.extend(paragraph_lines)
                else:
                    processed_lines.append(paragraph_lines[0])
                    if len(paragraph_lines) > 1:
                        processed_lines.append('...')
                        processed_lines.append(paragraph_lines[-1])
            
            return '\n'.join(processed_lines)
        except Exception as e:
            return f"无法解析Markdown文件 {file_path}: {str(e)}"
    
    def _parse_yaml_file(self, file_path):
        """
        解析YAML文件，保留结构但精简内容
        
        Args:
            file_path: YAML文件路径
            
        Returns:
            精简后的YAML内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 对于配置文件，保留原始格式更好
            if len(content.split('\n')) < 100:  # 如果是简短的YAML文件，完整保留
                return content
            
            # 对于较长的YAML文件，尝试解析并精简
            try:
                data = yaml.safe_load(content)
                
                # 递归精简YAML内容
                def simplify_yaml(obj, max_items=10, max_str_len=100):
                    if isinstance(obj, dict):
                        result = {}
                        for i, (k, v) in enumerate(obj.items()):
                            if i >= max_items:
                                result['...'] = '(更多项已省略)'
                                break
                            result[k] = simplify_yaml(v, max_items, max_str_len)
                        return result
                    elif isinstance(obj, list):
                        if len(obj) <= max_items:
                            return [simplify_yaml(item, max_items, max_str_len) for item in obj]
                        else:
                            result = [simplify_yaml(item, max_items, max_str_len) for item in obj[:max_items]]
                            result.append('(更多项已省略)')
                            return result
                    elif isinstance(obj, str) and len(obj) > max_str_len:
                        return obj[:max_str_len] + '...'
                    else:
                        return obj
                
                simplified_data = simplify_yaml(data)
                return yaml.dump(simplified_data, default_flow_style=False, allow_unicode=True)
            except:
                # 如果解析失败，使用行过滤方式
                lines = content.split('\n')
                result_lines = []
                
                for line in lines:
                    # 保留所有缩进和键，但可能截断长值
                    stripped = line.lstrip()
                    indent = line[:len(line)-len(stripped)]
                    
                    if ':' in stripped:
                        key, value = stripped.split(':', 1)
                        if len(value.strip()) > 100:
                            result_lines.append(f"{indent}{key}: {value.strip()[:100]}...")
                        else:
                            result_lines.append(line)
                    else:
                        result_lines.append(line)
                
                return '\n'.join(result_lines)
        except Exception as e:
            return f"无法解析YAML文件 {file_path}: {str(e)}"
    
    def _parse_json_file(self, file_path):
        """
        解析JSON文件，保留结构但精简长数组和长字符串
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            精简后的JSON内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
            
            # 递归精简JSON内容
            def simplify_json(obj, max_items=10, max_str_len=100):
                if isinstance(obj, dict):
                    result = {}
                    for i, (k, v) in enumerate(obj.items()):
                        if i >= max_items:
                            result["..."] = "(更多项已省略)"
                            break
                        result[k] = simplify_json(v, max_items, max_str_len)
                    return result
                elif isinstance(obj, list):
                    if len(obj) <= max_items:
                        return [simplify_json(item, max_items, max_str_len) for item in obj]
                    else:
                        result = [simplify_json(item, max_items, max_str_len) for item in obj[:max_items]]
                        result.append("(更多项已省略)")
                        return result
                elif isinstance(obj, str) and len(obj) > max_str_len:
                    return obj[:max_str_len] + "..."
                else:
                    return obj
            
            simplified_data = simplify_json(data)
            return json.dumps(simplified_data, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"无法解析JSON文件 {file_path}: {str(e)}"
    
    def _parse_html_file(self, file_path):
        """
        解析HTML文件，提取结构和关键内容
        
        Args:
            file_path: HTML文件路径
            
        Returns:
            简化后的HTML结构
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # 移除脚本和样式内容
            for script in soup(["script", "style"]):
                script.extract()
            
            # 移除注释
            comments = soup.find_all(string=lambda text: isinstance(text, str) and text.strip().startswith('<!--'))
            for comment in comments:
                comment.extract()
            
            # 提取HTML结构
            structure_lines = []
            
            def extract_structure(element, depth=0):
                if not element:
                    return
                
                if element.name:
                    indent = '  ' * depth
                    attrs = ''
                    
                    # 保留重要属性
                    important_attrs = ['id', 'class', 'href', 'src', 'alt', 'type']
                    attr_list = []
                    
                    for attr in important_attrs:
                        if element.has_attr(attr):
                            value = element[attr]
                            if isinstance(value, list):
                                value = ' '.join(value)
                            if len(str(value)) > 50:
                                value = str(value)[:50] + '...'
                            attr_list.append(f'{attr}="{value}"')
                    
                    if attr_list:
                        attrs = ' ' + ' '.join(attr_list)
                    
                    # 处理内容
                    content = ''
                    if element.string and element.string.strip():
                        text = element.string.strip()
                        if len(text) > 100:
                            text = text[:100] + '...'
                        content = f': "{text}"'
                    
                    structure_lines.append(f"{indent}<{element.name}{attrs}>{content}")
                    
                    # 递归处理子元素
                    for child in element.children:
                        if child.name:
                            extract_structure(child, depth + 1)
                    
                    # 只为特定元素显示结束标记
                    if element.name in ['html', 'head', 'body', 'div', 'section', 'article', 'main']:
                        structure_lines.append(f"{indent}</{element.name}>")
            
            extract_structure(soup.html)
            
            return '\n'.join(structure_lines)
        except Exception as e:
            return f"无法解析HTML文件 {file_path}: {str(e)}"
    
    def _parse_css_file(self, file_path):
        """
        解析CSS文件，保留选择器和属性，简化大量重复内容
        
        Args:
            file_path: CSS文件路径
            
        Returns:
            简化的CSS内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 使用正则表达式分离CSS规则
            # 匹配从选择器到闭合大括号的整个规则块
            rule_pattern = re.compile(r'([^{]+){([^}]*)}')
            rules = rule_pattern.findall(content)
            
            processed_rules = []
            seen_selectors = set()
            
            for selector, declarations in rules:
                selector = selector.strip()
                
                # 跳过已处理的相似选择器
                selector_base = re.sub(r'[.#][a-zA-Z0-9-_]+', '.CLASS', selector)
                if selector_base in seen_selectors and len(seen_selectors) > 50:
                    continue
                
                seen_selectors.add(selector_base)
                
                # 处理声明
                declaration_lines = [d.strip() for d in declarations.split(';') if d.strip()]
                
                if len(declaration_lines) > 5:
                    # 只保留前5个重要属性
                    important_properties = ['display', 'position', 'width', 'height', 'margin', 'padding', 
                                          'color', 'background', 'font', 'text-align', 'z-index']
                    
                    kept_declarations = []
                    for decl in declaration_lines:
                        if ':' in decl:
                            prop = decl.split(':', 1)[0].strip()
                            if prop in important_properties or len(kept_declarations) < 3:
                                kept_declarations.append(decl)
                                if len(kept_declarations) >= 5:
                                    break
                    
                    if len(kept_declarations) < len(declaration_lines):
                        kept_declarations.append('/* 更多属性已省略 */')
                    
                    declaration_text = ';\n  '.join(kept_declarations)
                else:
                    declaration_text = ';\n  '.join(declaration_lines)
                
                rule_text = f"{selector} {{\n  {declaration_text};\n}}"
                processed_rules.append(rule_text)
            
            if len(processed_rules) > 100:
                # 如果规则太多，只保留部分
                return '\n\n'.join(processed_rules[:100]) + '\n\n/* 更多CSS规则已省略... */'
            
            return '\n\n'.join(processed_rules)
        except Exception as e:
            return f"无法解析CSS文件 {file_path}: {str(e)}"
    
    def _parse_js_file(self, file_path):
        """
        解析JavaScript文件，保留函数声明、类定义和重要代码
        
        Args:
            file_path: JavaScript文件路径
            
        Returns:
            简化的JavaScript代码
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            result_lines = []
            
            in_comment = False
            skip_lines = 0
            
            for line in lines:
                if skip_lines > 0:
                    skip_lines -= 1
                    continue
                
                # 处理多行注释
                if '/*' in line and '*/' in line:
                    # 单行注释，保留
                    result_lines.append(line)
                elif '/*' in line:
                    in_comment = True
                    # 只保留开始的注释
                    result_lines.append(line)
                elif '*/' in line:
                    in_comment = False
                    result_lines.append(line)
                elif in_comment:
                    # 在多行注释中，只保留JSDoc风格的重要注释行
                    if '@' in line or line.strip().startswith('*'):
                        result_lines.append(line)
                else:
                    # 保留import/export语句
                    if re.match(r'^\s*(import|export)\s', line):
                        result_lines.append(line)
                    # 保留函数和类声明
                    elif re.search(r'(function|class|const|let|var|=>)\s', line) or '{' in line:
                        result_lines.append(line)
                    # 保留其他代码行（不是空行或单纯的注释）
                    elif line.strip() and not line.strip().startswith('//'):
                        result_lines.append(line)
                    # 保留短注释，可能包含重要信息
                    elif line.strip().startswith('//') and len(line) < 80:
                        result_lines.append(line)
            
            return '\n'.join(result_lines)
        except Exception as e:
            return f"无法解析JavaScript文件 {file_path}: {str(e)}"
    
    def _parse_typescript_file(self, file_path):
        """
        解析TypeScript文件，类似JS但保留类型定义
        
        Args:
            file_path: TypeScript文件路径
            
        Returns:
            简化的TypeScript代码
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # TypeScript解析与JavaScript类似，但要特别关注类型定义
            lines = content.split('\n')
            result_lines = []
            
            in_comment = False
            skip_lines = 0
            
            for line in lines:
                if skip_lines > 0:
                    skip_lines -= 1
                    continue
                
                # 处理多行注释
                if '/*' in line and '*/' in line:
                    result_lines.append(line)
                elif '/*' in line:
                    in_comment = True
                    result_lines.append(line)
                elif '*/' in line:
                    in_comment = False
                    result_lines.append(line)
                elif in_comment:
                    if '@' in line or line.strip().startswith('*'):
                        result_lines.append(line)
                else:
                    # 保留类型定义
                    if re.match(r'^\s*(type|interface|enum)\s', line) or ':' in line:
                        result_lines.append(line)
                    # 保留import/export语句
                    elif re.match(r'^\s*(import|export)\s', line):
                        result_lines.append(line)
                    # 保留函数和类声明
                    elif re.search(r'(function|class|const|let|var|=>)\s', line) or '{' in line:
                        result_lines.append(line)
                    # 保留其他代码行
                    elif line.strip() and not line.strip().startswith('//'):
                        result_lines.append(line)
                    # 保留短注释
                    elif line.strip().startswith('//') and len(line) < 80:
                        result_lines.append(line)
            
            return '\n'.join(result_lines)
        except Exception as e:
            return f"无法解析TypeScript文件 {file_path}: {str(e)}"
    
    def _parse_java_file(self, file_path):
        """
        解析Java文件，保留类结构、方法定义和重要代码
        
        Args:
            file_path: Java文件路径
            
        Returns:
            简化的Java代码
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            result_lines = []
            
            in_comment = False
            in_method_body = False
            method_body_indent = 0
            bracket_count = 0
            
            for line in lines:
                stripped = line.strip()
                
                # 处理多行注释
                if '/*' in stripped and '*/' in stripped:
                    result_lines.append(line)
                elif '/*' in stripped:
                    in_comment = True
                    result_lines.append(line)
                elif '*/' in stripped:
                    in_comment = False
                    result_lines.append(line)
                elif in_comment:
                    # 保留Javadoc关键注释
                    if '@' in line or line.strip().startswith('*'):
                        result_lines.append(line)
                else:
                    # 包和导入声明
                    if stripped.startswith(('package ', 'import ')):
                        result_lines.append(line)
                    # 类和接口定义
                    elif any(keyword in stripped for keyword in ['class ', 'interface ', 'enum ', '@interface']):
                        result_lines.append(line)
                        if '{' in stripped:
                            bracket_count += 1
                    # 方法和字段定义
                    elif re.match(r'^\s*(public|private|protected|static|final|native|synchronized|abstract|transient|volatile)\s', line) or re.match(r'^\s*[A-Za-z][A-Za-z0-9_<>[\],\s]+\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(', line):
                        result_lines.append(line)
                        if '{' in stripped:
                            in_method_body = True
                            method_body_indent = len(line) - len(stripped)
                            bracket_count = 1
                    # 方法体内的关键行
                    elif in_method_body:
                        # 计数括号以确定何时退出方法体
                        bracket_count += stripped.count('{')
                        bracket_count -= stripped.count('}')
                        
                        if bracket_count <= 0:
                            in_method_body = False
                        
                        # 在方法体内只保留一些关键行
                        if ('{' in stripped or '}' in stripped or 
                            any(keyword in stripped for keyword in ['if', 'for', 'while', 'switch', 'try', 'catch', 'return', 'throw']) or
                            '=' in stripped or stripped.endswith(';')):
                            
                            # 只保留第一层级的语句
                            current_indent = len(line) - len(stripped)
                            if current_indent <= method_body_indent + 4:
                                result_lines.append(line)
                    # 其他大括号行（用于类结构）
                    elif '{' in stripped or '}' in stripped:
                        result_lines.append(line)
            
            return '\n'.join(result_lines)
        except Exception as e:
            return f"无法解析Java文件 {file_path}: {str(e)}"
    
    def _parse_c_file(self, file_path):
        """
        解析C文件，保留函数声明、结构体定义和重要代码
        
        Args:
            file_path: C文件路径
            
        Returns:
            简化的C代码
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            result_lines = []
            
            in_comment = False
            in_function_body = False
            function_body_indent = 0
            bracket_count = 0
            
            for line in lines:
                stripped = line.strip()
                
                # 处理多行注释
                if '/*' in stripped and '*/' in stripped:
                    result_lines.append(line)
                elif '/*' in stripped:
                    in_comment = True
                    result_lines.append(line)
                elif '*/' in stripped:
                    in_comment = False
                    result_lines.append(line)
                elif in_comment:
                    # 只保留关键注释
                    if '@' in line or line.strip().startswith('*'):
                        result_lines.append(line)
                else:
                    # 预处理指令
                    if stripped.startswith('#'):
                        result_lines.append(line)
                    # 结构体、联合体和枚举定义
                    elif any(keyword in stripped for keyword in ['struct ', 'union ', 'enum ', 'typedef ']):
                        result_lines.append(line)
                    # 函数定义
                    elif re.match(r'^[a-zA-Z_][a-zA-Z0-9_*\s]+\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(', stripped):
                        result_lines.append(line)
                        if '{' in stripped:
                            in_function_body = True
                            function_body_indent = len(line) - len(stripped)
                            bracket_count = 1
                    # 函数体内的关键行
                    elif in_function_body:
                        # 计数括号以确定何时退出函数体
                        bracket_count += stripped.count('{')
                        bracket_count -= stripped.count('}')
                        
                        if bracket_count <= 0:
                            in_function_body = False
                        
                        # 在函数体内只保留一些关键行
                        if ('{' in stripped or '}' in stripped or 
                            any(keyword in stripped for keyword in ['if', 'for', 'while', 'switch', 'case', 'return', 'goto']) or
                            '=' in stripped or stripped.endswith(';')):
                            
                            # 只保留第一层级的语句
                            current_indent = len(line) - len(stripped)
                            if current_indent <= function_body_indent + 4:
                                result_lines.append(line)
                    # 全局变量声明
                    elif ';' in stripped and not in_function_body:
                        result_lines.append(line)
                    # 其他大括号行
                    elif '{' in stripped or '}' in stripped:
                        result_lines.append(line)
            
            return '\n'.join(result_lines)
        except Exception as e:
            return f"无法解析C文件 {file_path}: {str(e)}"
    
    def _parse_cpp_file(self, file_path):
        """
        解析C++文件，保留类定义、函数声明和重要代码
        
        Args:
            file_path: C++文件路径
            
        Returns:
            简化的C++代码
        """
        # C++解析与C类似，但需要增加类特有的处理
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            result_lines = []
            
            in_comment = False
            in_function_body = False
            function_body_indent = 0
            bracket_count = 0
            
            for line in lines:
                stripped = line.strip()
                
                # 处理多行注释
                if '/*' in stripped and '*/' in stripped:
                    result_lines.append(line)
                elif '/*' in stripped:
                    in_comment = True
                    result_lines.append(line)
                elif '*/' in stripped:
                    in_comment = False
                    result_lines.append(line)
                elif in_comment:
                    if '@' in line or line.strip().startswith('*'):
                        result_lines.append(line)
                else:
                    # 预处理指令
                    if stripped.startswith('#'):
                        result_lines.append(line)
                    # 命名空间、using指令
                    elif stripped.startswith(('namespace ', 'using ')):
                        result_lines.append(line)
                    # 类、结构体、联合体和枚举定义
                    elif any(keyword in stripped for keyword in ['class ', 'struct ', 'union ', 'enum ', 'typedef ']):
                        result_lines.append(line)
                    # 模板定义
                    elif stripped.startswith('template'):
                        result_lines.append(line)
                    # 函数定义
                    elif re.match(r'^[a-zA-Z_][a-zA-Z0-9_:*<>[\],\s]+\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(', stripped):
                        result_lines.append(line)
                        if '{' in stripped:
                            in_function_body = True
                            function_body_indent = len(line) - len(stripped)
                            bracket_count = 1
                    # 函数体内的关键行
                    elif in_function_body:
                        # 计数括号以确定何时退出函数体
                        bracket_count += stripped.count('{')
                        bracket_count -= stripped.count('}')
                        
                        if bracket_count <= 0:
                            in_function_body = False
                        
                        # 在函数体内只保留一些关键行
                        if ('{' in stripped or '}' in stripped or 
                            any(keyword in stripped for keyword in ['if', 'for', 'while', 'switch', 'case', 'return', 'throw', 'try', 'catch']) or
                            '=' in stripped or stripped.endswith(';')):
                            
                            # 只保留第一层级的语句
                            current_indent = len(line) - len(stripped)
                            if current_indent <= function_body_indent + 4:
                                result_lines.append(line)
                    # 全局变量声明
                    elif ';' in stripped and not in_function_body:
                        result_lines.append(line)
                    # 其他大括号行
                    elif '{' in stripped or '}' in stripped:
                        result_lines.append(line)
            
            return '\n'.join(result_lines)
        except Exception as e:
            return f"无法解析C++文件 {file_path}: {str(e)}"
    
    def _parse_header_file(self, file_path):
        """
        解析C/C++头文件，保留类型定义、函数声明等
        
        Args:
            file_path: 头文件路径
            
        Returns:
            简化的头文件内容
        """
        # 头文件解析类似于C/C++文件，但主要关注声明而非定义
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            result_lines = []
            
            in_comment = False
            
            for line in lines:
                stripped = line.strip()
                
                # 处理多行注释
                if '/*' in stripped and '*/' in stripped:
                    result_lines.append(line)
                elif '/*' in stripped:
                    in_comment = True
                    result_lines.append(line)
                elif '*/' in stripped:
                    in_comment = False
                    result_lines.append(line)
                elif in_comment:
                    if '@' in line or line.strip().startswith('*'):
                        result_lines.append(line)
                else:
                    # 保留大部分头文件内容，因为它们通常是声明而非实现
                    # 预处理指令、包含保护、条件编译
                    if stripped.startswith('#'):
                        result_lines.append(line)
                    # 类型定义、结构体、类等
                    elif any(keyword in stripped for keyword in ['class ', 'struct ', 'union ', 'enum ', 'typedef ']):
                        result_lines.append(line)
                    # 函数原型
                    elif ';' in stripped and '(' in stripped:
                        result_lines.append(line)
                    # 变量声明
                    elif ';' in stripped:
                        result_lines.append(line)
                    # 命名空间、using指令
                    elif stripped.startswith(('namespace ', 'using ')):
                        result_lines.append(line)
                    # 模板定义
                    elif stripped.startswith('template'):
                        result_lines.append(line)
                    # 保留大括号结构
                    elif '{' in stripped or '}' in stripped:
                        result_lines.append(line)
            
            return '\n'.join(result_lines)
        except Exception as e:
            return f"无法解析头文件 {file_path}: {str(e)}"
    
    def _parse_shell_file(self, file_path):
        """
        解析Shell脚本，保留命令和重要注释
        
        Args:
            file_path: Shell脚本文件路径
            
        Returns:
            简化的Shell脚本内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            result_lines = []
            in_heredoc = False
            heredoc_marker = ''
            
            for line in lines:
                stripped = line.strip()
                
                # 处理heredoc结构
                if in_heredoc:
                    if stripped == heredoc_marker:
                        in_heredoc = False
                        result_lines.append(line)
                    continue
                elif '<<' in line and not stripped.startswith('#'):
                    parts = line.split('<<', 1)[1].strip()
                    if parts:
                        heredoc_marker = parts.split()[0].strip("'\"")
                        if heredoc_marker:
                            in_heredoc = True
                            result_lines.append(line)
                            continue
                
                # 保留以下内容
                # Shebang
                if stripped.startswith('#!'):
                    result_lines.append(line)
                # 函数定义
                elif stripped.startswith('function ') or re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*\(\s*\)', stripped):
                    result_lines.append(line)
                # 控制结构
                elif any(stripped.startswith(keyword) for keyword in ['if ', 'for ', 'while ', 'case ', 'until ', 'select ']):
                    result_lines.append(line)
                elif any(keyword == stripped for keyword in ['then', 'do', 'done', 'fi', 'esac']):
                    result_lines.append(line)
                # 变量赋值
                elif '=' in stripped and not stripped.startswith('#') and not ' ' in stripped.split('=')[0]:
                    result_lines.append(line)
                # 管道和重定向
                elif '|' in stripped or '>' in stripped or '<' in stripped:
                    result_lines.append(line)
                # 重要注释（TODO, FIXME等）
                elif stripped.startswith('#') and any(marker in stripped.upper() for marker in ['TODO', 'FIXME', 'NOTE', 'WARNING']):
                    result_lines.append(line)
                # 常用命令
                elif any(stripped.startswith(cmd) for cmd in ['cd ', 'ls ', 'echo ', 'cat ', 'grep ', 'find ', 'sed ', 'awk ', 'curl ', 'wget ', 'mkdir ', 'rm ', 'cp ', 'mv ']):
                    result_lines.append(line)
                # 非空的执行命令行
                elif not stripped.startswith('#') and stripped:
                    result_lines.append(line)
            
            return ''.join(result_lines)
        except Exception as e:
            return f"无法解析Shell脚本文件 {file_path}: {str(e)}"
    
    def _parse_xml_file(self, file_path):
        """
        解析XML文件，保留结构但精简内容
        
        Args:
            file_path: XML文件路径
            
        Returns:
            简化的XML内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 处理XML声明和DOCTYPE
            result = []
            lines = content.split('\n')
            for line in lines:
                if line.strip().startswith('<?xml') or line.strip().startswith('<!DOCTYPE'):
                    result.append(line)
            
            try:
                # 尝试解析XML
                root = ET.fromstring(content)
                
                # 递归处理XML元素
                def process_element(element, depth=0):
                    indent = '  ' * depth
                    tag = element.tag
                    
                    # 处理命名空间
                    if '}' in tag:
                        tag = tag.split('}', 1)[1]
                    
                    # 获取元素属性
                    attrs = []
                    for key, value in element.attrib.items():
                        # 简化属性值
                        if len(value) > 50:
                            value = value[:50] + '...'
                        
                        # 处理属性中的命名空间
                        if '}' in key:
                            key = key.split('}', 1)[1]
                        
                        attrs.append(f'{key}="{value}"')
                    
                    attr_str = ' ' + ' '.join(attrs) if attrs else ''
                    
                    # 如果元素有子元素，递归处理
                    children = list(element)
                    if children:
                        result.append(f"{indent}<{tag}{attr_str}>")
                        
                        # 限制子元素数量
                        if len(children) > 10:
                            for child in children[:5]:
                                process_element(child, depth + 1)
                            result.append(f"{indent}  <!-- {len(children) - 10} more elements omitted -->")
                            for child in children[-5:]:
                                process_element(child, depth + 1)
                        else:
                            for child in children:
                                process_element(child, depth + 1)
                        
                        result.append(f"{indent}</{tag}>")
                    else:
                        # 处理文本内容
                        text = element.text
                        if text and text.strip():
                            if len(text.strip()) > 100:
                                text = text.strip()[:100] + '...'
                            result.append(f"{indent}<{tag}{attr_str}>{text}</{tag}>")
                        else:
                            result.append(f"{indent}<{tag}{attr_str} />")
                
                process_element(root)
                return '\n'.join(result)
            
            except Exception:
                # 如果XML解析失败，使用简单的行处理方式
                in_tag = False
                depth = 0
                
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    
                    # 移除注释
                    if '<!--' in stripped and '-->' in stripped:
                        continue
                    
                    # 简单处理XML标签和内容
                    if '<' in stripped and '>' in stripped:
                        if stripped.startswith('</'):
                            depth -= 1
                        
                        indent = '  ' * max(0, depth)
                        result.append(f"{indent}{stripped}")
                        
                        if not stripped.startswith('</') and not stripped.endswith('/>') and not stripped.startswith('<?'):
                            depth += 1
                
                return '\n'.join(result)
        except Exception as e:
            return f"无法解析XML文件 {file_path}: {str(e)}"
    
    def _parse_csv_file(self, file_path):
        """
        解析CSV文件，保留结构但限制行数
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            简化的CSV内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if not rows:
                return "CSV文件为空"
            
            header = rows[0]
            data_rows = rows[1:] if len(rows) > 1 else []
            
            # 如果行数过多，只保留前10行和后5行
            MAX_ROWS = 15
            if len(data_rows) > MAX_ROWS:
                result_rows = [header] + data_rows[:10]
                result_rows.append(['...'] * len(header))
                result_rows.extend(data_rows[-5:])
            else:
                result_rows = rows
            
            # 如果列数过多，只保留前面几列
            MAX_COLS = 10
            if any(len(row) > MAX_COLS for row in result_rows):
                truncated_rows = []
                for row in result_rows:
                    if len(row) > MAX_COLS:
                        truncated_row = row[:MAX_COLS] + ['...']
                        truncated_rows.append(truncated_row)
                    else:
                        truncated_rows.append(row)
                result_rows = truncated_rows
            
            # 生成CSV字符串
            output = []
            for row in result_rows:
                # 处理每个字段，如果太长就截断
                processed_row = []
                for field in row:
                    if len(field) > 50:
                        processed_row.append(field[:50] + '...')
                    else:
                        processed_row.append(field)
                
                output.append(','.join(f'"{field}"' if ',' in field else field for field in processed_row))
            
            return '\n'.join(output)
        except Exception as e:
            return f"无法解析CSV文件 {file_path}: {str(e)}"
    
    def _parse_text_file(self, file_path):
        """
        解析文本文件，保留重要行，精简长段落
        
        Args:
            file_path: 文本文件路径
            
        Returns:
            处理后的文本内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            result_lines = []
            current_paragraph = []
            
            for line in lines:
                stripped = line.strip()
                
                # 空行表示段落结束
                if not stripped:
                    if current_paragraph:
                        # 处理当前段落
                        if len(current_paragraph) <= 5:
                            # 短段落完整保留
                            result_lines.extend(current_paragraph)
                        else:
                            # 长段落只保留首尾行
                            result_lines.append(current_paragraph[0])
                            result_lines.append("...")
                            result_lines.append(current_paragraph[-1])
                        
                        current_paragraph = []
                    
                    result_lines.append(line)  # 保留空行
                else:
                    # 可能的标题或分隔线
                    if all(c == '=' for c in stripped) or all(c == '-' for c in stripped) or all(c == '*' for c in stripped):
                        # 处理之前的段落
                        if current_paragraph:
                            result_lines.extend(current_paragraph)
                            current_paragraph = []
                        
                        result_lines.append(line)
                    # 可能的列表项
                    elif stripped.startswith(('-', '*', '+', '•', '1.', '2.')):
                        # 处理之前的段落
                        if current_paragraph:
                            result_lines.extend(current_paragraph)
                            current_paragraph = []
                        
                        result_lines.append(line)
                    # 普通段落文本
                    else:
                        current_paragraph.append(line)
            
            # 处理最后一个段落
            if current_paragraph:
                if len(current_paragraph) <= 5:
                    result_lines.extend(current_paragraph)
                else:
                    result_lines.append(current_paragraph[0])
                    result_lines.append("...")
                    result_lines.append(current_paragraph[-1])
            
            return ''.join(result_lines)
        except Exception as e:
            return f"无法解析文本文件 {file_path}: {str(e)}"
    
    def _parse_ini_file(self, file_path):
        """
        解析INI配置文件，保留结构
        
        Args:
            file_path: INI文件路径
            
        Returns:
            处理后的INI内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            result_lines = []
            current_section = None
            section_items = 0
            
            for line in lines:
                stripped = line.strip()
                
                # 跳过空行和注释
                if not stripped or stripped.startswith((';', '#')):
                    result_lines.append(line)
                    continue
                
                # 处理节
                if stripped.startswith('[') and stripped.endswith(']'):
                    current_section = stripped
                    section_items = 0
                    result_lines.append(line)
                # 处理键值对
                elif '=' in stripped:
                    section_items += 1
                    # 限制每个节显示的项数
                    if section_items <= 10:
                        result_lines.append(line)
                    elif section_items == 11:
                        result_lines.append("# ... more items omitted ...\n")
                else:
                    result_lines.append(line)
            
            return ''.join(result_lines)
        except Exception as e:
            return f"无法解析INI文件 {file_path}: {str(e)}"
    
    def _parse_toml_file(self, file_path):
        """
        解析TOML配置文件，保留结构
        
        Args:
            file_path: TOML文件路径
            
        Returns:
            处理后的TOML内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            result_lines = []
            current_section = None
            section_items = 0
            in_array = False
            array_items = 0
            
            for line in lines:
                stripped = line.strip()
                
                # 跳过空行和注释
                if not stripped or stripped.startswith('#'):
                    result_lines.append(line)
                    continue
                
                # 处理表
                if stripped.startswith('[') and ']' in stripped and not stripped.startswith('[['):
                    current_section = stripped
                    section_items = 0
                    in_array = False
                    result_lines.append(line)
                # 处理数组表
                elif stripped.startswith('[[') and ']]' in stripped:
                    current_section = stripped
                    section_items = 0
                    in_array = False
                    result_lines.append(line)
                # 处理多行数组开始
                elif '=[' in stripped and not stripped.endswith(']'):
                    in_array = True
                    array_items = 0
                    result_lines.append(line)
                # 处理多行数组项
                elif in_array:
                    array_items += 1
                    # 限制数组中显示的项
                    if stripped.endswith(']'):
                        in_array = False
                        if array_items <= 5:
                            result_lines.append(line)
                        else:
                            # 已经省略了一些项，现在添加结束括号
                            result_lines.append(']')
                    elif array_items <= 5:
                        result_lines.append(line)
                    elif array_items == 6:
                        result_lines.append("# ... more array items omitted ...\n")
                # 处理键值对
                elif '=' in stripped:
                    section_items += 1
                    key, value = stripped.split('=', 1)
                    
                    # 处理长字符串值
                    if len(value.strip()) > 100 and not (
                            value.strip().startswith(('"""', "'''")) or
                            value.strip().startswith('[') and value.strip().endswith(']')):
                        result_lines.append(f"{key}= {value.strip()[:100]}...\n")
                    else:
                        result_lines.append(line)
                else:
                    result_lines.append(line)
            
            return ''.join(result_lines)
        except Exception as e:
            return f"无法解析TOML文件 {file_path}: {str(e)}"
    
    def _parse_dockerfile(self, file_path):
        """
        解析Dockerfile，保留全部指令
        
        Args:
            file_path: Dockerfile路径
            
        Returns:
            处理后的Dockerfile内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            result_lines = []
            continued_line = False
            current_instruction = None
            
            for line in lines:
                stripped = line.strip()
                
                # 跳过空行和注释
                if not stripped or stripped.startswith('#'):
                    if not continued_line:  # 不在多行指令中才添加注释
                        result_lines.append(line)
                    continue
                
                # 处理行尾反斜杠（多行指令）
                if stripped.endswith('\\'):
                    continued_line = True
                    # 如果是指令的第一行
                    if not current_instruction:
                        parts = stripped.split(None, 1)
                        if len(parts) > 0:
                            current_instruction = parts[0].upper()
                    
                    # 保留RUN、ENV等重要指令的完整内容
                    if current_instruction in ['FROM', 'RUN', 'CMD', 'ENTRYPOINT', 'ENV', 'ARG']:
                        result_lines.append(line)
                    # 对于COPY、ADD等，可能包含很多文件，可以简化
                    elif current_instruction in ['COPY', 'ADD'] and len(result_lines) > 0 and '\\' in result_lines[-1]:
                        # 已经添加了第一行，后续行可能包含大量文件
                        if len(stripped) > 100:
                            # 简化长行
                            result_lines.append(f"{stripped[:50]}... \\\n")
                        else:
                            result_lines.append(line)
                    else:
                        result_lines.append(line)
                else:
                    continued_line = False
                    current_instruction = None
                    
                    # 不是多行指令的延续，直接添加
                    if not stripped.startswith('#'):
                        result_lines.append(line)
            
            return ''.join(result_lines)
        except Exception as e:
            return f"无法解析Dockerfile文件 {file_path}: {str(e)}"