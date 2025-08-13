"""
File monitoring utilities for tracking file changes during code execution.
Provides functions to monitor directory changes and display new files in a structured format.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def should_ignore_path(path: Path) -> bool:
    """Check if a file or directory path should be ignored.
    
    Args:
        path: Path to check
        
    Returns:
        True if the path should be ignored, False otherwise
    """
    # Ignored directory names
    ignored_dirs = ['__pycache__', '.git', '.svn', '.hg', 'node_modules', '.venv', 'venv', '.env', 'env', '.pytest_cache', '.mypy_cache', '.tox', 'dist', 'build', 'egg-info', '.eggs', '.idea', '.vscode', '.DS_Store']
    
    # Ignored file extensions
    ignored_extensions = ['.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib', '.log', '.tmp', '.bak', '.swp', '.DS_Store']
    
    # Check if it's an ignored directory
    for part in path.parts:
        if part in ignored_dirs:
            return True
    
    # Check file extension
    if path.suffix.lower() in ignored_extensions:
        return True
    
    # Check hidden files (files starting with ., but not including . and .. from relative paths)
    if path.name.startswith('.') and path.name not in {'.', '..'}:
        return True
    
    return False


def get_file_info_with_time(file_path: Path) -> Optional[Dict]:
    """Get file information including creation time and size.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary containing file info or None if file doesn't exist
    """
    try:
        stat = file_path.stat()
        return {
            "path": file_path,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "ctime": stat.st_ctime,
        }
    except (OSError, FileNotFoundError):
        return None


def get_directory_files(directory: Path) -> Dict[str, Dict]:
    """Recursively get information about all files in a directory.
    
    Args:
        directory: Path to the directory to scan
        
    Returns:
        Dictionary mapping file paths to file information
    """
    files_info = {}
    if not directory.exists():
        return files_info
    
    try:
        for item in directory.rglob("*"):
            # Ignore unwanted files and directories
            if should_ignore_path(item):
                continue
                
            if item.is_file():
                info = get_file_info_with_time(item)
                if info:
                    files_info[str(item)] = info
    except (OSError, PermissionError):
        pass
    
    return files_info


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 KB", "2.3 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def display_new_files_tree(new_files: List[Path], base_path: Path, max_depth: int = 3) -> str:
    """Display new files in a tree structure format.
    
    Args:
        new_files: List of new file paths
        base_path: Base directory path for relative path calculation
        max_depth: Maximum depth to show in the tree
        
    Returns:
        Formatted tree structure string
    """
    if not new_files:
        return "No new files found"
    
    # Organize files by relative path
    file_tree = {}
    for file_path in new_files:
        try:
            rel_path = file_path.relative_to(base_path)
            parts = rel_path.parts
            
            current = file_tree
            for part in parts[:-1]:  # Directory parts
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # File part
            filename = parts[-1]
            stat = file_path.stat()
            current[filename] = {
                "is_file": True,
                "size": stat.st_size,
                "ctime": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            }
        except (ValueError, OSError):
            continue
    
    def format_tree(tree_dict: Dict, depth: int = 0, prefix: str = "") -> List[str]:
        """Recursively format tree structure."""
        lines = []
        items = sorted(tree_dict.items())
        
        # Limit displayed items based on depth
        if depth == 0:
            max_items = 15
        elif depth == 1:
            max_items = 10
        elif depth == 2:
            max_items = 8
        else:
            max_items = 6
            
        displayed_items = items[:max_items]
        
        for i, (name, content) in enumerate(displayed_items):
            is_last = i == len(displayed_items) - 1
            current_prefix = "└── " if is_last else "├── "
            
            if isinstance(content, dict) and content.get("is_file"):
                # This is a file
                size_str = format_file_size(content["size"])
                time_str = content["ctime"]
                lines.append(f"{prefix}{current_prefix}{name} ({size_str}, created: {time_str})")
            else:
                # This is a directory
                lines.append(f"{prefix}{current_prefix}{name}/")
                if depth < max_depth and content:
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    lines.extend(format_tree(content, depth + 1, next_prefix))
        
        # Add ellipsis for hidden items
        if len(items) > max_items:
            remaining = len(items) - max_items
            lines.append(f"{prefix}... and {remaining} more items")
        
        return lines
    
    result_lines = [f"New files generated (total: {len(new_files)}):"]
    result_lines.extend(format_tree(file_tree))
    
    return "\n".join(result_lines)


def compare_and_display_new_files(before_files: Dict[str, Dict], after_files: Dict[str, Dict], work_dir: Path) -> str:
    """Compare file changes and display new files.
    
    Args:
        before_files: File information before execution
        after_files: File information after execution
        work_dir: Working directory path
        
    Returns:
        Formatted string showing new files
    """
    # Find new files and filter out ignored ones
    new_file_paths = []
    for file_path, info in after_files.items():
        if file_path not in before_files:
            path_obj = Path(file_path)
            # Apply filtering logic, ignore unwanted files
            if not should_ignore_path(path_obj):
                new_file_paths.append(path_obj)
    
    if not new_file_paths:
        return "No new files generated during execution"
    
    # For few files, use simple list display
    if len(new_file_paths) <= 5:
        lines = [f"New files generated (total: {len(new_file_paths)}):"]
        for file_path in sorted(new_file_paths):
            try:
                rel_path = file_path.relative_to(work_dir)
                stat = file_path.stat()
                size_str = format_file_size(stat.st_size)
                time_str = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"  - {rel_path} ({size_str}, created: {time_str})")
            except (ValueError, OSError):
                lines.append(f"  - {file_path} (unable to get info)")
        return "\n".join(lines)
    else:
        # For many files, use tree structure display
        return display_new_files_tree(new_file_paths, work_dir)


def monitor_directory_changes(directory: Path, operation_func, *args, **kwargs):
    """Monitor directory changes during a function execution.
    
    Args:
        directory: Directory to monitor
        operation_func: Function to execute
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        Tuple of (function_result, file_changes_info)
    """
    before_files = get_directory_files(directory)
    
    try:
        result = operation_func(*args, **kwargs)
    except Exception as e:
        result = f"Error during execution: {str(e)}"
    
    after_files = get_directory_files(directory)
    changes_info = compare_and_display_new_files(before_files, after_files, directory)
    print(f"File changes:\n{changes_info}", flush=True)
    return result, changes_info


# Test cases
def test_file_monitor():
    """Test cases for file monitoring functionality."""
    
    def test_format_file_size():
        """Test file size formatting."""
        print("Testing format_file_size...")
        assert format_file_size(0) == "0 B"
        assert format_file_size(512) == "512.0 B"
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(1073741824) == "1.0 GB"
        print("✓ format_file_size tests passed")
    
    def test_get_file_info():
        """Test file info retrieval."""
        print("Testing get_file_info_with_time...")
        
        # Test with existing file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = Path(tmp.name)
        
        info = get_file_info_with_time(tmp_path)
        assert info is not None
        assert "size" in info
        assert "mtime" in info
        assert "ctime" in info
        assert info["size"] == 12  # "test content" is 12 bytes
        
        # Test with non-existing file
        non_existing = Path("/non/existing/file.txt")
        info = get_file_info_with_time(non_existing)
        assert info is None
        
        # Cleanup
        tmp_path.unlink()
        print("✓ get_file_info_with_time tests passed")
    
    def test_directory_monitoring():
        """Test directory monitoring functionality."""
        print("Testing directory monitoring...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create initial file
            initial_file = temp_path / "initial.txt"
            initial_file.write_text("initial content")
            
            def create_files():
                """Function that creates new files."""
                (temp_path / "new_file1.txt").write_text("content 1")
                (temp_path / "new_file2.txt").write_text("content 2")
                (temp_path / "subdir").mkdir()
                (temp_path / "subdir" / "nested.txt").write_text("nested content")
                return "Files created successfully"
            
            result, changes = monitor_directory_changes(temp_path, create_files)
            assert result == "Files created successfully"
            assert "new_file1.txt" in changes
            assert "new_file2.txt" in changes
            assert "nested.txt" in changes
            assert "total: 3" in changes
        
        # Test multi-level directory creation
        print("Testing multi-level directory monitoring...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create some initial files
            (temp_path / "existing.txt").write_text("existing file")
            
            def create_complex_structure():
                """Function that creates complex multi-level directory structure."""
                # Level 1 directories
                (temp_path / "src").mkdir()
                (temp_path / "data").mkdir()
                (temp_path / "outputs").mkdir()
                
                # Level 2 directories and files
                (temp_path / "src" / "utils").mkdir()
                (temp_path / "src" / "models").mkdir()
                (temp_path / "src" / "__init__.py").write_text("")
                (temp_path / "src" / "main.py").write_text("print('Hello, World!')")
                
                # Level 3 directories and files
                (temp_path / "src" / "utils" / "preprocessing").mkdir()
                (temp_path / "src" / "utils" / "helpers.py").write_text("def helper_function():\n    pass")
                (temp_path / "src" / "models" / "neural_net").mkdir()
                for i in range(10):
                    (temp_path / "src" / "models" / f"model_{i}.py").write_text(f"class Model_{i}:\n    pass")
                (temp_path / "src" / "models" / "base_model.py").write_text("class BaseModel:\n    pass")
                
                # Level 4 directories and files
                (temp_path / "src" / "utils" / "preprocessing" / "clean_data.py").write_text("def clean_data():\n    pass")
                (temp_path / "src" / "models" / "neural_net" / "layers").mkdir()
                (temp_path / "src" / "models" / "neural_net" / "network.py").write_text("import torch")
                
                # Level 5 files
                (temp_path / "src" / "models" / "neural_net" / "layers" / "dense.py").write_text("class DenseLayer:\n    pass")
                (temp_path / "src" / "models" / "neural_net" / "layers" / "activation.py").write_text("import torch.nn as nn")
                
                # Data directory structure
                (temp_path / "data" / "raw").mkdir()
                (temp_path / "data" / "processed").mkdir()
                (temp_path / "data" / "raw" / "train.csv").write_text("id,feature1,feature2,label\n1,0.5,0.3,1")
                (temp_path / "data" / "processed" / "train_processed.csv").write_text("feature1,feature2,label\n0.5,0.3,1")
                
                # Outputs directory with multiple subdirectories
                (temp_path / "outputs" / "experiments").mkdir()
                (temp_path / "outputs" / "logs").mkdir()
                (temp_path / "outputs" / "checkpoints").mkdir()
                (temp_path / "outputs" / "experiments" / "exp_001").mkdir()
                (temp_path / "outputs" / "experiments" / "exp_001" / "config.json").write_text('{"lr": 0.001}')
                (temp_path / "outputs" / "logs" / "training.log").write_text("Training started...")
                (temp_path / "outputs" / "checkpoints" / "model_v1.bin").write_text("fake model weights")
                
                return "Complex multi-level structure created successfully"
            
            result, changes = monitor_directory_changes(temp_path, create_complex_structure)
            
            assert result == "Complex multi-level structure created successfully"
            # Check for presence of files at different levels
            assert "main.py" in changes
            assert "helpers.py" in changes
            assert "clean_data.py" in changes
            
            # Should show tree structure for many files (>5)
            assert "├──" in changes or "└──" in changes
            assert "total:" in changes
        
        print("✓ directory monitoring tests (including multi-level) passed")
    
    def test_empty_directory():
        """Test with empty directory."""
        print("Testing empty directory...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            before_files = get_directory_files(temp_path)
            after_files = get_directory_files(temp_path)
            
            result = compare_and_display_new_files(before_files, after_files, temp_path)
            assert result == "No new files generated during execution"
        
        print("✓ empty directory tests passed")
    
    def test_tree_display():
        """Test tree structure display."""
        print("Testing tree display...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create multiple files in different directories
            files_to_create = [
                "file1.txt",
                "file2.txt", 
                "dir1/file3.txt",
                "dir1/file4.txt",
                "dir1/subdir/file5.txt",
                "dir2/file6.txt"
            ]
            
            new_files = []
            for file_rel in files_to_create:
                file_path = temp_path / file_rel
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(f"content of {file_rel}")
                new_files.append(file_path)
            
            tree_display = display_new_files_tree(new_files, temp_path)
            
            assert "New files generated (total: 6)" in tree_display
            assert "file1.txt" in tree_display
            assert "dir1/" in tree_display
            assert "├──" in tree_display or "└──" in tree_display
        
        print("✓ tree display tests passed")
    
    # Run all tests
    test_format_file_size()
    test_get_file_info()
    test_directory_monitoring()
    test_empty_directory()
    test_tree_display()
    
    print("\n🎉 All file monitor tests passed!")


if __name__ == "__main__":
    test_file_monitor() 