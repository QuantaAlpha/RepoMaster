import json
from typing import List, Dict, Any, Optional

from src.utils.agent_gpt4 import AzureGPT4Chat


def _build_system_prompt() -> str:
    return (
        "You are a code block execution planner.\n"
        "Input is a set of code blocks extracted from conversation, each containing index, language, code.\n"
        "\n"
        "Task description:\n"
        "1) Judge whether each code block is runnable and whether the language label matches the code (language_ok)\n"
        "2) Identify code block intent:\n"
        "   - env_setup: System dependencies/environment preparation (such as apt-get, pip install, etc.)\n"
        "   - direct_exec: Code to be executed directly (contains specific logic, will be executed directly by autogen)\n" 
        "   - script_run: Run script commands (such as python xxx.py)\n"
        "   - other: Other types\n"
        "3) Extract target file target_file:\n"
        "   - If Python code contains '# filename: xxx.py', then target_file=that filename\n"
        "   - If Shell code is like 'python xxx.py' or 'python3 xxx.py', then target_file=xxx.py\n"
        "4) Deduplication rules: If one code block is directly executable code (contains filename comment), another code block runs the same script, then keep the directly executable code and discard the run command\n"
        "   - Keep only one run command for the same script\n"
        "   - Keep only one code block with identical content\n"
        "5) Sorting rules: Intelligent sorting based on execution logic\n"
        "   - Environment preparation (env_setup) executes first\n"
        "   - Reasonably arrange other code blocks order based on dependencies and execution logic\n"
        "   - Such as: data preparation → data processing → result output\n"
        "   - Such as: generate dependent files first\n"
        "   - Such as: prioritize content that needs to be imported/defined first\n"
        "\n"
        "Output JSON format:\n"
        "{\n"
        '  "blocks": [\n'
        '    {"index": 0, "keep": true, "intent": "env_setup", "target_file": null},\n'
        '    {"index": 1, "keep": true, "intent": "direct_exec", "target_file": "convert.py"}\n'
        '  ],\n'
        '  "order": [0, 1]\n'
        "}\n"
        "\n"
        "Example 1 - Intelligent reordering (environment preparation + direct execution):\n"
        "Input: [\n"
        '  {"index": 0, "language": "python", "code": "# filename: convert.py\\nimport os\\nfrom spatie.pdf_to_text import Pdf\\nprint(\\"converting\\")"},\n'
        '  {"index": 1, "language": "sh", "code": "apt-get update && apt-get install -y poppler-utils"}\n'
        "]\n"
        "Output: {\n"
        '  "blocks": [{"index": 1, "keep": true, "intent": "env_setup", "target_file": null}, {"index": 0, "keep": true, "intent": "direct_exec", "target_file": "convert.py"}],\n'
        '  "order": [1, 0]\n'
        "}\n"
        "\n"
        "Example 2 - Direct execution + run script deduplication:\n"
        "Input: [\n"
        '  {"index": 0, "language": "python", "code": "# filename: test.py\\nprint(\\"test\\")"},\n'
        '  {"index": 1, "language": "sh", "code": "python test.py"}\n'
        "]\n"
        "Output: {\n"
        '  "blocks": [{"index": 0, "keep": true, "intent": "direct_exec", "target_file": "test.py"}, {"index": 1, "keep": false, "intent": "script_run", "target_file": "test.py"}],\n'
        '  "order": [0]\n'
        "}\n"
        "\n"
                "Only output JSON, no other text."
    )


def _build_user_prompt(raw_blocks: List[Dict[str, Any]]) -> str:
    return f"Code block list:\n{json.dumps(raw_blocks, ensure_ascii=False, indent=2)}\n\nPlease analyze and output JSON:"


def llm_judge_code_blocks(
    raw_blocks: List[Dict[str, Any]],
    message_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Use LLM to judge code block executability, language matching, deduplication and sorting.

    Args:
        raw_blocks: [{"index": int, "language": str, "code": str}, ...]
        message_list: Additional context (optional, can pass None if not needed).

    Returns:
        Dict containing blocks/order.
    """
    system_prompt = _build_system_prompt()

    if message_list is None:
        message_list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_prompt(raw_blocks)},
        ]
    else:
        # In case of passing custom message_list, ensure it contains system and user requirements
        message_list = list(message_list)
        message_list.insert(0, {"role": "system", "content": system_prompt})
        message_list.append({"role": "user", "content": _build_user_prompt(raw_blocks)})

    agent = AzureGPT4Chat()

    try:
        content = agent.chat_with_message(
            message=message_list,
            json_format=True
        )
        # chat_with_message returns parsed dict
        if isinstance(content, str):
            result = json.loads(content)
        else:
            result = content
            
        # Basic robustness: fill in missing keys
        if "blocks" not in result:
            result["blocks"] = []
        if "order" not in result:
            result["order"] = []
        return result
    except Exception as e:
        print(f"LLM judgment failed: {e}")
        # Fallback: keep all, in original order
        n = len(raw_blocks)
        return {
            "blocks": [
                {"index": i, "keep": True, "intent": "other", "target_file": None}
                for i in range(n)
            ],
            "order": list(range(n))
        }


def process_and_filter_code_blocks(code_blocks) -> List:
    """
    Process code blocks: use LLM for judgment, deduplication and sorting, return processed code block list.
    
    Args:
        code_blocks: Code block list extracted from autogen code_extractor
        
    Returns:
        List: Processed code block list (deduplicated, sorted)
    """
    if len(code_blocks) == 0:
        return []
    
    try:
        # Use LLM for code block judgment, deduplication and sorting
        raw_blocks = [
            {"index": i, "language": getattr(cb, "language", None), "code": getattr(cb, "code", None)}
            for i, cb in enumerate(code_blocks)
        ]
        judge = llm_judge_code_blocks(raw_blocks)
        
        # Parse judgment results
        blocks_info = {item.get("index"): item for item in judge.get("blocks", [])}
        ordered = judge.get("order", list(range(len(code_blocks))))
        keep_set = {idx for idx, info in blocks_info.items() if info.get("keep", True)}
        
        # If blocks_info is empty, default to keep all
        if not blocks_info:
            keep_set = set(range(len(code_blocks)))
        
        # Filter and reorder
        selected_indexes = [idx for idx in ordered if idx in keep_set and 0 <= idx < len(code_blocks)]
        
        # Deduplication (prevent LLM from outputting duplicate index)
        seen = set()
        selected_indexes = [idx for idx in selected_indexes if not (idx in seen or seen.add(idx))]
        
        if len(selected_indexes) == 0:
            return []
        
        return [code_blocks[idx] for idx in selected_indexes]
        
    except Exception as e:
        print(f"Code block processing failed: {e}")
        # Fallback: return original code block list
        return code_blocks 