import os
import re
import json
import ast
import time
import random
from openai import AzureOpenAI, OpenAI
from typing import Annotated, Optional, Union, Dict, Any, List, Callable
from openai._types import NOT_GIVEN
from configs.oai_config import get_llm_config

try:
    from autogen.oai import OpenAIWrapper
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False

def create_response_format(schema: dict) -> dict:
    """
    Quickly generate the response_format parameter for OpenAI API based on the given schema dictionary.

    Example schema parameter:
    {
        "field_name": {"type": "data_type", "description": "field_description"},
        ...
    }
    """
    properties = {}
    for key, val in schema.items():
        prop = {"type": val["type"], "description": val["description"]}
        # Add items definition for array type
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

class RetryHandler:
    """More flexible retry handler"""
    
    def __init__(self, max_retries: int = 2, base_delay: float = 1.0, max_delay: float = 10.0, 
                 exponential_base: float = 2.0, jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay time"""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        if self.jitter:
            delay *= (0.5 + random.random() * 0.5)  # Add 50% random jitter
        return delay
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    time.sleep(delay)
                    continue
                else:
                    break
        
        return f"Still failed after {self.max_retries} retries. Error: {str(last_exception)}"

class AzureGPT4Chat:
    def __init__(
        self, 
        system_prompt="You are a helpfule assistant.",
        model_name=None,
        config_list: Optional[List[Dict]] = None,
        max_retries: int = 2,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        **wrapper_kwargs
    ):
        if not AUTOGEN_AVAILABLE:
            raise ImportError("autogen package is not available. Please install it with: pip install pyautogen")
        
        # If no config_list is provided, try to build from environment variables
        if config_list is None:
            config_list = get_llm_config(api_type="basic")
        
        if 'config_list' in config_list:
            config_list = config_list['config_list']

        if 'model' in config_list[0] and model_name is None:
            model_name = config_list[0]['model']
        elif model_name is None:
            model_name = "gpt-4o"
        
        self.client = OpenAIWrapper(config_list=config_list, **wrapper_kwargs)
        self.deployment_name = model_name
        self.system_prompt = system_prompt
        
        # Initialize retry handler
        self.retry_handler = RetryHandler(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay
        )

    def set_system_prompt(self, prompt):
        self.system_prompt = prompt

    def chat(self, question: str, system_prompt: Optional[str] = None, json_format = None) -> str:
        """Chat method using RetryHandler"""
        _system_prompt = system_prompt if system_prompt is not None else self.system_prompt
        
        def _chat_call():
            messages = [
                {"role": "system", "content": _system_prompt},
                {"role": "user", "content": question}
            ]
            response = self.client.create(
                model=self.deployment_name,
                messages=messages
            )
            if json_format:
                return self.parse_llm_response(response.choices[0].message.content)
            return response.choices[0].message.content
        
        return self.retry_handler.execute_with_retry(_chat_call)
    
    def chat_with_message(self, message: List[Dict], model_name: Optional[str] = None, json_format = False) -> str:
        """Chat method using RetryHandler"""
        _model = model_name if model_name is not None else self.deployment_name
        
        def _chat_call():
            # Directly use original parameters to avoid decorator parameter passing issues
            response = self.client.create(
                model=_model,
                messages=message
            )
            if json_format:
                return self.parse_llm_response(response.choices[0].message.content)
            return response.choices[0].message.content
        
        return self.retry_handler.execute_with_retry(_chat_call)

    def chat_with_message_format(
        self, 
        question=None,
        system_prompt=None, 
        message_list=None,
        response_format=None,
        **create_kwargs
    ):
        """
        Chat with specified output format
        
        Args:
            question (str): User question
            response_format (dict): Response format, e.g. {"type": "json_object"} or {"type": "text"}
            system_prompt (str, optional): Optional system prompt
            **create_kwargs: Additional parameters passed to the create method
        """
        _system_prompt = system_prompt if system_prompt is not None else self.system_prompt
        
        def _chat_with_message_format():
            if message_list is None:
                messages = [
                    {"role": "system", "content": _system_prompt},
                    {"role": "user", "content": question}
                ]
            else:
                messages = message_list
            
            create_params = {
                "model": self.deployment_name,
                "messages": messages,
                **create_kwargs
            }
            
            if response_format:
                create_params["response_format"] = response_format
            
            response = self.client.create(**create_params)
            return response.choices[0].message.content
        
        return self.retry_handler.execute_with_retry(_chat_with_message_format)

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
    
    def get_usage_summary(self) -> Dict:
        """
        Get usage summary (if OpenAIWrapper supports it)
        
        Returns:
            Dict: Usage statistics
        """
        try:
            return self.client.get_usage()
        except AttributeError:
            return {"error": "OpenAIWrapper does not support usage statistics"}
    
    def clear_usage_summary(self):
        """Clear usage statistics (if OpenAIWrapper supports it)"""
        try:
            self.client.clear_usage_summary()
        except AttributeError:
            pass

if __name__ == "__main__":
    from dotenv import load_dotenv
    
    load_dotenv("configs/.env")
    
    agent = AzureGPT4Chat()
    print(agent.chat("What is the maximum drawdown of NVIDIA's stock in 2024?"))