#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python Package Error Extraction Tool

This script is used to extract package-related errors from Python execution results or log files,
and provide detailed error analysis and fix suggestions.

Usage:
1. Import as module:
   from package_error_extractor import PackageErrorExtractor
   extractor = PackageErrorExtractor()
   errors = extractor.extract_errors_from_text(error_text)

2. Run as script directly:
   python package_error_extractor.py
   
   This will run built-in test cases, demonstrating identification and analysis of various package errors.
"""

import re
import sys
import os
from typing import List, Dict, Tuple, Optional, Union
import json


class PackageErrorExtractor:
    """Python package error extractor class"""
    
    def __init__(self):
        """Initialize error patterns and classifications"""
        # Error pattern dictionary: {error_type: (regex_pattern, capture_group_description)}
        self.error_patterns = {
            "missing_package": (
                r"(?:ImportError|ModuleNotFoundError): No module named ['\"]([^'\"]+)['\"]",
                ["package_name"]
            ),
            "import_name_error": (
                r"(?:ImportError): cannot import name ['\"]([^'\"]+)['\"] from ['\"]([^'\"]+)['\"]",
                ["component_name", "package_name"]
            ),
            "attribute_error": (
                r"(?:AttributeError): module ['\"]([^'\"]+)['\"] has no attribute ['\"]([^'\"]+)['\"]",
                ["package_name", "attribute_name"]
            ),
            "version_conflict": (
                r"(?:.*?)requires ([^\s]+) ([^,]+), but ([^\s]+) is installed",
                ["package_name", "required_version", "installed_version"]
            ),
            "syntax_error_in_package": (
                r"(?:SyntaxError|IndentationError)(?:.*?)File ['\"](?:.*?)site-packages[/\\]([^/\\]+)[/\\](?:.*?)['\"], line (\d+)",
                ["package_name", "line_number"]
            ),
            "import_error_in_package": (
                r"(?:ImportError): (?:.*?)site-packages[/\\]([^/\\]+)[/\\](?:.*?): ([^\"'\n]+)",
                ["package_name", "error_details"]
            ),
            "dependency_error": (
                r"(?:.*?)([^\s]+) requires ([^\s]+), which is not installed",
                ["package_name", "dependency_name"]
            ),
            "dll_load_error": (
                r"(?:ImportError): DLL load failed while importing ([^:]+): ([^\"'\n]+)",
                ["module_name", "error_details"]
            ),
            "permission_error": (
                r"(?:PermissionError)(?:.*?)site-packages[/\\]([^/\\]+)[/\\]",
                ["package_name"]
            ),
            "pkg_resources_error": (
                r"(?:pkg_resources\.DistributionNotFound): The '([^']+)(?:[^']*?)' distribution was not found",
                ["package_name"]
            ),
            "incompatible_version": (
                r"(?:.*?)([^\s]+) ([^\s]+) is incompatible with ([^\s]+) ([^\s]+)",
                ["package1", "version1", "package2", "version2"]
            ),
        }
        
        # Fix suggestion dictionary
        self.fix_suggestions = {
            "missing_package": "Install the missing package using pip: pip install {package_name}",
            "import_name_error": "Check if package {package_name} version is correct. Component {component_name} may have been added in newer versions or doesn't exist in current version.",
            "attribute_error": "Check the documentation of package {package_name} to confirm if {attribute_name} exists or requires additional imports.",
            "version_conflict": "Install the required version of package: pip install {package_name}=={required_version} or use virtual environment to isolate dependencies.",
            "syntax_error_in_package": "Package {package_name} may be incompletely installed or corrupted. Try reinstalling: pip uninstall {package_name} && pip install {package_name}",
            "import_error_in_package": "Package {package_name} internal dependency issue: {error_details}. Check if its dependencies are completely installed.",
            "dependency_error": "Install the missing dependency: pip install {dependency_name}",
            "dll_load_error": "Module {module_name} failed to load DLL: {error_details}. May need to install system-level dependencies or VC++ runtime.",
            "permission_error": "Package {package_name} access permission issue. Try running with administrator/sudo privileges or check file permissions.",
            "pkg_resources_error": "Distribution package {package_name} not found. Try: pip install {package_name}",
            "incompatible_version": "Package version conflict: {package1} {version1} is incompatible with {package2} {version2}. Create virtual environment or adjust dependency versions.",
        }

    def extract_errors_from_text(self, text: str) -> List[Dict]:
        """Extract all package-related errors from text
        
        Args:
            text: Text containing error information
            
        Returns:
            List of error information, each item contains error type, match content and related details
        """
        results = []
        
        # Match each error pattern
        for error_type, (pattern, capture_groups) in self.error_patterns.items():
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
            
            for match in matches:
                error_info = {
                    "error_type": error_type,
                    "match_text": match.group(0),
                    "details": {}
                }
                
                # Extract capture group information
                for i, group_name in enumerate(capture_groups, 1):
                    if i <= len(match.groups()):
                        error_info["details"][group_name] = match.group(i)
                
                # Generate fix suggestion based on error type and details
                suggestion_template = self.fix_suggestions.get(error_type, "No fix suggestion available")
                try:
                    error_info["suggestion"] = suggestion_template.format(**error_info["details"])
                except KeyError:
                    error_info["suggestion"] = "Cannot generate fix suggestion, details incomplete"
                
                # Get error context (3 lines before and after)
                error_line_match = re.search(r'(?:.*\n){0,3}' + re.escape(match.group(0)) + r'(?:\n.*){0,3}', text)
                if error_line_match:
                    error_info["context"] = error_line_match.group(0)
                
                results.append(error_info)
        
        return results

    def extract_errors_from_file(self, file_path: str) -> List[Dict]:
        """Extract package-related errors from file
        
        Args:
            file_path: Error log file path
            
        Returns:
            List of error information
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.extract_errors_from_text(content)
        except UnicodeDecodeError:
            # Try other encodings
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                return self.extract_errors_from_text(content)
            except Exception as e:
                print(f"Error reading file: {e}")
                return []
        except Exception as e:
            print(f"Error processing file: {e}")
            return []

    def get_error_summary(self, errors: List[Dict]) -> Dict:
        """Generate error summary information
        
        Args:
            errors: List of error information
            
        Returns:
            Dictionary containing error summary
        """
        if not errors:
            return {"total_errors": 0, "error_types": {}}
        
        summary = {
            "total_errors": len(errors),
            "error_types": {},
            "affected_packages": set(),
        }
        
        for error in errors:
            error_type = error["error_type"]
            if error_type not in summary["error_types"]:
                summary["error_types"][error_type] = 0
            summary["error_types"][error_type] += 1
            
            # Collect affected packages
            for key, value in error["details"].items():
                if "package" in key or "module" in key:
                    # Extract base package name (remove submodules)
                    base_package = value.split('.')[0]
                    summary["affected_packages"].add(base_package)
        
        # Convert to list for JSON serialization
        summary["affected_packages"] = list(summary["affected_packages"])
        
        return summary

    def generate_fix_commands(self, errors: List[Dict]) -> Tuple[List[str], List[str]]:
        """Generate possible fix commands
        
        Args:
            errors: List of error information
            install_packages: List of packages that can be installed
            
        Returns:
            List of fix commands
        """
        fix_commands = []
        install_packages = []
        seen_packages = set()
        
        for error in errors:
            error_type = error["error_type"]
            details = error["details"]
            if error_type in ["missing_package", "version_conflict", "dependency_error", "pkg_resources_error", "syntax_error_in_package"]:
                install_packages.append(details["package_name"])
            if error_type == "missing_package" and "package_name" in details:
                package = details["package_name"]
                base_package = package.split('.')[0]  # Get base package name
                if base_package not in seen_packages:
                    fix_commands.append(f"pip install {base_package}")
                    seen_packages.add(base_package)
                    
            elif error_type == "dependency_error" and "dependency_name" in details:
                dependency = details["dependency_name"]
                if dependency not in seen_packages:
                    fix_commands.append(f"pip install {dependency}")
                    seen_packages.add(dependency)
                    
            elif error_type == "version_conflict" and all(k in details for k in ["package_name", "required_version"]):
                package = details["package_name"]
                version = details["required_version"]
                cmd = f"pip install {package}=={version}"
                if cmd not in fix_commands:
                    fix_commands.append(cmd)
                    
            elif error_type == "syntax_error_in_package" and "package_name" in details:
                package = details["package_name"]
                if package not in seen_packages:
                    fix_commands.append(f"pip uninstall -y {package} && pip install --no-cache-dir {package}")
                    seen_packages.add(package)
        
        # Add virtual environment suggestion
        if fix_commands:
            fix_commands.insert(0, "# Recommend installing dependencies in virtual environment to avoid version conflicts")
            fix_commands.insert(1, "python -m venv venv")
            fix_commands.insert(2, "# Windows: venv\\Scripts\\activate")
            fix_commands.insert(3, "# Linux/Mac: source venv/bin/activate")
            
        return fix_commands, install_packages

    def print_errors(self, errors: List[Dict]):
        """Print error information to console
        
        Args:
            errors: List of error information
        """
        if not errors:
            print("No package-related errors found.")
            return
            
        summary = self.get_error_summary(errors)
        fix_commands, install_packages = self.generate_fix_commands(errors)
        
        print("=" * 80)
        print("Python Package Error Analysis Report")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"- Found {summary['total_errors']} package-related errors")
        print(f"- Affected packages: {', '.join(summary['affected_packages'])}")
        print()
        print("Error type distribution:")
        
        for error_type, count in summary["error_types"].items():
            print(f"- {self._friendly_error_name(error_type)}: {count} errors")
        
        print()
        
        if fix_commands:
            print("Suggested fix commands:")
            print("-" * 40)
            for cmd in fix_commands:
                print(cmd)
            print("-" * 40)
            print()
        
        print("Detailed error information:")
        print()
        
        for i, error in enumerate(errors, 1):
            print(f"Error #{i}: {self._friendly_error_name(error['error_type'])}")
            print("-" * 40)
            
            # Error details
            print("Details:")
            for key, value in error["details"].items():
                print(f"  {key}: {value}")
            
            # Context
            if "context" in error:
                print("\nContext:")
                print(f"{error['context']}")
            
            # Fix suggestion
            print("\nFix suggestion:")
            print(f"{error['suggestion']}")
            
            print("\n" + "=" * 80 + "\n")

    def _friendly_error_name(self, error_type: str) -> str:
        """Convert error type to friendly description
        
        Args:
            error_type: Error type code
            
        Returns:
            Friendly description of error type
        """
        name_map = {
            "missing_package": "Missing Package",
            "import_name_error": "Import Name Error",
            "attribute_error": "Attribute Error",
            "version_conflict": "Version Conflict",
            "syntax_error_in_package": "Syntax Error in Package",
            "import_error_in_package": "Package Import Error",
            "dependency_error": "Dependency Error",
            "dll_load_error": "DLL Load Error",
            "permission_error": "Permission Error",
            "pkg_resources_error": "Resource Distribution Error",
            "incompatible_version": "Incompatible Version"
        }
        return name_map.get(error_type, error_type)


