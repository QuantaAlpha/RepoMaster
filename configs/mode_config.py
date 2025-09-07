#!/usr/bin/env python3
"""
RepoMaster Runtime Mode Configuration System

Supported runtime modes:
1. frontend: Frontend Streamlit interface mode (app_autogen_enhanced.py)
2. backend: Backend service mode, including four sub-modes:
   - unified: Unified general mode (includes all features, intelligent switching)
   - deepsearch: Deep search mode (deep_search_agent.py)
   - general_assistant: General programming assistant mode (run_general_code_assistant)
   - repository_agent: Repository task processing mode (run_repository_agent)

Usage:
    python launcher.py --mode frontend
    python launcher.py --mode backend --backend-mode unified
    python launcher.py --mode backend --backend-mode deepsearch
"""

import os
import argparse
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from .oai_config import get_llm_config
from src.utils.utils_config import random_string

@dataclass
class RunConfig:
    """Base configuration class for runtime"""
    mode: str
    work_dir: str = ""  # Will be set to absolute path in __post_init__
    log_level: str = "INFO"
    use_docker: bool = False
    timeout: int = 120
    
    def __post_init__(self):
        """Post-initialization processing, set absolute path"""
        import os
        if not self.work_dir or self.work_dir == "coding":
            # If work_dir is not specified or using default value, use absolute path with random subdirectory
            pwd = os.getcwd()
            self.work_dir = f"{pwd}/coding/{random_string()}"
        elif not os.path.isabs(self.work_dir):
            # If relative path is specified, convert to absolute path
            pwd = os.getcwd()
            self.work_dir = f"{pwd}/{self.work_dir}"
        # If already absolute path, keep unchanged

@dataclass
class FrontendConfig(RunConfig):
    """Frontend mode configuration"""
    mode: str = "frontend"
    streamlit_port: int = 8501
    streamlit_host: str = "localhost"
    file_watcher_type: str = "none"
    enable_auth: bool = True
    enable_file_browser: bool = True
    max_upload_size: int = 200  # MB

@dataclass
class BackendConfig(RunConfig):
    """Backend mode configuration"""
    mode: str = "backend"
    backend_mode: str = "deepsearch"  # deepsearch, general_assistant, repository_agent
    api_type: str = "basic"  # basic, azure_openai, openai, claude, deepseek
    temperature: float = 0.1
    max_tokens: int = 4000
    max_turns: int = 30

@dataclass
class DeepSearchConfig(BackendConfig):
    """Deep search mode configuration"""
    backend_mode: str = "deepsearch"
    enable_web_search: bool = True
    max_search_results: int = 10
    search_timeout: int = 30
    enable_code_tool: bool = True
    max_tool_messages: int = 2

@dataclass
class GeneralAssistantConfig(BackendConfig):
    """General programming assistant mode configuration"""
    backend_mode: str = "general_assistant"
    enable_venv: bool = True
    cleanup_venv: bool = False
    max_execution_time: int = 600
    supported_languages: list = field(default_factory=lambda: [
        'python', 'javascript', 'typescript', 'java', 'cpp', 'go'
    ])

@dataclass
class RepositoryAgentConfig(BackendConfig):
    """Repository task mode configuration"""
    backend_mode: str = "repository_agent"
    enable_repository_search: bool = True
    max_repo_size_mb: int = 100
    clone_timeout: int = 300
    enable_parallel_execution: bool = True
    retry_times: int = 3

