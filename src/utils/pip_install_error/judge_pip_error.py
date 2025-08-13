import importlib.util
import requests
import os
import sys
from functools import lru_cache

@lru_cache(maxsize=128)
def is_pypi_package(package_name):
    """Check if package exists on PyPI"""
    try:
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False

def is_pip_installable(package_name):
    """
    Determine if a package can definitely be installed via pip
    
    Returns:
    - True: Definitely can be installed via pip
    - False: Cannot be installed via pip or uncertain
    """
    # Handle empty strings or relative imports
    if not package_name or package_name.startswith('.'):
        return False
    
    # Get base package name (remove submodules)
    base_package = package_name.split('.')[0]
    
    # Standard library doesn't need pip installation
    if base_package in sys.builtin_module_names:
        return False
    
    # Check if package is already installed and its location
    try:
        spec = importlib.util.find_spec(base_package)
        if spec is not None:
            # Already installed package, check if it's a third-party library
            if spec.origin and "site-packages" in spec.origin:
                # Although already installed, it is indeed pip-installable
                return True
            elif spec.origin and (os.getcwd() in spec.origin or os.path.abspath(os.path.dirname(".")) in spec.origin):
                # Local module, doesn't need pip installation
                return False
    except (ImportError, AttributeError, ValueError):
        pass
    
    # If not local, check PyPI
    if is_pypi_package(base_package):
        return True
    
    # Default return False (including uncertain cases)
    return False

def judge_pip_package(error_text):
    """
    Determine if error text is a pip installation error
    """
    from src.utils.pip_install_error.extract_pip_error import PackageErrorExtractor
    extractor = PackageErrorExtractor()
    
    errors = extractor.extract_errors_from_text(error_text)
    
    fix_commands, install_packages = extractor.generate_fix_commands(errors)
    output_packages = []
    for package in install_packages:
        if is_pip_installable(package):
            output_packages.append(package)
    return output_packages

def main():
    from test_messages import test_cases
    
    for case_name, error_text in test_cases.items():
        print(f"Test case: {case_name}")
        print(f"Error text: {error_text}")
        print(f"Is pip installation error: {judge_pip_package(error_text)}")
        print("-"*100)

if __name__ == "__main__":
    main()
