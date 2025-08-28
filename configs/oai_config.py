import os
import warnings

# Default provider priority order
DEFAULT_PROVIDER_PRIORITY = [
    'openai',
    'claude', 
    'deepseek',
    'basic',
    'azure_openai'
]

def get_api_config():
    return {
        'openai': {
            "config_list": [{
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
                "api_key": os.environ.get("OPENAI_API_KEY"),
                "base_url": os.environ.get("OPENAI_BASE_URL")
            }]
        },
        'claude': {
            "config_list": [{
                "model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                "api_key": os.environ.get("ANTHROPIC_API_KEY"),
                "base_url": os.environ.get("ANTHROPIC_BASE_URL")
            }]
        },
        'deepseek': {
            "config_list": [{
                "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-v3"),
                "api_key": os.environ.get("DEEPSEEK_API_KEY"),
                "base_url": os.environ.get("DEEPSEEK_BASE_URL")
            }]
        },
        'basic': {
            "config_list": [{
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
                "api_key": os.environ.get("OPENAI_API_KEY"),
                "base_url": os.environ.get("OPENAI_BASE_URL")
            }]
        },
        'azure_openai': {
            "config_list": [{
                "model": os.environ.get("AZURE_OPENAI_MODEL", "gpt-4o"),
                "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
                "base_url": os.environ.get("AZURE_OPENAI_BASE_URL"),
                "api_type": "azure",
                "api_version": "2024-02-15-preview"
            }]
        },
        'basic_deepseek_r1': {
            "config_list": [{
                "model": "deepseek-r1-0528",
                "api_key": os.environ.get("DEEPSEEK_API_KEY"),
                "base_url": os.environ.get("DEEPSEEK_BASE_URL"),
            }],
        },
        'basic_claude4': {
            "config_list": [{
                "model": "claude-sonnet-4-20250514",
                "api_key": os.environ.get("CLAUDE_API_KEY"),
                "base_url": os.environ.get("CLAUDE_BASE_URL"),
            }],
        }
    }

service_config = {
    "summary": get_api_config()["basic"],
    "deepsearch": get_api_config()["basic"],
    "code_explore": get_api_config()["basic"],
}


def get_default_provider():
    """Get the default API provider from environment variable or use the first in priority list."""
    return os.environ.get('DEFAULT_API_PROVIDER', DEFAULT_PROVIDER_PRIORITY[0])

def get_provider_by_priority():
    """Get the first available provider based on priority order."""
    # First try the default provider
    default_provider = get_default_provider()
    api_configs = get_api_config()
    
    if default_provider in api_configs:
        config = api_configs[default_provider]
        config_list = config.get("config_list", [])
        if config_list:
            api_key = config_list[0].get("api_key")
            if api_key and api_key.strip():
                return default_provider, config
    
    # If default provider is not available, try others in priority order
    for provider in DEFAULT_PROVIDER_PRIORITY:
        if provider == default_provider:
            continue  # Already tried
            
        if provider in api_configs:
            config = api_configs[provider]
            config_list = config.get("config_list", [])
            if config_list:
                api_key = config_list[0].get("api_key")
                if api_key and api_key.strip():
                    return provider, config
    
    raise ValueError("No valid API provider found. Please configure at least one API key.")

def validate_and_get_fallback_config(api_type: str = None, service_type: str = ''):
    """
    Validate API key and provide fallback configuration if needed.
    
    Args:
        api_type: Type of API configuration to validate. If None, uses provider priority.
        service_type: Specific service type configuration
        
    Returns:
        tuple: (config_name, api_config) - the actual config name used and its data
        
    Raises:
        ValueError: If no valid API key is found in any configuration
    """
    # If no api_type specified, use provider priority
    if api_type is None:
        provider, config = get_provider_by_priority()
        print(f"✅ Using API provider '{provider}' with valid configuration")
        return provider, config
    
    # Original logic for specific api_type
    if api_type not in get_api_config():
        raise ValueError(f"API type '{api_type}' not found in configuration")
    
    api_config = get_api_config()[api_type]
    if service_type and service_type in service_config:
        api_config = service_config[service_type]
        config_source = f"service:{service_type}"
    else:
        config_source = api_type
    
    # Check if the requested configuration has a valid API key
    config_list = api_config.get("config_list", [])
    if not config_list:
        raise ValueError(f"No config_list found for API type '{api_type}'")
    
    primary_config = config_list[0]
    primary_api_key = primary_config.get("api_key")
    
    # Check if primary API key is None or empty
    if not primary_api_key or primary_api_key.strip() == "":
        warnings.warn(f"⚠️  API key for '{config_source}' is None or empty. Using provider priority fallback...")
        
        # Use provider priority fallback
        try:
            provider, config = get_provider_by_priority()
            warnings.warn(f"✅ Using fallback provider '{provider}' with valid configuration")
            return provider, config
        except ValueError:
            raise ValueError(
                f"❌ No valid API key found in any configuration. "
                f"Please set up at least one valid API key in environment variables."
            )
    else:
        # print(f"✅  '{config_source}' with valid API key.")
        return config_source, api_config


def get_llm_config(api_type: str = None, timeout: int = 240, temperature: float = 0.1, top_p=0.95, service_type: str = '', validate_api_key: bool = True):
    """
    Get LLM configuration with provider priority support.
    
    Args:
        api_type: Type of API configuration to use. If None, uses provider priority.
        timeout: Request timeout in seconds
        temperature: Model temperature parameter
        top_p: Model top_p parameter
        service_type: Specific service type configuration
        validate_api_key: Whether to validate API key and use fallback if needed
        
    Returns:
        dict: LLM configuration
        
    Raises:
        ValueError: If validate_api_key=True and no valid API key is found
    """
    if validate_api_key or api_type is None:
        # Use validation and fallback functionality
        config_name, api_config = validate_and_get_fallback_config(api_type, service_type)
        api_config = api_config.copy()  # Make a copy to avoid modifying original
    else:
        # Original behavior - no validation
        api_config = get_api_config()[api_type]
        if service_type and service_type in service_config:
            api_config = service_config[service_type]
    
    # Add runtime parameters
    api_config["timeout"] = timeout
    api_config["temperature"] = temperature
    api_config["top_p"] = top_p
    
    return api_config

def load_envs_func():
    pwd = os.getcwd()
    from dotenv import load_dotenv
    load_dotenv(os.path.join(pwd, "configs", ".env"))    
