import os
import json
import subprocess
import glob
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Any, Annotated, Union
from dataclasses import dataclass, asdict
from enum import Enum
import base64
import requests
from urllib.parse import quote_plus

# ============================================================================
# Base Classes and Types
# ============================================================================

class FileEditTool:
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
        - Must read file with Read tool before editing
        - Preserve exact indentation as it appears in file
        - ALWAYS prefer editing existing files over creating new ones
        - Edit fails if old_string is not unique (unless replace_all=True)
        - Use replace_all for renaming variables across file
        """
        try:
            if not os.path.exists(file_path):
                return f"Error: File not found: {file_path}"
            
            if old_string == new_string:
                return "Error: old_string and new_string are identical"
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if old_string exists
            if old_string not in content:
                return f"Error: The string to replace was not found in {file_path}"
            
            # Check for multiple occurrences if not replace_all
            occurrences = content.count(old_string)
            if not replace_all and occurrences > 1:
                return f"Error: Found {occurrences} matches of the string to replace. Use replace_all=True or add more context to make it unique."
            
            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replacements_made = occurrences
            else:
                new_content = content.replace(old_string, new_string, 1)
                replacements_made = 1
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # Generate snippet around the modification
            lines = new_content.split('\n')
            for i, line in enumerate(lines):
                if new_string in line:
                    start = max(0, i - 3)
                    end = min(len(lines), i + 4)
                    
                    snippet_lines = []
                    for j in range(start, end):
                        snippet_lines.append(f"{j+1:6}|{lines[j]}")
                    
                    replacement_info = f" ({replacements_made} replacement{'s' if replacements_made > 1 else ''} made)" if replace_all else ""
                    result = f"The file {file_path} has been updated{replacement_info}. Here's the result:\n"
                    result += '\n'.join(snippet_lines)
                    return result
            
            replacement_info = f" ({replacements_made} replacement{'s' if replacements_made > 1 else ''} made)" if replace_all else ""
            return f"The file {file_path} has been updated successfully{replacement_info}."
            
        except Exception as e:
            return f"Error editing file: {str(e)}"
