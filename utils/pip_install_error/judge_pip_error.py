import importlib.util
import requests
import os
import sys
from functools import lru_cache

@lru_cache(maxsize=128)
def is_pypi_package(package_name):
    """检查包是否存在于 PyPI 上"""
    try:
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False

def is_pip_installable(package_name):
    """
    判断包是否确定可以通过 pip 安装
    
    返回:
    - True: 确定可以通过 pip 安装
    - False: 不能通过 pip 安装或无法确定
    """
    # 处理空字符串或相对导入
    if not package_name or package_name.startswith('.'):
        return False
    
    # 获取基础包名（去除子模块）
    base_package = package_name.split('.')[0]
    
    # 标准库不需要 pip 安装
    if base_package in sys.builtin_module_names:
        return False
    
    # 检查包是否已安装及其位置
    try:
        spec = importlib.util.find_spec(base_package)
        if spec is not None:
            # 已安装的包，检查它是否是第三方库
            if spec.origin and "site-packages" in spec.origin:
                # 虽然已安装，但确实是可 pip 安装的包
                return True
            elif spec.origin and (os.getcwd() in spec.origin or os.path.abspath(os.path.dirname(".")) in spec.origin):
                # 本地模块，不需要 pip 安装
                return False
    except (ImportError, AttributeError, ValueError):
        pass
    
    # 如果不在本地，检查 PyPI
    if is_pypi_package(base_package):
        return True
    
    # 默认返回 False（包括无法确定的情况）
    return False

def judge_pip_package(error_text):
    """
    判断错误文本是否是pip安装错误
    """
    from utils.pip_install_error.extract_pip_error import PackageErrorExtractor
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
        print(f"测试用例: {case_name}")
        print(f"错误文本: {error_text}")
        print(f"是否是pip安装错误: {judge_pip_package(error_text)}")
        print("-"*100)

if __name__ == "__main__":
    main()
