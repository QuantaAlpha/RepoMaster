#!/usr/bin/env python3
"""
RepoMaster Configuration Template

This module provides a centralized configuration management system for RepoMaster.
It supports multiple LLM providers and execution environments with proper error handling.

Usage:
    from configs.config_template import ConfigManager
    
    config_manager = ConfigManager()
    llm_config = config_manager.get_llm_config('openai')
    execution_config = config_manager.get_execution_config('workspace')
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LLMProvider:
    """Data class for LLM provider configuration"""
    name: str
    model: str
    api_key_env: str
    base_url: Optional[str] = None
    api_type: str = "openai"
    api_version: Optional[str] = None
    timeout: int = 120
    temperature: float = 0.1
    top_p: float = 0.95
    max_tokens: Optional[int] = None


@dataclass
class RepoMasterConfig:
    """Main configuration class for RepoMaster"""
    
    # LLM Providers
    llm_providers: Dict[str, LLMProvider] = field(default_factory=dict)
    
    # Default settings
    default_llm_provider: str = "openai"
    default_timeout: int = 120
    default_temperature: float = 0.1
    default_top_p: float = 0.95
    
    # Execution settings
    default_work_dir: str = "workspace"
    use_docker: bool = False
    max_execution_time: int = 7200  # 2 hours
    
    # Repository settings
    max_repo_size_mb: int = 100
    max_file_size_mb: int = 10
    supported_file_extensions: List[str] = field(default_factory=lambda: [
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php'
    ])
    
    # Search settings
    max_search_results: int = 10
    search_timeout: int = 30
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class ConfigManager:
    """Centralized configuration manager for RepoMaster"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the configuration manager
        
        Args:
            config_file: Optional path to custom config file
        """
        self.config = RepoMasterConfig()
        self._load_environment_variables()
        self._initialize_llm_providers()
        
        if config_file:
            self._load_config_file(config_file)
    
    def _load_environment_variables(self):
        """Load environment variables from .env file"""
        # Try to load from multiple locations
        env_paths = [
            os.path.join(os.getcwd(), ".env"),
            os.path.join(os.getcwd(), "configs", ".env"),
            os.path.join(os.path.dirname(__file__), ".env"),
        ]
        
        for env_path in env_paths:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                logger.info(f"Loaded environment variables from {env_path}")
                break
        else:
            logger.warning("No .env file found, using system environment variables only")
    
    def _initialize_llm_providers(self):
        """Initialize LLM provider configurations"""
        
        # OpenAI Configuration
        self.config.llm_providers["openai"] = LLMProvider(
            name="OpenAI",
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            api_key_env="OPENAI_API_KEY",
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        
        # Azure OpenAI Configuration
        self.config.llm_providers["azure_openai"] = LLMProvider(
            name="Azure OpenAI",
            model=os.getenv("AZURE_OPENAI_MODEL", "gpt-4o"),
            api_key_env="AZURE_OPENAI_API_KEY",
            base_url=os.getenv("AZURE_OPENAI_BASE_URL"),
            api_type="azure",
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        )
        
        # Anthropic Claude Configuration
        self.config.llm_providers["anthropic"] = LLMProvider(
            name="Anthropic Claude",
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key_env="ANTHROPIC_API_KEY",
            api_type="anthropic",
        )
        
        # DeepSeek Configuration
        self.config.llm_providers["deepseek"] = LLMProvider(
            name="DeepSeek",
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v3"),
            api_key_env="DEEPSEEK_API_KEY",
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        )
        
        # Google Gemini Configuration
        self.config.llm_providers["gemini"] = LLMProvider(
            name="Google Gemini",
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
            api_key_env="GEMINI_API_KEY",
            base_url=os.getenv("GEMINI_BASE_URL"),
        )
    
    def _load_config_file(self, config_file: str):
        """Load configuration from file (JSON/YAML)"""
        # TODO: Implement config file loading
        pass
    
    def get_llm_config(self, 
                      provider: str = None, 
                      timeout: int = None,
                      temperature: float = None,
                      top_p: float = None,
                      max_tokens: int = None) -> Dict[str, Any]:
        """
        Get LLM configuration for specified provider
        
        Args:
            provider: LLM provider name (openai, azure_openai, anthropic, etc.)
            timeout: Request timeout in seconds
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dictionary containing LLM configuration
            
        Raises:
            ValueError: If provider is not supported or API key is missing
        """
        if provider is None:
            provider = self.config.default_llm_provider
        
        if provider not in self.config.llm_providers:
            available_providers = list(self.config.llm_providers.keys())
            raise ValueError(f"Unsupported LLM provider '{provider}'. "
                           f"Available providers: {available_providers}")
        
        llm_provider = self.config.llm_providers[provider]
        
        # Check if API key is available
        api_key = os.getenv(llm_provider.api_key_env)
        if not api_key:
            raise ValueError(f"API key not found for {llm_provider.name}. "
                           f"Please set the {llm_provider.api_key_env} environment variable.")
        
        # Build configuration
        config = {
            "config_list": [{
                "model": llm_provider.model,
                "api_key": api_key,
                "api_type": llm_provider.api_type,
            }],
            "timeout": timeout or llm_provider.timeout or self.config.default_timeout,
            "temperature": temperature or llm_provider.temperature or self.config.default_temperature,
            "top_p": top_p or llm_provider.top_p or self.config.default_top_p,
        }
        
        # Add optional parameters
        if llm_provider.base_url:
            config["config_list"][0]["base_url"] = llm_provider.base_url
        
        if llm_provider.api_version:
            config["config_list"][0]["api_version"] = llm_provider.api_version
        
        if max_tokens or llm_provider.max_tokens:
            config["config_list"][0]["max_tokens"] = max_tokens or llm_provider.max_tokens
        
        return config
    
    def get_execution_config(self, work_dir: str = None, use_docker: bool = None) -> Dict[str, Any]:
        """
        Get code execution configuration
        
        Args:
            work_dir: Working directory for code execution
            use_docker: Whether to use Docker for execution
            
        Returns:
            Dictionary containing execution configuration
        """
        return {
            "work_dir": work_dir or self.config.default_work_dir,
            "use_docker": use_docker if use_docker is not None else self.config.use_docker,
            "timeout": self.config.max_execution_time,
            "last_n_messages": 1,
        }
    
    def get_tokenizer_config(self, model: str = None) -> Dict[str, Any]:
        """
        Get tokenizer configuration
        
        Args:
            model: Model name for tokenization
            
        Returns:
            Dictionary containing tokenizer configuration
        """
        return {
            "model": model or "gpt-4o",
            "chunk_token_size": 2000,
            "max_context_length": 128000,
        }
    
    def get_repository_config(self) -> Dict[str, Any]:
        """
        Get repository analysis configuration
        
        Returns:
            Dictionary containing repository configuration
        """
        return {
            "max_repo_size_mb": self.config.max_repo_size_mb,
            "max_file_size_mb": self.config.max_file_size_mb,
            "supported_extensions": self.config.supported_file_extensions,
        }
    
    def get_search_config(self) -> Dict[str, Any]:
        """
        Get search configuration
        
        Returns:
            Dictionary containing search configuration
        """
        return {
            "max_results": self.config.max_search_results,
            "timeout": self.config.search_timeout,
            "github_token": os.getenv("GITHUB_TOKEN"),
            "serper_api_key": os.getenv("SERPER_API_KEY"),
            "serpapi_api_key": os.getenv("SERPAPI_API_KEY"),
        }
    
    def validate_configuration(self) -> Dict[str, List[str]]:
        """
        Validate current configuration and return any issues
        
        Returns:
            Dictionary with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []
        
        # Check for at least one valid LLM provider
        valid_providers = []
        for provider_name, provider in self.config.llm_providers.items():
            if os.getenv(provider.api_key_env):
                valid_providers.append(provider_name)
            else:
                warnings.append(f"No API key found for {provider.name} ({provider.api_key_env})")
        
        if not valid_providers:
            errors.append("No valid LLM providers configured. Please set at least one API key.")
        
        # Check work directory
        work_dir = self.config.default_work_dir
        if not os.path.exists(work_dir):
            try:
                os.makedirs(work_dir, exist_ok=True)
                warnings.append(f"Created work directory: {work_dir}")
            except Exception as e:
                errors.append(f"Cannot create work directory {work_dir}: {e}")
        
        return {"errors": errors, "warnings": warnings}
    
    def get_available_providers(self) -> List[str]:
        """
        Get list of available LLM providers (with valid API keys)
        
        Returns:
            List of provider names with valid configurations
        """
        available = []
        for provider_name, provider in self.config.llm_providers.items():
            if os.getenv(provider.api_key_env):
                available.append(provider_name)
        return available


