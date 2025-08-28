import os
import warnings

def get_api_config():
    return {
        'basic': {
            "config_list": [{
                "model": "gpt-4o",
                "api_key": os.environ.get("OPENAI_API_KEY"),
                "base_url": os.environ.get("OPENAI_BASE_URL"),
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
        },    
        "azure_openai": {
            "config_list": [{
                "model": os.environ.get("AZURE_OPENAI_MODEL"),
                "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
                "base_url": os.environ.get("AZURE_OPENAI_BASE_URL"),
                "api_type": "azure",
                "api_version": "2024-02-15-preview"
            }]
        },
        "openai": {
            "config_list": [{
                "model": "gpt-4o",
                "api_key": os.environ.get("OPENAI_API_KEY")
            }]
        },
        "deepseek": {
            "config_list": [{
                "model": "deepseek-v3",
                "api_key": os.environ.get("DEEPSEEK_API_KEY")
            }],
        },
        'claude': {
            "config_list": [{
                "model": "claude-3-5-sonnet-20240620",
                "api_key": os.environ.get("CLAUDE_API_KEY")
            }],
        }
    }

service_config = {
    "summary": get_api_config()["basic"],
    "deepsearch": get_api_config()["basic"],
    "code_explore": get_api_config()["basic"],
}


def validate_and_get_fallback_config(api_type: str = 'basic', service_type: str = ''):
    """
    Validate API key and provide fallback configuration if needed.
    
    Args:
        api_type: Type of API configuration to validate
        service_type: Specific service type configuration
        
    Returns:
        tuple: (config_name, api_config) - the actual config name used and its data
        
    Raises:
        ValueError: If no valid API key is found in any configuration
    """
    # First, try to get the requested configuration
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
        warnings.warn(f"⚠️  API key for '{config_source}' is None or empty. Searching for alternative configurations...")
        
        # Search for alternative valid configurations in get_api_config()
        for config_name, config_data in get_api_config().items():
            if config_name == api_type:
                continue  # Skip the already checked configuration
                
            config_list_alt = config_data.get("config_list", [])
            if not config_list_alt:
                continue
                
            alt_config = config_list_alt[0]
            alt_api_key = alt_config.get("api_key")
            
            # Check if it's a valid non-None API key
            if alt_api_key and alt_api_key.strip() != "":
                warnings.warn(f"✅ Found valid API key in '{config_name}' configuration. Using as fallback.")
                return config_name, config_data
        
        # Search for alternative valid configurations in service_config
        for service_name, service_config_data in service_config.items():
            if service_type and service_name == service_type:
                continue  # Skip the already checked service configuration
                
            service_config_list = service_config_data.get("config_list", [])
            if not service_config_list:
                continue
                
            service_alt_config = service_config_list[0]
            service_alt_api_key = service_alt_config.get("api_key")
            
            if service_alt_api_key and service_alt_api_key.strip() != "":
                warnings.warn(f"✅ Found valid API key in service '{service_name}' configuration. Using as fallback.")
                return f"service:{service_name}", service_config_data
        
        # If no valid configuration found
        raise ValueError(
            f"❌ No valid API key found in any configuration. "
            f"Please set up at least one valid API key in configs/oai_config.py or environment variables."
        )
    else:
        return config_source, api_config


def get_llm_config(api_type: str = 'basic', timeout: int = 240, temperature: float = 0.1, top_p=0.95, service_type: str = '', validate_api_key: bool = False):
    """
    Get LLM configuration with optional API key validation and fallback.
    
    Args:
        api_type: Type of API configuration to use
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
    if validate_api_key:
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
