import os

from dotenv import load_dotenv
load_dotenv()


def get_tokenizer_config():
    return {
        "model": "gpt-4o",
        "chunk_token_size": 2000
    }


def get_llm_config(timeout: int = 120, temperature: float = 0.5):
    # 尝试获取Azure配置，如果不存在则使用OpenAI配置
    if all(key in os.environ for key in ["AZURE_OPENAI_MODEL", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_BASE_URL"]):
        return {
            "config_list": [{
                "model": os.environ["AZURE_OPENAI_MODEL"],
                "api_key": os.environ["AZURE_OPENAI_API_KEY"],
                "base_url": os.environ["AZURE_OPENAI_BASE_URL"],
                "api_type": "azure",
                "api_version": "2024-02-15-preview"
                }
            ],
            "timeout": timeout,
            "temperature": temperature,
        }
    else:
        return {
            "config_list": [{
                "model": "gpt-4o",
                "api_key": os.environ["OPENAI_API_KEY"]
                }
            ],
            "timeout": timeout,
            "temperature": temperature,
        }

def get_claude_config():
    return {
        "config_list": [{
            "model": "claude-3-5-sonnet-latest",
            "api_key": os.environ["ANTHROPIC_API_KEY"],
            "api_type": "anthropic",
        }],
        "timeout": 120,
        "temperature": 0.5,
    }

def get_grok_config():
    return {
        "config_list": [{
            "model": "grok-3-beta",
            "base_url": "https://api.x.ai/v1",
            # "api_key": os.environ["XAI_API_KEY"],
            "api_key": "xai-EDLNVlgABTpgEllcde1FUMdA60hBQPaaGW81bQd5rYaAudWKS18BotXhhq9HxEGl0UlNNAoXuMIIMHkn",
        }],
    }

def load_envs_func():
    pwd = os.getcwd()
    load_dotenv(os.path.join(pwd, "configs", ".env"))    

def get_code_execution_config(workdir: str):
    return {
        "last_n_messages": 1,
        "work_dir": workdir,
        "use_docker": False
    }