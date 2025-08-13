from typing import List, Callable
from functools import wraps
from pandas import DataFrame
from autogen import register_function, ConversableAgent
import inspect


def stringify_output(func):
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        return result

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result

    # Return corresponding wrapper based on whether the function is a coroutine
    return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper


def register_toolkits(
    config: List[Callable],
    caller: ConversableAgent,
    executor: ConversableAgent,
    **kwargs
):
    """Register tools from a configuration list."""

    for tool in config:

        if isinstance(tool, type):
            register_tookits_from_cls(caller, executor, tool, **kwargs)
            continue

        tool_dict = {"function": tool} if callable(tool) else tool
        if "function" not in tool_dict or not callable(tool_dict["function"]):
            raise ValueError(
                "Function not found in tool configuration or not callable."
            )

        tool_function = tool_dict["function"]
        name = tool_dict.get("name", tool_function.__name__)
        description = tool_dict.get("description", tool_function.__doc__)
        register_function(
            stringify_output(tool_function),
            caller=caller,
            executor=executor,
            name=name,
            description=description,
        )



def register_tookits_from_cls(
    caller: ConversableAgent,
    executor: ConversableAgent,
    cls: type,
    include_private: bool = False,
):
    """Register all methods of a class as tools."""
    if include_private:
        funcs = [
            func
            for func in dir(cls)
            if callable(getattr(cls, func)) and not func.startswith("__")
        ]
    else:
        funcs = [
            func
            for func in dir(cls)
            if callable(getattr(cls, func))
            and not func.startswith("__")
            and not func.startswith("_")
        ]
    register_toolkits([getattr(cls, func) for func in funcs], caller, executor)
