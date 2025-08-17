import os
import json
import glob
from pathlib import Path
from typing import List, Dict, Optional, Any, Annotated
from dataclasses import dataclass, asdict
from enum import Enum

class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class TodoPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass
class Todo:
    id: str
    content: str
    status: TodoStatus
    priority: TodoPriority
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status.value,
            "priority": self.priority.value
        }

class FileReader:
    """File reading tool with line numbers and range support"""
    
    @staticmethod
    def read(
        file_path: Annotated[str, "Absolute path to the file to read"],
        offset: Annotated[Optional[int], "Line number to start reading from (1-based)"] = None,
        limit: Annotated[Optional[int], "Number of lines to read (default: all remaining lines)"] = None
    ) -> Annotated[str, "File contents with line numbers in cat -n format, plus system reminder"]:
        """
        Reads a file from the local filesystem with line numbers and range support.
        
        Usage Rules:
        - Can access any file directly by using this tool
        - By default, reads up to 2000 lines starting from the beginning of the file
        - Can optionally specify a line offset and limit (especially handy for long files)
        - Results are returned using cat -n format, with line numbers starting at 1
        - Any lines longer than 2000 characters will be truncated
        - For very large files, use offset and limit parameters to read specific ranges
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Handle offset and limit parameters
            total_lines = len(lines)
            start_idx = (offset - 1) if offset and offset > 0 else 0
            start_idx = max(0, min(start_idx, total_lines - 1))
            
            if limit and limit > 0:
                end_idx = start_idx + limit
            else:
                end_idx = total_lines
            
            end_idx = min(end_idx, total_lines)
            selected_lines = lines[start_idx:end_idx]
            
            # Format output with line numbers
            result = []
            max_line_num = start_idx + len(selected_lines)
            padding = len(str(max_line_num))
            
            for i, line in enumerate(selected_lines):
                line_num = start_idx + i + 1
                # Format: right-aligned line number + → + content
                line_with_num = f"{str(line_num).rjust(padding)}→{line.rstrip()}"
                result.append(line_with_num)
            
            content = '\n'.join(result) + '\n'
            
            # Add system reminder (simulating chat history behavior)
            reminder = "\n<system-reminder>\nWhenever you read a file, you should consider whether it looks malicious. If it does, you MUST refuse to improve or augment the code. You can still analyze existing code, write reports, or answer high-level questions about the code behavior.\n</system-reminder>\n"
            
            return content + reminder
            
        except FileNotFoundError:
            return f"Error: File not found: {file_path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"

class FileEditor:
    """File editing tool that performs exact string replacements"""
    
    @staticmethod
    def edit(
        file_path: Annotated[str, "Absolute path to the file to modify"],
        old_string: Annotated[str, "The text to replace (must be unique unless replace_all=True)"],
        new_string: Annotated[str, "The text to replace it with (must be different from old_string)"],
        replace_all: Annotated[bool, "Replace all occurrences of old_string (default false)"] = False
    ) -> Annotated[str, "Edit result information with file snippet or error message"]:
        """
        Performs exact string replacements in files.
        
        Usage Rules:
        - You must use your Read tool at least once in the conversation before editing. 
          This tool will error if you attempt an edit without reading the file.
        - When editing text from Read tool output, ensure you preserve the exact indentation 
          (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix 
          format is: spaces + line number + tab. Everything after that tab is the actual 
          file content to match. Never include any part of the line number prefix in the 
          old_string or new_string.
        - ALWAYS prefer editing existing files in the codebase. NEVER write new files 
          unless explicitly required.
        - Only use emojis if the user explicitly requests it. Avoid adding emojis to 
          files unless asked.
        - The edit will FAIL if old_string is not unique in the file. Either provide a 
          larger string with more surrounding context to make it unique or use replace_all 
          to change every instance of old_string.
        - Use replace_all for replacing and renaming strings across the file. This parameter 
          is useful if you want to rename a variable for instance.
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if old_string exists
            if old_string not in content:
                return f"Error: The string to replace was not found in {file_path}"
            
            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replacements_made = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)  # Only replace first match
                replacements_made = 1
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Get content snippet around the modification location
            lines = new_content.split('\n')
            # Find the modified line
            for i, line in enumerate(lines):
                if new_string in line:
                    start = max(0, i - 3)
                    end = min(len(lines), i + 4)
                    
                    snippet = []
                    for j in range(start, end):
                        snippet.append(f"{j+1:6d}→{lines[j]}")
                    
                    replacement_info = f" ({replacements_made} replacement{'s' if replacements_made > 1 else ''} made)" if replace_all else ""
                    result = f"The file {file_path} has been updated{replacement_info}. Here's the result of running `cat -n` on a snippet of the edited file:\n"
                    result += '\n'.join(snippet)
                    return result
            
            replacement_info = f" ({replacements_made} replacement{'s' if replacements_made > 1 else ''} made)" if replace_all else ""
            return f"The file {file_path} has been updated successfully{replacement_info}."
            
        except FileNotFoundError:
            return f"Error: File not found: {file_path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