@dataclass
class UnifiedConfig(BackendConfig):
    """Unified general mode configuration"""
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
    """Mode configuration manager"""
    
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
        """Create configuration object"""
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
        """Get LLM configuration"""
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
        """Get execution configuration"""
        if not self.config:
            raise ValueError("Configuration not initialized")
            
        return {
            "work_dir": self.config.work_dir,
            "use_docker": self.config.use_docker,
            "timeout": self.config.timeout
        }
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> 'ModeConfigManager':
        """Create configuration manager from command line arguments"""
        manager = cls()
        
        # Basic common parameters (supported by all configuration classes)
        base_params = ['work_dir', 'log_level', 'use_docker', 'timeout']
        
        # Frontend-specific parameters
        frontend_params = base_params + [
            'streamlit_port', 'streamlit_host', 'max_upload_size'
        ]
        
        # Backend-specific parameters  
        backend_params = base_params + [
            'api_type', 'temperature', 'max_tokens', 'max_turns'
        ]
        
        # Filter parameters based on mode
        if args.mode == 'frontend':
            allowed_params = frontend_params
        else:
            allowed_params = backend_params
        
        # Only pass allowed parameters
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
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="RepoMaster - AI-driven code repository analysis and task execution framework"
    )
    
    # Main mode selection
    parser.add_argument(
        '--mode', '-m',
        choices=['frontend', 'backend'],
        default='backend',
        help='Runtime mode (default: backend)'
    )
    
    # Backend mode sub-options
    parser.add_argument(
        '--backend-mode', '-b',
        choices=['unified', 'deepsearch', 'general_assistant', 'repository_agent'],
        default='unified',
        help='Backend mode type (default: unified)'
    )
    
    # General configuration
    parser.add_argument(
        '--work-dir', '-w',
        default='coding',
        help='Working directory (default: coding)'
    )
    
    parser.add_argument(
        '--api-type', '-a',
        choices=['basic', 'azure_openai', 'openai', 'claude', 'deepseek', 'basic_claude4', 'basic_deepseek_r1'],
        default='basic',
        help='API type (default: basic)'
    )
    
    parser.add_argument(
        '--temperature', '-t',
        type=float,
        default=0.1,
        help='Model temperature parameter (default: 0.1)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=120,
        help='Request timeout in seconds (default: 120)'
    )
    
    # Frontend mode specific parameters
    parser.add_argument(
        '--streamlit-port', '-p',
        type=int,
        default=8501,
        help='Streamlit port (default: 8501)'
    )
    
    parser.add_argument(
        '--streamlit-host',
        default='localhost',
        help='Streamlit host address (default: localhost)'
    )
    
    parser.add_argument(
        '--max-upload-size',
        type=int,
        default=200,
        help='Maximum file upload size in MB (default: 200)'
    )
    
    # Debug and logging
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Log level (default: INFO)'
    )
    
    parser.add_argument(
        '--use-docker',
        action='store_true',
        help='Use Docker to execute code'
    )
    
    # Advanced options
    parser.add_argument(
        '--max-turns',
        type=int,
        default=30,
        help='Maximum conversation turns (default: 30)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=4000,
        help='Maximum token count (default: 4000)'
    )
    
    # Configuration check options
    parser.add_argument(
        '--skip-config-check',
        action='store_true',
        help='Skip API configuration check (not recommended)'
    )
    
    return parser

def print_config_info(config: RunConfig):
    """Print configuration information - using beautiful format"""
    # Import the beautiful formatting function
    from src.frontend.terminal_show import print_launch_config
    print_launch_config(config)


def verify_config(
    config_manager: ModeConfigManager, 
    config_info: list,
    model: str
    ):
    """Verify if the configuration manager's config meets the required config_info"""
    if model in ['gpt-5']:
        if config_manager.config.temperature != 1.0:
            print(f"⚠️  Warning: {model} only support temperature=1.0. Resetting...")
            config_manager.config.temperature = 1.0

    return config_manager


if __name__ == "__main__":
    # Example usage
    parser = create_argument_parser()
    args = parser.parse_args()
    
    manager = ModeConfigManager.from_args(args)
    print_config_info(manager.config)
    
    # Print LLM configuration
    if hasattr(manager.config, 'api_type'):
        llm_config = manager.get_llm_config(manager.config.api_type)
        print(f"LLM Configuration: {llm_config}")
