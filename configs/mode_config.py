#!/usr/bin/env python3
"""
RepoMaster运行模式配置系统

支持的运行模式：
1. frontend: 前端Streamlit界面模式 (app_autogen_enhanced.py)
2. backend: 后台服务模式，包含四个子模式：
   - unified: 统一通用模式 (包含所有功能，智能切换)
   - deepsearch: 深度搜索模式 (deep_search_agent.py)
   - general_assistant: 通用编程助手模式 (run_general_code_assistant)
   - repository_agent: 仓库任务处理模式 (run_repository_agent)

使用方法：
    python launcher.py --mode frontend
    python launcher.py --mode backend --backend-mode unified
    python launcher.py --mode backend --backend-mode deepsearch
"""

import os
import argparse
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from .oai_config import get_llm_config

@dataclass
class RunConfig:
    """运行配置基类"""
    mode: str
    work_dir: str = ""  # 将在__post_init__中设置为绝对路径
    log_level: str = "INFO"
    use_docker: bool = False
    timeout: int = 120
    
    def __post_init__(self):
        """后初始化处理，设置绝对路径"""
        import os
        if not self.work_dir or self.work_dir == "coding":
            # 如果没有指定work_dir或使用默认值，则使用绝对路径
            pwd = os.getcwd()
            self.work_dir = f"{pwd}/coding"
        elif not os.path.isabs(self.work_dir):
            # 如果指定了相对路径，转换为绝对路径
            pwd = os.getcwd()
            self.work_dir = f"{pwd}/{self.work_dir}"
        # 如果已经是绝对路径，则保持不变

@dataclass
class FrontendConfig(RunConfig):
    """前端模式配置"""
    mode: str = "frontend"
    streamlit_port: int = 8501
    streamlit_host: str = "localhost"
    file_watcher_type: str = "none"
    enable_auth: bool = True
    enable_file_browser: bool = True
    max_upload_size: int = 200  # MB

@dataclass
class BackendConfig(RunConfig):
    """后台模式配置"""
    mode: str = "backend"
    backend_mode: str = "deepsearch"  # deepsearch, general_assistant, repository_agent
    api_type: str = "basic"  # basic, azure_openai, openai, claude, deepseek
    temperature: float = 0.1
    max_tokens: int = 4000
    max_turns: int = 30

@dataclass
class DeepSearchConfig(BackendConfig):
    """深度搜索模式配置"""
    backend_mode: str = "deepsearch"
    enable_web_search: bool = True
    max_search_results: int = 10
    search_timeout: int = 30
    enable_code_tool: bool = True
    max_tool_messages: int = 2

@dataclass
class GeneralAssistantConfig(BackendConfig):
    """通用编程助手模式配置"""
    backend_mode: str = "general_assistant"
    enable_venv: bool = True
    cleanup_venv: bool = False
    max_execution_time: int = 600
    supported_languages: list = field(default_factory=lambda: [
        'python', 'javascript', 'typescript', 'java', 'cpp', 'go'
    ])

@dataclass
class RepositoryAgentConfig(BackendConfig):
    """仓库任务模式配置"""
    backend_mode: str = "repository_agent"
    enable_repository_search: bool = True
    max_repo_size_mb: int = 100
    clone_timeout: int = 300
    enable_parallel_execution: bool = True
    retry_times: int = 3

@dataclass
class UnifiedConfig(BackendConfig):
    """统一通用模式配置"""
    backend_mode: str = "unified"
    enable_web_search: bool = True
    enable_repository_search: bool = True
    enable_venv: bool = True
    cleanup_venv: bool = False
    max_search_results: int = 10
    search_timeout: int = 30
    max_execution_time: int = 600
    max_repo_size_mb: int = 100
    clone_timeout: int = 300
    retry_times: int = 3
    supported_languages: list = field(default_factory=lambda: [
        'python', 'javascript', 'typescript', 'java', 'cpp', 'go'
    ])