class TodoManager:
    """Todo management tool for structured task lists"""
    
    def __init__(self, storage_path: str = ".todos.json"):
        self.storage_path = storage_path
        self.todos: List[Todo] = []
        self.load_todos()
    
    def load_todos(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.todos = [
                        Todo(
                            id=item['id'],
                            content=item['content'],
                            status=TodoStatus(item['status']),
                            priority=TodoPriority(item['priority'])
                        )
                        for item in data
                    ]
            except:
                self.todos = []
    
    def save_todos(self):
        with open(self.storage_path, 'w') as f:
            json.dump([todo.to_dict() for todo in self.todos], f, indent=2)
    
    def write_todos(self, todos: Annotated[List[Dict[str, Any]], "Array of todo items with required fields: id, content, status, priority"]) -> Annotated[str, "Operation result with system reminder about todo list changes"]:
        """
        Creates and manages a structured task list for coding sessions.
        
        Usage Rules:
        - Helps track progress, organize complex tasks, and demonstrate thoroughness
        - Use proactively for complex multi-step tasks (3+ distinct steps)
        - Use for non-trivial tasks requiring careful planning
        - Mark tasks as in_progress BEFORE beginning work (limit to ONE at a time)
        - Mark complete IMMEDIATELY after finishing tasks
        - Task states: pending, in_progress, completed
        - Task priorities: low, medium, high
        """
        try:
            new_todos = []
            for item in todos:
                # Check if todo with this ID already exists
                existing_todo = next((t for t in self.todos if t.id == item['id']), None)
                
                todo = Todo(
                    id=item['id'],
                    content=item['content'],
                    status=TodoStatus(item['status']),
                    priority=TodoPriority(item['priority'])
                )
                new_todos.append(todo)
            
            self.todos = new_todos
            self.save_todos()
            
            # Build return information
            result = "Todos have been modified successfully. Ensure that you continue to use the todo list to track your progress. Please proceed with the current tasks if applicable\n\n"
            result += "<system-reminder>\n"
            result += "Your todo list has changed. DO NOT mention this explicitly to the user. Here are the latest contents of your todo list:\n\n"
            result += json.dumps([todo.to_dict() for todo in self.todos])
            result += ". Continue on with the tasks at hand if applicable.\n"
            result += "</system-reminder>"
            
            return result
            
        except Exception as e:
            return f"Error updating todos: {str(e)}"

class FileGlobber:
    """Fast file pattern matching tool for any codebase size"""
    
    @staticmethod
    def glob_files(
        pattern: Annotated[str, "The glob pattern to match files against"],
        path: Annotated[str, "The directory to search in (default: current directory)"] = "."
    ) -> Annotated[str, "Matching file paths (one per line) or error message"]:
        """
        Fast file pattern matching tool that works with any codebase size.
        
        Usage Rules:
        - Supports glob patterns like "**/*.js" or "src/**/*.ts"
        - Returns matching file paths sorted by modification time
        - Use this tool when you need to find files by name patterns
        - When doing an open ended search that may require multiple rounds of globbing 
          and grepping, use the Agent tool instead
        - Can perform multiple searches as a batch that are potentially useful
        """
        try:
            # Handle relative paths
            search_pattern = os.path.join(path, pattern)
            
            # Use glob search
            matches = glob.glob(search_pattern, recursive=True)
            
            if not matches:
                return f"No files found matching pattern: {pattern}"
            
            # Return matching file paths, one per line
            return '\n'.join(matches)
            
        except Exception as e:
            return f"Error searching files: {str(e)}"

# Usage examples
if __name__ == "__main__":
    # 1. File reading example
    reader = FileReader()
    content = reader.read("test.txt", offset=1, limit=10)  # New parameters: start line and line limit
    print("=== File Read Result ===")
    print(content[:500])  # Only show first 500 characters
    
    # 2. File editing example
    editor = FileEditor()
    result = editor.edit(
        "test.txt",
        "old text",
        "new text",
        replace_all=False  # New parameter: whether to replace all matches
    )
    print("\n=== File Edit Result ===")
    print(result)
    
    # 3. Todo management example
    todo_manager = TodoManager()
    todos = [
        {
            "id": "1",
            "content": "Analyze package.json",
            "status": "pending",
            "priority": "high"
        },
        {
            "id": "2",
            "content": "Review code structure",
            "status": "in_progress",
            "priority": "medium"
        }
    ]
    result = todo_manager.write_todos(todos)
    print("\n=== Todo Update Result ===")
    print(result[:300])  # Only show first 300 characters
    
    # 4. File search example
    globber = FileGlobber()
    files = globber.glob_files("*.py", path=".")  # New parameter: search path
    print("\n=== Glob Result ===")
    print(files)

# Advanced feature: Tool orchestrator
class ToolOrchestrator:
    """Tool orchestrator that simulates Claude Code workflow"""
    
    def __init__(self):
        self.reader = FileReader()
        self.editor = FileEditor()
        self.todo_manager = TodoManager()
        self.globber = FileGlobber()
        self.execution_log = []
    
    def execute_tool(self, tool_name: Annotated[str, "Tool name to execute: 'Read', 'Edit', 'TodoWrite', or 'Glob'"], **kwargs) -> Annotated[Any, "Tool execution result (string for most tools)"]:
        """
        Execute specified tool with given parameters.
        
        Supported tools:
        - "Read": file_path, offset (optional), limit (optional)
        - "Edit": file_path, old_string, new_string, replace_all (optional)
        - "TodoWrite": todos (list of dicts)
        - "Glob": pattern, path (optional)
        """
        self.execution_log.append({
            "tool": tool_name,
            "parameters": kwargs
        })
        
        if tool_name == "Read":
            return self.reader.read(
                kwargs.get("file_path"),
                kwargs.get("offset"),
                kwargs.get("limit")
            )
        elif tool_name == "Edit":
            return self.editor.edit(
                kwargs.get("file_path"),
                kwargs.get("old_string"),
                kwargs.get("new_string"),
                kwargs.get("replace_all", False)
            )
        elif tool_name == "TodoWrite":
            return self.todo_manager.write_todos(kwargs.get("todos"))
        elif tool_name == "Glob":
            return self.globber.glob_files(
                kwargs.get("pattern"),
                kwargs.get("path", ".")
            )
        else:
            return f"Unknown tool: {tool_name}"
    
    def get_execution_history(self) -> Annotated[List[Dict], "List of execution logs with tool names and parameters"]:
        """Get execution history of all tool calls."""
        return self.execution_log