import os

API_CONFIG = {
    'basic': {
        "config_list": [{
            "model": "gpt-4o",
            "api_key": "sk-1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "base_url": "http://claude0openai.a.pinggy.link/v1",
            # "base_url": "http://publicshare.a.pinggy.link/v1"
        }]
    },
    'basic_deepseek_r1': {
        "config_list": [{
            "model": "deepseek-r1-0528",
            "api_key": 'sk-KcNy1X5Pl33be23Rtjs2UKTsCBiD8cWM9YzK0g8tC4pRHcLm',
            "base_url": "https://api.ezai88.com/v1"
        }],
    },
    'basic_claude4': {
        "config_list": [{
            "model": "claude-sonnet-4-20250514",
            "api_key": 'sk-KcNy1X5Pl33be23Rtjs2UKTsCBiD8cWM9YzK0g8tC4pRHcLm',
            "base_url": "https://api.ezai88.com/v1"
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
    "summary": API_CONFIG["basic"],
    "deepsearch": API_CONFIG["basic"],
    "code_explore": API_CONFIG["basic"],
}


def get_llm_config(api_type: str = 'basic', timeout: int = 240, temperature: float = 0.1, top_p=0.95, service_type: str = ''):

    api_config = API_CONFIG[api_type]
    if service_type and service_type in service_config:
        api_config = service_config[service_type]
    api_config["timeout"] = timeout
    api_config["temperature"] = temperature
    api_config["top_p"] = top_p
    return api_config