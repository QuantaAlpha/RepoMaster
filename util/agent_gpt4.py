import os
import re
import json
import ast
from openai import AzureOpenAI, OpenAI
from typing import Annotated, Optional, Union, Dict, Any
from openai._types import NOT_GIVEN
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from functools import wraps

def create_response_format(schema: dict) -> dict:
    """
    根据给定的 schema 字典快速生成 OpenAI API 的 response_format 参数。

    参数 schema 示例:
    {
        "字段名": {"type": "数据类型", "description": "字段描述"},
        ...
    }
    """
    properties = {}
    for key, val in schema.items():
        prop = {"type": val["type"], "description": val["description"]}
        # 添加数组类型的items定义
        if val["type"] == "array" and "items" in val:
            prop["items"] = val["items"]
        properties[key] = prop

    json_schema = {
        "name": "response_jsons",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": list(schema.keys()),
            "additionalProperties": False
        }
    }

    return {
        "type": "json_schema", 
        "json_schema": json_schema
    }

def retry_with_exponential_backoff(
    max_retries: int = 2,
    base_delay: float = 2,
    max_delay: float = 2
):
    """
    指数退避重试装饰器
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=base_delay, max=max_delay),
            reraise=False
        )
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
            
        @wraps(func)
        def safe_wrapper(*args, **kwargs):
            try:
                return wrapper(*args, **kwargs)
            except RetryError as e:
                last_exception = e.last_attempt.exception()
                return f"在重试 {max_retries} 次后仍然失败。错误: {str(last_exception)}"
            except Exception as e:
                return f"发生未预期的错误: {str(e)}"
                
        return safe_wrapper
    return decorator

class AzureGPT4Chat:
    def __init__(
        self, 
        system_prompt="You are a helpfule assistant.",
        model_name=None,
        max_retries: int = 2,
        base_delay: float = 2,
        max_delay: float = 2
    ):
        # Try to initialize Azure client first, fall back to OpenAI if not available
        if os.getenv("AZURE_OPENAI_API_KEY"):
            self.client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
            self.deployment_name = model_name or os.getenv("AZURE_OPENAI_MODEL", 'gpt-4o')
            self.is_azure = True
        else:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.deployment_name = model_name or "gpt-4o"
            self.is_azure = False
            
        self.system_prompt = system_prompt
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def set_system_prompt(self, prompt):
        self.system_prompt = prompt

    @property
    def retry_decorator(self):
        """获取当前实例的重试装饰器"""
        return retry_with_exponential_backoff(
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay
        )

    def chat(self, question, system_prompt=None):
        _system_prompt = system_prompt if system_prompt is not None else self.system_prompt
        
        @self.retry_decorator
        def _chat():
            messages = [
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": question}
            ]
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages
            )
            return response.choices[0].message.content
        
        return _chat()
    
    def chat_with_message(self, message, model_name=None):
        _model = model_name if model_name is not None else self.deployment_name
        
        @self.retry_decorator
        def _chat_with_message():
            response = self.client.chat.completions.create(
                model=_model,
                messages=message
            )
            return response.choices[0].message.content
        
        return _chat_with_message()

    def chat_with_message_format(
        self, 
        question=None,
        system_prompt=None, 
        message_list=None,
        response_format=None
    ):
        """
        使用指定的输出格式进行对话
        
        Args:
            question (str): 用户问题
            response_format (dict): 响应格式,例如 {"type": "json_object"} 或 {"type": "text"}
            system_prompt (str, optional): 可选的系统提示
        """
        _system_prompt = system_prompt if system_prompt is not None else self.system_prompt
        _format = response_format if response_format else NOT_GIVEN
        
        @self.retry_decorator
        def _chat_with_message_format():
            if message_list is None:
                messages = [
                    {"role": "system", "content": _system_prompt},
                    {"role": "user", "content": question}
                ]
            else:
                messages = message_list
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                response_format=_format
            )
            return response.choices[0].message.content
        
        return _chat_with_message_format()

    def parse_llm_response(self, response_text: str) -> Dict:
        """
        Parse LLM response text into dictionary.
        """
        # Remove any markdown code block indicators
        response_text = re.sub(r"```(?:json|python)?\s*", "", response_text)
        response_text = response_text.strip("`")

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(response_text)
            except (SyntaxError, ValueError):
                result = {}
                pattern = r'["\']?(\w+)["\']?\s*:\s*([^,}\n]+)'
                matches = re.findall(pattern, response_text)
                for key, value in matches:
                    try:
                        result[key] = ast.literal_eval(value)
                    except (SyntaxError, ValueError):
                        result[key] = value.strip("\"'")
                return result

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("configs/.env")
    
    agent = AzureGPT4Chat()
    print(agent.chat("What is the maximum drawdown of NVIDIA's stock in 2024?"))