def main():
    """Main function: Run error extraction test cases"""
    print("Running Python package error extractor test cases...")
    
    from test_messages import test_cases
    
    extractor = PackageErrorExtractor()
    
    # Run all test cases
    for case_name, error_text in test_cases.items():
        print("\n" + "=" * 80)
        print(f"Test case: {case_name}")
        print("=" * 80)
        
        # Extract errors
        errors = extractor.extract_errors_from_text(error_text)
        
        # Print extracted errors
        extractor.print_errors(errors)
        
    # Combined test case
    print("\n" + "=" * 80)
    print("Combined test case: All errors")
    print("=" * 80)
    
    # Merge all test texts
    all_errors_text = "\n\n".join(test_cases.values())
    all_errors = extractor.extract_errors_from_text(all_errors_text)
    extractor.print_errors(all_errors)
    
    # Example: How to use this tool in actual code
    print("\n" + "=" * 80)
    print("Practical Application Example")
    print("=" * 80)
    print("Here's how to use this tool in your code:")
    print("""
# Example 1: Extract errors from log file
from package_error_extractor import PackageErrorExtractor

extractor = PackageErrorExtractor()
errors = extractor.extract_errors_from_file('error_log.txt')
extractor.print_errors(errors)

# Example 2: Extract directly from error text
error_text = '''
Traceback (most recent call last):
  File "example.py", line 10, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
'''
errors = extractor.extract_errors_from_text(error_text)
# Get extracted error details
for error in errors:
    print(f"Error type: {error['error_type']}")
    print(f"Details: {error['details']}")
    print(f"Fix suggestion: {error['suggestion']}")
    
# Example 3: Generate fix commands
fix_commands, install_packages = extractor.generate_fix_commands(errors)
for cmd in fix_commands:
    print(cmd)
""")


if __name__ == "__main__":
    main()