class ModeConfigManager:
    """模式配置管理器"""
    
    SUPPORTED_MODES = {
        'frontend': FrontendConfig,
        'backend': {
            'unified': UnifiedConfig,
            'deepsearch': DeepSearchConfig,
            'general_assistant': GeneralAssistantConfig,
            'repository_agent': RepositoryAgentConfig
        }
    }
    
    def __init__(self):
        self.config = None
        
    def create_config(self, mode: str, backend_mode: str = None, **kwargs) -> RunConfig:
        """创建配置对象"""
        if mode == 'frontend':
            self.config = self.SUPPORTED_MODES['frontend'](**kwargs)
        elif mode == 'backend':
            if backend_mode not in self.SUPPORTED_MODES['backend']:
                raise ValueError(f"Unsupported backend mode: {backend_mode}")
            backend_config_class = self.SUPPORTED_MODES['backend'][backend_mode]
            self.config = backend_config_class(backend_mode=backend_mode, **kwargs)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
            
        return self.config
    
    def get_llm_config(self, api_type: str = 'basic') -> Dict[str, Any]:
        """获取LLM配置"""
        if hasattr(self.config, 'temperature'):
            temperature = self.config.temperature
        else:
            temperature = 0.1
            
        return get_llm_config(
            api_type=api_type,
            temperature=temperature,
            timeout=self.config.timeout if self.config else 120
        )
    
    def get_execution_config(self) -> Dict[str, Any]:
        """获取执行配置"""
        if not self.config:
            raise ValueError("Configuration not initialized")
            
        return {
            "work_dir": self.config.work_dir,
            "use_docker": self.config.use_docker,
            "timeout": self.config.timeout
        }
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'ModeConfigManager':
        """从命令行参数创建配置管理器"""
        manager = cls()
        
        # 基础通用参数（所有配置类都支持）
        base_params = ['work_dir', 'log_level', 'use_docker', 'timeout']
        
        # 前端特定参数
        frontend_params = base_params + [
            'streamlit_port', 'streamlit_host'
        ]
        
        # 后台特定参数  
        backend_params = base_params + [
            'api_type', 'temperature', 'max_tokens', 'max_turns'
        ]
        
        # 根据模式过滤参数
        if args.mode == 'frontend':
            allowed_params = frontend_params
        else:
            allowed_params = backend_params
        
        # 只传递允许的参数
        config_kwargs = {
            k: v for k, v in vars(args).items() 
            if v is not None and k not in ['mode', 'backend_mode'] and k in allowed_params
        }
        
        manager.create_config(
            mode=args.mode,
            backend_mode=getattr(args, 'backend_mode', None),
            **config_kwargs
        )
        
        return manager

def create_argument_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="RepoMaster - AI驱动的代码仓库分析和任务执行框架"
    )
    
    # 主要模式选择
    parser.add_argument(
        '--mode', '-m',
        choices=['frontend', 'backend'],
        default='frontend',
        help='运行模式 (默认: frontend)'
    )
    
    # 后台模式子选项
    parser.add_argument(
        '--backend-mode', '-b',
        choices=['unified', 'deepsearch', 'general_assistant', 'repository_agent'],
        default='deepsearch',
        help='后台模式类型 (默认: deepsearch)'
    )
    
    # 通用配置
    parser.add_argument(
        '--work-dir', '-w',
        default='coding',
        help='工作目录 (默认: coding)'
    )
    
    parser.add_argument(
        '--api-type', '-a',
        choices=['basic', 'azure_openai', 'openai', 'claude', 'deepseek', 'basic_claude4', 'basic_deepseek_r1'],
        default='basic',
        help='API类型 (默认: basic)'
    )
    
    parser.add_argument(
        '--temperature', '-t',
        type=float,
        default=0.1,
        help='模型温度参数 (默认: 0.1)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=120,
        help='请求超时时间(秒) (默认: 120)'
    )
    
    # 前端模式特定参数
    parser.add_argument(
        '--streamlit-port', '-p',
        type=int,
        default=8501,
        help='Streamlit端口 (默认: 8501)'
    )
    
    parser.add_argument(
        '--streamlit-host',
        default='localhost',
        help='Streamlit主机地址 (默认: localhost)'
    )
    
    # 调试和日志
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别 (默认: INFO)'
    )
    
    parser.add_argument(
        '--use-docker',
        action='store_true',
        help='使用Docker执行代码'
    )
    
    # 高级选项
    parser.add_argument(
        '--max-turns',
        type=int,
        default=30,
        help='最大对话轮数 (默认: 30)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=4000,
        help='最大token数量 (默认: 4000)'
    )
    
    # 配置检查选项
    parser.add_argument(
        '--skip-config-check',
        action='store_true',
        help='跳过API配置检查 (不推荐)'
    )
    
    return parser

def print_config_info(config: RunConfig):
    """打印配置信息 - 使用美观格式"""
    # Import the beautiful formatting function
    from src.frontend.terminal_show import print_launch_config
    print_launch_config(config)

if __name__ == "__main__":
    # 示例用法
    parser = create_argument_parser()
    args = parser.parse_args()
    
    manager = ModeConfigManager.from_args(args)
    print_config_info(manager.config)
    
    # 打印LLM配置
    if hasattr(manager.config, 'api_type'):
        llm_config = manager.get_llm_config(manager.config.api_type)
        print(f"LLM配置: {llm_config}")