# Global configuration instance
config_manager = ConfigManager()


# Convenience functions for backward compatibility
def get_llm_config(provider: str = "openai", **kwargs) -> Dict[str, Any]:
    """Get LLM configuration (backward compatibility)"""
    return config_manager.get_llm_config(provider, **kwargs)


def get_execution_config(work_dir: str = "workspace", **kwargs) -> Dict[str, Any]:
    """Get execution configuration (backward compatibility)"""
    return config_manager.get_execution_config(work_dir, **kwargs)


def get_tokenizer_config(model: str = "gpt-4o") -> Dict[str, Any]:
    """Get tokenizer configuration (backward compatibility)"""
    return config_manager.get_tokenizer_config(model)


if __name__ == "__main__":
    # Configuration validation and testing
    validation_result = config_manager.validate_configuration()
    
    if validation_result["errors"]:
        print("❌ Configuration Errors:")
        for error in validation_result["errors"]:
            print(f"  - {error}")
    
    if validation_result["warnings"]:
        print("⚠️  Configuration Warnings:")
        for warning in validation_result["warnings"]:
            print(f"  - {warning}")
    
    available_providers = config_manager.get_available_providers()
    if available_providers:
        print(f"✅ Available LLM Providers: {', '.join(available_providers)}")
    else:
        print("❌ No LLM providers available")